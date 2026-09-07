import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

# Initialize app
app = dash.Dash(__name__, use_pages=True, suppress_callback_exceptions=True,
                title="Health Statistics Dashboard", external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

app.layout = html.Div([
    dbc.NavbarSimple(
        children = [
            dbc.NavLink("Health Overview", href = "/", active = "exact"), 
            dbc.NavLink("Drivers & Risk Factors", href = "/drivers_and_risk_factors", active = "exact"),
            dbc.NavLink("Social Determinants & Access", href = "/social_determinants_and_access", active = "exact"), 
            dbc.NavLink("At Risk Counties", href = "/at_risk_counties", active = "exact"),
            ],
            brand = "Public Health Dashboard",

        ),
        dash.page_container
])

if __name__ == "__main__":
    app.run(debug = True)