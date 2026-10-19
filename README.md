# Kuopio lunch menus

Fetches the lunch menus of Snellmania, Tietoteknia and Canthia from Compass Group's
public menu feed, and shows them on a small static page with a "no meat" filter.

```
scripts/fetch_menus.py          fetches the feeds, writes docs/menus.json
docs/index.html, docs/filters.js  the page (filters.js holds the meat/fish word lists)
.github/workflows/update-menus.yml  runs the fetcher on weekdays and commits changes
tests/test_all.py               python tests/test_all.py
```

## Set up (all free)
1. Create a GitHub repo and push this folder to it.
2. Settings > Pages > Deploy from a branch > `main` / `/docs`.
3. Actions tab > "Update lunch menus" > Run workflow (once, to fetch real data).
   The included `docs/menus.json` is only sample data for 19-23 Oct and gets replaced.
4. Open the Pages URL.

If GitHub pauses the schedule after a long time without repo activity, re-enable it in the Actions tab.

## Tweaking the filter
Edit the word lists at the top of `docs/filters.js` (`MEAT`, `FISH`, `PLANT`). A dish is
classified from its name and diet tags only, so it can be wrong. Dishes with no signal
show a "?" badge. Always check allergens at the restaurant.

## Adding a restaurant
Add a line to `RESTAURANTS` in `scripts/fetch_menus.py`. The `costNumber` is in the
`menuapi/feed/json?costNumber=...` request your browser makes when you open the restaurant page.
