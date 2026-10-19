"""Antell Round: reads the weekly print list and returns the same day/meal structure
as the Compass feed, so the page can show both the same way.

The print list is https://antell.fi/lounas/kuopio/round/?print_lunch_list_week=1&week-offset=0
Each day has a heading ("Maanantai 19.10.") followed by rows of
    Category | Dish (codes), Dish (codes), ...

The parser works on the page's plain text lines, not on CSS selectors, so small markup
changes should not break it. If the layout changes a lot, fetch() raises an error instead
of publishing empty data.
"""
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://antell.fi/lounas/kuopio/round/"
HEADERS = {"User-Agent": "lunch-menu-hobby-project/1.0"}
WEEK_OFFSETS = (0, 1)  # this week and next week (next week may not be published yet)
LUNCH_TIME = "10.00–13.30"
FULL_PRICE = "12,50"
# The weekly list has no prices. These student prices come from the restaurant page
# (shown there as "12,50/3,10 €" = full price / student price). Update them if they change.
STUDENT_PRICES = {"kotiruokalounas": 3.10, "makumatka": 5.90, "kasvislounas": 3.10}

DAY_RE = re.compile(
    r"^(maanantai|tiistai|keskiviikko|torstai|perjantai|lauantai|sunnuntai)(\d{1,2})\.(\d{1,2})\.?$")
KNOWN_CATEGORIES = ("kotiruokalounas", "makumatka", "kasvislounas", "salaattilounas", "keittolounas")
SKIP_LINE = re.compile(r"ruokalajien|pidätämme|lounaslista viikko|antell round$|©", re.I)
TRAILING_PARENS = re.compile(r"\s*\(([^()]*)\)\s*$")
CODE_TOKEN = re.compile(r"^[A-Za-zÄÖäö*]{1,4}$")


def parse_dish(raw: str) -> dict:
    raw = raw.strip()
    name, diets = raw, []
    m = TRAILING_PARENS.search(raw)
    if m:
        tokens = [t.strip() for t in m.group(1).split(",") if t.strip()]
        if tokens and all(CODE_TOKEN.match(t) for t in tokens):
            diets = tokens
            name = raw[: m.start()].strip()
    return {"name": name, "diets": diets}


def split_dishes(text: str) -> list:
    # "Nakkikastiketta (A, G, L, M), Perunoita (G, L, M, VEG)" -> split after each ")," only
    parts = re.split(r"(?<=\))\s*,\s*", text.strip())
    return [parse_dish(p) for p in parts if p.strip()]


def _year_for(month: int, today: date) -> int:
    if month == 1 and today.month == 12:
        return today.year + 1
    if month == 12 and today.month == 1:
        return today.year - 1
    return today.year


def _looks_like_category(line: str, next_line) -> bool:
    return ("(" not in line and "," not in line and len(line) <= 30
            and next_line is not None and "(" in next_line)


def parse_lines(lines, today: date) -> list:
    cleaned = [" ".join(l.split()) for l in lines]
    cleaned = [l for l in cleaned if l]
    days, day, current = [], None, None

    def finish():
        nonlocal current
        if day is not None and current is not None:
            dishes = split_dishes(" ".join(current["chunks"]))
            if dishes:
                key = current["category"].lower()
                student = STUDENT_PRICES.get(key)
                price_text = (f"Opiskelija {student:.2f} € / täysi {FULL_PRICE} €".replace(".", ",")
                              if student is not None else "")
                day["meals"].append({
                    "category": current["category"],
                    "priceText": price_text,
                    "studentPrice": student,
                    "dishes": dishes,
                })
        current = None

    for i, line in enumerate(cleaned):
        nxt = cleaned[i + 1] if i + 1 < len(cleaned) else None
        # Day headings can come letter-spaced ("M A A N A N T A I 19.10."), so squeeze spaces first.
        m = DAY_RE.match(re.sub(r"\s+", "", line).lower())
        if m:
            finish()
            try:
                d = date(_year_for(int(m.group(3)), today), int(m.group(3)), int(m.group(2)))
            except ValueError:
                day = None
                continue
            day = {"date": d.isoformat(), "lunchTime": LUNCH_TIME, "meals": []}
            days.append(day)
            continue
        if day is None or SKIP_LINE.search(line):
            continue
        low = line.lower()
        known = next((c for c in KNOWN_CATEGORIES if low.startswith(c)), None)
        if known:
            finish()
            current = {"category": line[: len(known)], "chunks": []}
            rest = line[len(known):].strip(" :|-–")
            if rest:
                current["chunks"].append(rest)
        elif _looks_like_category(line, nxt):
            finish()
            current = {"category": line, "chunks": []}
        elif current is not None:
            current["chunks"].append(line)
    finish()
    return days


def parse_html(html: str, today: date) -> list:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return parse_lines(soup.get_text("\n").splitlines(), today)


def fetch(r: dict) -> dict:
    today = datetime.now(ZoneInfo("Europe/Helsinki")).date()
    by_date = {}
    for offset in WEEK_OFFSETS:
        try:
            resp = requests.get(
                BASE_URL,
                params={"print_lunch_list_week": 1, "week-offset": offset},
                headers=HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            days = [d for d in parse_html(resp.text, today) if d["meals"]]
            if not days and offset == 0:
                raise ValueError("no menu days found in the Antell weekly list (layout changed?)")
            for d in days:
                by_date.setdefault(d["date"], d)
        except Exception:
            if offset == 0:  # this week must work; next week is optional
                raise
    return {
        "id": r["id"],
        "name": r["name"],
        "url": r.get("url") or BASE_URL,
        "days": [by_date[k] for k in sorted(by_date)],
    }
