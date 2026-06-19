import requests
import pandas as pd
import time
import sys

# ─── CONFIG ──────────────────────────────────────────────────────────────────

# ACS Applied Materials & Interfaces
#   OpenAlex source page : https://explore.openalex.org/sources/S164001016
#   ISSN (web/electronic): 1944-8252   ISSN (print): 1944-8244
SOURCE_ID   = "S164001016"
ISSN        = "1944-8252"

START_YEAR  = 2012
END_YEAR    = 2026

EMAIL       = "your_email@example.com"   # <-- CHANGE THIS (polite pool = faster)

OUTPUT_FILE = "openalex_all_dataset.csv"

FIELDS = ",".join([
    "id",
    "doi",
    "title",
    "publication_year",
    "abstract_inverted_index",
    "cited_by_count",
    "counts_by_year",
    "authorships",
    "topics",
    "primary_topic",
    "open_access",
    "type",
])

BASE_URL = "https://api.openalex.org/works"
PER_PAGE = 200

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pairs = [(pos, w) for w, positions in inv.items() for pos in positions]
    pairs.sort()
    return " ".join(w for _, w in pairs)


def safe_get(url: str, params: dict, retries: int = 6) -> dict | None:
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=40)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"\n  ⚠ Rate-limited. Sleeping {wait}s …")
                time.sleep(wait)
            else:
                print(f"\n  ✗ HTTP {r.status_code}: {r.text[:300]}")
                return None
        except requests.RequestException as e:
            print(f"\n  ✗ Request error: {e}. Retry {attempt+1}/{retries} …")
            time.sleep(2 ** attempt)
    return None


def parse_authors(authorships: list) -> tuple[str, str]:
    names, institutions = [], []
    for a in authorships:
        names.append(a.get("author", {}).get("display_name", ""))
        for inst in a.get("institutions", []):
            institutions.append(inst.get("display_name", ""))
    return " | ".join(names), " | ".join(dict.fromkeys(institutions))


def parse_topics(topics: list) -> tuple[str, str, str]:
    fields, subfields, topic_names = [], [], []
    for t in topics[:3]:
        fields.append(t.get("field", {}).get("display_name", ""))
        subfields.append(t.get("subfield", {}).get("display_name", ""))
        topic_names.append(t.get("display_name", ""))
    return " | ".join(fields), " | ".join(subfields), " | ".join(topic_names)


def citation_series(counts_by_year: list) -> dict:
    result = {y: 0 for y in range(2012, 2024)}
    for entry in counts_by_year or []:
        yr = entry.get("year")
        if yr and yr in result:
            result[yr] = entry.get("cited_by_count", 0)
    return result

# ─── CONNECTIVITY / SOURCE CHECK ─────────────────────────────────────────────

def verify_source():
    """Confirm the source ID and show expected record count before full run."""
    print("🔍 Verifying source ID against OpenAlex …")
    url = f"https://api.openalex.org/sources/{SOURCE_ID}"
    r = requests.get(url, params={"mailto": EMAIL}, timeout=20)
    if r.status_code == 200:
        src = r.json()
        print(f"  ✓ Source found  : {src.get('display_name')}")
        print(f"    Works count   : {src.get('works_count'):,}")
        print(f"    ISSNs         : {src.get('issn')}")
    else:
        print(f"  ✗ Source lookup failed (HTTP {r.status_code}). Trying ISSN filter …")

    # Quick count check for 2012
    test = safe_get(BASE_URL, {
        "filter":   f"primary_location.source.issn:{ISSN},publication_year:2012",
        "per-page": 1,
        "mailto":   EMAIL,
    })
    if test:
        count = test.get("meta", {}).get("count", 0)
        print(f"  ✓ Test query (year=2012): {count} papers found")
        if count == 0:
            print("  ⚠ 0 results — check ISSN or source ID above before continuing.")
            sys.exit(1)
    else:
        print("  ✗ Test query failed. Check your internet connection.")
        sys.exit(1)

# ─── MAIN EXTRACTION ─────────────────────────────────────────────────────────

def fetch_papers() -> list[dict]:
    records = []

    for year in range(START_YEAR, END_YEAR + 1):
        print(f"\n Fetching year {year} …")
        cursor = "*"
        page_count = 0
        year_count = 0

        while cursor:
            params = {
                # Use ISSN filter — most reliable across OpenAlex versions
                "filter":   f"primary_location.source.issn:{ISSN},publication_year:{year}",
                "select":   FIELDS,
                "per-page": PER_PAGE,
                "cursor":   cursor,
                "mailto":   EMAIL,
            }

            data = safe_get(BASE_URL, params)
            if data is None:
                print(f"\n  ✗ Failed to fetch page {page_count+1}. Stopping year {year}.")
                break

            results = data.get("results", [])
            if not results:
                break

            for work in results:
                cby = citation_series(work.get("counts_by_year", []))
                authors, institutions = parse_authors(work.get("authorships", []))
                fields, subfields, topics_str = parse_topics(work.get("topics", []))

                row = {
                    "openalex_id":      work.get("id", ""),
                    "doi":              work.get("doi", ""),
                    "title":            work.get("title", ""),
                    "publication_year": work.get("publication_year"),
                    "abstract":         reconstruct_abstract(
                                            work.get("abstract_inverted_index")),
                    "cited_by_count":   work.get("cited_by_count", 0),
                    "authors":          authors,
                    "institutions":     institutions,
                    "fields":           fields,
                    "subfields":        subfields,
                    "topics":           topics_str,
                    "primary_topic":    (work.get("primary_topic") or {})
                                            .get("display_name", ""),
                    "open_access":      (work.get("open_access") or {})
                                            .get("is_oa", False),
                    "type":             work.get("type", ""),
                }
                for yr, cnt in cby.items():
                    row[f"cite_{yr}"] = cnt

                records.append(row)

            year_count += len(results)
            cursor = data.get("meta", {}).get("next_cursor")
            page_count += 1

            total_expected = data.get("meta", {}).get("count", "?")
            print(f"  Page {page_count:3d} | year {year}: {year_count}/{total_expected} "
                  f"| total so far: {len(records)}", end="\r")

            time.sleep(0.12)   # polite crawl

        print(f"\n  ✓ Year {year}: {year_count} papers fetched.")

    return records

# ─── ACC / YCC LABELS ────────────────────────────────────────────────────────

def add_labels(df: pd.DataFrame) -> pd.DataFrame:
    
    cite_years = sorted(
        int(c.split("_")[1]) for c in df.columns if c.startswith("cite_")
    )
    print("\nComputing ACC / YCC top-20% labels …")

    for pub_year in sorted(df["publication_year"].unique()):
        mask = df["publication_year"] == pub_year
        cohort = df.loc[mask]

        for y in cite_years:
            if y <= pub_year:
                continue
            n = y - pub_year   # years ahead

            # ACC: sum from pub_year+1 to y
            acc_cols = [f"cite_{yr}" for yr in cite_years
                        if pub_year < yr <= y and f"cite_{yr}" in df.columns]
            if acc_cols:
                acc_sum = cohort[acc_cols].sum(axis=1)
                thr = acc_sum.quantile(0.80)
                df.loc[mask, f"ACC_top20_year{n}"] = (acc_sum >= thr).astype(int)

            # YCC: citations in year y alone
            col = f"cite_{y}"
            if col in df.columns:
                ycc = cohort[col]
                thr = ycc.quantile(0.80)
                df.loc[mask, f"YCC_top20_year{n}"] = (ycc >= thr).astype(int)

    return df

# ─── RUN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  OpenAlex Extractor — ACS AMI")
    print("=" * 60)

    verify_source()

    records = fetch_papers()

    if not records:
        print("\n✗ No records fetched. Exiting.")
        sys.exit(1)

    df = pd.DataFrame(records)

    before = len(df)
    df = df[df["abstract"].str.strip() != ""].reset_index(drop=True)
    print(f"\nDropped {before - len(df)} papers without abstracts.")
    print(f"Remaining: {len(df):,} papers.")

    df = add_labels(df)

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n  Saved → {OUTPUT_FILE}")
    print(f"    Shape : {df.shape[0]:,} rows × {df.shape[1]} columns")

    print("\nColumn overview:")
    for col in df.columns:
        nn = df[col].notna().sum()
        print(f"  {col:<42} {nn:>7,} non-null")