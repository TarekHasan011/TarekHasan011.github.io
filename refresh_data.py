"""
Refresh the saved data the website reads when it is hosted as static files
(for example on GitHub Pages, where server.py does not run).

    python refresh_data.py

Updates, in site/data/:
  scholar-snapshot.json   citations, h-index, citations per year, publication list
  journals-snapshot.json  journal metrics (OpenAlex; Scopus too if ELSEVIER_API_KEY is set)
  abstracts.json          abstracts for any publication that does not have one yet

A source that fails (for example Google Scholar asking for a CAPTCHA) leaves its
previous file untouched, so the site never loses data. The GitHub Action in
.github/workflows/pages.yml runs this once a day.
"""

import json
import sys

import server

DATA = server.DATA


def read(name):
    path = DATA / f"{name}-snapshot.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save(name, payload):
    path = DATA / f"{name}-snapshot.json"
    payload = {**payload, "fetched_at": server.now_iso()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[ok] saved {path.name}")


def refresh_scholar():
    old = read("scholar")
    try:
        new = server.fetch_scholar(server.CFG["scholar_user"])
    except Exception as e:
        print(f"[warn] Google Scholar not refreshed, keeping saved data: {e}")
        return old
    # Guard against a partial or blocked page wiping out good data.
    old_pubs = len((old or {}).get("publications", []))
    if not new["publications"] or new["metrics"]["citations"] == 0 or len(new["publications"]) < old_pubs * 0.5:
        print("[warn] Google Scholar returned incomplete data, keeping saved data.")
        return old
    save("scholar", new)
    print(f"       {new['metrics']['citations']} citations, h-index {new['metrics']['h_index']}, "
          f"{len(new['publications'])} publications")
    return new


def refresh_journals():
    old = read("journals") or {}
    old_by_key = {j["key"]: j for j in old.get("journals", [])}
    try:
        new = server.fetch_journals(server.CFG)
    except Exception as e:
        print(f"[warn] Journal metrics not refreshed, keeping saved data: {e}")
        return
    # If one journal's lookup failed, keep its previous values instead of blanking them.
    for j in new["journals"]:
        prev = old_by_key.get(j["key"], {})
        for field in ("openalex", "scopus"):
            if j.get(field) is None and prev.get(field) is not None:
                j[field] = prev[field]
    save("journals", new)


def main():
    scholar = refresh_scholar()
    refresh_journals()
    if scholar:
        server.update_abstracts(scholar.get("publications", []))
    return 0


if __name__ == "__main__":
    sys.exit(main())
