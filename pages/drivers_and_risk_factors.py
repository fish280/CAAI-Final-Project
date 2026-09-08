"""
Page 2 -- Drivers & Risk Factors.

The question this page answers: "Is a county's disease rate explained by
its risk factors and access gaps, or is something else going on there?"

The user picks any two of the 40 CDC PLACES measures for the X and Y
axes, and every county in the selection is plotted. A least-squares line
shows the expected relationship; each county is then colored by how far
it sits ABOVE or BELOW that line. Counties in deep rust are the ones
whose outcome is worse than their drivers predict -- the counties that
would be invisible in a flat ranking.

Clicking any bubble pins that county to a watchlist below the chart,
which can be exported to CSV.

Callbacks on this page: 5
  1. update_scatter    -- 5 inputs -> figure + 3 live stat cards + footnote
  2. swap_axes         -- flips X and Y
  3. edit_watchlist    -- pin (chart click), remove (pattern-matching), clear
  4. render_watchlist  -- store -> styled table
  5. download_watchlist-- store -> CSV file

AI assistance: used Claude Code to draft the residual-coloring approach,
the pattern-matching remove-button callback, and the hover template;
reviewed and edited all of it, and verified the correlation figures
against the raw CSV by hand. -- SAMUEL: edit to match what you did.
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
    STATE_OPTIONS,
    correlate,
    describe_strength,
    measure_year,
    worst_outlier,
)

from data_prep import DISEASES, risk_factors

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


def _stat(value_id, label_id, label_text, value_text="—"):
    """One card in the live stat strip."""
    return html.Div(
        className="stat",
        children=[
            html.Div(value_text, id=value_id, className="stat__value figure"),
            html.Div(label_text, id=label_id, className="stat__label"),
        ],
    )


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
                    html.H1("Drivers & Risk Factors"),
                    html.P(
                        "Plot any risk factor, social need, or access gap "
                        "against any health outcome. Counties are colored by "
                        "how far their outcome sits above or below what the "
                        "driver alone would predict.",
                        className="dek",
                    ),
                ],
            ),

            # ---------------- Controls ----------------
            html.Div(
                className="panel",
                children=[
                    html.Div(
                        className="grid grid--2",
                        children=[
                            html.Div([
                                html.Label("Driver — horizontal axis",
                                           className="label", htmlFor="rf-x"),
                                dcc.Dropdown(
                                    id="rf-x",
                                    options = [
                                        {"label":r, "value": r}
                                        for r in risk_factors
                                    ],
                                    value=DEFAULT_X, clearable=False,
                                ),
                            ]),
                            html.Div([
                                html.Label("Outcome — vertical axis",
                                           className="label", htmlFor="rf-y"),
                                dcc.Dropdown(
                                    id="rf-y",
                                    options = [
                                        {"label":d, "value":d}
                                        for d in DISEASES
                                    ],
                                    value=DEFAULT_Y, clearable=False,
                                ),
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
                            ]),
                            html.Div([
                                html.Span("Chart options", className="label"),
                                html.Div(
                                    style={"display": "flex", "gap": "0.75rem",
                                           "alignItems": "center",
                                           "marginTop": "0.5rem"},
                                    children=[
                                        dcc.Checklist(
                                            id="rf-trend",
                                            options=[{"label": " Expected-value line",
                                                      "value": "on"}],
                                            value=["on"],
                                            inputStyle={"marginRight": "0.35rem"},
                                        ),
                                        html.Button(
                                            "Swap axes", id="rf-swap",
                                            n_clicks=0,
                                            className="btn btn--secondary",
                                        ),
                                    ],
                                ),
                            ]),
                        ],
                    ),
                ],
            ),

            # ---------------- Live stat strip ----------------
            html.Div(
                className="panel",
                children=[
                    html.Div(
                        className="grid grid--3",
                        children=[
                            _stat("rf-stat-r", "rf-stat-r-label", "Correlation"),
                            _stat("rf-stat-n", "rf-stat-n-label",
                                  "Counties plotted"),
                            _stat("rf-stat-outlier", "rf-stat-outlier-label",
                                  "Largest unexplained gap"),
                        ],
                    ),
                ],
            ),

            # ---------------- Scatter ----------------
            html.Div(
                className="panel",
                children=[
                    dcc.Graph(
                        id="rf-scatter",
                        config={"displayModeBar": False},
                        figure=_message_figure("Loading…"),
                    ),
                    html.P(id="rf-note", className="stat__label",
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
    # correlate() raises on an invalid pair (same measure on both axes,
    # nothing selected) -- surface the reason instead of a broken chart.
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

    # Expected-value line: what Y the fit predicts at each X.
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
        coloraxis_colorbar=dict(
            title=dict(text="Gap vs.<br>expected<br>(pp)", font=dict(size=11)),
            thickness=12, len=0.6, outlinewidth=0,
        ),
    )
    fig.update_xaxes(gridcolor="#E4E7E1", zeroline=False,
                     ticksuffix="%", showline=True, linecolor="#D8DCD6")
    fig.update_yaxes(gridcolor="#E4E7E1", zeroline=False,
                     ticksuffix="%", showline=True, linecolor="#D8DCD6")

    # ---- stat cards ----
    r = stats["r"]
    r_value = f"{r:+.2f}" if r is not None else "—"
    r_label = describe_strength(r)

    n_value = f"{stats['n']:,}"
    n_label = f"of {scope}, bubble size = adult population"

    top = worst_outlier(frame)
    if top is None:
        out_value, out_label = "—", "Not enough counties to rank"
    else:
        out_value = f"{top['locationname']}"
        out_label = (
            f"{top['statedesc']} — {top['residual']:+.1f} pp above the "
            f"{y_label.lower()} rate its {x_label.lower()} predicts"
        )

    note = (
        f"{y_label} plotted against {x_label}, {basis_word}, {scope}. "
        f"BRFSS survey year: {measure_year(y_label)} for {y_label}, "
        f"{measure_year(x_label)} for {x_label}. "
        "Color shows each county's distance from the dashed expected-value "
        "line in percentage points — rust means the outcome is worse than "
        "the driver alone predicts, teal means better. Association only; "
        "these are model-based small-area estimates, not causal evidence."
    )

    return (fig, r_value, r_label, n_value, n_label,
            out_value, out_label, note)


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