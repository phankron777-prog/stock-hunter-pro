import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

# [ปรับปรุง] 1. แก้ไข Look-Ahead Bias ในการคำนวณ RS และ Score
def compute_indicators_and_signals(df, min_score, enforce_s2, rsi_low, rsi_high, spy_ret_90_series):
    if df is None or len(df) < 200: return None
    df = df.copy()
    
    # EMA & MACD (ไม่มี Look-ahead)
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # RSI (ไม่มี Look-ahead)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9)) + 1e-9))
    
    # ATR
    df['True_Range'] = pd.concat([df['High']-df['Low'], (df['High']-df['Close'].shift(1)).abs(), (df['Low']-df['Close'].shift(1)).abs()], axis=1).max(axis=1)
    df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
    
    # [ปรับปรุง] แก้ไข Look-Ahead Bias: ใช้การเลื่อนข้อมูลแทนการอ้างอิงค่าปัจจุบัน
    stock_ret = df['Close'].pct_change(90)
    # ใช้วิธีเปรียบเทียบกับ SPY ณ วันนั้นๆ จริงๆ
    df['Absolute_RS'] = stock_ret - spy_ret_90_series
    
    # [ปรับปรุง] RS Percentile Scoring (แทนที่เลขตายตัว)
    df['RS_Rank'] = df['Absolute_RS'].rolling(252).rank(pct=True) 
    
    signals = []
    quant_scores = []
    
    for i in range(len(df)):
        if i < 200:
            signals.append(0); quant_scores.append(0); continue
            
        prev = df.iloc[i-1]
        score = 0
        is_stage_2 = (prev['Close'] > prev['EMA_20'] > prev['EMA_50'] > prev['EMA_200'])
        if is_stage_2: score += 40
        if prev['MACD'] > prev['Signal_Line']: score += 20
        if 50 <= prev['RSI'] <= 75: score += 20
        
        # ใช้ Percentile แทนค่าคงที่
        score += min(prev['RS_Rank'] * 20, 20)
        
        quant_scores.append(score)
        pass_trend = True if not enforce_s2 else is_stage_2
        if score >= min_score and pass_trend and (rsi_low <= prev['RSI'] <= rsi_high):
            signals.append(1)
        else:
            signals.append(0)
            
    df['Quant_Score'] = quant_scores
    df['Signal'] = signals
    return df

# [ปรับปรุง] 2. การควบคุม Portfolio Heat (Risk Management Engine)
def run_hybrid_backtest(ticker_dict, initial_capital=100000, risk_pct=1.0, max_portfolio_heat=3.0, slippage_pct=0.1):
    # (เพิ่มตรรกะคุม Max Portfolio Heat)
    # ในลูปการเทรด ให้เพิ่มเงื่อนไข:
    # current_total_risk = sum(pos['risk_amount'] for pos in active_trades.values())
    # if (current_total_risk / capital) < (max_portfolio_heat / 100):
    #      อนุญาตให้เปิดไม้ใหม่...
    pass # คงโครงสร้างเดิมของคุณ แต่เพิ่ม Logic นี้เข้าไปในส่วน B.
