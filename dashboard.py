import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from flask import Flask
from overall_analysis import overall_analysis_layout, register_overall_callbacks
from pagewise_analysis import pagewise_analysis_layout, register_pagewise_callbacks

primary_color = "#FF8C00"
container_style = {"margin": "20px", "fontFamily": "Arial, sans-serif"}

dashboard_server = Flask(
    __name__,
    static_folder="images",       # <-- folder on disks
    static_url_path="/images"     # <-- URL prefix
    )
dashboard_server.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://username:password@localhost/shimmy'
dashboard_server.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

dash_app = dash.Dash(__name__, server=dashboard_server, url_base_pathname='/dashboard/', suppress_callback_exceptions=True)

main_layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div([
        dcc.Link("Overall Analysis", href="/overall", style={"marginRight": "20px", "color": primary_color, "fontWeight": "bold"}),
        dcc.Link("Page-wise Analysis", href="/pagewise", style={"color": primary_color, "fontWeight": "bold"})
    ], style={"padding": "20px", "borderBottom": f"1px solid {primary_color}", "textAlign": "center"}),
    html.Div(id="page-content", style=container_style)
], style=container_style)

dash_app.layout = main_layout

@dash_app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    if pathname == "/pagewise":
        return pagewise_analysis_layout()
    else:
        return overall_analysis_layout()

register_overall_callbacks(dash_app, dashboard_server)
register_pagewise_callbacks(dash_app, dashboard_server)

if __name__ == '__main__':
    print("Access Dashboard here: http://127.0.0.1:5000/dashboard")
    dashboard_server.run(debug=True)
