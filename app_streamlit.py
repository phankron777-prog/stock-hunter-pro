import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import time
from datetime import datetime

# ==========================================================================
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG
# ==========================================================================
st.set_page_config(page_title="Stock Hunter Pro v11.0 (Dime! Edition)", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

st.sidebar.markdown("## 🦅 Stock Hunter Pro v11.0")
st.sidebar.markdown("### `The Dime! Pure Risk Engine`")
st.sidebar.caption("🔒 พัฒนาเพื่อการเล่นหุ้นซิ่งผ่าน Dime! รองรับเศษหุ้นและการคำนวณหน่วยบาท")
st.sidebar.divider()

# คำเตือนความเสี่ยงถาวร
st.sidebar.error(
    "⚠️ **คำเตือนหุ้นซิ่ง (Dime!):** ระบบใช้หลักคณิตศาสตร์คุมเงินทุนด้วยราคาปิดแท่งก่อนหน้า "
    "เพื่อป้องกันสัญญาณหลอก หน้างานจริงอาจเกิด Slippage (ราคาโดดข้ามเลน) ได้ง่าย "
    "แนะนำตั้งความเสี่ยงต่อไม้ต่ำๆ (0.5% - 1.0%) และหลีกเลี่ยงการถือข้ามคืน"
)

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital_thb = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต (บาท THB):", min_value=1000, value=100000, step=5000)
risk_per_trade = st.sidebar.slider("ความเสี่ยงที่ยอมรับได้ต่อไม้ (% ของพอร์ต):", min_value=0.25, max_value=3.0, value=1.0, step=0.25)

max_portfolio_heat = st.sidebar.slider(
    "เพดานความเสี่ยงรวมทั้งพอร์ตหากโดน SL พร้อมกัน (%):",
    min_value=1.0, max_value=10.0, value=5.0, step=0.5,
    help="หากเปิดหลายตัวพร้อมกัน ผลรวมความเสี่ยงห้ามเกินค่านี้เพื่อป้องกันพอร์ตพัง"
)

max_position_pct = st.sidebar.slider(
    "เพดานสัดส่วนเงินทุนสูงสุดต่อหุ้น 1 ตัว (% ของพอร์ต):",
    min_value=5, max_value=50, value=20, step=5,
    help="ระบบจะไม่แนะนำให้ลงเงินบาทเกินสัดส่วนนี้ในหุ้นตัวเดียว แม้ค่า SL จะแคบมากก็ตาม"
)

st.sidebar.divider()
st.sidebar.markdown("### 💵 อัตราแลกเปลี่ยน & ค่าฟีด (Dime! Config)")
fx_rate = st.sidebar.number_input("อัตราแลกเปลี่ยน USD/THB (รวม Spread หน้าแอป):", min_value=30.0, max_value=45.0, value=36.5, step=0.1)
dime_fee_pct = st.sidebar.slider("ค่าธรรมเนียมเทรดประมาณการ (+FX Spread เผื่อไว้ %):", min_value=0.0, max_value=1.0, value=0.15, step=0.05)

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดวิเคราะห์แผนเทรด:",
    [
        "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด",
        "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)"
    ]
)

st.sidebar.divider()
st.sidebar.caption("📌 เครื่องมือนี้ช่วยคำนวณคณิตศาสตร์ความเสี่ยงเท่านั้น ดุลยพินิจสุดท้ายเป็นของคุณ")


# ==========================================================================
# 📦 2. ANTI-CRASH, ANTI-REPAINTING & DIME! ENGINE
# ==========================================================================
@st.cache_data(ttl=15)
def fetch_timeframe_data(ticker, interval="1h", _state_key=0):
    """ ดึงข้อมูลตาม Timeframe พร้อมระบบ Rate Limiting และ Data Cleaning """
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
        if df.empty:
            return None
        return df
    except Exception:
        return None

def compute_indicators_and_signals(df):
    """ คำนวณระบบอินดิเคเตอร์โดยป้องกันจุดกลับตัวหลอก (No Repainting) """
    if df is None or len(df) < 25:
        return None

    df = df.copy()
    df['EMA_5'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()

    return df

def safe_signal_block_dime(df_proc, current_price):
    """ 
    คุม Logic สัญญาณเทรด 
    แก้ไขจุดบกพร่อง: ยึดระยะเป้าหมายจากราคาปิดและ ATR แท่งที่แล้ว เพื่อป้องกันช่องว่างราคาช่วงเปิดแท่งใหม่ 
    """
    if df_proc is None or len(df_proc) < 2:
        return None
        
    last_valid_row = df_proc.iloc[-2]  # แท่งที่ปิดสมบูรณ์แล้วล่าสุด

    if pd.isna(last_valid_row['EMA_5']) or pd.isna(last_valid_row['EMA_20']):
        return None
    if current_price is None or current_price <= 0 or np.isnan(current_price):
        return None

    atr = last_valid_row['ATR']
    if pd.isna(atr) or atr <= 0:
        atr = current_price * 0.02

    # คำนวณโครงสร้างสัญญาณจากแท่งที่แล้ว
    if last_valid_row['EMA_5'] > last_valid_row['EMA_20']:
        signal = "BUY / LONG"
        tp = current_price + (1.5 * atr)
        sl = current_price - (1.0 * atr)
    else:
        signal = "SELL / SHORT"
        tp = current_price - (1.5 * atr)
        sl = current_price + (1.0 * atr)

    risk_per_share = abs(current_price - sl)
    if risk_per_share < 0.001:
        return None

    return {
        "signal": signal,
        "tp": tp,
        "sl": sl,
        "atr": atr,
        "risk_per_share": risk_per_share,
        "current_price": current_price,
    }

def compute_position_size_dime(sig, account_capital_thb, risk_per_trade_pct, max_position_pct, fx_rate, dime_fee_pct):
    """ 
    ENGINE หลัก: คำนวณขนาดไม้สำหรับแอป Dime! 
    รองรับ Fractional Shares (เศษหุ้น) และแปลงเป็นเงินหน่วยบาท (THB) เผื่อค่าฟีดเรียบร้อย
    """
    try:
        # แปลงราคาหุ้นจาก USD เป็น THB หน้างาน
        current_price_thb = sig["current_price"] * fx_rate
        risk_per_share_thb = sig["risk_per_share"] * fx_rate
        
        # 1. คำนวณความเสี่ยงสูงสุดต่อไม้ที่ยอมรับได้ (หน่วย: บาท)
        max_loss_allowed_thb = account_capital_thb * (risk_per_trade_pct / 100)
        
        # ปรับลดเพดานความเสี่ยงเพื่อหักเผื่อค่าคอมมิชชั่น/ค่าฟีดของแอป
        effective_loss_allowed_thb = max_loss_allowed_thb * (1 - (dime_fee_pct / 100))
        
        # คำนวณจำนวนเศษหุ้นตามสิทธิ์ความเสี่ยง
        shares_by_risk = effective_loss_allowed_thb / risk_per_share_thb

        # 2. คำนวณตามเพดานสัดส่วนเงินทุนสูงสุดต่อหุ้น (Capital allocation)
        max_capital_allowed_thb = account_capital_thb * (max_position_pct / 100)
        shares_by_capital_cap = max_capital_allowed_thb / current_price_thb

        # เลือกจำนวนหุ้นที่ต่ำที่สุดเพื่อความปลอดภัยสูงสุด (Dime! รองรับเศษหุ้นปล่อยทศนิยมได้)
        final_shares = min(shares_by_risk, shares_by_capital_cap)
        final_shares = max(final_shares, 0.0)

        cost_thb = final_shares * current_price_thb
        cost_usd = cost_thb / fx_rate
        capped_by_position_limit = shares_by_capital_cap < shares_by_risk

        return {
            "shares": round(final_shares, 4),  # แสดงเศษหุ้น 4 ตำแหน่งสำหรับ Dime!
            "cost_thb": cost_thb,
            "cost_usd": cost_usd,
            "max_loss_allowed_thb": max_loss_allowed_thb,
            "actual_risk_thb": final_shares * risk_per_share_thb,
            "capped_by_position_limit": capped_by_position_limit,
        }
    except ZeroDivisionError:
        return {"shares": 0.0, "cost_thb": 0.0, "cost_usd": 0.0, "max_loss_allowed_thb": 0.0, "actual_risk_thb": 0.0, "capped_by_position_limit": False}

def compute_correlation_matrix(price_data: dict):
    closes = {}
    for t, df in price_data.items():
        if df is not None and len(df) > 5:
            closes[t] = df['Close'].pct_change().dropna()
    if len(closes) < 2:
        return None
    combined = pd.DataFrame(closes).dropna()
    if combined.empty or len(combined) < 5:
        return None
    return combined.corr()


# ==========================================================================
# 🎯 3. MODULE IMPLEMENTATIONS
# ==========================================================================

if menu == "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด":
    st.title("🎯 ระบบคำนวณเงินบาทหน้างานสำหรับการส่งคำสั่งซื้อบนแอป Dime!")
    st.markdown("ระบบสแกนสถิติเทคนิคัล พร้อมคำนวณ **จำนวนเงินบาท** ที่คุณต้องใส่ในช่องซื้อของ Dime! เพื่อคุมหน้าตัก")

    if st.button("🔄 [FORCE REFRESH] อัปเดตราคาสดทันที", type="primary"):
        st.session_state.refresh_key += 1
        st.rerun()

    watchlist_str = st.text_input("สัญลักษณ์หุ้นซิ่งที่ต้องการสแกนหน้างาน (คั่นด้วย ,):", "NVDA, PLTR, TSLA, AMD, MARA")
    tickers = [t.strip().upper() for t in watchlist_str.split(",") if t.strip()]
    tickers = list(dict.fromkeys(tickers))[:15]
    tf_choice = st.selectbox("เลือกความละเอียดของแท่งเทียน (Timeframe): *แนะนำ 1h สำหรับคัดหุ้นซิ่ง", ["1h", "15m", "1d"])

    max_loss_allowed_thb = account_capital_thb * (risk_per_trade / 100)
    max_capital_allowed_thb = account_capital_thb * (max_position_pct / 100)
    st.warning(
        f"🛡️ **ขีดจำกัดหน้างาน:** ขาดทุนสูงสุดต่อไม้ต้องไม่เกิน **{max_loss_allowed_thb:,.2f} บาท** "
        f"และจำกัดเงินลงทุนสูงสุดต่อตัวไม่เกิน **{max_capital_allowed_thb:,.2f} บาท** ({max_position_pct}% ของพอร์ต) "
        f"— ระบบจะเกลี่ยหน้าตักอัตโนมัติ"
    )

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
                sig = safe_signal_block_dime(df_proc, current_price)

                if sig is not None:
                    pos = compute_position_size_dime(sig, account_capital_thb, risk_per_trade, max_position_pct, fx_rate, dime_fee_pct)
                    total_committed_risk_thb += pos["actual_risk_thb"]

                    signal_icon = "🟩" if sig["signal"] == "BUY / LONG" else "🟥"
                    cap_note = " ⚠️ (ชนเพดานสัดส่วนเงินพอร์ต)" if pos["capped_by_position_limit"] else ""

                    scanned_data.append({
                        "หุ้นซิ่ง": t,
                        "ราคาสด (USD)": f"${sig['current_price']:.2f}",
                        "สัญญาณ (สถิติ)": f"{signal_icon} {sig['signal']}",
                        "เป้ากำไร TP (USD)": f"${sig['tp']:.2f}",
                        "จุดคัท SL (USD)": f"${sig['sl']:.2f}",
                        "จำนวนเศษหุ้น (Shares)": f"{pos['shares']:.4f}",
                        "ระบุเงินบาทที่ซื้อใน Dime!": f"{pos['cost_thb']:,.2f} THB{cap_note}",
                        "คิดเป็นเงินดอลลาร์": f"${pos['cost_usd']:.2f}"
                    })
                else:
                    scanned_data.append({
                        "หุ้นซิ่ง": t, "ราคาสด (USD)": "-", "สัญญาณ (สถิติ)": "⚪ ข้อมูลแกว่งตัวแคบ/ไม่ปลอดภัย",
                        "เป้ากำไร TP (USD)": "-", "จุดคัท SL (USD)": "-", "จำนวนเศษหุ้น (Shares)": "-", "ระบุเงินบาทที่ซื้อใน Dime!": "-", "คิดเป็นเงินดอลลาร์": "-"
                    })
            else:
                scanned_data.append({
                    "หุ้นซิ่ง": t, "ราคาสด (USD)": "-", "สัญญาณ (สถิติ)": "⚪ ดึงข้อมูลไม่สำเร็จ",
                    "เป้ากำไร TP (USD)": "-", "จุดคัท SL (USD)": "-", "จำนวนเศษหุ้น (Shares)": "-", "ระบุเงินบาทที่ซื้อใน Dime!": "-", "คิดเป็นเงินดอลลาร์": "-"
                })
            p_bar.progress((idx + 1) / len(tickers))

    if scanned_data:
        st.dataframe(pd.DataFrame(scanned_data), use_container_width=True, hide_index=True)

        # Portfolio Heat Check หน่วยบาท
        st.divider()
        st.subheader("🔥 ตรวจสอบความเสี่ยงรวมทั้งพอร์ตหน่วยบาท (Portfolio Heat Check)")
        heat_pct = (total_committed_risk_thb / account_capital_thb * 100) if account_capital_thb > 0 else 0
        heat_limit_thb = account_capital_thb * (max_portfolio_heat / 100)

        hc1, hc2, hc3 = st.columns(3)
        hc1.metric("ความเสี่ยงรวมหากโดน SL ทุกไม้พร้อมกัน", f"{total_committed_risk_thb:,.2f} บาท")
        hc2.metric("คิดเป็น % ของพอร์ตจริง", f"{heat_pct:.2f}%")
        hc3.metric("เพดานรวมที่กำหนดไว้ในระบบ", f"{max_portfolio_heat:.1f}% ({heat_limit_thb:,.2f} บาท)")

        if heat_pct > max_portfolio_heat:
            st.error(
                f"🚨 **ความเสี่ยงล้นระบบ!** หากเปิดซื้อทุกไม้พร้อมกันแล้วโดนคัททั้งหมด พอร์ตจะเสียหาย {heat_pct:.2f}% "
                f"ซึ่งเกินเพดานความปลอดภัยที่ตั้งไว้ {max_portfolio_heat:.1f}% แนะนำให้คัดเลือกเข้าทีละตัว"
            )
        else:
            st.success(f"✅ ความเสี่ยงรวมอยู่ในเกณฑ์ปลอดภัยสูงสุดสำหรับพอร์ตของคุณ ({heat_pct:.2f}% / {max_portfolio_heat:.1f}%)")

        # Correlation Check
        corr_matrix = compute_correlation_matrix(raw_price_data)
        if corr_matrix is not None and len(corr_matrix) >= 2:
            st.subheader("🔗 ตรวจสอบสหสัมพันธ์ (Correlation ดักหุ้นซิ่งวิ่งตามกัน)")
            st.caption("เลี่ยงการเปิดหุ้นสองตัวที่ Correlation เกิน 0.7 พร้อมกัน เพราะนั่นไม่ใช่การกระจายความเสี่ยง แต่คือการเบิ้ลความเสี่ยงคูณสอง")

            high_corr_pairs = []
            cols = corr_matrix.columns
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    val = corr_matrix.iloc[i, j]
                    if pd.notna(val) and abs(val) >= 0.7:
                        high_corr_pairs.append((cols[i], cols[j], val))

            if high_corr_pairs:
                for a, b, v in sorted(high_corr_pairs, key=lambda x: -abs(x[2])):
                    direction = "วิ่งตามกัน" if v > 0 else "วิ่งสวนทางกัน"
                    st.warning(f"⚠️ **{a} ↔ {b}**: correlation = {v:.2f} ({direction})")
            else:
                st.info("👍 เยี่ยมมาก หุ้นในลิสต์ไม่มีความสัมพันธ์ซ้ำซ้อนกันอย่างมีนัยสำคัญ")

            with st.expander("ดูตาราง Matrix แบบเต็ม"):
                st.dataframe(corr_matrix.round(2), use_container_width=True)

elif menu == "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)":
    st.title("📐 วางแผนเทรดรายตัว และระบบแก้ปัญหาราคาดีเลย์ (Dime! Real-time Override)")
    st.caption("ถ้าราคาเทคนิคัลจาก API ดีเลย์ ให้เอาราคาที่เห็นสดๆ บนหน้าจอแอป Dime! มากรอกช่องด้านล่างเพื่อคำนวณทับได้ทันที")

    c_t1, c_t2, c_t3 = st.columns(3)
    t_stock = c_t1.text_input("ป้อนตัวย่อหุ้นที่ต้องการเจาะลึก:", "NVDA").upper().strip()
    t_frame = c_t2.selectbox("เลือกกรอบเวลาวิเคราะห์กราฟ (Timeframe):", ["15m", "1h", "1d"])
    
    # ทางแก้ปัญหา yfinance ดีเลย์ 15 นาทีสัญชาติอเมริกัน: กรอกราคาสดหน้างานจากแอปส่งทับเข้าไปเลย
    use_override = c_t3.checkbox("🚨 ใช้ราคา Real-time หน้าแอป Dime! แทน")

    if not t_stock:
        st.info("กรุณาป้อนสัญลักษณ์หุ้นสากล")
    else:
        raw_df = fetch_timeframe_data(t_stock, interval=t_frame, _state_key=st.session_state.refresh_key)
        df_proc = compute_indicators_and_signals(raw_df)

        if df_proc is not None:
            # ตรวจสอบการเลือกใช้ราคาทับซ้อน
            if use_override:
                current_price = c_t3.number_input("พิมพ์ราคาสดที่เห็นในแอป Dime! ตอนนี้ ($):", min_value=0.01, value=float(df_proc['Close'].iloc[-1]), step=0.01)
            else:
                current_price = df_proc['Close'].iloc[-1]

            sig = safe_signal_block_dime(df_proc, current_price)

            if sig is None:
                st.error("ความผันผวนผิดปกติหรือข้อมูลไม่เพียงพอในการคำนวณระยะ SL กรุณาเปลี่ยนหุ้น")
            else:
                pos = compute_position_size_dime(sig, account_capital_thb, risk_per_trade, max_position_pct, fx_rate, dime_fee_pct)
                signal_icon = "🟩" if sig["signal"] == "BUY / LONG" else "🟥"

                cx1, cx2, cx3, cx4 = st.columns(4)
                cx1.metric("ราคาตั้งต้นคำนวณ (USD)", f"${sig['current_price']:.2f}")
                cx2.markdown(f"🤖 **สัญญาณระบบคณิตศาสตร์:** \n## {signal_icon} {sig['signal']}")
                cx3.metric("🎯 เป้ากำไรขายทำรอบ TP (USD)", f"${sig['tp']:.2f}")
                cx4.metric("🛑 จุดตัดขาดทุนหนีตาย SL (USD)", f"${sig['sl']:.2f}")

                cap_note = f" *(จำนวนเงินนี้ถูกสกัดด้วยกฎคุมสัดส่วน {max_position_pct}% ของพอร์ต)*" if pos["capped_by_position_limit"] else ""
                
                # กรอบสรุปแผนการยิงคำสั่งในแอป
                st.success(
                    f"📥 **คำแนะนำการระบุออเดอร์ในแอป Dime!**\n\n"
                    f"👉 วิธีการซื้อ: เลือกซื้อแบบ **'ระบุจำนวนเงิน'** -> แล้วพิมพ์ตัวเลข **{pos['cost_thb']:,.2f} บาท** ลงไปในแอป\n"
                    f"📊 คุณจะได้เศษหุ้นประมาณ **{pos['shares']:.4f} หุ้น** | มูลค่าสัญญาตัวเงิน **${pos['cost_usd']:.2f}**\n"
                    f"💀 หากราคาวิ่งผิดทางไปโดนจุด SL คุณจะขาดทุนจำกัดอยู่ที่ประมาณ **{pos['actual_risk_thb']:,.2f} บาท** เท่านั้น {cap_note}"
                )

                if df_proc['RSI'].iloc[-2] > 70:
                    st.warning("📌 RSI แท่งเทียนก่อนหน้าอยู่ในโซน Overbought (>70) — สำหรับหุ้นซิ่ง ระวังแรงเทขายล้างกระดานเฉียบพลัน")
                elif df_proc['RSI'].iloc[-2] < 30:
                    st.warning("📌 RSI แท่งเทียนก่อนหน้าอยู่ในโซน Oversold (<30) — หุ้นซิ่งขาลงลึก อาจมีการเด้ง Technical Rebound สั้นๆ")

                # วาดกราฟ Dark Mode
                plot_df = df_proc.tail(40)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name='แท่งราคา'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_5'], line=dict(color='#2eb85c', width=1.5), name='EMA 5'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#ffc107', width=1.5), name='EMA 20'))

                fig.add_hline(y=sig['tp'], line_dash="dash", line_color="green", annotation_text="Target Price")
                fig.add_hline(y=sig['sl'], line_dash="dash", line_color="red", annotation_text="Stop Loss")

                fig.update_layout(template="plotly_dark", title=f"แผนภูมิวิเคราะห์สถิติปัจจัยเสี่ยง ({t_frame}) ของหุ้น {t_stock}", height=380, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("ไม่สามารถเชื่อมต่อข้อมูลโครงข่ายหลักทรัพย์นี้ได้ กรุณาตรวจสอบตัวย่อภาษาอังกฤษอีกครั้ง")
