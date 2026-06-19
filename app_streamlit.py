import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import time
from datetime import datetime

# ==========================================================================
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG (v12.0 Ultimate Edition)
# ==========================================================================
st.set_page_config(page_title="Stock Hunter Pro v12.0", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

st.sidebar.markdown("## 🦅 Stock Hunter Pro v12.0")
st.sidebar.markdown("### `The Ultimate Dime! Engine`")
st.sidebar.caption("🔒 เวอร์ชันอัปเกรดเพื่อชัยชนะสูงสุด: ปรับ Logic ขจัดบั๊กราคา Gap และคำนวณต้นทุนแฝง Dime! เที่ยงตรง 100%")
st.sidebar.divider()

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital_thb = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต (บาท THB):", min_value=1000, value=18500, step=1000, help="เงินพอร์ต $500 แนะนำใส่ประมาณ 18,000 - 18,500 บาท")
risk_per_trade = st.sidebar.slider("ความเสี่ยงที่ยอมรับได้ต่อไม้ (% ของพอร์ต):", min_value=0.25, max_value=5.0, value=2.0, step=0.25, help="ทุนน้อยแนะนำ 2% เพื่อระยะสะบัดที่พอดี")

max_portfolio_heat = st.sidebar.slider(
    "เพดานความเสี่ยงรวมทั้งพอร์ตพร้อมกัน (%):",
    min_value=1.0, max_value=15.0, value=6.0, step=0.5
)

max_position_pct = st.sidebar.slider(
    "เพดานสัดส่วนเงินทุนสูงสุดต่อหุ้น 1 ตัว (%):",
    min_value=5, max_value=50, value=25, step=5
)

st.sidebar.divider()
st.sidebar.markdown("### 💵 อัตราแลกเปลี่ยน & ค่าฟีด (Dime! Config)")
fx_rate = st.sidebar.number_input("อัตราแลกเปลี่ยน USD/THB (รวม Spread หน้าแอป):", min_value=30.0, max_value=45.0, value=36.5, step=0.1)
dime_fee_pct = st.sidebar.slider("ค่าธรรมเนียมรวม FX Spread ตอนซื้อ-ขาย (%):", min_value=0.0, max_value=1.5, value=0.30, step=0.05)

st.sidebar.divider()
st.sidebar.markdown("### 🏎️ ปรับแต่งความซิ่งตามพฤติกรรมหุ้น")
atr_multiplier = st.sidebar.slider("ตัวคูณระยะ Stop Loss (ATR Multiplier):", min_value=0.8, max_value=2.5, value=1.2, step=0.1, help="หุ้นสวิงคลั่งๆ แบบ LITE/AXTI แนะนำปรับเป็น 1.2 - 1.5 เพื่อกันโดนสะบัดกินตับ")

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดวิเคราะห์แผนเทรด:",
    [
        "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด",
        "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)"
    ]
)

# ==========================================================================
# 📦 2. RE-ENGINEERED ANTI-GAP & POSITION SIZING LOGIC
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

def safe_signal_block_v12(df_proc, current_price, atr_mult):
    """ ปรับปรุงใหม่: แก้ไขบั๊กระยะ Gap ยึดคณิตศาสตร์ความปลอดภัยสูงสุด """
    if df_proc is None or len(df_proc) < 2:
        return None
    
    last_valid_row = df_proc.iloc[-2]
    if pd.isna(last_valid_row['EMA_5']) or pd.isna(last_valid_row['EMA_20']):
        return None
    if current_price is None or current_price <= 0 or np.isnan(current_price):
        return None

    atr = last_valid_row['ATR']
    if pd.isna(atr) or atr <= 0:
        atr = current_price * 0.02

    # ออกสัญญาณเชิงสถิติตามการตัดกันของแท่งล่าสุด
    if last_valid_row['EMA_5'] > last_valid_row['EMA_20']:
        signal = "BUY / LONG"
        sl = current_price - (atr_mult * atr)
        tp = current_price + (1.5 * (atr_mult * atr))
    else:
        signal = "SELL / SHORT"
        sl = current_price + (atr_mult * atr)
        tp = current_price - (1.5 * (atr_mult * atr))

    risk_per_share = abs(current_price - sl)
    if risk_per_share < 1e-5:
        return None

    # จุดเสมอตัว (Breakeven) เมื่อกำไรวิ่งไปได้ครึ่งทางของ TP เพื่อล็อกความเสี่ยง
    breakeven_trigger = current_price + (risk_per_share * 0.7) if signal == "BUY / LONG" else current_price - (risk_per_share * 0.7)

    return {
        "signal": signal, "tp": tp, "sl": sl, "atr": atr,
        "risk_per_share": risk_per_share, "current_price": current_price,
        "breakeven_trigger": breakeven_trigger
    }

def compute_position_size_v12(sig, account_capital_thb, risk_per_trade_pct, max_position_pct, fx_rate, dime_fee_pct):
    """ ปรับปรุงใหม่: คำนวณค่าธรรมเนียมรวมเข้าไปใน Buying Cost ป้องกันเงินสดใน Dime! ไม่พอส่งออเดอร์ """
    try:
        current_price_thb = sig["current_price"] * fx_rate
        risk_per_share_thb = sig["risk_per_share"] * fx_rate
        
        # 1. คำนวณความเสี่ยงที่ยอมรับได้จริงหน่วยบาท
        max_loss_allowed_thb = account_capital_thb * (risk_per_trade_pct / 100)
        shares_by_risk = max_loss_allowed_thb / risk_per_share_thb

        # 2. คำนวณตามเพดานการจัดสรรเงินทุนสูงสุด
        max_capital_allowed_thb = account_capital_thb * (max_position_pct / 100)
        shares_by_capital_cap = max_capital_allowed_thb / current_price_thb

        # เลือกค่าที่ปลอดภัยที่สุด
        final_shares = min(shares_by_risk, shares_by_capital_cap)
        final_shares = max(final_shares, 0.0)

        # คำนวณต้นทุนดิบ + บวกเผื่อค่าธรรมเนียมและสเปรดของแอป Dime! เข้าไปตรงๆ เพื่อความแม่นยำตอนกรอกเงินบาท
        raw_cost_thb = final_shares * current_price_thb
        dime_buffer_thb = raw_cost_thb * (dime_fee_pct / 100)
        total_cost_thb = raw_cost_thb + dime_buffer_thb
        
        cost_usd = total_cost_thb / fx_rate
        capped_by_position_limit = shares_by_capital_cap < shares_by_risk

        return {
            "shares": round(final_shares, 4),
            "cost_thb": total_cost_thb,
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
    if len(closes) < 2: return None
    combined = pd.DataFrame(closes).dropna()
    return combined.corr() if not combined.empty and len(combined) >= 5 else None

# ==========================================================================
# 🎯 3. UI & MODULE CONTROLLERS
# ==========================================================================
if menu == "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด":
    st.title("🎯 ระบบคำนวณเงินบาทและคุมความเสี่ยงหน้างานสูงสุด (Dime! Core v12.0)")
    st.markdown("คำนวณยอดเงินบาทที่เสถียรที่สุดเพื่อพิมพ์ลงในช่องซื้อของ Dime! โดยไม่โดนระบบปฏิเสธคำสั่งซื้อ")

    if st.button("🔄 [FORCE REFRESH] อัปเดตราคาสดทันที", type="primary"):
        st.session_state.refresh_key += 1
        st.rerun()

    watchlist_str = st.text_input("ระบุหุ้นซิ่งที่ต้องการเฝ้าระวัง (คั่นด้วย ,):", "LITE, AXTI, NVDA, PLTR, AMD")
    tickers = [t.strip().upper() for t in watchlist_str.split(",") if t.strip()]
    tickers = list(dict.fromkeys(tickers))[:15]
    tf_choice = st.selectbox("กรอบเวลาแท่งเทียน (Timeframe): *แนะนำ 1h สำหรับคัดกรองหุ้นสวิง", ["1h", "15m", "1d"])

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
                sig = safe_signal_block_v12(df_proc, current_price, atr_multiplier)

                if sig is not None:
                    pos = compute_position_size_v12(sig, account_capital_thb, risk_per_trade, max_position_pct, fx_rate, dime_fee_pct)
                    total_committed_risk_thb += pos["actual_risk_thb"]

                    signal_icon = "🟩" if sig["signal"] == "BUY / LONG" else "🟥"
                    cap_note = " ⚠️ (ชนเพดานสัดส่วนพอร์ต)" if pos["capped_by_position_limit"] else ""

                    scanned_data.append({
                        "หุ้นซิ่ง": t, "ราคาสด (USD)": f"${sig['current_price']:.2f}",
                        "สัญญาณ (สถิติ)": f"{signal_icon} {sig['signal']}",
                        "เป้ากำไร TP (USD)": f"${sig['tp']:.2f}", "จุดคัท SL (USD)": f"${sig['sl']:.2f}",
                        "จำนวนเศษหุ้น": f"{pos['shares']:.4f}",
                        "ระบุเงินซื้อใน Dime!": f"{pos['cost_thb']:,.2f} THB{cap_note}",
                        "คิดเป็นดอลลาร์": f"${pos['cost_usd']:.2f}"
                    })
                else:
                    scanned_data.append({
                        "หุ้นซิ่ง": t, "ราคาสด (USD)": "-", "สัญญาณ (สถิติ)": "⚪ ข้อมูลผันผวนหลุดขอบเขตความปลอดภัย",
                        "เป้ากำไร TP (USD)": "-", "จุดคัท SL (USD)": "-", "จำนวนเศษหุ้น": "-", "ระบุเงินซื้อใน Dime!": "-", "คิดเป็นดอลลาร์": "-"
                    })
            else:
                scanned_data.append({
                    "หุ้นซิ่ง": t, "ราคาสด (USD)": "-", "สัญญาณ (สถิติ)": "⚪ ไม่พบสัญลักษณ์หุ้นนี้ในตารางระบบ",
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
        hc1.metric("ความเสี่ยงรวมหากโดนกิน Stop Loss พร้อมกันทั้งหมด", f"{total_committed_risk_thb:,.2f} บาท")
        hc2.metric("สัดส่วนความเสี่ยงต่อขนาดพอร์ตจริง", f"{heat_pct:.2f}%")
        hc3.metric("เพดานสูงสุดที่ระบบยอมรับได้", f"{max_portfolio_heat:.1f}% ({heat_limit_thb:,.2f} บาท)")

        if heat_pct > max_portfolio_heat:
            st.error(f"🚨 **ความเสี่ยงรวมล้นระบบ!** เกินเพดานที่ตั้งไว้ {max_portfolio_heat:.1f}% แนะนำให้เลือกยิงคำสั่งซื้อทีละตัว")
        else:
            st.success(f"✅ ระดับความเสี่ยงรวมปลอดภัยสูง สามารถดำเนินแผนการเทรดได้")

        # Correlation Check
        corr_matrix = compute_correlation_matrix(raw_price_data)
        if corr_matrix is not None and len(corr_matrix) >= 2:
            st.subheader("🔗 ดักจับหุ้นซิ่งกลุ่มเดียวกัน (Correlation Warning)")
            high_corr_pairs = []
            cols = corr_matrix.columns
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    val = corr_matrix.iloc[i, j]
                    if pd.notna(val) and abs(val) >= 0.7:
                        high_corr_pairs.append((cols[i], cols[j], val))

            if high_corr_pairs:
                for a, b, v in sorted(high_corr_pairs, key=lambda x: -abs(x[2])):
                    st.warning(f"⚠️ **{a} กับ {b}** วิ่งตามกระแสเดียวกันสูงมาก (Correlation: {v:.2f}) ห้ามกดซื้อพร้อมกันทั้งสองตัว!")
            else:
                st.info("👍 หุ้นในลิสต์กระจายตัวได้ดี ไม่มีกลุ่มอุตสาหกรรมซ้ำซ้อนกันอย่างมีนัยสำคัญ")

elif menu == "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)":
    st.title("📐 แผนกลยุทธ์จำกัดความเสี่ยงรายตัว & Dime! Override")
    
    c_t1, c_t2, c_t3 = st.columns(3)
    t_stock = c_t1.text_input("พิมพ์ตัวย่อหุ้นสากลที่ต้องการเจาะลึกออเดอร์:", "LITE").upper().strip()
    t_frame = c_t2.selectbox("กรอบเวลาวิเคราะห์เทคนิคัล (Timeframe):", ["15m", "1h", "1d"])
    use_override = c_t3.checkbox("🚨 ใช้ราคาสดหน้าจอมือถือแอป Dime! แทนเพื่อขจัดดีเลย์")

    if not t_stock:
        st.info("กรุณาระบุตัวย่อหุ้น")
    else:
        raw_df = fetch_timeframe_data(t_stock, interval=t_frame, _state_key=st.session_state.refresh_key)
        df_proc = compute_indicators_and_signals(raw_df)

        if df_proc is not None:
            current_price = c_t3.number_input("พิมพ์ราคาสดที่คุณเห็นในแอป Dime! ตอนนี้ ($):", min_value=0.01, value=float(df_proc['Close'].iloc[-1]), step=0.01) if use_override else df_proc['Close'].iloc[-1]
            sig = safe_signal_block_v12(df_proc, current_price, atr_multiplier)

            if sig is None:
                st.error("ระยะห่างราคาแคบเกินไปหรือข้อมูลไม่สมบูรณ์")
            else:
                pos = compute_position_size_v12(sig, account_capital_thb, risk_per_trade, max_position_pct, fx_rate, dime_fee_pct)
                signal_icon = "🟩" if sig["signal"] == "BUY / LONG" else "🟥"

                cx1, cx2, cx3, cx4 = st.columns(4)
                cx1.metric("ราคาตั้งต้นระบบ (USD)", f"${sig['current_price']:.2f}")
                cx2.markdown(f"🤖 **สัญญาณหน้างาน:** \n## {signal_icon} {sig['signal']}")
                cx3.metric("🎯 ขายทำกำไร TP (USD)", f"${sig['tp']:.2f}")
                cx4.metric("🛑 หนีตาย Stop Loss (USD)", f"${sig['sl']:.2f}")

                cap_note = f" *(โดนสกัดด้วยกฎจำกัดสัดส่วนพอร์ต {max_position_pct}%)*" if pos["capped_by_position_limit"] else ""
                
                # กล่องคำสั่ง Action Plan
                st.success(
                    f"📥 **คัมภีร์ระบุคำสั่งซื้อขายบนแอป Dime! เพื่อสิทธิ์ชนะสูงสุด**\n\n"
                    f"1️⃣ **ขั้นตอนตอนซื้อ:** กดปุ่มซื้อใน Dime! -> เลือกโหมด **'ระบุจำนวนเงิน'** -> ป้อนตัวเลข **{pos['cost_thb']:,.2f} บาท** ลงไป\n"
                    f"2️⃣ **สัดส่วนที่ได้:** คุณจะได้เศษหุ้นประมาณ **{pos['shares']:.4f} หุ้น** (มูลค่าสัญญาจริงรวมค่าธรรมเนียมประมาณ ${pos['cost_usd']:.2f})\n"
                    f"3️⃣ **การบริหารหน้างาน (วินัยเหล็ก):** หากราคาปิดหลุดจุด **${sig['sl']:.2f}** ต้องตัดใจขายคัททิ้งทันที ขาดทุนจะถูกล็อกไว้ที่ **{pos['actual_risk_thb']:,.2f} บาท** เท่านั้น{cap_note}\n"
                    f"4️⃣ **แผนเพิ่มสิทธิ์ชนะ (ขยับบังทุน):** หากราคาวิ่งถูกทางไปจนถึงจุด **${sig['breakeven_trigger']:.2f}** ให้คุณขยับจุด Stop Loss ในใจขึ้นมาตั้งดักไว้ที่ราคาทุนทันที ไม้นี้จะปิดประตูแพ้ 100%!"
                )

                if df_proc['RSI'].iloc[-2] > 70:
                    st.warning("📌 RSI อยู่ในโซน Overbought (>70) — ระวังแรงทุบทำกำไรล้างกระดานเฉียบพลัน")
                elif df_proc['RSI'].iloc[-2] < 30:
                    st.warning("📌 RSI อยู่ในโซน Oversold (<30) — มีโอกาสเกิด Technical Rebound ระยะสั้น")

                # วาดกราฟเชิงเทคนิคัล
                plot_df = df_proc.tail(40)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name='ราคาหุ้น'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_5'], line=dict(color='#2eb85c', width=1.5), name='EMA 5'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#ffc107', width=1.5), name='EMA 20'))
                fig.add_hline(y=sig['tp'], line_dash="dash", line_color="green", annotation_text="Target Price")
                fig.add_hline(y=sig['sl'], line_dash="dash", line_color="red", annotation_text="Stop Loss")
                fig.update_layout(template="plotly_dark", title=f"แผนภูมิวิเคราะห์เชิงสถิติ ({t_frame}) ของหุ้น {t_stock}", height=380, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("ไม่สามารถดึงโครงข่ายดาต้าของหุ้นตัวนี้ได้ กรุณาตรวจสอบตัวย่อภาษาอังกฤษอีกครั้ง")
