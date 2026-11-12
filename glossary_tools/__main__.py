"""python -m glossary_tools validate | build | new <category> <id>"""

import argparse
import sys
from datetime import date
from pathlib import Path

from .core import DEFAULT_DB_SCHEMA, GLOSSARY, ROOT, build, validate


def cmd_validate(args) -> int:
    g = validate(Path(args.glossary), Path(args.db_schema) if args.db_schema else None)
    for issue in g.issues:
        if issue.level == "error" or not args.quiet:
            print(issue)
    print(f"\n{len(g.terms)} terms, {len(g.categories)} categories, "
          f"{len(g.errors)} error(s), {len(g.issues) - len(g.errors)} warning(s)")
    return 1 if g.errors else 0


def cmd_build(args) -> int:
    g = validate(Path(args.glossary), Path(args.db_schema) if args.db_schema else None)
    if g.errors:
        for issue in g.errors:
            print(issue)
        print(f"\nnot built: {len(g.errors)} error(s); run 'validate' for details")
        return 1
    for name, path in build(g, Path(args.out)).items():
        print(f"{name:11} {path}")
    print(f"{len(g.terms)} terms -> {args.out}")
    return 0


def cmd_pdf(args) -> int:
    from .pdf import build_pdf

    g = validate(Path(args.glossary), Path(args.db_schema) if args.db_schema else None)
    if g.errors:
        for issue in g.errors:
            print(issue)
        print(f"\nno PDF: {len(g.errors)} error(s); run 'validate' for details")
        return 1
    path = build_pdf(g, Path(args.out), include_drafts=not args.approved_only)
    print(f"PDF -> {path}")
    return 0


def cmd_new(args) -> int:
    folder = Path(args.glossary) / args.category
    if not (folder / "_category.yaml").exists():
        print(f"category '{args.category}' does not exist (no {folder / '_category.yaml'})")
        return 1
    target = folder / f"{args.id}.yaml"
    if target.exists():
        print(f"{target} already exists")
        return 1
    today = date.today().isoformat()
    text = (ROOT / "templates" / "term.yaml").read_text(encoding="utf-8")
    text = (text.replace('id: ""  ', f'id: {args.id}  ', 1)
                .replace('category: ""  ', f'category: {args.category}  ', 1)
                .replace('created: ""  ', f'created: "{today}"  ', 1)
                .replace('updated: ""  ', f'updated: "{today}"  ', 1))
    target.write_text(text, encoding="utf-8")
    print(f"created {target}: fill it in and run 'validate'")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m glossary_tools")
    p.add_argument("--glossary", default=str(GLOSSARY), help="glossary folder (default: glossary/)")
    p.add_argument("--db-schema", default=str(DEFAULT_DB_SCHEMA) if DEFAULT_DB_SCHEMA.exists() else "",
                   help="snf-db-app backend/schema_v2.json, to check db_mapping (skipped if empty)")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="check every term and category")
    v.add_argument("-q", "--quiet", action="store_true", help="show errors only")
    v.set_defaults(func=cmd_validate)
    b = sub.add_parser("build", help="compile the glossary to JSON for APIs (dist/)")
    b.add_argument("--out", default=str(ROOT / "dist"))
    b.set_defaults(func=cmd_build)
    d = sub.add_parser("pdf", help="render the glossary as a PDF (dist/glossary.pdf)")
    d.add_argument("--out", default=str(ROOT / "dist" / "glossary.pdf"))
    d.add_argument("--approved-only", action="store_true", help="leave out draft, review and deprecated terms")
    d.set_defaults(func=cmd_pdf)
    n = sub.add_parser("new", help="create a term file from the template")
    n.add_argument("category", help="folder path, e.g. sf-dissolution")
    n.add_argument("id", help="term id, e.g. fiap")
    n.set_defaults(func=cmd_new)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
