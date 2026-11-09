"""
sample_2wiki.py -- builds a reproducible, stratified 100-question sample of
2WikiMultihopQA (25 per type: comparison, inference, compositional,
bridge_comparison) for the pilot's coverage-annotation pass (C2/C3).

Data source: HuggingFace repackaging "framolfese/2WikiMultihopQA" (Apache 2.0,
carried over from the original https://github.com/Alab-NII/2wikimultihop, Ho et al.,
COLING 2020). Verified directly:
  - License: Apache 2.0 (confirmed on the HF dataset card and the upstream GitHub repo).
  - Validation split size: 12,576 rows (confirmed via the HF datasets-server /size API).
  - Type field values: confirmed present as "type" with the four expected categories by
    probing the datasets-server /rows API directly (see VERIFICATION.md).

This script uses ONLY the public, unauthenticated datasets-server REST API
(https://datasets-server.huggingface.co) via urllib -- no `datasets`/`huggingface_hub`
package required, no API key required.

Contamination note (see README/VERIFICATION.md): 2WikiMultihopQA predates most current
small open models' training cutoffs by several years and is a widely-used, widely-mirrored
benchmark; treat any absolute accuracy number from a model that may have memorized parts
of it with real suspicion, especially for Llama/Qwen-family models explicitly reporting
multi-hop-QA numbers in their technical reports. This is a known, unresolved risk, not a
solved one -- the pilot cannot rule out contamination, it can only flag it.

Usage:
    python sample_2wiki.py                  # writes sample_2wiki.csv + sample_2wiki.jsonl
    python sample_2wiki.py --per-type 25 --seed 42 --pages 60

If your network cannot reach datasets-server.huggingface.co, this script will tell you
exactly which URLs it tried; fetch them manually (they are plain HTTPS GET, no auth) and
place the concatenated row JSON under data/2wiki_rows_raw.jsonl, one row-JSON per line,
then re-run with --from-cache.
"""

import argparse
import csv
import json
import os
import random
import sys
import urllib.request
import urllib.error

DATASET = "framolfese/2WikiMultihopQA"
SPLIT = "validation"
BASE_URL = "https://datasets-server.huggingface.co/rows"
PAGE_SIZE = 100
EXPECTED_TYPES = {"comparison", "inference", "compositional", "bridge_comparison"}

RAW_CACHE = os.path.join("data", "2wiki_rows_raw.jsonl")


def fetch_page(offset: int, length: int = PAGE_SIZE):
    url = f"{BASE_URL}?dataset={DATASET}&config=default&split={SPLIT}&offset={offset}&length={length}"
    req = urllib.request.Request(url, headers={"User-Agent": "pilot-kit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def collect_rows(pages: int, cache_path: str):
    rows = []
    os.makedirs("data", exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as cache_f:
        for i in range(pages):
            offset = i * PAGE_SIZE
            try:
                data = fetch_page(offset)
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"WARNING: failed to fetch offset={offset}: {e}. Stopping early "
                      f"with {len(rows)} rows collected so far.", file=sys.stderr)
                break
            page_rows = [r["row"] for r in data.get("rows", [])]
            if not page_rows:
                break
            for r in page_rows:
                cache_f.write(json.dumps(r) + "\n")
            rows.extend(page_rows)
            print(f"fetched offset={offset}: {len(page_rows)} rows "
                  f"(total so far: {len(rows)})")
    return rows


def load_from_cache(cache_path: str):
    rows = []
    with open(cache_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def context_to_docs(context: dict):
    """context: {'title': [...], 'sentences': [[...], [...], ...]} -> {doc_id: full_text}."""
    titles = context.get("title", [])
    sentence_lists = context.get("sentences", [])
    docs = {}
    for i, (title, sentences) in enumerate(zip(titles, sentence_lists)):
        doc_id = f"p{i}"
        docs[doc_id] = {"title": title, "text": " ".join(sentences)}
    return docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pages", type=int, default=60, help="API pages (100 rows each) to scan "
                     "before stratified sampling; 60 pages = 6000 rows, generous margin over "
                     "the ~3144-per-type expected density in a 12576-row validation split")
    ap.add_argument("--from-cache", action="store_true", help="skip network, reuse data/2wiki_rows_raw.jsonl")
    ap.add_argument("--csv-out", default="sample_2wiki.csv")
    ap.add_argument("--jsonl-out", default="sample_2wiki.jsonl")
    args = ap.parse_args()

    if args.from_cache:
        if not os.path.exists(RAW_CACHE):
            print(f"ERROR: {RAW_CACHE} not found and --from-cache given.", file=sys.stderr)
            sys.exit(1)
        rows = load_from_cache(RAW_CACHE)
    else:
        rows = collect_rows(args.pages, RAW_CACHE)

    if not rows:
        print("ERROR: collected zero rows. See warnings above. You can fetch pages manually:\n"
              f"  curl '{BASE_URL}?dataset={DATASET}&config=default&split={SPLIT}&offset=0&length=100'\n"
              "and increment offset by 100 each call; save each page's .rows[].row entries, one "
              f"JSON object per line, to {RAW_CACHE}, then re-run with --from-cache.",
              file=sys.stderr)
        sys.exit(1)

    by_type = {t: [] for t in EXPECTED_TYPES}
    unknown_types = set()
    for r in rows:
        t = r.get("type")
        if t in by_type:
            by_type[t].append(r)
        else:
            unknown_types.add(t)

    if unknown_types:
        print(f"NOTE: encountered unexpected type value(s) {unknown_types}; "
              "verify EXPECTED_TYPES against the live schema before trusting the stratification.",
              file=sys.stderr)

    random.seed(args.seed)
    sampled = []
    shortfalls = {}
    for t in sorted(EXPECTED_TYPES):
        pool = by_type[t]
        if len(pool) < args.per_type:
            shortfalls[t] = (len(pool), args.per_type)
        k = min(len(pool), args.per_type)
        sampled.extend(random.sample(pool, k))

    if shortfalls:
        print("WARNING: not enough rows scanned to reach --per-type for some categories "
              "(increase --pages):", file=sys.stderr)
        for t, (have, want) in shortfalls.items():
            print(f"  {t}: have {have}, want {want}", file=sys.stderr)

    # write CSV (human-annotation friendly)
    with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "type", "question", "answer", "evidences",
                    "supporting_facts_titles", "context_preview"])
        for r in sampled:
            docs = context_to_docs(r.get("context", {}))
            preview = " || ".join(f"[{d}:{v['title']}] {v['text'][:200]}" for d, v in list(docs.items())[:4])
            w.writerow([
                r.get("id"), r.get("type"), r.get("question"), r.get("answer"),
                json.dumps(r.get("evidences")), json.dumps(r.get("supporting_facts", {}).get("title")),
                preview,
            ])

    # write JSONL (full structured data for the harness)
    with open(args.jsonl_out, "w", encoding="utf-8") as f:
        for r in sampled:
            docs = context_to_docs(r.get("context", {}))
            rec = {
                "id": r.get("id"), "type": r.get("type"), "question": r.get("question"),
                "answer": r.get("answer"), "evidences": r.get("evidences"),
                "supporting_facts": r.get("supporting_facts"), "docs": docs,
            }
            f.write(json.dumps(rec) + "\n")

    print(f"\nWrote {len(sampled)} questions to {args.csv_out} and {args.jsonl_out}.")
    print("Per-type counts:", {t: sum(1 for r in sampled if r.get("type") == t) for t in sorted(EXPECTED_TYPES)})


if __name__ == "__main__":
    main()
