# Spent Fuel Dissolution Glossary

Controlled vocabulary for the spent nuclear fuel leaching database
([snf-db-app](../spent_nuclear_fuel_db/snf-db-app)): what each concept of a spent fuel leaching or dissolution
experiment means, its synonyms, units, typical values, where it is stored in the database and which
references support it.

- **One file = one term** (`glossary/<category>/<sub-category>/<id>.yaml`).
- **One folder = one category**, described by its `_category.yaml`.
- Plain YAML, validated against a JSON Schema and compiled to JSON, so it can be served by an API without
  changes.

The glossary content is written by the team (see [docs/GUIA_BECARIO.md](docs/GUIA_BECARIO.md), in Spanish).
This repository currently contains the structure, the template and the tools, not the terms.

## Layout

```
glossary/                    the glossary: category folders (_category.yaml) and term files (<id>.yaml)
templates/term.yaml          blank term template, every field explained
templates/term.example.yaml  a filled example (FIAP), not part of the glossary
templates/_category.yaml     blank category template
schema/term.schema.json      JSON Schema of a term (the contract for APIs)
schema/category.schema.json  JSON Schema of a category
glossary_tools/              validate, build and new commands
tests/                       pytest suite of the tools
docs/GUIA_BECARIO.md         how to write terms (Spanish)
```

Starting categories (they follow the tables of the SNF database and can be changed):
`fuel` (fuel-types, irradiation-history, inventory), `sample` (preparation, geometry-and-surface),
`experiment` (methods, atmosphere, solution-chemistry, conditions), `analysis`,
`results` (release-fractions, matrix-dissolution, secondary-phases), `radionuclides`,
`quantities-and-units`, `data-provenance`.

## What a term contains

| Block | Fields | Used for |
|---|---|---|
| Identity | `id`, `term`, `abbreviation`, `symbol`, `category`, `tags`, `status`, `replaced_by` | stable API key, display, search, review workflow |
| Meaning | `definition`, `description`, `notes`, `pitfalls` | tooltips (definition), help pages (description) |
| Other names | `synonyms` (typed: exact, abbreviation, spelling-variant, deprecated…), `translations` | search and matching of free text to a term |
| Quantity | `kind`, `unit`, `si_unit`, `other_units` with conversion, `allowed_values`, `typical_range`, `formula` | data entry validation, unit conversion, plausibility checks |
| Relations | `broader`, `narrower`, `related` (typed) | navigation, thesaurus export (SKOS) |
| Database | `db_mapping`: table, field, Excel header | link from each DB column to its definition and back |
| Sources | `references` (citation, DOI, pages, quote, what it supports), `standards`, `external_ids` | traceability of every definition |
| Bookkeeping | `authors`, `reviewers`, `created`, `updated`, `history` | review and versioning |

Required: `id`, `term`, `category`, `status`, `definition`, `authors`, `created`, `updated`. An `approved` term
also needs a reviewer and at least one reference or standard.

## Commands

```
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python -m glossary_tools new results/release-fractions fiap   # new term from the template
.venv\Scripts\python -m glossary_tools validate                             # check everything
.venv\Scripts\python -m glossary_tools build                                # compile to dist/
.venv\Scripts\python -m pytest                                              # tests of the tools
```

`validate` checks each file against the JSON Schema, and also:
- `id` equals the file name, `category` equals the folder;
- ids are unique, and every folder has a `_category.yaml`;
- relations point to existing terms (a warning while those terms are not written yet), and broader/narrower
  pairs are consistent;
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
