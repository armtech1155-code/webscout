"""WebScout scanner v2 - trending AI tool websites (image, video, 3D, music...)
whose mobile app is not found. Free public sources only. No API keys, no AI APIs."""
import json, os, re, time, datetime
import urllib.error, urllib.parse, urllib.request
from html import unescape

DATA = "data.json"
DAILY_TARGET = 3
WINDOW_DAYS = 21
MIN_POINTS = 8
UA = {"User-Agent": "Mozilla/5.0 (compatible; WebScout/2.0; personal trend scanner)"}
NO_APP = "No official iOS app found - needs verification"
NO_ANDROID = "No Play Store link found on website - needs verification"

QUERIES = [
    "text to video", "AI video generator", "image to video", "AI animation",
    "AI image generator", "text to image", "AI art", "AI photo editor",
    "text to 3D", "3D model generator", "AI avatar", "AI design tool",
    "AI music generator", "AI voice",
]

SKIP = set("""github.com gitlab.com youtube.com youtu.be twitter.com x.com medium.com reddit.com
wikipedia.org nytimes.com bbc.com bbc.co.uk theverge.com arstechnica.com substack.com google.com
apple.com microsoft.com amazon.com facebook.com instagram.com linkedin.com arxiv.org
news.ycombinator.com producthunt.com lobste.rs wired.com bloomberg.com reuters.com
theguardian.com techcrunch.com cnn.com forbes.com wsj.com ft.com openai.com anthropic.com
mozilla.org apache.org python.org stackoverflow.com notion.so figma.com huggingface.co
replicate.com kaggle.com paperswithcode.com nvidia.com meta.com x.ai deepmind.google
stability.ai midjourney.com runwayml.com""".split())

AI_RE = re.compile(r"\bai\b|\ba\.i\.|gpt|llm|diffusion|generat|text[- ]to|image[- ]to|neural|sora|flux", re.I)
CATS = [
    ("3D", r"\b3d\b|mesh"),
    ("Video", r"video|animat|motion|film|clip"),
    ("Music/Audio", r"music|song|audio|voice|speech|tts|sound|podcast"),
    ("Image", r"image|photo|picture|\bart\b|logo|illustrat|avatar|portrait|design|sketch|draw|icon"),
]


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
    return "Other AI"


# ---------------- Sources (free, public) ----------------
def hn_hits(params):
    return json.loads(get("https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(params))).get("hits", [])


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
    hits = hn_hits({"tags": "show_hn", "hitsPerPage": 100,
                    "numericFilters": f"points>=5,created_at_i>{since}"})
    return [to_item(h, "Hacker News (Show HN)") for h in hits if h.get("url")]


def src_lobsters():
    out = []
    for it in json.loads(get("https://lobste.rs/t/ai.json"))[:40]:
        if it.get("url"):
            out.append(dict(url=it["url"], title=it.get("title") or "", source="Lobsters (ai tag)",
                            score=it.get("score", 0), signal=f"{it.get('score', 0)} points"))
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

    report, candidates = [], []
    for fn in SOURCES:
        try:
            got = fn()
            candidates += got
            report.append(f"{fn.__name__}: {len(got)} items")
        except Exception as e:
            report.append(f"{fn.__name__}: FAILED ({e})")
    candidates.sort(key=lambda c: c["score"], reverse=True)

    seen = {s["domain"] for s in db["sites"]}
    found, checked = [], 0
    for c in candidates:
        if len(found) >= need or checked >= 40:
            break
        d = root_domain(c["url"])
        if not d or d in SKIP or d in seen:
            continue
        text = c["title"] + " " + d
        if not AI_RE.search(text):
            continue  # not an AI tool
        seen.add(d)
        alive, html = homepage(d)
        if not alive:
            continue
        checked += 1
        ios_link, android_link = store_links(html)
        if ios_link or android_link:
            continue  # website itself links to an app
        name = page_name(html, d)
        status = ios_status(d, name)
        if status != NO_APP:
            continue
        found.append(dict(name=name, url=f"https://{d}", domain=d,
                          category=classify(text), source=c["source"], signal=c["signal"],
                          found_date=today, ios_status=status, android_status=NO_ANDROID))
        time.sleep(2)

    db["sites"] = found + db["sites"]
    db["history"][today] = db["history"].get(today, 0) + len(found)
    db["updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    db["sources"] = report
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    print(f"Found {len(found)} new site(s) (needed {need}), checked {checked}")
    print("\n".join(report))

    topic = os.environ.get("NTFY_TOPIC")
    if topic and found:
        body = "\n".join(f"{s['name']} ({s['category']}) - {s['url']}" for s in found)
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
            headers={"Title": f"WebScout: {len(found)} new AI tool websites"})
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print("ntfy failed:", e)


if __name__ == "__main__":
    main()
