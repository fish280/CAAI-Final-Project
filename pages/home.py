"""
Overview page — choropleth of disease prevalence by Virginia county,
with a disease dropdown and a raw / age-adjusted toggle.

Lives in pages/, so Dash's built-in Pages feature (dash.register_page)
picks it up automatically as long as your main app.py has
`use_pages=True` and renders `dash.page_container`.
"""

import json
import urllib.request

import dash
from dash import dcc, html, Input, Output
import plotly.express as px

from data_prep import va_raw_health, va_aa_health, DISEASES, FIPS, COUNTY

dash.register_page(__name__, path="/", name="Public Health Overview")

# --------------------------------------------------------------------
# Virginia county boundaries (FIPS-keyed geojson), fetched once at
# import time and cached at module level for every callback to reuse.
# --------------------------------------------------------------------
GEOJSON_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/"
    "geojson-counties-fips.json"
)

with urllib.request.urlopen(GEOJSON_URL) as resp:
    _counties_geojson = json.load(resp)

# Virginia's state FIPS prefix is "51" — trim to just VA counties.
_counties_geojson["features"] = [
    feat for feat in _counties_geojson["features"]
    if feat["properties"]["STATE"] == "51"
]

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

def _stat_card(card_id, label):
    return html.Div(
        className = "panel stat", 
        children = [
            html.Div(id=f"{card_id}-value", className = "stat__value", children = "-"), 
            html.Div(label, className = "stat__label"), 
            html.Div(id = f"{card_id}-delta", className = "stat__delta"),
        ],
    )


def layout(**kwargs):
    return html.Div(
        className="page-wrap",
        children=[
            html.Div(
                className="page-header",
                children=[
                    html.H1("Public Health Overview"),
                    html.P(
                        "County-level disease prevalence, raw or age-adjusted.",
                        className="dek",
                    ),
                ],
            ),

            html.Div(
                className = "grid grid--3",
                children = [
                    _stat_card("VA-total", "Virginia %"), 
                    _stat_card("gross-number", "Total Cases"), 
                    _stat_card("county-rank", "Top Counties")
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
                                    html.Label(
                                        "Disease / condition",
                                        className="label",
                                        htmlFor="disease-dropdown",
                                    ),
                                    dcc.Dropdown(
                                        id="disease-dropdown",
                                        options=[
                                            {"label": d, "value": d}
                                            for d in DISEASES
                                        ],
                                        value=DISEASES[0],
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
                                ]
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="panel",
                children=[
                    dcc.Graph(
                        id="choropleth-map", config={"displayModeBar": False}
                    ),
                ],
            ),
        ],
    )


@dash.callback(
    Output("choropleth-map", "figure"),
    Input("disease-dropdown", "value"),
    Input("adjustment-toggle", "value"),
)
def update_map(selected_disease, adjustment_value):
    use_age_adjusted = "aa" in adjustment_value
    source_df = va_aa_health if use_age_adjusted else va_raw_health
    stat_label = (
        "Age-adjusted prevalence (%)" if use_age_adjusted else "Crude prevalence (%)"
    )

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
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 0, "t": 10, "l": 0, "b": 0},
        font_family="IBM Plex Sans, -apple-system, sans-serif",
        coloraxis_colorbar_title=stat_label,
        title=f"{selected_disease} — {stat_label}",
        title_font_family="Spectral, Georgia, serif",
    )
    return fig

@dash.callback(
    Output("state-avg-value", "children"),
    Output("state-avg-delta", "children"),
    Output("county-rank-value", "children"),
    Output("county-rank-delta", "children"),
    Output("card-three-value", "children"),
    Output("card-three-delta", "children"),
    Input("disease-dropdown", "value"),
    Input("adjustment-toggle", "value"),
)
def update_stat_cards(selected_disease, adjustment_value):
    use_age_adjusted = "aa" in adjustment_value
    source_df = va_aa_health if use_age_adjusted else va_raw_health

    #todo: state_avg = source_df[selected_disease].mean()
    state_avg_value = "—"
    state_avg_delta = ""

    #todo: county rank needs a selected county from somewhere (a new
    # dropdown, a click on the map, etc.) — not wired up yet.
    county_rank_value = "—"
    county_rank_delta = ""

    #todo: pick a stat for card three and fill this in.
    card_three_value = "—"
    card_three_delta = ""

    return (
        state_avg_value,
        state_avg_delta,
        county_rank_value,
        county_rank_delta,
        card_three_value,
        card_three_delta,
    )