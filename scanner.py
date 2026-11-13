"""WebScout scanner - free public sources only, no API keys, no AI."""
import json, os, re, time, datetime
import urllib.error, urllib.parse, urllib.request

DATA = "data.json"
DAILY_TARGET = 3
UA = {"User-Agent": "WebScout/1.0 (personal trend scanner)"}
NO_APP = "No official iOS app found - needs verification"

# Big sites / aggregators: never useful as leads
SKIP = set("""github.com gitlab.com youtube.com youtu.be twitter.com x.com medium.com reddit.com
wikipedia.org nytimes.com bbc.com bbc.co.uk theverge.com arstechnica.com substack.com google.com
apple.com microsoft.com amazon.com facebook.com instagram.com linkedin.com arxiv.org
news.ycombinator.com producthunt.com lobste.rs wired.com bloomberg.com reuters.com
theguardian.com techcrunch.com cnn.com forbes.com wsj.com ft.com openai.com anthropic.com
mozilla.org apache.org python.org stackoverflow.com notion.so figma.com""".split())


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


def clean_name(title, domain, is_show):
    if is_show and title:
        t = re.sub(r"^(show|launch) hn:\s*", "", title, flags=re.I)
        t = re.split(r"\s[–—-]\s|:\s|\s\|\s", t)[0].strip()
        if 2 <= len(t) <= 40:
            return t
    return brand(domain).capitalize()


# ---------------- Sources (free, public) ----------------
def src_hn(tags, label, min_points):
    since = int(time.time()) - 3 * 86400
    q = urllib.parse.urlencode({
        "tags": tags,
        "numericFilters": f"points>={min_points},created_at_i>{since}",
        "hitsPerPage": 50,
    })
    out = []
    for h in json.loads(get("https://hn.algolia.com/api/v1/search?" + q)).get("hits", []):
        if h.get("url"):
            out.append(dict(
                url=h["url"], title=h.get("title"), show=(tags == "show_hn"),
                source=label, score=h.get("points", 0),
                signal=f"{h.get('points', 0)} points, {h.get('num_comments', 0)} comments"))
    return out


def src_hn_show():
    return src_hn("show_hn", "Hacker News (Show HN)", 20)


def src_hn_front():
    return src_hn("front_page", "Hacker News (front page)", 50)


def src_lobsters():
    out = []
    for it in json.loads(get("https://lobste.rs/hottest.json"))[:40]:
        if it.get("url"):
            out.append(dict(url=it["url"], title=it.get("title"), show=False,
                            source="Lobsters (hottest)", score=it.get("score", 0),
                            signal=f"{it.get('score', 0)} points"))
    return out


SOURCES = [src_hn_show, src_hn_front, src_lobsters]


# ---------------- Checks ----------------
def alive(url):
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12)
        return True
    except urllib.error.HTTPError as e:
        return e.code in (401, 403, 429)  # site exists but blocks bots
    except Exception:
        return False


def ios_status(domain, name):
    """Search the free iTunes Search API. Returns 'iOS app found', NO_APP, or an error text."""
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
        seen.add(d)
        if not alive(f"https://{d}"):
            continue
        checked += 1
        name = clean_name(c["title"], d, c["show"])
        status = ios_status(d, name)
        if status != NO_APP:
            continue  # app found or check failed: not a qualifying lead
        found.append(dict(name=name, url=f"https://{d}", domain=d, source=c["source"],
                          signal=c["signal"], found_date=today, ios_status=status))
        time.sleep(2)

    db["sites"] = found + db["sites"]
    db["history"][today] = db["history"].get(today, 0) + len(found)
    db["updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    db["sources"] = report
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)
    print(f"Found {len(found)} new site(s) (target {need})")
    print("\n".join(report))

    topic = os.environ.get("NTFY_TOPIC")
    if topic and found:
        body = "\n".join(f"{s['name']} - {s['url']}" for s in found)
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
            headers={"Title": f"WebScout: {len(found)} new trending websites"})
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print("ntfy failed:", e)


if __name__ == "__main__":
    main()
