import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc

# Initialize app
app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True,
                title="County Health Atlas", external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# One place that defines the tab bar. Order is the reading order we want
# a first-time visitor to follow: where the problem is, what predicts it,
# what compounds it, who to help first.
NAV_TABS = [
    ("Health Overview", "/"),
    ("Drivers & Risk Factors", "/drivers_and_risk_factors"),
    ("Access & Social Determinants", "/access_and_social_determinants"),
    ("At-Risk Counties", "/at_risk_counties"),
]


def _nav_links(active_path="/"):
    """Tab bar with the current page highlighted.

    dcc.Link does not set aria-current, so the active tab has to be
    marked from a callback -- without this every tab renders in the
    default state and the current page is never indicated.
    """
    links = []
    for label, href in NAV_TABS:
        classes = "nav-btn nav-btn--active" if href == active_path else "nav-btn"
        links.append(html.Li(dcc.Link(label, href=href, className=classes)))
    return links


app.layout = html.Div([
    dcc.Location(id="url"),
    html.Nav(
        className="site-nav",
        children=html.Div(
            className="site-nav__inner",
            children=[
                html.A(
                    [
                        "County Health Atlas",
                        html.Span("CDC PLACES · 2025 release · 3,144 counties"),
                    ],
                    className="site-nav__mark",
                    href="/",
                ),
                html.Ul(id="nav-links", className="site-nav__links",
                        children=_nav_links()),
            ],
        ),
    ),
    dash.page_container,
])


@app.callback(
    Output("nav-links", "children"),
    Input("url", "pathname"),
)
def highlight_active_tab(pathname):
    return _nav_links(pathname or "/")


if __name__ == "__main__":
    app.run(debug = True)
