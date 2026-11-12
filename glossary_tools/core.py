"""Load, validate and compile the glossary (glossary/**/<id>.yaml + _category.yaml per folder)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "glossary"
SCHEMA_DIR = ROOT / "schema"
CATEGORY_FILE = "_category.yaml"
DEFAULT_DB_SCHEMA = ROOT.parent / "spent_nuclear_fuel_db" / "snf-db-app" / "backend" / "schema_v2.json"


@dataclass
class Issue:
    level: str          # "error" or "warning"
    path: str           # file relative to the repo root
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.path}: {self.message}"


@dataclass
class Glossary:
    root: Path
    categories: dict[str, dict] = field(default_factory=dict)   # "sf-dissolution" -> data
    terms: dict[str, dict] = field(default_factory=dict)        # id -> data
    files: dict[str, Path] = field(default_factory=dict)        # id or category path -> file
    issues: list[Issue] = field(default_factory=list)

    def rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.root.parent).as_posix()
        except ValueError:
            return path.as_posix()

    def add(self, level: str, path: Path, message: str) -> None:
        self.issues.append(Issue(level, self.rel(path), message))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]


def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8")))


def _read_yaml(path: Path, g: Glossary):
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        g.add("error", path, f"not valid YAML: {exc}")
        return None
    if not isinstance(data, dict):
        g.add("error", path, "the file must contain a YAML mapping (key: value lines)")
        return None
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in data.items()}   # unquoted dates


def _schema_errors(validator: Draft202012Validator, data: dict, path: Path, g: Glossary) -> None:
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in err.path) or "(file)"
        g.add("error", path, f"{where}: {err.message}")


def load(root: Path = GLOSSARY) -> Glossary:
    """Read every category and term file under root, checking each against its JSON schema."""
    g = Glossary(root)
    cat_schema, term_schema = _schema("category.schema.json"), _schema("term.schema.json")
    if not root.exists():
        g.add("error", root, "glossary folder not found")
        return g
    for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
        cat_path = folder.relative_to(root).as_posix()
        cat_file = folder / CATEGORY_FILE
        if not cat_file.exists():
            g.add("error", folder, f"folder without {CATEGORY_FILE}: every category needs one (see templates/)")
            continue
        data = _read_yaml(cat_file, g)
        if data is None:
            continue
        _schema_errors(cat_schema, data, cat_file, g)
        if data.get("id") != folder.name:
            g.add("error", cat_file, f"id '{data.get('id')}' must equal the folder name '{folder.name}'")
        g.categories[cat_path] = data
        g.files[cat_path] = cat_file
    for path in sorted(root.rglob("*.yaml")):
        if path.name == CATEGORY_FILE:
            continue
        if path.parent == root:
            g.add("error", path, "terms must be inside a category folder, not directly in glossary/")
            continue
        data = _read_yaml(path, g)
        if data is None:
            continue
        _schema_errors(term_schema, data, path, g)
        tid = data.get("id")
        if tid != path.stem:
            g.add("error", path, f"id '{tid}' must equal the file name '{path.stem}'")
        expected = path.parent.relative_to(root).as_posix()
        if data.get("category") != expected:
            g.add("error", path, f"category '{data.get('category')}' must be the folder path '{expected}'")
        if not isinstance(tid, str):
            continue
        if tid in g.terms:
            g.add("error", path, f"duplicated id '{tid}', also in {g.rel(g.files[tid])}")
            continue
        g.terms[tid] = data
        g.files[tid] = path
    return g


def _labels(term: dict) -> list[str]:
    out = [term.get("term"), term.get("abbreviation")]
    out += [s.get("label") for s in term.get("synonyms") or [] if s.get("type") != "deprecated"]
    return [x for x in out if x]


def db_fields(db_schema: Path | None) -> dict[str, set[str]] | None:
    """table -> field names from snf-db-app backend/schema_v2.json (None if the file is not available)."""
    if not db_schema or not db_schema.exists():
        return None
    tables = json.loads(db_schema.read_text(encoding="utf-8"))["TABLES"]
    out = {}
    for name, t in tables.items():
        cols = set(t.get("fields", {})) | set(t.get("pk", []))
        for fk in t.get("fk", {}):
            cols |= set(fk.split(","))
        out[name] = cols
    return out


# relation -> the relation the other term should list back (only for hierarchical pairs)
INVERSE = {"broader": "narrower", "narrower": "broader", "part-of": "has-part", "has-part": "part-of"}


def check(g: Glossary, db_schema: Path | None = DEFAULT_DB_SCHEMA) -> Glossary:
    """Cross-file rules that a JSON schema cannot express."""
    known = set(g.terms)
    tables = db_fields(db_schema)
    seen_labels: dict[str, str] = {}
    for tid, t in g.terms.items():
        path = g.files[tid]
        for r in t.get("related_terms") or []:
            other, rel = r.get("id"), r.get("relation")
            if other == tid:
                g.add("error", path, f"related term '{other}' points to itself")
            elif other not in known:
                g.add("warning", path, f"related term '{other}' is not a term yet")
            elif rel in INVERSE and not any(x.get("id") == tid and x.get("relation") == INVERSE[rel]
                                            for x in g.terms[other].get("related_terms") or []):
                g.add("warning", path, f"'{other}' is {rel} but does not list '{tid}' as {INVERSE[rel]}")
        if not t.get("authors"):
            g.add("warning", path, "authors is empty: add who wrote the entry")

        status = t.get("status")
        if status == "deprecated" and t.get("replaced_by") and t["replaced_by"] not in known:
            g.add("error", path, f"replaced_by '{t['replaced_by']}' does not exist")
        if status == "approved":
            if not t.get("reviewers"):
                g.add("error", path, "an approved term needs at least one reviewer")
            if not t.get("references") and not t.get("standards"):
                g.add("error", path, "an approved term needs at least one reference or standard")
        if status != "deprecated" and t.get("replaced_by"):
            g.add("warning", path, "replaced_by is only used when status is deprecated")

        if t.get("created") and t.get("updated") and str(t["updated"]) < str(t["created"]):
            g.add("error", path, "updated is earlier than created")
        ref_ids = [r.get("id") for r in t.get("references") or [] if r.get("id")]
        if len(ref_ids) != len(set(ref_ids)):
            g.add("error", path, "two references share the same id")
        rng = t.get("typical_range") or {}
        if rng.get("min") is not None and rng.get("max") is not None and rng["min"] > rng["max"]:
            g.add("error", path, "typical_range min is greater than max")
        cited = [rng.get("reference")] + [e.get("reference") for e in t.get("examples") or []]
        for ref in filter(None, cited):
            if ref not in ref_ids:
                g.add("error", path, f"reference '{ref}' is not in this term's references")
        for m in t.get("db_mapping") or []:
            if tables is None:
                break
            if m.get("table") not in tables:
                g.add("error", path, f"db_mapping table '{m.get('table')}' does not exist in the SNF DB")
            elif m.get("field") not in tables[m["table"]]:
                g.add("error", path, f"db_mapping field '{m.get('field')}' is not a column of {m['table']}")

        for label in _labels(t):
            key = label.casefold()
            if key in seen_labels and seen_labels[key] != tid:
                g.add("warning", path, f"label '{label}' is also used by '{seen_labels[key]}'")
            seen_labels.setdefault(key, tid)
    return g


def validate(root: Path = GLOSSARY, db_schema: Path | None = DEFAULT_DB_SCHEMA) -> Glossary:
    return check(load(root), db_schema)


def _tree(g: Glossary) -> list[dict]:
    nodes = {p: {"path": p, **c, "children": [], "terms": []} for p, c in g.categories.items()}
    top = []
    for p, node in sorted(nodes.items()):
        parent = p.rsplit("/", 1)[0] if "/" in p else None
        (nodes[parent]["children"] if parent in nodes else top).append(node)
    for tid, t in sorted(g.terms.items()):
        if t.get("category") in nodes:
            nodes[t["category"]]["terms"].append(tid)
    for node in nodes.values():
        node["children"].sort(key=lambda n: (n.get("order", 0), n["id"]))
    return sorted(top, key=lambda n: (n.get("order", 0), n["id"]))


def build(g: Glossary, out: Path) -> dict[str, Path]:
    """Write the static API: everything a web service or the SNF app needs, as plain JSON files."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "terms").mkdir(exist_ok=True)
    terms = [g.terms[t] for t in sorted(g.terms)]
    labels: dict[str, list[str]] = {}
    fields: dict[str, list[str]] = {}
    for t in terms:
        for label in _labels(t):
            labels.setdefault(label.casefold(), []).append(t["id"])
        for m in t.get("db_mapping") or []:
            fields.setdefault(f"{m['table']}.{m['field']}", []).append(t["id"])
        (out / "terms" / f"{t['id']}.json").write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
    written = {
        "glossary": out / "glossary.json",
        "categories": out / "categories.json",
        "labels": out / "index_labels.json",
        "db_fields": out / "index_db_fields.json",
        "skos": out / "glossary.skos.jsonld",
    }
    doc = {"generated": date.today().isoformat(), "count": len(terms), "categories": _tree(g), "terms": terms}
    dumps = {
        "glossary": doc,
        "categories": doc["categories"],
        "labels": dict(sorted(labels.items())),
        "db_fields": dict(sorted(fields.items())),
        "skos": skos(g),
    }
    for key, path in written.items():
        path.write_text(json.dumps(dumps[key], ensure_ascii=False, indent=2), encoding="utf-8")
    return written


SKOS_RELATIONS = {"broader": "skos:broader", "narrower": "skos:narrower"}


def skos(g: Glossary, base: str = "https://w3id.org/snf-glossary/") -> dict:
    """SKOS JSON-LD (W3C standard for thesauri) so the glossary can be served as linked data."""
    graph = []
    for path, c in g.categories.items():
        graph.append({"@id": base + "category/" + path, "@type": "skos:Collection", "skos:prefLabel": c["name"],
                      "skos:definition": c.get("description", "")})
    for tid, t in sorted(g.terms.items()):
        node = {
            "@id": base + tid,
            "@type": "skos:Concept",
            "skos:inScheme": {"@id": base},
            "skos:prefLabel": [{"@value": t["term"], "@language": "en"}]
            + [{"@value": v, "@language": k} for k, v in (t.get("translations") or {}).items() if v],
            "skos:altLabel": [{"@value": s["label"], "@language": s.get("lang", "en")}
                              for s in t.get("synonyms") or [] if s.get("type") != "deprecated"]
            + ([{"@value": t["abbreviation"], "@language": "en"}] if t.get("abbreviation") else []),
            "skos:hiddenLabel": [s["label"] for s in t.get("synonyms") or [] if s.get("type") == "deprecated"],
            "skos:definition": t["definition"],
        }
        for r in t.get("related_terms") or []:
            prop = SKOS_RELATIONS.get(r.get("relation"), "skos:related")
            node.setdefault(prop, []).append({"@id": base + r["id"]})
        if t.get("abbreviation"):
            node["skos:notation"] = t["abbreviation"]
        graph.append({k: v for k, v in node.items() if v not in ([], "", None)})
    for path in g.categories:
        members = [{"@id": base + tid} for tid, t in g.terms.items() if t.get("category") == path]
        members += [{"@id": base + "category/" + p} for p in g.categories if p.rsplit("/", 1)[0] == path and "/" in p]
        next(n for n in graph if n["@id"] == base + "category/" + path)["skos:member"] = members
    return {
        "@context": {"skos": "http://www.w3.org/2004/02/skos/core#"},
        "@graph": [{"@id": base, "@type": "skos:ConceptScheme",
                    "skos:prefLabel": "Spent fuel dissolution glossary"}] + graph,
    }
