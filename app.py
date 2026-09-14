"""
Project Soochak - Mine Assessment & Terrain Response
Smart India Hackathon 2026 | Problem Statement 26025
Team MATR

AeroLinkTree-Inspired Dark Editorial Geotechnical Command Dashboard:
- Real-Time Hardware Bridge via USB Serial (Node S-103)
- Multi-Sensor Simulation Engine (MPU6050, VL53L1X, HX711, 980m Laser Baseline, Gas)
- AI Layer 1: UCI Seismic-Bumps Isolation Forest Anomaly Detection
- AI Layer 2: Sentinel-1 InSAR STGCN-LSTM 12-Hour Subsidence Forecasting
- AeroLinkTree Hero Presenter Stage with Giant Tabular Countdown Timer
- 4 Numbered Editorial Cards (01-04) Consolidating Real Models & Management by Exception
- Interactive 8x6 Health Grid (Phi-Cube), Schematic Mine Wall Map & Sentinel-1 InSAR Imagery
"""

import math
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_engine import (
    MineEnvironmentSimulator,
    OperationalScenario,
    ThreatLevel,
)
from hardware import bridge, get_available_ports
from models.seismic_isolation_forest import get_seismic_detector
from models.stgcn_lstm import get_stgcn_forecaster

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & AEROLINKTREE EDITORIAL THEME
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Project Soochak | Mine Subsidence Monitoring",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* AeroLinkTree Dark Grain & Ambient Radial Lighting */
.stApp {
    background-color: #080a0f !important;
    color: #f3f4f6 !important;
    background-image:
        radial-gradient(circle at 50% 0%, rgba(56, 189, 248, 0.13), transparent 52%),
        radial-gradient(circle at 100% 100%, rgba(52, 211, 153, 0.06), transparent 50%),
        radial-gradient(circle at 0% 50%, rgba(192, 132, 252, 0.04), transparent 45%) !important;
    background-attachment: fixed !important;
}

/* Subtle Fixed Noise Grain Overlay */
.grain-overlay {
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    pointer-events: none;
    z-index: 999999;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    opacity: 0.038;
}

[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}
[data-testid="stHeader"] {
    background: transparent !important;
}

/* AeroLinkTree Constrained Centered Editorial Container */
.aero-container {
    max-width: 1220px;
    margin: 0 auto;
    width: 100%;
}

/* Brand Header */
.brand-header-box {
    text-align: center;
    padding: 18px 0 14px 0;
    margin-bottom: 12px;
}
.brand-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
    color: #38bdf8;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}
.brand-title {
    font-family: 'Outfit', sans-serif;
    font-size: clamp(2.0rem, 3.8vw, 3.1rem);
    font-weight: 800;
    letter-spacing: 0.09em;
    color: #f8fafc;
    text-transform: uppercase;
    line-height: 1.05;
    margin: 0;
}
.brand-title .accent {
    color: #38bdf8;
    text-shadow: 0 0 24px rgba(56, 189, 248, 0.45);
}
.brand-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.84rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-top: 6px;
    font-weight: 500;
}

/* Frosted Glass Base */
.glass-card {
    background: rgba(15, 23, 42, 0.55);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
}

/* Pulse Dot */
.pulse-circle {
    width: 7px; height: 7px; border-radius: 50%; background: currentColor; display: inline-block;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.55; transform: scale(0.9); }
}

/* AeroLinkTree Presenter Stage */
.presenter-shell {
    position: relative;
    background: rgba(15, 23, 42, 0.58);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 24px;
    padding: 24px 28px;
    margin-bottom: 20px;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.45);
}
.presenter-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 10px;
    margin-bottom: 14px;
}
.presenter-brand-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 8px;
}
.presenter-sub-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.presenter-topic-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.presenter-topic-title {
    font-family: 'Outfit', sans-serif;
    font-size: clamp(1.4rem, 2.3vw, 2.1rem);
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
    line-height: 1.15;
    margin: 4px 0 8px 0;
}
.presenter-topic-desc {
    font-family: 'Inter', sans-serif;
    font-size: 0.86rem;
    color: #94a3b8;
    line-height: 1.5;
    margin: 0;
    max-width: 640px;
}
.presenter-timer-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: #94a3b8;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 4px;
}
.presenter-timer-digits {
    font-family: 'Outfit', 'JetBrains Mono', monospace;
    font-size: clamp(3.0rem, 5.0vw, 4.4rem);
    font-weight: 800;
    line-height: 0.95;
    letter-spacing: 0.04em;
    font-variant-numeric: tabular-nums;
    color: #f8fafc;
    text-shadow: 0 0 35px rgba(56, 189, 248, 0.35);
    margin: 6px 0;
}
.presenter-timer-digits.urgent {
    color: #f87171 !important;
    text-shadow: 0 0 45px rgba(239, 68, 68, 0.65) !important;
    animation: pulse-urgent 1.2s infinite ease-in-out;
}
.presenter-timer-digits.warning {
    color: #fbbf24 !important;
    text-shadow: 0 0 35px rgba(245, 158, 11, 0.5) !important;
}
@keyframes pulse-urgent {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.88; transform: scale(0.985); }
}
.timer-progress-track {
    width: 100%;
    height: 6px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 9999px;
    overflow: hidden;
    margin-top: 6px;
}
.timer-progress-fill {
    height: 100%;
    border-radius: 9999px;
    background: linear-gradient(90deg, #38bdf8, #10b981);
    transition: width 0.4s ease;
}
.timer-progress-fill.urgent {
    background: linear-gradient(90deg, #f59e0b, #ef4444);
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.5);
}
.timer-progress-fill.warning {
    background: linear-gradient(90deg, #38bdf8, #f59e0b);
}

/* AeroLinkTree Numbered Editorial Cards (01, 02, 03, 04) */
.editorial-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 22px;
}
@media (max-width: 900px) {
    .editorial-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}
@media (max-width: 550px) {
    .editorial-grid {
        grid-template-columns: 1fr;
    }
}
.editorial-card {
    position: relative;
    background: rgba(15, 23, 42, 0.60);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 16px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.25s, border-color 0.25s;
    overflow: hidden;
}
.editorial-card:hover {
    transform: translateY(-2px);
    border-color: rgba(56, 189, 248, 0.4);
}
.editorial-card::before {
    content: attr(data-index);
    position: absolute;
    right: 14px;
    top: 10px;
    font-family: 'Outfit', sans-serif;
    font-size: 1.8rem;
    font-weight: 800;
    color: rgba(255, 255, 255, 0.05);
    line-height: 1;
    pointer-events: none;
}
.card-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.card-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #94a3b8;
    font-weight: 700;
}
.card-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 0.66rem;
    font-weight: 700;
    width: fit-content;
}
.pill-safe { background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); }
.pill-info { background: rgba(56, 189, 248, 0.16); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); }
.pill-warn { background: rgba(245, 158, 11, 0.16); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35); }
.pill-crit { background: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); animation: pulse 1.6s infinite; }

.card-metric-val {
    font-family: 'Outfit', 'JetBrains Mono', monospace;
    font-size: 1.95rem;
    font-weight: 800;
    color: #f8fafc;
    line-height: 1.05;
    margin: 4px 0 6px 0;
}
.card-subtext {
    font-size: 0.74rem;
    color: #cbd5e1;
    line-height: 1.35;
    margin-bottom: 6px;
}
.card-footer-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #64748b;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 6px;
    margin-top: 2px;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: rgba(15, 23, 42, 0.45);
    padding: 6px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    margin-bottom: 16px;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    border-radius: 8px !important;
    padding: 8px 20px !important;
    font-weight: 600 !important;
    font-size: 0.86rem !important;
    color: #94a3b8 !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background-color: rgba(56, 189, 248, 0.16) !important;
    color: #38bdf8 !important;
    border: 1px solid rgba(56, 189, 248, 0.35) !important;
}

/* Phi-Cube Sensor Matrix */
.phi-matrix { display: grid; gap: 8px; }
.phi-tile {
    aspect-ratio: 1/1; border-radius: 10px;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace; border: 2px solid transparent;
    transition: transform 0.16s, box-shadow 0.16s; position: relative;
}
.phi-tile:hover { transform: scale(1.05); z-index: 2; }
.phi-score { font-size: 1.25rem; font-weight: 800; color: #0b1120; line-height: 1; }
.phi-id { font-size: 0.52rem; font-weight: 700; color: rgba(11, 17, 32, 0.75); margin-top: 3px; }
.phi-excellent { background: #16a34a; }
.phi-good { background: #86efac; }
.phi-suboptimal { background: #f59e0b; }
.phi-critical { background: #f87171; }
.phi-empty { background: rgba(30, 41, 59, 0.25); border: 1px dashed rgba(75, 85, 99, 0.25); }
.phi-selected { border-color: #38bdf8 !important; box-shadow: 0 0 12px rgba(56, 189, 248, 0.55); }
.phi-live-badge {
    position: absolute; top: 3px; right: 3px;
    background: #ef4444; color: #ffffff;
    font-size: 0.42rem; font-weight: 800; padding: 1px 4px; border-radius: 4px;
    animation: pulse 1.4s infinite;
}

/* Detail Card */
.detail-card {
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
}
.detail-row {
    display: flex; justify-content: space-between; padding: 4px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05); font-size: 0.81rem;
}
.detail-label { color: #94a3b8; }
.detail-value { color: #f3f4f6; font-weight: 600; font-family: 'JetBrains Mono', monospace; }

/* Section Subheaders */
.section-headline {
    font-family: 'Outfit', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: #e2e8f0;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 16px 0 10px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-headline::after {
    content: "";
    flex: 1;
    height: 1px;
    background: rgba(255, 255, 255, 0.08);
    margin-left: 10px;
}
</style>
<div class="grain-overlay"></div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. SESSION STATE & SIMULATOR INITIALIZATION
# -----------------------------------------------------------------------------
if "simulator" not in st.session_state:
    with st.spinner("Initializing Project Soochak AI Engines..."):
        st.session_state.simulator = MineEnvironmentSimulator()
        st.session_state.current_data = st.session_state.simulator.step(OperationalScenario.NORMAL)
        st.session_state.auto_refresh = False
        st.session_state.selected_node_id = "S-103"
        st.session_state.active_scenario = OperationalScenario.NORMAL

sim: MineEnvironmentSimulator = st.session_state.simulator


# -----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS & METRIC TIERS
# -----------------------------------------------------------------------------
def mine_health_score(anomaly_score: float) -> int:
    return max(0, min(100, int(round((1.0 - anomaly_score) * 100))))

def health_tier(score: int):
    if score >= 80: return "excellent", "Excellent", "#16a34a"
    elif score >= 60: return "good", "Good", "#4ade80"
    elif score >= 40: return "suboptimal", "Suboptimal", "#f59e0b"
    else: return "critical", "Critical", "#f87171"


# -----------------------------------------------------------------------------
# 4. SENSOR GRID & SCHEMATIC WALL MAP
# -----------------------------------------------------------------------------
GRID_COLS, GRID_ROWS = 8, 6

def compute_sensor_grid(nodes_list):
    lats = [n["lat"] for n in nodes_list]; lons = [n["lon"] for n in nodes_list]
    la1, la2 = min(lats), max(lats); lo1, lo2 = min(lons), max(lons)
    lp = (la2 - la1) * 0.15 or 0.001; lop = (lo2 - lo1) * 0.15 or 0.001
    la1 -= lp; la2 += lp; lo1 -= lop; lo2 += lop

    placements = {}
    for n in nodes_list:
        col = min(GRID_COLS - 1, int((n["lon"] - lo1) / (lo2 - lo1) * GRID_COLS))
        row = min(GRID_ROWS - 1, int(GRID_ROWS - (n["lat"] - la1) / (la2 - la1) * GRID_ROWS))
        placements[(row, col)] = n
    return placements

def compute_grid_refs(nodes_list):
    pl = compute_sensor_grid(nodes_list)
    refs = {}
    for (r, c), n in pl.items():
        refs[n["node_id"]] = f"{chr(65 + c)}{r + 1}"
    return refs

def render_sensor_grid_html(nodes_list, sel_id=None, is_hardware_live=False):
    pl = compute_sensor_grid(nodes_list)
    cells = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            n = pl.get((r, c))
            if not n:
                cells.append('<div class="phi-tile phi-empty"></div>')
                continue
            sc = mine_health_score(n["anomaly_score"])
            tier, _, _ = health_tier(sc)
            sel_cls = " phi-selected" if n["node_id"] == sel_id else ""
            live_badge = '<div class="phi-live-badge">LIVE</div>' if (n["node_id"] == "S-103" and is_hardware_live) else ''
            cells.append(
                f'<div class="phi-tile phi-{tier}{sel_cls}">'
                f'{live_badge}'
                f'<span class="phi-score">{sc}</span>'
                f'<span class="phi-id">{n["node_id"]}</span>'
                f'</div>'
            )
    return f'<div class="phi-matrix" style="grid-template-columns: repeat({GRID_COLS}, 1fr);">{"".join(cells)}</div>'

panel_polygon = [
    [23.7542, 86.4155], [23.7548, 86.4235],
    [23.7500, 86.4242], [23.7495, 86.4162],
]
goaf_polygon = [
    [23.7530, 86.4175], [23.7520, 86.4215],
    [23.7508, 86.4210], [23.7518, 86.4170],
]
WALL_COLS, WALL_ROWS = 12, 9

def build_schematic_wall_map(nodes_list, laser_dict, grid_refs_dict):
    all_lats = [n["lat"] for n in nodes_list] + [p[0] for p in panel_polygon + goaf_polygon] + [laser_dict["tx_lat"], laser_dict["rx_lat"]]
    all_lons = [n["lon"] for n in nodes_list] + [p[1] for p in panel_polygon + goaf_polygon] + [laser_dict["tx_lon"], laser_dict["rx_lon"]]
    la1, la2 = min(all_lats), max(all_lats); lo1, lo2 = min(all_lons), max(all_lons)
    lp = (la2 - la1) * 0.18 or 0.001; lop = (lo2 - lo1) * 0.18 or 0.001
    la1 -= lp; la2 += lp; lo1 -= lop; lo2 += lop

    def proj(la, lo):
        return ((lo - lo1) / (lo2 - lo1) * WALL_COLS, (la - la1) / (la2 - la1) * WALL_ROWS)

    nl = {n["node_id"]: n for n in nodes_list}
    fig = go.Figure()

    # Panel boundary wall
    pp = [proj(la, lo) for la, lo in panel_polygon] + [proj(*panel_polygon[0])]
    fig.add_trace(go.Scatter(
        x=[p[0] for p in pp], y=[p[1] for p in pp],
        mode="lines", fill="toself",
        fillcolor="rgba(56, 189, 248, 0.08)",
        line=dict(color="#38bdf8", width=2.5),
        name="Panel 4-B Boundary", hoverinfo="text",
        hovertext="Underground Longwall Extraction Panel 4-B",
    ))

    # Goaf caving zone
    gp = [proj(la, lo) for la, lo in goaf_polygon] + [proj(*goaf_polygon[0])]
    fig.add_trace(go.Scatter(
        x=[p[0] for p in gp], y=[p[1] for p in gp],
        mode="lines", fill="toself",
        fillcolor="rgba(249, 115, 22, 0.12)",
        line=dict(color="#f97316", width=2, dash="dash"),
        name="Active Goaf Margin", hoverinfo="text",
        hovertext="Goaf Caving Zone — Decompressed roof strata prone to subsidence",
    ))

    # Roadway Tunnel
    main_nodes = [nid for nid in ["S-101", "S-102", "S-103", "S-104", "S-105"] if nid in nl]
    mx = [proj(nl[nid]["lat"], nl[nid]["lon"])[0] for nid in main_nodes]
    my = [proj(nl[nid]["lat"], nl[nid]["lon"])[1] for nid in main_nodes]
    fig.add_trace(go.Scatter(
        x=mx, y=my, mode="lines",
        line=dict(color="#94a3b8", width=7),
        opacity=0.25, name="Main Roadway", hoverinfo="skip",
    ))

    # Laser Baseline
    tx = proj(laser_dict["tx_lat"], laser_dict["tx_lon"])
    rx = proj(laser_dict["rx_lat"], laser_dict["rx_lon"])
    dev = laser_dict["total_deviation_mm"]
    laser_color = "#ef4444" if dev > 2.5 else ("#f59e0b" if dev > 0.8 else "#10b981")
    fig.add_trace(go.Scatter(
        x=[tx[0], rx[0]], y=[tx[1], rx[1]],
        mode="lines+markers",
        line=dict(color=laser_color, width=2.2, dash="dot"),
        marker=dict(size=10, symbol="diamond", color=laser_color, line=dict(color="#ffffff", width=1)),
        name=f"Laser Baseline ({dev:.2f}mm)",
        hovertext=[
            f"<b>{laser_dict['tx_name']}</b><br>Optical Emitter (North Portal)",
            f"<b>{laser_dict['rx_name']}</b><br>Deviation: {dev:.2f}mm | Status: {laser_dict['status']}",
        ],
        hoverinfo="text",
    ))

    # Nodes
    status_colors = {"SAFE": "#10b981", "WATCH": "#0284c7", "WARNING": "#f97316", "CRITICAL": "#ef4444"}
    nx, ny, nc, nt, nh, ns = [], [], [], [], [], []
    for n in nodes_list:
        x, y = proj(n["lat"], n["lon"])
        nx.append(x); ny.append(y)
        nc.append(status_colors.get(n["status"], "#10b981"))
        nt.append(n["node_id"])
        ns.append(15 + n["anomaly_score"] * 15)
        nh.append(
            f"<b>{n['node_id']} — {n['name']}</b><br>"
            f"Grid: {grid_refs_dict.get(n['node_id'], '-')}<br>"
            f"Status: <b>{n['status']}</b> | ML Score: <b>{n['anomaly_score']:.3f}</b><br>"
            f"Tilt: {n['tilt_magnitude_deg']}° | Disp: {n['displacement_mm']:.2f}mm<br>"
            f"Load: {n['load_kN']:.1f} kN | CH₄: {n['methane_ppm']:.0f} ppm"
        )

    fig.add_trace(go.Scatter(
        x=nx, y=ny, mode="markers+text",
        marker=dict(size=ns, color=nc, line=dict(color="white", width=1.5), symbol="square"),
        text=nt, textposition="top center",
        textfont=dict(color="#f3f4f6", size=10, family="monospace"),
        hovertext=nh, hoverinfo="text", showlegend=False,
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15, 23, 42, 0.6)",
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
        xaxis=dict(
            range=[0, WALL_COLS], showgrid=True, gridcolor="rgba(148, 163, 184, 0.12)",
            dtick=1, zeroline=False, fixedrange=True,
            tickvals=[i + 0.5 for i in range(WALL_COLS)],
            ticktext=[chr(65 + i) for i in range(WALL_COLS)],
        ),
        yaxis=dict(
            range=[0, WALL_ROWS], showgrid=True, gridcolor="rgba(148, 163, 184, 0.12)",
            dtick=1, zeroline=False, fixedrange=True, scaleanchor="x", scaleratio=1,
            tickvals=[i + 0.5 for i in range(WALL_ROWS)],
            ticktext=[str(WALL_ROWS - i) for i in range(WALL_ROWS)],
        ),
        hovermode="closest",
    )
    return fig


# -----------------------------------------------------------------------------
# 5. TOP BRAND HEADER & HARDWARE EXPANDER (AeroLinkTree Centered Minimalist)
# -----------------------------------------------------------------------------
st.markdown("""
<div class="aero-container">
<div class="brand-header-box">
<div class="brand-eyebrow">
<span class="pulse-circle" style="background:#38bdf8;"></span>
<span>SIH 2026 · PROBLEM STATEMENT 26025 · TEAM MATR</span>
</div>
<h1 class="brand-title">PROJECT SOOCHAK <span class="accent">MINE RESPONSE</span></h1>
<div class="brand-sub">Real-Time Autonomous Mine Subsidence Monitoring, Prediction & Early Warning · Jharia Coalfield Panel 4-B</div>
</div>
</div>
""", unsafe_allow_html=True)

# Clean, modern hardware bridge in an unobtrusive expander
ports = get_available_ports()
hw_active = bridge.is_active

with st.expander("🔌 Hardware Serial Port Bridge (ESP32 Node S-103)", expanded=False):
    s_col1, s_col2, s_col3 = st.columns([2.2, 1.2, 1.6])
    with s_col1:
        sel_port = st.selectbox(
            "Serial Device Port",
            ports if ports else ["No Ports Found"],
            key="hw_port_selector",
            label_visibility="collapsed",
        )
    with s_col2:
        if not bridge.running:
            if st.button("🔌 Connect", use_container_width=True, key="hw_conn_btn"):
                if sel_port and sel_port != "No Ports Found":
                    ok, msg = bridge.connect(sel_port)
                    if not ok:
                        st.error(msg)
                    else:
                        st.rerun()
        else:
            if st.button("⏹️ Disconnect", use_container_width=True, key="hw_disconn_btn"):
                bridge.disconnect()
                st.rerun()
    with s_col3:
        if hw_active:
            st.markdown(f'<div style="margin-top:4px;"><span class="card-pill pill-crit"><span class="pulse-circle"></span>LIVE ESP32 S-103 · {bridge.port}</span></div>', unsafe_allow_html=True)
        elif bridge.running:
            st.markdown(f'<div style="margin-top:4px;"><span class="card-pill pill-info"><span class="pulse-circle"></span>LISTENING ON {bridge.port}...</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="margin-top:4px;"><span class="card-pill pill-safe"><span class="pulse-circle"></span>SYNTHETIC SIMULATION ACTIVE</span></div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 6. 1-CLICK PILL SCENARIO SWITCHER (AeroLinkTree Signature Style)
# -----------------------------------------------------------------------------
scenario_pill_meta = [
    ("🟢 Normal Shift", OperationalScenario.NORMAL),
    ("🛡️ Blasting Guard", OperationalScenario.BLASTING),
    ("⚠️ Strata Creep", OperationalScenario.STRATA_CREEP),
    ("🚨 Critical Subsidence", OperationalScenario.CRITICAL_SUBSIDENCE),
    ("🔧 Sensor Glitch", OperationalScenario.SENSOR_GLITCH),
]

st.markdown("""<div style="text-align:center; font-family:'JetBrains Mono',monospace; font-size:0.70rem; color:#94a3b8; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; margin-bottom:8px;">⚡ SELECT OPERATIONAL SCENARIO (INSTANT 1-CLICK EVALUATION)</div>""", unsafe_allow_html=True)

pill_cols = st.columns(5)
for i, (p_label, p_enum) in enumerate(scenario_pill_meta):
    with pill_cols[i]:
        is_active = (st.session_state.active_scenario == p_enum)
        if st.button(p_label, key=f"quick_pill_{p_enum.value}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.active_scenario = p_enum
            st.session_state.current_data = sim.step(scenario=p_enum)
            st.rerun()

# Auto run step if enabled
if (st.session_state.auto_refresh or hw_active):
    st.session_state.current_data = sim.step(scenario=st.session_state.active_scenario)

data = st.session_state.current_data
nodes = data["nodes"]
laser = data["laser_system"]
threat_level = data["threat_level"]
peak_score = data["peak_anomaly_score"]
false_alarms = data["false_alarms_rejected"]
history = data["history"]
logs = data["logs"]
uci_seismic = data.get("uci_seismic", {})
insar_forecast = data.get("insar_forecast", {})
active_sc = st.session_state.active_scenario

# -----------------------------------------------------------------------------
# 7. AEROLINKTREE PRESENTER STAGE & GIANT COUNTDOWN TIMER
# -----------------------------------------------------------------------------
max_d = max(n["displacement_mm"] for n in nodes)
top_node_item = max(nodes, key=lambda n: n["anomaly_score"])

if threat_level == "CRITICAL":
    stage_status = "CRITICAL SUBSIDENCE DETECTED"
    stage_status_color = "#f87171"
    stage_pulse_cls = "urgent"
    stage_title = "Coordinated Strata Roof Collapse in Progress"
    stage_desc = f"Severe multi-node roof displacement ({max_d:.2f}mm) validated by 980m Long-Baseline Optical Laser ({laser['total_deviation_mm']:.2f}mm). Immediate underground evacuation mandatory!"
    
    step_mod = (sim.step_counter * 22) % 480
    rem_sec = max(160, 900 - step_mod)
    mins, secs = divmod(rem_sec, 60)
    timer_str = f"{mins:02d}:{secs:02d}"
    timer_label = "🚨 SAFE RETREAT WINDOW (ESTIMATED BUFFER BEFORE ROOF CAVING)"
    progress_pct = int((rem_sec / 900) * 100)

elif threat_level == "WARNING":
    stage_status = "ELEVATED STRATA CREEP WARNING"
    stage_status_color = "#fbbf24"
    stage_pulse_cls = "warning"
    stage_title = "Pre-Subsidence Bed Separation at Goaf Margins"
    stage_desc = f"Continuous micro-strain and roof sag identified around Node {top_node_item['node_id']} ({top_node_item['panel_zone']}). Laser drift active at {laser['total_deviation_mm']:.2f}mm. Precautionary support inspection advised."
    
    timer_str = "03:45:00"
    timer_label = "⚠️ STABILIZATION & INSPECTION BUFFER WINDOW"
    progress_pct = 65

elif active_sc == OperationalScenario.BLASTING:
    stage_status = "CONTROLLED BLASTING FILTERED"
    stage_status_color = "#38bdf8"
    stage_pulse_cls = ""
    stage_title = "Heavy Blast Vibration Filtered · Zero Strata Movement"
    stage_desc = "Transient acoustic shock (1.2g RMS) rejected by Spatial Correlation Guard. Crack displacement and optical laser baseline stable. False alarm suppressed."
    
    timer_str = "00:00:00"
    timer_label = "🛡️ BLAST SHOCK DISSIPATED · TELEMETRY NOMINAL"
    progress_pct = 100

elif active_sc == OperationalScenario.SENSOR_GLITCH:
    stage_status = "SENSOR DRIFT FILTERED"
    stage_status_color = "#38bdf8"
    stage_pulse_cls = ""
    stage_title = "Isolated Sensor Drift Suppressed by Multi-Node Guard"
    stage_desc = "Single-node telemetry jump rejected because neighboring nodes confirm undisturbed strata. False mine evacuation prevented."
    
    timer_str = "00:00:00"
    timer_label = "🛡️ DRIFT ISOLATED · MINE EXTRACTION CONTINUES"
    progress_pct = 100

else:
    stage_status = "NORMAL STRATA EQUILIBRIUM"
    stage_status_color = "#34d399"
    stage_pulse_cls = ""
    stage_title = "All 8 Sectors Stable · Regular Extraction Shift Authorized"
    stage_desc = "Underground strata micro-vibrations, hydraulic prop loads, and 980m long-baseline optical reference are within geological baseline limits."
    
    timer_str = "11:42:15"
    timer_label = "🛰️ COPERNICUS SENTINEL-1 SATELLITE RADAR PREDICTIVE HORIZON"
    progress_pct = 92

stage_html = f"""<div class="presenter-shell">
<div class="presenter-header">
<div class="presenter-brand-name"><span class="pulse-circle" style="background:{stage_status_color};"></span><span>PROJECT SOOCHAK MINE COMMAND // EARLY WARNING STAGE SYNCED</span></div>
<div class="presenter-sub-tag" style="color: {stage_status_color};">● {stage_status}</div>
</div>
<div style="display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 18px;">
<div style="flex: 1; min-width: 320px;">
<div class="presenter-topic-label" style="color: {stage_status_color};">● {stage_status}</div>
<h2 class="presenter-topic-title">{stage_title}</h2>
<p class="presenter-topic-desc">{stage_desc}</p>
</div>
<div style="text-align: right; min-width: 280px;">
<div class="presenter-timer-label">{timer_label}</div>
<div class="presenter-timer-digits {stage_pulse_cls}">{timer_str}</div>
<div class="timer-progress-track"><div class="timer-progress-fill {stage_pulse_cls}" style="width: {progress_pct}%;"></div></div>
</div>
</div>
</div>"""
st.markdown(stage_html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 8. THE 4 NUMBERED EDITORIAL CARDS (01, 02, 03, 04)
# Replaces the old 5 repetitive KPI boxes + MBE banner with unified editorial elegance
# -----------------------------------------------------------------------------
# Card 01 calculations: AI Anomaly Verdict & Adaptive Sampling
c1_score = peak_score
if c1_score >= 0.70:
    c1_pill_cls, c1_pill_txt = "pill-crit", "CRITICAL ALERT"
    c1_adaptive = "2.0s High-Rate Focused Polling"
    c1_status_txt = f"Anomaly {c1_score:.3f} exceeds threshold. Immediate action required."
elif c1_score >= 0.40:
    c1_pill_cls, c1_pill_txt = "pill-warn", "ELEVATED CREEP"
    c1_adaptive = "2.0s Focused Polling on Hotspot"
    c1_status_txt = f"Anomaly {c1_score:.3f} detected in roof strata."
else:
    c1_pill_cls, c1_pill_txt = "pill-safe", "NORMAL EQUILIBRIUM"
    c1_adaptive = "30.0s Power-Save Fleet Polling"
    c1_status_txt = "All nodes within geological safety limits."

# Card 02 calculations: Roof Crack Sag (VL53L1X ToF)
c2_disp = max_d
if c2_disp >= 5.0:
    c2_pill_cls, c2_pill_txt = "pill-crit", "CRITICAL SAG"
elif c2_disp >= 2.0:
    c2_pill_cls, c2_pill_txt = "pill-warn", "ELEVATED SAG"
else:
    c2_pill_cls, c2_pill_txt = "pill-safe", "NORMAL (<2.0mm)"

c2_rate = top_node_item.get("displacement_rate_mm_min", 0.0)

# Card 03 calculations: 980m Optical Laser Baseline
c3_dev = laser["total_deviation_mm"]
if c3_dev > 2.5:
    c3_pill_cls, c3_pill_txt = "pill-crit", "BEAM DEVIATED"
elif c3_dev > 0.8:
    c3_pill_cls, c3_pill_txt = "pill-warn", "SLIGHT DRIFT"
else:
    c3_pill_cls, c3_pill_txt = "pill-safe", "ALIGNED"

# Card 04 calculations: Copernicus Sentinel-1 InSAR 12h Forecast (PyTorch STGCN-LSTM)
insar_risks = insar_forecast.get("peak_12h_risk", [0.12])
insar_peak_risk = float(max(insar_risks)) if insar_risks else 0.12
if insar_peak_risk >= 0.65:
    c4_pill_cls, c4_pill_txt = "pill-crit", "HAZARD PREDICTED"
elif insar_peak_risk >= 0.35:
    c4_pill_cls, c4_pill_txt = "pill-warn", "ELEVATED RISK"
else:
    c4_pill_cls, c4_pill_txt = "pill-safe", "LOW RISK (<35%)"

editorial_html = f"""<div class="editorial-grid">
<div class="editorial-card" data-index="01">
<div>
<div class="card-header-row"><span class="card-label">AI Anomaly Verdict</span><span class="card-pill {c1_pill_cls}"><span class="pulse-circle"></span>{c1_pill_txt}</span></div>
<div class="card-metric-val">{c1_score:.3f}</div>
<div class="card-subtext">{c1_status_txt}</div>
</div>
<div class="card-footer-tag">⚡ Adaptive Sampling: {c1_adaptive} · UCI Seismic IF</div>
</div>

<div class="editorial-card" data-index="02">
<div>
<div class="card-header-row"><span class="card-label">Roof Crack Sag</span><span class="card-pill {c2_pill_cls}"><span class="pulse-circle"></span>{c2_pill_txt}</span></div>
<div class="card-metric-val">{c2_disp:.2f} <span style="font-size:1.05rem; font-weight:600; color:#94a3b8;">mm</span></div>
<div class="card-subtext">Peak crack widening at {top_node_item['node_id']} ({top_node_item['panel_zone']}). Rate: {c2_rate:+.2f} mm/min.</div>
</div>
<div class="card-footer-tag">📏 VL53L1X ToF Laser Extensometer Array</div>
</div>

<div class="editorial-card" data-index="03">
<div>
<div class="card-header-row"><span class="card-label">980m Laser Baseline</span><span class="card-pill {c3_pill_cls}"><span class="pulse-circle"></span>{c3_pill_txt}</span></div>
<div class="card-metric-val">{c3_dev:.2f} <span style="font-size:1.05rem; font-weight:600; color:#94a3b8;">mm</span></div>
<div class="card-subtext">North Portal Emitter (Tx) ↔ South Portal Receiver (Rx). 980m differential beam reference.</div>
</div>
<div class="card-footer-tag">🎯 Absolute Macro-Strata Reference Baseline</div>
</div>

<div class="editorial-card" data-index="04">
<div>
<div class="card-header-row"><span class="card-label">InSAR 12h Forecast</span><span class="card-pill {c4_pill_cls}"><span class="pulse-circle"></span>{c4_pill_txt}</span></div>
<div class="card-metric-val">{insar_peak_risk*100:.1f}% <span style="font-size:1.05rem; font-weight:600; color:#94a3b8;">risk</span></div>
<div class="card-subtext">Copernicus Sentinel-1 SAR orbit pass validated. Spatial LOS deformation tracking active.</div>
</div>
<div class="card-footer-tag">🛰️ PyTorch Spatio-Temporal GCN + LSTM Engine</div>
</div>
</div>"""
st.markdown(editorial_html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 9. NAVIGATION TABS
# -----------------------------------------------------------------------------
tab_operations, tab_simulation, tab_analytics = st.tabs([
    "🗺️  Mine Operations & Sensor Maps",
    "🎮  Simulation Lab & Telemetry Stream",
    "📊  Anomaly Analytics & Audit Log",
])


# -----------------------------------------------------------------------------
# TAB 1: MINE OPERATIONS & SENSOR MAPS
# -----------------------------------------------------------------------------
with tab_operations:
    grefs = compute_grid_refs(nodes)
    node_lookup = {n["node_id"]: n for n in nodes}

    # Sort nodes by risk priority (Management by Exception)
    sorted_fleet = sorted(nodes, key=lambda n: n["anomaly_score"], reverse=True)
    top_hazard = sorted_fleet[0]
    top_hazard_id = top_hazard["node_id"]

    if "selected_node_id" not in st.session_state or st.session_state.selected_node_id not in node_lookup:
        st.session_state.selected_node_id = top_hazard_id

    grid_col, detail_col = st.columns([1.75, 1.25])

    with grid_col:
        st.markdown('<div class="section-headline">🧭 8x6 Sensor Matrix (Phi-Cube) & Priority Hotspots</div>', unsafe_allow_html=True)
        st.caption("Color-coded health scores (0-100). Higher = safer. Automatic exception filter isolates anomalous sectors.")

        grid_html = render_sensor_grid_html(
            nodes,
            sel_id=st.session_state.selected_node_id,
            is_hardware_live=hw_active,
        )
        st.markdown(f'<div class="glass-card" style="padding: 14px 16px;">{grid_html}</div>', unsafe_allow_html=True)

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        
        # Priority quick-bar for 1-click drilldown into top hotspots
        st.markdown('<div style="font-size: 0.72rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;">⚡ Quick Node Drilldown (Ranked by Risk):</div>', unsafe_allow_html=True)
        quick_cols = st.columns([1.3] + [1] * min(4, len(sorted_fleet)) + [1.3])
        with quick_cols[0]:
            is_auto_sel = st.session_state.selected_node_id == top_hazard_id
            if st.button(f"🎯 Top ({top_hazard_id})", key="btn_autofocus", use_container_width=True, type="primary" if is_auto_sel else "secondary"):
                st.session_state.selected_node_id = top_hazard_id
                st.rerun()

        for idx, n in enumerate(sorted_fleet[:4]):
            with quick_cols[idx + 1]:
                is_sel = n["node_id"] == st.session_state.selected_node_id
                if st.button(n["node_id"], key=f"btn_node_{n['node_id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                    st.session_state.selected_node_id = n["node_id"]
                    st.rerun()

        with quick_cols[-1]:
            all_nids = [n["node_id"] for n in nodes]
            cur_idx = all_nids.index(st.session_state.selected_node_id) if st.session_state.selected_node_id in all_nids else 0
            chosen_nid = st.selectbox("Fleet Dropdown", all_nids, index=cur_idx, label_visibility="collapsed", key="fleet_node_dropdown")
            if chosen_nid != st.session_state.selected_node_id:
                st.session_state.selected_node_id = chosen_nid
                st.rerun()

    with detail_col:
        st.markdown('<div class="section-headline">🔍 Node Inspector Deep Dive</div>', unsafe_allow_html=True)
        sn = node_lookup[st.session_state.selected_node_id]
        h_score = mine_health_score(sn["anomaly_score"])
        h_tier, h_tier_label, h_color = health_tier(h_score)
        is_node_hw = sn["node_id"] == "S-103" and hw_active

        hw_tag = f'<span class="card-pill pill-crit" style="font-size:0.65rem; margin-left:6px;"><span class="pulse-circle"></span>LIVE ESP32 ({bridge.port})</span>' if is_node_hw else '<span class="card-pill pill-safe" style="font-size:0.65rem; margin-left:6px;">SIMULATED</span>'

        # Match node index to InSAR
        insar_node_list = insar_forecast.get("nodes", [])
        insar_risk_list = insar_forecast.get("peak_12h_risk", [])
        node_num = int(sn["node_id"].split("-")[-1]) if "-" in sn["node_id"] else 1
        insar_idx = min(len(insar_risk_list) - 1, max(0, node_num - 101)) if insar_risk_list else 0
        node_12h_risk = float(insar_risk_list[insar_idx]) if insar_risk_list else 0.12
        insar_meta = insar_node_list[insar_idx] if len(insar_node_list) > insar_idx else {}
        insar_velocity = insar_meta.get("velocity_mmyr", -14.5)

        gas_alarm_badge = ""
        if is_node_hw and bridge.latest_data and bridge.latest_data.get("gasAlarm"):
            gas_alarm_badge = ' <span style="color:#f87171; font-weight:800;">[🚨 GAS ALARM]</span>'

        st.markdown(f"""<div class="detail-card">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
<div>
<div style="font-size: 1.1rem; font-weight: 800; color: #f8fafc;">{sn['node_id']} {hw_tag}</div>
<div style="font-size: 0.76rem; color: #94a3b8;">{sn['name']}</div>
</div>
<div style="text-align: right;">
<div style="font-size: 1.8rem; font-weight: 800; color: {h_color}; font-family: 'JetBrains Mono', monospace; line-height: 1;">{h_score}</div>
<div style="font-size: 0.68rem; color: {h_color}; font-weight: 700; text-transform: uppercase;">{h_tier_label}</div>
</div>
</div>
<div class="detail-row"><span class="detail-label">Grid Reference</span><span class="detail-value">{grefs.get(sn['node_id'], '-')}</span></div>
<div class="detail-row"><span class="detail-label">Zone & Depth</span><span class="detail-value">{sn['panel_zone']} ({sn['depth_m']}m)</span></div>
<div class="detail-row"><span class="detail-label">GPS Coordinates</span><span class="detail-value">{sn['lat']:.4f}° N, {sn['lon']:.4f}° E</span></div>
<div class="detail-row"><span class="detail-label">AI Threat Status</span><span class="detail-value">{sn['status']} (ML: {sn['anomaly_score']:.3f})</span></div>
<div class="detail-row"><span class="detail-label">MPU6050 Tilt</span><span class="detail-value">{sn['tilt_magnitude_deg']}° (P:{sn['pitch_deg']}° R:{sn['roll_deg']}°)</span></div>
<div class="detail-row"><span class="detail-label">VL53L0X / VL53L1X Crack Sag</span><span class="detail-value">{sn['displacement_mm']:.2f} mm ({sn['displacement_rate_mm_min']:+.2f} mm/min)</span></div>
<div class="detail-row"><span class="detail-label">Vibration Acceleration</span><span class="detail-value">RMS: {sn['vibration_rms_g']}g | Peak: {sn['vibration_peak_g']}g</span></div>
<div class="detail-row"><span class="detail-label">Prop Load (HX711)</span><span class="detail-value">{sn['load_kN']:.1f} kN (Δ {sn['load_delta_kN']:+.1f} kN)</span></div>
<div class="detail-row"><span class="detail-label">DHT22 Ambient Temp & Humidity</span><span class="detail-value">{sn['temp_c']:.1f}°C | {sn.get('humidity_pct', 65.0):.1f}% RH</span></div>
<div class="detail-row"><span class="detail-label">MQ-2 Combustible Gas</span><span class="detail-value">{sn['methane_ppm']:.0f} ppm{gas_alarm_badge}</span></div>
<div class="detail-row"><span class="detail-label">InSAR Satellite Velocity</span><span class="detail-value" style="color:#38bdf8;">{insar_velocity:.1f} mm/yr</span></div>
<div class="detail-row"><span class="detail-label">12h Subsidence Risk</span><span class="detail-value" style="color:{'#f87171' if node_12h_risk > 0.65 else '#34d399'};">{node_12h_risk*100:.1f}%</span></div>
<div class="detail-row" style="border-bottom: none;"><span class="detail-label">Last Telemetry</span><span class="detail-value">{sn['last_updated']}</span></div>
</div>""", unsafe_allow_html=True)

    # Schematic Mine Wall Map Section
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-headline">🗺️ Schematic Underground Mine Wall & 980m Laser Baseline</div>', unsafe_allow_html=True)
    st.caption("Panel 4-B boundary wall, active goaf caving margin, haulage roadway tunnel, and 980m dual-portal optical reference beam.")
    wall_fig = build_schematic_wall_map(nodes, laser, grefs)
    st.plotly_chart(wall_fig, use_container_width=True, config={"displayModeBar": False})

    # Copernicus Sentinel-1 InSAR Satellite Remote Sensing Map
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-headline">🛰️ Copernicus Sentinel-1 InSAR Satellite Surface Deformation</div>', unsafe_allow_html=True)
    st.caption("Multi-temporal C-band Synthetic Aperture Radar (SAR) remote sensing over Jharia Coalfield Panel 4-B. Left: Wrapped Phase Fringe Rings (28mm/cycle). Right: Calibrated LOS Subsidence Velocity Field with Ground Sensor Array.")

    st.image(
        "assets/insar_sentinel1_jharia.png",
        caption="Copernicus Sentinel-1A SAR Differential Interferogram (Left) & Calibrated Line-of-Sight Subsidence Velocity Map (Right) · Jharia Coalfield Panel 4-B (Project Soochak)",
        use_container_width=True,
    )


# -----------------------------------------------------------------------------
# TAB 2: SIMULATION LAB & TELEMETRY STREAM
# -----------------------------------------------------------------------------
with tab_simulation:
    st.markdown('<div class="section-headline">🎮 Geotechnical Simulation Engine & Disturbance Injection</div>', unsafe_allow_html=True)
    st.caption("Inject manual ground displacement, acoustic blast shocks, or sensor drift to evaluate real-time AI classification response.")

    sim_c1, sim_c2 = st.columns([1.2, 1.8])
    with sim_c1:
        st.markdown("##### ⚡ Simulation Controls")
        b1, b2, b3 = st.columns(3)
        with b1:
            btn_step = st.button("⚡ Next Step", use_container_width=True, key="sim_btn_step")
        with b2:
            btn_reset = st.button("🔄 Reset Base", use_container_width=True, key="sim_btn_reset")
        with b3:
            auto_toggle = st.checkbox("🔁 Auto-Play", value=st.session_state.auto_refresh, key="sim_auto_chk")
            st.session_state.auto_refresh = auto_toggle

        if btn_reset:
            st.session_state.simulator = MineEnvironmentSimulator()
            sim = st.session_state.simulator
            st.session_state.current_data = sim.step(OperationalScenario.NORMAL)
            st.session_state.active_scenario = OperationalScenario.NORMAL
            st.rerun()

    with sim_c2:
        st.markdown("##### 🎛️ Manual Disturbance Sliders")
        sc_m1, sc_m2, sc_m3 = st.columns(3)
        with sc_m1:
            man_disp = st.slider("Crack Sag (mm)", 0.0, 10.0, 0.0, 0.1, key="sim_man_disp")
        with sc_m2:
            man_tilt = st.slider("Roof Tilt (°)", 0.0, 5.0, 0.0, 0.1, key="sim_man_tilt")
        with sc_m3:
            man_laser = st.slider("Laser Drift (mm)", 0.0, 6.0, 0.0, 0.1, key="sim_man_laser")

    if btn_step:
        st.session_state.current_data = sim.step(
            scenario=st.session_state.active_scenario,
            manual_disp_offset=man_disp,
            manual_tilt_offset=man_tilt,
            manual_laser_offset=man_laser,
        )
        st.rerun()

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-headline">📋 Live Multi-Node Underground Telemetry Stream</div>', unsafe_allow_html=True)
    df_nodes = pd.DataFrame(nodes)[[
        "node_id", "name", "panel_zone", "depth_m", "pitch_deg", "roll_deg",
        "tilt_magnitude_deg", "vibration_rms_g", "vibration_peak_g",
        "displacement_mm", "displacement_rate_mm_min", "load_kN", "load_delta_kN",
        "methane_ppm", "temp_c", "battery_pct", "status", "anomaly_score",
    ]]
    df_nodes.columns = [
        "Node ID", "Name", "Zone", "Depth (m)", "Pitch (°)", "Roll (°)",
        "Tilt Mag (°)", "Vib RMS (g)", "Vib Peak (g)", "Disp (mm)",
        "Disp Rate", "Load (kN)", "Δ Load (kN)", "CH₄ (ppm)", "Temp (°C)",
        "Batt (%)", "Status", "Anomaly Score",
    ]
    st.dataframe(
        df_nodes.style.format({
            "Pitch (°)": "{:.2f}", "Roll (°)": "{:.2f}", "Tilt Mag (°)": "{:.2f}",
            "Vib RMS (g)": "{:.3f}", "Vib Peak (g)": "{:.3f}",
            "Disp (mm)": "{:.2f}", "Disp Rate": "{:+.2f}",
            "Load (kN)": "{:.1f}", "Δ Load (kN)": "{:+.1f}",
            "CH₄ (ppm)": "{:.0f}", "Temp (°C)": "{:.1f}", "Batt (%)": "{:.0f}%",
            "Anomaly Score": "{:.3f}",
        }),
        use_container_width=True,
        height=320,
    )


# -----------------------------------------------------------------------------
# TAB 3: ANOMALY ANALYTICS & AUDIT LOG
# -----------------------------------------------------------------------------
with tab_analytics:
    st.markdown('<div class="section-headline">📊 Historical Telemetry Trends & Predictive Analytics</div>', unsafe_allow_html=True)

    if history:
        df_hist = pd.DataFrame(history)
        c_tr1, c_tr2 = st.columns(2)

        with c_tr1:
            fig_score = go.Figure()
            fig_score.add_trace(go.Scatter(
                x=df_hist["step"], y=df_hist["peak_anomaly_score"],
                mode="lines+markers", name="Peak Anomaly Score",
                line=dict(color="#ef4444", width=2.5),
            ))
            fig_score.add_trace(go.Scatter(
                x=df_hist["step"], y=df_hist["mean_anomaly_score"],
                mode="lines", name="Mean Mine Score",
                line=dict(color="#38bdf8", width=1.5, dash="dot"),
            ))
            fig_score.add_hline(y=0.70, line_dash="dash", line_color="#dc2626", annotation_text="Critical (0.70)")
            fig_score.add_hline(y=0.40, line_dash="dash", line_color="#f59e0b", annotation_text="Warning (0.40)")
            fig_score.update_layout(
                title="Isolation Forest Anomaly Score vs Time Steps",
                xaxis_title="Simulation Step", yaxis_title="Normalized Score [0, 1]",
                template="plotly_dark", height=300,
                margin=dict(l=35, r=15, t=40, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(15, 23, 42, 0.6)",
            )
            st.plotly_chart(fig_score, use_container_width=True)

        with c_tr2:
            fig_disp = go.Figure()
            fig_disp.add_trace(go.Scatter(
                x=df_hist["step"], y=df_hist["max_displacement_mm"],
                mode="lines+markers", name="Max Crack Disp (mm)",
                line=dict(color="#f59e0b", width=2.2),
            ))
            fig_disp.add_trace(go.Scatter(
                x=df_hist["step"], y=df_hist["laser_deviation_mm"],
                mode="lines+markers", name="Laser Optical Drift (mm)",
                line=dict(color="#10b981", width=2.0, dash="dash"),
            ))
            fig_disp.update_layout(
                title="Ground Displacement vs Long-Baseline Laser Drift",
                xaxis_title="Simulation Step", yaxis_title="Displacement (mm)",
                template="plotly_dark", height=300,
                margin=dict(l=35, r=15, t=40, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(15, 23, 42, 0.6)",
            )
            st.plotly_chart(fig_disp, use_container_width=True)

        c_tr3, c_tr4 = st.columns(2)
        with c_tr3:
            fig_tilt = px.line(
                df_hist, x="step", y="max_tilt_deg",
                title="Peak MPU6050 Roof Tilt Magnitude (°)",
                template="plotly_dark", markers=True,
            )
            fig_tilt.update_traces(line_color="#c084fc", line_width=2)
            fig_tilt.update_layout(height=260, margin=dict(l=35, r=15, t=35, b=25), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15, 23, 42, 0.6)")
            st.plotly_chart(fig_tilt, use_container_width=True)

        with c_tr4:
            fig_load = px.line(
                df_hist, x="step", y="mean_load_kN",
                title="Average Hydraulic Prop Load (kN)",
                template="plotly_dark", markers=True,
            )
            fig_load.update_traces(line_color="#38bdf8", line_width=2)
            fig_load.update_layout(height=260, margin=dict(l=35, r=15, t=35, b=25), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15, 23, 42, 0.6)")
            st.plotly_chart(fig_load, use_container_width=True)

    # Per-node scores & Radar Fingerprint
    st.markdown('<div class="section-headline">🎯 Spatial Cross-Correlation & Multi-Sensor Fingerprint</div>', unsafe_allow_html=True)
    sp_col1, sp_col2 = st.columns([1.6, 1.2])

    with sp_col1:
        df_bars = pd.DataFrame(nodes)
        fig_bar = px.bar(
            df_bars, x="node_id", y="anomaly_score", color="status",
            color_discrete_map={"SAFE": "#10b981", "WATCH": "#0284c7", "WARNING": "#f59e0b", "CRITICAL": "#ef4444"},
            title="Per-Node ML Anomaly Scores across Panel 4-B",
            hover_data=["name", "displacement_mm", "tilt_magnitude_deg", "load_kN"],
            template="plotly_dark",
        )
        fig_bar.add_hline(y=0.70, line_dash="dash", line_color="#ef4444", annotation_text="Critical (0.70)")
        fig_bar.add_hline(y=0.40, line_dash="dash", line_color="#f59e0b", annotation_text="Warning (0.40)")
        fig_bar.update_layout(height=300, margin=dict(l=30, r=15, t=40, b=25), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15, 23, 42, 0.6)", showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    with sp_col2:
        crit_node = max(nodes, key=lambda n: n["anomaly_score"])
        cats = ["Displacement", "Tilt Angle", "Vibration RMS", "Load Delta", "Laser Shift"]
        norm_v = [
            min(1.0, crit_node["displacement_mm"] / 5.0),
            min(1.0, crit_node["tilt_magnitude_deg"] / 3.0),
            min(1.0, crit_node["vibration_rms_g"] / 0.8),
            min(1.0, max(0.0, crit_node["load_delta_kN"]) / 80.0),
            min(1.0, laser["total_deviation_mm"] / 3.0),
        ]
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=norm_v, theta=cats, fill="toself",
            name=f"Node {crit_node['node_id']}", line_color="#f43f5e",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            title=f"Multi-Sensor Fingerprint ({crit_node['node_id']})",
            template="plotly_dark", height=300,
            margin=dict(l=25, r=25, t=40, b=25),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # Multi-Node AI Correlation & False-Alarm Audit Log
    st.markdown('<div class="section-headline">🛡️ Multi-Node AI Correlation & False Alarm Audit Log</div>', unsafe_allow_html=True)
    if logs:
        for log in logs:
            l_type = log.get("type", "INFO")
            if l_type == "FILTERED_ALARM": l_icon, l_col = "🛡️", "#38bdf8"
            elif l_type == "SUBSIDENCE_ALERT": l_icon, l_col = "🚨", "#f87171"
            elif l_type == "STRATA_CREEP": l_icon, l_col = "⚠️", "#fbbf24"
            else: l_icon, l_col = "ℹ️", "#94a3b8"

            st.markdown(f"""<div style="background: rgba(15, 23, 42, 0.65); border-left: 3px solid {l_col}; padding: 8px 14px; border-radius: 6px; margin-bottom: 6px; font-size: 0.85rem;">
<span style="color: #94a3b8; font-size: 0.78rem; font-family: monospace;">[{log['time']}]</span>
<span style="font-weight: 700; color: {l_col}; margin-left: 8px;">{l_icon} {l_type}</span>:
<span style="color: #e2e8f0; margin-left: 6px;">{log['message']}</span>
</div>""", unsafe_allow_html=True)
    else:
        st.info("No alert events recorded yet. Run a scenario in the Simulation Control Center tab to generate events.")


# -----------------------------------------------------------------------------
# 10. AUTOMATIC REFRESH LOOP
# -----------------------------------------------------------------------------
if st.session_state.auto_refresh or hw_active:
    time.sleep(1.5 if hw_active else 2.0)
    st.rerun()
