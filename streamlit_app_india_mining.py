"""
Fleet Mesh — Streamlit (GitHub → Streamlit Community Cloud)

Deploy:
  1. Push this repo to GitHub (streamlit_app.py + requirements.txt at repo root).
  2. https://share.streamlit.io  → New app → pick the repo → Main file: streamlit_app.py
"""

from __future__ import annotations

import math
import random
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SITE_LAT, SITE_LON = 23.3441, 85.3096  # Ranchi/Jharkhand mining-region reference
LIVE, CAUTION, STALE = "#3ecf6e", "#f5a623", "#e5484d"

TRUCK_DEFS = [
    {"id": "TRK-01", "role": "Haul A", "payload": "Iron ore (loaded)", "v_kph": 16.0},
    {"id": "TRK-02", "role": "Haul B", "payload": "Iron ore (empty)", "v_kph": 26.0},
    {"id": "TRK-03", "role": "Haul C", "payload": "Waste rock", "v_kph": 20.0},
    {"id": "TRK-04", "role": "Haul D", "payload": "Iron ore (loaded)", "v_kph": 14.0},
    {"id": "TRK-05", "role": "Water cart", "payload": "Dust suppressant", "v_kph": 18.0},
    {"id": "TRK-06", "role": "Service", "payload": "Fuel / parts", "v_kph": 12.0},
]

LOOPS = [
    {"cx": 0, "cy": 20, "rx": 160, "ry": 110},
    {"cx": 10, "cy": 10, "rx": 240, "ry": 165},
    {"cx": -20, "cy": 0, "rx": 320, "ry": 220},
    {"cx": 0, "cy": -10, "rx": 400, "ry": 280},
    {"cx": 30, "cy": 30, "rx": 480, "ry": 330},
    {"cx": 420, "cy": 40, "rx": 90, "ry": 70},
]


def ellipse_pt(cx, cy, rx, ry, a):
    return cx + math.cos(a) * rx, cy + math.sin(a) * ry


def ring(cx, cy, rx, ry, n=80):
    pts = [ellipse_pt(cx, cy, rx, ry, i / n * math.tau) for i in range(n + 1)]
    return [p[0] for p in pts], [p[1] for p in pts]


def world_to_latlon(x, y):
    mlat = 111_320.0
    mlon = 111_320.0 * math.cos(math.radians(SITE_LAT))
    return SITE_LAT + y / mlat, SITE_LON + x / mlon


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1.0, a)))


def bearing_deg(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def init_state():
    if "trucks" in st.session_state:
        return
    trucks = []
    for i, d in enumerate(TRUCK_DEFS):
        L = LOOPS[i]
        mean_r = (L["rx"] + L["ry"]) / 2
        omega = (d["v_kph"] / 3.6) / mean_r
        t = random.random() * 6
        wx, wy = ellipse_pt(L["cx"], L["cy"], L["rx"], L["ry"], t)
        lat, lon = world_to_latlon(wx, wy)
        trucks.append(
            {
                **d,
                "i": i,
                "omega": omega,
                "t": t,
                "wx": wx,
                "wy": wy,
                "lat": lat,
                "lon": lon,
                "heading": 0.0,
                "speed": d["v_kph"],
                "hops": 1,
                "age": 0,
                "status": "live",
                "dropout": 0,
                "trail": [(wx, wy)],
            }
        )
    st.session_state.trucks = trucks
    st.session_state.pkt = 0


def step(dt: float = 1.0):
    trucks = st.session_state.trucks
    for tr in trucks:
        i = tr["i"]
        L = LOOPS[i]
        if tr["dropout"] > 0:
            tr["dropout"] -= dt
            tr["age"] += dt
        else:
            if random.random() < 0.02:
                tr["dropout"] = 2 + random.random() * 4
            tr["t"] += tr["omega"] * dt
            wx, wy = ellipse_pt(L["cx"], L["cy"], L["rx"], L["ry"], tr["t"])
            lat, lon = world_to_latlon(wx, wy)
            dist = haversine_m(tr["lat"], tr["lon"], lat, lon)
            hdg = bearing_deg(tr["lat"], tr["lon"], lat, lon) if dist > 0.2 else tr["heading"]
            spd = (dist / max(dt, 0.05)) * 3.6
            spd = min(32.0, max(6.0, spd))
            tr.update(
                wx=wx,
                wy=wy,
                lat=lat,
                lon=lon,
                heading=hdg,
                speed=spd,
                hops=1 + random.randint(0, 2),
                age=0,
            )
            tr["trail"].append((wx, wy))
            tr["trail"] = tr["trail"][-40:]
            st.session_state.pkt += 1
        age = tr["age"]
        tr["status"] = "live" if age <= 5 else ("caution" if age <= 8 else "stale")


def fill(xs, ys, color, name="", legend=False, hover=None):
    return go.Scatter(
        x=xs,
        y=ys,
        fill="toself",
        fillcolor=color,
        line=dict(width=1.5, color="rgba(255,255,255,0.25)"),
        name=name,
        showlegend=legend,
        hovertemplate=hover or name or None,
        mode="lines",
    )


def label_trace(x, y, text, color):
    return go.Scatter(
        x=[x],
        y=[y],
        mode="text",
        text=[text],
        textfont=dict(color=color, size=11, family="Consolas, monospace"),
        hoverinfo="skip",
        showlegend=False,
    )


def build_fig(fog: bool, show_links: bool):
    fig = go.Figure()
    # overburden
    xs, ys = ring(-100, 430, 190, 80, 40)
    fig.add_trace(fill(xs, ys, "#3d4a38", "Overburden dump", True, "Overburden dump<extra></extra>"))
    fig.add_trace(label_trace(-100, 430, "OVERBURDEN", "#c5d4b8"))
    # waste
    for cx, cy, rx, ry in ((-520, 280, 140, 90), (-480, -260, 160, 80)):
        xs, ys = ring(cx, cy, rx, ry, 36)
        fig.add_trace(fill(xs, ys, "#4a545c", "Waste dump", cx == -520, "Waste dump<extra></extra>"))
        fig.add_trace(label_trace(cx, cy, "WASTE DUMP", "#d0d6dc"))
    # ore stockpiles
    for cx, cy, rx, ry in ((500, -220, 130, 100), (540, 260, 150, 85)):
        xs, ys = ring(cx, cy, rx, ry, 36)
        fig.add_trace(fill(xs, ys, "#8c3a22", "Ore stockpile", cx == 500, "High-grade Fe stockpile<extra></extra>"))
        ix, iy = ring(cx, cy, rx * 0.5, ry * 0.5, 20)
        fig.add_trace(fill(ix, iy, "#c45c32"))
        fig.add_trace(label_trace(cx, cy, "ORE STOCKPILE", "#ffd0b8"))
    # benches
    benches = [
        (540, 375, "#7a6244"),
        (470, 325, "#6e583c"),
        (400, 275, "#624e36"),
        (330, 225, "#564430"),
        (260, 175, "#4a3a2a"),
        (190, 125, "#3e3024"),
        (120, 80, "#32261c"),
    ]
    for i, (rx, ry, col) in enumerate(benches):
        xs, ys = ring(0, 10, rx, ry, 72)
        fig.add_trace(fill(xs, ys, col, "Pit benches", i == 0, "Waste-rock bench<extra></extra>"))
    fig.add_trace(label_trace(0, 360, "BENCH 4", "#e8d2a8"))
    fig.add_trace(label_trace(0, 250, "BENCH 3", "#e8d2a8"))
    fig.add_trace(label_trace(0, 150, "BENCH 2", "#e8d2a8"))
    fig.add_trace(label_trace(0, 70, "BENCH 1", "#e8d2a8"))
    # pit floor ore
    xs, ys = ring(0, 10, 85, 55, 40)
    fig.add_trace(fill(xs, ys, "#6a2414", "Pit floor Fe", True, "Pit floor high-grade Fe<extra></extra>"))
    ix, iy = ring(-6, 8, 40, 24, 20)
    fig.add_trace(fill(ix, iy, "#c45c32"))
    fig.add_trace(label_trace(0, 10, "PIT FLOOR  Fe", "#ffd0b8"))
    # haul roads
    first_road = True
    for rx, ry in ((210, 140), (280, 190), (350, 240), (420, 290), (490, 340)):
        xs, ys = ring(0, 10, rx, ry, 90)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color="#d4b45a", width=3, dash="dash"),
                name="Haul road",
                showlegend=first_road,
                hovertemplate="Haul road · 30 km/h cap<extra></extra>",
            )
        )
        first_road = False
    fig.add_trace(label_trace(200, -150, "HAUL ROAD", "#d4b45a"))
    # ramp
    fig.add_trace(
        fill(
            [-20, 500, 512, -8, -20],
            [-48, -42, -6, -16, -48],
            "#4a4034",
            "Ramp 8%",
            True,
            "Ramp 8%<extra></extra>",
        )
    )
    fig.add_trace(label_trace(240, -28, "RAMP 8%", "#d4b45a"))
    # pond
    xs, ys = ring(80, -390, 120, 55, 36)
    fig.add_trace(fill(xs, ys, "#1e3a4a", "Settling pond", True, "Settling pond<extra></extra>"))
    fig.add_trace(label_trace(80, -390, "SETTLING POND", "#b8d8ee"))
    # crusher
    fig.add_trace(
        fill(
            [-580, -420, -420, -580, -580],
            [-50, -50, 90, 90, -50],
            "#2c3238",
            "Crusher / ROM",
            True,
            "Crusher / ROM pad<extra></extra>",
        )
    )
    fig.add_trace(label_trace(-500, 20, "CRUSHER / ROM", "#e0e6ec"))
    fig.add_trace(
        fill(
            [370, 520, 520, 370, 370],
            [0, 0, 100, 100, 0],
            "#2c3238",
            "Workshop",
            True,
            "Workshop<extra></extra>",
        )
    )
    fig.add_trace(label_trace(445, 50, "WORKSHOP", "#e0e6ec"))
    if fog:
        xs, ys = ring(0, 0, 700, 520, 40)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                fill="toself",
                fillcolor="rgba(190,198,206,0.22)",
                line=dict(width=0),
                name="Fog",
                showlegend=True,
                hoverinfo="skip",
            )
        )

    trucks = st.session_state.trucks
    if show_links:
        live = [t for t in trucks if t["status"] != "stale"]
        for i, a in enumerate(live):
            for b in live[i + 1 :]:
                d = math.hypot(a["wx"] - b["wx"], a["wy"] - b["wy"])
                if d < 380:
                    fig.add_trace(
                        go.Scatter(
                            x=[a["wx"], b["wx"]],
                            y=[a["wy"], b["wy"]],
                            mode="lines",
                            line=dict(color="rgba(62,207,110,0.4)", width=1),
                            hoverinfo="skip",
                            showlegend=False,
                        )
                    )
    for tr in trucks:
        col = {"live": LIVE, "caution": CAUTION, "stale": STALE}[tr["status"]]
        if len(tr["trail"]) > 1:
            fig.add_trace(
                go.Scatter(
                    x=[p[0] for p in tr["trail"]],
                    y=[p[1] for p in tr["trail"]],
                    mode="lines",
                    line=dict(color=col, width=2),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        fig.add_trace(
            go.Scatter(
                x=[tr["wx"]],
                y=[tr["wy"]],
                mode="markers+text",
                marker=dict(size=16, color=col, symbol="diamond", line=dict(color="#0d0f13", width=1)),
                text=[tr["id"]],
                textposition="bottom center",
                textfont=dict(color="#e9edf1", size=11, family="Consolas"),
                name=tr["id"],
                hovertemplate=(
                    f"<b>{tr['id']}</b><br>{tr['role']}<br>{tr['payload']}<br>"
                    f"{tr['speed']:.0f} km/h · hdg {tr['heading']:.0f}°<br>"
                    f"hops {tr['hops']}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        paper_bgcolor="#12151a",
        plot_bgcolor="#1a1612",
        margin=dict(l=10, r=10, t=30, b=10),
        height=640,
        legend=dict(font=dict(color="#8b95a1", size=11), bgcolor="rgba(18,21,26,0.7)"),
        title=dict(
            text="India Open-Pit Mine · LoRa Mesh · Fog / Low Visibility",
            font=dict(color="#e9edf1", size=14),
        ),
        xaxis=dict(visible=False, range=[-720, 720], scaleanchor="y", scaleratio=1),
        yaxis=dict(visible=False, range=[-520, 540]),
        font=dict(color="#8b95a1"),
    )
    return fig


def main():
    st.set_page_config(
        page_title="Fleet Mesh — Mine Fog Ops",
        page_icon="🚛",
        layout="wide",
    )
    st.markdown(
        """
        <style>
          .stApp { background:#12151a; color:#8b95a1; }
          [data-testid="stSidebar"] { background:#1a1f26; }
          h1,h2,h3 { color:#e9edf1 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    init_state()

    st.title("FLEET MESH — INDIA MINING OPS")
    st.caption(
        "Safe and Efficient Operation of Indian Mine Vehicles in Fog and Low-Visibility Conditions  ·  "
        "LoRa P2P  ·  no central node  ·  GTA-style mine layout"
    )

    fog = st.sidebar.toggle("Fog / low visibility", value=True)
    show_links = st.sidebar.toggle("LoRa mesh links", value=True)
    auto = st.sidebar.toggle("Live demo (2 s tick)", value=True)
    if st.sidebar.button("Step once"):
        step(1.0)

    if auto:

        @st.fragment(run_every=timedelta(seconds=2))
        def live_panel():
            step(2.0)
            render(fog, show_links)

        live_panel()
    else:
        render(fog, show_links)


def render(fog, show_links):
    trucks = st.session_state.trucks
    live_n = sum(1 for t in trucks if t["status"] == "live")
    stale_n = sum(1 for t in trucks if t["status"] == "stale")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mesh nodes", len(trucks))
    c2.metric("Live", live_n)
    c3.metric("Stale", stale_n)
    c4.metric("Packets", st.session_state.pkt)
    st.info("🇮🇳 India mining-region simulation • Vehicles move automatically • LoRa mesh links update with vehicle positions • Fog mode simulates low visibility.")

    st.plotly_chart(build_fig(fog, show_links), use_container_width=True)

    rows = [
        {
            "Truck": t["id"],
            "Role": t["role"],
            "Payload": t["payload"],
            "Status": t["status"].upper(),
            "Speed km/h": round(t["speed"]),
            "Heading": round(t["heading"]),
            "Seen s": int(t["age"]),
            "Hops": t["hops"],
        }
        for t in trucks
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


main()
