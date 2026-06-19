import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Stock Hunter Pro v19.0 (Stable)", layout="wide")

# Sidebar - แผงคุมความเสี่ยง
st.sidebar.markdown("## 🦅 Stock Hunter Pro v19.0")
capital = st.sidebar.number_input("เงินทุน ($):", value=100000)
risk_pct = st.sidebar.slider("ความเสี่ยงต่อไม้ (%):", 0.1, 2.0, 1.0)
tickers = ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "COIN", "ASTS", "SMCI", "AVGO", "CMG"]

# Engine - คำนวณสัญญาณ
def get_signal(ticker):
    try:
        df = yf.Ticker(ticker).history(period="1y")
        if df.empty: return None
        
        # ตัวบ่งชี้
        df['EMA9'] = df['Close'].ewm(span=9).mean()
        df['EMA21'] = df['Close'].ewm(span=21).mean()
        df['EMA50'] = df['Close'].ewm(span=50).mean()
        df['ATR'] = df['High'].rolling(14).max() - df['Low'].rolling(14).min()
        df['VolMA20'] = df['Volume'].rolling(20).mean()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # กรองสัญญาณ (Stage 2 + Vol + Trend)
        is_stage2 = last['Close'] > last['EMA50']
        is_cross = prev['EMA9'] <= prev['EMA21'] and last['EMA9'] > last['EMA21']
        vol_ok = last['Volume'] > last['VolMA20']
        
        if is_stage2 and is_cross and vol_ok:
            sl = last['Close'] - (last['ATR'] * 2)
            shares = (capital * (risk_pct/100)) / (last['Close'] - sl)
            return {
                "Shares": int(shares),
                "Stop Loss": round(sl, 2),
                "Take Profit 2R": round(last['Close'] + ((last['Close'] - sl) * 2), 2),
                "Price": round(last['Close'], 2)
            }
        return None
    except:
        return None

# UI ส่วนแสดงผล
st.title("🦅 หน้าจอเทรดรายวัน")
tabs = st.tabs(["🟢 BUY TODAY", "⚠️ WATCHLIST", "❌ BANNED"])

buy_list = []
watch_list = []
ban_list = []

with st.spinner("กำลังวิเคราะห์ข้อมูล..."):
    for t in tickers:
        data = get_signal(t)
        if data:
            data['Ticker'] = t
            buy_list.append(data)
        else:
            watch_list.append({"Ticker": t})

with tabs[0]:
    if buy_list:
        st.dataframe(pd.DataFrame(buy_list))
    else:
        st.info("วันนี้ยังไม่มีสัญญาณซื้อที่ผ่านเกณฑ์")

with tabs[1]:
    st.write("รายการหุ้นเฝ้าระวัง")
    st.dataframe(pd.DataFrame(watch_list))
