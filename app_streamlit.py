import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path

st.set_page_config(page_title="Stock Hunter Pro v21", layout="wide")

# --- 1. ฟังก์ชันคำนวณสถิติ (Expectancy & Performance) ---
def get_performance_metrics(journal_df):
    if journal_df.empty: return 0, 0, 0
    wins = journal_df[journal_df['R'] > 0]
    losses = journal_df[journal_df['R'] <= 0]
    win_rate = len(wins) / len(journal_df)
    profit_factor = abs(wins['R'].sum() / losses['R'].sum()) if losses['R'].sum() != 0 else 99
    expectancy = (win_rate * (wins['R'].mean() if not wins.empty else 0)) - ((1-win_rate) * abs(losses['R'].mean() if not losses.empty else 0))
    return win_rate, profit_factor, expectancy

# --- 2. Indicators & Scoring v21 ---
def indicators(df):
    df = df.copy()
    df["ATR"] = pd.concat([df["High"]-df["Low"], (df["High"]-df["Close"].shift(1)).abs(), (df["Low"]-df["Close"].shift(1)).abs()], axis=1).max(axis=1).ewm(span=14).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()
    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()
    
    # Score Engine
    score = np.zeros(len(df))
    score += np.where(df["EMA50"] > df["EMA200"], 30, 0)
    score += np.where(df["Close"] > df["High"].rolling(20).max().shift(1), 20, 0)
    score += np.where(df["RVOL"] > 1.5, 15, 10)
    df["Score"] = score
    return df

# --- 3. UI & Main Logic ---
st.title("🦅 Stock Hunter Pro v21")
capital = st.sidebar.number_input("Capital", value=100000)
max_heat = st.sidebar.slider("Max Portfolio Heat %", 1.0, 5.0, 3.0)

# Load Journal
journal_path = Path("trade_journal.csv")
journal_df = pd.read_csv(journal_path) if journal_path.exists() else pd.DataFrame(columns=["Ticker","R"])

# แสดง Dashboard สรุปผล
wr, pf, exp = get_performance_metrics(journal_df)
c1, c2, c3 = st.columns(3)
c1.metric("Win Rate", f"{wr:.1%}")
c2.metric("Profit Factor", f"{pf:.2f}")
c3.metric("Expectancy (R)", f"{exp:.2f}")

# สแกนหุ้น (ใช้ signal_row = iloc[-2])
results = []
for t in ["NVDA", "PLTR", "AMD", "TSLA"]:
    df = indicators(yf.Ticker(t).history(period="1y"))
    signal = df.iloc[-2] # <--- ใช้ข้อมูลก่อนปิดแท่งล่าสุด
    
    score = signal["Score"]
    if score >= 75: action = "🚀 STRONG BUY"
    elif score >= 60: action = "🔥 BUY"
    elif score >= 45: action = "👀 WATCH"
    else: action = "❌ AVOID"
    
    # คำนวณ Size ตาม Max Heat
    diff = signal["ATR"] * 2
    shares = int(min((capital * (max_heat/100)) / diff, capital / signal["Close"]))
    
    results.append({"Ticker": t, "Action": action, "Score": score, "Shares": shares})

st.dataframe(pd.DataFrame(results), use_container_width=True)
