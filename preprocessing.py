

import pandas as pd
import ast

INPUT  = "/home/vikash/openalex_all_dataset.csv"
OUTPUT = "/home/vikash/Dataset"

# ─── LOAD ────────────────────────────────────────────────────────────────────
print("Loading CSV …")
df = pd.read_csv(INPUT, low_memory=False)
print(f"  Loaded: {len(df):,} rows × {df.shape[1]} columns")

# ─── CLEAN paper_id ──────────────────────────────────────────────────────────
# "https://openalex.org/W2741809807"  →  "W2741809807"
df["paper_id"] = df["openalex_id"].str.replace(
    "https://openalex.org/", "", regex=False
).str.strip()

# ─── CITATION PER YEAR (as a readable string) ────────────────────────────────
cite_cols = sorted(
    [c for c in df.columns if c.startswith("cite_")],
    key=lambda x: int(x.split("_")[1])
)

def build_cite_dict(row):
    return "{" + ", ".join(
        f"{c.split('_')[1]}:{int(row[c])}" for c in cite_cols
    ) + "}"

print("Building citation_per_year column …")
df["citation_per_year"] = df.apply(build_cite_dict, axis=1)

# ─── IDENTIFY ACC / YCC LABEL COLUMNS ────────────────────────────────────────
acc_cols = sorted(
    [c for c in df.columns if c.startswith("ACC_top20_year")],
    key=lambda x: int(x.replace("ACC_top20_year", ""))
)
ycc_cols = sorted(
    [c for c in df.columns if c.startswith("YCC_top20_year")],
    key=lambda x: int(x.replace("YCC_top20_year", ""))
)

# ─── RESHAPE TO LONG FORMAT (one row per paper × years_ahead) ────────────────
print("Reshaping to long format (paper × years_ahead) …")

base_cols = ["paper_id", "title", "abstract", "publication_year",
             "cited_by_count", "citation_per_year"]

rows = []
for _, r in df[base_cols + acc_cols + ycc_cols].iterrows():
    for acc_col, ycc_col in zip(acc_cols, ycc_cols):
        n = int(acc_col.replace("ACC_top20_year", ""))
        acc_val = r[acc_col]
        ycc_val = r[ycc_col]

        # Skip if no label exists (paper too recent for this years_ahead)
        if pd.isna(acc_val) or pd.isna(ycc_val):
            continue

        rows.append({
            "paper_id":          r["paper_id"],
            "title":             r["title"],
            "abstract":          r["abstract"],
            "year":              int(r["publication_year"]),
            "citation_total":    int(r["cited_by_count"]),
            "citation_per_year": r["citation_per_year"],
            "ACC":               int(acc_val),
            "YCC":               int(ycc_val),
            "years_ahead":       n,
            "label":             f"ACC={int(acc_val)},YCC={int(ycc_val)}",
        })

out = pd.DataFrame(rows, columns=[
    "paper_id", "title", "abstract", "year",
    "citation_total", "citation_per_year",
    "ACC", "YCC", "years_ahead", "label"
])

# ─── SAVE ────────────────────────────────────────────────────────────────────
out.to_csv(OUTPUT, index=False)
print(f"\n  Saved → {OUTPUT}")
print(f"    Shape : {out.shape[0]:,} rows × {out.shape[1]} columns")

# ─── PREVIEW ─────────────────────────────────────────────────────────────────
print("\nSample rows:")
print(out.head(3).to_string(index=False))

print("\nColumn value counts (label):")
print(out["label"].value_counts())

print("\nYears ahead distribution:")
print(out["years_ahead"].value_counts().sort_index())