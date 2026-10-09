"""Nocny skaner Weeb Radar: sprawdza WSZYSTKICH artystów z watch.json w darmowych API.

Wynik trafia do candidates/*.json. To tylko kandydaci: rutyna skanu (Sonnet) czyta je,
weryfikuje i dopiero wtedy zapisuje do bazy. Skrypt nic nie wie o bazie poza tym,
co jest już w opublikowanych events.json i music.json, więc pomija tylko to, co tam jest.

Źródła (wszystkie bez klucza):
  muzyka:   iTunes Search (sklep JP), MusicBrainz release-groups, VocaDB songs
  koncerty: Songkick (kalendarz artysty, adres z relacji MusicBrainz), VocaDB release events
  Japonia:  Songkick (JP), Eventernote (wyszukiwarka eventów)

Uruchomienie: python3 tools/scan.py [--limit N] [--only music,concerts,japan]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "candidates"
IDS = ROOT / "tools" / "ids.json"
UA_API = "WeebRadar/1.0 (https://github.com/Alexsydfq/weeb-radar)"
UA_WEB = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

TODAY = dt.date.today()
MUSIC_FROM = TODAY - dt.timedelta(days=14)
MUSIC_TO = TODAY + dt.timedelta(days=30)
EUROPE = set(
    "AL AD AT BY BE BA BG HR CY CZ DK EE FI FR DE GR HU IS IE IT XK LV LI LT LU MT MD MC ME NL MK NO PL PT RO "
    "SM RS SK SI ES SE CH UA GB UK VA".split()
)
COUNTRY_CC = {
    "united kingdom": "UK", "uk": "UK", "england": "UK", "scotland": "UK", "wales": "UK", "germany": "DE",
    "france": "FR", "spain": "ES", "italy": "IT", "netherlands": "NL", "belgium": "BE", "poland": "PL",
    "czech republic": "CZ", "czechia": "CZ", "austria": "AT", "switzerland": "CH", "hungary": "HU",
    "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI", "ireland": "IE", "portugal": "PT",
    "slovakia": "SK", "slovenia": "SI", "croatia": "HR", "romania": "RO", "bulgaria": "BG", "greece": "GR",
    "lithuania": "LT", "latvia": "LV", "estonia": "EE", "luxembourg": "LU", "serbia": "RS", "japan": "JP",
    "ukraine": "UA", "iceland": "IS", "malta": "MT", "cyprus": "CY",
}
DROP_PAREN = re.compile(r"dowoln|japońsk|wokalist|^vo\.|^cv|festiwal|konwent", re.I)

errors: list[str] = []
stats: dict[str, int] = {}
lock = threading.Lock()


def bump(key: str, n: int = 1) -> None:
    with lock:
        stats[key] = stats.get(key, 0) + n


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"[\s\-_.,'’!?*~☆★♡♪:/()\[\]「」『』【】]+", "", s)


def terms_for(entry: str) -> list[str]:
    """'柊マグネタイト (Hiiragi Magnetite)' -> ['柊マグネタイト', 'Hiiragi Magnetite']."""
    out: list[str] = []
    for part in entry.split(" / "):
        m = re.match(r"(.+?)\s*\((.+)\)\s*$", part.strip())
        base, paren = (m.group(1), m.group(2)) if m else (part.strip(), "")
        out.append(base.strip())
        if paren and "," not in paren and not DROP_PAREN.search(paren):
            out.append(paren.strip())
    seen, res = set(), []
    for t in out:
        if t and norm(t) not in seen and len(norm(t)) >= 2:
            seen.add(norm(t))
            res.append(t)
    return res


def matches(name: str, terms: list[str]) -> bool:
    n = norm(name)
    return any(norm(t) and (norm(t) == n or norm(t) in n.split("&") or norm(t) in n) for t in terms)


class Http:
    """Prosty klient z odstępem między zapytaniami do jednego hosta."""

    def __init__(self, gap: float, ua: str = UA_API):
        self.gap, self.ua, self.last = gap, ua, 0.0
        self.lock = threading.Lock()

    def get(self, url: str, js: bool = True, tries: int = 3):
        for attempt in range(tries):
            with self.lock:
                wait = self.last + self.gap - time.time()
                if wait > 0:
                    time.sleep(wait)
                self.last = time.time()
            req = urllib.request.Request(url, headers={
                "User-Agent": self.ua, "Accept": "application/json" if js else "text/html", "Accept-Language": "en"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read().decode("utf-8", "replace")
                    return json.loads(body) if js else body
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < tries - 1:
                    time.sleep(10 * (attempt + 1))
                    continue
                if e.code in (404, 410):
                    return None
                raise
            except Exception:  # noqa: BLE001
                if attempt < tries - 1:
                    time.sleep(3)
                    continue
                raise
        return None


itunes = Http(3.1)
mb = Http(1.1)
vocadb = Http(0.4)
songkick = Http(1.0, UA_WEB)
eventernote = Http(1.5, UA_WEB)
q = urllib.parse.quote


def safe(label: str, fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001
        with lock:
            if len(errors) < 80:
                errors.append(f"{label}: {type(e).__name__} {str(e)[:120]}")
        bump("errors")
        return None


# ---------- muzyka ----------

def itunes_releases(entry: str, terms: list[str]) -> list[dict]:
    res = []
    for kind in ("album", "song"):
        url = (f"https://itunes.apple.com/search?term={q(terms[0])}&entity={kind}&attribute=artistTerm"
               f"&country=JP&limit=50")
        data = itunes.get(url) or {}
        bump("itunes_calls")
        for r in data.get("results", []):
            d = (r.get("releaseDate") or "")[:10]
            if not d or not (MUSIC_FROM.isoformat() <= d <= MUSIC_TO.isoformat()):
                continue
            if not matches(r.get("artistName", ""), terms):
                continue
            title = r.get("collectionName") if kind == "album" else r.get("trackName")
            res.append({
                "watch": entry, "artist": r.get("artistName"), "title": title, "released": d,
                "kind": "singiel" if kind == "song" or "Single" in (title or "") else ("EP" if " - EP" in (title or "") else "album"),
                "url": r.get("collectionViewUrl") or r.get("trackViewUrl"), "source": "itunes",
            })
        if kind == "album" and res:
            break  # single i tak pojawia się jako „album – Single”
    return res


def mb_releases(entry: str, terms: list[str]) -> list[dict]:
    names = " OR ".join(f'artist:"{t}"' for t in terms[:2])
    query = f"({names}) AND firstreleasedate:[{MUSIC_FROM} TO {MUSIC_TO}]"
    data = mb.get(f"https://musicbrainz.org/ws/2/release-group?fmt=json&limit=25&query={q(query)}") or {}
    bump("mb_calls")
    res = []
    for rg in data.get("release-groups", []):
        credit = "".join(c.get("name", "") + c.get("joinphrase", "") for c in rg.get("artist-credit", []))
        d = rg.get("first-release-date") or ""
        if len(d) < 10 or not matches(credit, terms) or rg.get("score", 0) < 80:
            continue
        res.append({
            "watch": entry, "artist": credit, "title": rg.get("title"), "released": d,
            "kind": {"Single": "singiel", "EP": "EP"}.get(rg.get("primary-type"), "album"),
            "url": f"https://musicbrainz.org/release-group/{rg['id']}", "source": "musicbrainz",
        })
    return res


def vocadb_id(entry: str, terms: list[str], ids: dict) -> int | None:
    rec = ids.setdefault(entry, {})
    if "vocadb" in rec:
        return rec["vocadb"]
    found = None
    for t in terms[:2]:
        data = vocadb.get(f"https://vocadb.net/api/artists?query={q(t)}&maxResults=3&nameMatchMode=Exact"
                          f"&fields=None") or {}
        bump("vocadb_calls")
        for a in data.get("items", []):
            if a.get("artistType") in ("Producer", "CoverArtist", "Circle", "OtherGroup", "Vocaloid",
                                       "UTAU", "SynthesizerV", "OtherVoiceSynthesizer", "Band", "Utaite",
                                       "Vocalist", "Unknown", "Label", "OtherIndividual", "Illustrator"):
                found = a["id"]
                break
        if found:
            break
    rec["vocadb"] = found
    return found


def vocadb_songs(entry: str, terms: list[str], ids: dict) -> list[dict]:
    aid = vocadb_id(entry, terms, ids)
    if not aid:
        return []
    url = (f"https://vocadb.net/api/songs?artistId[]={aid}&afterDate={MUSIC_FROM}&sort=PublishDate"
           f"&maxResults=20&fields=PVs&songTypes=Original,Remix,Cover,MusicPV&artistParticipationStatus=Everything")
    data = vocadb.get(url) or {}
    bump("vocadb_calls")
    res = []
    for s in data.get("items", []):
        d = (s.get("publishDate") or "")[:10]
        if not d or d < MUSIC_FROM.isoformat():
            continue
        pv = next((p.get("url") for p in s.get("pvs", []) if p.get("service") == "Youtube" and p.get("pvType") == "Original"), None)
        res.append({
            "watch": entry, "artist": s.get("artistString"), "title": s.get("defaultName") or s.get("name"),
            "released": d, "kind": "cover" if s.get("songType") == "Cover" else "singiel",
            "url": pv or f"https://vocadb.net/S/{s['id']}", "source": "vocadb",
        })
    return res


# ---------- koncerty ----------

def mb_songkick(entry: str, terms: list[str], ids: dict) -> str | None:
    rec = ids.setdefault(entry, {})
    if "songkick" in rec and rec.get("checked", "") >= (TODAY - dt.timedelta(days=30)).isoformat():
        return rec["songkick"]
    sk = None
    mbid = rec.get("mbid")
    if not mbid:
        names = " OR ".join(f'artist:"{t}"' for t in terms[:2])
        data = mb.get(f"https://musicbrainz.org/ws/2/artist?fmt=json&limit=5&query={q(names)}") or {}
        bump("mb_calls")
        for a in data.get("artists", []):
            names = [a.get("name", "")] + [x.get("name", "") for x in a.get("aliases", [])]
            if a.get("score", 0) >= 90 and any(matches(n, terms) for n in names):
                mbid = a["id"]
                break
        rec["mbid"] = mbid
    if mbid:
        data = mb.get(f"https://musicbrainz.org/ws/2/artist/{mbid}?fmt=json&inc=url-rels") or {}
        bump("mb_calls")
        for rel in data.get("relations", []):
            u = (rel.get("url") or {}).get("resource", "")
            m = re.search(r"songkick\.com/artists/(\d+[^/?#]*)", u)
            if m:
                sk = m.group(1)
            if "bandsintown.com" in u:
                rec["bandsintown"] = u
    rec["songkick"] = sk
    rec["checked"] = TODAY.isoformat()
    return sk


def cc_of(addr: dict) -> str:
    c = (addr or {}).get("addressCountry") or ""
    if isinstance(c, dict):
        c = c.get("name", "")
    c = c.strip()
    if len(c) == 2:
        return "UK" if c.upper() == "GB" else c.upper()
    return COUNTRY_CC.get(c.lower(), c[:20])


def songkick_events(entry: str, sk: str) -> list[dict]:
    page = songkick.get(f"https://www.songkick.com/artists/{sk}/calendar", js=False)
    bump("songkick_calls")
    if not page:
        return []
    res = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for e in data if isinstance(data, list) else [data]:
            if "Event" not in str(e.get("@type")):
                continue
            d = (e.get("startDate") or "")[:10]
            if not d or d < TODAY.isoformat():
                continue
            loc = e.get("location") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            addr = loc.get("address") or {}
            cc = cc_of(addr)
            if cc not in EUROPE and cc != "JP":
                continue
            res.append({
                "watch": entry, "name": html.unescape(e.get("name", "")), "date": d,
                "dateEnd": (e.get("endDate") or "")[:10] or None, "city": addr.get("addressLocality"),
                "cc": cc, "venue": loc.get("name"), "url": (e.get("url") or "").split("?")[0], "source": "songkick",
            })
    return res


def eventernote_events(entry: str, terms: list[str]) -> list[dict]:
    page = eventernote.get(f"https://www.eventernote.com/events/search?keyword={q(terms[0])}", js=False)
    bump("eventernote_calls")
    if not page:
        return []
    res = []
    for block in re.split(r'<li class="clearfix">', page)[1:]:
        title = re.search(r"<h4><a href=\"(/events/\d+)\"[^>]*>([^<]+)", block)
        date = re.search(r"(\d{4}-\d{2}-\d{2})", block)
        if not title or not date or date.group(1) < TODAY.isoformat():
            continue
        place = re.search(r'<a href="/places/\d+"[^>]*>([^<]+)', block)
        res.append({
            "watch": entry, "name": html.unescape(title.group(2)), "date": date.group(1),
            "city": None, "cc": "JP", "venue": html.unescape(place.group(1)) if place else None,
            "url": "https://www.eventernote.com" + title.group(1), "source": "eventernote",
        })
    return res


def vocadb_events() -> list[dict]:
    url = (f"https://vocadb.net/api/releaseEvents?afterDate={TODAY}&beforeDate={TODAY + dt.timedelta(days=365)}"
           f"&sort=Date&maxResults=100&fields=Venue,WebLinks&category=Unspecified")
    res = []
    for cat in ("Concert", "Convention", "Club", "Festival"):
        data = vocadb.get(url.replace("Unspecified", cat)) or {}
        bump("vocadb_calls")
        for e in data.get("items", []):
            v = e.get("venue") or {}
            addr = v.get("address") or {}
            cc = (v.get("addressCountryCode") or "").upper()
            res.append({
                "watch": None, "name": e.get("name"), "date": (e.get("date") or "")[:10],
                "dateEnd": (e.get("endDate") or "")[:10] or None, "city": e.get("venueName") or v.get("name"),
                "cc": "UK" if cc == "GB" else cc, "category": cat,
                "url": next((w.get("url") for w in e.get("webLinks", [])), f"https://vocadb.net/E/{e['id']}"),
                "source": "vocadb",
            })
    return res


# ---------- porównanie z feedem ----------

def load_feed():
    ev = json.loads((ROOT / "events.json").read_text()).get("events", [])
    songs = json.loads((ROOT / "music.json").read_text()).get("songs", [])
    return ev, songs


def known_song(c: dict, songs: list[dict]) -> bool:
    t = norm(re.sub(r"\s*-\s*(Single|EP)$", "", c["title"] or ""))
    return any(t and (t in norm(s.get("title")) or norm(s.get("title")) in t) and
               (matches(s.get("artist", ""), [c["artist"] or ""]) or matches(c["artist"] or "", [s.get("artist", "")]))
               for s in songs)


def known_event(c: dict, events: list[dict]) -> bool:
    who = [c.get("watch") or "", c.get("name") or ""]
    for e in events:
        if not (matches(e.get("artist", ""), terms_for(who[0]) or [who[1]]) or norm(e.get("artist", "")) in norm(who[1])):
            continue
        dates = {e.get("dateStart"), e.get("dateEnd")} | {s.get("date") for s in e.get("stops", [])}
        cities = {norm(s.get("city", "")) for s in e.get("stops", [])}
        if c["date"] in dates or (c.get("city") and norm(c["city"]) in cities):
            return True
        if e.get("dateStart") and e.get("dateEnd") and e["dateStart"] <= c["date"] <= e["dateEnd"]:
            return True
    return False


def dedupe(items: list[dict], key) -> list[dict]:
    seen, out = {}, []
    for it in items:
        k = key(it)
        if k in seen:
            src = seen[k]
            if it["source"] not in src["source"]:
                src["source"] += "+" + it["source"]
            continue
        seen[k] = it
        out.append(it)
    return out


def run_pool(label: str, entries: list[str], fn) -> list[dict]:
    """Każde źródło ma własny wątek, więc limity hostów nie blokują się nawzajem."""
    res: list[dict] = []

    def worker():
        for e in entries:
            r = safe(f"{label} {e}", fn, e, terms_for(e))
            if r:
                with lock:
                    res.extend(r)
    t = threading.Thread(target=worker, name=label)
    t.start()
    return t, res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="music,concerts,japan")
    args = ap.parse_args()
    only = set(args.only.split(","))
    watch = json.loads((ROOT / "watch.json").read_text())
    artists = [a for a in watch["artists"] if "(CV:" not in a]
    if args.limit:
        artists = artists[: args.limit]
    ids = json.loads(IDS.read_text()) if IDS.exists() else {}
    events, songs = load_feed()
    OUT.mkdir(exist_ok=True)
    started = time.time()

    threads = []
    if "music" in only:
        threads.append(("itunes",) + run_pool("itunes", artists, itunes_releases))
        threads.append(("mb_music",) + run_pool("mb", artists, mb_releases))
        threads.append(("vocadb",) + run_pool("vocadb", artists, lambda e, t: vocadb_songs(e, t, ids)))
    if "concerts" in only or "japan" in only:
        def sk_fn(e, t):
            sk = mb_songkick(e, t, ids)
            return songkick_events(e, sk) if sk else []
        # MusicBrainz jest wspólny z muzyką, więc Songkick idzie po muzyce w tym samym limicie.
        threads.append(("songkick",) + run_pool("songkick", artists, sk_fn))
    if "japan" in only:
        threads.append(("eventernote",) + run_pool("eventernote", artists[:200], eventernote_events))
    for _, t, _ in threads:
        t.join()
    got = {name: res for name, _, res in threads}

    summary = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "artists": len(artists), "seconds": int(time.time() - started)}

    if "music" in only:
        music = got["itunes"] + got["mb_music"] + got["vocadb"]
        music = dedupe(music, lambda m: (norm(m["artist"])[:12], norm(re.sub(r"\s*-\s*(Single|EP)$", "", m["title"] or ""))))
        fresh = [m for m in music if not known_song(m, songs)]
        fresh.sort(key=lambda m: m["released"], reverse=True)
        write("music", fresh, f"Premiery {MUSIC_FROM}..{MUSIC_TO} artystów z watch.json, których nie ma w music.json")
        summary["music"] = {"found": len(music), "new": len(fresh)}
    if "concerts" in only or "japan" in only:
        sk = got.get("songkick", [])
        sk = dedupe(sk, lambda e: (norm(e["watch"]), e["date"], norm(e.get("city") or "")))
        eu = [e for e in sk if e["cc"] != "JP"]
        jp = [e for e in sk if e["cc"] == "JP"] + got.get("eventernote", [])
        voc = safe("vocadb events", vocadb_events) or []
        voc_eu = [e for e in voc if e["cc"] in EUROPE]
        if "concerts" in only:
            fresh = [e for e in eu + voc_eu if not known_event(e, events)]
            fresh.sort(key=lambda e: e["date"])
            write("concerts", fresh, "Koncerty w Europie (Songkick, VocaDB), których nie ma w events.json")
            summary["concerts"] = {"found": len(eu) + len(voc_eu), "new": len(fresh)}
        if "japan" in only:
            jp = dedupe(jp, lambda e: (norm(e["name"])[:30], e["date"]))
            fresh = [e for e in jp if not known_event(e, events)]
            fresh.sort(key=lambda e: e["date"])
            write("japan", fresh, "Lajwy w Japonii (Songkick, Eventernote), których nie ma w events.json")
            summary["japan"] = {"found": len(jp), "new": len(fresh)}
    summary["calls"] = stats
    summary["errors"] = errors
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    IDS.write_text(json.dumps(ids, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def write(name: str, items: list[dict], about: str) -> None:
    doc = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "about": about,
           "count": len(items), "items": items}
    (OUT / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    for it in items[:15]:
        print(name, "|", json.dumps(it, ensure_ascii=False)[:220])


if __name__ == "__main__":
    sys.exit(main())
