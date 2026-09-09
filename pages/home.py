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
import pandas as pd

from data_prep import df_raw, df_aa, DISEASES, FIPS, COUNTY, STATE, ALL_STATES, STATE_OPTIONS
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
                    _stat_card("VA-total", "Population-weighted %"),
                    _stat_card("county-rank", "Selected County Rank"),
                    html.Div(
                         className = "panel stat",
                         children = [
                              html.Div("Most affected counties", className = "stat__label"),
                              html.Div(id="top-counties-scope", className="stat__delta"),
                              html.Ol(id = "top-counties-list", className = "top-counties-list"),
                         ],
                    ),
                ],
            ),

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
                        id="choropleth-map",
                        config={"displayModeBar": False, "scrollZoom": False},
                        style = {"width": "100%", "height": "650px"},
                    ),
                ],
            ),
        ],
    )


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
        coloraxis_colorbar_title=stat_label,
        title=f"{selected_disease} — {stat_label} — {scope_title}",
        title_font_family="Spectral, Georgia, serif",
        height = 650,
        autosize = True,
        dragmode=False,
    )
    return fig
@dash.callback(
    Output("VA-total-value", "children"),
    Output("VA-total-delta", "children"),
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