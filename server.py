"""
Local server for the website.

  python server.py            -> http://localhost:8080

Serves the static site from ./site and two live JSON endpoints:

  /api/scholar   Citation metrics, citations per year and the full publication
                 list, read from the public Google Scholar profile.
  /api/journals  Journal metrics:
                   * OpenAlex 2-year mean citedness (free, no key; computed the
                     same way as an impact factor)
                   * Scopus CiteScore, SJR and quartile, if an Elsevier API key
                     is set (free key: https://dev.elsevier.com)
                   * JCR Impact Factor as recorded in the CV (Clarivate has no
                     public API, so this one cannot be live)

Every successful fetch is also written to site/data/*-snapshot.json, so the page
still shows the latest numbers if a source is down or the site is hosted as
plain static files.

Only the Python standard library is used.
"""

import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
DATA = SITE / "data"
CONFIG_FILE = ROOT / "config.json"

DEFAULT_CONFIG = {
    "port": 8080,
    "scholar_user": "SFfUSOIAAAAJ",
    # Google Scholar blocks clients that request too often, which would stop the
    # live numbers entirely. A page refresh inside this window reuses the last
    # result instead of asking Scholar again.
    "scholar_min_interval_seconds": 600,
    "journals_min_interval_seconds": 600,
    # Free key from https://dev.elsevier.com (enables live Scopus quartile/CiteScore).
    # Can also be given as the ELSEVIER_API_KEY environment variable.
    "elsevier_api_key": "",
    # Journals to look up. "match" is a case-insensitive substring of the venue
    # text on Google Scholar. jcr_* values come from the CV (not available live).
    "journals": [
        {"key": "patcog", "name": "Pattern Recognition", "match": "pattern recognition",
         "issn": "0031-3203", "jcr_if": 9.1, "jcr_quartile": "Q1"},
        {"key": "array", "name": "Array", "match": "array",
         "issn": "2590-0056", "jcr_if": 5.3, "jcr_quartile": "Q1"},
        {"key": "futureinternet", "name": "Future Internet", "match": "future internet",
         "issn": "1999-5903", "jcr_if": 4.6, "jcr_quartile": "Q1"},
        {"key": "cis", "name": "Complex & Intelligent Systems", "match": "complex & intelligent systems",
         "issn": "2199-4536", "jcr_if": 4.5, "jcr_quartile": "Q1"},
    ],
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_FILE.exists():
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    cfg["elsevier_api_key"] = os.environ.get("ELSEVIER_API_KEY") or cfg.get("elsevier_api_key", "")
    return cfg


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment or "")).replace("\xa0", " ").strip()


# ---------------------------------------------------------------------------
# Google Scholar
# ---------------------------------------------------------------------------
def fetch_scholar(user):
    # robots.txt allows /citations?user=... but not paging with cstart, so the
    # whole list is requested in one page.
    url = f"https://scholar.google.com/citations?user={urllib.parse.quote(user)}&hl=en&pagesize=100&sortby=pubdate"
    page = http_get(url)
    if "gsc_rsb_std" not in page:
        raise RuntimeError("Google Scholar did not return the profile (it may be asking for a CAPTCHA).")

    nums = [int(n) if n.strip().isdigit() else 0 for n in re.findall(r'class="gsc_rsb_std">([^<]*)<', page)]
    since = re.findall(r'<th class="gsc_rsb_sth">([^<]*)</th>', page)
    since_label = next((s for s in since if s.lower().startswith("since")), "")

    years = [int(y) for y in re.findall(r'<span class="gsc_g_t"[^>]*>(\d{4})</span>', page)]
    per_year = {y: 0 for y in years}
    for z, count in re.findall(r'class="gsc_g_a"[^>]*z-index:(\d+)"><span class="gsc_g_al">(\d+)</span>', page):
        idx = len(years) - int(z)  # z-index 1 is the most recent year
        if 0 <= idx < len(years):
            per_year[years[idx]] = int(count)

    pubs = []
    for row in re.findall(r'<tr class="gsc_a_tr">(.*?)</tr>', page, re.S):
        title_m = re.search(r'<a href="([^"]*)" class="gsc_a_at">(.*?)</a>', row, re.S) \
            or re.search(r'class="gsc_a_at"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', row, re.S)
        if not title_m:
            continue
        grays = [text(g) for g in re.findall(r'<div class="gs_gray">(.*?)</div>', row, re.S)]
        cites = re.search(r'class="gsc_a_ac gs_ibl"[^>]*>([^<]*)<', row)
        year = re.search(r'class="gsc_a_h gsc_a_hc gs_ibl">([^<]*)<', row)
        venue = grays[1] if len(grays) > 1 else ""
        venue = re.sub(r",\s*\d{4}$", "", venue).rstrip(" …").strip()
        pubs.append({
            "title": text(title_m.group(2)),
            "authors": grays[0] if grays else "",
            "venue": venue,
            "year": int(year.group(1)) if year and year.group(1).strip().isdigit() else None,
            "citations": int(cites.group(1)) if cites and cites.group(1).strip().isdigit() else 0,
            "scholar_url": "https://scholar.google.com" + html.unescape(title_m.group(1)),
        })

    name = re.search(r'id="gsc_prf_in">([^<]*)<', page)
    return {
        "name": text(name.group(1)) if name else "",
        "profile_url": f"https://scholar.google.com/citations?user={user}&hl=en",
        "metrics": {
            "citations": nums[0] if len(nums) > 0 else 0,
            "citations_recent": nums[1] if len(nums) > 1 else 0,
            "h_index": nums[2] if len(nums) > 2 else 0,
            "h_index_recent": nums[3] if len(nums) > 3 else 0,
            "i10_index": nums[4] if len(nums) > 4 else 0,
            "i10_index_recent": nums[5] if len(nums) > 5 else 0,
            "recent_label": since_label,
        },
        "citations_per_year": [{"year": y, "citations": per_year[y]} for y in years],
        "publications": pubs,
    }


# ---------------------------------------------------------------------------
# Journal metrics
# ---------------------------------------------------------------------------
def fetch_openalex(issn):
    data = json.loads(http_get(f"https://api.openalex.org/sources/issn:{issn}?select=display_name,summary_stats"))
    stats = data.get("summary_stats") or {}
    return {
        "two_year_mean_citedness": round(stats.get("2yr_mean_citedness") or 0, 2),
        "h_index": stats.get("h_index"),
    }


def quartile_from_percentile(p):
    return "Q1" if p >= 75 else "Q2" if p >= 50 else "Q3" if p >= 25 else "Q4"


def fetch_scopus(issn, key):
    url = f"https://api.elsevier.com/content/serial/title/issn/{issn}?view=CITESCORE"
    data = json.loads(http_get(url, headers={"X-ELS-APIKey": key, "Accept": "application/json"}))
    entry = (data.get("serial-metadata-response", {}).get("entry") or [{}])[0]
    info = entry.get("citeScoreYearInfoList") or {}
    result = {
        "citescore": float(info["citeScoreCurrentMetric"]) if info.get("citeScoreCurrentMetric") else None,
        "citescore_year": info.get("citeScoreCurrentMetricYear"),
        "sjr": None, "quartile": None, "best_percentile": None, "best_subject": None,
    }
    sjr = (entry.get("SJRList") or {}).get("SJR") or []
    if sjr:
        result["sjr"] = float(sjr[0].get("$", 0))
    # Quartile = best subject-area percentile of the latest complete CiteScore year.
    best = None
    for year_info in info.get("citeScoreYearInfo", []) or []:
        if year_info.get("@year") != result["citescore_year"]:
            continue
        for csi in year_info.get("citeScoreInformationList", []) or []:
            for ci in csi.get("citeScoreInfo", []) or []:
                for rank in ci.get("citeScoreSubjectRank", []) or []:
                    p = float(rank.get("percentile", 0))
                    if best is None or p > best[0]:
                        best = (p, rank.get("subjectCode"))
    if best:
        result["best_percentile"] = best[0]
        result["best_subject"] = best[1]
        result["quartile"] = quartile_from_percentile(best[0])
    return result


def fetch_journals(cfg):
    out = []
    for j in cfg["journals"]:
        item = {k: j[k] for k in ("key", "name", "match", "issn", "jcr_if", "jcr_quartile")}
        try:
            item["openalex"] = fetch_openalex(j["issn"])
        except Exception as e:  # keep going; one journal failing shouldn't blank the rest
            item["openalex"] = None
            item["openalex_error"] = str(e)
        item["scopus"] = None
        if cfg.get("elsevier_api_key"):
            try:
                item["scopus"] = fetch_scopus(j["issn"], cfg["elsevier_api_key"])
            except Exception as e:
                item["scopus_error"] = str(e)
        out.append(item)
    return {"journals": out, "scopus_enabled": bool(cfg.get("elsevier_api_key"))}


# ---------------------------------------------------------------------------
# Abstracts
# ---------------------------------------------------------------------------
# Google Scholar's profile page has no abstracts, so each publication's abstract
# is looked up once (arXiv, then OpenAlex, then Crossref, then Semantic Scholar)
# and stored in site/data/abstracts.json. Found abstracts are never fetched
# again; papers with none yet are retried after a week. A manual "abstract" in
# curated.json always wins.
ABSTRACTS_FILE = DATA / "abstracts.json"
ABSTRACT_RETRY_SECONDS = 7 * 24 * 3600
_abstract_lock = threading.Lock()


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def same_title(a, b):
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return False
    if a == b or a.startswith(b) or b.startswith(a):
        return True
    wa, wb = set(a.split()), set(b.split())
    return len(wa & wb) / max(len(wa | wb), 1) >= 0.8


def clean_abstract(s):
    s = re.sub(r"<[^>]+>", " ", s or "")          # JATS / HTML tags
    s = html.unescape(s)
    s = re.sub(r"^\s*(abstract|summary)[:.\s]+", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def from_inverted_index(inv):
    if not inv:
        return ""
    words = sorted((pos, w) for w, positions in inv.items() for pos in positions)
    return " ".join(w for _, w in words)


def abstract_from_arxiv(arxiv_id=None, title=None):
    if arxiv_id:
        q = "id_list=" + urllib.parse.quote(arxiv_id)
    else:
        q = "search_query=" + urllib.parse.quote(f'ti:"{title}"') + "&max_results=3"
    feed = http_get("https://export.arxiv.org/api/query?" + q)
    for entry in re.findall(r"<entry>(.*?)</entry>", feed, re.S):
        t = text(re.search(r"<title>(.*?)</title>", entry, re.S).group(1))
        summary = re.search(r"<summary>(.*?)</summary>", entry, re.S)
        if summary and (arxiv_id or same_title(t, title)):
            link = re.search(r"<id>(.*?)</id>", entry).group(1).strip()
            return clean_abstract(summary.group(1)), link
    return None


def abstract_from_openalex(doi=None, title=None):
    sel = "select=title,abstract_inverted_index,doi"
    if doi:
        works = [json.loads(http_get(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi)}?{sel}"))]
    else:
        works = json.loads(http_get(
            "https://api.openalex.org/works?per-page=5&" + sel + "&search=" + urllib.parse.quote(title)))["results"]
    for w in works:
        if (doi or same_title(w.get("title"), title)) and w.get("abstract_inverted_index"):
            return clean_abstract(from_inverted_index(w["abstract_inverted_index"])), w.get("doi")
    return None


def abstract_from_crossref(doi):
    msg = json.loads(http_get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"))["message"]
    if msg.get("abstract"):
        return clean_abstract(msg["abstract"]), f"https://doi.org/{doi}"
    return None


def abstract_from_semantic_scholar(title):
    data = json.loads(http_get(
        "https://api.semanticscholar.org/graph/v1/paper/search/match?fields=title,abstract,url&query="
        + urllib.parse.quote(title)))
    for p in data.get("data", []):
        if p.get("abstract") and same_title(p.get("title"), title):
            return clean_abstract(p["abstract"]), p.get("url")
    return None


def find_abstract(title, url=""):
    arxiv = re.search(r"arxiv\.org/abs/([\w.\-/]+?)(?:v\d+)?$", url or "")
    doi = re.search(r"(10\.\d{4,9}/[^\s?#]+)", url or "")
    doi = doi.group(1) if doi else None
    attempts = []
    if arxiv:
        attempts.append(("arXiv", lambda: abstract_from_arxiv(arxiv_id=arxiv.group(1))))
    if doi:
        attempts += [("OpenAlex", lambda: abstract_from_openalex(doi=doi)),
                     ("Crossref", lambda: abstract_from_crossref(doi))]
    attempts += [("OpenAlex", lambda: abstract_from_openalex(title=title)),
                 ("arXiv", lambda: abstract_from_arxiv(title=title)),
                 ("Semantic Scholar", lambda: abstract_from_semantic_scholar(title))]
    for source, attempt in attempts:
        try:
            found = attempt()
        except Exception as e:
            print(f"[abstracts] {source} failed for '{title[:50]}': {e}")
            found = None
        time.sleep(1)  # be polite to the free APIs
        if found and len(found[0]) > 80:
            return {"abstract": found[0], "source": source, "source_url": found[1] or ""}
    return None


def load_abstracts():
    try:
        return json.loads(ABSTRACTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"_about": "Abstracts looked up automatically by server.py. Keyed by normalised title.", "papers": {}}


def update_abstracts(pubs):
    """Fill in abstracts for any publication that does not have one yet."""
    if not _abstract_lock.acquire(blocking=False):
        return  # a lookup is already running
    try:
        store = load_abstracts()
        papers = store.setdefault("papers", {})
        try:
            curated = json.loads((DATA / "curated.json").read_text(encoding="utf-8"))
        except Exception:
            curated = {}
        changed = False
        for p in pubs:
            key = norm_title(p["title"])
            entry = papers.get(key)
            if entry and (entry.get("abstract") or time.time() - entry.get("checked", 0) < ABSTRACT_RETRY_SECONDS):
                continue
            extra = next((v for k, v in curated.items() if not k.startswith("_") and p["title"].lower().startswith(k)), {})
            found = find_abstract(p["title"], extra.get("url", ""))
            papers[key] = {"title": p["title"], **(found or {}), "checked": int(time.time())}
            print(f"[abstracts] {'found via ' + found['source'] if found else 'none yet'}: {p['title'][:60]}")
            changed = True
            ABSTRACTS_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
        if changed:
            print("[abstracts] saved", ABSTRACTS_FILE)
    finally:
        _abstract_lock.release()


def update_abstracts_in_background(pubs):
    threading.Thread(target=update_abstracts, args=(pubs,), daemon=True).start()


# ---------------------------------------------------------------------------
# Caching: live fetch, rate-limited, with snapshot fallback
# ---------------------------------------------------------------------------
class Source:
    def __init__(self, name, fetch, min_interval):
        self.name, self.fetch, self.min_interval = name, fetch, min_interval
        self.snapshot = DATA / f"{name}-snapshot.json"
        self.lock = threading.Lock()
        self.last_try = 0.0
        self.cached = None

    def get(self):
        with self.lock:
            age = time.time() - self.last_try
            if self.cached and age < self.min_interval:
                return {**self.cached, "status": "cached", "next_live_in_seconds": int(self.min_interval - age)}
            self.last_try = time.time()
            try:
                payload = {**self.fetch(), "fetched_at": now_iso()}
                self.cached = payload
                DATA.mkdir(parents=True, exist_ok=True)
                self.snapshot.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
                return {**payload, "status": "live"}
            except Exception as e:
                print(f"[{self.name}] live fetch failed: {e}")
                fallback = self.cached
                if fallback is None and self.snapshot.exists():
                    fallback = json.loads(self.snapshot.read_text(encoding="utf-8"))
                if fallback is None:
                    raise
                return {**fallback, "status": "snapshot", "error": str(e)}


def fetch_scholar_and_abstracts(user):
    data = fetch_scholar(user)
    update_abstracts_in_background(data["publications"])  # new papers get their abstract looked up
    return data


CFG = load_config()
SOURCES = {
    "/api/scholar": Source("scholar", lambda: fetch_scholar_and_abstracts(CFG["scholar_user"]), CFG["scholar_min_interval_seconds"]),
    "/api/journals": Source("journals", lambda: fetch_journals(CFG), CFG["journals_min_interval_seconds"]),
}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE), **kwargs)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in SOURCES:
            try:
                body, code = json.dumps(SOURCES[path].get(), ensure_ascii=False).encode("utf-8"), 200
            except Exception as e:
                body, code = json.dumps({"error": str(e)}).encode("utf-8"), 502
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        # Always re-check static files so edits show up on refresh.
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", CFG["port"]))
    print(f"Serving {SITE} at http://localhost:{port}")
    print("Scopus quartile:", "live (Elsevier key set)" if CFG["elsevier_api_key"] else "from CV (no Elsevier key)")
    snap = DATA / "scholar-snapshot.json"
    if snap.exists():  # fill any missing abstracts straight away, from the last known list
        update_abstracts_in_background(json.loads(snap.read_text(encoding="utf-8")).get("publications", []))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
