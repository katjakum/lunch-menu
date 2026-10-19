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

# --- Antell Round weekly list (data copied from the weekly list PDF, week 43)
from datetime import date  # noqa: E402

import antell  # noqa: E402

WEEK43 = [
    ("Maanantai 19.10.", [
        ("Kotiruokalounas", "Nakkikastiketta (A, G, L, M), Perunoita (G, L, M, VEG)"),
        ("Makumatka", "Rapeita chilikalafileitä (A, L), Kermaperunoita (A, G, L), Limejogurttia (A, G, L)"),
        ("Kasvislounas", "Papu-kasvistortillat (G, L, M, VEG), Limejogurttia (A, G, L), Salsakastiketta (G, L, M, VEG)")]),
    ("Tiistai 20.10.", [
        ("Kotiruokalounas", "Lohikastiketta (L, G, A), Keitetty pasta (VEG, M, L, A)"),
        ("Makumatka", "Kebabtortillat (L, A), Avokado-kermaviilikastiketta (L, G, A)"),
        ("Kasvislounas", "Tofua ja kasviksia hapanimeläkastikkeessa (VEG, M, L, G, A), Riisiä (VEG, M, L, G)")]),
    ("Keskiviikko 21.10.", [
        ("Kotiruokalounas", "Jauheliha lasagnette (A, L)"),
        ("Makumatka", "Kanaa kermaisessa valkosipulikastikkeessa (A, G, L), Pinaattiriisiä (G, L, M, VEG)"),
        ("Kasvislounas", "Perunoita (G, L, M, VEG), Kasvisstroganoffia (A, G, L, M, VEG)")]),
    ("Torstai 22.10.", [
        ("Kotiruokalounas", "Kanapyöryköitä (A, G, L, M), Currykastiketta (A, G, L), Riisiä (G, L, M, VEG)"),
        ("Makumatka", "Karamellisoitua possunkylkeä (A, G, L, M), Paistettua nuudelia ja neulapapuja (A, L, M)"),
        ("Kasvislounas", "Kasvispyöryköitä (A, G, L, M), Perunoita (G, L, M, VEG), Yrtti-jogurttikastiketta (A, G, L)")]),
    ("Perjantai 23.10.", [
        ("Kotiruokalounas", "Jauhelihapyöryköitä (A, L, M), Kermaista ruskeakastiketta (A, G, L), Perunoita (G, L, M, VEG)"),
        ("Makumatka", "Sriracha-maustettuja kanaburgereita (A, L), Lohkoperunoita (G, L, M, VEG)"),
        ("Kasvislounas", "Chili con Härkistä (G, L, M, VEG), Riisiä (G, L, M, VEG)")]),
]


def antell_table_html():
    out = ["<html><body><nav>Helsinki Vantaa Antell Round</nav><h1>Antell Round lounaslista viikko 43</h1>"]
    for head, rows in WEEK43:
        out.append(f"<h2>{head}</h2><table>")
        for cat, dishes in rows:
            out.append(f"<tr><td>{cat}</td><td>{dishes}</td></tr>")
        out.append("<tr><td>Salaattilounas</td><td></td></tr></table>")
    out.append("<p>Ruokalajien ainesosatiedot löydät ravintolan verkkosivulta. Pidätämme oikeuden muutoksiin.</p>")
    out.append("<script>var x = 'Kotiruokalounas (A)';</script></body></html>")
    return "".join(out)


def antell_div_html():
    # letter-spaced headings, divs instead of a table, category and dishes in one text node
    out = ["<html><body>"]
    for head, rows in WEEK43:
        name, dd = head.split(" ")
        out.append(f"<h2>{' '.join(name.upper())} {dd}</h2>")
        for cat, dishes in rows:
            out.append(f"<div>{cat} {dishes}</div>")
    out.append("</body></html>")
    return "".join(out)


TODAY = date(2026, 10, 20)
a_tab = antell.parse_html(antell_table_html(), TODAY)
a_div = antell.parse_html(antell_div_html(), TODAY)
check(len(a_tab) == 5 and [d["date"] for d in a_tab][0] == "2026-10-19", "antell: 5 days, dates with year")
check(all(len(d["meals"]) == 3 for d in a_tab), "antell: 3 meals per day, empty salad row and footer dropped")
check(a_tab[0]["meals"][0]["dishes"] == [{"name": "Nakkikastiketta", "diets": ["A", "G", "L", "M"]},
                                         {"name": "Perunoita", "diets": ["G", "L", "M", "VEG"]}],
      "antell: dishes split with their diet codes")
check([m["studentPrice"] for m in a_tab[0]["meals"]] == [3.10, 5.90, 3.10], "antell: student prices by category")
check(a_tab == a_div, "antell: table layout and letter-spaced div layout parse the same")
check(antell.parse_lines(["Maanantai 4.1.", "Kotiruokalounas", "Soppaa (A)"], date(2026, 12, 29))[0]["date"] == "2027-01-04",
      "antell: year rolls over in late December")
check(antell.parse_lines(["Intro text", "no days here"], TODAY) == [], "antell: page without days gives no days")
restaurants.append({"id": "antell-round", "name": "Antell Round", "url": antell.BASE_URL, "days": a_tab})

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
    got = {row["first"]: row["status"] for row in rows if row["r"] != "Antell Round"}
    for dish, status in want.items():
        check(got.get(dish) == status, f"{dish[:46]!r} -> {status} (got {got.get(dish)})")

    want_antell = {
        ("2026-10-19", "Kotiruokalounas"): "meat", ("2026-10-19", "Makumatka"): "fish",
        ("2026-10-19", "Kasvislounas"): "veg",
        ("2026-10-20", "Kotiruokalounas"): "fish", ("2026-10-20", "Makumatka"): "meat",
        ("2026-10-20", "Kasvislounas"): "vegan",
        ("2026-10-21", "Kotiruokalounas"): "meat", ("2026-10-21", "Makumatka"): "meat",
        ("2026-10-21", "Kasvislounas"): "vegan",
        ("2026-10-22", "Kotiruokalounas"): "meat", ("2026-10-22", "Makumatka"): "meat",
        ("2026-10-22", "Kasvislounas"): "veg",
        ("2026-10-23", "Kotiruokalounas"): "meat", ("2026-10-23", "Makumatka"): "meat",
        ("2026-10-23", "Kasvislounas"): "vegan",
    }
    got_a = {(row["date"], row["cat"]): row["status"] for row in rows if row["r"] == "Antell Round"}
    for key, status in want_antell.items():
        check(got_a.get(key) == status, f"Antell {key[0]} {key[1]} -> {status} (got {got_a.get(key)})")

sys.exit(1 if check.failed else 0)
