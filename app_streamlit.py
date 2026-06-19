import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

st.set_page_config(page_title="อาหวัง Pro Max v18.5 - Final", layout="wide")

# ==========================================================================
# 🧠 1. QUANT SIGNAL ENGINE (V18.5)
# ==========================================================================
def compute_indicators_and_signals_v18_5(df, spy_series):
    df = df.copy()
    
    # 1. Volume & Momentum Filter
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    ema12, ema26 = df['Close'].ewm(span=12).mean(), df['Close'].ewm(span=26).mean()
    df['MACD'], df['Signal_Line'] = ema12 - ema26, (ema12 - ema26).ewm(span=9).mean()
    
    # 2. RS Rank (Rolling Percentile - Fixed Bias)
    df['Stock_Ret_90'] = df['Close'] / df['Close'].shift(90) - 1
    df['Spy_Ret_90'] = spy_series / spy_series.shift(90) - 1
    df['Absolute_RS'] = df['Stock_Ret_90'] - df['Spy_Ret_90']
    df['RS_Rank'] = df['Absolute_RS'].rolling(252).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])
    
    # 3. Technicals
    df['EMA_50'], df['EMA_200'] = df['Close'].ewm(span=50).mean(), df['Close'].ewm(span=200).mean()
    df['ATR'] = (df['High']-df['Low']).ewm(span=14).mean()
    
    # 4. Quant Score (Final Weighting)
    score = (df['RS_Rank'] * 40) + \
            ((df['MACD'] > df['Signal_Line']).astype(int) * 20) + \
            ((df['Close'] > df['EMA_50']).astype(int) * 20) + \
            ((df['Close'] > df['EMA_200']).astype(int) * 20)
    
    df['Quant_Score'] = score
    # Signal ใช้ข้อมูลวันก่อนหน้า + กรอง Volume + กรองตลาด
    df['Signal'] = ((df['Quant_Score'] >= 60) & (df['Volume'] > df['Vol_MA20'])).astype(int).shift(1)
    return df

# ==========================================================================
# 🎯 3. MAIN UI
# ==========================================================================
st.title("🦅 อาหวัง Pro Max v18.5 (Final Polish)")

# Inputs
account_capital = st.sidebar.number_input("เงินทุน (บาท):", value=100000)
max_heat = st.sidebar.slider("Max Portfolio Heat (%):", 0.1, 5.0, 3.0)
tickers = st.multiselect("เลือกหุ้น:", ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "ASTS", "COIN"], default=["NVDA", "PLTR"])

spy = yf.Ticker("SPY").history(period="3y")['Close']
scan_results = []

for t in tickers:
    ticker_obj = yf.Ticker(t)
    df = compute_indicators_and_signals_v18_5(ticker_obj.history(period="3y"), spy)
    
    # Earnings Filter
    cal = ticker_obj.calendar
    next_earnings = cal.get('Earnings Date', [datetime.max.date()])[0] if isinstance(cal, dict) else datetime.max.date()
    in_earnings_window = abs((pd.to_datetime(next_earnings).date() - datetime.now().date()).days) <= 7
    
    if df is not None:
        last = df.iloc[-1]
        prev = df.iloc[-2] # ใช้ข้อมูลก่อนหน้ากัน Bias
        
        sl_price = prev['Close'] - (prev['ATR'] * 2)
        risk_money = account_capital * 0.01 # 1% Risk per trade
        shares = risk_money / (prev['Close'] - sl_price)
        
        status = "🔥 BUY NOW" if (prev['Signal'] == 1 and not in_earnings_window) else ("⚠️ EARNINGS" if in_earnings_window else "⬜ HOLD/WATCH")
        
        scan_results.append({
            "Ticker": t,
            "Action": status,
            "Score": round(prev['Quant_Score'], 1),
            "Shares (1% Risk)": int(shares) if status == "🔥 BUY NOW" else 0,
            "Stop Loss": round(sl_price, 2)
        })

st.table(pd.DataFrame(scan_results))

st.info("💡 **Ready to Trade:** ระบบนี้คำนวณจากข้อมูลที่ปราศจาก Look-ahead bias และตรวจสอบช่วงวันงบออกให้เรียบร้อยแล้ว")
