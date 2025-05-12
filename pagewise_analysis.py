import base64
from io import BytesIO
import random
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from wordcloud import WordCloud
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output
import data_handler

# Primary colors and styling
primary_color = "#FF8C00"
secondary_color = "#7E4CA4"
additional_colors = ["#FFA94D", "#FFD580", "#9C6DC0", "#B692D3"]
control_style = {"margin": "10px"}
filter_container_style = {
    "display": "flex",
    "flexWrap": "wrap",
    "alignItems": "center",
    "justifyContent": "center",
    "padding": "10px",
    "marginBottom": "15px"
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

def hex_to_rgba(hex_color, alpha=0.5):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"

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
            sessions = Session.query.filter(
                Session.timestamp >= start_dt,
                Session.timestamp <= end_dt
            ).order_by(Session.user_id, Session.timestamp).all()
        if sessions:
            return sessions
    except Exception as e:
        print("Using dummy data because:", e)
    sessions = data_handler.get_dummy_data()
    return [s for s in sessions if start_dt <= s.timestamp <= end_dt]

def aggregate_pagewise(sessions, page, dashboard_server, end_dt, user_filter="All", new_user_threshold=new_user_threshold_days):
    page_sessions = [s for s in sessions if s.page == page]
    user_ids = set(s.user_id for s in page_sessions)
    user_first = fetch_users(user_ids, dashboard_server)
    threshold = end_dt - timedelta(days=new_user_threshold)

    if user_filter == "New":
        page_sessions = [s for s in page_sessions if user_first.get(s.user_id, datetime.min) >= threshold]
    elif user_filter == "Old":
        page_sessions = [s for s in page_sessions if user_first.get(s.user_id, datetime.max) < threshold]

    traffic = defaultdict(int)
    for s in page_sessions:
        traffic[s.timestamp.date()] += 1
    traffic_df = pd.DataFrame(
        sorted(traffic.items()), columns=["Date", "Sessions"]
    )

    return {
        "total_sessions": len(page_sessions),
        "traffic_df": traffic_df,
        "page_sessions": page_sessions,
        "user_first": user_first
    }

def build_sankey_figure(page_sessions, n_pages=3):
    user_paths = []
    for session in page_sessions:
        pages = [session.referral_source]
        for _ in range(n_pages - 1):
            pages.append(random.choice([
                "Home", "Explore", "Post", "My Network", "Notifications",
                "Profile", "Settings", "About", "Contact"
            ]))
        for i in range(len(pages) - 1):
            user_paths.append((pages[i], pages[i+1]))

    if not user_paths:
        return {}

    pair_counts = Counter(user_paths)
    labels = sorted(set([p for pair in pair_counts for p in pair]))
    idx = {label: i for i, label in enumerate(labels)}
    sources = [idx[src] for src, _ in pair_counts]
    targets = [idx[tgt] for _, tgt in pair_counts]
    values = list(pair_counts.values())

    fig = go.Figure(data=[go.Sankey(
        node=dict(pad=15, thickness=20, line=dict(color="black", width=0.5), label=labels),
        link=dict(source=sources, target=targets, value=values)
    )])
    fig.update_layout(title="User Journey", margin=dict(l=20, r=20, t=40, b=20))
    return fig


def pagewise_analysis_layout():
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
                    id="page-date-picker",
                    start_date=(datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d'),
                    end_date=datetime.utcnow().strftime('%Y-%m-%d')
                )
            ], style=control_style),
            
            html.Div([  # Page Filter
                html.Label("Select Page:", style={"marginRight": "10px"}),
                dcc.Dropdown(id="page-dropdown", options=[], value="About", style={"width": "300px"})
            ], style=control_style),
            
            html.Div([  # User Filter
                html.Label("User Filter:", style={"marginRight": "10px"}),
                dcc.RadioItems(
                    id="page-user-filter",
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
            html.Button("Refresh", id="page-refresh", n_clicks=0,
                        style={"backgroundColor": primary_color, "color": "white", "border": "none", "padding": "10px 15px"}),
        style=refresh_button_container),

        html.Div([
            html.Div(   # Page Visits Overview
                id="page-session-summary",
                style={"width": "48%", "display": "inline-block"}),
            
            html.Div(   # Feedback Wordcloud
                id="page-feedback-table",
                style={"width": "48%", "display": "inline-block", "alignItems": "center", "justifyContent": "center", "float": "right"})
        ], style={"display": "flex", "justifyContent": "space-between"}),

        html.Div([  # New vs Old Users Chart 
            html.Div(dcc.Graph(id="page-user-pie-chart", config={"displayModeBar": False}),
                     style={"width": "38%", "display": "inline-block"}),
            
            html.Div([ # Traffic Analysis Chart
                dcc.Dropdown(
                    id="page-traffic-mode-filter",
                    options=[
                        {"label": "Overall Traffic Over Time", "value": "overall"},
                        {"label": "Average Weekly Traffic", "value": "weekly"},
                        {"label": "Average Daily Traffic", "value": "daily"}
                    ],
                    value="overall",
                    clearable=False,
                    style={"width": "100%"}
                ),
                dcc.Graph(id="page-traffic-chart", config={"displayModeBar": False})
            ], style={"width": "58%", "display": "inline-block", "float": "right"})
        ], style={"display": "flex", "justifyContent": "space-between"}),

        html.Div([  # Time and Day Usage Heatmap
            html.Div(
                dcc.Graph(id="page-weekly-heatmap", config={"displayModeBar": False}),
                style={"width": "48%", "display": "inline-block"}),
            
            html.Div(   # Device Type Chart
                dcc.Graph(id="page-device-chart", config={"displayModeBar": False}),
                style={"width": "48%", "display": "inline-block", "float": "right"})
        ], style={"display": "flex", "justifyContent": "space-between"}),

        html.Div(   # User Journey Chart
            dcc.Graph(id="page-sankey-chart", config={"displayModeBar": False}),
            style={"marginTop": "20px"})
    ], style=container_style)

def register_pagewise_callbacks(dash_app, dashboard_server):
    @dash_app.callback(
        [Output("page-dropdown", "options"),
        Output("page-dropdown", "value")],
        [Input("page-refresh", "n_clicks"),
         Input("page-date-picker", "start_date"),
         Input("page-date-picker", "end_date")]
    )
    def update_page_dropdown(n_clicks, start_date, end_date):
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            # Use the selected end date to both fetch sessions and compute threshold
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59)
        except Exception as e:
            print("Error parsing dates:", e)
            start_dt = datetime.utcnow() - timedelta(days=30)
            end_dt = datetime.utcnow()
        
        sessions = fetch_sessions(start_dt, end_dt, dashboard_server)
        pages = sorted({s.page for s in sessions})
        options = [{"label": p, "value": p} for p in pages]
        default_value = "About" if "About" in pages else (pages[0] if pages else None)
        return options, default_value

    @dash_app.callback(
        [
            Output("page-session-summary", "children"),
            Output("page-feedback-table", "children"),
            Output("page-user-pie-chart", "figure"),
            Output("page-traffic-chart", "figure"),
            Output("page-weekly-heatmap", "figure"),
            Output("page-device-chart", "figure"),
            Output("page-sankey-chart", "figure")
        ],
        [
            Input("page-refresh", "n_clicks"),
            Input("page-date-picker", "start_date"),
            Input("page-date-picker", "end_date"),
            Input("page-dropdown", "value"),
            Input("page-user-filter", "value"),
            Input("page-traffic-mode-filter", "value")
        ]
    )
    def update_pagewise(n_clicks, start_date, end_date, page, user_filter, traffic_mode):
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            # Use the selected end date to both fetch sessions and compute threshold
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59)
        except Exception as e:
            print("Error parsing dates:", e)
            start_dt = datetime.utcnow() - timedelta(days=30)
            end_dt = datetime.utcnow()
        
        if not page:
            return html.P("Error: Please select a page", style={"textAlign": "center"}), html.P(""), {}, {}, {}, {}, {}
        else:
            try:
                sessions = fetch_sessions(start_dt, end_dt, dashboard_server)
                data = aggregate_pagewise(sessions, page, dashboard_server, end_dt, user_filter)
                page_sessions = data["page_sessions"]
                user_first = data["user_first"]

                total_visits = data["total_sessions"]
                avg_time = round(sum(s.session_time for s in page_sessions) / total_visits, 2) if total_visits else 0
                exits = sum(1 for s in page_sessions if s == page_sessions[-1]) if total_visits else 0
                bounce_rate = round(exits / total_visits * 100, 2) if total_visits else 0

                today = end_dt.date()
                this_week = [today - timedelta(days=i) for i in range(6, -1, -1)]
                last_week = [d - timedelta(days=7) for d in this_week]
                counts = defaultdict(int)
                for s in page_sessions:
                    counts[s.timestamp.date()] += 1
                this_total = sum(counts[d] for d in this_week)
                last_total = sum(counts[d] for d in last_week)
                if last_total:
                    diff = (this_total - last_total) / last_total
                    arrow = "🔺" if diff > 0 else "🔻"
                    change_text = f"{arrow} {abs(diff)*100:.2f}% vs last week"
                    change_color = "#27ae60" if diff > 0 else "#e74c3c"
                else:
                    change_text = "No data for last week"
                    change_color = "#999"

                summary = html.Div([
                    html.H4("📊 Page Visit Overview", style={"fontWeight": "bold"}),
                    html.P(f"Total Visits: {total_visits}"),
                    html.P(f"Avg. Time on Page: {avg_time/60:.1f} min"),
                    html.P(f"Bounce Rate: {bounce_rate:.2f}%"),
                    html.P(change_text, style={"color": change_color, "fontWeight": "bold"})
                ], style={
                    "borderRadius": "12px",
                    "padding": "20px",
                    "textAlign": "center",
                    "margin": "0 auto",
                    "width": "600px"
                })

                feedback_text = " ".join([s.feedback for s in page_sessions if s.feedback])
                if feedback_text:
                    mask = None
                    size = 250
                    wc = WordCloud(
                        width=size, height=size, prefer_horizontal=1, color_func=lambda *args, **kwargs: primary_color, max_words=20,
                        min_font_size=12, max_font_size=20, background_color=None, mode="RGBA", collocations=False
                    ).generate(feedback_text)
                    img = wc.to_image().convert("RGBA")
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    fb_img = base64.b64encode(buf.getvalue()).decode()
                    feedback_component = html.Div([
                        html.H4("🗣️ Feedback Word Cloud", style={"textAlign": "center"}),
                        html.Img(src=f"data:image/png;base64,{fb_img}", style={"maxWidth": "100%"})
                    ], style={"display": "inline-block","alignItems": "center"})
                else:
                    feedback_component = html.P("No user feedback available", style={"textAlign": "center"})

                threshold = end_dt - timedelta(days=new_user_threshold_days)
                distinct_users = set(s.user_id for s in page_sessions)
                new_users = sum(1 for u in distinct_users if user_first.get(u, datetime.min) >= threshold)
                old_users = len(distinct_users) - new_users
                pie_fig = px.pie(
                    names=["New Users", "Old Users"],
                    values=[new_users, old_users],
                    title="User Distribution",
                    hole=0.4,
                    color_discrete_sequence=[primary_color, secondary_color]
                )
                pie_fig.update_layout(template="plotly_white")

                if traffic_mode == "overall":
                    traffic_fig = px.line(
                        data["traffic_df"], x="Date", y="Sessions",
                        title=f"Traffic Over Time for {page}",
                        template="plotly_white",
                        color_discrete_sequence=[primary_color]
                    )
                elif traffic_mode == "weekly":
                    df = pd.DataFrame([{"Weekday": s.timestamp.strftime("%A")} for s in page_sessions])
                    if not df.empty:
                        wc = df.groupby("Weekday").size().reindex(
                            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                            fill_value=0
                        ).reset_index(name="Sessions")
                        date_range = pd.date_range(start_dt.date(), end_dt.date(), freq='D')
                        occ = date_range.to_series().dt.day_name().value_counts().to_dict()
                        wc["AvgSessions"] = wc.apply(lambda r: r["Sessions"]/occ.get(r["Weekday"],1), axis=1)
                        traffic_fig = px.line(
                            wc, x="Weekday", y="AvgSessions",
                            title="Avg. Weekly Traffic",
                            template="plotly_white",
                            color_discrete_sequence=[primary_color]
                        )
                    else:
                        traffic_fig = {}
                elif traffic_mode == "daily":
                    df = pd.DataFrame([{"Hour": s.timestamp.hour} for s in page_sessions])
                    if not df.empty:
                        cnt = df.groupby("Hour").size().reset_index(name="Sessions")
                        days = (end_dt.date() - start_dt.date()).days + 1
                        cnt["AvgSessions"] = cnt["Sessions"] / days
                        traffic_fig = px.line(
                            cnt, x="Hour", y="AvgSessions",
                            title="Avg. Daily Traffic by Hour",
                            template="plotly_white",
                            color_discrete_sequence=[primary_color]
                        )
                    else:
                        traffic_fig = {}
                else:
                    traffic_fig = {}

                heat_df = pd.DataFrame([{"Date": s.timestamp.date(), "Hour": s.timestamp.hour} for s in page_sessions])
                if not heat_df.empty:
                    pivot = heat_df.groupby(["Hour", "Date"]).size().reset_index(name="Count")
                    heatmap = pivot.pivot(index="Hour", columns="Date", values="Count").fillna(0)
                    heatmap_fig = go.Figure(data=go.Heatmap(
                        z=heatmap.values,
                        x=heatmap.columns,
                        y=heatmap.index,
                        colorscale="YlOrRd",
                        hovertemplate="Visits: %{z}<extra></extra>"
                    ))
                    heatmap_fig.update_layout(
                        title="Time Heatmap (Hour × Date)",
                        xaxis_title="Date",
                        yaxis_title="Hour",
                        margin=dict(l=40, r=20, t=40, b=40)
                    )
                else:
                    heatmap_fig = {}

                def classify_device(ua):
                    ua = ua.lower()
                    if "iphone" in ua or "android" in ua:
                        return "Mobile"
                    elif any(x in ua for x in ["windows", "mac", "linux"]):
                        return "Desktop"
                    else:
                        return "Other"
                dev_series = pd.Series([classify_device(s.user_agent) for s in page_sessions]).value_counts()
                if not dev_series.empty:
                    dev_fig = px.pie(
                        names=dev_series.index,
                        values=dev_series.values,
                        title="Device Type",
                        color_discrete_sequence=[primary_color, secondary_color] + additional_colors
                    )
                    dev_fig.update_traces(textinfo="percent", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>")
                    dev_fig.update_layout(template="plotly_white")
                else:
                    dev_fig = {}

                sankey_fig = build_sankey_figure(page_sessions)

                return summary, feedback_component, pie_fig, traffic_fig, heatmap_fig, dev_fig, sankey_fig
            
            except Exception as e:
                print("Error in update_pagewise callback:", e)
                return html.P("Error updating page-wise analysis"), html.P(""), {}, {}, {}, {}, {}
