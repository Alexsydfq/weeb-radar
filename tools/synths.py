"""Syntezatory głosu (Vocaloid, UTAU, SynthV, CeVIO, VOICEVOX, ACE…) to instrumenty, nie artyści.

Awex (2026-11-07): w „Nowej muzyce” piosenka z Miku, Teto itd. ma się pojawić tylko wtedy,
gdy jest od twórcy, którego Awex obserwuje. Sam głos syntezatora w kredytach nie wystarcza.
Koncerty (Miku Expo, Magical Mirai) zostają, bo to dotyczy tylko muzyki.

Używają tego tools/scan.py (nie szuka premier „artysty” Miku) i build_feed.py (czyści music.json).
"""
import re
import unicodedata

SYNTHS = [
    # Crypton
    "Hatsune Miku", "初音ミク", "Kagamine Rin", "鏡音リン", "Kagamine Len", "鏡音レン",
    "Kagamine Rin/Len", "鏡音リン・レン", "Megurine Luka", "巡音ルカ", "MEIKO", "KAITO",
    # Internet / AH-Software / inne Vocaloidy
    "GUMI", "Megpoid", "Kamui Gakupo", "神威がくぽ", "IA", "IA AI", "OИE", "v flower", "v4 flower",
    "Otomachi Una", "Una Otomachi", "音街ウナ", "Yuzuki Yukari", "結月ゆかり", "Kizuna Akari", "紲星あかり",
    "Tohoku Kiritan", "東北きりたん", "Tohoku Zunko", "東北ずん子", "Nekomura Iroha", "猫村いろは",
    "SF-A2 miki", "Kaai Yuki", "歌愛ユキ", "Hiyama Kiyoteru", "氷山キヨテル", "CUL", 
    "Kotonoha Akane", "琴葉茜", "Kotonoha Aoi", "琴葉葵", "琴葉茜・葵", "Yuki Kaai",
    # UTAU / SynthV / CeVIO / NEUTRINO
    "Kasane Teto", "重音テト", "Teto", "Namine Ritsu", "波音リツ", "Momone Momo", "桃音モモ", "Yokune Ruko",
    "欲音ルコ", "Adachi Rei", "Rei Adachi", "足立レイ", "KAFU", "可不",  # KAFU (可不, CeVIO) to syntezator; KAF (花譜) to prawdziwa wokalistka i zostaje artystką
    "星界", "裏命",
    "COKO", "狐子", "Koharu Rikka", "小春六花", "Natsuki Karin", "夏色花梨", "Hanakuma Chifuyu", "花隈千冬",
    "Yumeno Yuusho", "夢ノ結唱", "夢ノ結唱 ROSE", "夢ノ結唱 POPY", "夢ノ結唱 HALO", "Yumeno Yuusho ROSE",
    "Yumeno Yuusho POPY", "Chis-A", "知声", "Tsurumaki Maki", "弦巻マキ", "Kyomachi Seika", "京町セイカ",
    "Saki AI", "Solaria", "Koyomi Mirai", "未来小町", "Haruno Sora", "春野ソラ", "Xia Yu Yao",
    "AI Mai", "Ci Fairy", "宮舞モカ", "Minase Kou",
    # VOICEVOX / ずんだもん i spółka
    "Zundamon", "ずんだもん", "Shikoku Metan", "四国めたん", "Kasukabe Tsumugi", "春日部つむぎ",
    # Chiny (Vsinger i inne)
    "Luo Tianyi", "洛天依", "Yuezheng Ling", "乐正绫", "Yanhe", "言和", "Yuezheng Longya", "乐正龙牙",
    "Zhiyu Moke", "徵羽摩柯", "Mo Qingxian", "墨清弦", "Xingchen", "星尘", "Haiyi", "海伊", "Chiyu", "赤羽",
    "Shian", "诗岸", "Cangqiong", "苍穹",
    # Korea
    "SeeU", "ユニ",
]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"[\s\-_.,'’!?*~☆★♡♪:/()\[\]「」『』【】・]+", "", s)


# Dopiski wersji głosu: „重音テトSV”, „初音ミク V4X”, „Hatsune Miku NT”, „GUMI (English)”.
SUFFIX = re.compile(r"(sv|synthv|v\d+x?|nt|ai|english|eng|cn|jp|ver\d*|sweet|dark|soft|solid|power|natural|"
                    r"original|append|vivid|light|whisper|chinese|utau|cevio)*$")
SYNTH_NORM = {norm(s) for s in SYNTHS}
SPLIT = re.compile(r"\s*(?:&|,|、|×|\bx\b|\bfeat\.?|\bft\.?|\bwith\b|\band\b|\bvs\.?|/|\+|\(|\)|（|）|\bcv\b)\s*", re.I)


def is_synth(name: str) -> bool:
    n = norm(name)
    if not n:
        return False
    if n in SYNTH_NORM:
        return True
    for s in SYNTH_NORM:
        if len(s) >= 2 and n.startswith(s) and SUFFIX.fullmatch(n[len(s):]):
            return True
    return False


def is_synth_entry(entry: str) -> bool:
    """Wpis z watch.json, który jest samym syntezatorem (np. „洛天依”, „Kasane Teto”)."""
    parts = [p for p in SPLIT.split(entry) if p.strip()]
    return bool(parts) and all(is_synth(p) for p in parts)


def credits(artist: str) -> list[str]:
    return [p.strip() for p in SPLIT.split(artist or "") if p.strip()]


# Ręczne zapisy oryginalne dla obserwowanych twórców, gdy VocaDB jeszcze ich nie podało
# (scan.py dopisuje nazwy z VocaDB do tools/ids.json jako "names").
ALIASES = {
    "NAKISO": ["なきそ"], "Marasy": ["まらしぃ"], "Sasuke Haraguchi": ["原口沙輔"],
    "Kairiki Bear": ["かいりきベア"], "cosMo@Bousou-P": ["cosMo@暴走P", "cosMo＠暴走P"],
}


def followed_terms(watch_artists: list[str], ids: dict | None = None) -> set[str]:
    """Znormalizowane nazwy obserwowanych twórców (bez syntezatorów), z aliasami z VocaDB."""
    out = set()
    for a in watch_artists:
        if is_synth_entry(a):
            continue
        names = re.split(r"\s+/\s+|\s*\(|\)", a) + ALIASES.get(a, [])
        names += ((ids or {}).get(a) or {}).get("names") or []
        for part in names:
            if len(norm(part)) >= 2 and not is_synth(part):
                out.add(norm(part))
    return out


def synth_only(song: dict, followed: set[str]) -> bool:
    """Prawda, gdy piosenka trafiła tu tylko przez głos syntezatora, a twórca nie jest obserwowany."""
    names = credits(song.get("artist", ""))
    if not any(is_synth(n) for n in names):
        return False
    if any(norm(n) in followed for n in names if not is_synth(n)):
        return False
    # Twórca bywa tylko w tytule: „曲名 (feat. 初音ミク) [DECO*27]” albo „Title / Kanaria”.
    title = norm(song.get("title", ""))
    return not any(len(f) >= 4 and f in title for f in followed)
