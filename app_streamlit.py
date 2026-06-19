import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# ==========================================================================
# 🧠 1. QUANT SIGNAL ENGINE (v19.5 Final Polish)
# ==========================================================================
def compute_indicators_and_signals(df, spy, qqq, iwm):
    df = df.copy()
    
    # 1. ATR (Wilder's) & RVOL (Relative Volume)
    prev_close = df['Close'].shift(1)
    tr = pd.concat([df['High']-df['Low'], (df['High']-prev_close).abs(), (df['Low']-prev_close).abs()], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()
    df['RVOL'] = df['Volume'] / df['Volume'].rolling(20).mean()
    
    # 2. Breakout Filter
    df['High_20'] = df['High'].rolling(20).max().shift(1)
    df['Breakout'] = df['Close'] > df['High_20']
    
    # 3. Market Breadth (2 out of 3 Regime)
    def is_bullish(idx): return idx.iloc[-1] > idx.ewm(span=200, adjust=False).mean().iloc[-1]
    breadth_score = sum([is_bullish(spy), is_bullish(qqq), is_bullish(iwm)])
    market_ok = breadth_score >= 2
    
    # 4. Quant Score + Filters
    df['Signal'] = ((df['RVOL'] > 1.5) & (df['Breakout']) & (market_ok)).astype(int).shift(1)
    return df

# ==========================================================================
# 🎯 2. PORTFOLIO & JOURNAL ENGINE (Actionable)
# ==========================================================================
# สมมติ st.session_state.active_trades เก็บ {ticker: {'risk': 0.01, 'entry': 100}}
def check_portfolio_heat(active_trades, account_capital, max_heat=0.03):
    current_risk = sum([trade['risk'] for trade in active_trades.values()])
    return (current_risk / account_capital) < max_heat

# เก็บ Journal (CSV)
def save_trade(ticker, entry, sl, reason):
    log = pd.DataFrame([{'Date': datetime.now(), 'Ticker': ticker, 'Entry': entry, 'SL': sl, 'Reason': reason}])
    log.to_csv("trade_journal.csv", mode='a', header=not pd.io.common.file_exists("trade_journal.csv"), index=False)

# ==========================================================================
# 🚀 Final Execution Logic
# ==========================================================================
# ในลูปสแกน:
# if not check_portfolio_heat(st.session_state.active_trades, cap):
#     status = "❌ OVER HEAT"
# else:
#     status = "🔥 BUY NOW" if signal else "⬜ HOLD"
