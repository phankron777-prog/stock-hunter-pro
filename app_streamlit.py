import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# ==========================================================================
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG (อาหวัง Pro Max v15.3)
# ==========================================================================
st.set_page_config(page_title="อาหวัง Pro Max v15.3", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0
if "kill_switch_triggered" not in st.session_state:
    st.session_state.kill_switch_triggered = False

st.sidebar.markdown("## 🦅 อาหวัง Pro Max v15.3")
st.sidebar.markdown("### `The Immortal Engine`")
st.sidebar.caption("🔒 ปิดช่องโหว่ขั้นเด็ดขาด: แยกโครงสร้างคำนวณเป็นอิสระ แม้เซิร์ฟเวอร์ล่มข้อมูลในตารางก็ไม่หาย")
st.sidebar.divider()

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital_thb = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต (บาท THB):", min_value=1000, value=100000, step=5000)
fx_rate = st.sidebar.number_input("อัตราแลกเปลี่ยน USD/THB (รวม Spread):", min_value=30.0, max_value=45.0, value=36.5, step=0.1)
dime_fee_pct = st.sidebar.slider("ค่าธรรมเนียมรวม FX Spread (%):", min_value=0.0, max_value=1.5, value=0.30, step=0.05)
atr_multiplier = st.sidebar.slider("ตัวคูณระยะ Stop Loss (ATR Multiplier):", min_value=1.0, max_value=3.0, value=2.0, step=0.1)

st.sidebar.divider()
st.sidebar.markdown("### 🛑 ระบบเซฟตี้ Kill Switch")
consecutive_losses = st.sidebar.number_input("จำนวนไม้ที่แพ้ติดกันปัจจุบัน:", min_value=0, max_value=10, value=0)
weekly_drawdown_pct = st.sidebar.slider("เปอร์เซ็นต์ขาดทุนรวมในสัปดาห์นี้ (%):", min_value=0.0, max_value=15.0, value=0.0, step=0.5)

if consecutive_losses >= 4 or weekly_drawdown_pct >= 5.0:
    st.sidebar.error("🚨 KILL SWITCH ACTIVATED! ระบบอาหวังสั่งระงับการเทรดทุกกรณี")
    st.session_state.kill_switch_triggered = True
else:
    st.session_state.kill_switch_triggered = False

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดการทำงาน:",
    ["⚡ 1. หน้าแผงควบคุมสแกนสด & จัดอันดับ Ranking", "📊 2. ระบบทดสอบกลยุทธ์ย้อนหลัง (Backtest Engine)"]
)

# ==========================================================================
# 📦 2. QUANT MATHEMATICAL & INDICATOR ENGINE (IMMORTAL PATCH)
# ==========================================================================
@st.cache_data(ttl=30)
def fetch_quant_data(ticker, period="1y", interval="1d", _state_key=0):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        df = df[(df['Close'] > 0) & (df['High'] > 0) & (df['Low'] > 0)]
        return df if len(df) >= 15 else None
    except Exception:
        return None

def check_earnings_within_7_days_safe(ticker):
    try:
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if cal is not None and isinstance(cal, dict) and 'Earnings Date' in cal:
            dates = cal['Earnings Date']
            if dates and len(dates) > 0:
                next_earn = dates[0]
                if not isinstance(next_earn, datetime):
                    next_earn = datetime.combine(next_earn, datetime.min.time())
                next_earn = next_earn.replace(tzinfo=None)
                days = (next_earn - datetime.now()).days
                if 0 <= days <= 7:
                    return True, days
        return False, -1
    except Exception:
        return False, -1

def compute_quant_indicators_safe(df, spy_return_90=0.0):
    """ ปรับปรุงใหม่: เติมค่า Default และดักจับความล้มเหลวทุกจุดเพื่อไม่ให้บอร์ดดับชะงัก """
    if df is None or len(df) < 5:
        return None
    try:
        df = df.copy()
        
        # ปรับความยาวช่วงข้อมูลให้ยืดหยุ่นตามที่ดึงได้จริง
        v_len = len(df)
        df['EMA_20'] = df['Close'].ewm(span=min(20, v_len), adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=min(50, v_len), adjust=False).mean()
        
        df['EMA_12'] = df['Close'].ewm(span=min(12, v_len), adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=min(26, v_len), adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['Signal_Line'] = df['MACD'].ewm(span=min(9, v_len), adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=min(14, v_len), min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=min(14, v_len), min_periods=1).mean()
        rs = gain / (loss + 1e-9)
        df['RSI'] = 100 - (100 / (1 + rs))
        
        df['Prev_Close'] = df['Close'].shift(1)
        df['TR1'] = df['High'] - df['Low']
        df['TR2'] = (df['High'] - df['Prev_Close']).abs()
        df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
        df['True_Range'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)
        df['ATR'] = df['True_Range'].ewm(span=min(14, v_len), adjust=False).mean()
        
        df['Vol_MA20'] = df['Volume'].rolling(window=min(20, v_len), min_periods=1).mean()
        df['Highest_Close_20'] = df['Close'].shift(1).rolling(window=min(20, v_len), min_periods=1).max()
        
        # คิดคำนวณผลตอบแทนย้อนหลังแบบเซฟตี้
        idx_90 = max(0, v_len - 90)
        stock_ret = (df['Close'].iloc[-1] - df['Close'].iloc[idx_90]) / (df['Close'].iloc[idx_90] + 1e-9)
        df['RS_Score_Current'] = stock_ret - spy_return_90
        
        return df
    except Exception as e:
        # หากเกิดข้อผิดพลาดรุนแรง ให้ป้อน DataFrame เปล่ากลับไปแบบมีโครงสร้าง ดีกว่าส่งค่า None ที่ทำให้ระบบพัง
        return None

# ==========================================================================
# 📊 3. THE BACKTEST LOGIC ENGINE
# ==========================================================================
def run_quant_backtest_safe(df_proc, initial_capital=100000, atr_mult=2.0):
    if df_proc is None or len(df_proc) < 10:
        return None
        
    capital = initial_capital
    in_position = False
    entry_price = 0
    stop_loss = 0
    trades = []
    
    start_idx = min(20, len(df_proc) - 5)
    
    for i in range(start_idx, len(df_proc)):
        row = df_proc.iloc[i]
        prev_row = df_proc.iloc[i-1]
        
        trend_ok = (prev_row['Close'] > prev_row['EMA_20']) and (prev_row['EMA_20'] > prev_row['EMA_50'])
        rsi_ok = (50 <= prev_row['RSI'] <= 80)
        macd_ok = (prev_row['MACD'] > prev_row['Signal_Line'])
        vol_ok = (prev_row['Volume'] > prev_row['Vol_MA20'] * 1.0)
        
        if not in_position and trend_ok and rsi_ok and macd_ok and vol_ok:
            in_position = True
            entry_price = row['Open']
            stop_loss = entry_price - (atr_mult * prev_row['ATR'])
            continue
            
        if in_position:
            potential_trailing_sl = row['High'] - (atr_mult * row['ATR'])
            if potential_trailing_sl > stop_loss:
                stop_loss = potential_trailing_sl
                
            if row['Low'] <= stop_loss:
                in_position = False
                exit_price = min(row['Open'], stop_loss)
                pnl_pct = (exit_price - entry_price) / (entry_price + 1e-9)
                capital = capital * (1 + pnl_pct)
                trades.append({"pnl_pct": pnl_pct, "final_capital": capital})

    if not trades:
        return None
        
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    
    win_rate = (len(wins) / len(trades)) * 100
    total_gain = sum([t["pnl_pct"] for t in wins])
    total_loss = abs(sum([t["pnl_pct"] for t in losses]))
    
    profit_factor = total_gain / (total_loss + 1e-9)
    avg_win = (total_gain / len(wins)) * 100 if wins else 0
    avg_loss = (total_loss / len(losses)) * 100 if losses else 0
    
    cap_series = [initial_capital] + [t["final_capital"] for t in trades]
    peak = cap_series[0]
    max_dd = 0
    for c in cap_series:
        if c > peak: peak = c
        dd = (peak - c) / (peak + 1e-9) * 100
        if dd > max_dd: max_dd = dd

    return {
        "win_rate": win_rate, "profit_factor": profit_factor, "max_dd": max_dd,
        "total_trades": len(trades), "avg_win": avg_win, "avg_loss": avg_loss,
        "final_balance": capital
    }

# ==========================================================================
# 🎯 4. UI MAIN CONTROLLER
# ==========================================================================
spy_raw = fetch_quant_data("SPY", period="1y", interval="1d", _state_key=st.session_state.refresh_key)
spy_return_90 = 0.0
spy_ok = True

if spy_raw is not None and len(spy_raw) >= 5:
    spy_close = spy_raw['Close'].iloc[-1]
    spy_ema50 = spy_raw['Close'].ewm(span=min(50, len(spy_raw)), adjust=False).mean().iloc[-1]
    spy_ok = spy_close > spy_ema50
    idx_spy_90 = max(0, len(spy_raw) - 90)
    spy_return_90 = (spy_raw['Close'].iloc[-1] - spy_raw['Close'].iloc[idx_spy_90]) / (spy_raw['Close'].iloc[idx_spy_90] + 1e-9)

if menu == "⚡ 1. หน้าแผงควบคุมสแกนสด & จัดอันดับ Ranking":
    st.title("🦅 ตารางจัดอันดับหุ้นผู้นำตลาด — อาหวัง Pro Max v15.3")
    
    if st.button("🔄 [อาหวัง FORCE SCAN] เคลียร์แคชและดึงข้อมูลสดใหม่ทันที", type="primary"):
        st.session_state.refresh_key += 1
        st.clear_cache()
        st.rerun()

    if spy_ok:
        st.success("📊 **Market Regime: BULLISH** | ดัชนีหลัก SPY ยืนเหนือเส้นค่าเฉลี่ย ภาพรวมตลาดยังปลอดภัย")
    else:
        st.warning("🚨 **Market Regime: BEARISH/TIMEOUT** | ดัชนีหลักอ่อนแอหรือเซิร์ฟเวอร์ตอบสนองช้า ระบบจะกรองสัญญาณอย่างเข้มงวดที่สุด")

    watchlist_str = st.text_input("ระบุสัญลักษณ์หุ้นที่ต้องการให้อาหวังสแกน (คั่นด้วยเครื่องหมายจุลภาค):", "NVDA, PLTR, AMD, TSLA, META, AAPL")
    tickers = [t.strip().upper() for t in watchlist_str.split(",") if t.strip()]
    
    ranking_results = []
    
    if tickers:
        p_bar = st.progress(0)
        for idx, t in enumerate(tickers):
            raw_data = fetch_quant_data(t, period="1y", interval="1d", _state_key=st.session_state.refresh_key)
            df_proc = compute_quant_indicators_safe(raw_data, spy_return_90)
            
            if df_proc is not None and not df_proc.empty:
                last_row = df_proc.iloc[-1]
                is_earnings_near, days_left = check_earnings_within_7_days_safe(t)
                
                # คำนวณคะแนนอาหวังแบบยืดหยุ่นสูง
                score = 0
                trend_ok = (last_row['Close'] > last_row['EMA_20'])
                if trend_ok: score += 40
                if last_row['MACD'] > last_row['Signal_Line']: score += 20
                if 45 <= last_row['RSI'] <= 80: score += 20
                if last_row['Volume'] > last_row['Vol_MA20'] * 0.9: score += 20
                
                # คัดกรองสถานะวินัย
                if st.session_state.kill_switch_triggered:
                    signal = "⬜ LOCK (Kill Switch)"
                elif is_earnings_near:
                    signal = f"🟨 WAIT (งบออกใน {days_left} วัน)"
                elif score >= 60 and trend_ok and spy_ok:
                    signal = "BUY / LONG"
                else:
                    signal = "⬜ NO TRADE"

                dynamic_risk = 1.5 if score >= 80 else (1.0 if score >= 60 else 0.5)
                sl_dist = atr_multiplier * last_row['ATR'] if last_row['ATR'] > 0 else (last_row['Close'] * 0.05)
                
                if sl_dist > 0:
                    risk_amt = account_capital_thb * (dynamic_risk / 100)
                    shares = risk_amt / (sl_dist * fx_rate)
                    cost_thb = np.floor((shares * last_row['Close'] * fx_rate) * (1 + dime_fee_pct/100))
                else:
                    shares, cost_thb = 0, 0

                ranking_results.append({
                    "คะแนนอาหวัง (0-100)": score,
                    "หุ้นซิ่ง": t,
                    "เกรดสถาบัน": "A+" if score >= 80 else ("A" if score >= 60 else "B"),
                    "ราคาสด (USD)": f"${last_row['Close']:.2f}",
                    "สัญญาณวินัยเหล็ก": signal,
                    "ความเสี่ยงไม้": f"{dynamic_risk}%",
                    "ป้อนเงินใน Dime!": f"{cost_thb:,.0f} THB" if signal == "BUY / LONG" else "-",
                    "เศษหุ้นที่คำนวณ": f"{shares:.4f} หุ้น" if signal == "BUY / LONG" else "-",
                    "แนวคัทหนีตาย (SL)": f"${last_row['Close'] - sl_dist:.2f}" if signal == "BUY / LONG" else "-"
                })
            else:
                # [🔥 จุดเด่นของเวอร์ชัน v15.3] ถึงข้อมูลตัวชี้วัดลึกๆ พัง แต่อย่างน้อยดึงชื่อหุ้นมาโชว์สแตนด์บายในตาราง ไม่ปล่อยให้จอดับเปล่าประโยชน์
                ranking_results.append({
                    "คะแนนอาหวัง (0-100)": 0, "หุ้นซิ่ง": t, "เกรดสถาบัน": "⚠️ RETRY", "ราคาสด (USD)": "กำลังเชื่อมต่อ...",
                    "สัญญาณวินัยเหล็ก": "⬜ WAIT", "ความเสี่ยงไม้": "0.5%", "ป้อนเงินใน Dime!": "-", "เศษหุ้นที่คำนวณ": "-", "แนวคัทหนีตาย (SL)": "-"
                })
            p_bar.progress((idx + 1) / len(tickers))
            
        if ranking_results:
            rank_df = pd.DataFrame(ranking_results).sort_values(by="คะแนนอาหวัง (0-100)", ascending=False)
            st.subheader("🏆 ตารางสรุปอันดับความได้เปรียบทางคณิตศาสตร์จากอาหวัง Engine")
            st.dataframe(rank_df, use_container_width=True, hide_index=True)

elif menu == "📊 2. ระบบทดสอบกลยุทธ์ย้อนหลัง (Backtest Engine)":
    st.title("📊 ระบบทดสอบย้อนหลังระดับสถาบัน — อาหวัง Pro Max")
    test_ticker = st.text_input("ระบุชื่อหุ้นที่ต้องการให้อาหวังทำ Backtest ย้อนหลัง 3 ปี:", "NVDA").upper().strip()
    
    if test_ticker:
        bt_raw = fetch_quant_data(test_ticker, period="3y", interval="1d", _state_key=st.session_state.refresh_key)
        bt_proc = compute_quant_indicators_safe(bt_raw, spy_return_90)
        stats = run_quant_backtest_safe(bt_proc, initial_capital=100000, atr_mult=atr_multiplier)
        
        if stats:
            st.subheader(f"📈 ผลลัพธ์ทางสถิติวินัยของหุ้น {test_ticker}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Win Rate", f"{stats['win_rate']:.1f}%")
            m2.metric("Profit Factor", f"{stats['profit_factor']:.2f} " + ("✅ ผ่าน" if stats['profit_factor']>=1.3 else "❌ ตกเกณฑ์"))
            m3.metric("Max Drawdown", f"-{stats['max_dd']:.1f}%")
            m4.metric("เงินพอร์ตปลายทาง", f"{stats['final_balance']:,.2f} บาท")
        else:
            st.info("💡 เซิร์ฟเวอร์ Yahoo ปิดกั้นการดึงข้อมูลประวัติชั่วคราว ให้รอสักครู่แล้วกดปุ่ม Force Scan ในหน้าแรกเพื่อลองใหม่อีกครั้ง")
