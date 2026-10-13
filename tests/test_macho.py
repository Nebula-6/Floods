import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "docs"))

from stackipa import macho


def segment(name, fileoff, filesize, sections=()):
    size = 72 + 80 * len(sections)
    body = struct.pack("<II16sQQQQiiII", macho.LC_SEGMENT_64, size, name, 0, 0x4000, fileoff, filesize, 7, 5, len(sections), 0)
    for sect_name, offset, length in sections:
        body += struct.pack("<16s16sQQIIIIIIII", sect_name, name, 0, length, offset, 0, 0, 0, 0, 0, 0, 0)
    return body


def build_image(pad, with_signature=True, cryptid=None):
    text_offset = 32 + 4096 if pad is None else pad
    sig_off = 0x8000
    sig_size = 0x100
    cmds = [segment(b"__TEXT", 0, 0x4000, [(b"__text", text_offset, 16)])]
    cmds.append(segment(b"__LINKEDIT", 0x4000, sig_off + sig_size - 0x4000))
    cmds.append(macho.dylib_command(macho.LC_LOAD_DYLIB, "/usr/lib/libSystem.B.dylib"))
    if cryptid is not None:
        cmds.append(struct.pack("<IIIIII", macho.LC_ENCRYPTION_INFO_64, 24, 0, 0, cryptid, 0))
    if with_signature:
        cmds.append(struct.pack("<IIII", macho.LC_CODE_SIGNATURE, 16, sig_off, sig_size))
    blob = b"".join(cmds)
    header = struct.pack("<8I", macho.MH_MAGIC_64, 0x0100000C, 0, 6, len(cmds), len(blob), 0, 0)
    data = bytearray(sig_off + sig_size)
    data[:32] = header
    data[32:32 + len(blob)] = blob
    return bytes(data)


class MachOTests(unittest.TestCase):
    def write(self, data):
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.write(data)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_adds_dylib_and_rpath_and_drops_signature(self):
        path = self.write(build_image(2048))
        macho.prepare_for_injection(path, ["@rpath/A.dylib", "@rpath/B.dylib"], rpaths=("@executable_path/Frameworks",))
        image = macho.MachO(path)
        names = [n for _, n in image.dependencies()]
        self.assertEqual(names, ["/usr/lib/libSystem.B.dylib", "@rpath/A.dylib", "@rpath/B.dylib"])
        self.assertEqual(image.rpaths(), ["@executable_path/Frameworks"])
        self.assertFalse(image.has_signature())
        self.assertEqual(os.path.getsize(path), 0x8000)

    def test_linkedit_shrinks_with_signature(self):
        path = self.write(build_image(2048))
        macho.prepare_for_injection(path, ["@rpath/A.dylib"])
        image = macho.MachO(path)
        linkedit = [c for c in image.commands if bytes(c[8:24]).rstrip(b"\0") == b"__LINKEDIT"][0]
        self.assertEqual(struct.unpack_from("<Q", linkedit, 48)[0], 0x8000 - 0x4000)

    def test_idempotent(self):
        path = self.write(build_image(2048))
        macho.prepare_for_injection(path, ["@rpath/A.dylib"])
        macho.prepare_for_injection(path, ["@rpath/A.dylib"])
        names = [n for _, n in macho.MachO(path).dependencies()]
        self.assertEqual(names.count("@rpath/A.dylib"), 1)

    def test_not_enough_space(self):
        path = self.write(build_image(32 + 220))
        with self.assertRaises(macho.MachOError):
            macho.prepare_for_injection(path, ["@rpath/AVeryLongNameThatWillNotFitInTheHeader.dylib"] * 3)

    def test_rejects_encrypted(self):
        path = self.write(build_image(2048, cryptid=1))
        with self.assertRaises(macho.MachOError):
            macho.prepare_for_injection(path, ["@rpath/A.dylib"])

    def test_rejects_universal(self):
        path = self.write(struct.pack(">II", 0xCAFEBABE, 1) + b"\0" * 64)
        with self.assertRaises(macho.MachOError):
            macho.MachO(path)

    def test_set_install_name_and_change_dependency(self):
        data = bytearray(build_image(2048, with_signature=False))
        path = self.write(bytes(data))
        image = macho.MachO(path)
        image.commands.insert(2, bytearray(macho.dylib_command(macho.LC_ID_DYLIB, "/Library/x/y.dylib")))
        image.dirty = True
        image.commit()
        image = macho.MachO(path)
        self.assertTrue(image.set_install_name("@rpath/y.dylib"))
        self.assertTrue(image.change_dependency("/usr/lib/libSystem.B.dylib", "@rpath/Z"))
        image.commit()
        image = macho.MachO(path)
        self.assertEqual(image.install_name(), "@rpath/y.dylib")
        self.assertIn("@rpath/Z", [n for _, n in image.dependencies()])


if __name__ == "__main__":
    unittest.main()
