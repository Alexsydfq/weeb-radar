import json, re, time, urllib.parse, urllib.request
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
q = urllib.parse.quote
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", "ERR"), str(e)
for u in ["https://www.songkick.com/search?utf8=%E2%9C%93&type=initial&query=BABYMETAL",
          "https://www.songkick.com/search?query=BABYMETAL&type=artists",
          "https://www.songkick.com/search?page=1&per_page=10&query=Hatsune+Miku&type=artists"]:
    c, b = get(u)
    print(u, c, re.findall(r'href="(/artists/\d+-[^"/?]+)', b)[:8])
c, b = get("https://www.songkick.com/artists/6614739-babymetal/calendar")
print("cal", c, len(b))
for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', b, re.S):
    try:
        d = json.loads(m.group(1))
    except Exception as e:
        print("bad", e); continue
    for e in (d if isinstance(d, list) else [d]):
        if "Event" in str(e.get("@type")):
            loc = e.get("location", {})
            print(" ", e.get("startDate"), e.get("name")[:80], "|", loc.get("name"), "|", (loc.get("address") or {}).get("addressLocality"), (loc.get("address") or {}).get("addressCountry"))
c, b = get("https://www.eventernote.com/actors/search?keyword=" + q("名取さな"))
print("en-search", c, re.findall(r'href="(/actors/[^"]+/\d+)"', b)[:5])
c, b = get("https://www.eventernote.com/events/search?keyword=" + q("hololive") + "&year=2026")
print("en-ev", c, re.findall(r'<h4><a[^>]*>([^<]+)', b)[:5])
