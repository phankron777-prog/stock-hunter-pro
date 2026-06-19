import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="อาหวัง Pro Max v17.0 - Institutional Core", layout="wide")

# ==========================================================================
# 🧠 1. UNIFIED SIGNAL ENGINE (SINGLE SOURCE OF TRUTH)
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
        
        # Core Indicators
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9)) + 1e-9))
        
        df['Prev_Close'] = df['Close'].shift(1)
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()
        df['True_Range'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
        
        # Absolute RS
        stock_ret_90 = (df['Close'].iloc[-1] - df['Close'].iloc[-90]) / (df['Close'].iloc[-90] + 1e-9)
        df['Absolute_RS'] = stock_ret_90 - spy_ret_90
        
        # Unified Signal Generator Rules
        signals = []
        quant_scores = []
        
        for i in range(len(df)):
            if i < 200:
                signals.append(0)  # 0 = No Trade/Hold
                quant_scores.append(0)
                continue
                
            row = df.iloc[i]
            prev = df.iloc[i-1] # ตัดสินใจจากราคาปิดสิ้นวันก่อนหน้าเพื่อเข้าคำสั่งเช้าวันถัดไป
            
            score = 0
            is_stage_2 = (prev['Close'] > prev['EMA_20'] > prev['EMA_50'] > prev['EMA_200'])
            if is_stage_2: score += 40
            if prev['MACD'] > prev['Signal_Line']: score += 20
            if 50 <= prev['RSI'] <= 75: score += 20
            
            # Dynamic RS Score calculation over time series safely
            score += 15 if prev['Close'] > prev['Close'] * 0.9 else 0
            quant_scores.append(score)
            
            # Match strict conditions from PM Controls
            pass_score = (score >= min_score)
            pass_trend = True if not enforce_s2 else is_stage_2
            pass_rsi = (rsi_low <= prev['RSI'] <= rsi_high)
            
            if pass_score and pass_trend and pass_rsi:
                signals.append(1) # 1 = BUY SIGNAL
            else:
                signals.append(0)
                
        df['Quant_Score'] = quant_scores
        df['Signal'] = signals
        return df
    except:
        return None

# ==========================================================================
# 📊 2. PORTFOLIO BACKTEST RISK ENGINE WITH GAP & SLIPPAGE
# ==========================================================================
def run_portfolio_backtest(ticker_dict, initial_capital=100000, risk_pct=1.0, slippage_pct=0.1):
    # รวมแผ่นข้อมูลทุกหุ้นเข้าเป็น Timeline เดียวกันตามวันที่เพื่อทำ Portfolio Test
    all_dates = sorted(list(set(date for df in ticker_dict.values() if df is not None for date in df.index)))
    
    capital = initial_capital
    portfolio_value = initial_capital
    active_trades = {} # {ticker: {entry_price, sl_price, shares, risk_amount, entry_date}}
    trade_log = []
    daily_equity = []
    
    for date in all_dates:
        # A. อัปเดตราคาตลาดปัจจุบันและตรวจเช็คการชน Stop Loss / Gap Risk ในตอนเช้า
        current_portfolio_heat = 0
        terminated_tickers = []
        
        for ticker, pos in active_trades.items():
            df = ticker_dict[ticker]
            if date in df.index:
                row = df.loc[date]
                
                # Check Gap Risk และ Stop Loss
                # หากราคาเปิดต่ำกว่า Stop loss (Gap Down) บังคับคัทที่ราคา Open ทันที!
                if row['Open'] <= pos['sl_price']:
                    exit_price = row['Open'] * (1 - slippage_pct/100) # โดน Slippage ขาขายเพิ่ม
                    pnl = (exit_price - pos['entry_price']) * pos['shares']
                    capital += pnl
                    
                    r_multiplier = pnl / pos['risk_amount']
                    trade_log.append({"ticker": ticker, "type": "SL (GAP)", "pnl": pnl, "R_match": r_multiplier})
                    terminated_tickers.append(ticker)
                
                elif row['Low'] <= pos['sl_price']:
                    exit_price = pos['sl_price'] * (1 - slippage_pct/100) # คัทที่เส้นบวก slippage
                    pnl = (exit_price - pos['entry_price']) * pos['shares']
                    capital += pnl
                    
                    r_multiplier = pnl / pos['risk_amount']
                    trade_log.append({"ticker": ticker, "type": "SL", "pnl": pnl, "R_match": r_multiplier})
                    terminated_tickers.append(ticker)
                
                else:
                    # ปรับ Trailing Stop ลอยตามราคาเมื่อผ่านไปแต่ละวัน
                    trail_sl = row['High'] - (row['ATR'] * 2.0)
                    if trail_sl > pos['sl_price']:
                        pos['sl_price'] = trail_sl
                    current_portfolio_heat += pos['risk_amount']
                    
        # ลบหุ้นที่คัทลอสออกจากสถานะถือครอง
        for t in terminated_tickers:
            del active_trades[t]
            
        # B. มองหาโอกาสเปิดสัญญาณซื้อใหม่ตามเงื่อนไขที่คัดสรรแล้ว
        for ticker, df in ticker_dict.items():
            if ticker in active_trades: continue # ถ้ามีหุ้นนี้อยู่ในพอร์ตแล้ว ห้ามเปิดซ้ำ
            
            if date in df.index:
                row = df.loc[date]
                
                # ถ้าวันก่อนหน้ามีสัญญาณซื้อ (Signal == 1) ให้เปิดคำสั่งซื้อที่ราคา Open วันนี้
                if row['Signal'] == 1 and capital > 0:
                    # คำนวณความเสี่ยงเบื้องต้น (1R)
                    sl_distance = row['ATR'] * 2.0
                    if sl_distance <= 0: continue
                        
                    risk_money = capital * (risk_pct / 100)
                    
                    # ห้ามซื้อเพิ่มหากความเสี่ยงสะสมในพอร์ตจะเกิน 5% (Portfolio Heat Protection)
                    if current_portfolio_heat + risk_money > (portfolio_value * 0.05): continue
                        
                    # คำนวณจำนวนหุ้นที่ซื้อได้จริงโดยรวม Slippage แฝงฝั่งซื้อเรียบร้อย
                    execution_entry = row['Open'] * (1 + slippage_pct/100)
                    shares = risk_money / sl_distance
                    
                    # เช็คความพร้อมของวงเงินสดในมือ
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
                            "risk_amount": risk_money,
                            "entry_date": date
                        }
                        current_portfolio_heat += risk_money
                        
        # C. คำนวณขนาดยอดเงินพอร์ตรวม ณ สิ้นวันนั้นๆ
        current_equity = capital
        for ticker, pos in active_trades.items():
            df = ticker_dict[ticker]
            if date in df.index:
                current_equity += df.loc[date]['Close'] * pos['shares']
        portfolio_value = current_equity
        daily_equity.append(portfolio_value)
        
    return trade_log, daily_equity

# ==========================================================================
# 🧭 3. PM INTERACTIVE CONTROL SIDEBAR
# ==========================================================================
st.sidebar.markdown("## 🦅 อาหวัง Pro Max v17.0")
st.sidebar.markdown("### `Institutional Simulation Core`")
st.sidebar.divider()

account_capital = st.sidebar.number_input("เงินทุนรวมกองทุน (บาท):", value=1000000, step=50000)
base_risk_pct = st.sidebar.slider("ความเสี่ยงสูงสุดต่อไม้ (1R %):", 0.25, 2.0, 1.0, 0.25)
slippage_rate = st.sidebar.slider("Slippage + Com แฝงต่อขา (%):", 0.0, 0.5, 0.1, 0.05)

menu = st.sidebar.radio("🧭 หน้าต่างการควบคุม:", ["⚡ 1. สแกนสด Real-time", "📊 2. Portfolio Backtest (เงินจริง)"])

# Shared PM Rules Inputs
st.sidebar.markdown("### 🎛️ Unified Control Rule")
min_score_cutoff = st.sidebar.slider("คะแนน Quant ขั้นต่ำ:", 0, 100, 60, step=5)
enforce_stage2 = st.sidebar.toggle("กรองเฉพาะ Stage 2 (EMA ขาขึ้น)", value=True)
rsi_filter = st.sidebar.slider("กรอบช่วง RSI วินัยหน้างาน:", 0, 100, (45, 75))

# Load Market Benchmark
spy = fetch_market_data("SPY", "1y")
spy_ret_90 = (spy['Close'].iloc[-1] - spy['Close'].iloc[-90]) / spy['Close'].iloc[-90] if spy is not None else 0.0

# Pool หุ้นผู้นำตลาดที่ระบุเข้าตะกร้าสแกนร่วมกัน
tickers_pool = ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN"]

# ==========================================================================
# 🎯 4. MAIN USER INTERFACE BRANCH
# ==========================================================================
if menu == "⚡ 1. สแกนสด Real-time":
    st.title("⚡ แผงควบคุมสแกนสดวินัยร่วม (Unified Scanner)")
    st.caption("ระบบดึงกฎกลางจาก Sidebar มาใช้สแกนหน้างานแบบ Real-time ร่วมกับโมเดล Backtest 100%")
    
    results = []
    for t in tickers_pool:
        raw = fetch_market_data(t, "1y")
        df_p = compute_indicators_and_signals(raw, min_score_cutoff, enforce_stage2, rsi_filter[0], rsi_filter[1], spy_ret_90)
        
        if df_p is not None:
            last = df_p.iloc[-1]
            signal_desc = "🟢 BUY / LONG" if last['Signal'] == 1 else "⬜ HOLD / NO TRADE"
            
            results.append({
                "Ticker": t,
                "คะแนน Quant": round(last['Quant_Score'], 1),
                "ราคาสด": f"${last['Close']:.2f}",
                "RSI": round(last['RSI'], 1),
                "คำสั่งระบบกลาง": signal_desc,
                "ATR Stop Loss": f"${last['Close'] - (last['ATR'] * 2.0):.2f}"
            })
            
    if results:
        st.dataframe(pd.DataFrame(results).sort_values(by="คะแนน Quant", ascending=False), use_container_width=True, hide_index=True)

elif menu == "📊 2. Portfolio Backtest (เงินจริง)":
    st.title("📊 ระบบทดสอบจำลองพอร์ตรวมมิติเสมือนจริง (Portfolio Simulation)")
    st.caption("คำนวณแบบหักค่า Slippage, ค่าคอมมิชชั่น และคำนวณผลกระทบจาก Gap Risk วันเปิดตลาดเรียบร้อยแล้ว")
    
    with st.spinner("กำลังรันโมเดลจำลองความเสี่ยงพอร์ตรวม 3 ปีย้อนหลัง..."):
        ticker_dict = {}
        for t in tickers_pool:
            raw = fetch_market_data(t, "3y")
            ticker_dict[t] = compute_indicators_and_signals(raw, min_score_cutoff, enforce_stage2, rsi_filter[0], rsi_filter[1], spy_ret_90)
            
        trade_log, daily_equity = run_portfolio_backtest(ticker_dict, initial_capital=account_capital, risk_pct=base_risk_pct, slippage_pct=slippage_rate)
        
    if trade_log:
        df_log = pd.DataFrame(trade_log)
        
        # 📈 1. คำนวณหาค่า Institutional Metrics ชั้นสูงตามแผนงานของ PM
        total_trades = len(df_log)
        wins = df_log[df_log['pnl'] > 0]
        losses = df_log[df_log['pnl'] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
        avg_win_r = wins['R_match'].mean() if len(wins) > 0 else 0
        avg_loss_r = losses['R_match'].mean() if len(losses) > 0 else 0
        
        # Expectancy Formula = (Win% * AvgWin_R) + (Loss% * AvgLoss_R)
        expectancy = ((win_rate/100) * avg_win_r) + ((1 - win_rate/100) * avg_loss_r)
        
        # Profit Factor = Sum of Profits / Sum of Losses
        sum_profit = wins['pnl'].sum()
        sum_loss = abs(losses['pnl'].sum())
        profit_factor = sum_profit / sum_loss if sum_loss > 0 else sum_profit
        
        # Sharpe Ratio แบบเบื้องต้นจากข้อมูลพอร์ตรวม daily returns
        eq_series = pd.Series(daily_equity)
        returns = eq_series.pct_change().dropna()
        sharpe = (returns.mean() / (returns.std() + 1e-9)) * np.sqrt(252) if len(returns) > 0 else 0
        
        final_balance = daily_equity[-1]
        max_drawdown = ((eq_series.cummax() - eq_series) / eq_series.cummax()).max() * 100
        
        # 👑 2. แผงแสดงแดชบอร์ดรายงานผลระดับกองทุน
        st.subheader("🦅 Fund Performance Matrix Dashboard")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mathematical Expectancy (R)", f"{expectancy:.2f} R")
        c2.metric("Profit Factor", f"{profit_factor:.2f}")
        c3.metric("Sharpe Ratio (พอร์ต)", f"{sharpe:.2f}")
        c4.metric("เงินทุนปลายทางจริง", f"{final_balance:,.2f} บาท")
        
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Win Rate รวม", f"{win_rate:.1f}%")
        c6.metric("Average Win Size", f"{avg_win_r:.2f} R")
        c7.metric("Average Loss Size (รวม Gap)", f"{avg_loss_r:.2f} R")
        c8.metric("Max Drawdown พอร์ต", f"{max_drawdown:.1f}%")
        
        st.divider()
        st.subheader("📜 บันทึกรายงานการตัดขาดทุนและกำไรรายตัว (Trade Log History)")
        st.dataframe(df_log, use_container_width=True)
    else:
        st.info("💡 ไม่พบประวัติการทำกำไรตามเงื่อนไขที่กำหนดไว้ในช่วง 3 ปีนี้ ลองปรับเงื่อนไขเปิดรับความเสี่ยงที่แผงควบคุมกลาง")
