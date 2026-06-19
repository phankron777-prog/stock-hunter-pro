import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import time
from datetime import datetime

# ==========================================================================
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG (v14.0 Apex Predator)
# ==========================================================================
st.set_page_config(page_title="Stock Hunter Pro v14.0", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

st.sidebar.markdown("## 🦅 Stock Hunter Pro v14.0")
st.sidebar.markdown("### `The Apex Predator Engine`")
st.sidebar.caption("🔒 พัฒนาตามพิมพ์เขียวระบบเทรดสถาบัน: ตรวจสอบความปลอดภัย 4 ชั้น เพื่อชัยชนะที่แท้จริง")
st.sidebar.divider()

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital_thb = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต (บาท THB):", min_value=1000, value=100000, step=5000)

# ปรับค่าเริ่มต้น (Default) เป็น 1% ตามกฎการอยู่รอดของโปรเทรดเดอร์
risk_per_trade = st.sidebar.slider(
    "ความเสี่ยงที่ยอมรับได้ต่อไม้ (% ของพอร์ต):", 
    min_value=0.25, max_value=5.0, value=1.0, step=0.25,
    help="แนะนำที่ 1% เพื่อให้อยู่รอดในตลาดได้ระยะยาวแม้จะแพ้ติดต่อกัน"
)

max_portfolio_heat = st.sidebar.slider("เพดานความเสี่ยงรวมทั้งพอร์ตพร้อมกัน (%):", min_value=1.0, max_value=15.0, value=5.0, step=0.5)
max_position_pct = st.sidebar.slider("เพดานสัดส่วนเงินทุนสูงสุดต่อหุ้น 1 ตัว (%):", min_value=5, max_value=50, value=20, step=5)

st.sidebar.divider()
st.sidebar.markdown("### 💵 อิมพอร์ตข้อมูล Dime! Config")
fx_rate = st.sidebar.number_input("อัตราแลกเปลี่ยน USD/THB (รวม Spread หน้าแอป):", min_value=30.0, max_value=45.0, value=36.5, step=0.1)
dime_fee_pct = st.sidebar.slider("ค่าธรรมเนียมรวม FX Spread ตอนซื้อ-ขาย (%):", min_value=0.0, max_value=1.5, value=0.30, step=0.05)

st.sidebar.divider()
st.sidebar.markdown("### 🏎️ ขีดจำกัดทางสถิติและคณิตศาสตร์")
atr_multiplier = st.sidebar.slider("ตัวคูณระยะ Stop Loss (ATR Multiplier):", min_value=1.0, max_value=3.0, value=1.5, step=0.1, help="สูตรคำนวณ True ATR จริง ปรับ 1.5 - 2.0 กำลังแน่น")

# ปรับเป้าหมายกำไรเป็น 2.5R ขั้นต่ำตามคำแนะนำของคุณ
rr_ratio = st.sidebar.slider("อัตราส่วนผลตอบแทนต่อความเสี่ยง (Risk Reward Ratio):", min_value=1.5, max_value=4.0, value=2.5, step=0.1, help="เป้าหมายกำไรเป็นกี่เท่าของระยะคัท")

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดวิเคราะห์แผนเทรด:",
    [
        "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด",
        "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)"
    ]
)

# ==========================================================================
# 📦 2. INSTITUTIONAL FILTERING & TRUE ATR MATHEMATICAL ENGINE
# ==========================================================================
@st.cache_data(ttl=15)
def fetch_timeframe_data(ticker, interval="1h", _state_key=0):
    time.sleep(0.3)
    period_map = {"15m": "5d", "1h": "1mo", "1d": "6mo"}
    period = period_map.get(interval, "1mo")
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        df = df[(df['Close'] > 0) & (df['High'] > 0) & (df['Low'] > 0)]
        return df if not df.empty else None
    except Exception:
        return None

def compute_indicators_and_signals(df):
    """ แก้บั๊กคำนวณ True ATR จริง และเพิ่มตัวกรองประสิทธิภาพสูงตามพิมพ์เขียวของคุณ """
    if df is None or len(df) < 200: # ต้องใช้ข้อมูล 200 แท่งเพื่อคำนวณ EMA 200
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
    
    # 4. [🔥 แก้ไขจุดตาย] คำนวณ TRUE ATR จริง ขจัดปัญหาราคา Gap เปิดกระโดด
    df['Prev_Close'] = df['Close'].shift(1)
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['True_Range'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)
    df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean() # ใช้ Exponential moving average ของ True Range
    
    # 5. โวลุ่มฟิลเตอร์
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    
    return df

def safe_signal_block_v14(df_proc, current_price, atr_mult, rr, spy_ok=True):
    """ v14.0: ระบบคัดกรองสัญญาณเด็ดขาด ไร้การ Short หุ้น ขจัดสัญญาณขยะสภาวะ Sideway """
    if df_proc is None or len(df_proc) < 2:
        return None
    
    last_valid_row = df_proc.iloc[-2] # ยึดข้อมูลแท่งที่ปิดแล้วเป็นหลักเพื่อความเสถียร
    
    if pd.isna(last_valid_row['EMA_20']) or pd.isna(last_valid_row['EMA_50']) or pd.isna(last_valid_row['EMA_200']):
        return None
    if current_price is None or current_price <= 0 or np.isnan(current_price):
        return None

    atr = last_valid_row['ATR']
    if pd.isna(atr) or atr <= 0:
        atr = current_price * 0.02

    # โครงสร้างคณิตศาสตร์คัดกรองสากลตามที่คุณแนะนำ
    trend_ok = (last_valid_row['Close'] > last_valid_row['EMA_20']) and \
               (last_valid_row['EMA_20'] > last_valid_row['EMA_50']) and \
               (last_valid_row['EMA_50'] > last_valid_row['EMA_200'])
               
    rsi_ok = (55 <= last_valid_row['RSI'] <= 80)
    macd_ok = (last_valid_row['MACD'] > last_valid_row['Signal_Line'])
    vol_ok = (last_valid_row['Volume'] > (last_valid_row['Vol_MA20'] * 1.3))

    # ตรวจสอบเงื่อนไขการออกไม้ฝั่ง BUY
    if trend_ok and rsi_ok and macd_ok and vol_ok and spy_ok:
        signal = "BUY / LONG"
    elif trend_ok and not vol_ok:
        signal = "🟨 WAIT (Volume ต่ำไม่ผ่านเกณฑ์)"
    elif trend_ok and (last_valid_row['RSI'] > 80):
        signal = "🟨 WAIT (RSI ตึงเกินขอบเขต)"
    elif not spy_ok:
        signal = "🟨 WAIT (ดัชนี SPY อยู่ใต้เส้น 50 ภาพรวมเสี่ยง)"
    else:
        signal = "⬜ NO TRADE (แนวโน้มขาลง/สภาวะ Sideway พักตัว)"

    # ระยะ Stop Loss และเป้าหมายกำไรอิงตาม True ATR และ RR Ratio ใหม่
    sl = current_price - (atr_mult * atr)
    tp = current_price + (rr * (atr_mult * atr))

    risk_per_share = abs(current_price - sl)
    if risk_per_share < 1e-5:
        return None

    # จุดขยับสกัดการขาดทุน (Breakeven Trigger เมื่อวิ่งไปได้ 0.7R)
    breakeven_trigger = current_price + (risk_per_share * 0.7)

    return {
        "signal": signal, "tp": tp, "sl": sl, "atr": atr,
        "risk_per_share": risk_per_share, "current_price": current_price,
        "breakeven_trigger": breakeven_trigger
    }

def compute_position_size_v14(sig, account_capital_thb, risk_per_trade_pct, max_position_pct, fx_rate, dime_fee_pct):
    try:
        current_price_thb = sig["current_price"] * fx_rate
        risk_per_share_thb = sig["risk_per_share"] * fx_rate
        
        max_loss_allowed_thb = account_capital_thb * (risk_per_trade_pct / 100)
        shares_by_risk = max_loss_allowed_thb / risk_per_share_thb

        max_capital_allowed_thb = account_capital_thb * (max_position_pct / 100)
        shares_by_capital_cap = max_capital_allowed_thb / current_price_thb

        final_shares = min(shares_by_risk, shares_by_capital_cap)
        final_shares = max(final_shares, 0.0)

        raw_cost_thb = final_shares * current_price_thb
        dime_buffer_thb = raw_cost_thb * (dime_fee_pct / 100)
        
        # ปัดเศษลงเพื่อความชัวร์ ป้องกันออเดอร์โดน Dime! ปฏิเสธ
        total_cost_thb = np.floor(raw_cost_thb + dime_buffer_thb)
        
        cost_usd = total_cost_thb / fx_rate
        capped_by_position_limit = shares_by_capital_cap < shares_by_risk

        return {
            "shares": round(final_shares, 4), "cost_thb": total_cost_thb, "cost_usd": cost_usd,
            "max_loss_allowed_thb": max_loss_allowed_thb, "actual_risk_thb": final_shares * risk_per_share_thb,
            "capped_by_position_limit": capped_by_position_limit,
        }
    except ZeroDivisionError:
        return {"shares": 0.0, "cost_thb": 0.0, "cost_usd": 0.0, "max_loss_allowed_thb": 0.0, "actual_risk_thb": 0.0, "capped_by_position_limit": False}

# ==========================================================================
# 🎯 3. UI & MODULE CONTROLLERS
# ==========================================================================
if menu == "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด":
    st.title("🦅 ระบบคัดกรองสัญญาร่วมสถาบันและคำนวณหน้าตัก (Dime! Apex v14.0)")
    
    if st.button("🔄 [FORCE REFRESH] อัปเดตราคาสดและดัชนีตลาดทันที", type="primary"):
        st.session_state.refresh_key += 1
        st.rerun()

    # --- MARKET FILTER MODULE ---
    spy_df = fetch_timeframe_data("SPY", interval=tf_choice if "tf_choice" in locals() else "1h", _state_key=st.session_state.refresh_key)
    spy_ok = True
    if spy_df is not None and len(spy_df) >= 50:
        spy_df['EMA_50'] = spy_df['Close'].ewm(span=50, adjust=False).mean()
        spy_current = spy_df['Close'].iloc[-1]
        spy_ema50 = spy_df['EMA_50'].iloc[-2]
        spy_ok = spy_current > spy_ema50
        if spy_ok:
            st.success(f"📊 **Market Filter (SPY): PASS** | ดัชนีหลักอยู่เหนือเส้นขาขึ้น (${spy_current:.2f} > ${spy_ema50:.2f}) ภาพรวมเล่นง่าย")
        else:
            st.error(f"🚨 **Market Filter (SPY): RISK** | ดัชนีหลักหลุดเส้นเฉลี่ย (${spy_current:.2f} < ${spy_ema50:.2f}) ตลาดขาลง ระบบจะระงับออเดอร์ฝั่ง BUY")
    else:
        st.caption("⚠️ ไม่สามารถดึงข้อมูลดัชนี SPY ได้ชั่วคราว ระบบข้ามไปกรองตัวหุ้นรายตัว")

    watchlist_str = st.text_input("ระบุสัญลักษณ์หุ้นรายตัวที่ต้องการเฝ้าระวัง (คั่นด้วย ,):", "LITE, AXTI, NVDA, PLTR, AMD, TSLA")
    tickers = [t.strip().upper() for t in watchlist_str.split(",") if t.strip()]
    tickers = list(dict.fromkeys(tickers))[:15]
    tf_choice = st.selectbox("กรอบเวลาแท่งเทียน (Timeframe):", ["1h", "15m", "1d"])

    scanned_data = []
    raw_price_data = {}
    total_committed_risk_thb = 0.0

    if tickers:
        p_bar = st.progress(0)
        for idx, t in enumerate(tickers):
            raw_df = fetch_timeframe_data(t, interval=tf_choice, _state_key=st.session_state.refresh_key)
            raw_price_data[t] = raw_df
            df_proc = compute_indicators_and_signals(raw_df)

            if df_proc is not None:
                current_price = df_proc['Close'].iloc[-1]
                sig = safe_signal_block_v14(df_proc, current_price, atr_multiplier, rr_ratio, spy_ok)

                if sig is not None:
                    pos = compute_position_size_v14(sig, account_capital_thb, risk_per_trade, max_position_pct, fx_rate, dime_fee_pct)
                    
                    if sig["signal"] == "BUY / LONG":
                        total_committed_risk_thb += pos["actual_risk_thb"]
                        signal_icon = "🟩"
                    elif "WAIT" in sig["signal"]:
                        signal_icon = "🟨"
                    else:
                        signal_icon = "⬜"
                        
                    cap_note = " ⚠️" if pos["capped_by_position_limit"] else ""

                    scanned_data.append({
                        "หุ้นซิ่ง": t, "ราคาสด (USD)": f"${sig['current_price']:.2f}",
                        "สัญญาณวินัยเหล็ก": f"{signal_icon} {sig['signal']}",
                        "เป้ากำไร TP (USD)": f"{rr_ratio:.1f}R (${sig['tp']:.2f})" if sig["signal"] == "BUY / LONG" else "-", 
                        "จุดคัท SL (USD)": f"${sig['sl']:.2f}" if sig["signal"] == "BUY / LONG" else "-",
                        "จำนวนเศษหุ้น": f"{pos['shares']:.4f}" if sig["signal"] == "BUY / LONG" else "-",
                        "ระบุเงินซื้อใน Dime!": f"{pos['cost_thb']:,.0f} THB{cap_note}" if sig["signal"] == "BUY / LONG" else "ข้าม",
                        "คิดเป็นดอลลาร์": f"${pos['cost_usd']:.2f}" if sig["signal"] == "BUY / LONG" else "-"
                    })
                else:
                    scanned_data.append({
                        "หุ้นซิ่ง": t, "ราคาสด (USD)": "-", "สัญญาณวินัยเหล็ก": "⬜ ข้อมูลผันผวนหลุดเกณฑ์คณิตศาสตร์",
                        "เป้ากำไร TP (USD)": "-", "จุดคัท SL (USD)": "-", "จำนวนเศษหุ้น": "-", "ระบุเงินซื้อใน Dime!": "-", "คิดเป็นดอลลาร์": "-"
                    })
            else:
                scanned_data.append({
                    "หุ้นซิ่ง": t, "ราคาสด (USD)": "-", "สัญญาณวินัยเหล็ก": "⬜ โครงสร้างแท่งราคาประวัติศาสตร์ไม่พอ (<200 แท่ง)",
                    "เป้ากำไร TP (USD)": "-", "จุดคัท SL (USD)": "-", "จำนวนเศษหุ้น": "-", "ระบุเงินซื้อใน Dime!": "-", "คิดเป็นดอลลาร์": "-"
                })
            p_bar.progress((idx + 1) / len(tickers))

    if scanned_data:
        st.dataframe(pd.DataFrame(scanned_data), use_container_width=True, hide_index=True)

        # Portfolio Heat Check หน่วยบาท
        st.divider()
        st.subheader("🔥 ตารางประเมินผลกระทบต่อหน้าตักทั้งหมด (Portfolio Heat Check)")
        heat_pct = (total_committed_risk_thb / account_capital_thb * 100) if account_capital_thb > 0 else 0
        heat_limit_thb = account_capital_thb * (max_portfolio_heat / 100)

        hc1, hc2, hc3 = st.columns(3)
        hc1.metric("ความเสี่ยงรวมหากโดนกิน Stop Loss ไม้ที่เปิดระบบพร้อมกัน", f"{total_committed_risk_thb:,.2f} บาท")
        hc2.metric("สัดส่วนความเสี่ยงรวมต่อขนาดพอร์ตจริง", f"{heat_pct:.2f}%")
        hc3.metric("เพดานรวมสูงสุดที่ระบบล็อกไว้", f"{max_portfolio_heat:.1f}% ({heat_limit_thb:,.2f} บาท)")

        if heat_pct > max_portfolio_heat:
            st.error(f"🚨 **ความเสี่ยงรวมล้นเพดานพอร์ต!** ระบบแนะนำเลือกเคาะซื้อเฉพาะ 1-2 ตัวแรกที่โวลุ่มหนาแน่นที่สุดเพื่อความปลอดภัย")

elif menu == "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)":
    st.title("📐 แผนกลยุทธ์วินัยรายตัว & Dime! Real-time Override v14.0")
    
    c_t1, c_t2, c_t3 = st.columns(3)
    t_stock = c_t1.text_input("พิมพ์ตัวย่อหุ้นที่ต้องการเจาะลึกออเดอร์:", "NVDA").upper().strip()
    t_frame = c_t2.selectbox("กรอบเวลาวิเคราะห์เทคนิคัล (Timeframe):", ["15m", "1h", "1d"])
    use_override = c_t3.checkbox("🚨 ใช้ราคาสดหน้าจอมือถือแอป Dime! แทนเพื่อขจัดดีเลย์")

    if not t_stock:
        st.info("กรุณาระบุตัวย่อหุ้น")
    else:
        raw_df = fetch_timeframe_data(t_stock, interval=t_frame, _state_key=st.session_state.refresh_key)
        df_proc = compute_indicators_and_signals(raw_df)

        if df_proc is not None:
            current_price = c_t3.number_input("พิมพ์ราคาสดที่คุณเห็นในแอป Dime! ตอนนี้ ($):", min_value=0.01, value=float(df_proc['Close'].iloc[-1]), step=0.01) if use_override else df_proc['Close'].iloc[-1]
            sig = safe_signal_block_v14(df_proc, current_price, atr_multiplier, rr_ratio, spy_ok=True)

            if sig is None:
                st.error("ระยะห่างราคาแคบเกินไปหรือข้อมูลประวัติศาสตร์ย้อนหลังไม่สมบูรณ์")
            else:
                pos = compute_position_size_v14(sig, account_capital_thb, risk_per_trade, max_position_pct, fx_rate, dime_fee_pct)
                
                if sig["signal"] == "BUY / LONG":
                    signal_icon = "🟩"
                elif "WAIT" in sig["signal"]:
                    signal_icon = "🟨"
                else:
                    signal_icon = "⬜"

                cx1, cx2, cx3, cx4 = st.columns(4)
                cx1.metric("ราคาตั้งต้นระบบ (USD)", f"${sig['current_price']:.2f}")
                cx2.markdown(f"🤖 **สัญญาณหน้างาน:** \n## {signal_icon} {sig['signal']}")
                cx3.metric("🎯 ขายทำกำไร TP (USD)", f"${sig['tp']:.2f}")
                cx4.metric("🛑 หนีตาย Stop Loss (USD)", f"${sig['sl']:.2f}")

                cap_note = f" *(โดนจำกัดด้วยกฎสัดส่วนพอร์ต {max_position_pct}%)*" if pos["capped_by_position_limit"] else ""
                
                # กล่องคำสั่ง Action Plan ปรับลดระดับความมั่นใจเกินจริงตามที่คุณเตือน
                st.success(
                    f"📥 **คัมภีร์ระบุคำสั่งซื้อขายบนแอป Dime! เพื่อเพิ่มความได้เปรียบทางสถิติ**\n\n"
                    f"1️⃣ **ขั้นตอนตอนซื้อ:** กดปุ่มซื้อใน Dime! -> เลือกโหมด **'ระบุจำนวนเงิน'** -> ป้อนตัวเลขจำนวนเต็ม **{pos['cost_thb']:,.0f} บาท** ลงไป\n"
                    f"2️⃣ **สัดส่วนที่ได้:** คุณจะได้เศษหุ้นประมาณ **{pos['shares']:.4f} หุ้น** (มูลค่ารวมค่าธรรมเนียมประมาณ ${pos['cost_usd']:.2f})\n"
                    f"3️⃣ **การบริหารหน้างาน:** หากราคาปิดหลุดจุด **${sig['sl']:.2f}** ต้องตัดใจขายคัททิ้งทันที ความเสียหายโดยปกติจะถูกจำกัดอยู่ที่ประมาณ **{pos['actual_risk_thb']:,.2f} บาท** {cap_note} *(หมายเหตุ: หากเกิดกรณีเปิด Gap Down รุนแรงหรือข่าวกระทันหัน ราคาหน้างานจริงอาจแย่กว่าจุด SL ได้เสมอ)*\n"
                    f"4️⃣ **แผนขยับบังทุน:** หากราคาวิ่งถูกทางไปจนถึงจุด **${sig['breakeven_trigger']:.2f}** ให้พิจารณาขยับจุด Stop Loss ในใจขึ้นมาตั้งดักไว้ที่ราคาทุน เพื่อลดโอกาสขาดทุนให้เหลือน้อยที่สุด"
                )

                # Quick Trade Plan Exporter
                log_text = f"📋 [PLAN] {t_stock} ({t_frame}) | Action: {sig['signal']} | Buy: {pos['cost_thb']:,.0f} THB (~{pos['shares']:.4f} Shares) | Entry: ${sig['current_price']:.2f} | TP: ${sig['tp']:.2f} | SL: ${sig['sl']:.2f} | Max Loss: {pos['actual_risk_thb']:,.0f} THB"
                st.text_area("📋 คัดลอกข้อความแผนการเทรดด่วนไปเก็บไว้ใน Line / Note:", log_text, height=70)

                # วาดกราฟเทคนิคัลระดับสากลแสดงเส้นแนวโน้มใหญ่
                plot_df = df_proc.tail(40)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name='ราคาหุ้น'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#2eb85c', width=1.5), name='EMA 20'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_50'], line=dict(color='#ffc107', width=1.5), name='EMA 50'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_200'], line=dict(color='#dc3545', width=2), name='EMA 200 (เส้นแบ่งแนวโน้มใหญ่)'))
                
                if sig["signal"] == "BUY / LONG":
                    fig.add_hline(y=sig['tp'], line_dash="dash", line_color="green", annotation_text=f"Target Price ({rr_ratio}R)")
                    fig.add_hline(y=sig['sl'], line_dash="dash", line_color="red", annotation_text="Stop Loss")
                
                fig.update_layout(template="plotly_dark", title=f"แผนภูมิวิเคราะห์คัดเกรดสถาบัน v14 ({t_frame}) ของหุ้น {t_stock}", height=380, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("ไม่สามารถดึงข้อมูลหุ้นตัวนี้ได้เนื่องจากข้อมูลประวัติสถิติไม่เพียงพอ (<200 แท่ง) กรุณาตรวจสอบตัวย่อหรือกรอบเวลาอีกครั้ง")
