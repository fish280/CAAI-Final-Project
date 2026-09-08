"""
risk_prep.py — National county-level data prep for the
"Drivers & Risk Factors" page (page 2). Owned by Samuel.

Deliberately separate from data_prep.py (which is Virginia-only and
feeds the Overview map) so the two pages can evolve without stepping
on each other. Page 3 can import from here too.

Everything in this module is a pure transform of
data/places_county_clean.csv — no network calls, no globals mutated
by callbacks, so the helpers below are directly unit-testable.

AI assistance: used Claude Code to draft the wide-pivot structure and
the residual/correlation helper, then verified column names, the
suppressed-county behavior, and the polyfit edge cases against the
real CSV. -- SAMUEL: edit this line to reflect what you actually did.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Resolve the CSV relative to this file, not the working directory, so
# the app runs the same locally and on Render.
CSV_PATH = Path(__file__).parent / "data" / "places_county_clean.csv"

ALL_STATES = "__ALL__"          # sentinel for the "national" dropdown option
MIN_COUNTIES_FOR_FIT = 3        # below this, a regression line is meaningless

# Long CDC category names -> short labels for dropdown grouping, and the
# order we want them to appear in (drivers first, outcomes last, because
# the user is looking for a cause).
CATEGORY_LABELS = {
    "Health Risk Behaviors":        "Risk Behaviors",
    "Health-Related Social Needs":  "Social Needs",
    "Prevention":                   "Access & Prevention",
    "Disability":                   "Disability",
    "Health Status":                "Health Status",
    "Health Outcomes":              "Outcomes",
}
CATEGORY_ORDER = list(CATEGORY_LABELS)

# --------------------------------------------------------------------
# Load
# --------------------------------------------------------------------
# locationid is a 5-digit county FIPS code. Read it as a string and
# re-pad: casting to int silently drops the leading zero on states like
# Alabama ("01001" -> 1001) and breaks every geographic join downstream.
_df = pd.read_csv(CSV_PATH, dtype={"locationid": str})
_df["locationid"] = _df["locationid"].str.zfill(5)

# One row per measure describing what it is. short_question_text is the
# display label used everywhere in the UI ("Physical Inactivity");
# `measure` is the full CDC sentence, kept for footnotes and tooltips.
MEASURE_META = (
    _df.drop_duplicates("measureid")[
        ["measureid", "short_question_text", "measure", "category", "year"]
    ]
    .rename(columns={"short_question_text": "label"})
    .assign(
        category_short=lambda d: d["category"].map(CATEGORY_LABELS),
        category_rank=lambda d: d["category"].map(CATEGORY_ORDER.index),
    )
    .sort_values(["category_rank", "label"])
    .set_index("label")
)

MEASURE_LABELS = list(MEASURE_META.index)

# Dropdown options, category-prefixed so a user can find "Food
# Insecurity" without knowing CDC's taxonomy. dcc.Dropdown has no
# native optgroup support, hence the prefix.
MEASURE_OPTIONS = [
    {"label": f"{row.category_short}  ·  {label}", "value": label}
    for label, row in MEASURE_META.iterrows()
]

# --------------------------------------------------------------------
# Wide frames: one row per county, one column per measure
# --------------------------------------------------------------------
_COUNTY_COLS = [
    "locationid", "locationname", "stateabbr", "statedesc",
    "totalpopulation", "totalpop18plus", "latitude", "longitude",
]
_county_meta = _df.drop_duplicates("locationid")[_COUNTY_COLS].copy()


def _to_wide(value_col: str) -> pd.DataFrame:
    """Pivot the long file to one row per county, one column per measure.

    Pivoting on locationid + measure only (not the 14 descriptive
    columns) and merging the descriptive columns back afterwards --
    pivoting on all of them blows up the product space.
    """
    wide = _df.pivot_table(
        index="locationid",
        columns="short_question_text",
        values=value_col,
    )
    wide.columns.name = None
    return _county_meta.merge(wide, on="locationid", how="left")


WIDE_CRUDE = _to_wide("crude_prevalence")
WIDE_ADJ = _to_wide("adj_prevalence")

STATE_OPTIONS = [{"label": "All states (national)", "value": ALL_STATES}] + [
    {"label": s, "value": s} for s in sorted(_county_meta["statedesc"].unique())
]

BASIS_FRAMES = {"crude": WIDE_CRUDE, "adjusted": WIDE_ADJ}
BASIS_LABELS = {"crude": "crude prevalence", "adjusted": "age-adjusted prevalence"}


# --------------------------------------------------------------------
# Analysis helpers  (pure functions -- these are the ones worth testing)
# --------------------------------------------------------------------
def measure_year(label: str) -> int:
    """BRFSS survey year backing a measure. Not constant across the file:
    the 2025 release uses 2023 data for most measures but 2022 for the
    five collected every other year."""
    return int(MEASURE_META.loc[label, "year"])


def correlate(x_label, y_label, basis="crude", state=ALL_STATES):
    """Build the plotting frame for one X/Y measure pair.

    Returns (frame, stats). The frame has one row per county that has a
    value for BOTH measures, plus:
        predicted  -- y implied by the least-squares fit on x
        residual   -- actual y minus predicted, in percentage points.
                      Positive = the county's outcome is worse than its
                      driver level explains. That is the whole point of
                      this page.

    Raises ValueError on an invalid pair so the callback can show a
    message instead of a broken chart.
    """
    if not x_label or not y_label:
        raise ValueError("Pick a measure for both axes.")
    if x_label == y_label:
        raise ValueError(
            "The X and Y axes are the same measure — every county would "
            "sit on a perfect diagonal. Pick two different measures."
        )
    if basis not in BASIS_FRAMES:
        raise ValueError(f"Unknown basis {basis!r}.")

    frame = BASIS_FRAMES[basis]
    if state and state != ALL_STATES:
        frame = frame[frame["statedesc"] == state]

    out = frame[
        ["locationid", "locationname", "statedesc", "stateabbr", "totalpop18plus"]
    ].copy()
    out["x"] = frame[x_label].to_numpy()
    out["y"] = frame[y_label].to_numpy()

    # Loving County, TX (FIPS 48301) is suppressed by CDC for sample
    # size and is NaN on every measure. Dropping it here is expected,
    # not a data error -- see data/notes_on_data.md.
    out = out.dropna(subset=["x", "y"]).reset_index(drop=True)

    # Bubble area = adult population. Guard against a missing count
    # rather than letting Plotly choke on a NaN size.
    out["bubble"] = out["totalpop18plus"].fillna(
        out["totalpop18plus"].median() if len(out) else 0
    ).clip(lower=1)

    stats = {
        "n": len(out),
        "r": None,
        "slope": None,
        "intercept": None,
        "basis": basis,
        "x_label": x_label,
        "y_label": y_label,
        "state": state,
    }

    fittable = (
        len(out) >= MIN_COUNTIES_FOR_FIT
        and out["x"].std() > 0
        and out["y"].std() > 0
    )
    if fittable:
        slope, intercept = np.polyfit(out["x"], out["y"], 1)
        out["predicted"] = slope * out["x"] + intercept
        out["residual"] = out["y"] - out["predicted"]
        stats.update(
            r=float(np.corrcoef(out["x"], out["y"])[0, 1]),
            slope=float(slope),
            intercept=float(intercept),
        )
    else:
        # Too few counties (a single-county state filter) or a flat
        # measure: still plot the points, just without a fit.
        out["predicted"] = np.nan
        out["residual"] = 0.0

    return out, stats


def describe_strength(r):
    """Plain-English reading of a correlation, for the stat card.
    Deliberately conservative wording -- this is association, not cause."""
    if r is None or np.isnan(r):
        return "not enough counties to fit"
    direction = "positive" if r >= 0 else "negative"
    magnitude = abs(r)
    if magnitude >= 0.7:
        strength = "Strong"
    elif magnitude >= 0.4:
        strength = "Moderate"
    elif magnitude >= 0.2:
        strength = "Weak"
    else:
        strength = "Little to no"
    return f"{strength} {direction} association"


def worst_outlier(frame):
    """County whose outcome most exceeds what its driver level predicts.
    Returns None when there is nothing to rank."""
    if frame.empty or frame["residual"].abs().max() == 0:
        return None
    return frame.loc[frame["residual"].idxmax()]