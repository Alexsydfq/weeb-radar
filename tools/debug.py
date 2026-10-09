import json, re, sys, urllib.request, urllib.parse
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
def get(u, ua=UA):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": ua, "Accept-Language": "en"}), timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", "ERR"), str(e)
c, b = get("https://www.eventernote.com/events/search?keyword=Camellia")
i = b.find("2026-1")
print("EN", c, len(b), "first date at", i); print(b[max(0, i - 1500): i + 400])
c, b = get("https://www.songkick.com/artists/5643294-babymetal/calendar")
print("SK", c, len(b), b.count("application/ld+json"), re.findall(r'"startDate":"([^"]+)"', b)[:10])
api = "WeebRadar/1.0 (https://github.com/Alexsydfq/weeb-radar)"
for n in ["Camellia", "DECO*27", "Ado", "ZUTOMAYO", "Mori Calliope"]:
    c, b = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&language=en&format=json&limit=5&search=" + urllib.parse.quote(n), api)
    ids = [x["id"] for x in json.loads(b).get("search", [])] if c == 200 else []
    c2, b2 = get("https://www.wikidata.org/w/api.php?action=wbgetentities&props=claims&format=json&ids=" + "|".join(ids), api) if ids else (0, "{}")
    ent = json.loads(b2).get("entities", {}) if c2 == 200 else {}
    out = {k: [cl["mainsnak"].get("datavalue", {}).get("value") for cl in v.get("claims", {}).get("P3478", [])] for k, v in ent.items()}
    print("WD", n, c, c2, out)
