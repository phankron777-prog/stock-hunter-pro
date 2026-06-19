import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import time
from datetime import datetime, timedelta

# ==========================================================================
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG (v15.0 Ultimate Quant)
# ==========================================================================
st.set_page_config(page_title="Stock Hunter Ultimate Quant v15.0", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0
if "kill_switch_triggered" not in st.session_state:
    st.session_state.kill_switch_triggered = False

st.sidebar.markdown("## 🦅 Stock Hunter Ultimate Quant v15.0")
st.sidebar.markdown("### `The Hedge Fund Core Engine`")
st.sidebar.caption("🔒 พัฒนาสู่ระบบ Quant เต็มรูปแบบ: มีระบบ Backtest ย้อนหลัง, ตัวกรองวันประกาศงบ และระบบจัดอันดับคะแนน")
st.sidebar.divider()

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital_thb = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต (บาท THB):", min_value=1000, value=100000, step=5000)
fx_rate = st.sidebar.number_input("อัตราแลกเปลี่ยน USD/THB (รวม Spread):", min_value=30.0, max_value=45.0, value=36.5, step=0.1)
dime_fee_pct = st.sidebar.slider("ค่าธรรมเนียมรวม FX Spread (%):", min_value=0.0, max_value=1.5, value=0.30, step=0.05)
atr_multiplier = st.sidebar.slider("ตัวคูณระยะ Stop Loss (ATR Multiplier):", min_value=1.0, max_value=3.0, value=2.0, step=0.1)

st.sidebar.divider()
# [🔥 เพิ่มระบบ Kill Switch]
st.sidebar.markdown("### 🛑 ระบบเซฟตี้ Kill Switch")
consecutive_losses = st.sidebar.number_input("จำนวนไม้ที่แพ้ติดกันปัจจุบัน:", min_value=0, max_value=10, value=0)
weekly_drawdown_pct = st.sidebar.slider("เปอร์เซ็นต์ขาดทุนรวมในสัปดาห์นี้ (%):", min_value=0.0, max_value=15.0, value=0.0, step=0.5)

if consecutive_losses >= 4 or weekly_drawdown_pct >= 5.0:
    st.sidebar.error("🚨 KILL SWITCH ACTIVATED! ระบบสั่งระงับการเทรดทุกกรณีเพื่อป้องกันอารมณ์และการล้างพอร์ต")
    st.session_state.kill_switch_triggered = True
else:
    st.session_state.kill_switch_triggered = False

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดการทำงาน:",
    [
        "⚡ 1. หน้าแผงควบคุมสแกนสด & จัดอันดับ Ranking",
        "📊 2. ระบบทดสอบกลยุทธ์ย้อนหลัง (Backtest Engine)"
    ]
)

# ==========================================================================
# 📦 2. QUANT MATHEMATICAL & INDICATOR ENGINE
# ==========================================================================
@st.cache_data(ttl=30)
def fetch_quant_data(ticker, period="3y", interval="1d"):
    """ ดึงข้อมูลประวัติย้อนหลังยาวนานพอสำหรับทำ Backtest และสแกนเทรนด์ """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        df = df[(df['Close'] > 0) & (df['High'] > 0) & (df['Low'] > 0)]
        return df if len(df) >= 200 else None
    except Exception:
        return None

@st.cache_data(ttl=3600)
def check_earnings_within_7_days(ticker):
    """ [🔥 แก้ไขจุดตาย] ตัวกรองวันประกาศงบล่วงหน้า 7 วัน ป้องกัน Black Swan ตอนเปิดตลาด """
    try:
        stock = yf.Ticker(ticker)
        calendar = stock.calendar
        if calendar is not None and 'Earnings Date' in calendar:
            earn_dates = calendar['Earnings Date']
            if earn_dates:
                next_earn = earn_dates[0]
                # แปลงเป็น datetime object
                if isinstance(next_earn, datetime):
                    next_earn = next_earn.replace(tzinfo=None)
                else:
                    next_earn = datetime.combine(next_earn, datetime.min.time())
                
                days_to_earnings = (next_earn - datetime.now()).days
                if 0 <= days_to_earnings <= 7:
                    return True, days_to_earnings
        return False, -1
    except Exception:
        return False, -1

def compute_quant_indicators(df, spy_df=None):
    if df is None or len(df) < 200:
        return None
    df = df.copy()
    
    # 1. เทรนด์ฟิลเตอร์ 3 ชั้น
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # 2. โมเมนตัม MACD
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # 3. ดัชนี RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 4. คำนวณ TRUE ATR จริง
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['True_Range'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)
    df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
    
    # 5. โว ลุ่ม ฟิลเตอร์ & Breakout 20 วัน
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    df['Highest_Close_20'] = df['Close'].shift(1).rolling(window=20).max()
    
    # 6. [🔥 เพิ่มระบบ Relative Strength] คำนวณ RS คะแนนเทียบกับ SPY ย้อนหลัง 90 วัน
    if spy_df is not None:
        df['Stock_Return_90'] = df['Close'].pct_change(periods=90)
        spy_df_copy = spy_df.copy()
        spy_df_copy['SPY_Return_90'] = spy_df_copy['Close'].pct_change(periods=90)
        # ทำการ Reindex ให้ตรงกันเพื่อดึงข้อมูลมาคำนวณสัดส่วน RS
        df = df.join(spy_df_copy['SPY_Return_90'], how='left')
        df['RS_Score'] = df['Stock_Return_90'] - df['SPY_Return_90']
    else:
        df['RS_Score'] = 0.0

    return df

def execute_signal_and_ranking_engine(df_proc, ticker, spy_ok=True):
    """ [🔥 พัฒนาใหม่] ระบบคิดคะแนนจริตระบบสถาบัน (0-100) และคัดกรองวันงบออก """
    if df_proc is None or len(df_proc) < 2:
        return None
    
    last_row = df_proc.iloc[-1]
    
    # เช็คเงื่อนไขงบการเงินล่วงหน้า
    is_earnings_near, days_left = check_earnings_within_7_days(ticker)
    
    # คำนวณคะแนนรวมระบบ (Ranking Score) จากฟิลเตอร์แต่ละตัว
    score = 0
    
    # เกณฑ์เทรนด์ 4 ชั้นตามพิมพ์เขียวใหม่ (สูงสุด 40 คะแนน)
    trend_ok = (last_row['Close'] > last_row['EMA_20']) and (last_row['EMA_20'] > last_row['EMA_50']) and (last_row['EMA_50'] > last_row['EMA_200'])
    if trend_ok: score += 40
    
    # เกณฑ์โมเมนตัม MACD (สูงสุด 15 คะแนน)
    macd_ok = (last_row['MACD'] > last_row['Signal_Line'])
    if macd_ok: score += 15
    
    # เกณฑ์ RSI โซนแข็งแกร่ง (สูงสุด 15 คะแนน)
    rsi_ok = (55 <= last_row['RSI'] <= 80)
    if rsi_ok: score += 15
    
    # [🔥 ปรับปรุงเกณฑ์ Volume Spike + Breakout 20 วัน] (สูงสุด 15 คะแนน)
    vol_spike = (last_row['Volume'] > last_row['Vol_MA20'] * 1.5) and (last_row['Close'] > last_row['Highest_Close_20'])
    if vol_spike: score += 15
    elif last_row['Volume'] > last_row['Vol_MA20'] * 1.3: score += 10
        
    # เกณฑ์ความแข็งแกร่งสัมพัทธ์ RS (สูงสุด 15 คะแนน)
    rs_ok = last_row['RS_Score'] > 0
    if rs_ok: score += 15

    # แยกแยะสัญญาณเด็ดขาด
    if st.session_state.kill_switch_triggered:
        signal = "⬜ LOCK (Kill Switch ทำงาน)"
    elif is_earnings_near:
        signal = f"🟨 WAIT (งบออกใน {days_left} วัน เสี่ยงเกินไป)"
    elif not spy_ok:
        signal = "🟨 WAIT (ดัชนี SPY หลุดเส้นขาขึ้น)"
    elif score >= 75 and trend_ok:
        signal = "BUY / LONG"
    elif trend_ok:
        signal = "🟨 WAIT (สัญญาณสนับสนุนอ่อนแอ)"
    else:
        signal = "⬜ NO TRADE (แนวโน้มไม่สอดคล้อง)"

    # [🔥 เพิ่มระบบ Dynamic Position Sizing] ปรับเปลี่ยน Risk ตามคะแนนสถาบัน
    if score >= 90:
        dynamic_risk = 1.5  # เกรด A+
        grade = "A+"
    elif score >= 75:
        dynamic_risk = 1.0  # เกรด A
        grade = "A"
    else:
        dynamic_risk = 0.5  # เกรด B
        grade = "B"

    return {
        "ticker": ticker, "signal": signal, "score": score, "grade": grade, "dynamic_risk": dynamic_risk,
        "current_price": last_row['Close'], "atr": last_row['ATR'], "rs_score": last_row['RS_Score']
    }

# ==========================================================================
# 📊 3. THE BACKTEST ENGINE ENGINE (ทดสอบย้อนหลังสตรีมไลน์)
# ==========================================================================
def run_quant_backtest(df_proc, initial_capital=100000, atr_mult=2.0):
    """ [🔥 ชิ้นส่วนสำคัญที่สุด] ระบบทดสอบย้อนหลังอิงตาม True ATR Trailing Stop """
    if df_proc is None or len(df_proc) < 200:
        return None
        
    capital = initial_capital
    in_position = False
    entry_price = 0
    stop_loss = 0
    trades = []
    
    # ลูปรันข้อมูลย้อนหลังแท่งต่อแท่ง
    for i in range(200, len(df_proc)):
        row = df_proc.iloc[i]
        prev_row = df_proc.iloc[i-1]
        
        # เงื่อนไขตรวจสอบความสอดคล้องสัญญาณขาขึ้น
        trend_ok = (prev_row['Close'] > prev_row['EMA_20']) and (prev_row['EMA_20'] > prev_row['EMA_50']) and (prev_row['EMA_50'] > prev_row['EMA_200'])
        rsi_ok = (55 <= prev_row['RSI'] <= 80)
        macd_ok = (prev_row['MACD'] > prev_row['Signal_Line'])
        vol_ok = (prev_row['Volume'] > prev_row['Vol_MA20'] * 1.3)
        
        # จังหวะเข้าซื้อ (Entry)
        if not in_position and trend_ok and rsi_ok and macd_ok and vol_ok:
            in_position = True
            entry_price = row['Open'] # เข้าซื้อราคาเปิดของแท่งถัดไปเพื่อความสมจริง
            stop_loss = entry_price - (atr_mult * prev_row['ATR'])
            trades.append({"type": "BUY", "date": df_proc.index[i], "price": entry_price})
            continue
            
        # จังหวะถือครองและใช้ระบบ [🔥 Chandelier Trailing Stop] ขยับเส้นตามขึ้นไปเรื่อยๆ
        if in_position:
            # ขยับ Stop Loss ขึ้นเมื่อราคาสร้างจุดสูงสุดใหม่ ปล่อยให้กำไรรันไปได้ยาวๆ
            potential_trailing_sl = row['High'] - (atr_mult * row['ATR'])
            if potential_trailing_sl > stop_loss:
                stop_loss = potential_trailing_sl
                
            # จังหวะชนคัทเอาท์ออกหนีตาย (Exit)
            if row['Low'] <= stop_loss:
                in_position = False
                exit_price = min(row['Open'], stop_loss) # หากเปิดโดดลงต่ำกว่า ให้หลุดที่ราคาเปิดทันที
                pnl_pct = (exit_price - entry_price) / entry_price
                capital = capital * (1 + pnl_pct)
                trades.append({"type": "SELL", "date": df_proc.index[i], "price": exit_price, "pnl_pct": pnl_pct, "final_capital": capital})

    # สรุปสถิติผลลัพธ์คณิตศาสตร์ส่งให้ผู้ใช้วิเคราะห์
    if not trades or len([t for t in trades if t["type"] == "SELL"]) == 0:
        return None
        
    sell_trades = [t for t in trades if t["type"] == "SELL"]
    wins = [t for t in sell_trades if t["pnl_pct"] > 0]
    losses = [t for t in sell_trades if t["pnl_pct"] <= 0]
    
    win_rate = (len(wins) / len(sell_trades)) * 100 if sell_trades else 0
    total_gain = sum([t["pnl_pct"] for t in wins])
    total_loss = abs(sum([t["pnl_pct"] for t in losses]))
    
    profit_factor = total_gain / (total_loss + 1e-9)
    avg_win = (total_gain / len(wins)) * 100 if wins else 0
    avg_loss = (total_loss / len(losses)) * 100 if losses else 0
    
    # คำนวณหาจุด Max Drawdown ย้อนหลัง
    cap_series = [initial_capital] + [t["final_capital"] for t in sell_trades]
    peak = cap_series[0]
    max_dd = 0
    for c in cap_series:
        if c > peak: peak = c
        dd = (peak - c) / peak * 100
        if dd > max_dd: max_dd = dd

    return {
        "win_rate": win_rate, "profit_factor": profit_factor, "max_dd": max_dd,
        "total_trades": len(sell_trades), "avg_win": avg_win, "avg_loss": avg_loss,
        "final_balance": capital
    }

# ==========================================================================
# 🎯 4. UI CONTROLLERS & MODULES
# ==========================================================================
spy_raw = fetch_quant_data("SPY", period="3y", interval="1d")
spy_df = compute_quant_indicators(spy_raw)

# เช็คความแข็งแกร่งดัชนีตลาดภาพรวม
spy_ok = True
if spy_df is not None:
    spy_ok = spy_df['Close'].iloc[-1] > spy_df['EMA_50'].iloc[-1]

if menu == "⚡ 1. หน้าแผงควบคุมสแกนสด & จัดอันดับ Ranking":
    st.title("🦅 ตารางจัดอันดับหุ้นผู้นำตลาดด้วยคะแนน Quant สถาบัน (v15.0)")
    
    if st.button("🔄 อัปเดตข้อมูลราคาสด สแกนวันประกาศงบ และสลับลำดับ Ranking ทันที", type="primary"):
        st.session_state.refresh_key += 1
        st.rerun()

    # ยืนยันสถานะตลาดภาพรวม
    if spy_ok:
        st.success("📊 **Market Regime: BULLISH (SPY > EMA50)** ภาพรวมตลาดเปิดทางให้วางความเสี่ยงฝั่งซื้อได้อย่างปลอดภัย")
    else:
        st.error("🚨 **Market Regime: BEARISH (SPY < EMA50)** ตลาดภาพรวมอ่อนแอ ระบบสั่งกักสัญญาทุกตัวให้อยู่ในสถานะ WAIT")

    watchlist_str = st.text_input("กรอกชื่อหุ้นคั่นด้วยเครื่องหมายจุลภาค (,):", "NVDA, PLTR, AMD, TSLA, META, AAPL, ASTS")
    tickers = [t.strip().upper() for t in watchlist_str.split(",") if t.strip()]
    
    ranking_results = []
    
    if tickers:
        p_bar = st.progress(0)
        for idx, t in enumerate(tickers):
            raw_data = fetch_quant_data(t, period="6mo", interval="1d")
            df_proc = compute_quant_indicators(raw_data, spy_df)
            
            res = execute_signal_and_ranking_engine(df_proc, t, spy_ok)
            if res:
                # คำนวณจำนวนขนาดไม้แบบ Dynamic อัตโนมัติจากคะแนนเกรด
                risk_amt_thb = account_capital_thb * (res["dynamic_risk"] / 100)
                sl_dist_usd = atr_multiplier * res["atr"]
                
                if sl_dist_usd > 0:
                    shares_to_buy = risk_amt_thb / (sl_dist_usd * fx_rate)
                    cost_thb = shares_to_buy * res["current_price"] * fx_rate
                    # รวม buffer ค่าธรรมเนียม
                    cost_thb_with_fee = np.floor(cost_thb * (1 + dime_fee_pct/100))
                else:
                    shares_to_buy, cost_thb_with_fee = 0, 0

                ranking_results.append({
                    "คะแนน (0-100)": res["score"],
                    "หุ้นซิ่ง": t,
                    "เกรดระบบ": res["grade"],
                    "ราคาสด": f"${res['current_price']:.2f}",
                    "สัญญาณสัญชาตญาณเหล็ก": res["signal"],
                    "Dynamic Risk": f"{res['dynamic_risk']}%",
                    "จำนวนเงินเคาะซื้อใน Dime!": f"{cost_thb_with_fee:,.0f} THB" if res["signal"] == "BUY / LONG" else "-",
                    "เศษหุ้นที่ได้": f"{shares_to_buy:.4f} หุ้น" if res["signal"] == "BUY / LONG" else "-",
                    "จุดตัดขาดทุนหน้างาน (SL)": f"${res['current_price'] - sl_dist_usd:.2f}" if res["signal"] == "BUY / LONG" else "-"
                })
            p_bar.progress((idx + 1) / len(tickers))
            
        if ranking_results:
            # [🔥 จัดทำระบบ Ranking เรียงคะแนนจากมากไปน้อยตามที่คุณขอ]
            rank_df = pd.DataFrame(ranking_results).sort_values(by="คะแนน (0-100)", ascending=False)
            st.subheader("🏆 รายการจัดลำดับคะแนนความได้เปรียบทางสถิติประจำวันนี้")
            st.dataframe(rank_df, use_container_width=True, hide_index=True)
            st.caption("💡 ข้อแนะนำสถาบัน: ให้เลือกพิจารณาเฉพาะหุ้นที่อยู่อันดับ 1-3 แรกของตารางที่มีสถานะสีเขียว (BUY) และเกรด A+ เท่านั้น")

elif menu == "📊 2. ระบบทดสอบกลยุทธ์ย้อนหลัง (Backtest Engine)":
    st.title("📊 ควอนท์เทสย้อนหลัง 3 ปีด้วยระบบสถิติวินัยเหล็ก (Backtest Engine)")
    st.caption("ระบบจะคำนวณเงินจำลอง 100,000 บาท รันระบบตามสัญญาณ True ATR Trailing Stop เพื่อพิสูจน์หาค่าความอยู่รอดที่แท้จริง")
    
    test_ticker = st.text_input("พิมพ์ตัวย่อหุ้นที่ต้องการทดสอบระบบ (Backtest):", "NVDA").upper().strip()
    
    if test_ticker:
        with st.spinner("🔄 กำลังย้อนเวลาประวัติศาสตร์ไปเก็บชุดข้อมูลราคา 3 ปีเพื่อประมวลผลควอนท์..."):
            bt_raw = fetch_quant_data(test_ticker, period="3y", interval="1d")
            bt_proc = compute_quant_indicators(bt_raw, spy_df)
            stats = run_quant_backtest(bt_proc, initial_capital=100000, atr_mult=atr_multiplier)
            
        if stats:
            st.subheader(f"📈 ผลลัพธ์ชุดสถิติการทดสอบระบบของหุ้น {test_ticker} ย้อนหลัง 3 ปี")
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("อัตราการชนะ (Win Rate)", f"{stats['win_rate']:.1f}%")
            
            # ตรวจสอบตัวช่วยคัดเกรดสถาบัน Profit Factor ไม่น้อยกว่า 1.3 ตามคำสั่งคุณ
            pf = stats['profit_factor']
            if pf >= 1.3:
                m2.metric("Profit Factor (ค่าความคุ้มค่า)", f"{pf:.2f}  ✅ ผ่านเกณฑ์สถาบัน")
            else:
                m2.metric("Profit Factor (ค่าความคุ้มค่า)", f"{pf:.2f}  ❌ ต่ำกว่าเกณฑ์ 1.3 (ระบบไม่ผ่าน)", delta_color="inverse")
                
            m3.metric("จุดขาดทุนสูงสุดย้อนหลัง (Max Drawdown)", f"-{stats['max_dd']:.1f}%")
            m4.metric("จำนวนเงินทุนปลายทางหลังจบแผน", f"{stats['final_balance']:,.2f} THB")
            
            st.divider()
            c1, c2 = st.columns(2)
            c1.info(f"🔹 **ขนาดการชนะเฉลี่ย (Average Win):** +{stats['avg_win']:.2f}% ของขนาดออเดอร์")
            c2.warning(f"🔸 **ขนาดการแพ้เฉลี่ย (Average Loss):** -{stats['avg_loss']:.2f}% ของขนาดออเดอร์")
            
            st.caption("📝 *หมายเหตุคณิตศาสตร์: ระบบทำ Backtest นี้ใช้สูตร Chandelier Trailing Stop (ขยับตามระยะเส้น ATR จากจุดสูงสุด) ทำให้ขนาดผลกำไรเฉลี่ยเวลาเจอหุ้นซิ่งรอบใหญ่ขยายตัวเกิน 2.5R อัตโนมัติ*")
        else:
            st.error("❌ ไม่พบประวัติการเข้าเทรดที่ตรงตามเกณฑ์วินัยเหล็กในหุ้นตัวนี้ในช่วง 3 ปีที่ผ่านมา หรือข้อมูลไม่เพียงพอ")
