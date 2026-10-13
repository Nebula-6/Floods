import os
import struct

MH_MAGIC_64 = 0xFEEDFACF
FAT_MAGICS = (0xCAFEBABE, 0xBEBAFECA, 0xCAFEBABF, 0xBFBAFECA)

LC_SEGMENT_64 = 0x19
LC_LOAD_DYLIB = 0x0C
LC_ID_DYLIB = 0x0D
LC_LOAD_WEAK_DYLIB = 0x80000018
LC_REEXPORT_DYLIB = 0x8000001F
LC_LAZY_LOAD_DYLIB = 0x20
LC_LOAD_UPWARD_DYLIB = 0x80000023
LC_RPATH = 0x8000001C
LC_CODE_SIGNATURE = 0x1D
LC_ENCRYPTION_INFO_64 = 0x2C

DYLIB_COMMANDS = (
    LC_LOAD_DYLIB,
    LC_LOAD_WEAK_DYLIB,
    LC_REEXPORT_DYLIB,
    LC_LAZY_LOAD_DYLIB,
    LC_LOAD_UPWARD_DYLIB,
)

HEADER_SIZE = 32
PAGE = 0x4000


class MachOError(Exception):
    pass


def align8(n):
    return (n + 7) & ~7


def is_fat(path):
    with open(path, "rb") as f:
        magic = f.read(4)
    return len(magic) == 4 and struct.unpack(">I", magic)[0] in (0xCAFEBABE, 0xCAFEBABF)


def is_macho64(path):
    with open(path, "rb") as f:
        magic = f.read(4)
    return len(magic) == 4 and struct.unpack("<I", magic)[0] == MH_MAGIC_64


def dylib_command(kind, path, current=0x10000, compat=0x10000, timestamp=2):
    raw = path.encode() + b"\0"
    size = align8(24 + len(raw))
    return struct.pack("<IIIIII", kind, size, 24, timestamp, current, compat) + raw.ljust(size - 24, b"\0")


def rpath_command(path):
    raw = path.encode() + b"\0"
    size = align8(12 + len(raw))
    return struct.pack("<III", LC_RPATH, size, 12) + raw.ljust(size - 12, b"\0")


def cstring(blob, offset):
    end = blob.index(b"\0", offset)
    return blob[offset:end].decode()


class MachO:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            head = f.read(HEADER_SIZE)
            if len(head) < HEADER_SIZE:
                raise MachOError(f"{path}: too small to be a Mach-O file")
            magic = struct.unpack("<I", head[:4])[0]
            if struct.unpack(">I", head[:4])[0] in (0xCAFEBABE, 0xCAFEBABF):
                raise MachOError(f"{path}: universal binary, thin it to arm64 first")
            if magic != MH_MAGIC_64:
                raise MachOError(f"{path}: not a 64-bit little-endian Mach-O file")
            self.header = list(struct.unpack("<8I", head))
            ncmds, sizeofcmds = self.header[4], self.header[5]
            blob = f.read(sizeofcmds)
            if len(blob) != sizeofcmds:
                raise MachOError(f"{path}: truncated load commands")
            f.seek(0, os.SEEK_END)
            self.file_size = f.tell()
        self.original_sizeofcmds = sizeofcmds
        self.commands = []
        pos = 0
        for _ in range(ncmds):
            cmd, size = struct.unpack_from("<II", blob, pos)
            if size < 8 or pos + size > len(blob):
                raise MachOError(f"{path}: corrupt load command")
            self.commands.append(bytearray(blob[pos:pos + size]))
            pos += size
        self.limit = self.content_start()
        self.dirty = False
        self.truncate_to = None

    def content_start(self):
        smallest = self.file_size
        for cmd in self.commands:
            if struct.unpack_from("<I", cmd)[0] != LC_SEGMENT_64:
                continue
            nsects = struct.unpack_from("<I", cmd, 64)[0]
            for i in range(nsects):
                base = 72 + i * 80
                size = struct.unpack_from("<Q", cmd, base + 40)[0]
                offset = struct.unpack_from("<I", cmd, base + 48)[0]
                if offset and size:
                    smallest = min(smallest, offset)
        return smallest

    @property
    def free_space(self):
        used = sum(len(c) for c in self.commands)
        return self.limit - HEADER_SIZE - used

    def kind(self, cmd):
        return struct.unpack_from("<I", cmd)[0]

    def dylib_name(self, cmd):
        return cstring(bytes(cmd), struct.unpack_from("<I", cmd, 8)[0])

    def encrypted(self):
        for cmd in self.commands:
            if self.kind(cmd) == LC_ENCRYPTION_INFO_64:
                return struct.unpack_from("<I", cmd, 16)[0] != 0
        return False

    def install_name(self):
        for cmd in self.commands:
            if self.kind(cmd) == LC_ID_DYLIB:
                return self.dylib_name(cmd)
        return None

    def dependencies(self):
        out = []
        for cmd in self.commands:
            kind = self.kind(cmd)
            if kind in DYLIB_COMMANDS:
                out.append((kind, self.dylib_name(cmd)))
        return out

    def rpaths(self):
        out = []
        for cmd in self.commands:
            if self.kind(cmd) == LC_RPATH:
                out.append(cstring(bytes(cmd), struct.unpack_from("<I", cmd, 8)[0]))
        return out

    def has_signature(self):
        return any(self.kind(c) == LC_CODE_SIGNATURE for c in self.commands)

    def replace(self, index, blob):
        self.commands[index] = bytearray(blob)
        self.dirty = True

    def set_install_name(self, name):
        for i, cmd in enumerate(self.commands):
            if self.kind(cmd) == LC_ID_DYLIB:
                current, compat = struct.unpack_from("<II", cmd, 16)
                stamp = struct.unpack_from("<I", cmd, 12)[0]
                self.replace(i, dylib_command(LC_ID_DYLIB, name, current, compat, stamp))
                return True
        return False

    def change_dependency(self, old, new):
        changed = False
        for i, cmd in enumerate(self.commands):
            kind = self.kind(cmd)
            if kind in DYLIB_COMMANDS and self.dylib_name(cmd) == old:
                stamp, current, compat = struct.unpack_from("<III", cmd, 12)
                self.replace(i, dylib_command(kind, new, current, compat, stamp))
                changed = True
        return changed

    def remove_rpaths(self, predicate):
        kept = []
        removed = 0
        for cmd in self.commands:
            if self.kind(cmd) == LC_RPATH:
                value = cstring(bytes(cmd), struct.unpack_from("<I", cmd, 8)[0])
                if predicate(value):
                    removed += 1
                    continue
            kept.append(cmd)
        if removed:
            self.commands = kept
            self.dirty = True
        return removed

    def add_dylib(self, path, weak=True):
        if any(name == path for _, name in self.dependencies()):
            return False
        kind = LC_LOAD_WEAK_DYLIB if weak else LC_LOAD_DYLIB
        self.commands.append(bytearray(dylib_command(kind, path)))
        self.dirty = True
        return True

    def add_rpath(self, path):
        if path in self.rpaths():
            return False
        self.commands.append(bytearray(rpath_command(path)))
        self.dirty = True
        return True

    def drop_signature(self):
        index = None
        for i, cmd in enumerate(self.commands):
            if self.kind(cmd) == LC_CODE_SIGNATURE:
                index = i
        if index is None:
            return False
        dataoff, datasize = struct.unpack_from("<II", self.commands[index], 8)
        del self.commands[index]
        self.dirty = True
        if dataoff and dataoff + datasize >= self.file_size:
            self.truncate_to = dataoff
        return True

    def commit(self):
        if not self.dirty:
            return
        if self.free_space < 0:
            raise MachOError(
                f"{self.path}: not enough header space for the new load commands "
                f"({-self.free_space} bytes short)"
            )
        truncate_to = self.truncate_to
        if truncate_to is not None:
            self.fix_linkedit(truncate_to)
        total = sum(len(c) for c in self.commands)
        self.header[4] = len(self.commands)
        self.header[5] = total
        region = b"".join(bytes(c) for c in self.commands)
        region = region.ljust(max(self.original_sizeofcmds, total), b"\0")
        with open(self.path, "r+b") as f:
            f.write(struct.pack("<8I", *self.header))
            f.write(region)
            if truncate_to is not None:
                f.truncate(truncate_to)
        self.dirty = False

    def fix_linkedit(self, end):
        for cmd in self.commands:
            if self.kind(cmd) != LC_SEGMENT_64:
                continue
            if bytes(cmd[8:24]).rstrip(b"\0") != b"__LINKEDIT":
                continue
            fileoff = struct.unpack_from("<Q", cmd, 40)[0]
            newsize = max(end - fileoff, 0)
            struct.pack_into("<Q", cmd, 32, (newsize + PAGE - 1) // PAGE * PAGE)
            struct.pack_into("<Q", cmd, 48, newsize)
            return


def prepare_for_injection(path, additions, rpaths=(), weak=True):
    image = MachO(path)
    if image.encrypted():
        raise MachOError(f"{path}: binary is still FairPlay-encrypted, a decrypted IPA is required")
    image.drop_signature()
    for rp in rpaths:
        image.add_rpath(rp)
    for name in additions:
        image.add_dylib(name, weak=weak)
    image.commit()
    return image
