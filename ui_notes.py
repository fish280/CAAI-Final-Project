"""
ui_notes.py -- small, reusable explanatory UI snippets shared across
pages. Not owned by any one page: any page that shows a crude vs.
age-adjusted control (the Overview map, this page, and eventually the
Access & Social Determinants page) should render crude_adjusted_note()
next to it, so the wording reads identically everywhere in the
dashboard instead of every page explaining it differently, or not
explaining it at all.
"""

from dash import html


def crude_adjusted_note():
    """Collapsed-by-default explainer for a crude / age-adjusted
    toggle. Uses a native <details> element, so dropping this into any
    page's layout is a one-line addition -- no callback required."""
    return html.Details(
        style={"marginTop": "0.6rem"},
        children=[
            html.Summary(
                "Crude vs. age-adjusted — what's the difference?",
                style={
                    "cursor": "pointer",
                    "fontWeight": 500,
                    "color": "var(--muted)",
                    "fontSize": "0.875rem",
                },
            ),
            html.P(
                "Crude is the raw percentage of adults reporting the "
                "condition — no adjustments. Age-adjusted re-weights "
                "that percentage as if every county had the same age "
                "mix, so a county doesn't look worse purely because it "
                "has more older residents. Use crude for \"how many "
                "people, right now\"; use age-adjusted for \"how much "
                "of this is really about this place, not who lives "
                "here.\"",
                className="dek",
                style={"marginTop": "0.5rem", "marginBottom": 0},
            ),
        ],
    )