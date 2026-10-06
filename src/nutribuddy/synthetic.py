"""Synthetic demo data: source documents, a small food table and labelled evaluation sets.

All text and all numbers here are written for the demo. They are not medical guidance and the food
amounts are illustrative approximations, not USDA values. The demo and the tests use only this data.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

SYNTHETIC_NOTE = "Synthetic demo text written for nutribuddy. It is not medical advice."

DOCS: dict[tuple[str, str], tuple[str, list[str]]] = {
    ("diabetes", "disease"): (
        "Recognising type 2 diabetes (synthetic)",
        [
            "# Common symptoms\nPeople with high blood glucose often feel very thirsty and pass urine more often, "
            "most of all at night. Some people notice constant hunger even after a meal. Unexplained weight loss can "
            "happen when the body cannot use glucose for energy. Tiredness and low energy are common.\n"
            "# Changes in vision and skin\nBlurred vision comes and goes when blood sugar levels change. Cuts, sores "
            "and bruises heal slowly. Frequent infections of the skin, gums or bladder are a warning sign. Dark, "
            "velvety patches of skin on the neck or armpits can appear.",
            "# Nerve symptoms\nTingling, burning or numbness in the hands or feet is a sign of nerve damage from "
            "long-term high glucose.\n# Risk factors\nRisk is higher with excess body weight, a family history of "
            "diabetes, low physical activity and a past history of high blood sugar in pregnancy. A fasting glucose "
            "test or an HbA1c test confirms the condition. Only a clinician can make the diagnosis.",
        ],
    ),
    ("heart", "disease"): (
        "Signs of coronary heart disease (synthetic)",
        [
            "# Common symptoms\nThe classic sign is discomfort in the chest during effort that stops with rest. "
            "Many people feel breathless when they climb stairs or walk uphill. Palpitations, a racing or irregular "
            "heartbeat, can occur. Pain can spread to the jaw, the neck, the left arm or the back.\n"
            "# Signs of fluid build-up\nSwollen ankles, feet or legs, and sudden weight gain from fluid, can show "
            "that the heart pumps less well. Some people cannot lie flat at night without extra pillows.",
            "# Other symptoms\nDizziness, a cold sweat, nausea and a feeling like indigestion can come with heart "
            "problems, most of all in women and older adults. Extreme tiredness after light activity is common.\n"
            "# Risk factors\nHigh blood pressure, high LDL cholesterol, smoking, diabetes, excess weight and a family "
            "history of early heart disease raise the risk. An ECG, blood tests and a stress test help a clinician "
            "decide.",
        ],
    ),
    ("thyroid", "disease"): (
        "Thyroid disorders in adults (synthetic)",
        [
            "# Underactive thyroid\nHypothyroidism develops slowly. People feel tired and cold when others feel "
            "warm. Weight gain, constipation, dry skin and thinning hair are common. The face can look puffy and "
            "the voice can become hoarse. Muscle aches, a slow heart rate and a low mood can occur.",
            "# Overactive thyroid\nHyperthyroidism speeds the body up. Signs include weight loss with a normal "
            "appetite, a fast heartbeat, a tremor of the hands, sweating and intolerance of heat. Anxiety, "
            "irritability and frequent bowel movements are common.\n# Goiter\nA swelling at the front of the neck, "
            "called a goiter, can come with either form. A TSH blood test helps a clinician confirm the condition.",
        ],
    ),
    ("diabetes", "diet_plan"): (
        "Eating well with type 2 diabetes (synthetic)",
        [
            "# The plate method\nFill half of the plate with non-starchy vegetables, one quarter with lean protein "
            "and one quarter with whole grains or other complex carbohydrates. Spread carbohydrate evenly across "
            "the day, at regular meal times, to keep blood glucose stable.\n"
            "# Fiber and protein\nInclude foods rich in fiber, such as lentils, beans, oats and vegetables, because "
            "fiber slows the rise in blood sugar after a meal. Choose lean protein such as fish, eggs, tofu and "
            "chicken. Include magnesium from nuts, seeds and leafy greens.",
            "# Fats\nChoose unsaturated fat from olive oil, nuts and avocado instead of butter.\n"
            "# Foods to limit\nLimit sugary drinks, sweets, white bread and white rice, because they raise blood "
            "glucose quickly. Avoid fruit juice and large portions of potato chips. Water, tea and coffee without "
            "sugar are good drinks. Alcohol can cause low blood sugar with some medicines.",
        ],
    ),
    ("heart", "diet_plan"): (
        "A heart-healthy eating pattern (synthetic)",
        [
            "# Salt and blood pressure\nKeep sodium under 2,300 mg a day, and lower if blood pressure is high. "
            "Limit salt, processed meats, salty snacks and canned soups. Cook with herbs and lemon instead of "
            "salt.\n# Potassium\nInclude potassium from fruits, vegetables, beans and yogurt, because "
            "potassium helps to balance the effect of sodium on blood pressure.",
            "# Fats and fiber\nEat more oily fish, such as salmon and sardines, two times a week for omega-3 fatty "
            "acids. Choose unsaturated fat from olive oil and nuts. Reduce saturated fat, fried foods and butter. "
            "Include soluble fiber from oats, barley and beans, because it helps to lower LDL cholesterol.\n"
            "# Alcohol\nLimit alcohol to small amounts, or do not drink it.",
        ],
    ),
    ("thyroid", "diet_plan"): (
        "Nutrition for thyroid health (synthetic)",
        [
            "# Iodine and selenium\nThe thyroid needs iodine to make hormones. Include iodine from dairy, eggs, fish "
            "and iodized salt in normal amounts. Too much iodine from seaweed supplements can also harm the thyroid. "
            "Include selenium from fish, eggs and a small number of nuts, because selenium protects the gland.",
            "# Medicine timing\nTake thyroid hormone tablets on an empty stomach. Keep calcium and iron supplements, "
            "soy foods and coffee at least four hours away from the tablet, because they reduce absorption.\n"
            "# Everyday diet\nChoose protein at each meal and include zinc from seeds, beans and meat. Include fiber "
            "to help with constipation. Limit highly processed foods and sugary snacks if weight gain is a problem.",
        ],
    ),
}

NUTRIENTS = [
    (1003, "Protein", "G"), (1005, "Carbohydrate, by difference", "G"), (1079, "Fiber, total dietary", "G"),
    (2000, "Sugars, total including NLEA", "G"), (1087, "Calcium, Ca", "MG"), (1089, "Iron, Fe", "MG"),
    (1090, "Magnesium, Mg", "MG"), (1092, "Potassium, K", "MG"), (1093, "Sodium, Na", "MG"),
    (1095, "Zinc, Zn", "MG"), (1100, "Iodine, I", "UG"), (1103, "Selenium, Se", "UG"),
    (1114, "Vitamin D (D2 + D3)", "UG"), (1162, "Vitamin C, total ascorbic acid", "MG"),
    (1292, "Fatty acids, total monounsaturated", "G"), (1293, "Fatty acids, total polyunsaturated", "G"),
    (1258, "Fatty acids, total saturated", "G"),
]

# Illustrative amounts per 100 g (protein, carbohydrate, fiber, sugars, Ca, Fe, Mg, K, Na, Zn, I, Se,
# vitamin D, vitamin C, MUFA, PUFA, SFA). Written for the demo, not copied from USDA tables.
FOODS: list[tuple[str, tuple[float, ...]]] = [
    ("Lentils, cooked", (9.0, 20, 7.9, 1.8, 19, 3.3, 36, 369, 2, 1.3, 1, 2.8, 0, 1.5, 0.1, 0.2, 0.1)),
    ("Black beans, cooked", (8.9, 24, 8.7, 0.3, 27, 2.1, 70, 355, 1, 1.1, 1, 1.2, 0, 0, 0.1, 0.2, 0.1)),
    ("Chickpeas, cooked", (8.9, 27, 7.6, 4.8, 49, 2.9, 48, 291, 7, 1.5, 1, 3.7, 0, 1.3, 0.6, 1.2, 0.3)),
    ("Oats, rolled, dry", (13.2, 67, 10.1, 1.0, 52, 4.3, 138, 362, 6, 3.6, 1, 28.9, 0, 0, 2.2, 2.5, 1.1)),
    ("Barley, pearled, cooked", (2.3, 28, 3.8, 0.3, 11, 1.3, 22, 93, 3, 0.8, 1, 8.6, 0, 0, 0.1, 0.2, 0.1)),
    ("Brown rice, cooked", (2.7, 23, 1.8, 0.4, 3, 0.4, 39, 86, 1, 0.6, 1, 5.8, 0, 0, 0.3, 0.3, 0.2)),
    ("White rice, cooked", (2.7, 28, 0.4, 0.1, 10, 0.2, 12, 35, 1, 0.5, 1, 7.5, 0, 0, 0.1, 0.1, 0.1)),
    ("White bread", (9.0, 49, 2.7, 5.7, 151, 3.6, 25, 126, 490, 0.7, 2, 22.0, 0, 0, 1.0, 1.4, 0.7)),
    ("Spinach, raw", (2.9, 3.6, 2.2, 0.4, 99, 2.7, 79, 558, 79, 0.5, 2, 1.0, 0, 28, 0, 0.2, 0.1)),
    ("Broccoli, raw", (2.8, 6.6, 2.6, 1.7, 47, 0.7, 21, 316, 33, 0.4, 1, 2.5, 0, 89, 0, 0.1, 0.1)),
    ("Sweet potato, baked", (2.0, 21, 3.3, 6.5, 38, 0.7, 27, 475, 36, 0.3, 1, 0.2, 0, 19.6, 0, 0.1, 0)),
    ("Banana, raw", (1.1, 23, 2.6, 12.2, 5, 0.3, 27, 358, 1, 0.2, 1, 1.0, 0, 8.7, 0, 0.1, 0.1)),
    ("Orange, raw", (0.9, 12, 2.4, 9.4, 40, 0.1, 10, 181, 0, 0.1, 1, 0.5, 0, 53, 0, 0, 0)),
    ("Avocado, raw", (2.0, 8.5, 6.7, 0.7, 12, 0.6, 29, 485, 7, 0.6, 1, 0.4, 0, 10, 9.8, 1.8, 2.1)),
    ("Almonds", (21.2, 22, 12.5, 4.4, 269, 3.7, 270, 733, 1, 3.1, 1, 4.1, 0, 0, 31.6, 12.3, 3.8)),
    ("Walnuts", (15.2, 14, 6.7, 2.6, 98, 2.9, 158, 441, 2, 3.1, 1, 4.9, 0, 1.3, 8.9, 47.2, 6.1)),
    ("Brazil nuts", (14.3, 12, 7.5, 2.3, 160, 2.4, 376, 659, 3, 4.1, 1, 1917.0, 0, 0.7, 24.5, 20.6, 15.1)),
    ("Pumpkin seeds", (30.2, 11, 6.0, 1.4, 46, 8.8, 592, 809, 7, 7.8, 1, 9.4, 0, 1.9, 16.2, 21.0, 8.7)),
    ("Olive oil", (0, 0, 0, 0, 1, 0.6, 0, 1, 2, 0, 0, 0, 0, 0, 73.0, 10.5, 13.8)),
    ("Salmon, cooked", (25.4, 0, 0, 0, 15, 0.3, 30, 384, 61, 0.4, 14, 41.4, 13.1, 0, 2.1, 4.0, 1.0)),
    ("Sardines, canned in water", (24.6, 0, 0, 0, 382, 2.9, 39, 397, 307, 1.3, 35, 52.7, 4.8, 0, 3.9, 5.1, 1.5)),
    ("Cod, cooked", (22.8, 0, 0, 0, 14, 0.5, 42, 244, 78, 0.6, 99, 37.6, 1.1, 1.0, 0.1, 0.3, 0.2)),
    ("Eggs, whole, boiled", (12.6, 1.1, 0, 1.1, 50, 1.2, 10, 126, 124, 1.1, 50, 30.8, 2.2, 0, 4.1, 1.4, 3.3)),
    ("Chicken breast, roasted", (31.0, 0, 0, 0, 15, 1.0, 29, 256, 74, 1.0, 7, 27.6, 0.1, 0, 1.2, 0.8, 1.0)),
    ("Tofu, firm", (17.3, 2.8, 2.3, 0.6, 683, 2.7, 58, 237, 14, 1.6, 1, 17.4, 0, 0, 2.4, 5.0, 1.3)),
    ("Greek yogurt, plain, low fat", (10.3, 3.6, 0, 3.2, 115, 0.1, 11, 141, 34, 0.5, 31, 9.7, 0, 0, 0.5, 0.1, 1.2)),
    ("Milk, low fat", (3.4, 5.0, 0, 5.1, 125, 0, 11, 150, 44, 0.4, 32, 3.3, 1.2, 0, 0.3, 0, 0.6)),
    ("Cheddar cheese", (24.9, 1.3, 0, 0.5, 721, 0.7, 28, 98, 621, 3.7, 25, 28.5, 0.6, 0, 9.4, 1.4, 19.4)),
    ("Bacon, cooked", (37.0, 1.4, 0, 0, 11, 1.4, 34, 565, 1717, 3.5, 2, 62.0, 0.3, 0, 18.5, 4.5, 13.7)),
    ("Potato chips, salted", (6.6, 53, 4.4, 0.3, 21, 1.2, 67, 1196, 525, 1.0, 1, 7.6, 0, 19, 9.8, 13.1, 3.4)),
    ("Cola soft drink", (0, 10.6, 0, 9.0, 2, 0.1, 0, 2, 4, 0, 0, 0.1, 0, 0, 0, 0, 0)),
    ("Mushrooms, UV-exposed, raw", (3.1, 3.3, 1.0, 2.0, 3, 0.5, 9, 318, 5, 0.5, 1, 9.3, 11.2, 2.1, 0, 0.2, 0)),
]

SYMPTOMS: dict[str, list[str]] = {
    "diabetes": ["I am always thirsty", "I need to urinate a lot at night", "my vision is blurred some days",
                 "small cuts on my feet heal slowly", "my toes tingle", "I lose weight without trying",
                 "I am hungry all the time", "I get skin infections again and again", "numbness in my feet"],
    "heart": ["I get breathless when I climb stairs", "my ankles are swollen in the evening",
              "I notice palpitations", "my heartbeat races and skips", "an ache spreads to my jaw when I walk fast",
              "I need extra pillows to sleep", "I get dizzy and break out in a cold sweat",
              "my legs swell by the end of the day"],
    "thyroid": ["I always feel cold", "my hair is thinning", "my skin is very dry", "I am constipated",
                "my face looks puffy", "my voice is hoarse", "I gained weight with no change in diet",
                "my hands have a tremor", "there is a swelling at the front of my neck", "heat makes me sweat badly"],
    "none": ["I have a runny nose", "I keep sneezing", "I have a sore throat", "I sprained my wrist",
             "my eyes itch in spring", "I have a toothache", "there is a rash on my arm after gardening",
             "my back hurts after I lifted boxes", "I have an earache", "my knee clicks when I squat"],
}
SHARED = ["I feel tired", "I have low energy"]

RETRIEVAL_QUESTIONS = [
    ("Which drinks raise blood glucose quickly?", "diabetes", "syn-diabetes-diet"),
    ("How do I fill my plate with vegetables and grains?", "diabetes", "syn-diabetes-diet"),
    ("Why does fiber help after a meal?", "diabetes", "syn-diabetes-diet"),
    ("Can alcohol cause low blood sugar?", "diabetes", "syn-diabetes-diet"),
    ("How much sodium per day is the limit?", "heart", "syn-heart-diet"),
    ("Which fish give omega-3 fatty acids?", "heart", "syn-heart-diet"),
    ("What lowers LDL cholesterol in the diet?", "heart", "syn-heart-diet"),
    ("Why is potassium good for blood pressure?", "heart", "syn-heart-diet"),
    ("Which foods give iodine?", "thyroid", "syn-thyroid-diet"),
    ("When do I take calcium supplements with thyroid tablets?", "thyroid", "syn-thyroid-diet"),
    ("Is seaweed safe for the thyroid?", "thyroid", "syn-thyroid-diet"),
    ("Which foods give selenium?", "thyroid", "syn-thyroid-diet"),
    ("thirsty and urinate at night", None, "syn-diabetes-symptoms"),
    ("tingling numbness in the feet", None, "syn-diabetes-symptoms"),
    ("swollen ankles and extra pillows at night", None, "syn-heart-symptoms"),
    ("pain spreads to the jaw and left arm", None, "syn-heart-symptoms"),
    ("feel cold with dry skin and thinning hair", None, "syn-thyroid-symptoms"),
    ("swelling at the front of the neck", None, "syn-thyroid-symptoms"),
]

SOURCE_IDS = {
    ("diabetes", "disease"): "syn-diabetes-symptoms", ("heart", "disease"): "syn-heart-symptoms",
    ("thyroid", "disease"): "syn-thyroid-symptoms", ("diabetes", "diet_plan"): "syn-diabetes-diet",
    ("heart", "diet_plan"): "syn-heart-diet", ("thyroid", "diet_plan"): "syn-thyroid-diet",
}


def write_documents(out: Path) -> list[dict]:
    sources = []
    for (cond, kind), (title, pages) in DOCS.items():
        sid = SOURCE_IDS[(cond, kind)]
        rel = f"{kind}/{cond}/{sid}.md"
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{SYNTHETIC_NOTE}\n" + "\f".join(pages) + "\n", encoding="utf-8")
        sources.append({"id": sid, "title": title, "url": f"https://example.org/nutribuddy-synthetic/{sid}",
                        "licence": "CC0-1.0 (synthetic demo text)", "condition": cond, "kind": kind, "path": rel})
    (out / "sources.json").write_text(json.dumps({"sources": sources}, indent=2), encoding="utf-8")
    return sources


def write_food_data(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "nutrient.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name", "unit_name", "nutrient_nbr", "rank"])
        for i, (nid, name, unit) in enumerate(NUTRIENTS):
            w.writerow([nid, name, unit, "", i])
    with (folder / "food.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["fdc_id", "data_type", "description", "food_category_id", "publication_date"])
        for i, (name, _) in enumerate(FOODS):
            w.writerow([900001 + i, "synthetic", name, "", "2026-01-01"])
    with (folder / "food_nutrient.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "fdc_id", "nutrient_id", "amount"])
        row_id = 1
        for i, (_, amounts) in enumerate(FOODS):
            for (nid, _, _), amount in zip(NUTRIENTS, amounts):
                w.writerow([row_id, 900001 + i, nid, amount])
                row_id += 1


def screening_items(seed: int = 7, per_class: int = 15) -> list[dict]:
    rng = random.Random(seed)
    items = []
    for label, phrases in SYMPTOMS.items():
        for _ in range(per_class):
            picked = rng.sample(phrases, k=rng.choice([2, 3]))
            if label != "none" and rng.random() < 0.35:
                picked.append(rng.choice(SHARED))
            rng.shuffle(picked)
            text = ", ".join(picked[:-1]) + " and " + picked[-1] + "."
            items.append({"text": text[0].upper() + text[1:], "label": label})
    rng.shuffle(items)
    return items


def write_eval_sets(out: Path, seed: int = 7) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "screening.jsonl").open("w", encoding="utf-8") as fh:
        for item in screening_items(seed):
            fh.write(json.dumps(item) + "\n")
    with (out / "retrieval.jsonl").open("w", encoding="utf-8") as fh:
        for q, cond, sid in RETRIEVAL_QUESTIONS:
            kind = "diet_plan" if sid.endswith("-diet") else "disease"
            fh.write(json.dumps({"question": q, "condition": cond, "kind": kind, "source_id": sid}) + "\n")


def write_all(out: Path, seed: int = 7) -> Path:
    out = Path(out)
    write_documents(out)
    write_food_data(out / "food_data" / "synthetic")
    write_eval_sets(out / "eval", seed)
    return out
