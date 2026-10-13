import hashlib
import os
import urllib.request

COMMIT = "740d3716dcd98c20c000f12cdb88f1f0b2a533a4"
BASE = f"https://raw.githubusercontent.com/asdfzxcvbn/pyzule-rw/{COMMIT}/cyan/extras"

FILES = {
    "Orion.framework/Orion": "290889165a4d156a41ed29c88015083e40b5101153e52fa462f2a25d4942a4e8",
    "Orion.framework/Info.plist": "b3b9ce166f994293d94ed46a81476df2c78db7c25cf076d29571721aaceeb375",
    "CydiaSubstrate.framework/CydiaSubstrate": "bca859c9413cb85ca0d3ecfca494c61d67e4acd5846660e618526a152963965b",
    "CydiaSubstrate.framework/Info.plist": "0ebfa285140432c6a5a713a186c3049dd87ce6fc97f46be7b6872332773e408d",
    "CydiaSubstrate.framework/LICENSE": "ac3842df55783a43c093806730c480cecdd3c011dfb7fd001ec1ed5258fb0c08",
}

PROVIDES = {
    "orion": ("Orion.framework", ("CydiaSubstrate.framework",)),
    "substrate": ("CydiaSubstrate.framework", ()),
}


class ExtrasError(Exception):
    pass


def cache_root():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "stackipa", COMMIT[:12])


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(relative, destination):
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    request = urllib.request.Request(f"{BASE}/{relative}", headers={"User-Agent": "stackipa"})
    with urllib.request.urlopen(request, timeout=60) as response, open(destination + ".part", "wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    os.replace(destination + ".part", destination)


def ensure(directory=None):
    root = directory or cache_root()
    for relative, expected in FILES.items():
        path = os.path.join(root, relative)
        if os.path.isfile(path) and (directory or digest(path) == expected):
            continue
        if directory:
            raise ExtrasError(f"{path} is missing from --extras-dir")
        try:
            fetch(relative, path)
        except OSError as error:
            raise ExtrasError(f"could not download {relative}: {error}") from error
        if digest(path) != expected:
            os.remove(path)
            raise ExtrasError(f"checksum mismatch for {relative}")
    return root


def framework_files(root, framework):
    prefix = framework + "/"
    return [(relative, os.path.join(root, relative)) for relative in FILES if relative.startswith(prefix)]
