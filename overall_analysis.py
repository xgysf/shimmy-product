from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
from dash import dcc, html
from dash.dependencies import Input, Output
import data_handler

# Primary colors and styling
primary_color = "#FF8C00"
secondary_color = "#7E4CA4"
control_style = {"margin": "10px"}
filter_container_style = {
    "display": "flex",
    "flexWrap": "wrap",
    "alignItems": "center",
    "justifyContent": "center",
    "padding": "10px",
    "marginBottom": "10px"
}
refresh_button_container = {
    "width": "100%",
    "textAlign": "center",
    "marginTop": "10px",
    "marginBottom": "15px"
}
container_style = {"margin": "10px", "fontFamily": "Arial, sans-serif"}

# Threshold in days for New User
new_user_threshold_days = 14

# Helper functions for fetching sessions and users (using DB if available, otherwise dummy data)
def fetch_users(user_ids, dashboard_server):
    try:
        with dashboard_server.app_context():
            from models import User
            users = User.query.filter(User.user_id.in_(list(user_ids))).all()
        if users:
            return {u.user_id: u.first_login for u in users}
    except Exception as e:
        print("Error in fetch_users:", e)
        if not data_handler.FAKE_USERS:
            data_handler.get_dummy_data()
        return {uid: data_handler.FAKE_USERS[uid].first_login for uid in user_ids if uid in data_handler.FAKE_USERS}

def fetch_sessions(start_dt, end_dt, dashboard_server):
    try:
        with dashboard_server.app_context():
            from models import Session
            sessions = Session.query.filter(Session.timestamp >= start_dt, Session.timestamp <= end_dt)\
                                     .order_by(Session.user_id, Session.timestamp).all()
        if not sessions:
            raise Exception("No sessions found in DB.")
        return sessions
    except Exception as e:
        print("Using dummy data because:", e)
        # Get all dummy data and filter by the selected date range
        sessions = data_handler.get_dummy_data()
        sessions = [s for s in sessions if s.timestamp >= start_dt and s.timestamp <= end_dt]
        return sessions

def aggregate_overall(sessions, dashboard_server, end_dt, user_filter="All", new_user_threshold=new_user_threshold_days):
    total_records = len(sessions)
    user_ids = set(s.user_id for s in sessions)
    user_first = fetch_users(user_ids, dashboard_server)
    
    # Compute threshold relative to the selected end date
    threshold = end_dt - timedelta(days=new_user_threshold)
    overall_new = sum(1 for first in user_first.values() if first >= threshold)
    overall_old = len(user_first) - overall_new

    if user_filter == "New":
        filtered_sessions = [s for s in sessions if user_first.get(s.user_id, datetime.max) >= threshold]
    elif user_filter == "Old":
        filtered_sessions = [s for s in sessions if user_first.get(s.user_id, datetime.min) < threshold]
    else:
        filtered_sessions = sessions

    # Daily traffic aggregation
    traffic = {}
    for s in filtered_sessions:
        day = s.timestamp.date()
        traffic[day] = traffic.get(day, 0) + 1
    traffic_df = pd.DataFrame(list(traffic.items()), columns=["Date", "Sessions"]).sort_values("Date")

    # Aggregate page counts for top and bottom pages
    page_counts = {}
    for s in filtered_sessions:
        page_counts[s.page] = page_counts.get(s.page, 0) + 1
    top_pages = dict(sorted(page_counts.items(), key=lambda x: x[1], reverse=True)[:5])
    bottom_pages = dict(sorted(page_counts.items(), key=lambda x: x[1])[:5])
    
    # Referral source distribution
    src_counts = pd.Series([s.referral_source for s in sessions]).value_counts().to_dict()

    return {
        "total_records": total_records,
        "distinct_users": len(user_first),
        "new_users": overall_new,
        "old_users": overall_old,
        "top_pages": top_pages,
        "bottom_pages": bottom_pages,
        "traffic_df": traffic_df,
        "filtered_sessions": filtered_sessions,
        "source_distribution": src_counts
    }

def overall_analysis_layout():
    return html.Div([  
        html.Div([  # Header
            html.H2("Analytics Dashboard", style={"margin": 0}),
            html.Img(src="/images/logo.png", style={"height": "60px"})
        ], style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "backgroundColor": "white",
            "padding": "15px",
            "color": primary_color,
            "fontFamily": "Arial, sans-serif",
            "fontSize": "24px"
        }),

        html.Div([  # Filters Section
            html.Div([  # Date Picker
                html.Label("Select Date Range:", style={"marginRight": "10px"}),
                dcc.DatePickerRange(
                    id="overall-date-picker",
                    start_date=(datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d'),
                    end_date=datetime.utcnow().strftime('%Y-%m-%d')
                )
            ], style=control_style),

            html.Div([  # User Filter
                html.Label("User Filter:", style={"marginRight": "10px"}),
                dcc.RadioItems(
                    id="overall-user-filter",
                    options=[
                        {"label": "All", "value": "All"},
                        {"label": "New Users", "value": "New"},
                        {"label": "Old Users", "value": "Old"}
                    ],
                    value="All",
                    labelStyle={"display": "inline-block", "marginRight": "10px"}
                )
            ], style=control_style)
        ], style=filter_container_style),

        html.Div(  # Refresh Button
            html.Button("Refresh", id="overall-refresh", n_clicks=0,
                        style={"backgroundColor": primary_color, "color": "white", "border": "none", "padding": "10px 15px"}),
        style=refresh_button_container),

        html.Div([
            html.Div([  # Overall Records
                html.P(id="total-records", style={"fontSize": "18px", "margin": "7px"}),
                html.P(id="distinct-users", style={"fontSize": "18px", "margin": "7px"})
            ], style={"textAlign": "center", "marginBottom": "15px"})
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "marginBottom": "15px"}),

        html.Div([
            html.Div(  # New vs Old Users Chart
                dcc.Graph(id="user-pie-chart", config={"displayModeBar": False}),
                style={"width": "38%", "display": "inline-block"}),
            
            html.Div([  # Traffic Analysis Chart
                html.Div(
                    dcc.Dropdown(
                        id="traffic-mode-filter",
                        options=[
                            {"label": "Overall Traffic Over Time (by Date)", "value": "overall"},
                            {"label": "Average Weekly Traffic (by Day of the Week)", "value": "weekly"},
                            {"label": "Average Daily Traffic (by Hour of the Day)", "value": "daily"}
                        ],
                        value="overall",
                        placeholder="Overall Traffic Over Time (by Date)",
                        style={
                            "width": "100%",
                            "display": "inline-block",
                            "border": "none",
                            "boxShadow": "none",
                            "outline": "none",
                            "borderRadius": "0"
                        },
                        clearable=False)),
                
                html.Div([
                    dcc.Graph(id="overall-traffic-chart", config={"displayModeBar": False}),
                ], style={"display": "inline-block", "justifyContent": "center"})
            ], style={"width": "58%", "display": "inline-block", "float": "right"}),
        ], style={"display": "flex", "justifyContent": "space-between"}),

        html.Div([
            html.Div([  # Top Pages Chart
                dcc.Graph(id="top-pages-chart", config={"displayModeBar": False}),
            ], style={"width": "48%", "display": "inline-block"}),
            
            html.Div([  # Bottom Pages Chart
                dcc.Graph(id="bottom-pages-chart", config={"displayModeBar": False}),
            ], style={"width": "48%", "display": "inline-block", "float": "right"})
        ], style={"display": "flex", "justifyContent": "space-between"}),
        
        html.Div([
            html.Div([  # Source Distribution
                dcc.Graph(id="overall-source-chart", config={"displayModeBar": False}),
        ], style={"width": "48%", "display": "inline-block"})
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "center"}
        ),
    ], style=container_style)


def register_overall_callbacks(dash_app, dashboard_server):
    @dash_app.callback(
        [Output("total-records", "children"),
         Output("distinct-users", "children"),
         Output("user-pie-chart", "figure"),
         Output("overall-traffic-chart", "figure"),
         Output("top-pages-chart", "figure"),
         Output("bottom-pages-chart", "figure"),
         Output("overall-source-chart", "figure")],
        [Input("overall-refresh", "n_clicks"),
         Input("overall-date-picker", "start_date"),
         Input("overall-date-picker", "end_date"),
         Input("overall-user-filter", "value"),
         Input("traffic-mode-filter", "value")]
    )
    def update_overall(n_clicks, start_date, end_date, user_filter, traffic_mode):
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            # Use the selected end date to both fetch sessions and compute threshold
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59)
        except Exception as e:
            print("Error parsing dates:", e)
            start_dt = datetime.utcnow() - timedelta(days=30)
            end_dt = datetime.utcnow()
        try:
            sessions = fetch_sessions(start_dt, end_dt, dashboard_server)
            data = aggregate_overall(sessions, dashboard_server, end_dt, user_filter)
            total_records_text = f"Total Hits: {data['total_records']}"
            distinct_users_text = f"Distinct Users: {data['distinct_users']}"
            pie_fig = px.pie(
                names=["New Users", "Old Users"],
                values=[data["new_users"], data["old_users"]],
                title="User Distribution",
                color_discrete_sequence=[primary_color, secondary_color],
                hole=0.4
            )
            pie_fig.update_layout(template="plotly_white")
            if traffic_mode == "overall":
                traffic_fig = px.line(data["traffic_df"], x="Date", y="Sessions", 
                                      template="plotly_white",
                                      color_discrete_sequence=[primary_color])
            elif traffic_mode == "weekly":
                filtered_sessions = data["filtered_sessions"]
                if filtered_sessions:
                    df = pd.DataFrame([{"Weekday": s.timestamp.strftime("%A")} for s in filtered_sessions])
                    weekday_counts = df.groupby("Weekday").size().reset_index(name="Sessions")
                    date_range = pd.date_range(start_dt.date(), end_dt.date(), freq='D')
                    weekday_occurrences = date_range.to_series().dt.day_name().value_counts().to_dict()
                    weekday_counts["AvgSessions"] = weekday_counts.apply(
                        lambda row: row["Sessions"] / weekday_occurrences.get(row["Weekday"], 1), axis=1)
                    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    weekday_counts["Weekday"] = pd.Categorical(weekday_counts["Weekday"], categories=weekday_order, ordered=True)
                    weekday_counts = weekday_counts.sort_values("Weekday")
                    traffic_fig = px.line(weekday_counts, x="Weekday", y="AvgSessions", 
                                          template="plotly_white",
                                          color_discrete_sequence=[primary_color])
                else:
                    traffic_fig = {}
            elif traffic_mode == "daily":
                filtered_sessions = data["filtered_sessions"]
                if filtered_sessions:
                    df = pd.DataFrame([{"Hour": s.timestamp.hour} for s in filtered_sessions])
                    hour_counts = df.groupby("Hour").size().reset_index(name="Sessions")
                    num_days = (end_dt.date() - start_dt.date()).days + 1
                    hour_counts["AvgSessions"] = hour_counts["Sessions"] / num_days
                    traffic_fig = px.line(hour_counts, x="Hour", y="AvgSessions", 
                                          template="plotly_white",
                                          color_discrete_sequence=[primary_color])
                else:
                    traffic_fig = {}
            else:
                traffic_fig = {}
            
            top_df = pd.DataFrame(list(data["top_pages"].items()), columns=["Page", "Views"])
            top_df = top_df.sort_values("Views", ascending=True)
            top_fig = px.bar(top_df, x="Views", y="Page", orientation="h", 
                             title="Top Viewed Pages", template="plotly_white",
                             color_discrete_sequence=[primary_color])
            
            bottom_df = pd.DataFrame(list(data["bottom_pages"].items()), columns=["Page", "Views"])
            bottom_df = bottom_df.sort_values("Views", ascending=False)
            bottom_fig = px.bar(bottom_df, x="Views", y="Page", orientation="h", 
                                title="Bottom Viewed Pages", template="plotly_white",
                                color_discrete_sequence=[primary_color])
            
            src_series = pd.Series(data["source_distribution"])
            src_fig = px.pie(
                names=src_series.index,
                values=src_series.values,
                title="Referral Source Distribution",
                color_discrete_sequence=[primary_color, secondary_color]
            )
            src_fig.update_layout(template="plotly_white")

            return total_records_text, distinct_users_text, pie_fig, traffic_fig, top_fig, bottom_fig, src_fig
        
        except Exception as e:
            print("Error in update_overall callback:", e)
            return html.P("Error updating overall analysis"), html.P(""), {}, {}, {}, {}, {}
