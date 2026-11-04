# Guía para escribir el glosario

El glosario explica, término a término, los conceptos de los experimentos de lixiviación y disolución de
combustible gastado que aparecen en la base de datos SNF (`snf-db-app`). Cada término es un fichero YAML y
cada carpeta es una categoría.

## 1. Preparar el entorno (una sola vez)

```
cd spent-fuel-dissolution-glossary
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 2. Crear un término

1. Elige la categoría (carpeta) donde encaja, por ejemplo `results/release-fractions`. Si no existe ninguna
   adecuada, crea la carpeta y copia dentro `templates/_category.yaml` rellenado.
2. Elige el `id`: en inglés, minúsculas y guiones, corto y estable (`fiap`, `burn-up`, `instant-release-fraction`).
3. Crea el fichero desde la plantilla:
   ```
   .venv\Scripts\python -m glossary_tools new results/release-fractions fiap
   ```
   Esto crea `glossary/results/release-fractions/fiap.yaml` con el `id`, la categoría y las fechas ya puestas.
4. Rellénalo siguiendo los comentarios de la plantilla. Hay un ejemplo completo en `templates/term.example.yaml`.
5. Comprueba:
   ```
   .venv\Scripts\python -m glossary_tools validate
   ```
   Los **errores** hay que corregirlos. Los **avisos** son normales mientras faltan términos: por ejemplo,
   «related 'x' is not a term yet» desaparece cuando alguien escriba el término `x`.

## 3. Reglas de contenido

- **Idioma:** los términos, las definiciones y las descripciones se escriben en inglés. Las traducciones van
  en `translations` (por ejemplo, `es:`).
- **Definición:** una o dos frases que se entiendan solas, sin citas dentro. Lo demás va en `description`.
- **No inventes:** si no sabes un dato (rango típico, unidad, DOI…), deja el campo vacío. Es mejor vacío que dudoso.
- **Cada afirmación tiene su fuente** en `references`, con las páginas o la tabla y, si puedes, una frase
  literal en `quote`. En `supports` indica qué campos respalda (`definition`, `typical_range`…).
- **Sinónimos:** solo nombres del mismo concepto, indicando el tipo (`exact`, `abbreviation`,
  `spelling-variant`, `deprecated`…). Los conceptos parecidos pero distintos van en `related`.
- **Relaciones:** `broader` es el concepto más general y `narrower` los más específicos. Si pones
  `broader: [release-fraction]` en `fiap`, añade `fiap` en el `narrower` de `release-fraction`.
- **Base de datos:** en `db_mapping`, la tabla y la columna de `snf-db-app` (`backend/schema_v2.json`) y la
  cabecera del Excel de carga. El validador comprueba que la columna existe.
- **Unidades:** la unidad tal como se guarda en la base de datos (`unit`) y, en `other_units`, las que salen
  en los artículos con su conversión (`x / 1000`…).
- **Valores controlados:** si el término solo admite ciertos valores (p. ej. la atmósfera: `oxidizing`,
  `anoxic`, `reducing`), lístalos en `allowed_values`, cada uno con su definición.

## 4. Estados y revisión

| Estado | Cuándo |
|---|---|
| `draft` | en redacción |
| `review` | terminado, pendiente de revisión |
| `approved` | revisado: necesita al menos un revisor en `reviewers` y una referencia o norma |
| `deprecated` | ya no se usa: indica el término que lo sustituye en `replaced_by` |

Cada vez que edites un término, cambia `updated` y añade una línea en `history`. El `id` de un término
aprobado no se cambia nunca, porque las APIs lo usan como clave.

## 5. Subir los cambios

Antes de cada commit, `validate` sin errores y `pytest` en verde:

```
.venv\Scripts\python -m glossary_tools validate
.venv\Scripts\python -m pytest
git add glossary
git commit -m "glossary: add fiap"
```
