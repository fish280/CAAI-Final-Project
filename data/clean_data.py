import pandas as pd
import ast
import re
from API_fetch import get_raw_places_data

ARTIFACT_COLS = [":@computed_region_hjsp_umg2", ":@computed_region_skr5_azej"]
TEXT_COLS = ["stateabbr", "statedesc", "locationname", "datasource",
             "category", "measure", "data_value_unit", "data_value_type",
             "short_question_text"]


def check_duplicates(df):
    exact_dupes = df.duplicated().sum()
    print(f"Exact duplicate rows: {exact_dupes}")
    key_cols = ["locationid", "measure", "data_value_type"]
    key_dupes = df.duplicated(subset=key_cols, keep=False).sum()
    print(f"Rows sharing the same county + measure + value-type combo: {key_dupes}")


def check_year_consistency(df):
    year_per_group = df.groupby(["locationid", "measure"])["year"].nunique()
    mismatches = year_per_group[year_per_group > 1]
    print(f"County+measure combos where crude/adjusted disagree on year: {len(mismatches)}")


def split_geolocation(df):
    def parse_point(val):
        if pd.isna(val):
            return (None, None)
        if isinstance(val, str):
            try:
                parsed = ast.literal_eval(val)
                coords = parsed.get("coordinates")
                if coords and len(coords) == 2:
                    return (coords[0], coords[1])
            except (ValueError, SyntaxError):
                match = re.match(r"POINT \(([-\d\.]+) ([-\d\.]+)\)", val)
                if match:
                    return (float(match.group(1)), float(match.group(2)))
        return (None, None)

    parsed = df["geolocation"].apply(parse_point)
    df["longitude"] = parsed.apply(lambda c: c[0])
    df["latitude"] = parsed.apply(lambda c: c[1])
    return df


def clean_data(df):
    df = df.drop(columns=[c for c in ARTIFACT_COLS if c in df.columns])
    df = df[df["stateabbr"] != "US"].copy()

    for col in TEXT_COLS:
        if col in df.columns:
            df[col] = df[col].str.strip()

    df["locationid"] = df["locationid"].astype(str).str.zfill(5)

    numeric_cols = ["data_value", "low_confidence_limit", "high_confidence_limit",
                     "totalpopulation", "totalpop18plus"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = split_geolocation(df)

    # Minimal pivot key — only what's needed to identify a crude/adjusted pair.
    # unstack() reshapes existing rows only; it won't explode like pivot_table did.
    pivot_key = ["locationid", "measure", "year"]
    wide = (
        df.set_index(pivot_key + ["data_value_type"])["data_value"]
        .unstack("data_value_type")
        .rename(columns={
            "Crude prevalence": "crude_prevalence",
            "Age-adjusted prevalence": "adj_prevalence"
        })
        .reset_index()
    )

    # Descriptive columns are 1:1 with locationid or measure — bring them back via lookup,
    # instead of cramming them into the pivot index.
    county_info = df[["locationid", "stateabbr", "statedesc", "locationname",
                       "totalpopulation", "totalpop18plus",
                       "latitude", "longitude"]].drop_duplicates(subset="locationid")
    measure_info = df[["measure", "measureid", "category", "categoryid",
                        "short_question_text"]].drop_duplicates(subset="measure")

    wide = wide.merge(county_info, on="locationid", how="left")
    wide = wide.merge(measure_info, on="measure", how="left")

    return wide


if __name__ == "__main__":
    raw = get_raw_places_data()
    check_duplicates(raw)
    check_year_consistency(raw)

    cleaned = clean_data(raw)
    print(f"\nCleaned shape: {cleaned.shape}")
    print(cleaned.head())
    print(f"\nCounties in cleaned data: {cleaned['locationid'].nunique()}")

    cleaned.to_csv("data/places_county_clean.csv", index=False)
    print("Saved to places_county_clean.csv")