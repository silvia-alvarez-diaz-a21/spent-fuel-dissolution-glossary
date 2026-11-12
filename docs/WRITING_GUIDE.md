# Writing guide

The glossary explains, term by term, the concepts of spent fuel leaching and dissolution experiments that
appear in the SNF database (`snf-db-app`). Each term is a YAML file and each folder is a category.

## 1. Set up the environment (once)

```
cd spent-fuel-dissolution-glossary
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 2. Create a term

1. Choose the category (folder) it belongs to, e.g. `sf-dissolution`. If none fits, create the
   folder and copy `templates/_category.yaml` into it, filled in (with the references of its
   description in `source`).
   Before writing a term, check `docs/TERM_BACKLOG.md`: it may already have notes and sources for it.
2. Choose the `id`: English, lowercase with hyphens, short and stable (`fiap`, `burnup`,
   `instant-release-fraction`).
3. Create the file from the template:
   ```
   .venv\Scripts\python -m glossary_tools new sf-dissolution leachant
   ```
   This creates `glossary/sf-dissolution/leachant.yaml` with the `id`, the category and the dates
   already filled in.
4. Fill it in following the comments of the template. `templates/term.example.yaml` is a complete example, and
   `glossary/sf-dissolution/leaching.yaml` is a real term.
5. Check it:
   ```
   .venv\Scripts\python -m glossary_tools validate
   ```
   **Errors** must be fixed. **Warnings** are normal while terms are missing: for example,
   "related term 'x' is not a term yet" disappears once the term `x` is written.

## 3. Content rules

- **Language:** terms, definitions and descriptions are written in English. Labels in other languages go in
  `translations` (e.g. `es:`, `fr:`).
- **Definition:** one or two self-contained sentences, with no citations inside. Everything else goes in
  `description`.
- **Do not guess:** if a value is unknown (typical range, unit, DOI…), leave the field empty. Empty is better
  than doubtful.
- **Every statement has a source** in `references`: full citation (authors, year, title, journal or
  publisher, volume, pages), DOI or URL when available, and the pages or table used.
- **Synonyms:** only other names of the same concept, with their type (`exact`, `abbreviation`,
  `spelling-variant`, `deprecated`…). Similar but different concepts go in `related_terms`.
- **Related terms:** each item is `{id, relation}`, and `id` is the id of another term (not a category).
  Use only the relations listed in the template. `broader` is the more general concept and `narrower` the
  more specific one; `part-of` / `has-part` is for physical components (pellet part-of fuel-rod). List both
  sides: if `fiap` has `{id: release-fraction, relation: broader}`, `release-fraction` should have
  `{id: fiap, relation: narrower}`.
- **Database:** in `db_mapping`, the table and column of `snf-db-app` (`backend/schema_v2.json`) and the header
  of the upload Excel template. The validator checks that the column exists.
- **Units:** in `units`, the SI unit (`si`), the unit as stored in the database (`db`) and, in `other`, the
  ones found in papers (optionally with their conversion: `{unit: "1 (fraction)", to_db_unit: "x * 100"}`).
- **Controlled values:** if the term only takes some values (e.g. the type of experiment: `Batch`,
  `Replenishment`, `Dynamic`), list them in `allowed_values`, each with its definition.

## 4. Status and review

| Status | When |
|---|---|
| `draft` | being written |
| `review` | finished, waiting for review |
| `approved` | reviewed: needs at least one reviewer in `reviewers` and one reference or standard |
| `deprecated` | no longer used: give the term that replaces it in `replaced_by` |

On every edit, update `updated` and add a line to `history`. The `id` of an approved term never changes,
because the APIs use it as the key.

## 5. Share the glossary

```
.venv\Scripts\python -m glossary_tools pdf     # dist/glossary.pdf
.venv\Scripts\python -m glossary_tools word    # dist/glossary.docx (editable; update the contents when Word asks)
```

Add `--approved-only` to leave out the terms that are not approved yet.

## 6. Commit the changes

Before each commit, `validate` without errors and `pytest` passing:

```
.venv\Scripts\python -m glossary_tools validate
.venv\Scripts\python -m pytest
git add glossary
git commit -m "glossary: add fiap"
```
