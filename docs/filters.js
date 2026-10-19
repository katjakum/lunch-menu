/*
 * Dish and meal classification. Edit the word lists below to tune the filters.
 * Words are matched as substrings of the lowercase dish name, so "liha" also
 * catches "jauheliha" and "lihamureke".
 */
(function (root) {
  // Meat words. Substitutes (see PLANT) override these.
  const MEAT = /liha|kana|broileri|kalkkuna|possu|porsa|sika|nauta|naudan|lammas|kinkku|pekoni|bacon|makkara|nakki|salami|savupalvi|kebab|ankka|riista|poro|hirvi|chorizo/;
  // Fish and seafood.
  const FISH = /kala|lohi|silakka|muikku|ahven|kampela|turska|seiti|siika|rapu|äyriä/;
  // Plant-based words. A match here wins over MEAT/FISH ("kasvispyörykkä", "quornia").
  const PLANT = /kasvis|vege|vegaan|quorn|tofu|härkis|soija|mifu|falafel|seitan|linssi|kikher|papu|bataatti|juures/;
  // Categories that are not main dishes.
  const DESSERT = /makea|jälkkäri|jälkiruoka/i;

  function normalize(s) {
    // eggs ("kananmuna") contain "kana" but are not meat
    return String(s || "").toLowerCase().replace(/kananmun\w*/g, "");
  }

  // 'vegan' (tagged Veg) | 'veg' | 'meat' | 'fish' | 'other' (no signal, e.g. a sauce)
  function classifyDish(dish) {
    const name = normalize(dish.name);
    const diets = (dish.diets || []).map((d) => d.toLowerCase());
    if (diets.includes("veg")) return "vegan";
    if (PLANT.test(name)) return "veg";
    if (MEAT.test(name)) return "meat";
    if (FISH.test(name)) return "fish";
    return "other";
  }

  // 'meat' | 'fish' | 'vegan' | 'veg' | 'unsure'
  function classifyMeal(meal) {
    const kinds = meal.dishes.map(classifyDish);
    if (kinds.includes("meat")) return "meat";
    if (kinds.includes("fish")) return "fish";
    if (kinds.every((k) => k === "vegan")) return "vegan";
    // Positive "vegetarian" evidence must come from the category or the main dish (the first item).
    // Veg-tagged sides like potatoes or rice say nothing about the main.
    if (/kasvis/i.test(meal.category || "") || kinds[0] === "veg" || kinds[0] === "vegan") return "veg";
    return "unsure";
  }

  // mode: 'all' | 'nomeat' (fish ok) | 'vegetarian' (no meat, no fish) | 'vegan'
  function visible(status, mode, includeUnsure) {
    if (mode === "all") return true;
    if (status === "unsure") return mode !== "vegan" && includeUnsure;
    if (mode === "nomeat") return status !== "meat";
    if (mode === "vegetarian") return status === "veg" || status === "vegan";
    if (mode === "vegan") return status === "vegan";
    return true;
  }

  function isDessert(category) {
    return DESSERT.test(category || "");
  }

  const api = { classifyDish, classifyMeal, visible, isDessert };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MenuFilters = api;
})(typeof self !== "undefined" ? self : this);
