"""Sprawdza, które źródła koncertów odpowiadają z GitHub Actions."""
import json, re, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
q = urllib.parse.quote


def get(url, js=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json" if js else "text/html,*/*", "Accept-Language": "en"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            b = r.read().decode("utf-8", "replace")
            return r.status, b, time.time() - t
    except Exception as e:  # noqa: BLE001
        return getattr(e, "code", "ERR"), str(e)[:150], time.time() - t


def probe(name, url, js=False, pat=None):
    code, body, dt = get(url, js)
    info = f"len={len(body)}"
    if code == 200:
        ld = len(re.findall(r'"@type"\s*:\s*"(?:Music)?Event"', body))
        info += f" jsonld_events={ld}"
        if pat:
            info += " hits=" + json.dumps(re.findall(pat, body)[:6], ensure_ascii=False)[:500]
        else:
            info += " head=" + json.dumps(body[:300], ensure_ascii=False)
    else:
        info += " " + body
    print(f"[{name}] {code} {dt:.1f}s {info}\n")


probe("songkick-search", "https://www.songkick.com/search?type=artists&query=Ado", pat=r'href="(/artists/\d+-[^"]+)"')
probe("songkick-cal", "https://www.songkick.com/artists/8932659-ado/calendar", pat=r'"startDate":"([^"]+)"[^}]*?"name":"([^"]+)"')
probe("jame", "https://www.jame-world.com/en/concerts.html", pat=r'<h3[^>]*>([^<]+)')
probe("eventim-api", "https://public-api.eventim.com/websearch/search/api/exploration/v2/productGroups?webId=web__eventim-de&language=de&search_term=" + q("BABYMETAL"), js=True, pat=r'"name":"([^"]+)"')
probe("eventernote", "https://www.eventernote.com/actors/IOSYS/10656/events", pat=r'<h4><a[^>]*>([^<]+)')
probe("vocadb-events", "https://vocadb.net/api/releaseEvents?sort=Date&maxResults=10&afterDate=2026-10-01&fields=Venue", js=True, pat=r'"name":"([^"]+)"')
probe("vocafest", "https://vocafest.co.uk/", pat=r'<title>([^<]+)')
probe("nautiljon", "https://www.nautiljon.com/agenda/", pat=r'<title>([^<]+)')
probe("animexx", "https://www.animexx.de/events/", pat=r'<title>([^<]+)')
probe("dice", "https://dice.fm/search?query=anime%20rave", pat=r'<title>([^<]+)')
probe("ra", "https://ra.co/events/pl/warsaw", pat=r'<title>([^<]+)')
probe("bit-web", "https://www.bandsintown.com/a/9614017-babymetal", pat=r'<title>([^<]+)')
probe("ticketmaster-web", "https://www.ticketmaster.de/search?q=babymetal", pat=r'<title>([^<]+)')
probe("lastfm-events", "https://www.last.fm/music/BABYMETAL/+events", pat=r'<title>([^<]+)')
probe("musicbrainz-events", "https://musicbrainz.org/ws/2/event?query=" + q('artist:"BABYMETAL"') + "&fmt=json&limit=5", js=True, pat=r'"name":"([^"]+)"')
