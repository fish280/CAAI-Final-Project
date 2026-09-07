import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

# Initialize app
app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True,
                title="Health Statistics Dashboard", external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

app.layout = html.Div([
    html.Nav(
        className="site-nav",
        children=html.Div(
            className="site-nav__inner",
            children=[
                html.A(
                    "Public Health Dashboard",
                    className="site-nav__mark",
                    href="/",
                ),
                html.Ul(
                    className="site-nav__links",
                    children=[
                        html.Li(
                            dcc.Link(
                                "Health Overview",
                                href="/",
                                className="nav-btn",
                            )
                        ),
                        html.Li(
                            dcc.Link(
                                "Drivers & Risk Factors",
                                href="/drivers_and_risk_factors",
                                className="nav-btn",
                            )
                        ),
                        html.Li(
                            dcc.Link(
                                "Social Determinants & Access",
                                href="/social_determinants_and_access",
                                className="nav-btn",
                            )
                        ),
                        html.Li(
                            dcc.Link(
                                "At Risk Counties",
                                href="/at_risk_counties",
                                className="nav-btn",
                            )
                        ),
                    ],
                ),
            ],
        ),
    ),
    dash.page_container,
])

if __name__ == "__main__":
    app.run(debug = True)