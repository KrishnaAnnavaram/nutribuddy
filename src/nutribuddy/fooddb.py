"""Food composition store (SQLite) loaded from USDA FoodData Central CSV files.

Rules:
- Every query uses bound parameters. No text from a user or a model goes into the SQL string.
- A nutrient name from a model must resolve to a row of the ``nutrient`` table before a lookup.
- The load is idempotent: ``INSERT ... ON CONFLICT DO UPDATE`` on the natural keys.
- Amounts keep their unit and their basis (per 100 g of food, as in FoodData Central).
"""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS nutrient (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    unit TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS food (
    fdc_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    data_type TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS food_nutrient (
    fdc_id INTEGER NOT NULL REFERENCES food(fdc_id),
    nutrient_id INTEGER NOT NULL REFERENCES nutrient(id),
    amount REAL NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (fdc_id, nutrient_id)
);
CREATE INDEX IF NOT EXISTS ix_food_nutrient_nutrient ON food_nutrient(nutrient_id, amount DESC);
"""

REQUIRED_COLUMNS = {
    "nutrient.csv": {"id", "name", "unit_name"},
    "food.csv": {"fdc_id", "description"},
    "food_nutrient.csv": {"fdc_id", "nutrient_id", "amount"},
}

# Common words a model uses for a nutrient, mapped to the FoodData Central nutrient name.
ALIASES = {
    "fiber": "Fiber, total dietary",
    "fibre": "Fiber, total dietary",
    "dietary fiber": "Fiber, total dietary",
    "soluble fiber": "Fiber, total dietary",
    "protein": "Protein",
    "lean protein": "Protein",
    "potassium": "Potassium, K",
    "magnesium": "Magnesium, Mg",
    "calcium": "Calcium, Ca",
    "iron": "Iron, Fe",
    "zinc": "Zinc, Zn",
    "selenium": "Selenium, Se",
    "iodine": "Iodine, I",
    "sodium": "Sodium, Na",
    "vitamin d": "Vitamin D (D2 + D3)",
    "vitamin c": "Vitamin C, total ascorbic acid",
    "vitamin b12": "Vitamin B-12",
    "folate": "Folate, total",
    "omega-3": "Fatty acids, total polyunsaturated",
    "omega-3 fatty acid": "Fatty acids, total polyunsaturated",
    "polyunsaturated fat": "Fatty acids, total polyunsaturated",
    "unsaturated fat": "Fatty acids, total monounsaturated",
    "monounsaturated fat": "Fatty acids, total monounsaturated",
    "carbohydrate": "Carbohydrate, by difference",
    "complex carbohydrate": "Carbohydrate, by difference",
    "sugar": "Sugars, total including NLEA",
}


UNIT_LABELS = {"G": "g", "MG": "mg", "UG": "µg", "KCAL": "kcal"}

# Foods that a plan never suggests as an example, whatever their nutrient amount.
NEVER_SUGGEST = ("bacon", "chips", "soft drink", "cola", "candy", "fried", "sausage")


class FoodDataError(ValueError):
    """A food data file is missing or has the wrong columns."""


@dataclass(frozen=True)
class Nutrient:
    id: int
    name: str
    unit: str


@dataclass(frozen=True)
class FoodExample:
    description: str
    nutrient: str
    amount: float
    unit: str
    basis: str = "per 100 g"

    def describe(self) -> str:
        unit = UNIT_LABELS.get(self.unit.upper(), self.unit)
        return f"{self.description} ({self.amount:g} {unit} {self.nutrient} {self.basis})"


@dataclass
class LoadReport:
    nutrients: int = 0
    foods: int = 0
    amounts: int = 0
    skipped_rows: int = 0


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def _rows(path: Path, required: set[str]):
    if not path.exists():
        raise FoodDataError(f"{path} not found")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise FoodDataError(f"{path.name} lacks columns {sorted(missing)}")
        yield from reader


def load_fdc(conn: sqlite3.Connection, folder: Path) -> LoadReport:
    """Load nutrient.csv, food.csv and food_nutrient.csv from one FoodData Central release folder."""
    folder = Path(folder)
    rep = LoadReport()
    with conn:
        for r in _rows(folder / "nutrient.csv", REQUIRED_COLUMNS["nutrient.csv"]):
            try:
                nid, name, unit = int(r["id"]), r["name"].strip(), r["unit_name"].strip()
            except (ValueError, AttributeError):
                rep.skipped_rows += 1
                continue
            if not name:
                rep.skipped_rows += 1
                continue
            conn.execute(
                "INSERT INTO nutrient(id, name, unit) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name = excluded.name, unit = excluded.unit",
                (nid, name, unit),
            )
            rep.nutrients += 1
        for r in _rows(folder / "food.csv", REQUIRED_COLUMNS["food.csv"]):
            try:
                fid, desc = int(r["fdc_id"]), r["description"].strip()
            except (ValueError, AttributeError):
                rep.skipped_rows += 1
                continue
            if not desc:
                rep.skipped_rows += 1
                continue
            conn.execute(
                "INSERT INTO food(fdc_id, description, data_type) VALUES (?, ?, ?) "
                "ON CONFLICT(fdc_id) DO UPDATE SET description = excluded.description, data_type = excluded.data_type",
                (fid, desc, (r.get("data_type") or "").strip()),
            )
            rep.foods += 1
        known_foods = {row[0] for row in conn.execute("SELECT fdc_id FROM food")}
        known_nutrients = {row[0] for row in conn.execute("SELECT id FROM nutrient")}
        for r in _rows(folder / "food_nutrient.csv", REQUIRED_COLUMNS["food_nutrient.csv"]):
            try:
                fid, nid, amount = int(r["fdc_id"]), int(r["nutrient_id"]), float(r["amount"])
            except (ValueError, TypeError):
                rep.skipped_rows += 1
                continue
            if amount < 0 or fid not in known_foods or nid not in known_nutrients:
                rep.skipped_rows += 1
                continue
            conn.execute(
                "INSERT INTO food_nutrient(fdc_id, nutrient_id, amount) VALUES (?, ?, ?) "
                "ON CONFLICT(fdc_id, nutrient_id) DO UPDATE SET amount = excluded.amount",
                (fid, nid, amount),
            )
            rep.amounts += 1
    return rep


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("nutrient", "food", "food_nutrient")}


def _norm(name: str) -> str:
    name = re.sub(r"[^a-z0-9\- ]+", " ", name.lower())
    name = re.sub(r"\s+", " ", name).strip()
    if name.endswith("s") and not name.endswith(("ss", "us")) and name not in ALIASES:
        singular = name[:-1]
        if singular in ALIASES:
            return singular
    return name


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def resolve_nutrient(conn: sqlite3.Connection, name: str) -> Nutrient | None:
    """Map a free-text nutrient name to one row of the nutrient table, or None."""
    key = _norm(name)
    if not key or len(key) > 60:
        return None
    target = ALIASES.get(key)
    if target:
        row = conn.execute("SELECT id, name, unit FROM nutrient WHERE name = ?", (target,)).fetchone()
        if row:
            return Nutrient(*row)
    row = conn.execute("SELECT id, name, unit FROM nutrient WHERE lower(name) = ? ORDER BY id LIMIT 1", (key,)).fetchone()
    if row:
        return Nutrient(*row)
    row = conn.execute(
        "SELECT id, name, unit FROM nutrient WHERE lower(name) LIKE ? ESCAPE '\\' ORDER BY length(name), id LIMIT 1",
        (_like_escape(key) + "%",),
    ).fetchone()
    return Nutrient(*row) if row else None


def top_foods(
    conn: sqlite3.Connection, nutrient: Nutrient, limit: int, exclude: list[str] | None = None
) -> list[FoodExample]:
    """Foods with the highest amount of one nutrient. Skip foods that contain an excluded word."""
    rows = conn.execute(
        "SELECT f.description, fn.amount FROM food_nutrient fn JOIN food f ON f.fdc_id = fn.fdc_id "
        "WHERE fn.nutrient_id = ? AND fn.amount > 0 ORDER BY fn.amount DESC, f.description LIMIT ?",
        (nutrient.id, limit * 10),
    ).fetchall()
    bad = [w.lower() for w in (exclude or []) if w.strip()] + list(NEVER_SUGGEST)
    out: list[FoodExample] = []
    for desc, amount in rows:
        low = desc.lower()
        if any(b in low for b in bad):
            continue
        out.append(FoodExample(desc, nutrient.name, round(float(amount), 2), nutrient.unit))
        if len(out) == limit:
            break
    return out
