"""Parses the sample feeds, checks the parser, and runs the JS classifier through node.

Run from the project root:  python tests/test_all.py
Writes tests/parsed_sample.json (used by the node step).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_menus as fm  # noqa: E402

TESTS = Path(__file__).resolve().parent


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        check.failed = True


check.failed = False

# --- component parsing
c = fm.parse_component("Linssi-kikhernekeitto Berkoukeh (*, A, ILM, L, M, Veg)")
check(c["name"] == "Linssi-kikhernekeitto Berkoukeh", "dish name split from codes")
check(c["diets"] == ["*", "A", "ILM", "L", "M", "Veg"], "diet codes parsed")
c = fm.parse_component("Pasta (kasvis ja juusto)")
check(c["diets"] == [] and c["name"] == "Pasta (kasvis ja juusto)", "non-code brackets are kept in the name")
c = fm.parse_component("Mustaherukkamoussea")
check(c["diets"] == [], "dish without brackets has no codes")

# --- student price formats
for text, want in [
    ("Opiskelija 1,46 € / Henkilökunta 4,59 € / Vierailija 4,59 €", 1.46),
    ("13,30€ / opisk.3,10 €", 3.10),
    ("13,30 €", None),
    ("Opisk. 1,80€", 1.80),
    ("Op 0,66 € / Hk 0,66€ / Vieras 1,40 €", 0.66),
]:
    check(fm.parse_student_price(text) == want, f"student price from {text!r}")

# --- feed parsing
restaurants = []
for rid, name, fn in [("snellmania", "Snellmania", "sample_snellmania.json"),
                      ("tietoteknia", "Tietoteknia", "sample_tietoteknia.json")]:
    data = json.loads((TESTS / fn).read_text(encoding="utf-8"))
    days = fm.parse_feed(data)
    restaurants.append({"id": rid, "name": name, "url": data["RestaurantUrl"], "days": days})
check(len(restaurants[1]["days"][0]["meals"]) == 5, "empty placeholder entry dropped (Tietoteknia Mon)")
check(restaurants[1]["days"][0]["meals"][3]["studentPrice"] is None, "meat-only buffet has no student price")
check(restaurants[0]["days"][0]["date"] == "2026-10-19", "date trimmed to YYYY-MM-DD")

(TESTS / "parsed_sample.json").write_text(
    json.dumps({"restaurants": restaurants}, ensure_ascii=False, indent=1), encoding="utf-8")

# --- JS classifier
js = r"""
const root = process.argv[1];
const f = require(root + '/docs/filters.js');
const data = JSON.parse(require('fs').readFileSync(root + '/tests/parsed_sample.json', 'utf8'));
const out = [];
for (const r of data.restaurants) for (const d of r.days) for (const m of d.meals)
  out.push({r: r.name, date: d.date, cat: m.category, first: m.dishes[0].name, status: f.classifyMeal(m)});
console.log(JSON.stringify(out));
"""
res = subprocess.run(["node", "-e", js, str(ROOT)], capture_output=True, text=True)
if res.returncode != 0:
    print(res.stderr)
    check(False, "node classifier ran")
else:
    rows = json.loads(res.stdout)
    for row in rows:
        print(f"  {row['r']:12} {row['date']} {row['cat'][:16]:16} {row['status']:7} {row['first'][:48]}")
    want = {
        "Linssi-kikhernekeitto Berkoukeh": "vegan",
        "Kasvisbolognesea": "vegan",
        "Jauhelihapihvejä ja metsäsienikastiketta": "meat",
        "Pitkään haudutettua nautaa": "meat",
        "Tomaattikeittoa": "veg",           # via category Kasviskeitto
        "Bataatti-kookoscurrya": "vegan",
        "Kylmäsavulohipastaa ja tilliä": "fish",
        "Kanaa Kiovan tapaan": "meat",
        "Quornia tomaattikastikkeessa": "veg",
        "Bolognesekastiketta": "unsure",
        "Aasialainen kalapihvi": "fish",
        "Porsaan lehtipihvi": "meat",
        "Juustoista kasvislasagnette": "veg",
        "Mausteista broileripataa - Broileripataa Mexicali": "meat",
        "Lihamureketta ja sinappista kastiketta": "meat",
        "Puna-ahventa ja sitruuna-smetanakastiketta": "fish",
        "Vuohenjuusto-tomaattikeittoa": "unsure",
        "Chili con Vege Unlimited® jauhismurusta": "vegan",
        "Tonnikala-pastavuokaa": "fish",
        "Makkaravalikoima": "meat",
        "Paahdettua broileria, kirsikkatomaatteja ja pinaattia": "meat",
        "Gratinoitua halloumi-kasvispastaa": "veg",
        "Kalapyöryköitä": "fish",
    }
    got = {row["first"]: row["status"] for row in rows}
    for dish, status in want.items():
        check(got.get(dish) == status, f"{dish[:46]!r} -> {status} (got {got.get(dish)})")

sys.exit(1 if check.failed else 0)
