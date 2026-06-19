import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import time
from datetime import datetime

# ==========================================================================
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG (อาหวัง Pro Max v15.2)
# ==========================================================================
st.set_page_config(page_title="อาหวัง Pro Max v15.2", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0
if "kill_switch_triggered" not in st.session_state:
    st.session_state.kill_switch_triggered = False

st.sidebar.markdown("## 🦅 อาหวัง Pro Max v15.2")
st.sidebar.markdown("### `The Hedge Fund Core Engine`")
st.sidebar.caption("🔒 เวอร์ชันเสถียรสูงสุด: ปรับปรุงชื่อระบบใหม่ พร้อมแก้บั๊กท่อข้อมูลเชื่อมต่อล่มเรียบร้อยแล้ว")
st.sidebar.divider()

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital_thb = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต (บาท THB):", min_value=1000, value=100000, step=5000)
fx_rate = st.sidebar.number_input("อัตราแลกเปลี่ยน USD/THB (รวม Spread):", min_value=30.0, max_value=45.0, value=36.5, step=0.1)
dime_fee_pct = st.sidebar.slider("ค่าธรรมเนียมรวม FX Spread (%):", min_value=0.0, max_value=1.5, value=0.30, step=0.05)
atr_multiplier = st.sidebar.slider("ตัวคูณระยะ Stop Loss (ATR Multiplier):", min_value=1.0, max_value=3.0, value=2.0, step=0.1)

st.sidebar.divider()
st.sidebar.markdown("### 🛑 ระบบเซฟตี้ Kill Switch")
consecutive_losses = st.sidebar.number_input("จำนวนไม้ที่แพ้ติดกันปัจจุบัน:", min_value=0, max_value=10, value=0)
weekly_drawdown_pct = st.sidebar.slider("เปอร์เซ็นต์ขาดทุนรวมในสัปดาห์นี้ (%):", min_value=0.0, max_value=15.0, value=0.0, step=0.5)

if consecutive_losses >= 4 or weekly_drawdown_pct >= 5.0:
    st.sidebar.error("🚨 KILL SWITCH ACTIVATED! ระบบอาหวังสั่งระงับการเทรดทุกกรณีเพื่อเซฟทุนถาวร")
    st.session_state.kill_switch_triggered = True
else:
    st.session_state.kill_switch_triggered = False

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดการทำงาน:",
    [
        "⚡ 1. หน้าแผงควบคุมสแกนสด & จัดอันดับ Ranking",
        "📊 2. ระบบทดสอบกลยุทธ์ย้อนหลัง (Backtest Engine)"
    ]
)

# ==========================================================================
# 📦 2. QUANT MATHEMATICAL & INDICATOR ENGINE (FIXED & STABLE)
# ==========================================================================
@st.cache_data(ttl=60)
def fetch_quant_data(ticker, period="3y", interval="1d", _state_key=0):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        df = df[(df['Close'] > 0) & (df['High'] > 0) & (df['Low'] > 0)]
        return df if len(df) >= 30 else None
    except Exception:
        return None

def check_earnings_within_7_days_safe(ticker):
    """ ฟังก์ชันสแกนวันงบการเงินแบบ Safe-Catch ไม่สั่งให้ระบบค้าง """
    try:
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if cal is not None and isinstance(cal, dict) and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if dates and len(dates) > 0:
                next_earn = dates[0]
                if not isinstance(next_earn, datetime):
                    next_earn = datetime.combine(next_earn, datetime.min.time())
                next_earn = next_earn.replace(tzinfo=None)
                days = (next_earn - datetime.now()).days
                if 0 <= days <= 7:
                    return True, days
        return False, -1
    except Exception:
        return False, -1

def compute_quant_indicators_safe(df, spy_return_90=0.0):
    if df is None or len(df) < 20:
        return None
    df = df.copy()
    
    span_200 = 200 if len(df) >= 200 else len(df)
    span_50 = 50 if len(df) >= 50 else len(df)
    span_20 = 20 if len(df) >= 20 else len(df)
    
    df['EMA_20'] = df['Close'].ewm(span=span_20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=span_50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=span_200, adjust=False).mean()
    
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['True_Range'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)
    df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
    
    df['Vol_MA20'] = df['Volume'].rolling(window=20, min_periods=1).mean()
    df['Highest_Close_20'] = df['Close'].shift(1).rolling(window=20, min_periods=1).max()
    
    if len(df) >= 90:
        stock_ret = (df['Close'].iloc[-1] - df['Close'].iloc[-90]) / df['Close'].iloc[-90]
    else:
        stock_ret = (df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]
        
    df['RS_Score_Current'] = stock_ret - spy_return_90
    return df

# ==========================================================================
# 📊 3. THE BACKTEST LOGIC ENGINE
# ==========================================================================
def run_quant_backtest_safe(df_proc, initial_capital=100000, atr_mult=2.0):
    if df_proc is None or len(df_proc) < 50:
        return None
        
    capital = initial_capital
    in_position = False
    entry_price = 0
    stop_loss = 0
    trades = []
    
    start_idx = min(200, len(df_proc) - 10)
    if start_idx
