import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path

st.set_page_config(page_title="Stock Hunter Pro v21", layout="wide")

# 1. ขยายรายการหุ้นให้ครอบคลุม
TICKERS = ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "COIN", "ASTS", "SMCI", "ARM", "MSTR", "INTC"]

@st.cache_data(ttl=3600)
def load_data(ticker):
    try:
        df = yf.Ticker(ticker).history(period="1y", auto_adjust=True)
        return df if not df.empty else None
    except: return None

def indicators(df):
    df = df.copy()
    df["ATR"] = pd.concat([df["High"]-df["Low"], (df["High"]-df["Close"].shift(1)).abs(), (df["Low"]-df["Close"].shift(1)).abs()], axis=1).max(axis=1).ewm(span=14).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()
    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["Score"] = (np.where(df["EMA50"] > df["EMA200"], 30, 0) + 
                   np.where(df["Close"] > df["High"].rolling(20).max().shift(1), 20, 0) + 
                   np.where(df["RVOL"] > 1.5, 15, 10))
    return df

st.title("🦅 Stock Hunter Pro v21 - Professional Edition")

# 2. ปรับระบบการเลือกหุ้น
selected = st.multiselect("เลือกหุ้นที่ต้องการสแกน:", TICKERS, default=["NVDA", "PLTR", "AMD", "TSLA"])
capital = st.sidebar.number_input("Capital ($)", value=100000)
max_heat = st.sidebar.slider("Max Portfolio Heat (%)", 1.0, 10.0, 3.0)

results = []
for t in selected:
    df = load_data(t)
    if df is None: continue
    df = indicators(df)
    
    # ใช้ signal_row = iloc[-2]
    signal = df.iloc[-2]
    
    if signal["Score"] >= 75: action = "🚀 STRONG BUY"
    elif signal["Score"] >= 60: action = "🔥 BUY"
    else: action = "❌ AVOID"
    
    # คำนวณ Shares แบบจำกัดความเสี่ยง
    diff = signal["ATR"] * 2
    risk_dollars = capital * (max_heat / 100)
    shares = int(min(risk_dollars / diff, capital / signal["Close"]))
    
    results.append({"Ticker": t, "Action": action, "Score": round(signal["Score"], 1), "Shares": shares, "Price": round(signal["Close"], 2)})

st.table(pd.DataFrame(results))
