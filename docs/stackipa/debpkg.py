import io
import os
import posixpath
import tarfile


class DebError(Exception):
    pass


def read_ar(path):
    members = {}
    with open(path, "rb") as f:
        if f.read(8) != b"!<arch>\n":
            raise DebError(f"{path}: not a .deb archive")
        while True:
            header = f.read(60)
            if len(header) < 60:
                break
            name = header[:16].decode().strip().rstrip("/")
            size = int(header[48:58].decode().strip())
            members[name] = f.read(size)
            if size % 2:
                f.read(1)
    return members


def open_tar(name, data):
    if name.endswith(".zst"):
        raise DebError(f"{name}: zstd-compressed packages are not supported, repack the .deb with xz or gzip")
    return tarfile.open(fileobj=io.BytesIO(data), mode="r:*")


def control_fields(members):
    for name, data in members.items():
        if name.startswith("control.tar"):
            with open_tar(name, data) as tar:
                for member in tar.getmembers():
                    if posixpath.basename(member.name) == "control" and member.isfile():
                        text = tar.extractfile(member).read().decode(errors="replace")
                        return parse_control(text)
    return {}


def parse_control(text):
    fields = {}
    for line in text.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def extract_data(path, destination):
    members = read_ar(path)
    fields = control_fields(members)
    data_name = next((n for n in members if n.startswith("data.tar")), None)
    if data_name is None:
        raise DebError(f"{path}: no data archive inside the package")
    os.makedirs(destination, exist_ok=True)
    root = os.path.realpath(destination)
    with open_tar(data_name, members[data_name]) as tar:
        for member in tar.getmembers():
            target = os.path.realpath(os.path.join(root, member.name))
            if target != root and not target.startswith(root + os.sep):
                raise DebError(f"{path}: unsafe path in archive: {member.name}")
            if member.issym() or member.islnk() or member.isdev():
                continue
            if member.isdir():
                os.makedirs(target, exist_ok=True)
            elif member.isfile():
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as out:
                    out.write(tar.extractfile(member).read())
    return fields


def find_file(root, name):
    for base, _, files in os.walk(root):
        if name in files:
            return os.path.join(base, name)
    return None


def find_dir(root, name):
    for base, dirs, _ in os.walk(root):
        if name in dirs:
            return os.path.join(base, name)
    return None
