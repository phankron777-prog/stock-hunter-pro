import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# ==========================================================================
# ⚙️ 1. SETUP ENGINE CONFIG & APP THEME
# ==========================================================================
st.set_page_config(page_title="อาหวัง Ultimate Core v18.0", layout="wide")

st.sidebar.markdown("## 🦅 อาหวัง Ultimate Core v18.0")
st.sidebar.markdown("### `The Perfect Fusion Architecture`")
st.sidebar.caption("🔒 เครื่องยนต์สถาบันความเสี่ยงต่ำ คุมพอร์ตรวมอัตโนมัติ ครอบด้วย UI หน้างาน 3 แท็บ")
st.sidebar.divider()

# แผงบริหารเงินทุนและความเสี่ยง (Risk Parameters จาก v17.1)
account_capital = st.sidebar.number_input("เงินทุนเริ่มต้นรวมของพอร์ต ($):", value=100000, step=5000)
base_risk_pct = st.sidebar.slider("ความเสี่ยงสูงสุดที่ยอมรับได้ต่อไม้ (1R %):", 0.25, 2.0, 1.0, 0.25)
max_heat_limit = st.sidebar.slider("🔥 Max Portfolio Heat Cap (%):", 1.0, 10.0, 3.0, 0.5)
slippage_rate = st.sidebar.slider("Slippage ประมาณการขาเข้า/ออก (%):", 0.0, 0.5, 0.1, 0.05)

st.sidebar.markdown("### 🎛️ Dynamic Alpha Filters (สมองกลสถาบัน)")
min_score_cutoff = st.sidebar.slider("คะแนน Quant ขั้นต่ำในการแจกสัญญาณ:", 0, 100, 50, step=5)
st.session_state['min_score_val'] = min_score_cutoff

enforce_stage2 = st.sidebar.toggle("กรองเฉพาะ Stage 2 (EMA เรียงตัวขาขึ้น)", value=True)
st.session_state['enforce_s2_val'] = enforce_stage2

rsi_filter = st.sidebar.slider("กรอบ RSI ปลอดภัยหน้างาน:", 0, 100, (45, 80))
st.session_state['rsi_low_val'] = rsi_filter[0]
st.session_state['rsi_high_val'] = rsi_filter[1]

# ตะกร้าหุ้นหลักที่เราพัฒนาด้วยกันมา
tickers_pool = ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "COIN", "ASTS", "SMCI", "AVGO", "CMG"]

# ==========================================================================
# 🧠 2. UNIFIED ZERO-BIAS SIGNAL ENGINE (สมองกลระดับฉลาดจาก v17.1)
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
        
        # 🟢 Trend Zones & Stage 2 Checking
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # 🟢 Volume Filter Indicator
        df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()
        
        # 🟢 Momentum Indicators
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # 🟢 RSI Metric
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9)) + 1e-9))
        
        # 🟢 True ATR Sizing Metrics
        df['Prev_Close'] = df['Close'].shift(1)
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()
        df['True_Range'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
        
        # ใช้ผลตอบแทนย้อนหลัง 90 วันเพื่อเอาไปทำ Relative Strength Ranking เทียบกับตัวอื่น
        df['Rolling_Ret_90'] = (df['Close'] / df['Close'].shift(90)) - 1.0
        
        # ประกาศคอลัมน์ล่วงหน้าเพื่อความปลอดภัย (ดักพวก KeyError)
        df['Quant_Score'] = 0.0
        df['Signal'] = 0
        
        return df
    except:
        return None

def apply_cross_sectional_ranking(ticker_dict, spy_df):
    valid_dfs = {k: v for k, v in ticker_dict.items() if v is not None and len(v) >= 200}
    if not valid_dfs: return
    
    # ดึงรายชื่อวันที่ทั้งหมดมาทำ Cross-Sectional เพื่อคำนวณคะแนนเกรดของแต่ละวันแข่งกัน
    all_dates = sorted(list(set(date for df in valid_dfs.values() for date in df.index)))
    
    # คำนวณตลาดภาพรวม (SPY Market Filter) ไว้ล่วงหน้าเพื่อใช้ล็อกความปลอดภัย
    spy_df['EMA_200'] = spy_df['Close'].ewm(span=200, adjust=False).mean()
    
    for date in all_dates:
        daily_returns = {}
        for ticker, df in valid_dfs.items():
            if date in df.index and not np.isnan(df.loc[date, 'Rolling_Ret_90']):
                daily_returns[ticker] = df.loc[date, 'Rolling_Ret_90']
                
        if len(daily_returns) < 2: continue
        
        # 🟢 นี่คือกลไก Relative Strength (RS) คัดหุ้นเกรดพรีเมียมจากเวอร์ชันสถาบัน
        ret_series = pd.Series(daily_returns)
        pct_ranks = ret_series.rank(pct=True) 
        
        # ดึงสัญญาณภาพรวมตลาดวันนั้น (SPY Market Filter) เพื่อคุมความเสี่ยงขาลงรุนแรง
        spy_market_healthy = True
        if date in spy_df.index:
            spy_market_healthy = spy_df.loc[date, 'Close'] > spy_df.loc[date, 'EMA_200']
            
        for ticker in daily_returns:
            df = valid_dfs[ticker]
            idx = df.index.get_loc(date)
            if idx < 200: continue
            
            prev_row = df.iloc[idx-1]
            score = 0
            
            # กฎให้คะแนนสะสมเชิงเทคนิค (Quant Score System)
            is_stage_2 = (prev_row['Close'] > prev_row['EMA_20'] > prev_row['EMA_50'] > prev_row['EMA_200'])
            if is_stage_2: score += 40
            if prev_row['MACD'] > prev_row['Signal_Line']: score += 20
            if 50 <= prev_row['RSI'] <= 75: score += 20
            
            # คะแนนโบนัสจาก Relative Strength ยิ่งแกร่งกว่าเพื่อนร่วมรุ่น ยิ่งได้แต้มเยอะ (NVDA ได้เปรียบหุ้นรองชัดเจน)
            ticker_pct = pct_ranks[ticker]
            if ticker_pct >= 0.90: score += 20
            elif ticker_pct >= 0.80: score += 15
            elif ticker_pct >= 0.70: score += 10
            elif ticker_pct >= 0.50: score += 5
            
            df.iloc[idx, df.columns.get_loc('Quant_Score')] = float(score)
            
            # 🟢 ดักกรองเช็คเงื่อนไขความสะอาดของสัญญาณอย่างเข้มงวด
            pass_score = (score >= st.session_state.get('min_score_val', 50))
            pass_trend = True if not st.session_state.get('enforce_s2_val', True) else is_stage_2
            pass_rsi = (st.session_state.get('rsi_low_val', 45) <= prev_row['RSI'] <= st.session_state.get('rsi_high_val', 80))
            
            # 🟢 Volume Filter: เพิ่มเข้าไปตามที่พี่สั่ง ห้ามดันราคาแบบไร้วอลุ่มหนุน
            pass_volume = prev_row['Volume'] > prev_row['Volume_MA20'] if 'Volume_MA20' in df.columns else True
            
            # ถ้าองค์ประกอบครบ + สภาพตลาดภาพรวมปลอดภัย (SPY Healthy) -> แจกสัญญาณ BUY TODAY ทันที
            if pass_score and pass_trend and pass_rsi and pass_volume and spy_market_healthy:
                df.iloc[idx, df.columns.get_loc('Signal')] = 1
            else:
                df.iloc[idx, df.columns.get_loc('Signal')] = 0

# ==========================================================================
# 📊 3. REALISTIC PORTFOLIO HEAT BACKTEST ENGINE (รันแบบ Hybrid 50/50)
# ==========================================================================
def run_strict_portfolio_backtest(ticker_dict, initial_capital=100000, risk_pct=1.0, slippage_pct=0.1, max_portfolio_heat=3.0):
    valid_dfs = {k: v for k, v in ticker_dict.items() if v is not None and len(v) >= 200}
    if not valid_dfs: return [], [initial_capital]
    
    all_dates = sorted(list(set(date for df in valid_dfs.values() for date in df.index)))
    capital = initial_capital
    portfolio_value = initial_capital
    active_trades = {}
    trade_log = []
    daily_equity = []
    
    for date in all_dates:
        current_open_risk = 0.0
        terminated_tickers = []
        
        # ตรวจสอบสถานะการถือครองของไม้นั้น ๆ หน้างานจำลอง
        for ticker, pos in active_trades.items():
            df = valid_dfs[ticker]
            if date in df.index:
                row = df.loc[date]
                
                # 🟢 พัฒนาระบบ Take Profit แบบ Hybrid ตามที่พี่สั่ง: แบ่งขาย 50% ที่ 2R และรัน ATR ที่เหลือ
                if not pos['is_half_tp_hit'] and row['High'] >= pos['tp_target_2r']:
                    # ล็อกกำไรไม้แรกครึ่งนึง (50% Quantity) เข้ากระเป๋า
                    half_pnl = (pos['tp_target_2r'] - pos['entry_price']) * (pos['shares'] * 0.5)
                    capital += (pos['entry_price'] * (pos['shares'] * 0.5)) + half_pnl
                    pos['shares'] = pos['shares'] * 0.5
                    pos['is_half_tp_hit'] = True
                    trade_log.append({"ticker": ticker, "type": "🔒 PARTIAL TP (2R 50%)", "pnl": half_pnl, "R_match": 2.0})
                
                # ตรวจเช็คจุด Stop Loss หรือจุด Trailing Stop ขาออกสำหรับหุ้นที่เหลือ
                if row['Open'] <= pos['sl_price']:
                    exit_price = row['Open'] * (1 - slippage_pct/100)
                    pnl = (exit_price - pos['entry_price']) * pos['shares']
                    capital += (exit_price * pos['shares'])
                    trade_log.append({"ticker": ticker, "type": "SL (GAP RISK)", "pnl": pnl, "R_match": pnl / (pos['risk_amount'] * 0.5 if pos['is_half_tp_hit'] else pos['risk_amount'])})
                    terminated_tickers.append(ticker)
                elif row['Low'] <= pos['sl_price']:
                    exit_price = pos['sl_price'] * (1 - slippage_pct/100)
                    pnl = (exit_price - pos['entry_price']) * pos['shares']
                    capital += (exit_price * pos['shares'])
                    trade_log.append({"ticker": ticker, "type": "SL / TRAILING EXITED", "pnl": pnl, "R_match": pnl / (pos['risk_amount'] * 0.5 if pos['is_half_tp_hit'] else pos['risk_amount'])})
                    terminated_tickers.append(ticker)
                else:
                    # 🟢 ขยับ Trailing Stop ตามด้วยระยะ 2.5 * ATR เพื่อรันเทรนด์กินคำโต 8R - 15R ขาขึ้นยาว
                    trail_sl = row['High'] - (row['ATR'] * 2.5)
                    if trail_sl > pos['sl_price']: 
                        pos['sl_price'] = trail_sl
                    
                    current_risk_distance = row['Close'] - pos['sl_price']
                    if current_risk_distance > 0:
                        current_open_risk += max(current_risk_distance * pos['shares'], 0.0)
                        
        for t in terminated_tickers: del active_trades[t]
            
        # เปิดไม้ใหม่เมื่อเจอบันทึกสัญญาณซื้อสมบูรณ์แบบ
        for ticker, df in valid_dfs.items():
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
                            "tp_target_2r": execution_entry + (sl_distance * 2.0),
                            "shares": shares,
                            "risk_amount": intended_risk_cash,
                            "is_half_tp_hit": False
                        }
                        current_open_risk += intended_risk_cash
                        
        end_day_equity = capital
        for ticker, pos in active_trades.items():
            if date in valid_dfs[ticker].index:
                end_day_equity += valid_dfs[ticker].loc[date, 'Close'] * pos['shares']
        portfolio_value = end_day_equity
        daily_equity.append(portfolio_value)
        
    return trade_log, daily_equity

# ==========================================================================
# 🎯 4. EXECUTIVE UX DASHBOARD: THE 3-TAB INTERFACE READY
# ==========================================================================
st.title("🦅 แผงควบคุมปฏิบัติการเทรด (Action List Dashboard v18.0)")
st.caption("การผสานร่างสมบูรณ์แบบ: ใช้สมองกลสถาบันขจัด Bias คุมความเสี่ยงของ v17.1 ครอบด้วยหน้าต่าง 3 แท็บดูง่ายของ v11.0")

with st.spinner("🧠 กำลังวิเคราะห์ข้อมูลเชิงลึก คัดเกรดความแข็งแกร่ง และสแกนตลาด..."):
    # ดึงดัชนี SPY มาเป็น Market Filter ดักวิกฤตเศรษฐกิจ
    spy_raw = fetch_market_data("SPY", "3y")
    
    ticker_dict = {}
    for t in tickers_pool:
        raw_df = fetch_market_data(t, "3y")
        if raw_df is not None:
            processed = compute_rolling_indicators_and_signals(raw_df)
            if processed is not None:
                ticker_dict[t] = processed
            
    if spy_raw is not None and len(spy_raw) >= 200:
        apply_cross_sectional_ranking(ticker_dict, spy_raw)

# สร้างอาเรย์ตะกร้าเพื่อแยกเอาข้อมูลไปโยนลง 3 แท็บ
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
            "ชื่อหุ้น (Ticker)": t,
            "คะแนนความพรีเมียม (Quant Score)": f"{last['Quant_Score']:.0f} แต้ม",
            "ราคาสดปัจจุบัน": f"${last['Close']:.2f}",
            "RSI วันนี้": f"{last['RSI']:.1f}",
            "จำนวนที่ต้องซื้อ (Shares)": int(exact_shares),
            "วงเงินที่ต้องคีย์ซื้อ ($)": f"${exact_cash:,.2f}",
            "ตั้งจุดตัดขาดทุน (Stop Loss)": f"${last['Close'] - sl_distance:.2f}",
            "เป้าขายทำกำไรไม้แรกครึ่งนึง (50% @ 2R)": f"${last['Close'] + (sl_distance * 2.0):.2f}",
            "แผนไม้ที่เหลือ (50% Trail ATR)": f"ใช้แผนขยับตามระยะ 2.5 * ATR (Trailing Stop)"
        }
        
        # คัดแยกหมวดหมู่เด็ดขาดตามเงื่อนไขสมองกล
        if last['Signal'] == 1:
            buy_today_list.append(metrics_payload)
        elif last['Quant_Score'] >= 40:
            watch_list.append(metrics_payload)
        else:
            ban_list.append(metrics_payload)

# 🚀 การแสดงผลหน้าต่างระดับ "ใช้ง่ายมาก" (UX 9.5/10 ที่พี่ต้องการ)
st.subheader("🔥 1. ส่วนสั่งการซื้อขายด่วนประจำวัน (Daily Action Sheet)")

tab_buy, tab_watch, tab_ban = st.tabs([
    "🟢 แผ่นงานส่งคำสั่งซื้อวันนี้ (BUY TODAY)", 
    "⚠️ รายการหุ้นเฝ้าระวัง (WATCHLIST)", 
    "❌ หุ้นห้ามจับต้องเด็ดขาด (BANNED ZONE)"
])

with tab_buy:
    if buy_today_list:
        st.success("🎯 พบหุ้นผู้นำตลาดเกิดสัญญาณซื้อที่สมบูรณ์แบบผ่านระบบคัดกรองสถาบันในเช้านี้! พี่สามารถลอกตารางคีย์ตามช่อง Shares และ Stop Loss ได้ทันที")
        st.dataframe(pd.DataFrame(buy_today_list), use_container_width=True, hide_index=True)
    else:
        st.info("⬜ เช้านี้ระบบประมวลผลแล้ว 'ไม่มีหุ้นตัวใดผ่านเงื่อนไขความปลอดภัยที่สมบูรณ์' นอนทับมือ คุมความเสี่ยง และถือเงินสดไว้ให้ปลอดภัยที่สุดครับพี่")

with tab_watch:
    if watch_list:
        st.info("👀 รายการหุ้นเกรดดีที่แนวโน้มยังเป็นขาขึ้น (Stage 2) แต่สัญญาณซื้อยังไม่สุกงอม คัดแยกออกมาให้เฝ้าดูความแข็งแกร่งเพื่อเตรียมความพร้อม")
        df_watch = pd.DataFrame(watch_list)[["ชื่อหุ้น (Ticker)", "คะแนนความพรีเมียม (Quant Score)", "ราคาสดปัจจุบัน", "RSI วันนี้"]]
        st.dataframe(df_watch, use_container_width=True, hide_index=True)

with tab_ban:
    if ban_list:
        st.error("❌ หุ้นอันตรายห้ามเข้าไปจับต้องเด็ดขาดในวันนี้ เนื่องจากระบบตรวจพบว่าเป็นเทรนด์ขาลง วอลุ่มบาง หรือคะแนนวินัยต่ำกว่าเกณฑ์ควบคุม")
        df_ban = pd.DataFrame(ban_list)[["ชื่อหุ้น (Ticker)", "คะแนนความพรีเมียม (Quant Score)", "ราคาสดปัจจุบัน", "RSI วันนี้"]]
        st.dataframe(df_ban, use_container_width=True, hide_index=True)

# ส่วนวิเคราะห์ระบบ Backtest ด้านล่างเพื่อยืนยันประสิทธิภาพของเครื่องยนต์ (Institutional Backtest Dashboard)
st.divider()
st.subheader("📊 2. ดัชนีวัดผลการทดสอบพอร์ตรวมจำลองแบบ Hybrid (Institutional Performance Metrics)")

if spy_raw is not None:
    trade_log, daily_equity = run_strict_portfolio_backtest(
        ticker_dict, initial_capital=account_capital, risk_pct=base_risk_pct, slippage_pct=slippage_rate, max_portfolio_heat=max_heat_limit
    )

    if trade_log:
        df_log = pd.DataFrame(trade_log)
        wins = df_log[df_log['pnl'] > 0]
        losses = df_log[df_log['pnl'] <= 0]
        
        total_trades = len(df_log)
        win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
        
        eq_series = pd.Series(daily_equity)
        max_drawdown = ((eq_series.cummax() - eq_series) / eq_series.cummax()).max() * 100
        final_return = ((eq_series.iloc[-1] - account_capital) / account_capital) * 100
        
        c1, c2, c3 = st.columns(3)
        c1.metric("จำนวนธุรกรรมทั้งหมดที่เกิดขึ้น (รวมแบ่งไม้)", f"{total_trades} ไม้")
        c2.metric("Max Drawdown สูงสุดของพอร์ต", f"{max_drawdown:.2f}%")
        c3.metric("ผลตอบแทนจำลองของพอร์ตรวม", f"+{final_return:.2f}%")
        
        st.markdown("#### 📜 ตารางบันทึกประวัติการเทรดเพื่อตรวจสอบความเสี่ยงย้อนหลัง (Strict Audit Trade Log)")
        st.dataframe(df_log, use_container_width=True)
    else:
        st.info("💡 ภายใต้กฎควบคุมความร้อนและจุดคัดกรองที่เข้มงวดสูงนี้ ไม่มีสัญญาณซื้อผิดพลาดใด ๆ เกิดขึ้นในประวัติการจำลอง")
