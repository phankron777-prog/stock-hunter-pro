import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="อาหวัง Pro Max v17.1 - PM Hybrid Core", layout="wide")

# ==========================================================================
# 🧠 1. UNIFIED QUANT SIGNAL ENGINE (SINGLE SOURCE OF TRUTH)
# ==========================================================================
@st.cache_data(ttl=60)
def fetch_market_data(ticker, period="3y"):
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df is None or df.empty: return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        return df
    except: return None

def compute_indicators_and_signals(df, min_score, enforce_s2, rsi_low, rsi_high, spy_ret_90=0.0):
    if df is None or len(df) < 200: return None
    try:
        df = df.copy()
        
        # 1. Trend Zones (EMA Stage 2)
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # 2. Momentum Indicators
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9)) + 1e-9))
        
        # 3. ATR Math Pipeline (Fixed Order)
        df['Prev_Close'] = df['Close'].shift(1)
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()
        df['True_Range'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
        
        # Relative Strength Scoring Engine
        stock_ret_90 = (df['Close'].iloc[-1] - df['Close'].iloc[-90]) / (df['Close'].iloc[-90] + 1e-9)
        df['Absolute_RS'] = stock_ret_90 - spy_ret_90
        
        signals = []
        quant_scores = []
        
        for i in range(len(df)):
            if i < 200:
                signals.append(0)
                quant_scores.append(0)
                continue
                
            row = df.iloc[i]
            prev = df.iloc[i-1]
            
            score = 0
            is_stage_2 = (prev['Close'] > prev['EMA_20'] > prev['EMA_50'] > prev['EMA_200'])
            if is_stage_2: score += 40
            if prev['MACD'] > prev['Signal_Line']: score += 20
            if 50 <= prev['RSI'] <= 75: score += 20
            
            # RS Performance Bonus
            rs_bonus = min(max(prev['Absolute_RS'] * 100, 0), 20)
            score += rs_bonus
            
            quant_scores.append(score)
            
            pass_score = (score >= min_score)
            pass_trend = True if not enforce_s2 else is_stage_2
            pass_rsi = (rsi_low <= prev['RSI'] <= rsi_high)
            
            if pass_score and pass_trend and pass_rsi:
                signals.append(1) # BUY
            else:
                signals.append(0)
                
        df['Quant_Score'] = quant_scores
        df['Signal'] = signals
        return df
    except:
        return None

# ==========================================================================
# 📊 2. REALISTIC HYBRID BACKTEST ENGINE (WITH EXECUTION FRICTION & GAP RISK)
# ==========================================================================
def run_hybrid_backtest(ticker_dict, initial_capital=100000, risk_pct=1.0, slippage_pct=0.1):
    all_dates = sorted(list(set(date for df in ticker_dict.values() if df is not None for date in df.index)))
    capital = initial_capital
    portfolio_value = initial_capital
    active_trades = {}
    trade_log = []
    daily_equity = []
    
    for date in all_dates:
        # A. เช็คการชน Stop Loss หน้างานตอนเช้า (รวม Gap Down Risk ทะลุแผน)
        terminated_tickers = []
        for ticker, pos in active_trades.items():
            df = ticker_dict[ticker]
            if date in df.index:
                row = df.loc[date]
                
                if row['Open'] <= pos['sl_price']: # เกิด Gap Down เปิดต่ำกว่าจุดคัทลอส
                    exit_price = row['Open'] * (1 - slippage_pct/100)
                    pnl = (exit_price - pos['entry_price']) * pos['shares']
                    capital += pnl
                    trade_log.append({"ticker": ticker, "pnl": pnl, "R_match": pnl / pos['risk_amount']})
                    terminated_tickers.append(ticker)
                elif row['Low'] <= pos['sl_price']: # ชน Stop loss ปกติระหว่างวัน
                    exit_price = pos['sl_price'] * (1 - slippage_pct/100)
                    pnl = (exit_price - pos['entry_price']) * pos['shares']
                    capital += pnl
                    trade_log.append({"ticker": ticker, "pnl": pnl, "R_match": pnl / pos['risk_amount']})
                    terminated_tickers.append(ticker)
                else:
                    # Trailing Stop ลอยตามความได้เปรียบ
                    trail_sl = row['High'] - (row['ATR'] * 2.0)
                    if trail_sl > pos['sl_price']: pos['sl_price'] = trail_sl
                    
        for t in terminated_tickers: del active_trades[t]
            
        # B. ตรวจสอบการเปิดสัญญาณเข้าซื้อใหม่
        for ticker, df in ticker_dict.items():
            if ticker in active_trades: continue
            if date in df.index:
                row = df.loc[date]
                if row['Signal'] == 1 and capital > 0:
                    sl_distance = row['ATR'] * 2.0
                    if sl_distance <= 0: continue
                    
                    risk_money = capital * (risk_pct / 100)
                    execution_entry = row['Open'] * (1 + slippage_pct/100) # รวม Slippage ฝั่งซื้อ
                    shares = risk_money / sl_distance
                    
                    cost = shares * execution_entry
                    if cost > capital:
                        shares = capital / execution_entry
                        cost = shares * execution_entry
                        
                    if shares > 0:
                        capital -= cost
                        active_trades[ticker] = {
                            "entry_price": execution_entry,
                            "sl_price": execution_entry - sl_distance,
                            "shares": shares,
                            "risk_amount": risk_money
                        }
                        
        # คำนวณ Equity สิ้นวัน
        current_equity = capital
        for ticker, pos in active_trades.items():
            df = ticker_dict[ticker]
            if date in df.index: current_equity += df.loc[date]['Close'] * pos['shares']
        portfolio_value = current_equity
        daily_equity.append(portfolio_value)
        
    return trade_log, daily_equity

# ==========================================================================
# 🎛️ 3. SIDEBAR RISK CONFIGURATION
# ==========================================================================
st.sidebar.markdown("## 🦅 อาหวัง Pro Max v17.1")
st.sidebar.markdown("### `PM Hybrid Dashboard Core`")
st.sidebar.divider()

st.sidebar.markdown("### 🛡️ Global Fund Settings")
account_capital = st.sidebar.number_input("เงินทุนรวมในพอร์ต (บาท THB):", value=100000, step=10000)
base_risk_pct = st.sidebar.slider("ความเสี่ยงพื้นฐานต่อไม้ (Base Risk %):", 0.25, 2.0, 1.0, 0.25)
slippage_rate = st.sidebar.slider("Slippage + Cost แฝงต่อขา (%):", 0.0, 0.5, 0.1, 0.05)

st.sidebar.markdown("### 🎛️ Unified Control Rules")
min_score_cutoff = st.sidebar.slider("คะแนน Quant ขั้นต่ำที่ยอมรับได้:", 0, 100, 50, step=5)
enforce_stage2 = st.sidebar.toggle("กรองเฉพาะ Stage 2 (EMA ขาขึ้นเท่านั้น)", value=True)
rsi_filter = st.sidebar.slider("ระบุช่วง RSI วินัยหน้างาน:", 0, 100, (45, 80))

# Benchmark Load
spy = fetch_market_data("SPY", "1y")
spy_ret_90 = (spy['Close'].iloc[-1] - spy['Close'].iloc[-90]) / spy['Close'].iloc[-90] if spy is not None else 0.0

# ==========================================================================
# 🎯 4. MAIN USER INTERFACE (INTERACTIVE SCANNER + METRICS LOWER DECK)
# ==========================================================================
st.title("🦅 แผงควบคุมจัดลำดับและสแกนสดอัจฉริยะ (Interactive PM Style)")
st.caption("โหมดสแกนสดโต้ตอบหน้างาน แนะนำแผนกุมความเสี่ยงเรียรายตัว พร้อมระบบคำนวณ Expectancy กองทุนหลังบ้านจากกฎเดียวกัน")

# ตะกร้าเลือกหุ้นอิสระตามรูปแบบเวอร์ชัน v16
selected_tickers = st.multiselect(
    "📥 เลือกรายชื่อหุ้นเข้าตะกร้าสแกนหน้างาน (เพิ่ม/ลด ได้ตามใจชอบ):",
    ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "COIN", "ASTS"],
    default=["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL"]
)

st.divider()

if selected_tickers:
    scan_results = []
    backtest_dict = {}
    
    # วิ่งลูปดึงข้อมูลสดรายตัวมาสแกนแผนการเทรดให้ผู้ใช้เห็นทันที
    for t in selected_tickers:
        raw_1y = fetch_market_data(t, "1y")
        raw_3y = fetch_market_data(t, "3y") # ใช้ข้อมูล 3 ปีไปเตรียมทำ Backtest หลังบ้านสอดคล้องขนานกันไป
        
        df_p = compute_indicators_and_signals(raw_1y, min_score_cutoff, enforce_stage2, rsi_filter[0], rsi_filter[1], spy_ret_90)
        if raw_3y is not None:
            backtest_dict[t] = compute_indicators_and_signals(raw_3y, min_score_cutoff, enforce_stage2, rsi_filter[0], rsi_filter[1], spy_ret_90)
            
        if df_p is not None and not df_p.empty:
            last = df_p.iloc[-1]
            
            # คำนวณคำแนะนำขนาดซื้อขายไม้ปัจจุบันหน้างานจริง (Position Sizing Machine)
            sl_distance = last['ATR'] * 2.0
            execution_entry = last['Close'] * (1 + slippage_rate/100) # ราคาทุนที่คาดว่าจะได้เมื่อบวก slippage
            risk_money_amount = account_capital * (base_risk_pct / 100)
            
            if sl_distance > 0:
                recommended_shares = risk_money_amount / sl_distance
                recommended_cash = recommended_shares * execution_entry
            else:
                recommended_shares, recommended_cash = 0, 0
                
            signal_desc = "🟢 BUY / LONG" if last['Signal'] == 1 else "⬜ HOLD / WAIT"
            
            scan_results.append({
                "Ticker": t,
                "คะแนน Quant": round(last['Quant_Score'], 1),
                "ราคาสดล่าสุด": f"${last['Close']:.2f}",
                "RSI": round(last['RSI'], 1),
                "ระบบสั่งการ": signal_desc,
                "ซื้อกี่หุ้น (Shares)": int(recommended_shares) if last['Signal'] == 1 else 0,
                "เงินที่ต้องลง (บาท)": f"{recommended_cash:,.0f}" if last['Signal'] == 1 else "0",
                "จุด Stop Loss แนะนำ": f"${last['Close'] - sl_distance:.2f}" if last['Signal'] == 1 else "-",
                "Trailing Stop ปัจจุบัน": f"${last['Close'] - (last['ATR'] * 2.0):.2f}"
            })
            
    # 🏆 แสดงผลหน้าจอที่พี่ชอบ: ตารางสแกนระบุแผนนับไม้และขอบเขตคัทลอสรายหุ้น
    if scan_results:
        st.subheader("🏆 แผนปฏิบัติการคุมความเสี่ยงหน้างานรายหุ้น (Real-time Execution Plan)")
        rank_df = pd.DataFrame(scan_results).sort_values(by="คะแนน Quant", ascending=False)
        st.dataframe(rank_df, use_container_width=True, hide_index=True)
        
        # 📊 แผงล่าง: แสดงความสมจริงด้วย Institutional Core Math (Backtest ขนานอัตโนมัติ)
        st.divider()
        st.subheader("🦅 ผลทดสอบความได้เปรียบทางคณิตศาสตร์ของตะกร้าหุ้นนี้ (Institutional Backtest Deck)")
        st.caption("ระบบคำนวณสถิติย้อนหลัง 3 ปี ของเฉพาะหุ้นกลุ่มด้านบนที่คุณเลือก โดยอิงเกณฑ์ Slippage และคัทลอสตามวิกฤตราคาเปิดจริง")
        
        trade_log, daily_equity = run_hybrid_backtest(backtest_dict, initial_capital=account_capital, risk_pct=base_risk_pct, slippage_pct=slippage_rate)
        
        if trade_log:
            df_log = pd.DataFrame(trade_log)
            wins = df_log[df_log['pnl'] > 0]
            losses = df_log[df_log['pnl'] <= 0]
            
            total_trades = len(df_log)
            win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
            avg_win_r = wins['R_match'].mean() if len(wins) > 0 else 0
            avg_loss_r = losses['R_match'].mean() if len(losses) > 0 else 0
            
            expectancy = ((win_rate/100) * avg_win_r) + ((1 - win_rate/100) * avg_loss_r)
            profit_factor = wins['pnl'].sum() / abs(losses['pnl'].sum()) if len(losses) > 0 else wins['pnl'].sum()
            
            eq_series = pd.Series(daily_equity)
            returns = eq_series.pct_change().dropna()
            sharpe = (returns.mean() / (returns.std() + 1e-9)) * np.sqrt(252) if len(returns) > 0 else 0
            max_drawdown = ((eq_series.cummax() - eq_series) / eq_series.cummax()).max() * 100
            
            # Dashboard สรุปความคุ้มค่าก่อนลงเงินจริง
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Expectancy Per Trade", f"{expectancy:.2f} R", help="ค่าความคุ้มค่าต่อไม้ ยิ่งเกิน 0.20R ยิ่งดีมาก")
            m2.metric("Profit Factor", f"{profit_factor:.2f}")
            m3.metric("Sharpe Ratio พอร์ต", f"{sharpe:.2f}")
            m4.metric("Win Rate พอร์ตรวม", f"{win_rate:.1f}%")
            m5.metric("Max Drawdown จริง", f"{max_drawdown:.1f}%")
            
            c1, c2 = st.columns(2)
            with c1:
                st.metric("ขนาดกำไรเฉลี่ย (Average Win)", f"{avg_win_r:.2f} R")
            with c2:
                st.metric("ขนาดขาดทุนเฉลี่ย (Average Loss + Gap Risk)", f"{avg_loss_r:.2f} R")
        else:
            st.info("💡 ไม่มีประวัติการเทรดเกิดขึ้นในตะกร้าหุ้นที่เลือกตามเงื่อนไขกฎควบคุมนี้ในช่วง 3 ปี")
else:
    st.warning("⚠️ กรุณาเลือกรายชื่อหุ้นเข้าตะกร้าสแกนอย่างน้อย 1 ตัวที่ช่องด้านบน")
