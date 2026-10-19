#!/usr/bin/env python3
"""Fetch lunch menus from Compass Group's public menu feed and write docs/menus.json.

Run:  python scripts/fetch_menus.py
Needs: pip install requests

Add a restaurant by adding a line to RESTAURANTS (the costNumber is the number in
the page's menuapi/feed/json?costNumber=... request).
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import antell

FEED_URL = "https://www.compass-group.fi/menuapi/feed/json"
# source "compass" (default) uses the Compass JSON feed; "antell" reads the Antell weekly list
RESTAURANTS = [
    {"id": "snellmania", "name": "Snellmania", "costNumber": "0437"},
    {"id": "tietoteknia", "name": "Tietoteknia", "costNumber": "0439"},
    {"id": "canthia", "name": "Canthia", "costNumber": "0436"},
    {"id": "antell-round", "name": "Antell Round", "source": "antell",
     "url": "https://antell.fi/lounas/kuopio/round/"},
]
OUT_FILE = Path(__file__).resolve().parent.parent / "docs" / "menus.json"
HEADERS = {"User-Agent": "lunch-menu-hobby-project/1.0"}

# A dish string looks like: "Linssi-kikhernekeitto Berkoukeh (*, A, ILM, L, M, Veg)"
TRAILING_PARENS = re.compile(r"\s*\(([^()]*)\)\s*$")
CODE_TOKEN = re.compile(r"^[A-Za-zÄÖäö*]{1,4}$")
# "Opiskelija 1,46 € / ..." (Snellmania), "Op 1,46 €" (Canthia), "13,30€ / opisk.3,10 €" (Tietoteknia)
STUDENT_PRICE = re.compile(r"\b(?:opisk\w*|op)\.?\s*([0-9]+(?:,[0-9]+)?)", re.I)


def parse_component(raw: str) -> dict:
    raw = raw.strip()
    name, diets = raw, []
    m = TRAILING_PARENS.search(raw)
    if m:
        tokens = [t.strip() for t in m.group(1).split(",") if t.strip()]
        # Only treat the brackets as diet codes if every token looks like a code
        if tokens and all(CODE_TOKEN.match(t) for t in tokens):
            diets = tokens
            name = raw[: m.start()].strip()
    return {"name": name, "diets": diets}


def parse_student_price(price_text: str):
    m = STUDENT_PRICE.search(price_text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def parse_feed(data: dict) -> list:
    days = []
    for day in data.get("MenusForDays") or []:
        meals = []
        for sm in day.get("SetMenus") or []:
            dishes = [parse_component(c) for c in (sm.get("Components") or []) if c and c.strip()]
            if not dishes:  # the feed contains empty placeholder entries
                continue
            price_text = (sm.get("Price") or "").strip()
            meals.append({
                "category": (sm.get("Name") or "").strip(),
                "priceText": price_text,
                "studentPrice": parse_student_price(price_text),
                "dishes": dishes,
            })
        days.append({
            "date": (day.get("Date") or "")[:10],
            "lunchTime": day.get("LunchTime"),
            "meals": meals,
        })
    return days


def fetch_restaurant(r: dict) -> dict:
    last_err = None
    for attempt in range(2):
        try:
            if r.get("source") == "antell":
                return antell.fetch(r)
            resp = requests.get(
                FEED_URL,
                params={"costNumber": r["costNumber"], "language": "fi"},
                headers=HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            data = resp.json()
            return {
                "id": r["id"],
                "name": r["name"],
                "url": data.get("RestaurantUrl"),
                "days": parse_feed(data),
            }
        except Exception as e:  # network error, bad JSON, HTTP error
            last_err = e
            time.sleep(3)
    raise last_err


def main() -> int:
    previous = {}
    if OUT_FILE.exists():
        try:
            previous = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    prev_by_id = {r["id"]: r for r in previous.get("restaurants", [])}

    restaurants, failures = [], 0
    for r in RESTAURANTS:
        try:
            restaurants.append(fetch_restaurant(r))
            print(f"ok    {r['name']}")
        except Exception as e:
            failures += 1
            print(f"FAIL  {r['name']}: {e}", file=sys.stderr)
            if r["id"] in prev_by_id:  # keep the last good data, flagged as stale
                old = dict(prev_by_id[r["id"]])
                old["stale"] = True
                restaurants.append(old)

    if failures == len(RESTAURANTS):
        return 1

    payload = {"restaurants": restaurants}
    old_payload = {"restaurants": previous.get("restaurants", [])}
    if payload == old_payload:
        print("No changes")
        return 0

    payload["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
