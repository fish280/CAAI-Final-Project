"""
access_prep.py — Data preparation for Page 3 (Access & Social Determinants)

WHAT THIS FILE DOES:
  Loads the CDC PLACES county data once at startup, isolates the nine
  health-related social needs (SOCLNEED) and prevention measures that
  this page needs, pivots the data from long format (one row per
  county × measure) to wide format (one row per county, one column
  per measure), flips the CHECKUP measure so all bars read
  "higher = worse," and provides helper functions for filtering,
  sorting, and flagging counties with severe access gaps.

WHY IT'S A SEPARATE FILE (same pattern as data_prep.py and risk_prep.py):
  Each page in the dashboard has its own prep module so the data
  loading and measure-specific logic live in one place. The page file
  (pages/access_social_determinants.py) only handles layout and
  callbacks; it imports everything it needs from here. This keeps the
  page file readable and makes it easy to test the data logic
  independently of the UI.

HOW IT CONNECTS TO THE REST OF THE APP:
  - Reads from: data/places_county_clean.csv (the same CDC PLACES
    dataset the other pages use — long format, one row per county ×
    measure)
  - Feeds into: pages/access_social_determinants.py (David's page)
  - Cross-page link: when a bar is clicked, the county's locationid
    (5-digit FIPS code) is passed to Page 1's map via URL query
    parameter so the map can auto-select that county

DATA SOURCE NOTE:
  The CSV is in LONG format: each row is one county × one measure.
  Columns include: locationid, measureid, crude_prevalence,
  adj_prevalence, statedesc, locationname, latitude, longitude,
  totalpopulation, etc. This module pivots the data to wide format
  (one row per county, one column per measure) so the page callbacks
  can work with it the same way they would with a wide-format CSV.
"""

import pandas as pd
from pathlib import Path


# ============================================================
# 1. MEASURE DEFINITIONS
# ============================================================
# WHY A DICTIONARY INSTEAD OF HARD-CODED COLUMN NAMES:
#   Each of the 9 measures has a short code (ACCESS2, CHECKUP, etc.)
#   that matches the measureid column in the CSV, a human-readable
#   label ("Lacks health insurance"), and a polarity ("worse" means
#   higher % = worse outcome; "better" means higher % = better
#   outcome and must be flipped). Centralizing this metadata means
#   the label and polarity only live in ONE place — if you add or
#   remove a measure, you change it here and every callback, chart,
#   and tooltip picks it up automatically.
#
# COLUMN NAMES AFTER PIVOTING:
#   After we pivot the long-format CSV to wide format, each measure
#   becomes a column named after its measureid (e.g., "ACCESS2",
#   "CHECKUP"). The "column" field below tells the pivot and the
#   helper functions which column to look for — it matches the
#   measureid value in the raw CSV.

MEASURES = {
    # --- Access to Care cluster ---
    "ACCESS2": {
        "label": "Lacks health insurance",
        "column": "ACCESS2",           # matches measureid in the CSV
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
    "LONELINESS": {
        "label": "Loneliness",
        "column": "LONELINESS",
        "polarity": "worse",
    },
    "FOODSTAMP": {
        "label": "Food stamp usage",
        "column": "FOODSTAMP",
        "polarity": "worse",          # proxy for economic need
    },
    "SHUTUTILITY": {
        "label": "Utility shutoff threat",
        "column": "SHUTUTILITY",
        "polarity": "worse",
    },
}


# ============================================================
# 2. CLUSTER DEFINITIONS
# ============================================================
# WHY TWO CLUSTERS INSTEAD OF ALL 9 AT ONCE:
#   A grouped bar chart with 9 bars per county across 15–20 counties
#   would be 135–180 bars — completely unreadable. Instead, the
#   measures are split into two thematic clusters that match how a
#   program officer actually thinks about the problem:
#
#   "Can people get to a doctor?" → Access to Care
#       (insurance coverage + routine preventive care)
#
#   "Are their basic needs met?" → Social & Economic Strain
#       (food, housing, transportation, social isolation, utilities)
#
#   The dashboard toggles between these clusters so each view stays
#   legible (2 bars per county for Access, 7 for Social — still dense
#   but manageable with hovering).

ACCESS_CLUSTER = ["ACCESS2", "CHECKUP"]
SOCIAL_CLUSTER = [
    "FOODINSECU", "HOUSINSECU", "LACKTRPT",
    "EMOTIONSPT", "LONELINESS", "FOODSTAMP", "SHUTUTILITY",
]

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
# WHY LOAD AT IMPORT TIME:
#   The CSV is ~20 MB and contains 114,000+ rows (one per county ×
#   measure). Reading it from disk on every user interaction would
#   make the dashboard sluggish. By loading it once here — when
#   Python first imports this module — the entire DataFrame sits in
#   memory and every callback reuses the same object. This is the
#   same pattern Lauren and Samuel use in data_prep.py and risk_prep.py.

# WHY Path(__file__).parent / "data" / ...: This resolves the CSV
# path relative to THIS file's location, then looks inside a "data"
# subfolder. So if access_prep.py is in CAAI-Final-Project\, the CSV
# should be at CAAI-Final-Project\data\places_county_clean.csv.
DATA_PATH = Path(__file__).parent / "data" / "places_county_clean.csv"

# Read the raw long-format CSV.
# WHY dtype={"locationid": str}: FIPS codes like "01001" lose their
# leading zero if pandas reads them as integers. The cross-page link
# to Page 1's map depends on locationid matching the GeoJSON keys,
# which are always 5-digit strings.
_raw_long = pd.read_csv(DATA_PATH, dtype={"locationid": str})
_raw_long["locationid"] = _raw_long["locationid"].str.zfill(5)


# ============================================================
# 3b. FILTER AND PIVOT TO WIDE FORMAT
# ============================================================
# WHY PIVOT:
#   The CSV is in long format — each row is one county × one measure.
#   For example, Autauga County, AL has 9 rows (one per measure we
#   care about), each with a different crude_prevalence value. The
#   grouped bar chart needs wide format — one row per county with
#   separate columns for each measure. Pandas' pivot_table does this
#   transformation.
#
# WHY FILTER FIRST:
#   The full CSV has 80+ measures. We only need our 9, so filtering
#   before pivoting keeps the pivot result small and fast.

_measure_ids = list(MEASURES.keys())

# Filter to only the 9 measures this page needs
_filtered = _raw_long[_raw_long["measureid"].isin(_measure_ids)].copy()

# Pivot from long to wide format:
#   - Index: one row per county (identified by locationid)
#   - Columns: one column per measure (using measureid as column name)
#   - Values: crude_prevalence
#   - aggfunc="first": if there happen to be duplicate rows, take the
#     first one (there shouldn't be, but this prevents errors)
_places = _filtered.pivot_table(
    index=["locationid", "locationname", "statedesc",
           "latitude", "longitude",
           "totalpopulation", "totalpop18plus"],
    columns="measureid",
    values="crude_prevalence",
    aggfunc="first",
).reset_index()

# Flatten the column index (pivot_table creates a MultiIndex column
# when using multiple index columns; reset_index fixes the row index
# but the column name might still be in a hierarchy)
_places.columns.name = None


# ============================================================
# 3c. VALIDATE EXPECTED COLUMNS
# ============================================================
# WHY: After pivoting, each measure should have its own column. If
# a measure had zero rows in the CSV (unlikely but possible), its
# column won't exist after pivoting. This check catches that.
_missing = []
for code, info in MEASURES.items():
    if info["column"] not in _places.columns:
        _missing.append(f"  {code} -> expected column '{info['column']}'")
if _missing:
    _missing_str = "\n".join(_missing)
    raise ValueError(
        f"access_prep.py: {len(_missing)} expected measure column(s) not "
        f"found after pivoting. Missing columns:\n{_missing_str}\n\n"
        f"These measures may not exist in the CSV's measureid column."
    )

# Also verify the location columns exist
for _loc_col in ("locationid", "locationname", "statedesc"):
    if _loc_col not in _places.columns:
        raise ValueError(
            f"access_prep.py: required column '{_loc_col}' not found "
            f"after pivoting. Check the CSV has these columns: "
            f"locationid, locationname, statedesc."
        )


# ============================================================
# 4. POLARITY FLIP FOR CHECKUP (AND ANY "HIGHER = BETTER" MEASURE)
# ============================================================
# WHY THIS IS NECESSARY:
#   The CDC measures CHECKUP as "% of adults who had an annual
#   checkup" — so a HIGH number is GOOD (more people getting
#   checkups). But every other measure on this page is framed as a
#   gap or hardship where HIGH = BAD. If we plot CHECKUP alongside
#   ACCESS2 without flipping, a tall CHECKUP bar would look like a
#   bad thing when it's actually a good thing — the chart would be
#   actively misleading.
#
#   THE FIX: Convert CHECKUP to 100 − value, which turns
#   "% who got a checkup" into "% who did NOT get a checkup."
#   Now every bar on the chart means the same thing:
#       taller bar = bigger gap = worse.
#
#   This is the "insurance/checkup gap" language from the project's
#   own planning doc — the professor framed it as a gap, not a rate.

def _flip_polarity(df):
    """
    Flip any measure whose polarity is "better" so that ALL measures
    read "higher = worse gap." Returns a new DataFrame; does not
    modify the original.

    Currently only CHECKUP is flipped, but if a future measure is
    added with polarity "better," this function handles it
    automatically — no other code needs to change.
    """
    out = df.copy()
    for code, info in MEASURES.items():
        col = info["column"]
        if col not in out.columns:
            continue
        if info["polarity"] == "better":
            # 100 − checkup rate = share who didn't get a checkup
            out[col] = 100.0 - out[col]
    return out

# Apply the flip ONCE at import time so every callback gets
# consistent, already-flipped data without re-doing the math.
_places = _flip_polarity(_places)


# ============================================================
# 5. STATE OPTIONS & MISSING-DATA HANDLING
# ============================================================
# WHY THIS MATTERS:
#   The CDC's social-needs questions (food insecurity, housing
#   insecurity, loneliness, etc.) come from a special BRFSS survey
#   module that 11 states chose not to administer. Those states have
#   ZERO data for the entire Social & Economic Strain cluster — not
#   just a few missing values, but no rows at all. If the state
#   dropdown lets someone pick Texas and switch to the Social
#   cluster, the chart would be blank with no explanation.
#
#   We handle this two ways:
#   1. The dropdown still lists all states (so the user can pick
#      Access to Care for any state), but the chart shows a clear
#      empty-state message when social-needs data is missing.
#   2. We export the set of missing states so the page can display
#      a contextual note.

SOCIAL_MISSING_STATES = {
    "Colorado", "Florida", "Kentucky", "Oregon", "Pennsylvania",
    "South Dakota", "Tennessee", "Texas", "Vermont", "Washington",
    "Wyoming",
}

# Build the state dropdown from states that actually appear in the
# data, sorted alphabetically. The "National (Top N)" option lets
# the user see the worst counties across the entire country without
# picking a specific state — useful for a grant-maker comparing
# across state lines.
_all_states = sorted(_places["statedesc"].dropna().unique())
STATE_OPTIONS = [{"label": "National (Top N counties)", "value": "ALL"}]
STATE_OPTIONS += [{"label": s, "value": s} for s in _all_states]

# Default to Virginia — matches the rest of the dashboard's scope
# decision (Page 1's map is Virginia-only, so cross-page links work
# cleanly when both pages look at the same state).
DEFAULT_STATE = "Virginia"


# ============================================================
# 6. COLOR PALETTE (from styles.css)
# ============================================================
# WHY FIXED COLORS PER MEASURE:
#   Each measure gets a fixed color so the user can identify it
#   across different views, states, and sort orders. If ACCESS2 is
#   always rust-colored, the user learns that association and can
#   read the chart faster.
#
#   The colors are drawn from the project's styles.css palette:
#     risk-high  #A8442E (rust)    — direct access barriers
#     risk-mid   #C98A2E (amber)   — preventive care gaps
#     risk-low   #1F7A63 (teal)    — social/emotional measures
#   plus muted earth tones for the strain cluster, keeping the
#   chart visually consistent with the rest of the site.

MEASURE_COLORS = {
    "ACCESS2":     "#A8442E",  # rust — direct access barrier
    "CHECKUP":     "#C98A2E",  # amber — preventive care gap
    "FOODINSECU":  "#8B5A2B",  # warm brown — food
    "HOUSINSECU":  "#6B4226",  # darker brown — housing
    "LACKTRPT":    "#5C6D67",  # muted gray-green — isolation/transport
    "EMOTIONSPT":  "#1F7A63",  # teal — social support
    "LONELINESS":  "#2E8B62",  # green — loneliness
    "FOODSTAMP":   "#4A7C6E",  # teal-green — economic need
    "SHUTUTILITY": "#86948E",  # gray — utility
}

# Map from human-readable measure labels to colors.
# WHY: Plotly Express's px.bar(color=...) keys the color map by the
# values in the color column. We use the human-readable label as the
# color column (so the legend says "Food insecurity" not "FOODINSECU"),
# so the color map must also be keyed by label.
LABEL_COLORS = {
    MEASURES[code]["label"]: MEASURE_COLORS[code]
    for code in MEASURE_COLORS
}


# ============================================================
# 7. FLAGGING SYSTEM — COUNTIES WITH SEVERE ACCESS GAPS
# ============================================================
# WHY THIS EXISTS:
#   The brainstorming doc asks for "a flagging system for counties
#   that severely lack access to healthcare options." A flat ranking
#   hides counties that are extreme on ONE measure but moderate on
#   others — exactly the counties a program officer needs to see.
#
#   HOW IT WORKS:
#   A county is "flagged" if ANY of its measures in the current
#   cluster exceeds the 90th percentile nationally. The OR logic is
#   deliberate: a county might have a moderate food insecurity rate
#   but the worst transportation barrier rate in the country. That
#   county deserves attention even though its average looks fine.
#
#   The threshold (90th percentile) is adjustable below. Lower it to
#   flag more counties; raise it to be more selective.

SEVERE_THRESHOLD_PERCENTILE = 90


def flag_severe_counties(df, measure_codes):
    """
    Returns a set of locationid strings for counties where ANY of the
    given measures exceeds the 90th percentile nationally.

    Parameters:
    -----------
    df : DataFrame
        The full (already-pivoted, already-flipped) CDC PLACES DataFrame.
    measure_codes : list of str
        Measure codes to check (e.g., ["ACCESS2", "CHECKUP"]).

    Returns:
    --------
    set of str — locationid values for flagged counties.
    """
    flagged = set()
    for code in measure_codes:
        col = MEASURES[code]["column"]
        if col not in df.columns:
            continue
        # Compute the 90th percentile threshold for this measure
        # across ALL counties (not just the current state), so the
        # flag means "extreme relative to the national distribution."
        threshold = df[col].dropna().quantile(
            SEVERE_THRESHOLD_PERCENTILE / 100.0
        )
        severe = df[df[col] >= threshold]
        flagged.update(severe["locationid"].tolist())
    return flagged


# ============================================================
# 8. MAIN DATA ACCESS FUNCTION
# ============================================================

def get_cluster_data(state="Virginia", cluster_key="access",
                     sort_measure=None, sort_order="gap", top_n=15):
    """
    Filter, sort, and prepare data for the grouped bar chart.

    This is the function the page's main callback calls every time
    the user changes a dropdown or toggle. It does all the data work
    in one place so the callback stays focused on building the figure.

    Parameters:
    -----------
    state : str
        State name (e.g., "Virginia"), or "ALL" for national top-N.
    cluster_key : str
        "access" or "social" — which cluster of measures to show.
    sort_measure : str or None
        Which measure code to sort counties by. If None, defaults to
        the first measure in the cluster (ACCESS2 for Access,
        FOODINSECU for Social).
    sort_order : str
        "gap" = biggest gap first (descending by sort measure value),
        "alpha" = alphabetical by county name.
    top_n : int
        How many counties to show (typically 10, 15, or 20).

    Returns:
    --------
    (melted_df, raw_df, flag_set)
        - melted_df: long-format DataFrame for px.bar — one row per
          county × measure, with columns: locationid, locationname,
          statedesc, measure (human-readable label), measure_code,
          and value (the percentage).
        - raw_df: wide-format DataFrame with the selected counties
          (one row per county, one column per measure) — used for
          the stat cards and coverage note.
        - flag_set: set of locationid strings for counties flagged
          as severely lacking (90th percentile or worse on any
          measure in the cluster).
    """
    cluster = CLUSTERS[cluster_key]
    measure_codes = cluster["measures"]

    # --- Step 1: Filter by state ---
    # WHY: The state dropdown narrows from ~3,144 national counties
    # to one state's counties (Virginia has 133). The "ALL" option
    # keeps all counties but we'll take only the top N below.
    if state == "ALL":
        df = _places.copy()
    else:
        df = _places[_places["statedesc"] == state].copy()

    # --- Step 2: Keep only the columns we need ---
    # WHY: The pivoted DataFrame has many columns (location info +
    # all 9 measures + population). We only need the location
    # identifiers and the measures in the current cluster.
    keep = ["locationid", "locationname", "statedesc"]
    for code in measure_codes:
        col = MEASURES[code]["column"]
        if col in df.columns:
            keep.append(col)
    df = df[keep]

    # Drop counties that have NO data for ANY measure in this cluster.
    # WHY: A county with all-NaN values would show as empty bars and
    # waste chart space. (how="all" means only drop if every measure
    # column is NaN — a county with data for 5 of 7 measures stays.)
    measure_cols = [c for c in keep if c not in
                    ("locationid", "locationname", "statedesc")]
    df = df.dropna(subset=measure_cols, how="all")

    # If nothing survived (e.g., a state with no social-needs data),
    # return empty results so the chart shows an empty-state message.
    if df.empty:
        return pd.DataFrame(), df, set()

    # --- Step 3: Sort ---
    # WHY "biggest gap first" is the default: a program officer's
    # primary question is "where is it worst?" — sorting by the
    # selected measure puts the highest-need counties at the left
    # where they're seen first. Alphabetical is the secondary option
    # for when the user wants to find a specific county by name.
    if sort_measure is None or sort_measure not in measure_codes:
        sort_measure = measure_codes[0]

    sort_col = MEASURES[sort_measure]["column"]
    if sort_order == "gap":
        df = df.sort_values(sort_col, ascending=False)
    else:
        df = df.sort_values("locationname")

    # --- Step 4: Top N ---
    # WHY: Even within one state, Virginia has 133 counties — too
    # many for a grouped bar chart. We take the top N (default 15)
    # after sorting, so the chart shows the most relevant counties.
    # For the national view, this is essential (3,144 counties would
    # be impossible to plot as bars).
    df = df.head(top_n)

    # --- Step 5: Flag severe counties (national threshold) ---
    # WHY: We compute flags against the FULL national distribution
    # (not just the current state) so "flagged" means "extreme
    # relative to the whole country," not just "extreme within
    # this state." A county that's worst in Virginia but only
    # average nationally should NOT be flagged.
    flags = flag_severe_counties(_places, measure_codes)

    # --- Step 6: Melt to long format ---
    # WHY: Plotly Express's px.bar with barmode="group" needs data
    # in "long" format — one row per bar. Right now our DataFrame is
    # "wide" (one row per county, one column per measure). Melting
    # transforms it so each county × measure combination gets its
    # own row, which is what px.bar uses to draw and color each bar.
    id_cols = ["locationid", "locationname", "statedesc"]
    value_vars = []
    var_labels = {}  # maps column name → human-readable label
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
    # Replace raw column names with human-readable labels for the
    # legend and hover tooltips.
    melted["measure"] = melted["measure_col"].map(var_labels)
    # Keep the measure code for color mapping (MEASURE_COLORS is
    # keyed by code, not by label).
    melted["measure_code"] = melted["measure_col"]

    # Drop rows where the value is NaN — these would render as
    # invisible bars and clutter the hover.
    melted = melted.dropna(subset=["value"])

    return melted, df, flags


# ============================================================
# 9. SUMMARY STATISTICS FOR STAT CARDS
# ============================================================

def get_state_summary(state, cluster_key, sort_measure):
    """
    Compute the numbers shown in the stat cards above the chart.

    WHY: The stat cards give the user a quick read on the current
    selection — what's the average gap, how many counties have data,
    which county is worst, and how many are flagged. These numbers
    must reflect the user's current filter (state + cluster + sort
    measure), not national totals, because a program officer looking
    at Virginia doesn't care about California's averages.

    Returns a dict with: avg, n_counties, worst_county, worst_val,
    n_flagged.
    """
    cluster = CLUSTERS[cluster_key]
    measure_codes = cluster["measures"]

    # Use the full dataset (not the top-N subset) for summary stats
    # so the averages reflect the entire state, not just the 15
    # counties shown in the chart.
    if state == "ALL":
        df = _places.copy()
    else:
        df = _places[_places["statedesc"] == state].copy()

    sort_col = MEASURES[sort_measure]["column"]

    # Counties with data for the sort measure
    has_data = df[sort_col].notna()
    n_counties = int(has_data.sum())

    # Average gap for the sort measure (simple mean — not population-
    # weighted, because CDC PLACES already accounts for sample size
    # in its small-area estimation methodology)
    avg_val = df.loc[has_data, sort_col].mean() if n_counties > 0 else 0.0

    # Worst county (highest value = biggest gap)
    if n_counties > 0:
        worst_row = df.loc[has_data].nlargest(1, sort_col).iloc[0]
        worst_county = worst_row["locationname"]
        worst_val = worst_row[sort_col]
    else:
        worst_county = "—"
        worst_val = 0.0

    # Count flagged counties in this selection
    flags = flag_severe_counties(_places, measure_codes)
    if state != "ALL":
        state_fips = set(df["locationid"])
        n_flagged = len(flags & state_fips)
    else:
        n_flagged = len(flags)

    return {
        "avg": avg_val,
        "n_counties": n_counties,
        "worst_county": worst_county,
        "worst_val": worst_val,
        "n_flagged": n_flagged,
    }


# ============================================================
# 10. HELPER: SORT-MEASURE DROPDOWN OPTIONS
# ============================================================

def get_measure_options(cluster_key):
    """
    Return dropdown options for the "sort by" measure selector.

    WHY: When the user switches clusters (e.g., from Access to
    Social), the sort-measure dropdown must update to show only the
    measures in the new cluster. If ACCESS2 was selected and the
    user switches to Social, ACCESS2 isn't in that cluster — the
    dropdown needs to reset to a valid option (FOODINSECU by
    default).
    """
    cluster = CLUSTERS[cluster_key]
    return [
        {"label": MEASURES[c]["label"], "value": c}
        for c in cluster["measures"]
    ]


# ============================================================
# 11. HELPER: TOTAL COUNTY COUNT (for coverage notes)
# ============================================================

def get_total_counties(state):
    """
    Return the total number of counties in the given state
    (or nationally if state == "ALL").

    WHY: The coverage note below the chart tells the user how many
    counties have data vs. how many exist. For example, "Data covers
    129 of 133 counties in Virginia" alerts the user that 4 counties
    are missing without surprising them with a shorter-than-expected
    chart.
    """
    if state == "ALL":
        return len(_places)
    return len(_places[_places["statedesc"] == state])
