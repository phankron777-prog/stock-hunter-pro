import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# ==========================================================================
# 🧠 1. QUANT SIGNAL ENGINE (V19 FINAL - MATHEMATICALLY CORRECTED)
# ==========================================================================
def compute_indicators_and_signals_v19(df, spy_series):
    df = df.copy()
    
    # 1. Correct ATR Calculation (The True Range)
    prev_close = df['Close'].shift(1)
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - prev_close).abs()
    tr3 = (df['Low'] - prev_close).abs()
    df['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = df['TR'].ewm(span=14, adjust=False).mean()
    
    # 2. Volume & Momentum (MACD)
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    ema12, ema26 = df['Close'].ewm(span=12).mean(), df['Close'].ewm(span=26).mean()
    df['MACD'], df['Signal_Line'] = ema12 - ema26, (ema12 - ema26).ewm(span=9).mean()
    
    # 3. Correct RS Calculation
    df['Stock_Ret_90'] = df['Close'] / df['Close'].shift(90) - 1
    df['Spy_Ret_90'] = spy_series / spy_series.shift(90) - 1
    df['Absolute_RS'] = df['Stock_Ret_90'] - df['Spy_Ret_90']
    df['RS_Rank'] = df['Absolute_RS'].rolling(252).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])
    
    # 4. Technicals
    df['EMA_50'], df['EMA_200'] = df['Close'].ewm(span=50).mean(), df['Close'].ewm(span=200).mean()
    
    # 5. Quant Score
    score = (df['RS_Rank'] * 40) + ((df['MACD'] > df['Signal_Line']).astype(int) * 20) + \
            ((df['Close'] > df['EMA_50']).astype(int) * 20) + ((df['Close'] > df['EMA_200']).astype(int) * 20)
    df['Quant_Score'] = score
    df['Signal'] = ((df['Quant_Score'] >= 60) & (df['Volume'] > df['Vol_MA20'])).astype(int).shift(1)
    return df

# ==========================================================================
# 🎯 2. ACTIONABLE SCANNER (WITH RR RATIO & REGIME FILTER)
# ==========================================================================
# (ในส่วนของ Loop)
# ...
market_bullish = spy.iloc[-1] > spy.ewm(span=200, adjust=False).mean().iloc[-1]

# 1. Earnings Filter (Error-proof)
def get_earnings_date(ticker_obj):
    try:
        cal = ticker_obj.calendar
        if isinstance(cal, pd.DataFrame): return cal.iloc[0].name
        if isinstance(cal, dict): return list(cal.keys())[0]
        return datetime.max.date()
    except: return datetime.max.date()

# 2. Inside the Loop:
sl_price = prev['Close'] - (prev['ATR'] * 2)
risk_money = account_capital * (base_risk_pct / 100)
raw_shares = risk_money / (prev['Close'] - sl_price)

# 3. Final Sizing Cap
shares = min(raw_shares, account_capital / prev['Close']) 

# 4. RR Ratio Calculation
# Assume Target = Entry + (2 * ATR)
tp_price = prev['Close'] + (prev['ATR'] * 4) 
rr_ratio = (tp_price - prev['Close']) / (prev['Close'] - sl_price)
# ...
