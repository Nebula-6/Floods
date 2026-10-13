import os
import plistlib
import posixpath
import re
import shutil
import struct
import tempfile
import time
import zipfile
from dataclasses import dataclass, field

from . import debpkg, extras
from .macho import DYLIB_COMMANDS, LC_LOAD_WEAK_DYLIB, MachO, MachOError, is_fat, is_macho64, prepare_for_injection

CHROMA_INFO_KEYS = {
    "UIDesignRequiresCompatibility": False,
    "NSSupportsLiveActivities": True,
    "NSSupportsLiveActivitiesFrequentUpdates": True,
}

SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")
VERSION_PATTERN = re.compile(rb"(?<![\w.])9\.\d{1,2}\.\d{1,3}(?![\w.])")
SUBSTRATE_NAMES = ("substrate", "substitute", "ellekit")
CHUNK = 1 << 20


class BuildError(Exception):
    pass


@dataclass
class Tweak:
    label: str
    package: dict
    dylibs: list = field(default_factory=list)
    frameworks: list = field(default_factory=list)
    resources: list = field(default_factory=list)


@dataclass
class Options:
    ipa: str
    output: str
    eevee: str = None
    chroma: str = None
    order: tuple = ("eevee", "chroma")
    bundle_id: str = None
    name: str = None
    strip_extensions: bool = False
    keep_watch: bool = False
    extras_dir: str = None
    force: bool = False
    dry_run: bool = False
    compress: int = 6
    work_dir: str = None


def say(lines, text):
    lines.append(text)
    print(text, flush=True)


def locate_app(archive):
    roots = set()
    for name in archive.namelist():
        match = re.match(r"^(Payload/[^/]+\.app)/Info\.plist$", name)
        if match:
            roots.add(match.group(1) + "/")
    if len(roots) != 1:
        raise BuildError("the IPA must contain exactly one Payload/<name>.app/Info.plist")
    return roots.pop()


def collect_tweak(label, deb, stage):
    target = os.path.join(stage, label)
    package = debpkg.extract_data(deb, target)
    tweak = Tweak(label, package)
    for base, _, files in os.walk(target):
        for name in sorted(files):
            path = os.path.join(base, name)
            if name.endswith(".dylib") and "/DynamicLibraries" in base.replace(os.sep, "/"):
                tweak.dylibs.append(path)
    tweak.dylibs.sort()
    for base, dirs, _ in os.walk(target):
        for name in sorted(dirs):
            path = os.path.join(base, name)
            if name.endswith(".framework"):
                tweak.frameworks.append(path)
            elif name.endswith(".bundle"):
                tweak.resources.append(path)
    if not tweak.dylibs:
        raise BuildError(f"{deb}: no tweak dylib found under DynamicLibraries")
    return tweak


def supported_versions(dylib):
    with open(dylib, "rb") as f:
        return sorted({m.decode() for m in VERSION_PATTERN.findall(f.read())})


def is_system(path):
    return path.startswith(SYSTEM_PREFIXES)


def map_dependency(path, injected):
    base = posixpath.basename(path)
    if base in injected:
        return f"@rpath/{base}"
    lowered = base.lower()
    if any(token in lowered for token in SUBSTRATE_NAMES):
        return "@rpath/CydiaSubstrate.framework/CydiaSubstrate"
    return None


def prepare_dylib(source, stage, injected, lines):
    name = os.path.basename(source)
    if is_fat(source) or not is_macho64(source):
        raise BuildError(f"{name}: expected a thin arm64 dylib")
    path = os.path.join(stage, "inject", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copy2(source, path)
    image = MachO(path)
    image.drop_signature()
    image.set_install_name(f"@rpath/{name}")
    for kind, dep in image.dependencies():
        if is_system(dep) or dep.startswith("@rpath/"):
            continue
        replacement = map_dependency(dep, injected)
        if replacement is None:
            raise BuildError(f"{name}: dependency {dep} cannot be satisfied in a sideloaded app")
        image.change_dependency(dep, replacement)
        say(lines, f"  {name}: {dep} -> {replacement}")
    removed = image.remove_rpaths(lambda value: "/var/jb" in value or ".jbroot" in value or value.startswith("/Library"))
    if removed:
        say(lines, f"  {name}: removed {removed} jailbreak rpath(s)")
    image.commit()
    return path, MachO(path)


def required_extras(images):
    needed = []
    for image in images:
        for _, dep in image.dependencies():
            lowered = dep.lower()
            for key, (framework, requires) in extras.PROVIDES.items():
                if key in lowered:
                    for item in (framework,) + requires:
                        if item not in needed:
                            needed.append(item)
    if "Orion.framework" in needed and "CydiaSubstrate.framework" not in needed:
        needed.append("CydiaSubstrate.framework")
    return needed


def framework_name(path):
    return posixpath.basename(path.rstrip("/"))


def is_probably_system_rpath(dep):
    return posixpath.basename(dep).startswith("libswift")


def unresolved(images, provided):
    missing = []
    for owner, image in images:
        for kind, dep in image.dependencies():
            if not dep.startswith("@rpath/"):
                continue
            tail = dep[len("@rpath/"):]
            top = tail.split("/")[0]
            if top in provided or is_probably_system_rpath(dep):
                continue
            if kind == LC_LOAD_WEAK_DYLIB:
                continue
            missing.append((owner, dep))
    return missing


def patch_plist(raw, options, chroma_present, lines):
    info = plistlib.loads(raw)
    if chroma_present:
        info.update(CHROMA_INFO_KEYS)
        say(lines, "Info.plist: enabled Liquid Glass compatibility and Live Activity keys")
    if info.pop("UISupportedDevices", None) is not None:
        say(lines, "Info.plist: removed UISupportedDevices")
    if options.bundle_id:
        info["CFBundleIdentifier"] = options.bundle_id
        say(lines, f"Info.plist: bundle id set to {options.bundle_id}")
    if options.name:
        info["CFBundleDisplayName"] = options.name
        info["CFBundleName"] = options.name
        say(lines, f"Info.plist: name set to {options.name}")
    return plistlib.dumps(info, fmt=plistlib.FMT_XML)


def walk_files(root):
    for base, _, files in os.walk(root):
        for name in sorted(files):
            full = os.path.join(base, name)
            yield os.path.relpath(full, root).replace(os.sep, "/"), full


def is_executable(relative, full):
    return os.access(full, os.X_OK) or relative.endswith(".dylib")


def add_file(archive, name, source, executable, compress):
    info = zipfile.ZipInfo(name, time.localtime()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    with open(source, "rb") as src, archive.open(info, "w") as dst:
        shutil.copyfileobj(src, dst, CHUNK)


def copy_raw(source, entry, out):
    if entry.flag_bits & 0x1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        return False
    info = zipfile.ZipInfo(entry.filename, entry.date_time)
    info.compress_type = entry.compress_type
    info.external_attr = entry.external_attr
    info.create_system = entry.create_system
    info.flag_bits = entry.flag_bits & 0x800
    info.CRC = entry.CRC
    info.compress_size = entry.compress_size
    info.file_size = entry.file_size
    fp = source.fp
    fp.seek(entry.header_offset)
    local = fp.read(30)
    if len(local) != 30 or local[:4] != b"PK\x03\x04":
        return False
    name_len, extra_len = struct.unpack("<HH", local[26:30])
    fp.seek(entry.header_offset + 30 + name_len + extra_len)
    info.header_offset = out.fp.tell()
    out.fp.write(info.FileHeader(zip64=entry.file_size >= zipfile.ZIP64_LIMIT or entry.compress_size >= zipfile.ZIP64_LIMIT))
    remaining = entry.compress_size
    while remaining:
        chunk = fp.read(min(CHUNK, remaining))
        if not chunk:
            raise BuildError(f"{entry.filename}: archive is truncated")
        out.fp.write(chunk)
        remaining -= len(chunk)
    out.filelist.append(info)
    out.NameToInfo[info.filename] = info
    out.start_dir = out.fp.tell()
    out._didModify = True
    return True


def build(options):
    lines = []
    if not (options.eevee or options.chroma):
        raise BuildError("give at least one of --eevee or --chroma")
    for label in ("ipa", "eevee", "chroma"):
        value = getattr(options, label)
        if value and not os.path.isfile(value):
            raise BuildError(f"{value} does not exist")
    if os.path.abspath(options.output) == os.path.abspath(options.ipa):
        raise BuildError("the output must not overwrite the input IPA")

    work = tempfile.mkdtemp(prefix="stackipa-", dir=options.work_dir)
    try:
        return run(options, work, lines)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run(options, work, lines):
    stage = os.path.join(work, "stage")
    os.makedirs(stage)
    archive = zipfile.ZipFile(options.ipa)
    app = locate_app(archive)
    info = plistlib.loads(archive.read(app + "Info.plist"))
    executable = info.get("CFBundleExecutable")
    version = info.get("CFBundleShortVersionString", "unknown")
    say(lines, f"Spotify {version} ({info.get('CFBundleIdentifier')}), executable {executable}")
    if executable is None or app + executable not in archive.namelist():
        raise BuildError("could not find the main executable named in Info.plist")

    tweaks = {}
    if options.eevee:
        tweaks["eevee"] = collect_tweak("eevee", options.eevee, stage)
    if options.chroma:
        tweaks["chroma"] = collect_tweak("chroma", options.chroma, stage)
    for key, tweak in tweaks.items():
        say(lines, f"{key}: {tweak.package.get('Name', key)} {tweak.package.get('Version', '?')}, "
                   f"{len(tweak.dylibs)} dylib(s), {len(tweak.frameworks)} framework(s), {len(tweak.resources)} bundle(s)")

    if "chroma" in tweaks:
        found = set()
        for dylib in tweaks["chroma"].dylibs:
            found.update(supported_versions(dylib))
        say(lines, f"chroma declares Spotify versions: {', '.join(sorted(found)) or 'none found'}")
        if version not in found and not options.force:
            raise BuildError(
                f"Spotify {version} is not a version this Chroma build was made for ({', '.join(sorted(found)) or 'unknown'}); "
                "use a matching IPA or pass --force"
            )
    if "eevee" in tweaks:
        say(lines, "eevee does not declare supported versions; check its README for the Spotify version it targets")

    injected_names = {os.path.basename(d) for t in tweaks.values() for d in t.dylibs}
    prepared = []
    ordered = [k for k in options.order if k in tweaks] + [k for k in tweaks if k not in options.order]
    for key in ordered:
        for dylib in tweaks[key].dylibs:
            prepared.append((key, *prepare_dylib(dylib, stage, injected_names, lines)))

    framework_images = []
    framework_sources = {}
    for key in ordered:
        for fw in tweaks[key].frameworks:
            name = framework_name(fw)
            framework_sources[name] = fw
            binary = os.path.join(fw, name[:-len(".framework")])
            if os.path.isfile(binary) and is_macho64(binary):
                framework_images.append((name, MachO(binary)))

    all_images = [(os.path.basename(p), image) for _, p, image in prepared] + framework_images
    needed = required_extras([image for _, image in all_images])
    extras_root = None
    if needed:
        say(lines, f"fetching or verifying {', '.join(needed)}")
        extras_root = extras.ensure(options.extras_dir)

    existing_frameworks = {
        n[len(app + "Frameworks/"):].split("/")[0] for n in archive.namelist() if n.startswith(app + "Frameworks/")
    }
    provided = set(injected_names) | set(framework_sources) | set(needed) | existing_frameworks
    provided |= {n for n in existing_frameworks}
    gaps = unresolved(all_images, provided)
    for owner, dep in gaps:
        say(lines, f"warning: {owner} needs {dep}, which is not provided")

    exe_path = os.path.join(stage, "main", executable)
    os.makedirs(os.path.dirname(exe_path))
    with archive.open(app + executable) as src, open(exe_path, "wb") as dst:
        shutil.copyfileobj(src, dst, CHUNK)
    if is_fat(exe_path):
        raise BuildError("the Spotify executable is a universal binary; thin it to arm64 first")
    try:
        image = prepare_for_injection(
            exe_path,
            [f"@rpath/{os.path.basename(p)}" for _, p, _ in prepared],
            rpaths=("@executable_path/Frameworks",),
        )
    except MachOError as error:
        raise BuildError(str(error)) from error
    say(lines, "main executable now loads: " + ", ".join(
        os.path.basename(name) for _, name in image.dependencies() if name.startswith("@rpath/")
    ))
    say(lines, f"header space left: {image.free_space} bytes")

    plist_bytes = patch_plist(archive.read(app + "Info.plist"), options, "chroma" in tweaks, lines)

    replaced = {app + "Info.plist", app + executable}
    additions = []
    for _, path, _ in prepared:
        additions.append((f"{app}Frameworks/{os.path.basename(path)}", path, True))
    for name, fw in framework_sources.items():
        for relative, full in walk_files(fw):
            if relative.startswith("Modules/") or relative.endswith((".swiftmodule", ".swiftdoc", ".swiftinterface")):
                continue
            additions.append((f"{app}Frameworks/{name}/{relative}", full, is_executable(relative, full)))
    for name in needed:
        for relative, full in extras.framework_files(extras_root, name):
            additions.append((f"{app}Frameworks/{relative}", full, relative == f"{name}/{name[:-len('.framework')]}"))
    for key in ordered:
        for bundle in tweaks[key].resources:
            name = framework_name(bundle)
            for relative, full in walk_files(bundle):
                additions.append((f"{app}{name}/{relative}", full, False))

    new_names = {n for n, _, _ in additions}
    skip_prefixes = []
    if not options.keep_watch:
        skip_prefixes += [app + "Watch/", app + "com.apple.WatchPlaceholder/"]
    if options.strip_extensions:
        skip_prefixes.append(app + "PlugIns/")

    say(lines, f"adding {len(additions)} file(s) to {app}")
    if options.dry_run:
        say(lines, "dry run: no output written")
        return lines

    out_tmp = options.output + ".part"
    try:
        with zipfile.ZipFile(out_tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=options.compress) as out:
            for entry in archive.infolist():
                if entry.filename in replaced or entry.filename in new_names:
                    continue
                if any(entry.filename.startswith(p) for p in skip_prefixes):
                    continue
                if copy_raw(archive, entry, out):
                    continue
                copy = zipfile.ZipInfo(entry.filename, entry.date_time)
                copy.compress_type = entry.compress_type
                copy.external_attr = entry.external_attr
                copy.create_system = entry.create_system
                if entry.is_dir():
                    out.writestr(copy, b"")
                    continue
                with archive.open(entry) as src, out.open(copy, "w") as dst:
                    shutil.copyfileobj(src, dst, CHUNK)
            plist_info = zipfile.ZipInfo(app + "Info.plist", time.localtime()[:6])
            plist_info.compress_type = zipfile.ZIP_DEFLATED
            plist_info.external_attr = 0o100644 << 16
            out.writestr(plist_info, plist_bytes)
            add_file(out, app + executable, exe_path, True, options.compress)
            os.remove(exe_path)
            for name, full, executable_flag in additions:
                add_file(out, name, full, executable_flag, options.compress)
        os.replace(out_tmp, options.output)
    finally:
        if os.path.exists(out_tmp):
            os.remove(out_tmp)
    say(lines, f"wrote {options.output}")
    return lines
