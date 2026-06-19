import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="อาหวัง Pro Max v16.1 - Portfolio Core", layout="wide")

# ==========================================================================
# 📊 1. PORTFOLIO HEAT & SESSION STATE JOURNAL
# ==========================================================================
if "trade_journal" not in st.session_state:
    st.session_state.trade_journal = [
        {"date": "2026-06-15", "ticker": "AMD", "pnl_r": -1.0},
        {"date": "2026-06-16", "ticker": "TSLA", "pnl_r": -1.0},
        {"date": "2026-06-17", "ticker": "AAPL", "pnl_r": 1.5},
    ]

def calculate_consecutive_losses(journal):
    if not journal: return 0
    count = 0
    for trade in reversed(journal):
        if trade["pnl_r"] < 0: count += 1
        else: break
    return count

current_consecutive_losses = calculate_consecutive_losses(st.session_state.trade_journal)

# แผงควบคุมบริหารความเสี่ยงระดับหัวกะทิ (Sidebar)
st.sidebar.markdown("## 🦅 อาหวัง Pro Max v16.1")
st.sidebar.markdown("### `Hedge Fund Risk Architecture`")
st.sidebar.divider()

st.sidebar.markdown("### 🛡️ Global Risk Settings")
account_capital = st.sidebar.number_input("เงินทุนรวมในพอร์ต (บาท):", value=100000, step=10000)
base_risk_pct = st.sidebar.slider("ความเสี่ยงพื้นฐานต่อไม้ (Base Risk %):", 0.25, 2.0, 1.0, 0.25)
max_portfolio_heat = st.sidebar.slider("เพดานความเสี่ยงรวมพอร์ต (Max Open Risk %):", 3.0, 10.0, 5.0, 0.5)
current_open_risk = st.sidebar.slider("ความเสี่ยงรวมของไม้ที่ถืออยู่ในปัจจุบัน (%):", 0.0, 7.0, 2.0, 0.5)

st.sidebar.markdown("### 🛑 Automated Kill Switch")
st.sidebar.write(f"จำนวนไม้ที่แพ้ติดกันปัจจุบัน: **{current_consecutive_losses} ไม้**")

kill_switch = False
if current_consecutive_losses >= 4 or current_open_risk >= max_portfolio_heat:
    st.sidebar.error("🚨 ALERT: ระบบล็อกการซื้อขายถาวร (Heat เกิน หรือแพ้ติดกัน)")
    kill_switch = True

menu = st.sidebar.radio("🧭 โหมดการทำงาน:", ["⚡ 1. สแกนสดระดับ PM (Interactive)", "📊 2. Backtest วินัยเหล็ก (Fixed Risk)"])

# ==========================================================================
# 📦 2. QUANT MATHEMATICAL ENGINE
# ==========================================================================
@st.cache_data(ttl=60)
def fetch_clean_data(ticker, period="3y"):
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df is None or df.empty: return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        return df
    except: return None

def compute_v16_indicators(
