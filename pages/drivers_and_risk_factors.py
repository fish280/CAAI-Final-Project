"""
Page 2 -- Drivers & Risk Factors.

The question this page answers: "Is a county's disease rate explained by
its risk factors and access gaps, or is something else going on there?"


Callbacks on this page: 5
  1. update_scatter    -- 5 inputs -> figure + 3 live stat cards + footnote
  2. swap_axes         -- flips X and Y
  3. edit_watchlist    -- pin (chart click), remove (pattern-matching), clear
  4. render_watchlist  -- store -> styled table
  5. download_watchlist-- store -> CSV file

AI ASSISTANCE:
  Used AI to help build this page's functionality and debug it, based on
  decisions made here first: which controls the page needed (driver/
  outcome dropdowns restricted by category, state filter, crude vs.
  age-adjusted toggle, a watchlist with CSV export), and the statistical
  approach for the "expected value" line -- a simple least-squares linear
  fit, with the gap defined as actual minus predicted, in percentage
  points.
  Specifics:
    - Prompted AI to draft the residual-coloring scatter approach and
      the county-outlier ranking
    - Prompted AI to build the pattern-matching remove-button callback
      for the watchlist, and the hover/click-to-pin behavior
    - Asked AI to debug a duplicate-decorator syntax error introduced
      while hand-editing the layout, and a merge conflict from
      untracked __pycache__ files
    - Asked AI to draft the plain-English measure-subtitle glossary
      (pulling CDC's own question wording) after finding the raw
      measure labels unclear to a first-time reader
  All AI-suggested code was reviewed, run against the real data, and
  edited before being added to the project.
  -- [Samuel]
"""

import dash
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from risk_prep import (
    ALL_STATES,
    BASIS_LABELS,
    MEASURE_OPTIONS,
    DRIVER_LABELS,
    OUTCOME_LABELS,
    STATE_OPTIONS,
    correlate,
    describe_strength,
    measure_subtitle,
    measure_year,
    worst_outlier,
)
from ui_notes import (
    correlation_caveats,
    crude_adjusted_note,
    diverging_legend,
    prevalence_note,
    readout,
    readout_cell,
)

# The diverging ramp, as a CSS gradient, so the HTML legend below the
# chart matches RESIDUAL_SCALE exactly.
RESIDUAL_GRADIENT = (
    "linear-gradient(to right, #1F7A63 0%, #E1F0EA 35%, "
    "#F5F6F1 50%, #F3E1DC 65%, #A8442E 100%)"
)

dash.register_page(
    __name__,
    path="/drivers_and_risk_factors",
    name="Drivers & Risk Factors",
    title="Drivers & Risk Factors",
)

# Defaults chosen to open on a real, legible story rather than an empty
# state: physical inactivity against diabetes, in Virginia.
DEFAULT_X = "Physical Inactivity"
DEFAULT_Y = "Diabetes"
DEFAULT_STATE = "Virginia"

# Diverging scale anchored to the site palette (styles.css). Teal ->
# neutral -> rust reads correctly under deuteranopia and protanopia
# because the two ends differ in lightness as well as hue.
RESIDUAL_SCALE = [
    [0.00, "#1F7A63"],
    [0.35, "#E1F0EA"],
    [0.50, "#F5F6F1"],
    [0.65, "#F3E1DC"],
    [1.00, "#A8442E"],
]

PLOT_BG = "#FBFAF6"
INK = "#1C2B27"
MUTED = "#5C6D67"
FONT_UI = "IBM Plex Sans, -apple-system, Segoe UI, sans-serif"


def _message_figure(text):
    """Empty-state figure. Used for an invalid pair or an empty filter,
    so the user gets an explanation instead of a blank rectangle."""
    fig = go.Figure()
    fig.add_annotation(
        text=text, showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
        font=dict(family=FONT_UI, size=15, color=MUTED),
    )
    fig.update_layout(
        height=560,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


def layout(**kwargs):
    return html.Div(
        className="page-wrap",
        children=[
            dcc.Store(id="rf-watchlist", data=[], storage_type="session"),
            dcc.Download(id="rf-download"),

            html.Div(
                className="page-header",
                children=[
                    html.H1("Is the outcome explained by its risk factors — or is something else going on?"),
                    html.P(
                        "Pick a risk factor and an outcome. Every county becomes "
                        "a dot, sized by adult population. The dashed line is "
                        "the selection's overall pattern — counties above it "
                        "have a worse outcome than the risk factor alone would predict.",
                        className="dek",
                    ),
                    prevalence_note(),
                ],
            ),

            # ---------------- Controls ----------------
            html.Div(
                className="panel",
                children=[
                    # Driver / swap / Outcome as one visual unit
                    html.Div(
                        className="axis-pair",
                        children=[
                            html.Div([
                                html.Label("Risk factor — horizontal axis",
                                           className="label", htmlFor="rf-x"),
                                dcc.Dropdown(
                                    id="rf-x",
                                    options = DRIVER_LABELS,
                                    value=DEFAULT_X, clearable=False,
                                ),
                                html.Div(id="rf-x-subtitle",
                                         className="measure-subtitle"),
                            ]),
                            html.Div(
                                className="axis-pair__swap",
                                children=[
                                    html.Button(
                                        "⇄",
                                        id="rf-swap",
                                        n_clicks=0,
                                        title="Swap axes",
                                        className="btn btn--secondary swap-btn",
                                    ),
                                ],
                            ),
                            html.Div([
                                html.Label("Outcome — vertical axis",
                                           className="label", htmlFor="rf-y"),
                                dcc.Dropdown(
                                    id="rf-y",
                                    options = OUTCOME_LABELS,
                                    value=DEFAULT_Y, clearable=False,
                                ),
                                html.Div(id="rf-y-subtitle",
                                         className="measure-subtitle"),
                            ]),
                        ],
                    ),
                    html.Div(
                        className="grid grid--3",
                        style={"marginTop": "1.25rem"},
                        children=[
                            html.Div([
                                html.Label("State", className="label",
                                           htmlFor="rf-state"),
                                dcc.Dropdown(
                                    id="rf-state", options=STATE_OPTIONS,
                                    value=DEFAULT_STATE, clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Span("Prevalence basis", className="label"),
                                dcc.RadioItems(
                                    id="rf-basis",
                                    options=[
                                        {"label": " Crude", "value": "crude"},
                                        {"label": " Age-adjusted",
                                         "value": "adjusted"},
                                    ],
                                    value="crude",
                                    inline=True,
                                    inputStyle={"marginRight": "0.35rem"},
                                    labelStyle={"marginRight": "1rem"},
                                    style={"marginTop": "0.5rem"},
                                ),
                                crude_adjusted_note(),
                            ]),
                            html.Div([
                                html.Span("Chart options", className="label"),
                                dcc.Checklist(
                                    id="rf-trend",
                                    options=[{"label": " Expected-value line",
                                              "value": "on"}],
                                    value=["on"],
                                    inputStyle={"marginRight": "0.35rem"},
                                    style={"marginTop": "0.6rem"},
                                ),
                            ]),
                        ],
                    ),
                ],
            ),

            # ---- Readout sits flush on top of the scatter, so the
            # ---- summary and the chart read as one instrument.
            readout([
                readout_cell(value_id="rf-stat-r", label_id="rf-stat-r-label",
                             label="Correlation"),
                readout_cell(value_id="rf-stat-outlier",
                             label_id="rf-stat-outlier-label",
                             label="Largest unexplained gap",
                             value_class="readout__value--risk"),
                readout_cell(value_id="rf-stat-n", label_id="rf-stat-n-label",
                             label="Counties plotted"),
            ], attached=True),

            # ---------------- Scatter ----------------
            html.Div(
                className="panel panel--attached",
                children=[
                    dcc.Graph(
                        id="rf-scatter",
                        config={"displayModeBar": False},
                        figure=_message_figure("Loading…"),
                    ),
                    # What the encodings mean, in words. Static -- none of
                    # it changes per selection, so no callback needed.
                    diverging_legend(
                        "Better than expected",
                        "Worse than expected",
                        RESIDUAL_GRADIENT,
                        items=[
                            ("dash", "Expected-value line — this selection's "
                                     "overall pattern"),
                            (None, "Bubble size = adult population, 18+"),
                            (None, "Click a county to pin it below"),
                        ],
                    ),
                    html.P(id="rf-note", className="readout__hint",
                           style={"marginTop": "0.75rem", "maxWidth": "68ch"}),
                ],
            ),

            # ---------------- Watchlist ----------------
            html.Div(
                className="panel",
                children=[
                    html.Div(
                        style={"display": "flex", "justifyContent": "space-between",
                               "alignItems": "flex-start", "gap": "1rem",
                               "flexWrap": "wrap"},
                        children=[
                            html.Div([
                                html.H4("Watchlist", className="panel__title",
                                        style={"marginBottom": "0.25rem"}),
                                html.Span(
                                    "Click any county on the chart to pin it here.",
                                    className="stat__label",
                                ),
                            ]),
                            html.Div(
                                style={"display": "flex", "gap": "0.5rem"},
                                children=[
                                    html.Button("Download CSV", id="rf-export",
                                                n_clicks=0,
                                                className="btn btn--primary"),
                                    html.Button("Clear all", id="rf-clear",
                                                n_clicks=0,
                                                className="btn btn--secondary"),
                                ],
                            ),
                        ],
                    ),
                    html.Div(id="rf-watchlist-table",
                             style={"marginTop": "1.25rem"}),
                ],
            ),

            # Limits to carry away -- last thing on the page, read after
            # the chart rather than standing in front of it.
            correlation_caveats(),
        ],
    )


# ====================================================================
# 1. Main chart + live stat cards
# ====================================================================
@callback(
    Output("rf-scatter", "figure"),
    Output("rf-stat-r", "children"),
    Output("rf-stat-r-label", "children"),
    Output("rf-stat-n", "children"),
    Output("rf-stat-n-label", "children"),
    Output("rf-stat-outlier", "children"),
    Output("rf-stat-outlier-label", "children"),
    Output("rf-note", "children"),
    Input("rf-x", "value"),
    Input("rf-y", "value"),
    Input("rf-state", "value"),
    Input("rf-basis", "value"),
    Input("rf-trend", "value"),
)
def update_scatter(x_label, y_label, state, basis, trend):
    try:
        frame, stats = correlate(x_label, y_label, basis=basis, state=state)
    except ValueError as err:
        blank = "—"
        return (_message_figure(str(err)), blank, "Correlation", blank,
                "Counties plotted", blank, "Largest unexplained gap", "")

    if frame.empty:
        msg = "No county in this selection reports both measures."
        return (_message_figure(msg), "—", "Correlation", "0",
                "Counties plotted", "—", "Largest unexplained gap", "")

    basis_word = BASIS_LABELS[basis]
    scope = "all states" if state == ALL_STATES else state

    fig = px.scatter(
        frame,
        x="x", y="y",
        size="bubble",
        color="residual",
        color_continuous_scale=RESIDUAL_SCALE,
        color_continuous_midpoint=0,
        size_max=30,
        custom_data=["locationid", "locationname", "statedesc",
                     "x", "y", "residual"],
    )

    hover = (
        "<b>%{customdata[1]}, %{customdata[2]}</b><br>"
        + f"{x_label}: " + "%{x:.1f}%<br>"
        + f"{y_label}: " + "%{y:.1f}%<br>"
        + "Gap vs. expected: %{customdata[5]:+.1f} pp"
        + "<extra>click to pin</extra>"
    )
    fig.update_traces(
        hovertemplate=hover,
        marker=dict(line=dict(width=0.5, color="rgba(28,43,39,0.30)"),
                    opacity=0.85),
    )

    if "on" in (trend or []) and stats["slope"] is not None:
        xs = np.array([frame["x"].min(), frame["x"].max()])
        fig.add_trace(go.Scatter(
            x=xs, y=stats["slope"] * xs + stats["intercept"],
            mode="lines", hoverinfo="skip", showlegend=False,
            line=dict(color=INK, width=1.4, dash="dash"),
        ))

    fig.update_layout(
        height=580,
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family=FONT_UI, color=INK, size=13),
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title=f"{x_label} — {basis_word} (%)",
        yaxis_title=f"{y_label} — {basis_word} (%)",
        # The HTML legend under the chart already explains the color, in
        # words rather than percentage points. A second numeric color bar
        # here would say the same thing worse, and eat chart width.
        coloraxis_showscale=False,
    )
    fig.update_xaxes(gridcolor="#E4E7E1", zeroline=False,
                     ticksuffix="%", showline=True, linecolor="#D8DCD6")
    fig.update_yaxes(gridcolor="#E4E7E1", zeroline=False,
                     ticksuffix="%", showline=True, linecolor="#D8DCD6")

    r = stats["r"]
    r_value = f"{r:+.2f}" if r is not None else "—"
    r_label = describe_strength(r)

    n_value = f"{stats['n']:,}"
    n_label = f"of {scope} · bubble size = adult population, 18+"

    top = worst_outlier(frame)
    if top is None:
        out_value, out_label = "—", "Not enough counties to rank"
    else:
        out_value = f"{top['residual']:+.1f} pp"
        out_label = (
            f"{top['locationname']}, {top['statedesc']} — worse than its "
            f"{x_label.lower()} predicts"
        )

    note = (
        f"{y_label} plotted against {x_label}, {basis_word}, {scope}. "
        f"BRFSS survey year: {measure_year(y_label)} for {y_label}, "
        f"{measure_year(x_label)} for {x_label}."
    )

    return (fig, r_value, r_label, n_value, n_label,
            out_value, out_label, note)

@callback(
    Output("rf-x-subtitle", "children"),
    Output("rf-y-subtitle", "children"),
    Input("rf-x", "value"),
    Input("rf-y", "value"),
)
def update_axis_subtitles(x_label, y_label):
    x_sub = measure_subtitle(x_label) if x_label else ""
    y_sub = measure_subtitle(y_label) if y_label else ""
    return x_sub, y_sub


# ====================================================================
# 2. Swap axes
# ====================================================================
@callback(
    Output("rf-x", "value"),
    Output("rf-y", "value"),
    Input("rf-swap", "n_clicks"),
    State("rf-x", "value"),
    State("rf-y", "value"),
    prevent_initial_call=True,
)
def swap_axes(_n, x_label, y_label):
    return y_label, x_label


# ====================================================================
# 3. Watchlist: pin / remove / clear
# ====================================================================
@callback(
    Output("rf-watchlist", "data"),
    Input("rf-scatter", "clickData"),
    Input("rf-clear", "n_clicks"),
    Input({"type": "rf-remove", "index": ALL}, "n_clicks"),
    State("rf-watchlist", "data"),
    State("rf-x", "value"),
    State("rf-y", "value"),
    State("rf-basis", "value"),
    prevent_initial_call=True,
)
def edit_watchlist(click_data, _clear, _removes, rows, x_label, y_label, basis):
    rows = rows or []
    trigger = ctx.triggered_id

    if trigger == "rf-clear":
        return []

    # Pattern-matching inputs also fire when the table re-renders and the
    # buttons are recreated with n_clicks=None. Only act on a real click.
    if isinstance(trigger, dict) and trigger.get("type") == "rf-remove":
        clicked = ctx.triggered[0]["value"]
        if not clicked:
            return no_update
        return [r for r in rows if r["fips"] != trigger["index"]]

    if trigger == "rf-scatter":
        if not click_data or not click_data.get("points"):
            return no_update
        cd = click_data["points"][0].get("customdata")
        if not cd:                       # the trendline trace carries none
            return no_update
        fips, county, state_name, x_val, y_val, resid = cd
        if any(r["fips"] == fips for r in rows):
            return no_update             # already pinned
        rows = rows + [{
            "fips": fips,
            "county": county,
            "state": state_name,
            "x_label": x_label,
            "y_label": y_label,
            "basis": basis,
            "x": round(float(x_val), 1),
            "y": round(float(y_val), 1),
            "gap": round(float(resid), 1),
        }]
        return rows

    return no_update


# ====================================================================
# 4. Render the watchlist table
# ====================================================================
@callback(
    Output("rf-watchlist-table", "children"),
    Input("rf-watchlist", "data"),
)
def render_watchlist(rows):
    if not rows:
        return html.Div(
            "No counties pinned yet.",
            className="chart-placeholder",
            style={"minHeight": "120px"},
        )

    def badge(gap):
        if gap >= 1.0:
            cls, word = "badge badge--high", "worse than expected"
        elif gap <= -1.0:
            cls, word = "badge badge--low", "better than expected"
        else:
            cls, word = "badge badge--mid", "as expected"
        return html.Span(f"{gap:+.1f} pp · {word}", className=cls)

    header = html.Thead(html.Tr([
        html.Th("County"), html.Th("State"), html.Th("Comparison"),
        html.Th("Driver"), html.Th("Outcome"), html.Th("Gap vs. expected"),
        html.Th(""),
    ]))

    body = html.Tbody([
        html.Tr([
            html.Td(r["county"]),
            html.Td(r["state"]),
            html.Td(f"{r['x_label']} → {r['y_label']}",
                    style={"color": MUTED}),
            html.Td(f"{r['x']}%", className="figure"),
            html.Td(f"{r['y']}%", className="figure"),
            html.Td(badge(r["gap"])),
            html.Td(html.Button(
                "✕",
                id={"type": "rf-remove", "index": r["fips"]},
                n_clicks=0,
                className="btn btn--secondary",
                style={"padding": "0.2rem 0.55rem", "lineHeight": 1},
                title=f"Remove {r['county']}",
            )),
        ], key=r["fips"])
        for r in rows
    ])

    return html.Table(
        [html.Caption(f"{len(rows)} county(ies) pinned"), header, body],
        className="data-table",
    )


# ====================================================================
# 5. Export the watchlist
# ====================================================================
@callback(
    Output("rf-download", "data"),
    Input("rf-export", "n_clicks"),
    State("rf-watchlist", "data"),
    prevent_initial_call=True,
)
def download_watchlist(_n, rows):
    if not rows:
        return no_update
    out = pd.DataFrame(rows).rename(columns={
        "fips": "county_fips", "x": "driver_value_pct",
        "y": "outcome_value_pct", "gap": "gap_vs_expected_pp",
        "x_label": "driver_measure", "y_label": "outcome_measure",
        "basis": "prevalence_basis",
    })
    return dcc.send_data_frame(out.to_csv, "watchlist.csv", index=False)

