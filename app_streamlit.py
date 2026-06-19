import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="อาหวัง Pro Max v19.5 - Final Build", layout="wide")

# ==========================================================================
# 🧠 1. QUANT SIGNAL ENGINE (V19.5 FINAL)
# ==========================================================================
def compute_indicators_and_signals(df, spy_series):
    df = df.copy()
    
    # 1. Correct True Range & ATR
    prev_close = df['Close'].shift(1)
    df['TR'] = pd.concat([df['High']-df['Low'], (df['High']-prev_close).abs(), (df['Low']-prev_close).abs()], axis=1).max(axis=1)
    df['ATR'] = df['TR'].ewm(span=14, adjust=False).mean()
    
    # 2. Volume & MACD
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    ema12, ema26 = df['Close'].ewm(span=12).mean(), df['Close'].ewm(span=26).mean()
    df['MACD'], df['Signal_Line'] = ema12 - ema26, (ema12 - ema26).ewm(span=9).mean()
    
    # 3. Correct RS Rank
    df['Stock_Ret_90'] = df['Close'] / df['Close'].shift(90) - 1
    df['Spy_Ret_90'] = spy_series / spy_series.shift(90) - 1
    df['Absolute_RS'] = df['Stock_Ret_90'] - df['Spy_Ret_90']
    df['RS_Rank'] = df['Absolute_RS'].rolling(252).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])
    
    # 4. Indicators
    df['EMA_50'], df['EMA_200'] = df['Close'].ewm(span=50).mean(), df['Close'].ewm(span=200).mean()
    df['Quant_Score'] = (df['RS_Rank']*40) + ((df['MACD'] > df['Signal_Line']).astype(int)*20) + \
                        ((df['Close'] > df['EMA_50']).astype(int)*20) + ((df['Close'] > df['EMA_200']).astype(int)*20)
    
    df['Signal'] = ((df['Quant_Score'] >= 60) & (df['Volume'] > df['Vol_MA20'])).astype(int).shift(1)
    return df

# ==========================================================================
# 🎯 2. MAIN APP
# ==========================================================================
st.title("🦅 อาหวัง Pro Max v19.5 (Final)")

# Load SPY
try:
    spy = yf.Ticker("SPY").history(period="3y")['Close']
    spy_ema200 = spy.ewm(span=200, adjust=False).mean().iloc[-1]
    market_ok = spy.iloc[-1] > spy_ema200
except:
    st.error("ไม่สามารถเชื่อมต่อข้อมูลตลาด (SPY)")
    st.stop()

# Settings
cap = st.sidebar.number_input("เงินทุน (บาท):", value=100000)
tickers = st.multiselect("หุ้นในตะกร้า:", ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "ASTS", "COIN"], default=["NVDA", "PLTR"])

if not market_ok:
    st.warning("⚠️ ตลาดอยู่ในสภาวะขาลง (SPY < EMA200) - ระบบลดความเสี่ยง: สัญญาณซื้อจะถูกระงับ")

results = []
for t in tickers:
    try:
        obj = yf.Ticker(t)
        df = compute_indicators_and_signals(obj.history(period="3y"), spy)
        
        # Earnings Filter (Robust)
        cal = obj.calendar
        earnings_date = cal.iloc[0].name if isinstance(cal, pd.DataFrame) else (list(cal.keys())[0] if isinstance(cal, dict) else datetime.max.date())
        in_earnings = abs((pd.to_datetime(earnings_date).date() - datetime.now().date()).days) <= 7
        
        last, prev = df.iloc[-1], df.iloc[-2]
        sl = prev['Close'] - (prev['ATR'] * 2)
        
        # Position Sizing: Risk 1% cap by capital
        risk_money = cap * 0.01
        shares = min(risk_money / (prev['Close'] - sl), cap / prev['Close'])
        
        # RR Ratio
        rr = ((prev['Close'] + (prev['ATR'] * 4)) - prev['Close']) / (prev['Close'] - sl)
        
        results.append({
            "Ticker": t,
            "Action": "🔥 BUY NOW" if (prev['Signal'] == 1 and market_ok and not in_earnings) else ("⚠️ EARNINGS" if in_earnings else "⬜ HOLD"),
            "Score": round(prev['Quant_Score'], 1),
            "Shares": int(shares) if prev['Signal'] == 1 else 0,
            "Stop Loss": round(sl, 2),
            "RR Ratio": round(rr, 2)
        })
    except: continue

st.table(pd.DataFrame(results))
