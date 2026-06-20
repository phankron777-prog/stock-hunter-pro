import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Stock Hunter Pro v20.5 Pro", layout="wide")

TICKERS = ["NVDA","PLTR","AMD","TSLA","META","AAPL","MSFT","GOOGL","AMZN","NFLX","COIN","ASTS"]

@st.cache_data(ttl=3600)
def load_data(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1y", auto_adjust=True)
        # ดึงข้อมูลวันประกาศงบ (Earnings)
        earnings_date = t.calendar.iloc[0]['Earnings Date'] if 'calendar' in dir(t) and not t.calendar.empty else None
        return df, earnings_date
    except: return None, None

def indicators(df):
    df = df.copy()
    df["ATR"] = pd.concat([df["High"]-df["Low"], (df["High"]-df["Close"].shift(1)).abs(), (df["Low"]-df["Close"].shift(1)).abs()], axis=1).max(axis=1).ewm(span=14).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()
    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["Score"] = (np.where(df["EMA50"] > df["EMA200"], 30, 0) + 
                   np.where(df["Close"] > df["High"].rolling(20).max().shift(1), 20, 0) + 
                   np.where(df["RVOL"] > 1.2, 15, 0))
    return df

def check_market():
    market_checks = 0
    for t in ["SPY", "QQQ", "IWM"]:
        data = yf.Ticker(t).history(period="1y")
        if data["Close"].iloc[-1] > data["Close"].ewm(span=200).mean().iloc[-1]:
            market_checks += 1
    return market_checks >= 2

# UI
st.title("🦅 Stock Hunter Pro v20.5 Professional")
capital = st.sidebar.number_input("Capital", value=100000)
max_heat = st.sidebar.slider("Max Portfolio Heat (%)", 1.0, 5.0, 3.0)
selected = st.multiselect("Stocks", TICKERS, default=["NVDA","PLTR","AMD"])

market_ok = check_market()
st.write(f"Market Filter (2/3): {'✅ RISK ON' if market_ok else '❌ RISK OFF'}")

results = []
summary = {"🚀 STRONG BUY": 0, "🔥 BUY": 0, "👀 WATCH": 0, "❌ AVOID": 0}

for t in selected:
    df, earnings = load_data(t)
    if df is None: continue
    df = indicators(df)
    
    signal = df.iloc[-2]
    score = signal["Score"]
    
    # Check Earnings
    is_earnings = False
    if earnings:
        days_to_earnings = (earnings - pd.Timestamp.now()).days
        if 0 <= days_to_earnings <= 3: is_earnings = True

    # Scoring
    if score >= 75: action = "🚀 STRONG BUY"
    elif score >= 60: action = "🔥 BUY"
    elif score >= 45: action = "👀 WATCH"
    else: action = "❌ AVOID"
    
    summary[action] = summary.get(action, 0) + 1
    
    # Position Sizing
    diff = signal["ATR"] * 2
    shares = int(min((capital * (max_heat/100)) / diff, capital / signal["Close"]))
    
    results.append({
        "Ticker": t, 
        "Action": f"{action} {'⚠️ EARNINGS' if is_earnings else ''}",
        "Score": round(score, 1), 
        "Shares": shares
    })

# Dashboard
c1, c2, c3 = st.columns(3)
c1.metric("Strong Buy", summary["🚀 STRONG BUY"])
c2.metric("Buy", summary["🔥 BUY"])
c3.metric("Watch", summary["👀 WATCH"])

st.dataframe(pd.DataFrame(results), use_container_width=True)
