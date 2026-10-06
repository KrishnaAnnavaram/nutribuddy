import csv

import pytest

from nutribuddy.fooddb import FoodDataError, connect, counts, load_fdc, resolve_nutrient, top_foods


@pytest.fixture()
def foods(data_dir):
    conn = connect(":memory:")
    load_fdc(conn, data_dir / "food_data" / "synthetic")
    return conn


def _write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def test_load_is_idempotent(data_dir, foods):
    first = counts(foods)
    load_fdc(foods, data_dir / "food_data" / "synthetic")
    assert counts(foods) == first
    assert first["food_nutrient"] > 0


def test_bad_rows_are_skipped_and_missing_columns_fail(tmp_path):
    _write(tmp_path / "nutrient.csv", [["id", "name", "unit_name"], [1003, "Protein", "G"], ["x", "Bad", "G"]])
    _write(tmp_path / "food.csv", [["fdc_id", "description"], [1, "Lentils"]])
    _write(tmp_path / "food_nutrient.csv",
           [["fdc_id", "nutrient_id", "amount"], [1, 1003, 9.0], [1, 1003, "n/a"], [2, 1003, 3], [1, 1003, -1]])
    conn = connect(":memory:")
    rep = load_fdc(conn, tmp_path)
    assert (rep.nutrients, rep.foods, rep.amounts, rep.skipped_rows) == (1, 1, 1, 4)
    (tmp_path / "food.csv").write_text("id,name\n1,x\n", encoding="utf-8")
    with pytest.raises(FoodDataError, match="lacks columns"):
        load_fdc(conn, tmp_path)


@pytest.mark.parametrize("name, expected", [
    ("Protein", "Protein"),
    ("fibre", "Fiber, total dietary"),
    ("Omega-3 fatty acids", "Fatty acids, total polyunsaturated"),
    ("potassium", "Potassium, K"),
    ("Complex carbohydrates", "Carbohydrate, by difference"),
    ("iodine", "Iodine, I"),
])
def test_resolve_nutrient_names(foods, name, expected):
    assert resolve_nutrient(foods, name).name == expected


@pytest.mark.parametrize("attack", [
    "protein'); DROP TABLE food; --",
    "%",
    "_",
    "x' OR '1'='1",
    "protein%' UNION SELECT name, unit FROM nutrient --",
])
def test_sql_injection_attempts_resolve_to_nothing_and_change_nothing(foods, attack):
    before = counts(foods)
    assert resolve_nutrient(foods, attack) is None
    assert counts(foods) == before


def test_top_foods_ranks_by_amount_and_excludes(foods):
    fiber = resolve_nutrient(foods, "fiber")
    top = top_foods(foods, fiber, 3)
    amounts = [f.amount for f in top]
    assert amounts == sorted(amounts, reverse=True) and len(top) == 3
    assert all(f.basis == "per 100 g" for f in top)
    protein = resolve_nutrient(foods, "protein")
    names = [f.description for f in top_foods(foods, protein, 5, exclude=["chicken"])]
    assert not any("Chicken" in n or "Bacon" in n for n in names)
    assert "g Protein per 100 g" in top_foods(foods, protein, 1)[0].describe()
