import pandas as pd
from API_fetch import get_raw_places_data

df = get_raw_places_data()

print("=== Overall shape ===")
print(f"Rows: {len(df)}, Columns: {len(df.columns)}")

print("\n=== Missing values per column ===")
missing = df.isna().sum()
missing_pct = (missing / len(df) * 100).round(1)
report = pd.DataFrame({"missing_count": missing, "missing_pct": missing_pct})
print(report[report["missing_count"] > 0].sort_values("missing_count", ascending=False))

print("\n=== Missing data_value by measure ===")
if "measure" in df.columns:
    by_measure = df[df["data_value"].isna()].groupby("measure").size().sort_values(ascending=False)
    print(by_measure)

print("\n=== Rows with a footnote explaining suppression ===")
if "data_value_footnote" in df.columns:
    print(df["data_value_footnote"].value_counts(dropna=True))

suppressed = df[df["data_value"].isna()]
print(suppressed[["stateabbr", "locationname", "locationid"]].drop_duplicates())

no_location = df[df["locationname"].isna()]
print(no_location[["stateabbr", "locationid", "measure", "data_value_footnote"]].drop_duplicates())

print(suppressed["data_value_type"].value_counts())
print(no_location["stateabbr"].value_counts())