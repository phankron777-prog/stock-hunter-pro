import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from pathlib import Path  # <--- เพิ่มบรรทัดนี้เข้ามาครับ

st.set_page_config(page_title="Stock Hunter Pro v20 Ultimate", layout="wide")

TICKERS = ["NVDA","PLTR","AMD","TSLA","META","AAPL","MSFT","GOOGL","AMZN","NFLX","COIN","ASTS"]

@st.cache_data(ttl=3600)
def load_data(ticker, period="3y"):
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        return None if df.empty else df
    except:
        return None

def indicators(df, spy_close):
    df = df.copy()
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(span=14, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()
    df["VolMA20"] = df["Volume"].rolling(20).mean()
    df["RVOL"] = df["Volume"] / df["VolMA20"]

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACDSignal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    stock90 = df["Close"] / df["Close"].shift(90) - 1
    spy = pd.DataFrame(index=df.index)
    spy["Close"] = spy_close.reindex(df.index).ffill()
    spy90 = spy["Close"] / spy["Close"].shift(90) - 1

    rs = stock90 - spy90
    df["RSRank"] = rs.rolling(252).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x.dropna()) > 0 else np.nan
    )
    df["Breakout"] = df["Close"] > df["High"].rolling(20).max().shift(1)

    score = np.zeros(len(df))
    score += np.where(df["EMA50"] > df["EMA200"], 30, 0)
    score += np.nan_to_num(df["RSRank"] * 25)
    score += np.where(df["Breakout"], 20, 0)
    score += np.where(df["RVOL"] > 2, 15, np.where(df["RVOL"] > 1.5, 10, np.where(df["RVOL"] > 1.2, 5, 0)))
    score += np.where(df["MACD"] > df["MACDSignal"], 10, 0)

    df["Score"] = score
    return df

# --- UI และการประมวลผล ---
st.sidebar.title("⚙️ Risk Settings")
capital = st.sidebar.number_input("Capital", value=100000)
risk_pct = st.sidebar.slider("Risk % per Trade", 0.25, 2.0, 1.0, 0.25)
selected = st.multiselect("Stocks", TICKERS, default=["NVDA","PLTR","AMD","TSLA"])

st.title("🦅 Stock Hunter Pro v20 Ultimate")

spy = load_data("SPY")
qqq = load_data("QQQ")
iwm = load_data("IWM")

market_ok = False
if spy is not None and qqq is not None and iwm is not None:
    checks = 0
    for x in [spy, qqq, iwm]:
        if not x.empty:
            ema200 = x["Close"].ewm(span=200, adjust=False).mean().iloc[-1]
            if x["Close"].iloc[-1] > ema200:
                checks += 1
    market_ok = checks >= 2

st.write(f"Market Filter: {'✅ RISK ON' if market_ok else '❌ RISK OFF'}")

results = []
for t in selected:
    df = load_data(t)
    if df is None: continue
    df = indicators(df, spy["Close"])
    if len(df) < 252: continue
    
    row = df.iloc[-1]
    entry = float(row["Close"])
    stop = float(entry - (row["ATR"] * 2))
    risk_amount = capital * (risk_pct / 100)
    diff = max(entry - stop, 0.01)
    
    results.append({
        "Ticker": t,
        "Action": "BUY" if (row["Score"] >= 70 and market_ok) else "WATCH",
        "Score": round(row["Score"], 1),
        "Entry": round(entry, 2),
        "Stop": round(stop, 2),
        "Shares": int(risk_amount / diff),
        "RR": round((4 * row["ATR"]) / diff, 2)
    })

if results:
    st.dataframe(pd.DataFrame(results).sort_values("Score", ascending=False), use_container_width=True, hide_index=True)

# ป้องกัน Error ของ Journal
journal_path = Path("trade_journal.csv")
if not journal_path.exists():
    pd.DataFrame(columns=["Date","Ticker","Entry","Stop","Shares","Risk","Result","R"]).to_csv(journal_path, index=False)

st.success("v20 Ultimate Ready")
