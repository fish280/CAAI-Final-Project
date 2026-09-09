import dash
from dash import dcc, html, Input, Output
import pandas as pd

from risk_prep import WIDE_CRUDE, MEASURE_META, STATE_OPTIONS, ALL_STATES
from ui_notes import estimate_caveats

dash.register_page(__name__, path = "/at_risk_counties", name = "At Risk Counties")

DISEASE_LABELS = list(MEASURE_META[MEASURE_META["category"] == "Health Outcomes"].index)
RISK_FACTOR_LABELS = list(MEASURE_META[MEASURE_META["category"] != "Health Outcomes"].index)

STATE_ONLY_OPTIONS = [opt for opt in STATE_OPTIONS if opt["value"] != ALL_STATES]

# Open on Virginia to match the Drivers page rather than on Alabama,
# which is only first because the list is alphabetical.
_STATE_VALUES = [opt["value"] for opt in STATE_ONLY_OPTIONS]
DEFAULT_STATE = (
    "Virginia" if "Virginia" in _STATE_VALUES
    else (_STATE_VALUES[0] if _STATE_VALUES else None)
)

# Open on diabetes rather than whatever sorts first alphabetically ("All
# Teeth Lost"), matching the other pages. Falls back to the first label
# if a future CDC release renames this one.
DEFAULT_DISEASE = (
    "Diabetes" if "Diabetes" in DISEASE_LABELS
    else (DISEASE_LABELS[0] if DISEASE_LABELS else None)
)

TOP_N_COUNTIES = 5
TOP_N_TAGS = 3

def layout(**kwargs):
    return html.Div(
        className="page-wrap",
        children=[
            html.Div(
                className="page-header",
                children=[
                    html.H1("At Risk Counties"),
                    html.P(
                        "The five highest-rate counties for a selected disease, "
                        "each tagged with the risk factors driving furthest "
                        "above its state's average.",
                        className="dek",
                    ),
                ],
            ),
            html.Div(
                className="panel",
                children=[
                    html.Div(
                        className="grid grid--2",
                        children=[
                            html.Div(
                                children=[
                                    html.Label("State", className="label", htmlFor="arc-state"),
                                    dcc.Dropdown(
                                        id="arc-state",
                                        options=STATE_ONLY_OPTIONS,
                                        value=DEFAULT_STATE,
                                        clearable=False,
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Disease / condition",
                                        className="label",
                                        htmlFor="arc-disease",
                                    ),
                                    dcc.Dropdown(
                                        id="arc-disease",
                                        options=[{"label": d, "value": d} for d in DISEASE_LABELS],
                                        value=DEFAULT_DISEASE,
                                        clearable=False,
                                    ),
                                ]
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="arc-leaderboard", className="panel"),

            # This page ranks counties, so the small-county uncertainty
            # point matters here more than anywhere else in the app.
            estimate_caveats(),
        ],
    )

def _tier_class(pct_above):
    """How far above the state average this risk factor sits, as a tier.
    Colors live in styles.css (.tag--high/mid/low) so they stay in step
    with the badges and readouts on the other pages."""
    if pct_above >= 50:
        return "tag tag--high"
    if pct_above >= 20:
        return "tag tag--mid"
    return "tag tag--low"

@dash.callback(
    Output("arc-leaderboard", "children"),
    Input("arc-state", "value"),
    Input("arc-disease", "value"),
)

def update_leaderboard(selected_state, selected_disease):
    if not selected_state or not selected_disease:
        return html.Div("Select a state and a disease.", className="label")

    state_frame = WIDE_CRUDE[WIDE_CRUDE["statedesc"] == selected_state]

    if state_frame.empty or selected_disease not in state_frame.columns:
        return html.Div(
            f"No data available for {selected_disease} in {selected_state}.",
            className="label",
        )
    risk_cols = [c for c in RISK_FACTOR_LABELS if c in state_frame.columns]
    state_avgs = state_frame[risk_cols].mean()

    top5 = (
        state_frame[["locationid", "locationname", selected_disease] + risk_cols]
        .dropna(subset=[selected_disease])
        .nlargest(TOP_N_COUNTIES, selected_disease)
    )
    rows = []
    for rank, (_, county) in enumerate(top5.iterrows(), start=1):
        # Percent above the state average, per risk factor. Skip
        # factors with a near-zero state average to avoid a
        # divide-by-near-zero dominating the ranking.
        deviations = []
        for col in risk_cols:
            county_val = county[col]
            avg_val = state_avgs[col]
            if pd.isna(county_val) or pd.isna(avg_val) or avg_val <= 0.01:
                continue
            pct_above = (county_val - avg_val) / avg_val * 100
            deviations.append((col, county_val, pct_above))

        top_tags = sorted(deviations, key=lambda t: t[2], reverse=True)[:TOP_N_TAGS]

        tags = [
            html.Span(f"{label} {value:.1f}%", className=_tier_class(pct_above))
            for label, value, pct_above in top_tags
        ]

        rows.append(
            html.Div(
                className="leaderboard-row",
                children=[
                    html.Div(str(rank), className="leaderboard-rank"),
                    html.Div(
                        className="leaderboard-main",
                        children=[
                            html.Div(county["locationname"], className="leaderboard-county"),
                            html.Div(tags, className="leaderboard-tags"),
                        ],
                    ),
                    html.Div(f"{county[selected_disease]:.1f}%", className="leaderboard-value"),
                ],
            )
        )

    return rows





