"""
Page 3: Access & Social Determinants

THE QUESTION THIS PAGE ANSWERS:
  "Which counties have the biggest gaps in healthcare access and
  social needs, and how do those gaps connect to disease outcomes?"

WHAT'S ON THIS PAGE:
  - A sidebar ranking the 10 most vulnerable counties for whatever
    measure(s) are currently on the chart.
  - A measure dropdown (the "primary" measure always shown) plus an
    "also compare" checklist to add more measures from the same
    cluster, the chart opens with just one measure, and you add more.
  - A ranked view (top N counties, biggest gap first) or a two-county
    compare view, switchable with a toggle.
  - A search box to pin any specific county into the ranked view, even
    if it's outside the top N.
  - A chart-width slider, on top of the chart auto-widening as more
    measures are toggled on.

WHY THE CHART TITLE ISN'T INSIDE THE PLOTLY FIGURE:
  Plotly's built-in title and its legend both anchor to the top-left
  corner by default, and with a dynamic multi-line title they used to
  collide with the legend (that's the overlap you saw in the
  screenshot). The fix is simple: the title/subtitle are now plain
  Dash text sitting above the chart, and the figure itself has no
  title at all, so there's nothing left for the legend to collide
  with.
"""

"""
AI ASSISTANCE:
  Used AI to draft the initial version of this page's
  layout and callback code and for later iterative changes.
  Specifics:
    - feedback on how to add the sidebar ranking, measure selector + "also
      compare" checklist, chart-width slider, county search, two-
      county compare mode
    - asked Ai to draft the updated layout
      and callback code implementing those changes.
    - Asked AI to help fix a layout bug where the chart's
      title and legend overlapped.
    - Asked AI to help debug a stray code duplication
      between this file and access_prep.py.
  All AI-suggested code was reviewed, tested by running the app, and
  edited/approved by the team before being added to the project.
"""

import sys
from pathlib import Path

import dash
from dash import Input, Output, State, callback, dcc, html
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

from access_prep import (
    CLUSTERS,
    DEFAULT_STATE,
    LABEL_COLORS,
    MEASURES,
    SOCIAL_MISSING_STATES,
    STATE_OPTIONS,
    get_cluster_data,
    get_county_options,
    get_measure_options,
    get_state_summary,
    get_top_vulnerable_counties,
    get_total_counties,
)
from ui_notes import estimate_caveats, readout, readout_cell

dash.register_page(
    __name__,
    path="/access_and_social_determinants",
    name="Access & Social Determinants",
    title="Access & Social Determinants",
)

# ============================================================
# Visual constants
# ============================================================
PLOT_BG = "#FBFAF6"
INK = "#1C2B27"
MUTED = "#5C6D67"
FONT_UI = "IBM Plex Sans, -apple-system, Segoe UI, sans-serif"
FONT_DISPLAY = "Spectral, Georgia, serif"
GRID_COLOR = "#E4E7E1"

DEFAULT_CLUSTER = "access"
DEFAULT_MEASURE = CLUSTERS[DEFAULT_CLUSTER]["measures"][0]


def _stat(value_id, label_id, label_text, value_text="—"):
    return html.Div(
        className="stat",
        children=[
            html.Div(value_text, id=value_id, className="stat__value figure"),
            html.Div(label_text, id=label_id, className="stat__label"),
        ],
    )


def _message_figure(text):
    fig = go.Figure()
    fig.add_annotation(
        text=text, showarrow=False, xref="paper", yref="paper",
        x=0.5, y=0.5, font=dict(family=FONT_UI, size=15, color=MUTED),
    )
    fig.update_layout(
        height=460,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        paper_bgcolor=PLOT_BG, plot_bgcolor=PLOT_BG,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


def _compute_chart_width(n_counties, n_measures, scale_pct):
    """
    Auto-width: each county needs more horizontal room the more
    measures are toggled on (more bars per group). The slider then
    scales that automatic width up or down.
    """
    if n_counties <= 0:
        n_counties = 1
    per_group = 90 + 40 * max(0, n_measures - 1)
    base_width = max(650, n_counties * per_group)
    return int(base_width * scale_pct / 100)


def _build_bar_chart(melted, measure_codes, county_order):
    """
    Grouped bar chart. No title here on purpose — see the module
    docstring for why. Legend stays horizontal along the top, which
    is now safe because nothing else occupies that space.
    """
    measure_order = [MEASURES[c]["label"] for c in measure_codes]

    fig = px.bar(
        melted,
        x="locationname", y="value", color="measure",
        barmode="group",
        color_discrete_map=LABEL_COLORS,
        category_orders={"measure": measure_order, "locationname": county_order},
    )

    fig.update_traces(
        hovertemplate=(
            "<b>%{x}</b><br>%{fullData.name}: %{y:.1f}%<br>"
            "Higher = worse gap<extra></extra>"
        ),
        marker=dict(line=dict(width=0.5, color="rgba(28,43,39,0.20)")),
    )

    fig.update_layout(
        height=560,
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family=FONT_UI, color=INK, size=13),
        margin=dict(l=50, r=20, t=30, b=120),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.0,
            xanchor="left", x=0.0, font=dict(size=11),
        ),
        xaxis=dict(
            tickangle=-45, tickfont=dict(size=10),
            showline=True, linecolor="#D8DCD6", title="",
        ),
        yaxis=dict(
            ticksuffix="%", gridcolor=GRID_COLOR, zeroline=False,
            showline=True, linecolor="#D8DCD6",
            title="Percentage of adults", tickfont=dict(size=11),
        ),
        hovermode="closest",
    )
    return fig


def _build_coverage_note(state, cluster_key):
    """Trimmed down on purpose — no "counties with data" figure and
    no severity flag, per feedback. Just the two notes that actually
    change how you read the chart."""
    notes = []
    if cluster_key == "access":
        notes.append(html.Span(
            "'No annual checkup' is flipped from CDC's '% who got a "
            "checkup' so every bar reads the same direction: "
            "taller = bigger gap = worse.",
            className="stat__label",
            style={"display": "block", "marginBottom": "0.4rem"},
        ))
    if cluster_key == "social" and state in SOCIAL_MISSING_STATES:
        notes.append(html.Span(
            f"{state} did not administer the BRFSS social-needs survey "
            "module, so this cluster has no data here.",
            className="badge badge--high",
            style={"display": "inline-block", "marginBottom": "0.4rem"},
        ))
    
    return html.Div(notes, style={"marginTop": "0.75rem"})


def _build_sidebar(top_df):
    if top_df.empty:
        return html.Div(
            "No data for this selection.",
            className="chart-placeholder",
            style={"minHeight": "120px"},
        )
    items = [
        html.Li(f"{row.locationname} — {row.score:.1f}%")
        for row in top_df.itertuples()
    ]
    return html.Ol(items, className="top-counties-list")


# ============================================================
# PAGE LAYOUT
# ============================================================
def layout(**kwargs):
    return html.Div(
        className="page-wrap",
        children=[
            html.Div(
                className="page-header",
                children=[
                    html.H1("Access & Social Determinants"),
                    html.P(
                        "County-level gaps in healthcare access and social "
                        "needs. Taller bars = bigger gaps = worse outcomes.",
                        className="dek",
                    ),
                ],
            ),

            # ---- Two-column layout: sidebar + main content ----
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "260px minmax(0, 1fr)",
                    "gap": "1.25rem",
                    "alignItems": "start",
                },
                children=[

                    # ---- Sidebar: top 10 most vulnerable ----
                    html.Div(
                        className="panel",
                        children=[
                            html.H4("Top 10 most vulnerable counties",
                                    className="panel__title"),
                            html.Div(
                                "Ranked by the measure(s) shown on the chart.",
                                className="stat__label",
                                style={"marginBottom": "0.75rem"},
                            ),
                            html.Div(id="access-vulnerable-list"),
                        ],
                    ),

                    # ---- Main content ----
                    html.Div(children=[

                        # --- Controls panel ---
                        html.Div(
                            className="panel",
                            children=[
                                html.Div(
                                    className="grid grid--2",
                                    children=[
                                        html.Div([
                                            html.Label("State", className="label",
                                                       htmlFor="access-state"),
                                            dcc.Dropdown(
                                                id="access-state",
                                                options=STATE_OPTIONS,
                                                value=DEFAULT_STATE, clearable=False,
                                            ),
                                        ]),
                                        html.Div([
                                            html.Span("Measure cluster",
                                                      className="label"),
                                            dcc.RadioItems(
                                                id="access-cluster",
                                                options=[
                                                    {"label": " Access to Care",
                                                     "value": "access"},
                                                    {"label": " Social & Economic Strain",
                                                     "value": "social"},
                                                ],
                                                value=DEFAULT_CLUSTER,
                                                inline=True,
                                                inputStyle={"marginRight": "0.35rem"},
                                                labelStyle={"marginRight": "1rem"},
                                                style={"marginTop": "0.5rem"},
                                            ),
                                        ]),
                                    ],
                                ),
                                html.Div(
                                    className="grid grid--2",
                                    style={"marginTop": "1.25rem"},
                                    children=[
                                        html.Div([
                                            html.Label("Measure", className="label",
                                                       htmlFor="access-primary-measure"),
                                            dcc.Dropdown(
                                                id="access-primary-measure",
                                                options=get_measure_options(DEFAULT_CLUSTER),
                                                value=DEFAULT_MEASURE, clearable=False,
                                            ),
                                        ]),
                                        html.Div([
                                            html.Span("Also compare", className="label"),
                                            dcc.Checklist(
                                                id="access-compare-measures",
                                                options=get_measure_options(
                                                    DEFAULT_CLUSTER, exclude=DEFAULT_MEASURE),
                                                value=[],
                                                inputStyle={"marginRight": "0.35rem"},
                                                labelStyle={"display": "block",
                                                            "marginTop": "0.35rem"},
                                                style={"marginTop": "0.5rem"},
                                            ),
                                        ]),
                                    ],
                                ),
                                html.Div(
                                    className="grid grid--2",
                                    style={"marginTop": "1.25rem"},
                                    children=[
                                        html.Div([
                                            html.Span("View mode", className="label"),
                                            dcc.RadioItems(
                                                id="access-view-mode",
                                                options=[
                                                    {"label": " Ranked view", "value": "rank"},
                                                    {"label": " Compare two counties",
                                                     "value": "compare"},
                                                ],
                                                value="rank",
                                                inline=True,
                                                inputStyle={"marginRight": "0.35rem"},
                                                labelStyle={"marginRight": "1rem"},
                                                style={"marginTop": "0.5rem"},
                                            ),
                                        ]),
                                        html.Div([
                                            html.Span("Chart width", className="label"),
                                            dcc.Slider(
                                                id="access-width-scale",
                                                min=50, max=200, step=10, value=80,
                                                marks={50: "50%", 100: "100%",
                                                       150: "150%", 200: "200%"},
                                            ),
                                        ]),
                                    ],
                                ),

                                # --- Ranked-view-only controls ---
                                html.Div(
                                    id="access-topn-container",
                                    className="grid grid--2",
                                    style={"marginTop": "1.25rem"},
                                    children=[
                                        html.Div([
                                            html.Span("Counties shown", className="label"),
                                            dcc.RadioItems(
                                                id="access-top-n",
                                                options=[
                                                    {"label": " 10", "value": 10},
                                                    {"label": " 15", "value": 15},
                                                    {"label": " 20", "value": 20},
                                                ],
                                                value=10, inline=True,
                                                inputStyle={"marginRight": "0.35rem"},
                                                labelStyle={"marginRight": "0.75rem"},
                                                style={"marginTop": "0.5rem"},
                                            ),
                                        ]),
                                        html.Div(
                                            id="access-county-search-container",
                                            children=[
                                                html.Label("Find a county", className="label",
                                                           htmlFor="access-county-search"),
                                                dcc.Dropdown(
                                                    id="access-county-search",
                                                    options=get_county_options(DEFAULT_STATE),
                                                    value=None, clearable=True,
                                                    placeholder="Search for a county…",
                                                ),
                                            ],
                                        ),
                                    ],
                                ),

                                # --- Compare-mode-only controls ---
                                html.Div(
                                    id="access-compare-controls",
                                    className="grid grid--2",
                                    style={"marginTop": "1.25rem", "display": "none"},
                                    children=[
                                        html.Div([
                                            html.Label("County A", className="label",
                                                       htmlFor="access-compare-a"),
                                            dcc.Dropdown(
                                                id="access-compare-a",
                                                options=get_county_options(DEFAULT_STATE),
                                                clearable=False,
                                            ),
                                        ]),
                                        html.Div([
                                            html.Label("County B", className="label",
                                                       htmlFor="access-compare-b"),
                                            dcc.Dropdown(
                                                id="access-compare-b",
                                                options=get_county_options(DEFAULT_STATE),
                                                clearable=False,
                                            ),
                                        ]),
                                    ],
                                ),
                            ],
                        ),

                        # --- Readout, flush on top of the chart ---
                        readout([
                            readout_cell(value_id="access-stat-avg-value",
                                         label_id="access-stat-avg-label",
                                         label="Average gap"),
                            readout_cell(value_id="access-stat-worst-value",
                                         label_id="access-stat-worst-label",
                                         label="Biggest gap",
                                         value_class="readout__value--risk"),
                        ], attached=True),

                        # --- Chart panel ---
                        html.Div(
                            className="panel panel--attached",
                            children=[
                                html.H4(id="access-chart-title",
                                        className="panel__title",
                                        style={"marginBottom": "0.15rem"}),
                                html.Div(id="access-chart-subtitle",
                                         className="stat__label",
                                         style={"marginBottom": "1rem"}),
                                html.Div(
                                    style={"overflowX": "auto"},
                                    children=[
                                        dcc.Graph(
                                            id="access-bar-chart",
                                            config={"displayModeBar": False},
                                            figure=_message_figure("Loading…"),
                                        ),
                                    ],
                                ),
                                html.Div(id="access-coverage-note"),
                            ],
                        ),
                    ]),
                ],
            ),

            # Limits to carry away -- last thing on the page.
            estimate_caveats(),
        ],
    )


# ============================================================
# CALLBACK 1 — measure dropdown resets when cluster changes
# ============================================================
@callback(
    Output("access-primary-measure", "options"),
    Output("access-primary-measure", "value"),
    Input("access-cluster", "value"),
    State("access-primary-measure", "value"),
)
def update_primary_measure_options(cluster_key, current_measure):
    new_options = get_measure_options(cluster_key)
    new_codes = [o["value"] for o in new_options]
    value = current_measure if current_measure in new_codes else new_codes[0]
    return new_options, value


# ============================================================
# CALLBACK 2 — "also compare" checklist follows cluster + primary
# ============================================================
@callback(
    Output("access-compare-measures", "options"),
    Output("access-compare-measures", "value"),
    Input("access-cluster", "value"),
    Input("access-primary-measure", "value"),
    State("access-compare-measures", "value"),
)
def update_compare_options(cluster_key, primary_measure, current_checked):
    new_options = get_measure_options(cluster_key, exclude=primary_measure)
    new_codes = {o["value"] for o in new_options}
    # Keep whatever was already checked that's still valid; this
    # naturally clears out anything from the old cluster, and drops
    # the old primary if it just got re-selected as primary again.
    kept = [c for c in (current_checked or []) if c in new_codes]
    return new_options, kept


# ============================================================
# CALLBACK 3 — county dropdowns refresh when state changes
# ============================================================
@callback(
    Output("access-county-search", "options"),
    Output("access-county-search", "value"),
    Output("access-compare-a", "options"),
    Output("access-compare-a", "value"),
    Output("access-compare-b", "options"),
    Output("access-compare-b", "value"),
    Input("access-state", "value"),
)
def update_county_dropdowns(state):
    options = get_county_options(state)
    first = options[0]["value"] if len(options) > 0 else None
    second = options[1]["value"] if len(options) > 1 else first
    # Search box always resets (nothing pinned yet in a new state).
    return options, None, options, first, options, second


# ============================================================
# CALLBACK 4 — show/hide ranked-view vs compare-view controls
# ============================================================
@callback(
    Output("access-topn-container", "style"),
    Output("access-compare-controls", "style"),
    Input("access-view-mode", "value"),
)
def toggle_view_controls(view_mode):
    grid = {"display": "grid", "gridTemplateColumns": "1fr 1fr",
            "gap": "1.25rem", "marginTop": "1.25rem"}
    hidden = {"display": "none"}
    if view_mode == "compare":
        return hidden, grid
    return grid, hidden


# ============================================================
# CALLBACK 5 — main chart + sidebar + stat cards + note
# ============================================================
@callback(
    Output("access-bar-chart", "figure"),
    Output("access-chart-title", "children"),
    Output("access-chart-subtitle", "children"),
    Output("access-stat-avg-value", "children"),
    Output("access-stat-avg-label", "children"),
    Output("access-stat-worst-value", "children"),
    Output("access-stat-worst-label", "children"),
    Output("access-coverage-note", "children"),
    Output("access-vulnerable-list", "children"),
    Input("access-state", "value"),
    Input("access-cluster", "value"),
    Input("access-primary-measure", "value"),
    Input("access-compare-measures", "value"),
    Input("access-view-mode", "value"),
    Input("access-top-n", "value"),
    Input("access-county-search", "value"),
    Input("access-compare-a", "value"),
    Input("access-compare-b", "value"),
    Input("access-width-scale", "value"),
)
def update_view(state, cluster_key, primary_measure, compare_checked,
                 view_mode, top_n, searched_county,
                 county_a, county_b, width_scale):

    cluster = CLUSTERS[cluster_key]
    checked = set(compare_checked or [])
    # Primary measure always comes first; order otherwise follows the
    # cluster's fixed measure order, not click order, so it's stable.
    measure_codes = [c for c in cluster["measures"]
                      if c == primary_measure or c in checked]
    if primary_measure not in measure_codes:
        measure_codes = [primary_measure] + measure_codes

    if view_mode == "compare":
        compare_ids = [c for c in (county_a, county_b) if c]
        if len(compare_ids) < 2:
            fig = _message_figure("Pick two counties to compare.")
            melted, raw_df = None, None
        else:
            melted, raw_df = get_cluster_data(
                cluster_key=cluster_key, measure_codes=measure_codes,
                compare_counties=compare_ids,
            )
    else:
        melted, raw_df = get_cluster_data(
            state=state, cluster_key=cluster_key, measure_codes=measure_codes,
            top_n=top_n, pinned_county=searched_county,
        )

    scope = "all states" if state == "ALL" else state
    measure_label = MEASURES[primary_measure]["label"]

    if melted is None or melted.empty:
        if melted is None:
            fig = _message_figure("Pick two counties to compare.")
        elif cluster_key == "social" and state in SOCIAL_MISSING_STATES:
            fig = _message_figure(f"No social-needs data reported for {state}.")
        else:
            fig = _message_figure("No data available for this selection.")
        title_text = f"{cluster['label']}"
        subtitle_text = ""
        n_shown = 0
    else:
        county_order = raw_df["locationname"].tolist()
        fig = _build_bar_chart(melted, measure_codes, county_order)
        n_shown = len(raw_df)
        chart_width = _compute_chart_width(n_shown, len(measure_codes), width_scale)
        fig.update_layout(width=chart_width, autosize=False)

        if view_mode == "compare":
            title_text = f"{cluster['label']} — comparing 2 counties"
            subtitle_text = ", ".join(MEASURES[c]["label"] for c in measure_codes)
        else:
            title_text = f"{cluster['label']} — {scope}"
            subtitle_text = (
                f"Sorted by {measure_label}, biggest gap first"
                if len(measure_codes) == 1
                else f"Sorted by {measure_label}, biggest gap first "
                     f"(comparing {len(measure_codes)} measures)"
            )

    # --- Stat cards ---
    summary = get_state_summary(
        state if state else DEFAULT_STATE, cluster_key, primary_measure
    )
    avg_value = f"{summary['avg']:.1f}%" if summary['n_counties'] > 0 else "—"
    avg_label = f"Average {measure_label}"
    if summary['n_counties'] > 0:
        worst_value = summary['worst_county']
        worst_label = f"{summary['worst_val']:.1f}% — worst in {scope}"
    else:
        worst_value, worst_label = "—", "No data"

    # --- Coverage note ---
    coverage_note = _build_coverage_note(state, cluster_key)

    # --- Sidebar: top 10 most vulnerable, for the current filters ---
    top_vuln = get_top_vulnerable_counties(
        state if state else DEFAULT_STATE, [primary_measure], n=10
    )
    sidebar_children = _build_sidebar(top_vuln)

    return (
        fig, title_text, subtitle_text,
        avg_value, avg_label, worst_value, worst_label,
        coverage_note, sidebar_children,
    )
