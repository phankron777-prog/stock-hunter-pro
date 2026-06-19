import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Ultimate Fusion Core", layout="wide")

# --- PARAMETERS ---
tickers = ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "COIN", "ASTS", "SMCI", "AVGO", "CMG"]
capital = st.sidebar.number_input("เงินทุน ($):", value=100000)
risk_per_trade = st.sidebar.slider("ความเสี่ยงต่อไม้ (%):", 0.1, 2.0, 1.0)

# --- ENGINE: วิ่งหา Signal ตามเงื่อนไข v17.1 ---
def get_smart_signal(ticker):
    try:
        df = yf.Ticker(ticker).history(period="1y")
        spy = yf.Ticker("SPY").history(period="1y") # Market Filter
        
        # Indicators
        df['EMA20'] = df['Close'].ewm(span=20).mean()
        df['EMA50'] = df['Close'].ewm(span=50).mean()
        df['EMA200'] = df['Close'].ewm(span=200).mean()
        df['VolMA20'] = df['Volume'].rolling(20).mean()
        df['ATR'] = (df['High'] - df['Low']).rolling(14).mean()
        
        last = df.iloc[-1]
        
        # 1. Market Filter (SPY ต้องอยู่เหนือ EMA200)
        if spy.iloc[-1]['Close'] < spy.iloc[-1]['Close'].ewm(span=200).mean():
            return "BANNED", None

        # 2. Stage 2 + Volume Filter
        is_stage2 = last['Close'] > last['EMA20'] > last['EMA50'] > last['EMA200']
        is_vol_ok = last['Volume'] > last['VolMA20']
        
        # 3. Position Sizing
        sl_dist = last['ATR'] * 2
        risk_cash = capital * (risk_per_trade / 100)
        shares = risk_cash / sl_dist
        
        if is_stage2 and is_vol_ok:
            data = {
                "Shares": int(shares),
                "Stop Loss": round(last['Close'] - sl_dist, 2),
                "TP (50% @ 2R)": round(last['Close'] + (sl_dist * 2), 2),
                "TP (50% Trail)": "2.5x ATR Trailing"
            }
            return "BUY", data
        else:
            return "WATCH", None
            
    except:
        return "BANNED", None

# --- UI: Dashboard 3 แท็บ ---
st.title("🦅 Ultimate Fusion Core: Smart Signal Dashboard")
tabs = st.tabs(["🟢 BUY TODAY", "⚠️ WATCHLIST", "❌ BANNED"])

buy_list, watch_list, ban_list = [], [], []

with st.spinner("วิเคราะห์ Engine v17.1..."):
    for t in tickers:
        status, data = get_smart_signal(t)
        if status == "BUY":
            data['Ticker'] = t
            buy_list.append(data)
        elif status == "WATCH":
            watch_list.append({"Ticker": t})
        else:
            ban_list.append({"Ticker": t})

with tabs[0]:
    if buy_list: st.dataframe(pd.DataFrame(buy_list))
    else: st.info("ไม่มีสัญญาณเข้าซื้อ (รอเงื่อนไข Engine ครบถ้วน)")

with tabs[1]:
    st.write("หุ้นแนวโน้มดี แต่ยังไม่เข้าเกณฑ์ซื้อ")
    st.table(pd.DataFrame(watch_list))

with tabs[2]:
    st.write("หุ้นตลาดหมี / ไม่ผ่านเกณฑ์ Stage 2")
    st.table(pd.DataFrame(ban_list))
