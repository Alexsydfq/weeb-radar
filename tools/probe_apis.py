"""Sprawdza, które darmowe API z koncertami i premierami odpowiadają z GitHub Actions."""
import json, sys, time, urllib.parse, urllib.request

UA = "WeebRadar/0.1 (https://github.com/Alexsydfq/weeb-radar)"
ARTISTS = ["Ado", "YOASOBI", "Hatsune Miku", "Babymetal", "Camellia"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode()), time.time() - t
    except Exception as e:  # noqa: BLE001
        return getattr(e, "code", "ERR"), str(e)[:200], time.time() - t


def show(name, url, pick):
    code, body, dt = get(url)
    try:
        out = pick(body) if code == 200 else body
    except Exception as e:  # noqa: BLE001
        out = f"parse error {e}: {str(body)[:200]}"
    print(f"[{name}] {code} {dt:.1f}s -> {json.dumps(out, ensure_ascii=False)[:600]}")


q = urllib.parse.quote
for a in ARTISTS:
    print(f"\n=== {a}")
    show("bandsintown", f"https://rest.bandsintown.com/artists/{q(a)}/events?app_id=weebradar&date=upcoming",
         lambda b: [(e["datetime"][:10], e["venue"]["city"], e["venue"]["country"]) for e in b][:8])
    show("musicbrainz", "https://musicbrainz.org/ws/2/release-group?fmt=json&limit=5&query="
         + q(f'artist:"{a}" AND firstreleasedate:[2026-09-01 TO 2027-12-31]'),
         lambda b: [(r["title"], r.get("first-release-date")) for r in b["release-groups"]])
    time.sleep(1.2)
    show("deezer", "https://api.deezer.com/search/album?limit=50&q=" + q('artist:"' + a + '"'),
         lambda b: sorted({(x["title"], x["artist"]["name"]) for x in b["data"]})[:5])
    show("itunes", f"https://itunes.apple.com/search?term={q(a)}&entity=album&country=JP&limit=50",
         lambda b: sorted([(r["releaseDate"][:10], r["collectionName"]) for r in b["results"]], reverse=True)[:5])
    show("vocadb", f"https://vocadb.net/api/artists?query={q(a)}&maxResults=1", lambda b: [x["name"] for x in b["items"]])
