# Spent Fuel Dissolution Glossary

Controlled vocabulary for the spent nuclear fuel leaching database
([snf-db-app](../spent_nuclear_fuel_db/snf-db-app)): what each concept of a spent fuel leaching or dissolution
experiment means, its synonyms, units, typical values, where it is stored in the database and which
references support it.

- **One file = one term** (`glossary/<category>/<sub-category>/<id>.yaml`).
- **One folder = one category**, described by its `_category.yaml`.
- Plain YAML, validated against a JSON Schema and compiled to JSON, so it can be served by an API without
  changes.

## Project context

This glossary is part of the work of **SAREC** (*Release of safety relevant radionuclides from spent nuclear
fuel under deep disposal conditions*), work package 8 of **EURAD-2**, the European Partnership on Radioactive
Waste Management. SAREC aims at a better quantification and mechanistic understanding of the release of
safety-relevant radionuclides from spent fuel, building on the earlier EU projects FIRST-Nuclides and DisCo,
to support post-closure safety assessments of deep geological repositories. The SNF database that the
glossary describes is the SAREC WP8 database (Excel template `SAREC_WP8_DataBase_SF-D`).

Created and maintained by **[Amphos 21](https://amphos21.com)** as a partner of EURAD-2 SAREC.

- EURAD-2 SAREC: https://www.ejp-eurad.eu/publications/eurad-2-d81-sarec-initial-sota (D8.1, initial
  state-of-the-art report) and https://igdtp.eu/activity/sarec/

## Content

How to write and review terms: [docs/WRITING_GUIDE.md](docs/WRITING_GUIDE.md).
Candidate terms not written yet, with working notes and sources: [docs/TERM_BACKLOG.md](docs/TERM_BACKLOG.md).

## Layout

```
glossary/                    the glossary: category folders (_category.yaml) and term files (<id>.yaml)
templates/term.yaml          blank term template, every field explained
templates/term.example.yaml  a filled example (FIAP), not part of the glossary
templates/_category.yaml     blank category template
schema/term.schema.json      JSON Schema of a term (the contract for APIs)
schema/category.schema.json  JSON Schema of a category
glossary_tools/              validate, build, pdf, word and new commands
tests/                       pytest suite of the tools
docs/WRITING_GUIDE.md        how to write and review terms
docs/TERM_BACKLOG.md         candidate terms not written yet (from first Glossary.xlsx)
```

Categories (one folder each under `glossary/`; `order` in `_category.yaml` sets the listing order):
`experimental-techniques`, `nuclear-fuel`, `irradiated-fuel`, `sf-dissolution`,
`fuel-microstructure-and-phases`, `quantities-and-units`, `deep-geological-repository`.
Each `_category.yaml` has `id` (the folder name), `name`, `description`, `order`, `translations` and `source`
(the references behind the description).

## What a term contains

The sections follow `templates/term.yaml`:

| Section | Fields | Used for |
|---|---|---|
| 1. Basic information | `id`, `term`, `abbreviation`, `symbol`, `category`, `tags`, `status`, `replaced_by` | stable API key, display, search, review workflow |
| 2. Scientific content | `definition`, `description`, `notes`, `pitfalls` | tooltips (definition), help pages (description) |
| 3. Related terms | `related_terms`: list of `{id, relation}` (related-to, broader, narrower, part-of, has-part, depends-on, input-of, result-of, measured-by, influences, applied-to, precedes, follows, see-also, opposite-of) | navigation, thesaurus export (SKOS) |
| 4. Formula and units | `formula`, `formula_variables`, `units` (`si`, `db`, `other`), `typical_range` | data entry validation, unit conversion, plausibility checks |
| 5. References and contributors | `references` (type, citation, DOI, URL, pages), `standards`, `examples`, `authors`, `reviewers`, `created`, `updated`, `history` | traceability and review |
| 6. Other names (optional) | `synonyms` (typed: exact, abbreviation, spelling-variant, deprecated…), `translations` | search and matching of free text to a term |
| 7. Link to the SNF database (optional) | `db_mapping` (table, field, Excel header), `allowed_values` | link from each DB column to its definition and back |

Required: `id`, `term`, `category`, `definition`. An empty `authors` list is reported as a warning. An
`approved` term also needs a reviewer and at least one reference or standard.

## Commands

```
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python -m glossary_tools new sf-dissolution leachant      # new term from the template
.venv\Scripts\python -m glossary_tools validate                             # check everything
.venv\Scripts\python -m glossary_tools build                                # compile to dist/
.venv\Scripts\python -m glossary_tools pdf                                  # dist/glossary.pdf (--approved-only)
.venv\Scripts\python -m glossary_tools word                                 # dist/glossary.docx (--approved-only)
.venv\Scripts\python -m pytest                                              # tests of the tools
```

`validate` checks each file against the JSON Schema, and also:
- `id` equals the file name, `category` equals the folder;
- ids are unique, and every folder has a `_category.yaml`;
- related terms point to existing terms (a warning while those terms are not written yet), and
  broader/narrower and part-of/has-part pairs are listed on both sides (warning);
- references used in `typical_range` and `examples` exist in the term;
- approved and deprecated terms follow their rules, and dates and ranges are coherent;
- labels and synonyms shared by two terms are reported;
- every `db_mapping` table and field exists in the SNF database. This reads
  `../spent_nuclear_fuel_db/snf-db-app/backend/schema_v2.json` when it is next to this repository; another
  path can be given with `--db-schema`, and an empty value skips the check.

## Using it from an API

`build` writes `dist/` (not versioned), which can be served as static files or loaded by a web service:

| File | Content | Typical endpoint |
|---|---|---|
| `glossary.json` | all terms + category tree | `GET /glossary` |
| `categories.json` | category tree with the ids of its terms | `GET /categories` |
| `terms/<id>.json` | one term | `GET /terms/{id}` |
| `index_labels.json` | lower-case label, abbreviation or synonym → term ids | `GET /lookup?label=fiap` |
| `index_db_fields.json` | `table.field` → term ids | `GET /db-fields/{table}.{field}` (help text in snf-db-app) |
| `glossary.skos.jsonld` | the glossary as a SKOS thesaurus (W3C standard, JSON-LD) | linked data, import in vocabulary tools |

The term `id` is the stable key: it never changes once a term is approved (deprecate it and use
`replaced_by` instead). `schema/term.schema.json` can be used as the response model of the API.
