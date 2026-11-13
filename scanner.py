"""WebScout scanner v3 - trending app-style websites across all app categories
whose mobile app is not found. Free public sources only. No API keys, no AI APIs."""
import json, os, re, time, datetime
import urllib.error, urllib.parse, urllib.request
from html import unescape

DATA = "data.json"
DAILY_TARGET = 20
WINDOW_DAYS = 45
MIN_POINTS = 3
MAX_CHECK = 250
UA = {"User-Agent": "Mozilla/5.0 (compatible; WebScout/3.0; personal trend scanner)"}
NO_APP = "No official iOS app found - needs verification"
NO_ANDROID = "No Play Store link found on website - needs verification"

# One group of searches per app-store style category
QUERIES = [
    "photo app", "camera app", "video downloader", "screen recorder", "subtitle generator",
    "AI voice", "text to speech", "audio editor", "karaoke", "radio", "playlist",
    "AI assistant", "AI writing", "AI photo", "AI headshot", "background remover",
    "sleep app", "diet tracker", "mental health", "running app", "yoga",
    "savings app", "stock tracker", "crypto wallet", "receipt scanner", "bill splitter",
    "kids learning", "typing practice", "math solver", "dictionary", "reading app",
    "coffee", "cooking timer", "grocery list", "nutrition",
    "flight tracker", "map app", "packing list", "city guide",
    "dating", "group chat", "event planner", "social media scheduler",
    "wallpaper", "icon pack", "color palette", "font", "sketch app",
    "pomodoro", "time tracker", "kanban", "mind map", "email app", "bookmark manager",
    "weather", "unit converter", "password manager", "translator", "barcode scanner",
]

CATS = [
    ("Music & Audio", r"music|song|audio|voice|podcast|sound|\bbeat"),
    ("Photo & Video", r"photo|video|image|camera|animation|\bgif\b|\bfilm"),
    ("Design & 3D", r"\b3d\b|design|logo|illustrat|avatar|sketch|draw|\bicons?\b|font|mockup"),
    ("Health & Fitness", r"fitness|workout|health|meditat|sleep|yoga|diet|nutrition|mental|therapy|running"),
    ("Finance", r"budget|expense|invoice|finance|money|invest|crypto|banking|\btax|payment"),
    ("Education", r"\blearn|study|flashcard|language|course|tutor|quiz|education|\bmath|school"),
    ("Food & Drink", r"recipe|meal|cooking|\bfood|restaurant|grocery|coffee"),
    ("Travel", r"travel|\btrip|flight|hotel|itinerary|navigation"),
    ("Social & Chat", r"social|\bchat|messag|community|dating|friends"),
    ("Productivity", r"\bnotes?\b|todo|to-do|\btasks?\b|calendar|planner|productiv|organi[sz]|schedul|reminder|habit|journal|focus|\bpdf|document|writing|resume"),
    ("Utilities", r"convert|calculator|scanner|qr code|utility|translate|weather|compress"),
]

SKIP = set("""github.com gitlab.com youtube.com youtu.be twitter.com x.com medium.com reddit.com
wikipedia.org nytimes.com bbc.com bbc.co.uk theverge.com arstechnica.com substack.com google.com
apple.com microsoft.com amazon.com facebook.com instagram.com linkedin.com arxiv.org
news.ycombinator.com producthunt.com lobste.rs wired.com bloomberg.com reuters.com
theguardian.com techcrunch.com cnn.com forbes.com wsj.com ft.com openai.com anthropic.com
mozilla.org apache.org python.org stackoverflow.com notion.so figma.com huggingface.co
replicate.com kaggle.com nvidia.com meta.com deepmind.google spotify.com netflix.com
duolingo.com canva.com tiktok.com whatsapp.com telegram.org discord.com""".split())

# Not an app-style product: developer tools, libraries, infrastructure
DEV_RE = re.compile(
    r"\b(api|sdk|library|libraries|framework|open[- ]source|cli|compiler|database|kubernetes|devops|"
    r"linux|rust|python|javascript|typescript|npm|programming|developers?|self-hosted|github|llm|"
    r"benchmark|repository|terminal|kernel|server|protocol|runtime|\bos\b)\b", re.I)
GAME_RE = re.compile(r"\bgames?\b|gaming|gamer|puzzle|multiplayer|arcade|chess|trivia|wordle|minecraft|roguelike|esports", re.I)
# Not a product: news / essay style post titles
BLOG_RE = re.compile(
    r"^(how|why|what|when|who|i |we |my |the )|\?$|lessons|essay|opinion|interview|study finds|paper|"
    r"research|announc|raises|funding|acquir|layoff|lawsuit|court|election|\bban\b|outage|breach|vulnerab",
    re.I)
BLOG_PATH_RE = re.compile(r"/(blog|posts?|news|articles?|p|story|stories|20\d\d)/", re.I)


def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def root_domain(url):
    host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    host = re.sub(r"^www\.", "", host)
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def brand(domain):
    return domain.split(".")[0]


def classify(text):
    for cat, rx in CATS:
        if re.search(rx, text, re.I):
            return cat
    return None


# ---------------- Sources (free, public) ----------------
def hn_hits(params):
    url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(params)
    return json.loads(get(url)).get("hits", [])


def to_item(h, label):
    return dict(url=h["url"], title=h.get("title") or "", source=label,
                score=h.get("points", 0),
                signal=f"{h.get('points', 0)} points, {h.get('num_comments', 0)} comments")


def src_hn_keywords():
    since = int(time.time()) - WINDOW_DAYS * 86400
    out, failed = [], 0
    for q in QUERIES:
        try:
            hits = hn_hits({"query": q, "tags": "story", "hitsPerPage": 30,
                            "numericFilters": f"points>={MIN_POINTS},created_at_i>{since}"})
            out += [to_item(h, "Hacker News search") for h in hits if h.get("url")]
        except Exception:
            failed += 1
        time.sleep(0.3)
    if failed == len(QUERIES):
        raise RuntimeError("all queries failed")
    return out


def src_hn_show():
    since = int(time.time()) - WINDOW_DAYS * 86400
    out = []
    for page in (0, 1, 2, 3):
        hits = hn_hits({"tags": "show_hn", "hitsPerPage": 100, "page": page,
                        "numericFilters": f"points>={MIN_POINTS},created_at_i>{since}"})
        out += [to_item(h, "Hacker News (Show HN)") for h in hits if h.get("url")]
    return out


def src_lobsters():
    out = []
    for url in ("https://lobste.rs/hottest.json", "https://lobste.rs/hottest.json?page=2",
                "https://lobste.rs/newest.json", "https://lobste.rs/newest.json?page=2"):
        try:
            for it in json.loads(get(url)):
                if it.get("url"):
                    out.append(dict(url=it["url"], title=it.get("title") or "",
                                    source="Lobsters", score=it.get("score", 0),
                                    signal=f"{it.get('score', 0)} points"))
        except Exception:
            pass
    return out


SOURCES = [src_hn_keywords, src_hn_show, src_lobsters]


# ---------------- Checks ----------------
def homepage(domain):
    """Returns (is_alive, html)."""
    for url in (f"https://{domain}", f"https://www.{domain}"):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=12) as r:
                return True, r.read(400000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429):
                return True, ""
        except Exception:
            pass
    return False, ""


def store_links(html):
    ios = bool(re.search(r"apps\.apple\.com|itunes\.apple\.com/[^\"' ]*app", html, re.I))
    android = bool(re.search(r"play\.google\.com/store/apps", html, re.I))
    return ios, android


def meta_text(html):
    parts = []
    t = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if t:
        parts.append(t.group(1))
    for m in re.finditer(
            r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\']([^"\']*)',
            html, re.I):
        parts.append(m.group(1))
    return unescape(re.sub(r"\s+", " ", " ".join(parts)))


def page_name(html, domain):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        t = unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        t = re.split(r"\s*[|–—]\s*|\s+-\s+|:\s", t)[0].strip()
        if 2 <= len(t) <= 30:
            return t
    return brand(domain).capitalize()


def ios_status(domain, name):
    b = brand(domain).lower()
    terms = []
    for t in (b, (name or "").lower()):
        if t and t not in terms:
            terms.append(t)
    try:
        for term in terms:
            q = urllib.parse.urlencode({"term": term, "entity": "software", "limit": 15})
            res = json.loads(get("https://itunes.apple.com/search?" + q)).get("results", [])
            for r in res:
                seller = ((r.get("sellerUrl") or "") + " " + (r.get("artistViewUrl") or "")).lower()
                if domain in seller:
                    return "iOS app found"
                track = r.get("trackName", "").lower().replace(" ", "")
                maker = r.get("sellerName", "").lower().replace(" ", "")
                if len(b) >= 4 and (b in track or b in maker):
                    return "iOS app found"
            time.sleep(2)
        return NO_APP
    except Exception:
        return "Could not check - needs verification"


def stage_a(c):
    """Homepage check: alive, no store links, app-style, has a category. Cached on c."""
    if "pre" in c:
        return c["pre"]
    alive, html = homepage(c["domain"])
    pre = None
    if alive:
        ios_l, and_l = store_links(html)
        text = " ".join([c["title"], meta_text(html), c["domain"]])
        if not (ios_l or and_l) and not DEV_RE.search(text) and not GAME_RE.search(text):
            cat = classify(text)
            if cat:
                pre = (cat, page_name(html, c["domain"]))
    c["pre"] = pre
    return pre


# ---------------- Main ----------------
def main():
    db = json.load(open(DATA)) if os.path.exists(DATA) else {}
    db.setdefault("sites", [])
    db.setdefault("history", {})
    today = datetime.date.today().isoformat()
    need = DAILY_TARGET - db["history"].get(today, 0)
    if need <= 0:
        print("Today's target already reached.")
        return

    report, raw = [], []
    for fn in SOURCES:
        try:
            got = fn()
            raw += got
            report.append(f"{fn.__name__}: {len(got)} items")
        except Exception as e:
            report.append(f"{fn.__name__}: FAILED ({e})")

    # prefilter + one entry per domain (highest score)
    seen = {s["domain"] for s in db["sites"]}
    best = {}
    for c in raw:
        d = root_domain(c["url"])
        path = urllib.parse.urlparse(c["url"]).path
        is_show = c["source"].startswith("Hacker News (Show")
        if not d or d in SKIP or d in seen:
            continue
        if BLOG_PATH_RE.search(path) or path.strip("/").count("/") >= 1:
            continue
        if not is_show and BLOG_RE.search(c["title"].strip()):
            continue
        c["domain"] = d
        if d not in best or c["score"] > best[d]["score"]:
            best[d] = c
    pool = sorted(best.values(), key=lambda c: c["score"], reverse=True)
    report.append(f"candidates after filtering: {len(pool)}")

    found, cats, checked = [], set(), 0
    for pass_no in (1, 2):  # pass 1: one per category, pass 2: fill remaining
        for c in pool:
            if len(found) >= need:
                break
            if c.get("rejected") or c.get("taken"):
                continue
            if "pre" not in c:
                if checked >= MAX_CHECK:
                    continue
                checked += 1
            pre = stage_a(c)
            if not pre:
                c["rejected"] = True
                continue
            cat, name = pre
            if pass_no == 1 and cat in cats:
                continue
            status = ios_status(c["domain"], name)
            if status != NO_APP:
                c["rejected"] = True
                continue
            c["taken"] = True
            cats.add(cat)
            found.append(dict(name=name, url=f"https://{c['domain']}", domain=c["domain"],
                              category=cat, source=c["source"], signal=c["signal"],
                              found_date=today, ios_status=status, android_status=NO_ANDROID))
            time.sleep(2)

    db["sites"] = found + db["sites"]
    db["history"][today] = db["history"].get(today, 0) + len(found)
    db["updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    db["sources"] = report
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    print(f"Found {len(found)} new site(s) (needed {need}), homepages checked {checked}")
    print("\n".join(report))

    topic = os.environ.get("NTFY_TOPIC")
    if topic and found:
        body = "\n".join(f"{s['name']} ({s['category']}) - {s['url']}" for s in found)
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
            headers={"Title": f"WebScout: {len(found)} new trending websites"})
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print("ntfy failed:", e)


if __name__ == "__main__":
    main()
