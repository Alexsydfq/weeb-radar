import re, urllib.request
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept-Language": "en"}), timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", "ERR"), str(e)
c, b = get("https://www.eventernote.com/events/search?keyword=Camellia")
i = b.find('href="/events/')
i = b.find('href="/events/', i + 1)
print("EN", c, [m.start() for m in re.finditer(r'href="/events/\d+', b)][:5]); print(b[i - 1200: i + 1500])
for u in ["https://www.songkick.com/search?query=ado&type=artists", "https://www.songkick.com/search?query=zutomayo"]:
    c, b = get(u)
    links = re.findall(r'href="(/artists/\d+-[^"/?]+)', b)
    print("SK", u, c, [l for l in links if "ado" in l or "zutomayo" in l or "zutto" in l][:5], len(links))
