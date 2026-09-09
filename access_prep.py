"""
access_prep.py: Data preparation for Page 3 (Access & Social Determinants)

WHAT THIS FILE DOES:
  Loads the CDC PLACES county data once at startup, isolates the six
  health-related social needs and prevention measures this page needs,
  pivots the data from long format (one row per county x measure) to
  wide format (one row per county, one column per measure), flips the
  CHECKUP measure so all bars read "higher = worse," and provides
  helper functions for filtering, sorting, ranking, and comparing
  counties.

HOW IT CONNECTS TO THE REST OF THE APP:
  - Reads from: data/places_county_clean.csv
  - Feeds into: pages/access_social_determinants.py
  - Cross-page link: when a bar is clicked, the county's locationid
    (5-digit FIPS code) is passed to Page 1's map via a URL query
    parameter so the map can auto-select that county.
"""

"""
AI ASSISTANCE:
  Used AI to draft the initial version of this file's
  data-prep logic and for iterative changes alongside the matching 
  changes in access_social_determinants.py.
  Specifics:
    - asked AI to draft the updated MEASURES/
      CLUSTERS definitions and the reworked data functions needed
      for the new page features
    - Asked AI to how to make the sidebar
      ranking always use the single primary measure, regardless of
      which extra measures are toggled for comparison.
  All AI-suggested code was reviewed, tested by running the app, and
  edited/approved by the team before being added to the project.
"""


import pandas as pd
from pathlib import Path


# ============================================================
# 1. MEASURE DEFINITIONS
# ============================================================
# Six measures now (down from nine) — Loneliness, Food stamp usage,
# and Utility shutoff threat were dropped from the Social & Economic
# Strain cluster per feedback, to keep that chart legible.
MEASURES = {
    # --- Access to Care cluster ---
    "ACCESS2": {
        "label": "Lacks health insurance",
        "column": "ACCESS2",
        "polarity": "worse",           # higher % = worse access
    },
    "CHECKUP": {
        "label": "No annual checkup",
        "column": "CHECKUP",
        "polarity": "better",          # higher % = BETTER — must flip!
    },
    # --- Social / Economic Strain cluster ---
    "FOODINSECU": {
        "label": "Food insecurity",
        "column": "FOODINSECU",
        "polarity": "worse",
    },
    "HOUSINSECU": {
        "label": "Housing insecurity",
        "column": "HOUSINSECU",
        "polarity": "worse",
    },
    "LACKTRPT": {
        "label": "Transportation barriers",
        "column": "LACKTRPT",
        "polarity": "worse",
    },
    "EMOTIONSPT": {
        "label": "Lack of social/emotional support",
        "column": "EMOTIONSPT",
        "polarity": "worse",
    },
}


# ============================================================
# 2. CLUSTER DEFINITIONS
# ============================================================
ACCESS_CLUSTER = ["ACCESS2", "CHECKUP"]
SOCIAL_CLUSTER = ["FOODINSECU", "HOUSINSECU", "LACKTRPT", "EMOTIONSPT"]

CLUSTERS = {
    "access": {
        "label": "Access to Care",
        "measures": ACCESS_CLUSTER,
        "description": "Insurance coverage and routine preventive care",
    },
    "social": {
        "label": "Social & Economic Strain",
        "measures": SOCIAL_CLUSTER,
        "description": "Food, housing, transportation, and social isolation",
    },
}


# ============================================================
# 3. LOAD THE CDC PLACES COUNTY DATA
# ============================================================
DATA_PATH = Path(__file__).parent / "data" / "places_county_clean.csv"

_raw_long = pd.read_csv(DATA_PATH, dtype={"locationid": str})
_raw_long["locationid"] = _raw_long["locationid"].str.zfill(5)

_measure_ids = list(MEASURES.keys())
_filtered = _raw_long[_raw_long["measureid"].isin(_measure_ids)].copy()

_places = _filtered.pivot_table(
    index=["locationid", "locationname", "statedesc",
           "latitude", "longitude",
           "totalpopulation", "totalpop18plus"],
    columns="measureid",
    values="crude_prevalence",
    aggfunc="first",
).reset_index()
_places.columns.name = None

# --- Validate expected columns exist after pivoting ---
_missing = []
for code, info in MEASURES.items():
    if info["column"] not in _places.columns:
        _missing.append(f"  {code} -> expected column '{info['column']}'")
if _missing:
    _missing_str = "\n".join(_missing)
    raise ValueError(
        f"access_prep.py: {len(_missing)} expected measure column(s) not "
        f"found after pivoting. Missing columns:\n{_missing_str}"
    )
for _loc_col in ("locationid", "locationname", "statedesc"):
    if _loc_col not in _places.columns:
        raise ValueError(
            f"access_prep.py: required column '{_loc_col}' not found "
            f"after pivoting."
        )


# ============================================================
# 4. POLARITY FLIP FOR CHECKUP
# ============================================================
# CHECKUP is "% who got a checkup" (higher = good). Flipping it to
# 100 - value turns it into "% who did NOT get a checkup," so every
# bar on the page means the same thing: taller = bigger gap = worse.
def _flip_polarity(df):
    out = df.copy()
    for code, info in MEASURES.items():
        col = info["column"]
        if col not in out.columns:
            continue
        if info["polarity"] == "better":
            out[col] = 100.0 - out[col]
    return out

_places = _flip_polarity(_places)


# ============================================================
# 5. STATE OPTIONS & MISSING-DATA HANDLING
# ============================================================
SOCIAL_MISSING_STATES = {
    "Colorado", "Florida", "Kentucky", "Oregon", "Pennsylvania",
    "South Dakota", "Tennessee", "Texas", "Vermont", "Washington",
    "Wyoming",
}

_all_states = sorted(_places["statedesc"].dropna().unique())
STATE_OPTIONS = [{"label": "National (Top N counties)", "value": "ALL"}]
STATE_OPTIONS += [{"label": s, "value": s} for s in _all_states]

DEFAULT_STATE = "Virginia"


# ============================================================
# 6. COLOR PALETTE
# ============================================================
MEASURE_COLORS = {
    "ACCESS2":     "#A8442E",  # rust — direct access barrier
    "CHECKUP":     "#C98A2E",  # amber — preventive care gap
    "FOODINSECU":  "#8B5A2B",  # warm brown — food
    "HOUSINSECU":  "#6B4226",  # darker brown — housing
    "LACKTRPT":    "#5C6D67",  # muted gray-green — transport
    "EMOTIONSPT":  "#1F7A63",  # teal — social support
}

LABEL_COLORS = {
    MEASURES[code]["label"]: MEASURE_COLORS[code]
    for code in MEASURE_COLORS
}


# ============================================================
# 7. MAIN DATA ACCESS FUNCTION — builds the chart data
# ============================================================
def get_cluster_data(state="Virginia", cluster_key="access",
                      measure_codes=None, top_n=15,
                      pinned_county=None, compare_counties=None):
    """
    Build the data behind the grouped bar chart.

    Parameters
    ----------
    state : str
        State name, or "ALL" for national.
    cluster_key : str
        "access" or "social" — which family of measures we're allowed
        to pick from.
    measure_codes : list of str or None
        Which measures are currently toggled ON in the chart. The
        FIRST code in this list is treated as the "primary" measure —
        it's the one counties are sorted by (biggest gap first). If
        None or empty, we fall back to the cluster's first measure so
        the chart is never blank.
    top_n : int
        How many counties to show in ranked view (ignored if
        compare_counties is given).
    pinned_county : str or None
        A single locationid (FIPS) to guarantee is included in the
        chart even if it didn't make the top N — this is what the
        "find a county" search box does.
    compare_counties : list of str or None
        Exactly the locationid values of the counties to show, in the
        order given. When provided, this OVERRIDES state/top_n/pinned
        entirely — it's the "compare two counties" mode.

    Returns
    -------
    (melted_df, raw_df)
        melted_df : long-format DataFrame ready for px.bar (one row
            per county x measure).
        raw_df : wide-format DataFrame of just the counties shown —
            used for stat cards.
    """
    cluster = CLUSTERS[cluster_key]
    valid_codes = cluster["measures"]

    # Keep only codes that actually belong to this cluster, in the
    # cluster's canonical order, so the bar order is stable.
    measure_codes = [c for c in (measure_codes or []) if c in valid_codes]
    if not measure_codes:
        measure_codes = [valid_codes[0]]

    # --- Step 1: filter to the counties we care about ---
    if compare_counties:
        df = _places[_places["locationid"].isin(compare_counties)].copy()
    elif state == "ALL":
        df = _places.copy()
    else:
        df = _places[_places["statedesc"] == state].copy()

    # --- Step 2: keep only the columns we need ---
    keep = ["locationid", "locationname", "statedesc"]
    for code in measure_codes:
        col = MEASURES[code]["column"]
        if col in df.columns:
            keep.append(col)
    df = df[keep]

    measure_cols = [c for c in keep if c not in
                    ("locationid", "locationname", "statedesc")]
    df = df.dropna(subset=measure_cols, how="all")

    if df.empty:
        return pd.DataFrame(), df

    # --- Step 3: pick the exact counties to display ---
    primary_col = MEASURES[measure_codes[0]]["column"]

    if compare_counties:
        # Keep the user's chosen order (County A first, then B).
        order = {fips: i for i, fips in enumerate(compare_counties)}
        df = df[df["locationid"].isin(order)]
        df = df.sort_values(
            by="locationid", key=lambda s: s.map(order)
        )
    else:
        df = df.sort_values(primary_col, ascending=False)
        top_df = df.head(top_n)
        # If a specific county was searched for and isn't already in
        # the top N, pin it to the front so it's always visible.
        if pinned_county and pinned_county not in top_df["locationid"].values:
            pinned_row = df[df["locationid"] == pinned_county]
            if not pinned_row.empty:
                top_df = pd.concat([pinned_row, top_df], ignore_index=True)
        df = top_df

    if df.empty:
        return pd.DataFrame(), df

    # --- Step 4: melt to long format for px.bar ---
    id_cols = ["locationid", "locationname", "statedesc"]
    value_vars, var_labels = [], {}
    for code in measure_codes:
        col = MEASURES[code]["column"]
        if col in df.columns:
            value_vars.append(col)
            var_labels[col] = MEASURES[code]["label"]

    melted = df.melt(
        id_vars=id_cols,
        value_vars=value_vars,
        var_name="measure_col",
        value_name="value",
    )
    melted["measure"] = melted["measure_col"].map(var_labels)
    melted["measure_code"] = melted["measure_col"]
    melted = melted.dropna(subset=["value"])

    return melted, df


# ============================================================
# 8. SUMMARY STATISTICS FOR STAT CARDS
# ============================================================
def get_state_summary(state, cluster_key, measure_code):
    """
    Numbers for the two stat cards above the chart: the average gap
    for the primary measure, and which county has the biggest gap.
    """
    if state == "ALL":
        df = _places.copy()
    else:
        df = _places[_places["statedesc"] == state].copy()

    col = MEASURES[measure_code]["column"]
    has_data = df[col].notna()
    n_counties = int(has_data.sum())

    avg_val = df.loc[has_data, col].mean() if n_counties > 0 else 0.0

    if n_counties > 0:
        worst_row = df.loc[has_data].nlargest(1, col).iloc[0]
        worst_county = worst_row["locationname"]
        worst_val = worst_row[col]
    else:
        worst_county = "—"
        worst_val = 0.0

    return {
        "avg": avg_val,
        "n_counties": n_counties,
        "worst_county": worst_county,
        "worst_val": worst_val,
    }


# ============================================================
# 9. SIDEBAR — TOP 10 MOST VULNERABLE COUNTIES
# ============================================================
def get_top_vulnerable_counties(state, measure_codes, n=10):
    """
    Rank counties for the sidebar. A county's "vulnerability score"
    is just the average of whatever measures are currently toggled on
    the chart — so the sidebar always reflects what's actually being
    shown, not a fixed formula.

    Returns a DataFrame with locationid, locationname, statedesc,
    score — worst (highest score) first, limited to n rows.
    """
    empty = pd.DataFrame(
        columns=["locationid", "locationname", "statedesc", "score"]
    )
    if not measure_codes:
        return empty

    if state == "ALL":
        df = _places.copy()
    else:
        df = _places[_places["statedesc"] == state].copy()

    cols = [MEASURES[c]["column"] for c in measure_codes
            if MEASURES[c]["column"] in df.columns]
    if not cols:
        return empty

    sub = df.dropna(subset=cols, how="all").copy()
    if sub.empty:
        return empty

    sub["score"] = sub[cols].mean(axis=1, skipna=True)
    sub = sub.sort_values("score", ascending=False).head(n)
    return sub[["locationid", "locationname", "statedesc", "score"]].reset_index(drop=True)


# ============================================================
# 10. HELPER: MEASURE DROPDOWN OPTIONS
# ============================================================
def get_measure_options(cluster_key, exclude=None):
    """
    Dropdown/checklist options for a cluster's measures.

    exclude : str or None — leave out one measure code (used to build
    the "also compare" checklist without repeating the primary
    measure that's already shown).
    """
    cluster = CLUSTERS[cluster_key]
    codes = [c for c in cluster["measures"] if c != exclude]
    return [{"label": MEASURES[c]["label"], "value": c} for c in codes]


# ============================================================
# 11. HELPER: COUNTY SEARCH / COMPARE DROPDOWN OPTIONS
# ============================================================
def get_county_options(state):
    """
    Alphabetical {label, value} list of counties, for the "find a
    county" search box and the two "compare counties" dropdowns.
    Value is the locationid (FIPS); label shows the state too so
    same-named counties in different states aren't ambiguous.
    """
    if state == "ALL":
        df = _places
    else:
        df = _places[_places["statedesc"] == state]
    df = df.sort_values("locationname")
    return [
        {"label": f"{row.locationname}, {row.statedesc}", "value": row.locationid}
        for row in df.itertuples()
    ]


# ============================================================
# 12. HELPER: TOTAL COUNTY COUNT (for the coverage note)
# ============================================================
def get_total_counties(state):
    if state == "ALL":
        return len(_places)
    return len(_places[_places["statedesc"] == state])