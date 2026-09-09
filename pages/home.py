"""
Overview page — choropleth of disease prevalence by Virginia county,
with a disease dropdown and a raw / age-adjusted toggle.

Lives in pages/, so Dash's built-in Pages feature (dash.register_page)
picks it up automatically as long as your main app.py has
`use_pages=True` and renders `dash.page_container`.
"""

import json
from pathlib import Path

import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import pandas as pd

from data_prep import (df_raw, df_aa, DISEASES, FIPS, COUNTY, STATE,
                       ALL_STATES, STATE_OPTIONS, SHORT_LABELS)
from ui_notes import (
    crude_adjusted_note,
    estimate_caveats,
    legend_row,
    prevalence_note,
    readout,
    readout_cell,
)

dash.register_page(__name__, path="/", name="Public Health Overview")

# --------------------------------------------------------------------
# County boundaries (FIPS-keyed geojson), loaded once at import time and
# cached at module level for every callback to reuse.
#
# This file is committed to the repo on purpose. It used to be fetched
# from raw.githubusercontent.com at import time, which meant a 3 MB
# download on every cold start -- and because that ran at module level,
# a slow or failed request took the whole app down rather than just this
# page. Reading it from disk removes the network from startup entirely.
#
# Source: https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json
# Re-download that URL into data/ if county boundaries ever need updating.
# --------------------------------------------------------------------
GEOJSON_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "geojson-counties-fips.json"
)

with open(GEOJSON_PATH, encoding="utf-8") as resp:
    _counties_geojson = json.load(resp)


# Colors pulled from styles.css so the map matches the rest of the site
# (risk-low -> risk-mid -> risk-high).
RISK_SCALE = [
    [0.0, "#eaf5ef"],
    [0.20, "#c7e4d5"],
    [0.40, "#96ccb0"],
    [0.60, "#5dae87"],
    [0.80, "#2e8b62"],
    [1.0, "#0f5c3d"],
]

# Open on diabetes rather than whatever sorts first alphabetically ("All
# Teeth Lost"), so the page lands on a measure people recognise and the
# orientation figure reads as a real headline. Falls back to the first
# measure if a future CDC release renames this one.
DEFAULT_DISEASE = (
    "Diagnosed diabetes among adults"
    if "Diagnosed diabetes among adults" in DISEASES else DISEASES[0]
)


# The four pages, restated as the question each one answers. "Drivers &
# Risk Factors" and "Access & Social Determinants" are CDC vocabulary a
# first-time visitor does not have; these are the plain-English version.
DOORS = [
    {
        "n": "01 · YOU ARE HERE",
        "q": "Where is it most common?",
        "body": "See every county at once on the map, or narrow to one state.",
        "go": "Below on this page ↓",
        "href": None,
    },
    {
        "n": "02",
        "q": "Is the rate explained by risk factors?",
        "body": "Plot a risk factor against an outcome and find the counties "
                "that break the pattern.",
        "go": "Drivers & Risk Factors →",
        "href": "/drivers_and_risk_factors",
    },
    {
        "n": "03",
        "q": "Who can't get care, and why?",
        "body": "Insurance and checkup gaps beside food, housing and "
                "transport strain.",
        "go": "Access & Social Determinants →",
        "href": "/access_and_social_determinants",
    },
    {
        "n": "04",
        "q": "Who should get help first?",
        "body": "The five worst counties for a condition, each tagged with "
                "what's driving it.",
        "go": "At-Risk Counties →",
        "href": "/at_risk_counties",
    },
]


def _door(spec):
    """One route card. The card for this page is inert; the others link."""
    inner = [
        html.Div(spec["n"], className="door__n"),
        html.Div(spec["q"], className="door__q"),
        html.P(spec["body"], className="door__body"),
        html.Div(spec["go"], className="door__go"),
    ]
    if spec["href"] is None:
        return html.Div(className="door door--here", children=inner)
    return dcc.Link(className="door", href=spec["href"], children=inner)


def layout(**kwargs):
    return html.Div(
        className="page-wrap",
        children=[
            # ---------------- Orientation band ----------------
            html.Div(
                className="welcome",
                children=[
                    html.Div(
                        className="welcome__row",
                        children=[
                            html.Div([
                                html.Div("County health, one county at a time",
                                         className="welcome__kicker"),
                                html.H1(
                                    "National averages hide the places that "
                                    "need help.",
                                    className="welcome__title",
                                ),
                                html.P(
                                    "This atlas breaks 40 CDC health measures "
                                    "down to all 3,144 U.S. counties, so a "
                                    "health department deciding where to send "
                                    "limited funding can see the geography "
                                    "instead of a single national figure.",
                                    className="welcome__lede",
                                ),
                            ]),
                            # The national figure beside the county spread it
                            # hides -- filled by update_snapshot() so it stays
                            # true for whichever measure is selected.
                            html.Div(
                                className="snapshot",
                                children=[
                                    html.Div(id="snapshot-figure",
                                             className="snapshot__fig",
                                             children="—"),
                                    html.Div(id="snapshot-caption",
                                             className="snapshot__cap"),
                                    html.Div(id="snapshot-spread",
                                             className="snapshot__sub"),
                                ],
                            ),
                        ],
                    ),
                ],
            ),

            html.Div(className="doors", children=[_door(d) for d in DOORS]),

            # ---------------- The tool ----------------
            html.Div(
                className="toolhead",
                children=[
                    html.H2("Where a condition is most common"),
                    html.Span(
                        "Each figure is the share of adults affected, not a "
                        "case count",
                        className="toolhead__note",
                    ),
                ],
            ),
            html.Div(prevalence_note(), style={"marginBottom": "1rem"}),

            # ---------------- Controls ----------------
            html.Div(
                className="panel",
                children=[
                    html.Div(
                        className="grid grid--3",
                        children=[
                            html.Div(
                                children=[
                                    html.Label(
                                        "Disease / condition",
                                        className="label",
                                        htmlFor="disease-dropdown",
                                    ),
                                    dcc.Dropdown(
                                        id="disease-dropdown",
                                        options=[
                                            {"label": SHORT_LABELS.get(d, d),
                                             "value": d}
                                            for d in DISEASES
                                        ],
                                        value=DEFAULT_DISEASE,
                                        clearable=False,
                                    ),
                                    # CDC's own full wording, which is where
                                    # the denominator hides -- "High
                                    # Cholesterol" is only among adults ever
                                    # screened, not all adults.
                                    html.Div(id="disease-subtitle",
                                             className="measure-subtitle"),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "State",
                                        className="label",
                                        htmlFor="state-dropdown",
                                    ),
                                    dcc.Dropdown(
                                        id="state-dropdown",
                                        options=STATE_OPTIONS,
                                        value=ALL_STATES,
                                        clearable=False,
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Span("Statistic type", className="label"),
                                    dcc.Checklist(
                                        id="adjustment-toggle",
                                        options=[
                                            {
                                                "label": " Show age-adjusted rate",
                                                "value": "aa",
                                            }
                                        ],
                                        value=[],  # unchecked = raw/crude
                                        style={"marginTop": "0.6rem"},
                                    ),
                                    crude_adjusted_note(),
                                ]
                            ),
                        ],
                    ),
                ],
            ),

            # ---- Readout sits flush on top of the map: one instrument,
            # ---- not two stacked boxes (see .readout--attached).
            readout([
                readout_cell(
                    value_id="US-total-value",
                    label="Population-weighted %",
                    extra=html.Div(id="US-total-delta", className="readout__hint"),
                ),
                readout_cell(
                    value_id="county-rank-value",
                    label="Selected county",
                    value_class="readout__value--name",
                    extra=html.Div(id="county-rank-delta", className="readout__hint"),
                ),
                html.Div(
                    className="readout__cell",
                    children=[
                        html.Div("Most affected counties", className="readout__label"),
                        html.Div(id="top-counties-scope", className="readout__hint"),
                        html.Ol(id="top-counties-list", className="top-counties-list"),
                    ],
                ),
            ], attached=True),

            # ---------------- Map ----------------
            html.Div(
                className="panel panel--attached",
                children=[
                    dcc.Graph(
                        id="choropleth-map",
                        config={"displayModeBar": False, "scrollZoom": False},
                        style = {"width": "100%", "height": "650px"},
                    ),
                    # Kentucky and Pennsylvania report no 2023 measures in
                    # this CDC release, so they render unshaded on every
                    # 2023-based measure. Say so rather than leave a hole.
                    legend_row([
                        ("#0f5c3d", "Darker = a larger share of adults affected"),
                        ("#EDEBE4", "Unshaded — no data reported for this measure"),
                        (None, "Click any county to read it in the panel above"),
                    ]),
                ],
            ),

            # Limits to carry away -- last thing on the page, read after
            # the map rather than standing in front of it.
            estimate_caveats(),
        ],
    )


@dash.callback(
    Output("snapshot-figure", "children"),
    Output("snapshot-caption", "children"),
    Output("snapshot-spread", "children"),
    Input("disease-dropdown", "value"),
    Input("adjustment-toggle", "value"),
)
def update_snapshot(selected_disease, adjustment_value):
    """The orientation figure: the national rate beside the county spread
    it hides. Always national, whatever the state filter says -- this is
    context for the whole app, not a readout of the current selection.
    Recomputed per measure so it never states a number that has stopped
    being true.
    """
    if not selected_disease:
        return "—", "", ""

    use_age_adjusted = "aa" in (adjustment_value or [])
    source_df = df_aa if use_age_adjusted else df_raw

    valid = source_df[[selected_disease, "totalpopulation"]].dropna()
    if valid.empty:
        return "—", "No data reported for this measure", ""

    weighted = (
        (valid[selected_disease] * valid["totalpopulation"]).sum()
        / valid["totalpopulation"].sum()
    )
    low = valid[selected_disease].min()
    high = valid[selected_disease].max()

    # Deliberately does NOT say "of U.S. adults": some measures have a
    # narrower denominator (High Cholesterol counts only adults ever
    # screened, All Teeth Lost only 65+). The measure's own wording is
    # shown under the dropdown, where it states its own denominator.
    caption = "U.S. rate, weighted by county population"
    if use_age_adjusted:
        caption = "U.S. rate, age-adjusted and population-weighted"

    spread = (
        f"County rates run from {low:.1f}% to {high:.1f}% — a spread that "
        f"one national number erases."
    )
    return f"{weighted:.1f}%", caption, spread


@dash.callback(
    Output("disease-subtitle", "children"),
    Input("disease-dropdown", "value"),
)
def update_disease_subtitle(selected_disease):
    """CDC's full wording for the selected measure. The dropdown shows the
    short label; this is where the real definition and its denominator
    live. Same pattern as the axis subtitles on the Drivers page."""
    if not selected_disease:
        return ""
    return selected_disease[:1].upper() + selected_disease[1:]


@dash.callback(
    Output("choropleth-map", "figure"),
    Input("disease-dropdown", "value"),
    Input("adjustment-toggle", "value"),
    Input("state-dropdown", "value"),
)
def update_map(selected_disease, adjustment_value, selected_state):
    use_age_adjusted = "aa" in adjustment_value
    source_df = df_aa if use_age_adjusted else df_raw
    stat_label = (
        "Age-adjusted prevalence (%)" if use_age_adjusted else "Crude prevalence (%)"
    )

    is_national = not selected_state or selected_state == ALL_STATES
    if not is_national:
        source_df = source_df[source_df[STATE] == selected_state]

    fig = px.choropleth(
        source_df,
        geojson=_counties_geojson,
        locations=FIPS,
        color=selected_disease,
        color_continuous_scale=RISK_SCALE,
        labels={selected_disease: stat_label},
        hover_name=COUNTY,
        hover_data = {
            FIPS: False,
            selected_disease: ":.1f"
        },
    )
    
    fig.update_traces(marker_line_width=0.2, 
    marker_line_color="rgba(255,255,255,0.4)")

    if is_national:
        fig.update_geos(
            scope = "usa",
            projection_type = "albers usa",
            visible = False,
            showsubunits = True,
            subunitcolor = "#1C2B27",
            subunitwidth = 1,
        )
    else:
        fig.update_geos(
            fitbounds="locations",
            visible=False,
            showsubunits = True,
            subunitcolor = "#1C2B27",
            subunitwidth = 1,
        )

    scope_title = "National" if is_national else selected_state
    fig.update_layout(
        margin={"r": 0, "t": 60, "l": 0, "b": 0},
        font_family="IBM Plex Sans, -apple-system, sans-serif",
        # Say which direction is worse in words -- a bare numeric scale
        # leaves a first-time reader guessing whether dark is good or bad.
        coloraxis_colorbar=dict(
            title=dict(text="% of adults<br>affected<br>&nbsp;", side="top"),
            ticksuffix="%",
            thickness=12,
            len=0.62,
            outlinewidth=0,
        ),
        title=f"{selected_disease} — {stat_label} — {scope_title}",
        title_font_family="Spectral, Georgia, serif",
        height = 650,
        autosize = True,
        dragmode=False,
    )
    return fig
@dash.callback(
    Output("US-total-value", "children"),
    Output("US-total-delta", "children"),
    Output("county-rank-value", "children"),
    Output("county-rank-delta", "children"),
    Output("top-counties-scope", "children"),
    Output("top-counties-list", "children"),
    Input("disease-dropdown", "value"),
    Input("adjustment-toggle", "value"),
    Input("state-dropdown", "value"),
    Input("choropleth-map", "clickData"),
)
def update_stat_cards(selected_disease, adjustment_value, selected_state, clickData):
    use_age_adjusted = "aa" in adjustment_value
    source_df = df_aa if use_age_adjusted else df_raw

    is_national = not selected_state or selected_state == ALL_STATES
    if not is_national:
        source_df = source_df[source_df[STATE] == selected_state]
    scope_label = "National" if is_national else selected_state

    POPULATION = "totalpopulation"
    valid = source_df[[selected_disease, POPULATION]].dropna()
    weighted_avg = (valid[selected_disease] * valid[POPULATION]).sum() / valid[POPULATION].sum()
    state_avg_value = f"{weighted_avg:.1f}%"
    state_avg_delta = f"{scope_label} · population-weighted"

    if clickData is not None:
        selected_fips = clickData["points"][0]["location"]
        county_row = source_df[source_df[FIPS] == selected_fips]
    else:
            county_row = pd.DataFrame()

    if not county_row.empty:
        selected_county = county_row[COUNTY].iloc[0]
        selected_state_name = county_row[STATE].iloc[0]

        ranks = source_df[selected_disease].rank(ascending = False, method = "min")
        county_rank = int(ranks.loc[county_row.index[0]])
        total_counties = source_df[selected_disease].notna().sum()

        county_rank_value = f"{selected_county}, {selected_state_name}"
        county_rank_delta = f"Rank {county_rank} of {total_counties} ({scope_label.lower()})"
    else:
         county_rank_value = "-"
         county_rank_delta = "Click a county on the map"

    top3 = source_df.nlargest(3, selected_disease)
    top_counties_children = [
        html.Li(f"{row[COUNTY]}, {row[STATE]} - {row[selected_disease]:.1f}%")
        for _, row in top3.iterrows()
    ]

    return (
        state_avg_value,
        state_avg_delta,
        county_rank_value,
        county_rank_delta,
        scope_label,
        top_counties_children
    )