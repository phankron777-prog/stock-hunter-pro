import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Stock Hunter Pro v21", layout="wide")

# 1. ตั้งค่ารายการหุ้นเริ่มต้น แต่คุณสามารถพิมพ์เพิ่มหรือลบได้ในช่อง UI
DEFAULT_TICKERS = ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL"]

@st.cache_data(ttl=3600)
def load_data(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1y", auto_adjust=True)
        return df if not df.empty else None
    except: return None

def indicators(df):
    df = df.copy()
    df["ATR"] = pd.concat([df["High"]-df["Low"], (df["High"]-df["Close"].shift(1)).abs(), (df["Low"]-df["Close"].shift(1)).abs()], axis=1).max(axis=1).ewm(span=14).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()
    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["Score"] = (np.where(df["Close"] > df["EMA50"], 20, 0) + 
                   np.where(df["Close"] > df["EMA200"], 20, 0) + 
                   np.where(df["RVOL"] > 1.1, 20, 0) + 
                   np.where(df["Close"] > df["Close"].shift(20), 20, 0))
    return df

st.title("🦅 Stock Hunter Pro v21")

# 2. ฟังก์ชันให้คุณพิมพ์ชื่อหุ้นเพิ่มเองได้ (User Input)
user_input = st.text_input("พิมพ์ชื่อหุ้นที่ต้องการ (คั่นด้วยลูกน้ำ เช่น AAPL, MSFT, SMCI):", "NVDA, PLTR, AMD, TSLA")
tickers = [t.strip().upper() for t in user_input.split(",")]

capital = st.sidebar.number_input("Capital", value=100000)

results = []
for t in tickers:
    df = load_data(t)
    if df is None: continue
    df = indicators(df)
    
    score = df["Score"].iloc[-1]
    
    if score >= 70: action = "🚀 STRONG BUY"
    elif score >= 50: action = "🔥 BUY"
    elif score >= 30: action = "👀 WATCH"
    else: action = "❌ AVOID"
    
    results.append({
        "Ticker": t, 
        "Action": action, 
        "Score": round(score, 1),
        "Price": round(df["Close"].iloc[-1], 2)
    })

st.dataframe(pd.DataFrame(results), use_container_width=True)
