
import pandas as pd

INPUT = "/home/vikash/preprocessing.csv"
OUT   = "/home/vikash/Dataset"
TOP   = 0.20   # top 20% = positive class 
SEED  = 42

df = pd.read_csv(INPUT)
print(f"Loaded {len(df):,} rows")

# ── Label: top 20% ACC within each publication-year cohort ───────────────────
def make_label(df, col):
    label = pd.Series(0, index=df.index)
    for _, grp in df.groupby("year"):
        thresh = grp[col].quantile(1 - TOP, interpolation='lower')
        label.loc[grp.index[grp[col] >= thresh]] = 1
    pos = label.sum()
    print(f"  label from {col}: pos={pos:,} ({pos/len(label)*100:.1f}%)  "
          f"neg={(label==0).sum():,}")
    return label

if "label" not in df.columns:
    df["label"] = make_label(df, "ACC")
else:
    print("Using existing label column")

# ── Skewed — natural 20/80 distribution ──────────────────────────────────────
df.to_csv(f"{OUT}skewed.csv", index=False)
print(f"Skewed   → {len(df):,} rows  "
      f"(pos={df['label'].sum():,}  neg={(df['label']==0).sum():,})")

# ── Balanced — undersample negatives to match positives ──────────────────────
pos      = df[df["label"] == 1]
neg      = df[df["label"] == 0].sample(n=len(pos), random_state=SEED)
balanced = pd.concat([pos, neg]).sample(frac=1, random_state=SEED)
balanced.to_csv(f"{OUT}balanced.csv", index=False)
print(f"Balanced → {len(balanced):,} rows  "
      f"(pos={balanced['label'].sum():,}  neg={(balanced['label']==0).sum():,})")

print("\nDone. Files written to", OUT)