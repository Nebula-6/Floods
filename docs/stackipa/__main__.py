import argparse
import sys

from .builder import BuildError, Options, build
from .debpkg import DebError
from .extras import ExtrasError


def parse(argv):
    parser = argparse.ArgumentParser(prog="stackipa")
    parser.add_argument("--ipa", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--eevee")
    parser.add_argument("--chroma")
    parser.add_argument("--order", default="eevee,chroma")
    parser.add_argument("--bundle-id")
    parser.add_argument("--name")
    parser.add_argument("--strip-extensions", action="store_true")
    parser.add_argument("--keep-watch", action="store_true")
    parser.add_argument("--extras-dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compress", type=int, default=6, choices=range(0, 10))
    parser.add_argument("--work-dir")
    parser.add_argument("--sideload-fix")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(sys.argv[1:] if argv is None else argv)
    order = tuple(part.strip() for part in args.order.split(",") if part.strip())
    options = Options(
        ipa=args.ipa,
        output=args.output,
        eevee=args.eevee,
        chroma=args.chroma,
        order=order,
        bundle_id=args.bundle_id,
        name=args.name,
        strip_extensions=args.strip_extensions,
        keep_watch=args.keep_watch,
        extras_dir=args.extras_dir,
        force=args.force,
        dry_run=args.dry_run,
        compress=args.compress,
        work_dir=args.work_dir,
        sideload_fix=args.sideload_fix,
    )
    try:
        build(options)
    except (BuildError, DebError, ExtrasError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
