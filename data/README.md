# Data for nutribuddy

The repository contains no documents, no food tables and no databases. The demo and the tests use
synthetic data that `nutribuddy synth` (or `nutribuddy demo`) writes. This file tells you how to
prepare real data.

## 1. Expected layout

```
data/
  sources.json                     # the source registry (required)
  disease/<condition>/<file>       # symptom documents: .md, .txt or .pdf
  diet_plan/<condition>/<file>     # nutrition guidance documents
  food_data/<release>/             # FoodData Central CSV files
    nutrient.csv                   # columns: id, name, unit_name
    food.csv                       # columns: fdc_id, description (data_type is optional)
    food_nutrient.csv              # columns: fdc_id, nutrient_id, amount
  eval/
    screening.jsonl                # {"text": "...", "label": "diabetes|heart|thyroid|none"}
    retrieval.jsonl                # {"question": "...", "condition": "...|null", "kind": "...", "source_id": "..."}
```

`<condition>` is `diabetes`, `heart` or `thyroid`.

## 2. The source registry

Each document must have one entry in `sources.json`. The indexer reads only registered documents
and it warns about other files.

```json
{"sources": [
  {"id": "who-diabetes-factsheet", "title": "Diabetes fact sheet", "url": "https://...",
   "licence": "CC BY-NC-SA 3.0 IGO", "condition": "diabetes", "kind": "disease",
   "path": "disease/diabetes/who-diabetes-factsheet.pdf"}
]}
```

| Field | Rule |
|---|---|
| `id` | Lower-case letters, digits, `-` and `_`. Unique. |
| `title`, `url`, `licence` | Required. The citation in each answer shows the title, the page and the URL. |
| `condition` | `diabetes`, `heart` or `thyroid` |
| `kind` | `disease` (symptoms) or `diet_plan` (nutrition guidance) |
| `path` | Relative to `data/`. No `..`. Ends with `.md`, `.txt` or `.pdf` (PDF needs `pip install "nutribuddy[pdf]"`). |

Use only documents whose licence allows a local copy. Good public sources are the fact sheets of
public-health agencies (for example the WHO and the CDC) and open-access review articles from PubMed Central.
Check the licence of each document.

## 3. FoodData Central

- Source: USDA FoodData Central, "Foundation Foods" CSV download
- URL: https://fdc.nal.usda.gov/download-datasets.html
- Licence: public domain (CC0 1.0)

Download a release, unzip it into `data/food_data/<release>/` and run:

```bash
nutribuddy load-foods --fdc-dir data/food_data
```

The load is idempotent. You can run it again after you add a release. FoodData Central gives
amounts per 100 g of food. nutribuddy keeps that basis and the unit of each nutrient.

## 4. Synthetic data

`nutribuddy synth --out data/synthetic` writes six short documents, a food table with 32 foods and
17 nutrients, and the two evaluation sets. The text and the amounts are written for the demo. They
are not medical guidance and they are not USDA values.
