import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="อาหวัง Pro Max v17.2 - Zero-Bias Core", layout="wide")

# ==========================================================================
# 🧠 1. UNIFIED ZERO-BIAS SIGNAL ENGINE (ROLLING COMPUTE ONLY)
# ==========================================================================
@st.cache_data(ttl=60)
def fetch_market_data(ticker, period="3y"):
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df is None or df.empty: return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        return df
    except: return None

def compute_rolling_indicators_and_signals(df):
    if df is None or len(df) < 200: return None
    try:
        df = df.copy()
        
        # Trend Zones (Stage 2 Metrics)
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # Momentum Indicators
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9)) + 1e-9))
        
        # True ATR Sizing Metrics
        df['Prev_Close'] = df['Close'].shift(1)
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()
        df['True_Range'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
        
        # 🔥 แก้ไข LOOK-AHEAD BIAS: Rolling 90 วัน
        df['Rolling_Ret_90'] = (df['Close'] / df['Close'].shift(90)) - 1.0
        
        return df
    except:
        return None

def apply_cross_sectional_ranking(ticker_dict):
    all_dates = sorted(list(set(date for df in ticker_dict.values() if df is not None for date in df.index)))
    
    for ticker in ticker_dict:
        if ticker_dict[ticker] is not None:
            ticker_dict[ticker]['Quant_Score'] = 0.0
            ticker_dict[ticker]['Signal'] = 0
            
    for date in all_dates:
        daily_returns = {}
        for ticker, df in ticker_dict.items():
            if df is not None and date in df.index and not np.isnan(df.loc[date, 'Rolling_Ret_90']):
                daily_returns[ticker] = df.loc[date, 'Rolling_Ret_90']
                
        if len(daily_returns) < 2: continue
        
        ret_series = pd.Series(daily_returns)
        pct_ranks = ret_series.rank(pct=True) 
        
        for ticker in daily_returns:
            df = ticker_dict[ticker]
            idx = df.index.get_loc(date)
            if idx < 200: continue
            
            prev_row = df.iloc[idx-1]
            
            score = 0
            is_stage_2 = (prev_row['Close'] > prev_row['EMA_20'] > prev_row['EMA_50'] > prev_row['EMA_200'])
            if is_stage_2: score += 40
            if prev_row['MACD'] > prev_row['Signal_Line']: score += 20
            if 50 <= prev_row['RSI'] <= 75: score += 20
            
            ticker_pct = pct_ranks[ticker]
            if ticker_pct >= 0.90: score += 20
            elif ticker_pct >= 0.80: score += 15
            elif ticker_pct >= 0.70: score += 10
            elif ticker_pct >= 0.50: score += 5
            
            df.iloc[idx, df.columns.get_loc('Quant_Score')] = score
            
            pass_score = (score >= st.session_state.get('min_score_val', 50))
            pass_trend = True if not st.session_state.get('enforce_s2_val', True) else is_stage_2
            pass_rsi = (st.session_state.get('rsi_low_val', 45) <= prev_row['RSI'] <= st.session_state.get('rsi_high_val', 80))
            
            if pass_score and pass_trend and pass_rsi:
                df.iloc[idx, df.columns.get_loc('Signal')] = 1
            else:
                df.iloc[idx, df.columns.get_loc('Signal')] = 0

# ==========================================================================
# 📊 2. REALISTIC PORTFOLIO HEAT RISK ENGINE
# ==========================================================================
def run_strict_portfolio_backtest(ticker_dict, initial_capital=100000, risk_pct=1.0, slippage_pct=0.1, max_portfolio_heat=3.0):
    all_dates = sorted(list(set(date for df in ticker_dict.values() if df is not None for date in df.index)))
    capital = initial_capital
    portfolio_value = initial_capital
    active_trades = {}
    trade_log = []
    daily_equity = []
    
    for date in all_dates:
        current_open_risk = 0.0
        terminated_tickers = []
        
        for ticker, pos in active_trades.items():
            df = ticker_dict[ticker]
            if date in df.index:
                row = df.loc[date]
                
                if row['Open'] <= pos['sl_price']:
                    exit_price = row['Open'] * (1 - slippage_pct/100)
                    pnl = (exit_price - pos['entry_price']) * pos['shares']
                    capital += pnl
                    trade_log.append({"ticker": ticker, "type": "SL (GAP RISK)", "pnl": pnl, "R_match": pnl / pos['risk_amount']})
                    terminated_tickers.append(ticker)
                elif row['Low'] <= pos['sl_price']:
                    exit_price = pos['sl_price'] * (1 - slippage_pct/100)
                    pnl = (exit_price - pos['entry_price']) * pos['shares']
                    capital += pnl
                    trade_log.append({"ticker": ticker, "type": "SL", "pnl": pnl, "R_match": pnl / pos['risk_amount']})
                    terminated_tickers.append(ticker)
                else:
                    trail_sl = row['High'] - (row['ATR'] * 2.0)
                    if trail_sl > pos['sl_price']: pos['sl_price'] = trail_sl
                    
                    current_risk_distance = row['Close'] - pos['sl_price']
                    if current_risk_distance > 0:
                        calculated_risk = current_risk_distance * pos['shares']
                        current_open_risk += max(calculated_risk, 0.0)
                        
        for t in terminated_tickers: del active_trades[t]
            
        for ticker, df in ticker_dict.items():
            if ticker in active_trades: continue
            if date in df.index:
                row = df.loc[date]
                
                if row['Signal'] == 1 and capital > 0:
                    sl_distance = row['ATR'] * 2.0
                    if sl_distance <= 0: continue
                    
                    intended_risk_cash = portfolio_value * (risk_pct / 100)
                    projected_heat_pct = ((current_open_risk + intended_risk_cash) / portfolio_value) * 100
                    if projected_heat_pct > max_portfolio_heat: continue 
                    
                    execution_entry = row['Open'] * (1 + slippage_pct/100)
                    shares = intended_risk_cash / (sl_distance + (row['Open'] * (slippage_pct/100)))
                    
                    cost = shares * execution_entry
                    if cost > capital:
                        shares = capital / execution_entry
                        cost = shares * execution_entry
                        
                    if shares > 1:
                        capital -= cost
                        active_trades[ticker] = {
                            "entry_price": execution_entry,
                            "sl_price": execution_entry - sl_distance,
                            "shares": shares,
                            "risk_amount": intended_risk_cash
                        }
                        current_open_risk += intended_risk_cash
                        
        end_day_equity = capital
        for ticker, pos in active_trades.items():
            if date in ticker_dict[ticker].index:
                end_day_equity += ticker_dict[ticker].loc[date, 'Close'] * pos['shares']
        portfolio_value = end_day_equity
        daily_equity.append(portfolio_value)
        
    return trade_log, daily_equity

# ==========================================================================
# 🎛️ 3. STREAMLIT CONFIGURATION CONTROL
# ==========================================================================
st.sidebar.markdown("## 🦅 อาหวัง Pro Max v17.2")
st.sidebar.markdown("### `Zero-Bias Institutional Core`")
st.sidebar.divider()

account_capital = st.sidebar.number_input("เงินทุนเริ่มต้นรวมกองทุน ($):", value=100000, step=5000)
base_risk_pct = st.sidebar.slider("ความเสี่ยงจำกัดต่อไม้ (1R %):", 0.25, 2.0, 1.0, 0.25)
max_heat_limit = st.sidebar.slider("🔥 Max Portfolio Heat Cap (%):", 1.0, 10.0, 3.0, 0.5)
slippage_rate = st.sidebar.slider("Slippage แฝงขาเข้า/ออก (%):", 0.0, 0.5, 0.1, 0.05)

st.sidebar.markdown("### 🎛️ Dynamic Alpha Filters")
# 🛠️ FIXED: แก้ไขการเรียกใช้งาน st.session_state ให้ถูกต้อง ป้องกันแอปพัง
min_score_cutoff = st.sidebar.slider("คะแนน Quant ขั้นต่ำ:", 0, 100, 50, step=5)
st.session_state['min_score_val'] = min_score_cutoff

enforce_stage2 = st.sidebar.toggle("กรองเฉพาะ Stage 2 (EMA ขาขึ้น)", value=True)
st.session_state['enforce_s2_val'] = enforce_stage2

rsi_filter = st.sidebar.slider("กรอบช่วง RSI เทรดหน้างาน:", 0, 100, (45, 80))
st.session_state['rsi_low_val'] = rsi_filter[0]
st.session_state['rsi_high_val'] = rsi_filter[1]

# Pool หุ้นผู้นำตลาด
tickers_pool = ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "COIN", "ASTS", "SMCI", "AVGO", "CMG"]

with st.spinner("กำลังล้างข้อมูลประวัติศาสตร์ และสกัด Look-Ahead Bias..."):
    ticker_dict = {}
    for t in tickers_pool:
        raw_df = fetch_market_data(t, "3y")
        if raw_df is not None:
            ticker_dict[t] = compute_rolling_indicators_and_signals(raw_df)
            
    apply_cross_sectional_ranking(ticker_dict)

# ==========================================================================
# 🎯 4. EXECUTIVE ACTION LIST & TRADE SHEET DASHBOARD
# ==========================================================================
st.title("🦅 แผงควบคุมปฏิบัติการเทรดสถาบัน v17.2 (The Strict Quant Engine)")
st.caption("ระบบคำนวณแบบขจัดความเอนเอียงทางเวลา (Zero-Bias) คุมความเสี่ยงพอร์ตรวมอัตโนมัติ พร้อมออกแผ่นงานส่งคำสั่งทันที")

buy_today_list = []
watch_list = []
ban_list = []

for t, df in ticker_dict.items():
    if df is not None and not df.empty:
        last = df.iloc[-1]
        
        sl_distance = last['ATR'] * 2.0
        execution_entry = last['Close'] * (1 + slippage_rate/100)
        intended_risk_cash = account_capital * (base_risk_pct / 100)
        
        exact_shares = intended_risk_cash / (sl_distance + (last['Close'] * (slippage_rate/100))) if sl_distance > 0 else 0
        exact_cash = exact_shares * execution_entry
        
        metrics_payload = {
            "Ticker": t,
            "คะแนน Quant": f"{last['Quant_Score']:.0f} แต้ม",
            "ราคาสดล่าสุด": f"${last['Close']:.2f}",
            "RSI": f"{last['RSI']:.1f}",
            "แนะนำเข้าซื้อ (Shares)": int(exact_shares),
            "วงเงินที่ใช้จริง ($)": f"${exact_cash:,.2f}",
            "จุดคัท Stop Loss": f"${last['Close'] - sl_distance:.2f}",
            "จุดล็อกกำไรแนะนำ (2R)": f"${last['Close'] + (sl_distance * 2.0):.2f}"
        }
        
        if last['Signal'] == 1:
            buy_today_list.append(metrics_payload)
        elif last['Quant_Score'] >= 40:
            watch_list.append(metrics_payload)
        else:
            ban_list.append(metrics_payload)

st.subheader("🔥 1. รายการสั่งการหน้างานด่วน (Action List & Trade Sheet)")
tab_buy, tab_watch, tab_ban = st.tabs(["🟢 แผ่นงานส่งคำสั่งซื้อวันนี้ (BUY TODAY)", "⚠️ รายการหุ้นเฝ้าระวัง (WATCHLIST)", "❌ หุ้นห้ามจับต้องเด็ดขาด (BANNED ZONE)"])

with tab_buy:
    if buy_today_list:
        st.success("🎯 พบสัญญาณซื้อตามกฎกองทุนเคร่งครัดในวันนี้! สามารถใช้สัดส่วน Sizing และจุด Stop Loss ด้านล่างคีย์ส่งคำสั่งซื้อขายจริงได้ทันที")
        st.dataframe(pd.DataFrame(buy_today_list), use_container_width=True, hide_index=True)
    else:
        st.info("⬜ วันนี้พอร์ตปลอดภัย ไม่มีสัญญาณซื้อร่วมที่สมบูรณ์แบบ นอนทับมือและคุมเงินสดไว้")

with tab_watch:
    if watch_list:
        st.dataframe(pd.DataFrame(watch_list)[["Ticker", "คะแนน Quant", "ราคาสดล่าสุด", "RSI"]], use_container_width=True, hide_index=True)

with tab_ban:
    if ban_list:
        st.dataframe(pd.DataFrame(ban_list)[["Ticker", "คะแนน Quant", "ราคาสดล่าสุด", "RSI"]], use_container_width=True, hide_index=True)

st.divider()
st.subheader("📊 2. ดัชนีวัดผลทดสอบพอร์ตรวมจำลองแบบตัดผลประโยชน์ล่วงหน้า (Institutional Performance Metrics)")

trade_log, daily_equity = run_strict_portfolio_backtest(ticker_dict, initial_capital=account_capital, risk_pct=base_risk_pct, slippage_pct=slippage_rate, max_portfolio_heat=max_heat_limit)

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
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mathematical Expectancy (R)", f"{expectancy:.2f} R")
    col2.metric("Profit Factor", f"{profit_factor:.2f}")
    col3.metric("Sharpe Ratio (พอร์ต)", f"{sharpe:.2f}")
    col4.metric("Max Drawdown จริงของพอร์ต", f"{max_drawdown:.1f}%")
    
    st.markdown("#### 📜 บันทึกตารางประวัติธุรกรรมเพื่อการตรวจสอบย้อนหลัง (Strict Audit Trade Log)")
    st.dataframe(df_log, use_container_width=True)
else:
    st.info("💡 ภายใต้กฎการคุม Portfolio Heat ที่เข้มงวดนี้ ไม่มีไม้ใดที่เปิดซื้อขายตลอดระยะเวลาที่ผ่านมา (ลองปรับคะแนนขั้นต่ำ หรือขยายขีดความเสี่ยงที่ Sidebar เพื่อทดสอบ)")
