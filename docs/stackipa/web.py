import json

from .builder import BuildError, Options, build
from .debpkg import DebError
from .extras import BASE, FILES, ExtrasError, cache_root


def extras_plan():
    return json.dumps({"base": BASE, "root": cache_root(), "files": list(FILES)})


def run(job_json):
    job = json.loads(job_json)
    options = Options(
        ipa=job["ipa"],
        output=job["output"],
        eevee=job.get("eevee"),
        chroma=job.get("chroma"),
        order=tuple(job.get("order", ["eevee", "chroma"])),
        bundle_id=job.get("bundleId") or None,
        name=job.get("name") or None,
        strip_extensions=bool(job.get("stripExtensions")),
        force=bool(job.get("force")),
        dry_run=bool(job.get("dryRun")),
        compress=int(job.get("compress", 1)),
    )
    try:
        build(options)
    except (BuildError, DebError, ExtrasError) as error:
        print(f"error: {error}")
        return False
    return True
