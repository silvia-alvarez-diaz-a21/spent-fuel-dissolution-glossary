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

1. Choose the category (folder) it belongs to, e.g. `results/release-fractions`. If none fits, create the
   folder and copy `templates/_category.yaml` into it, filled in.
2. Choose the `id`: English, lowercase with hyphens, short and stable (`fiap`, `burn-up`,
   `instant-release-fraction`).
3. Create the file from the template:
   ```
   .venv\Scripts\python -m glossary_tools new results/release-fractions fiap
   ```
   This creates `glossary/results/release-fractions/fiap.yaml` with the `id`, the category and the dates
   already filled in.
4. Fill it in following the comments of the template. `templates/term.example.yaml` is a complete example, and
   `glossary/experiment/leaching.yaml` is a real term.
5. Check it:
   ```
   .venv\Scripts\python -m glossary_tools validate
   ```
   **Errors** must be fixed. **Warnings** are normal while terms are missing: for example,
   "related 'x' is not a term yet" disappears once the term `x` is written.

## 3. Content rules

- **Language:** terms, definitions and descriptions are written in English. Labels in other languages go in
  `translations` (e.g. `es:`, `fr:`).
- **Definition:** one or two self-contained sentences, with no citations inside. Everything else goes in
  `description`.
- **Do not guess:** if a value is unknown (typical range, unit, DOI…), leave the field empty. Empty is better
  than doubtful.
- **Every statement has a source** in `references`, with pages or table and, if possible, a literal sentence in
  `quote`. In `supports`, list the fields it backs (`definition`, `typical_range`…).
- **Synonyms:** only other names of the same concept, with their type (`exact`, `abbreviation`,
  `spelling-variant`, `deprecated`…). Similar but different concepts go in `related`.
- **Relations:** `broader` is the more general concept and `narrower` the more specific ones. If `fiap` has
  `broader: [release-fraction]`, add `fiap` to the `narrower` list of `release-fraction`.
- **Database:** in `db_mapping`, the table and column of `snf-db-app` (`backend/schema_v2.json`) and the header
  of the upload Excel template. The validator checks that the column exists.
- **Units:** the unit as stored in the database (`unit`) and, in `other_units`, the ones found in papers with
  their conversion (`x / 1000`…).
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

## 5. Commit the changes

Before each commit, `validate` without errors and `pytest` passing:

```
.venv\Scripts\python -m glossary_tools validate
.venv\Scripts\python -m pytest
git add glossary
git commit -m "glossary: add fiap"
```
