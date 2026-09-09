"""
Page 3 — Access & Social Determinants

THE QUESTION THIS PAGE ANSWERS:
  "Which counties have the biggest gaps in healthcare access and
  social needs, and how do those gaps connect to the disease
  outcomes shown on the map?"

WHAT THE USER SEES:
  A grouped bar chart where each group of bars represents one county.
  The bars within each group show different access or social-need
  measures (e.g., uninsured rate, food insecurity rate). A toggle
  switches between two thematic clusters — "Access to Care" (insurance
  + checkup) and "Social & Economic Strain" (food, housing, transport,
  loneliness, etc.) — so the chart never tries to show all 9 measures
  at once.

WHY THE CLUSTER TOGGLE EXISTS:
  Nine bars per county across 15–20 counties is 135–180 bars —
  unreadable. Two thematic clusters keep each view legible and match
  how a program officer actually thinks: "Can people get to a doctor?"
  vs. "Are their basic needs met?"

THE INTERACTIONS:
  1. State dropdown — filters from national (top N) to one state's
     counties. Defaults to Virginia (matching the rest of the
     dashboard's scope).
  2. Cluster toggle — switch between Access to Care and Social &
     Economic Strain.
  3. Sort by dropdown — which measure to rank counties by.
  4. Sort order toggle — biggest gap first (descending) vs.
     alphabetical.
  5. Top-N toggle — show 10, 15, or 20 counties (uses the space freed
     by not having a year slider, since all data is from 2023 only).
  6. Hover — exact percentage + county name + measure name.
  7. Click a bar → jump to Page 1's map for that county (cross-page
     linked navigation via URL query parameter).

WHY CHECKUP IS FLIPPED:
  CDC measures CHECKUP as "% who got a checkup" (higher = better).
  Every other measure here is "higher = worse." We flip CHECKUP to
  100 − value so the entire chart reads consistently: taller bar =
  bigger gap = worse. The flip happens in access_prep.py at import
  time, so this page never sees the unflipped value.

CROSS-PAGE LINK (the "genuine complexity" piece):
  When a bar is clicked, the app navigates to Page 1 (the choropleth
  map) with the county's FIPS code as a URL query parameter
  (?locationid=51001). This lets a program officer go from "this
  county has the state's worst transportation barrier rate" directly
  to "show me how that maps against its diabetes prevalence" —
  connecting Page 3's access story to Page 1's disease story.

  See the comment in the jump_to_map callback below for exactly what
  Lauren needs to add to Page 1 to receive this link.

DESIGN NOTES:
  - Colors, fonts, and CSS classes come from styles.css so this page
    looks like the rest of the site (teal-green buttons, Spectral
    headings, IBM Plex Sans body, flat panels with no shadows).
  - The chart uses the same color palette as the risk scale in
    styles.css (rust = direct barriers, amber = preventive gaps,
    teal = social/emotional measures).
  - Empty states (no data for a state's social needs) show a clear
    message instead of a blank chart.

AI ASSISTANCE: Used to draft the grouped bar chart approach, the
cross-page URL-parameter navigation pattern, and the flagging
threshold logic. Reviewed and edited all of it. — DAVID
"""

import dash
import sys
from pathlib import Path
from dash import Input, Output, State, callback, dcc, html, no_update
import plotly.express as px
import plotly.graph_objects as go

# WHY THIS IS HERE:
#   Dash's Pages feature imports each page file from the pages/ folder,
#   but Python only searches pages/ and the standard library paths —
#   NOT the project root where access_prep.py lives. This line adds the
#   project root (the parent of the pages/ folder) to Python's module
#   search path so 'from access_prep import ...' can find the file.
#   Same fix Samuel and Lauren likely need for risk_prep / data_prep.
sys.path.insert(0, str(Path(__file__).parent.parent))

from access_prep import (
    CLUSTERS,
    DEFAULT_STATE,
    LABEL_COLORS,
    MEASURES,
    SOCIAL_MISSING_STATES,
    STATE_OPTIONS,
    get_cluster_data,
    get_measure_options,
    get_state_summary,
    get_total_counties,
)

# ============================================================
# Register this page with Dash's multi-page router.
# ============================================================
# WHY: Dash's Pages feature (use_pages=True in app.py) auto-discovers
# files in the pages/ directory. register_page tells Dash the URL
# path, the display name (shown in the nav bar), and the page title
# (shown in the browser tab). As long as app.py has use_pages=True
# and renders dash.page_container, this page appears automatically.
dash.register_page(
    __name__,
    path="/access_and_social_determinants",
    name="Access & Social Determinants",
    title="Access & Social Determinants",
)

# ============================================================
# Visual constants — pulled from styles.css so the chart matches.
# ============================================================
# WHY: Plotly figures don't automatically inherit CSS variables. We
# hard-code the same hex values here so the chart's background, text
# color, and font family match the panels, headings, and body text
# on the rest of the page. If styles.css changes, update these too.
PLOT_BG = "#FBFAF6"   # --panel: slightly lifted panel surface
INK = "#1C2B27"       # --ink: primary text color
MUTED = "#5C6D67"     # --muted: secondary text color
FONT_UI = "IBM Plex Sans, -apple-system, Segoe UI, sans-serif"
FONT_DISPLAY = "Spectral, Georgia, serif"
GRID_COLOR = "#E4E7E1"  # subtle gridline color, slightly lighter than --line


# ============================================================
# Helper: build a stat card (matches the .stat CSS class).
# ============================================================
# WHY: The three stat cards above the chart (average gap, counties
# with data, worst county) all have the same structure — a big
# number and a small label. This helper avoids repeating the same
# HTML structure three times. Same pattern Samuel uses on Page 2.
def _stat(value_id, label_id, label_text, value_text="—"):
    """One card in the stat strip. value_id/label_id let callbacks
    update the content dynamically."""
    return html.Div(
        className="stat",
        children=[
            html.Div(value_text, id=value_id, className="stat__value figure"),
            html.Div(label_text, id=label_id, className="stat__label"),
        ],
    )


# ============================================================
# Helper: empty-state figure (when there's no data to chart).
# ============================================================
# WHY: If a state has no social-needs data (e.g., Texas), showing a
# blank white rectangle is confusing. This function creates a
# Plotly figure with just a centered text message — same approach
# Samuel uses on Page 2 for invalid measure pairs.
def _message_figure(text):
    """A figure that shows a centered text message instead of a
    chart. Used when the selection has no data."""
    fig = go.Figure()
    fig.add_annotation(
        text=text,
        showarrow=False,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        font=dict(family=FONT_UI, size=15, color=MUTED),
    )
    fig.update_layout(
        height=550,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


# ============================================================
# Helper: build the grouped bar chart from melted data.
# ============================================================
def _build_bar_chart(melted, cluster_key, state, sort_measure, sort_order):
    """
    Create a Plotly grouped bar chart from the melted DataFrame.

    WHY GROUPED BARS:
      A grouped bar chart puts one cluster of bars per county on the
      x-axis, with each bar in the group representing a different
      measure. This lets the user compare measures within a county
      (e.g., "is this county's food insecurity worse than its housing
      insecurity?") and across counties (e.g., "which county has the
      highest uninsured rate?") in a single glance.

    WHY custom_data:
      We attach the county's locationid (FIPS code) to each bar as
      custom data. When the user clicks a bar, the clickData callback
      reads this FIPS and navigates to Page 1's map. Without
      custom_data, the click handler would only know the bar's x/y
      values (county name and percentage), not the FIPS needed for
      the cross-page link.
    """
    cluster = CLUSTERS[cluster_key]

    # The order of measures within each county group should match the
    # cluster definition (ACCESS2 first, then CHECKUP, etc.) so the
    # bars always appear in the same left-to-right order.
    measure_order = [MEASURES[c]["label"] for c in cluster["measures"]]

    # The x-axis order should match the sort order we already applied
    # in get_cluster_data — Plotly Express might reorder by default,
    # so we enforce it explicitly.
    county_order = melted["locationname"].unique().tolist()

    fig = px.bar(
        melted,
        x="locationname",
        y="value",
        color="measure",                  # color by human-readable label
        barmode="group",                  # bars side by side, not stacked
        color_discrete_map=LABEL_COLORS,  # fixed color per measure
        custom_data=["locationid"],       # FIPS carried to clickData
        category_orders={
            "measure": measure_order,
            "locationname": county_order,
        },
    )

    # --- Hover tooltip ---
    # WHY: The default Plotly hover shows raw column names. We
    # customize it to show the county name (bold), the measure name,
    # and the exact percentage — the three things a user needs to
    # read a bar. The "<extra></extra>" suppresses the secondary
    # trace-name box that Plotly shows by default.
    fig.update_traces(
        hovertemplate=(
            "<b>%{x}</b><br>"
            "%{fullData.name}: %{y:.1f}%<br>"
            "Higher = worse gap"
            "<extra></extra>"
        ),
        # Thin border around each bar for visual separation when bars
        # are narrow (7 measures × 15 counties = 105 bars).
        marker=dict(line=dict(width=0.5, color="rgba(28,43,39,0.20)")),
    )

    # --- Chart title ---
    # WHY: A dynamic title tells the user exactly what they're looking
    # at without reading the dropdowns: "Access to Care — Virginia"
    # or "Social & Economic Strain — National (Top 15)".
    scope = "National" if state == "ALL" else state
    measure_label = MEASURES[sort_measure]["label"]
    fig_title = f"{cluster['label']} — {scope}"

    # Subtitle reflects the actual sort order, not a hardcoded phrase.
    if sort_order == "alpha":
        fig_subtitle = "Sorted alphabetically by county name"
    else:
        fig_subtitle = f"Sorted by {measure_label} (biggest gap first)"

    fig.update_layout(
        height=600,
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(family=FONT_UI, color=INK, size=13),
        margin=dict(l=50, r=20, t=70, b=120),
        title=dict(
            text=f"<b>{fig_title}</b><br>"
                 f"<span style='font-size:12px;color:{MUTED}'>"
                 f"{fig_subtitle}</span>",
            font=dict(family=FONT_DISPLAY, size=18, color=INK),
            x=0.01,  # left-align the title
        ),
        # Legend at the top, horizontal — saves vertical space and
        # reads naturally left-to-right matching the bar order.
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0,
            font=dict(size=11),
        ),
        xaxis=dict(
            tickangle=-45,         # rotate county names for readability
            tickfont=dict(size=10),
            showline=True,
            linecolor="#D8DCD6",
            title="",
        ),
        yaxis=dict(
            ticksuffix="%",
            gridcolor=GRID_COLOR,
            zeroline=False,
            showline=True,
            linecolor="#D8DCD6",
            title="Percentage of adults",
            tickfont=dict(size=11),
        ),
        # Remove the Plotly mode bar (zoom, pan, etc.) — this chart
        # is read-only; interaction is through the dropdowns and
        # bar clicks, not Plotly's built-in tools.
        hovermode="closest",
    )

    return fig


# ============================================================
# Helper: build the data-coverage note below the chart.
# ============================================================
def _build_coverage_note(state, cluster_key, n_counties_with_data,
                         n_counties_shown, n_flagged):
    """
    Build a dynamic note explaining data coverage for the current
    selection.

    WHY: Three things can surprise a user looking at this chart:
    1. CHECKUP is flipped — without a note, a user who knows the CDC
       data might wonder why the checkup numbers look wrong.
    2. Some counties are missing — switching from Access (2,957
       counties) to Social (2,299 counties) can shrink the list.
    3. Eleven states have NO social-needs data at all — a blank
       chart needs an explanation, not silence.

    This function returns a Div with one or more Spans, each
    addressing a relevant concern for the current selection.

    Parameters:
    -----------
    n_counties_with_data : int
        How many counties in this state have data for the sort measure
        (from get_state_summary, NOT limited to top-N).
    n_counties_shown : int
        How many counties are actually displayed in the chart (top-N).
    n_flagged : int
        How many counties in this selection are flagged as severe.
    """
    notes = []

    # --- Note about the CHECKUP flip (only relevant for Access cluster) ---
    if cluster_key == "access":
        notes.append(html.Span(
            "CHECKUP is shown as '% without annual checkup' (flipped from "
            "CDC's '% who got a checkup') so every bar reads the same "
            "direction: taller = bigger gap = worse.",
            className="stat__label",
            style={"display": "block", "marginBottom": "0.4rem"},
        ))

    # --- Note about county coverage ---
    # WHY: Distinguish between "counties with data" (the full state's
    # data availability) and "counties shown" (the top-N subset in the
    # chart). A state might have 133 counties with data but only show
    # 15 in the chart — the user should know both numbers.
    if state == "ALL":
        notes.append(html.Span(
            f"Showing the top {n_counties_shown} counties nationally by the "
            "selected sort measure. Pick a state to see all its counties.",
            className="stat__label",
            style={"display": "block", "marginBottom": "0.4rem"},
        ))
    else:
        n_total = get_total_counties(state)
        if n_counties_with_data < n_total:
            notes.append(html.Span(
                f"Data covers {n_counties_with_data} of {n_total} counties "
                f"in {state}. Chart shows the top {n_counties_shown}.",
                className="stat__label",
                style={"display": "block", "marginBottom": "0.4rem"},
            ))
        else:
            notes.append(html.Span(
                f"All {n_total} counties in {state} have data. "
                f"Chart shows the top {n_counties_shown}.",
                className="stat__label",
                style={"display": "block", "marginBottom": "0.4rem"},
            ))

    # --- Note about states with no social-needs data ---
    if cluster_key == "social" and state in SOCIAL_MISSING_STATES:
        notes.append(html.Span(
            f"{state} did not administer the BRFSS social-needs survey "
            "module. No data is available for the Social & Economic Strain "
            "cluster here — try switching to Access to Care.",
            className="badge badge--high",
            style={"display": "inline-block", "marginBottom": "0.4rem"},
        ))

    # --- Flagged counties indicator ---
    # WHY: The flag count reflects the FULL state (or national), not just
    # the displayed top-N. This is deliberate — a program officer wants to
    # know the total scope of severe need, not just what fits on screen.
    if n_flagged > 0:
        scope = f"in {state}" if state != "ALL" else "nationally"
        notes.append(html.Span(
            f"{n_flagged} county(ies) flagged as severely lacking "
            f"(90th percentile or worse nationally on at least one measure "
            f"in this cluster) — {scope}.",
            className="badge badge--mid",
            style={"display": "inline-block", "marginBottom": "0.4rem"},
        ))

    # --- Cross-page hint ---
    notes.append(html.Span(
        "Click any bar to see that county on the disease prevalence map "
        "(Page 1).",
        className="stat__label",
        style={"display": "block", "marginTop": "0.3rem",
               "fontStyle": "italic"},
    ))

    return html.Div(notes, style={"marginTop": "0.75rem"})


# ============================================================
# PAGE LAYOUT
# ============================================================
def layout(**kwargs):
    """
    Build the page's HTML structure.

    The layout is divided into four sections, each wrapped in a
    .panel (the flat, border-only container from styles.css):

    1. Page header — title + one-line description
    2. Controls — state dropdown, cluster toggle, sort options, top-N
    3. Stat cards — three live-updating summary numbers
    4. Chart — the grouped bar chart + coverage note

    A hidden dcc.Location at the top handles cross-page navigation
    when a bar is clicked (see jump_to_map callback).
    """
    return html.Div(
        className="page-wrap",
        children=[
            # --- Hidden navigation component ---
            # WHY: dcc.Location is invisible — it has no visual
            # output. We include it here so the jump_to_map callback
            # can update its pathname/search to navigate to Page 1.
            # refresh=True causes a full page reload, ensuring Page 1
            # starts fresh and can read the locationid from the URL.
            dcc.Location(id="access-nav-url", refresh=True),

            # --- Page header ---
            html.Div(
                className="page-header",
                children=[
                    html.H1("Access & Social Determinants"),
                    html.P(
                        "County-level gaps in healthcare access and social "
                        "needs. Taller bars = bigger gaps = worse outcomes. "
                        "Click any bar to jump to that county on the disease "
                        "prevalence map.",
                        className="dek",
                    ),
                ],
            ),

            # --- Controls panel ---
            # WHY A SEPARATE PANEL: Grouping all controls in one panel
            # visually separates "what you can change" from "what the
            # data shows" (the chart below). The grid layout puts
            # related controls side by side: state + cluster on the
            # first row, sort options on the second row.
            html.Div(
                className="panel",
                children=[
                    # Row 1: State + Cluster toggle
                    html.Div(
                        className="grid grid--2",
                        children=[
                            # State dropdown
                            html.Div([
                                html.Label(
                                    "State",
                                    className="label",
                                    htmlFor="access-state",
                                ),
                                dcc.Dropdown(
                                    id="access-state",
                                    options=STATE_OPTIONS,
                                    value=DEFAULT_STATE,  # Virginia
                                    clearable=False,
                                ),
                            ]),
                            # Cluster toggle
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
                                    value="access",  # default to Access
                                    inline=True,
                                    inputStyle={"marginRight": "0.35rem"},
                                    labelStyle={"marginRight": "1rem"},
                                    style={"marginTop": "0.5rem"},
                                ),
                            ]),
                        ],
                    ),

                    # Row 2: Sort measure + sort order + top-N
                    # WHY THREE CONTROLS: The sort measure dropdown
                    # lets the user pick which measure to rank counties
                    # by (e.g., "sort by food insecurity"). The sort
                    # order toggle switches between "worst first" and
                    # "alphabetical." The top-N toggle controls how
                    # many counties appear — this replaces the year
                    # slider that other pages have, since all data
                    # here is from 2023 only.
                    html.Div(
                        className="grid grid--3",
                        style={"marginTop": "1.25rem"},
                        children=[
                            # Sort measure dropdown
                            html.Div([
                                html.Label(
                                    "Sort by",
                                    className="label",
                                    htmlFor="access-sort-measure",
                                ),
                                dcc.Dropdown(
                                    id="access-sort-measure",
                                    options=get_measure_options("access"),
                                    value="ACCESS2",
                                    clearable=False,
                                ),
                            ]),
                            # Sort order toggle
                            html.Div([
                                html.Span("Sort order", className="label"),
                                dcc.RadioItems(
                                    id="access-sort-order",
                                    options=[
                                        {"label": " Biggest gap first",
                                         "value": "gap"},
                                        {"label": " Alphabetical",
                                         "value": "alpha"},
                                    ],
                                    value="gap",  # default: worst first
                                    inline=True,
                                    inputStyle={"marginRight": "0.35rem"},
                                    labelStyle={"marginRight": "1rem"},
                                    style={"marginTop": "0.5rem"},
                                ),
                            ]),
                            # Top-N toggle
                            html.Div([
                                html.Span("Counties shown", className="label"),
                                dcc.RadioItems(
                                    id="access-top-n",
                                    options=[
                                        {"label": " 10", "value": 10},
                                        {"label": " 15", "value": 15},
                                        {"label": " 20", "value": 20},
                                    ],
                                    value=15,  # default: 15
                                    inline=True,
                                    inputStyle={"marginRight": "0.35rem"},
                                    labelStyle={"marginRight": "0.75rem"},
                                    style={"marginTop": "0.5rem"},
                                ),
                            ]),
                        ],
                    ),
                ],
            ),

            # --- Stat cards ---
            # WHY: Three quick-read numbers above the chart give the
            # user context before they even look at the bars: "What's
            # the average? How many counties have data? Which one is
            # worst?" These update live with every dropdown change.
            html.Div(
                className="panel",
                children=[
                    html.Div(
                        className="grid grid--3",
                        children=[
                            _stat(
                                "access-stat-avg-value",
                                "access-stat-avg-label",
                                "Average gap",
                            ),
                            _stat(
                                "access-stat-count-value",
                                "access-stat-count-label",
                                "Counties with data",
                            ),
                            _stat(
                                "access-stat-worst-value",
                                "access-stat-worst-label",
                                "Biggest gap",
                            ),
                        ],
                    ),
                ],
            ),

            # --- Chart panel ---
            # WHY: The chart and its coverage note live in one panel
            # so they're visually grouped — the note explains what
            # the chart shows and what's missing.
            html.Div(
                className="panel",
                children=[
                    dcc.Graph(
                        id="access-bar-chart",
                        config={"displayModeBar": False},
                        figure=_message_figure("Loading…"),
                    ),
                    # The coverage note is updated by the same
                    # callback that updates the chart, so it always
                    # matches the current selection.
                    html.Div(id="access-coverage-note"),
                ],
            ),
        ],
    )


# ============================================================
# CALLBACK 1: Update sort-measure dropdown when cluster changes.
# ============================================================
# WHY THIS IS A SEPARATE CALLBACK:
#   When the user switches clusters (e.g., Access → Social), the
#   sort-measure dropdown needs new options (only measures in the
#   new cluster) and possibly a new value (if the old selection
#   isn't valid for the new cluster). This callback handles ONLY
#   that dropdown update, so there's no circular dependency between
#   the sort-measure value being an input and an output of the same
#   callback.
#
#   The main chart callback (below) depends on the sort-measure value
#   as an input. When this callback changes the sort-measure value,
#   the chart callback fires again with the corrected value. There
#   may be a brief double-update, but the end result is correct and
#   Dash handles the sequencing automatically.
@callback(
    Output("access-sort-measure", "options"),
    Output("access-sort-measure", "value"),
    Input("access-cluster", "value"),
    State("access-sort-measure", "value"),
)
def update_sort_options(cluster_key, current_sort_measure):
    """
    Update the sort-measure dropdown's options and value when the
    cluster changes. If the current sort measure is still valid for
    the new cluster, keep it; otherwise reset to the new cluster's
    first measure.
    """
    new_options = get_measure_options(cluster_key)
    new_codes = [o["value"] for o in new_options]

    if current_sort_measure in new_codes:
        # Current selection is still valid — keep it
        return new_options, current_sort_measure
    else:
        # Current selection isn't in the new cluster — reset to default
        return new_options, new_codes[0]


# ============================================================
# CALLBACK 2: Main chart + stat cards + coverage note.
# ============================================================
# WHY ONE BIG CALLBACK INSTEAD OF SEPARATE ONES:
#   Five inputs (state, cluster, sort measure, sort order, top-N)
#   all affect the same outputs (chart, stat cards, coverage note).
#   Combining them into one callback means Dash only recomputes
#   once per user interaction, not five times. It also ensures the
#   chart, stat cards, and note are always in sync — you never see
#   a chart for Virginia with stat cards for Texas.
#
#   The sort-measure dropdown is updated by Callback 1 (above), so
#   its value is always valid for the current cluster by the time
#   this callback runs. If the cluster just changed and the sort
#   measure hasn't been corrected yet, get_cluster_data falls back
#   to the cluster's first measure automatically.
@callback(
    # --- Chart ---
    Output("access-bar-chart", "figure"),
    # --- Stat cards (value + label for each of 3 cards) ---
    Output("access-stat-avg-value", "children"),
    Output("access-stat-avg-label", "children"),
    Output("access-stat-count-value", "children"),
    Output("access-stat-count-label", "children"),
    Output("access-stat-worst-value", "children"),
    Output("access-stat-worst-label", "children"),
    # --- Coverage note ---
    Output("access-coverage-note", "children"),
    # --- Inputs ---
    Input("access-state", "value"),
    Input("access-cluster", "value"),
    Input("access-sort-measure", "value"),
    Input("access-sort-order", "value"),
    Input("access-top-n", "value"),
)
def update_view(state, cluster_key, sort_measure, sort_order, top_n):
    """
    Rebuild the chart, stat cards, and coverage note whenever any
    control changes.

    This is the heart of the page — it translates the user's filter
    selections into a visual response. Every dropdown or toggle on
    the page feeds into this one function.
    """

    # --- Step 1: Get the filtered, sorted, melted data ---
    # get_cluster_data handles the sort_measure being invalid for the
    # current cluster (falls back to the cluster's first measure).
    melted, raw_df, flags = get_cluster_data(
        state=state,
        cluster_key=cluster_key,
        sort_measure=sort_measure,
        sort_order=sort_order,
        top_n=top_n,
    )

    # --- Step 2: Build the chart (or empty-state message) ---
    if melted.empty:
        # No data — show a contextual message instead of a blank chart.
        if cluster_key == "social" and state in SOCIAL_MISSING_STATES:
            msg = (f"No social-needs data reported for {state}.\n"
                   "The BRFSS SOCLNEED module was not administered here.\n"
                   "Try 'Access to Care' or a different state.")
        else:
            msg = "No data available for this selection."
        fig = _message_figure(msg)
    else:
        fig = _build_bar_chart(melted, cluster_key, state,
                               sort_measure, sort_order)

    # --- Step 3: Compute summary statistics for the stat cards ---
    summary = get_state_summary(state, cluster_key, sort_measure)

    # Stat card 1: Average gap for the sort measure
    # WHY: Shows the mean value across ALL counties in the state (not
    # just the top N shown in the chart) so the user can see how the
    # charted counties compare to the state average.
    sort_label = MEASURES[sort_measure]["label"]
    avg_value = f"{summary['avg']:.1f}%" if summary['n_counties'] > 0 else "—"
    avg_label = f"Average {sort_label}"

    # Stat card 2: Counties with data
    # WHY: Tells the user how many counties in this state actually
    # have survey data for the selected cluster (not just how many
    # are displayed in the chart).
    count_value = str(summary['n_counties'])
    count_scope = state if state != "ALL" else "nationally"
    count_label = f"Counties with data ({count_scope})"

    # Stat card 3: Biggest gap county
    if summary['n_counties'] > 0:
        worst_value = summary['worst_county']
        worst_label = f"{summary['worst_val']:.1f}% — worst in selection"
    else:
        worst_value = "—"
        worst_label = "No data"

    # --- Step 4: Build the coverage note ---
    # n_counties_shown is how many counties are in the chart (top-N),
    # while n_counties_with_data is how many counties in the state have
    # survey data for the sort measure. Both numbers matter.
    n_shown = len(raw_df) if not raw_df.empty else 0
    coverage_note = _build_coverage_note(
        state, cluster_key,
        n_counties_with_data=summary['n_counties'],
        n_counties_shown=n_shown,
        n_flagged=summary['n_flagged'],
    )

    # --- Return everything ---
    return (
        fig,
        avg_value, avg_label,
        count_value, count_label,
        worst_value, worst_label,
        coverage_note,
    )


# ============================================================
# CROSS-PAGE NAVIGATION — click a bar → jump to Page 1's map
# ============================================================
# WHY THIS IS THE "GENUINE COMPLEXITY" PIECE:
#   The assignment specifically calls out cross-page linked filters as
#   more than just text filtering. When a program officer sees that
#   County X has the worst transportation barrier rate in Virginia,
#   their next question is "but what does that look like on the disease
#   map?" This callback answers that by navigating to Page 1 and
#   passing the county's FIPS code so the map can auto-select it.
#
# HOW IT WORKS:
#   1. The user clicks a bar on the grouped bar chart.
#   2. Plotly fires clickData, which includes the custom_data we
#      attached (the county's locationid / FIPS code).
#   3. This callback reads the FIPS and updates the hidden dcc.Location
#      component's pathname to "/" (Page 1) and search to
#      "?locationid=51001".
#   4. Because dcc.Location has refresh=True, the browser does a full
#      page reload to that URL.
#   5. Dash Pages loads Page 1, which needs to read the locationid
#      from the URL and auto-select that county on the map.
#
# WHAT LAUREN NEEDS TO ADD TO PAGE 1 (for the cross-page link to work):
#
#   Step A — Add a dcc.Location to Page 1's layout (if it doesn't
#   already have one):
#
#       dcc.Location(id="url", refresh=False)
#
#   Step B — Add "url.search" as an Input to Page 1's map callback:
#
#       @callback(
#           Output("choropleth-map", "figure"),
#           Input("disease-dropdown", "value"),
#           Input("adjustment-toggle", "value"),
#           Input("url", "search"),  # <-- NEW: reads ?locationid=XXXXX
#       )
#       def update_map(selected_disease, adjustment_value, search):
#           # Parse the locationid from the URL query string
#           from urllib.parse import parse_qs
#           params = parse_qs(search.lstrip("?"))
#           selected_fips = params.get("locationid", [None])[0]
#
#           # ... existing map-building code ...
#
#           # If a FIPS was passed from Page 3, use it to highlight
#           # that county. The exact approach depends on how Page 1's
#           # map is built — options include:
#           #   - Locating the matching row and centering the map view
#           #   - Opening the same detail popover that clicking the
#           #     county on the map would open
#           #   - Storing the FIPS in a dcc.Store that the stat-card
#           #     callback reads to show that county's details
#           # The key is: read selected_fips, find the county, and
#           # trigger the same selection state that a manual map click
#           # would produce.
#
#   Step C — Optionally, show a toast or banner on Page 1:
#       "Showing [County] — linked from Access & Social Determinants"
#   so the user knows why a specific county is pre-selected.
@callback(
    Output("access-nav-url", "pathname"),
    Output("access-nav-url", "search"),
    Input("access-bar-chart", "clickData"),
    prevent_initial_call=True,  # don't navigate on page load
)
def jump_to_map(clickData):
    """
    Navigate to Page 1's map when a bar is clicked.

    Reads the county's FIPS code from the bar's custom_data and
    constructs a URL like /?locationid=51001 that Page 1 can read.
    """
    # Guard: no click or no points (e.g., clicking on empty chart area)
    if not clickData or not clickData.get("points"):
        return no_update, no_update

    point = clickData["points"][0]

    # The FIPS code was attached via custom_data in _build_bar_chart.
    # Plotly stores it as a list (one element per custom_data column).
    customdata = point.get("customdata")
    if not customdata or len(customdata) == 0:
        return no_update, no_update

    fips = customdata[0]

    # Navigate to Page 1 ("/") with the county FIPS as a URL query
    # parameter. Page 1 reads this to auto-select the county.
    return "/", f"?locationid={fips}"
