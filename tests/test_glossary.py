import json
import shutil
from pathlib import Path

import pytest
import yaml

from glossary_tools.__main__ import main
from glossary_tools.core import DEFAULT_DB_SCHEMA, GLOSSARY, ROOT, build, validate

EXAMPLE = yaml.safe_load((ROOT / "templates" / "term.example.yaml").read_text(encoding="utf-8"))
DB = DEFAULT_DB_SCHEMA if DEFAULT_DB_SCHEMA.exists() else None


@pytest.fixture
def gl(tmp_path):
    """A copy of the real category tree, without its terms, ready to break."""
    root = tmp_path / "glossary"
    terms_only = lambda d, names: [n for n in names if n.endswith(".yaml") and n != "_category.yaml"]  # noqa: E731
    shutil.copytree(GLOSSARY, root, ignore=terms_only)
    return root


def write(root: Path, term: dict) -> Path:
    path = root / term["category"] / f"{term['id']}.yaml"
    path.write_text(yaml.safe_dump(term, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def messages(root: Path, db=DB):
    g = validate(root, db)
    return g, [str(i) for i in g.errors], [str(i) for i in g.issues if i.level == "warning"]


def test_real_glossary_is_valid():
    g, errors, _ = messages(GLOSSARY)
    assert errors == []
    assert len(g.categories) == 7


def test_example_term_is_valid_including_db_mapping(gl):
    write(gl, EXAMPLE)
    g, errors, warnings = messages(gl)
    assert errors == []
    assert "fiap" in g.terms
    assert any("not a term yet" in w for w in warnings)        # relations to terms not written yet


def test_blank_template_is_rejected_until_filled(gl):
    assert main(["--glossary", str(gl), "new", "sf-dissolution", "irf"]) == 0
    g, errors, warnings = messages(gl)
    assert any("definition" in e for e in errors) and any("term" in e for e in errors)
    assert any("authors is empty" in w for w in warnings)
    assert g.terms["irf"]["created"]                             # new fills id, category and dates


def test_template_matches_the_schema():
    """Every field of the blank template and of the example is in the schema, so they cannot drift apart."""
    schema = json.loads((ROOT / "schema" / "term.schema.json").read_text(encoding="utf-8"))
    fields = set(schema["properties"])
    template = yaml.safe_load((ROOT / "templates" / "term.yaml").read_text(encoding="utf-8"))
    assert set(template) <= fields, set(template) - fields
    assert set(EXAMPLE) <= fields, set(EXAMPLE) - fields
    assert set(schema["required"]) <= set(template)


def test_category_source_is_accepted(gl):
    cat = gl / "sf-dissolution" / "_category.yaml"
    data = yaml.safe_load(cat.read_text(encoding="utf-8"))
    cat.write_text(yaml.safe_dump({**data, "source": "Some reference."}), encoding="utf-8")
    assert messages(gl)[1] == []
    cat.write_text(yaml.safe_dump({**data, "sources": "typo"}), encoding="utf-8")
    assert any("Additional properties" in e for e in messages(gl)[1])


def test_new_refuses_unknown_category_and_existing_file(gl):
    assert main(["--glossary", str(gl), "new", "no-such", "x"]) == 1
    assert main(["--glossary", str(gl), "new", "irradiated-fuel", "x"]) == 0
    assert main(["--glossary", str(gl), "new", "irradiated-fuel", "x"]) == 1


@pytest.mark.parametrize("change,expected", [
    ({"id": "other"}, "must equal the file name"),
    ({"category": "fuel"}, "must be the folder path"),
    ({"status": "approved"}, "needs at least one reviewer"),
    ({"status": "finished"}, "status"),
    ({"updated": "2020-01-01"}, "earlier than created"),
    ({"id": "Bad Id"}, "id"),
    ({"typical_range": {"min": 5, "max": 1}}, "min is greater than max"),
    ({"examples": [{"text": "x", "reference": "nope"}]}, "reference 'nope'"),
    ({"references": [{"id": "r", "type": "article", "citation": "c", "doi": "https://doi.org/10.1/x"}]}, "doi"),
    ({"synonyms": [{"label": "x", "type": "kind-of"}]}, "synonyms"),
    ({"unknown_field": 1}, "Additional properties"),
    ({"related_terms": [{"id": "fiap", "relation": "broader"}]}, "points to itself"),
    ({"related_terms": [{"id": "x", "relation": "kind-of"}]}, "related_terms"),
    ({"references": [{"type": "journal-article", "citation": "c"}]}, "references"),
    ({"status": "deprecated", "replaced_by": "ghost"}, "replaced_by 'ghost'"),
])
def test_rules(gl, change, expected):
    term = {**EXAMPLE, **change}
    path = gl / EXAMPLE["category"] / "fiap.yaml"
    path.write_text(yaml.safe_dump(term, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _, errors, _ = messages(gl)
    assert any(expected in e for e in errors), errors


@pytest.mark.skipif(DB is None, reason="snf-db-app schema_v2.json not found next to this repo")
def test_db_mapping_must_exist_in_the_snf_db(gl):
    write(gl, {**EXAMPLE, "db_mapping": [{"table": "results_fiap_v2", "field": "fiap_unobtainium"},
                                         {"table": "no_table", "field": "x"}]})
    _, errors, _ = messages(gl)
    assert any("fiap_unobtainium" in e for e in errors) and any("no_table" in e for e in errors)


def test_duplicate_ids_and_shared_labels(gl):
    write(gl, EXAMPLE)
    other = {**EXAMPLE, "id": "fiap", "category": "irradiated-fuel"}
    write(gl, other)
    _, errors, _ = messages(gl)
    assert any("duplicated id" in e for e in errors)
    (gl / "irradiated-fuel" / "fiap.yaml").unlink()
    write(gl, {**EXAMPLE, "id": "fiap-copy", "category": "irradiated-fuel", "related_terms": []})
    _, _, warnings = messages(gl)
    assert any("also used by" in w for w in warnings)


def test_minimal_term_and_relation_warnings(gl):
    write(gl, {"id": "pellet", "term": "Pellet", "category": "nuclear-fuel", "definition": "d",
               "related_terms": [{"id": "fuel-rod", "relation": "part-of"}]})
    write(gl, {"id": "fuel-rod", "term": "Fuel rod", "category": "nuclear-fuel", "definition": "d",
               "authors": ["a"]})
    g, errors, warnings = messages(gl)
    assert errors == [] and set(g.terms) == {"pellet", "fuel-rod"}
    assert any("does not list 'pellet' as has-part" in w for w in warnings)
    assert any("pellet.yaml: authors is empty" in w for w in warnings)


def test_structure_errors(gl):
    (gl / "irradiated-fuel" / "orphan").mkdir()
    (gl / "loose.yaml").write_text("id: loose\n", encoding="utf-8")
    (gl / "irradiated-fuel" / "broken.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    _, errors, _ = messages(gl)
    assert any("folder without _category.yaml" in e for e in errors)
    assert any("inside a category folder" in e for e in errors)
    assert any("not valid YAML" in e for e in errors)


def test_build_outputs_for_apis(gl, tmp_path):
    write(gl, EXAMPLE)
    write(gl, {**EXAMPLE, "id": "release-fraction", "term": "Release fraction", "abbreviation": "",
               "category": "sf-dissolution", "synonyms": [],
               "related_terms": [{"id": "fiap", "relation": "narrower"}], "db_mapping": [], "translations": {}})
    g = validate(gl, DB)
    assert g.errors == []
    out = build(g, tmp_path / "dist")
    doc = json.loads(out["glossary"].read_text(encoding="utf-8"))
    assert doc["count"] == 2 and [t["id"] for t in doc["terms"]] == ["fiap", "release-fraction"]
    results = next(c for c in doc["categories"] if c["id"] == "sf-dissolution")
    assert results["terms"] == ["fiap", "release-fraction"]
    labels = json.loads(out["labels"].read_text(encoding="utf-8"))
    assert labels["fiap"] == ["fiap"] and labels["fractional release"] == ["fiap"]
    assert json.loads(out["db_fields"].read_text(encoding="utf-8"))["results_fiap_v2.fiap_am241"] == ["fiap"]
    assert json.loads((tmp_path / "dist" / "terms" / "fiap.json").read_text(encoding="utf-8"))["abbreviation"] == "FIAP"
    skos = json.loads(out["skos"].read_text(encoding="utf-8"))
    concept = next(n for n in skos["@graph"] if n["@id"].endswith("/fiap"))
    assert concept["@type"] == "skos:Concept" and concept["skos:notation"] == "FIAP"
    assert {"@id": "https://w3id.org/snf-glossary/release-fraction"} in concept["skos:broader"]
    assert {"@id": "https://w3id.org/snf-glossary/initial-inventory"} in concept["skos:related"]
    other = next(n for n in skos["@graph"] if n["@id"].endswith("/release-fraction"))
    assert other["skos:narrower"] == [{"@id": "https://w3id.org/snf-glossary/fiap"}]


def test_pdf(gl, tmp_path):
    write(gl, EXAMPLE)
    out = tmp_path / "g.pdf"
    assert main(["--glossary", str(gl), "pdf", "--out", str(out)]) == 0
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 3000
    assert main(["--glossary", str(gl), "pdf", "--approved-only", "--out", str(tmp_path / "a.pdf")]) == 0


def test_word(gl, tmp_path):
    from docx import Document

    write(gl, EXAMPLE)
    out = tmp_path / "g.docx"
    assert main(["--glossary", str(gl), "word", "--out", str(out)]) == 0
    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Spent Fuel Dissolution Glossary" in text and "Fraction of Inventory in the Aqueous Phase" in text
    assert any(p.style.name == "Heading 1" and p.text == "Spent fuel dissolution" for p in doc.paragraphs)
    cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
    assert "Related terms" in cells and any("results_fiap_v2.fiap_am241" in c for c in cells)
    assert main(["--glossary", str(gl), "word", "--approved-only", "--out", str(tmp_path / "a.docx")]) == 0


def test_word_refuses_invalid_glossary(gl, tmp_path):
    write(gl, {**EXAMPLE, "status": "approved"})
    assert main(["--glossary", str(gl), "word", "--out", str(tmp_path / "g.docx")]) == 1
    assert not (tmp_path / "g.docx").exists()


def test_pdf_refuses_invalid_glossary(gl, tmp_path):
    write(gl, {**EXAMPLE, "status": "approved"})
    assert main(["--glossary", str(gl), "pdf", "--out", str(tmp_path / "g.pdf")]) == 1
    assert not (tmp_path / "g.pdf").exists()


def test_cli_build_refuses_invalid_glossary(gl, tmp_path, capsys):
    write(gl, {**EXAMPLE, "status": "approved"})
    assert main(["--glossary", str(gl), "build", "--out", str(tmp_path / "d")]) == 1
    assert "not built" in capsys.readouterr().out
