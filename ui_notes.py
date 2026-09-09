"""
ui_notes.py -- shared UI building blocks used by every page.

Nothing here is owned by one page. If two pages show the same kind of
thing -- a readout above a chart, a legend explaining what the colors
mean, an explainer for a piece of CDC jargon -- it is built once here so
the wording and the styling match across the whole dashboard instead of
each page inventing its own.

All styling comes from the classes in assets/styles.css (.readout,
.caveats, .chart-legend, .note). Deliberately no inline style dicts:
change the look in the stylesheet and it changes on all four pages.
"""

from dash import html


# ======================================================================
# Readout strip -- the summary that sits directly above a chart
# ======================================================================
def readout_cell(value_id=None, label_id=None, value="—", label="",
                 hint=None, extra=None, value_class=""):
    """One cell of a readout strip.

    value_id / label_id are optional: pass them when a callback needs to
    write into the cell, leave them off for static text. `extra` takes
    any extra component (a ranked list, a badge) rendered under the label.
    """
    children = [
        html.Div(value, id=value_id, className=f"readout__value {value_class}".strip())
        if value_id else
        html.Div(value, className=f"readout__value {value_class}".strip()),
    ]
    children.append(
        html.Div(label, id=label_id, className="readout__label") if label_id
        else html.Div(label, className="readout__label")
    )
    if hint:
        children.append(html.Div(hint, className="readout__hint"))
    if extra is not None:
        children.append(extra)
    return html.Div(className="readout__cell", children=children)


def readout(cells, attached=False):
    """A readout strip. Two or three cells; the stylesheet handles the
    hairline dividers and collapses it to one column on a narrow screen.

    attached=True removes the gap and bottom border so the strip sits
    flush on the chart panel below it -- pair it with the class
    "panel panel--attached" on that panel so the two read as one object.
    """
    classes = ["readout"]
    if len(cells) == 2:
        classes.append("readout--2")
    if attached:
        classes.append("readout--attached")
    return html.Div(className=" ".join(classes), children=cells)


# ======================================================================
# Chart legends -- what the encodings mean, in words
# ======================================================================
def diverging_legend(low_label, high_label, ramp, items=()):
    """Legend for a diverging color scale, e.g. better/worse than
    expected. `ramp` is a CSS gradient string; `items` are extra
    (swatch_kind, text) pairs where swatch_kind is "dash", a hex color,
    or None for text only."""
    scale = html.Div(
        className="chart-legend__scale",
        children=[
            html.Div(className="chart-legend__ramp", style={"background": ramp}),
            html.Div(
                className="chart-legend__ends",
                children=[
                    html.Span(low_label, className="chart-legend__low"),
                    html.Span(high_label, className="chart-legend__high"),
                ],
            ),
        ],
    )
    return html.Div(
        className="chart-legend",
        children=[scale] + [_legend_item(kind, text) for kind, text in items],
    )


def legend_row(items):
    """A legend with no color scale -- just labelled encodings."""
    return html.Div(
        className="chart-legend",
        children=[_legend_item(kind, text) for kind, text in items],
    )


def _legend_item(kind, text):
    parts = []
    if kind == "dash":
        parts.append(html.Span(className="chart-legend__dash"))
    elif kind:
        parts.append(html.Span(className="chart-legend__swatch",
                               style={"background": kind}))
    parts.append(html.Span(text))
    return html.Div(className="chart-legend__item", children=parts)


# ======================================================================
# Jargon explainers -- collapsed by default, one click to open
# ======================================================================
def _note(summary, body):
    return html.Details(
        className="note",
        children=[
            html.Summary(summary, className="note__summary"),
            html.P(body, className="note__body"),
        ],
    )


def prevalence_note():
    """What "prevalence" means at all. Every page leans on the word, and
    a first-time reader has no reason to know it."""
    return _note(
        "What does \"prevalence\" mean?",
        "Prevalence is the share of adults who currently have or report a "
        "condition — a percentage, not a headcount. It answers \"what "
        "fraction of people right now,\" not \"how many new cases this "
        "year.\" A county at 20% means 1 in 5 adults there report the "
        "condition, however large or small the county is.",
    )


def crude_adjusted_note():
    """The crude / age-adjusted distinction. Belongs next to any control
    that switches between the two."""
    return _note(
        "Crude vs. age-adjusted — what's the difference?",
        "Crude is the raw percentage of adults reporting the condition — no "
        "adjustments. Age-adjusted re-weights that percentage as if every "
        "county had the same age mix, so a county doesn't look worse purely "
        "because it has more older residents. Use crude for \"how many "
        "people, right now\"; use age-adjusted for \"how much of this is "
        "really about this place, not who lives here.\"",
    )


# ======================================================================
# Caveats -- methodological limits that must not be missable
# ======================================================================
def _caveat(title, body):
    return html.Div([
        html.Div(title, className="caveat__title"),
        html.P(body, className="caveat__body"),
    ])


def correlation_caveats():
    """Both limits on reading a correlation between two PLACES measures.
    Not a collapsed note on purpose: a reader who never opens it is
    exactly the reader who would misread the number."""
    return html.Div(
        className="caveats",
        children=[
            _caveat(
                "Two numbers, not two measurements",
                "Both axes are CDC model estimates built from overlapping "
                "county demographics. Part of this correlation reflects "
                "shared modeling structure, not just real behavior.",
            ),
            _caveat(
                "Counties, not people",
                "Each dot is one county, not one person. A county having both "
                "more inactive residents and more diabetes does not mean the "
                "inactive residents are the ones with diabetes.",
            ),
        ],
    )


def estimate_caveats():
    """The same two ideas, worded for a page that ranks or maps a single
    measure rather than correlating two."""
    return html.Div(
        className="caveats",
        children=[
            _caveat(
                "Estimates, not measurements",
                "Most counties are too small for the CDC's survey to measure "
                "directly, so each rate is predicted from survey responses "
                "plus local demographics. Small counties carry the most "
                "uncertainty and can land at either extreme of a ranking.",
            ),
            _caveat(
                "Places, not people",
                "These figures describe counties. A county with a high rate "
                "is not evidence about any individual who lives there.",
            ),
        ],
    )
