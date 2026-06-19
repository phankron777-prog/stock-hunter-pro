import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import time
from datetime import datetime

# ==========================================================================
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG (v13.0 Ultimate Winning Edition)
# ==========================================================================
st.set_page_config(page_title="Stock Hunter Pro v13.0", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

st.sidebar.markdown("## 🦅 Stock Hunter Pro v13.0")
st.sidebar.markdown("### `The Ultimate Winning Engine`")
st.sidebar.caption("🔒 เวอร์ชันสมบูรณ์แบบ: ขจัดสัญญาณหลอกด้วย Trend Filter + ปัดเศษเงิน Dime! ยิงคำสั่งติด 100%")
st.sidebar.divider()

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital_thb = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต (บาท THB):", min_value=1000, value=18500, step=1000)
risk_per_trade = st.sidebar.slider("ความเสี่ยงที่ยอมรับได้ต่อไม้ (% ของพอร์ต):", min_value=0.25, max_value=5.0, value=2.0, step=0.25)

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
atr_multiplier = st.sidebar.slider("ตัวคูณระยะ Stop Loss (ATR Multiplier):", min_value=0.8, max_value=2.5, value=1.2, step=0.1)

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดวิเคราะห์แผนเทรด:",
    [
        "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด",
        "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)"
    ]
)

# ==========================================================================
# 📦 2. RE-ENGINEERED WINNING FILTER & MATHEMATICAL ENGINE
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
    if df is None or len(df) < 50: # เพิ่มข้อมูลขั้นต่ำเพื่อคำนวณ EMA เทรนด์ใหญ่
        return None
    df = df.copy()
    df['EMA_5'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean() # เส้นแบ่งเทรนด์หลักขาขึ้น-ลง
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    return df

def safe_signal_block_v13(df_proc, current_price, atr_mult):
    """ v13.0 Ultimate: ระบบคัดกรองเทรนด์ใหญ่และแรงเหวี่ยง RSI ป้องกันการสวนเทรนด์พัง """
    if df_proc is None or len(df_proc) < 2:
        return None
    
    last_valid_row = df_proc.iloc[-2]
    if pd.isna(last_valid_row['EMA_5']) or pd.isna(last_valid_row['EMA_20']) or pd.isna(last_valid_row['EMA_50']):
        return None
    if current_price is None or current_price <= 0 or np.isnan(current_price):
        return None

    atr = last_valid_row['ATR']
    if pd.isna(atr) or atr <= 0:
        atr = current_price * 0.02

    # โครงสร้างสัญญาณพื้นฐานจากเส้นตัด
    base_buy = last_valid_row['EMA_5'] > last_valid_row['EMA_20']
    
    # [🏆 ฟีเจอร์เด็ด v13] Trend Filter: หุ้นต้องอยู่เหนือเส้นเทรนด์ใหญ่ 50 วัน ถึงจะยอมรับสัญญาณ BUY
    trend_aligned = last_valid_row['Close'] > last_valid_row['EMA_50']
    
    # [🏆 ฟีเจอร์เด็ด v13] RSI Overbought Block: ป้องกันการไล่ราคาที่จุดสูงสุด
    rsi_overbought = last_valid_row['RSI'] > 75

    if base_buy:
        if not trend_aligned:
            signal = "⚠️ WAIT (ใต้เทรนด์ใหญ่เสี่ยงหลอก)"
        elif rsi_overbought:
            signal = "⚠️ WAIT (RSI ตึงเกินไป)"
        else:
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

    breakeven_trigger = current_price + (risk_per_share * 0.7) if "BUY" in signal else current_price - (risk_per_share * 0.7)

    return {
        "signal": signal, "tp": tp, "sl": sl, "atr": atr,
        "risk_per_share": risk_per_share, "current_price": current_price,
        "breakeven_trigger": breakeven_trigger
    }

def compute_position_size_v13(sig, account_capital_thb, risk_per_trade_pct, max_position_pct, fx_rate, dime_fee_pct):
    """ v13.0 Ultimate: คำนวณเงินบาทแบบปัดเศษเต็มจำนวนเพื่อป้องกัน Dime! ปฏิเสธคำสั่งซื้อ """
    try:
        current_price_thb = sig["current_price"] * fx_rate
        risk_per_share_thb = sig["risk_per_share"] * fx_rate
        
        # 1. ขนาดตามความเสี่ยงยอมรับได้
        max_loss_allowed_thb = account_capital_thb * (risk_per_trade_pct / 100)
        shares_by_risk = max_loss_allowed_thb / risk_per_share_thb

        # 2. ขนาดตามเพดานสัดส่วนพอร์ต
        max_capital_allowed_thb = account_capital_thb * (max_position_pct / 100)
        shares_by_capital_cap = max_capital_allowed_thb / current_price_thb

        final_shares = min(shares_by_risk, shares_by_capital_cap)
        final_shares = max(final_shares, 0.0)

        raw_cost_thb = final_shares * current_price_thb
        dime_buffer_thb = raw_cost_thb * (dime_fee_pct / 100)
        
        # [🏆 ฟีเจอร์เด็ด v13] ปัดเศษลงเป็นจำนวนเต็ม (Floor) ป้องกันปัญหาเศษทศนิยมล้นบัฟเฟอร์ในแอป
        total_cost_thb = np.floor(raw_cost_thb + dime_buffer_thb)
        
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
    st.title("🎯 ระบบคำนวณเงินบาทและกรองเทรนด์เอาชนะตลาด (Dime! Core v13.0)")
    st.markdown("ระบบจะกรองหุ้นซิ่งที่เข้าเกณฑ์ **ปลอดภัยสูงสุด** มาให้คุณเพื่อปิดประตูแพ้")

    if st.button("🔄 [FORCE REFRESH] อัปเดตราคาสดทันที", type="primary"):
        st.session_state.refresh_key += 1
        st.rerun()

    watchlist_str = st.text_input("ระบุหุ้นซิ่งที่ต้องการเฝ้าระวัง (คั่นด้วย ,):", "LITE, AXTI, NVDA, PLTR, AMD, TSLA")
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
                sig = safe_signal_block_v13(df_proc, current_price, atr_multiplier)

                if sig is not None:
                    pos = compute_position_size_v13(sig, account_capital_thb, risk_per_trade, max_position_pct, fx_rate, dime_fee_pct)
                    
                    if "⚠️" not in sig["signal"]:
                        total_committed_risk_thb += pos["actual_risk_thb"]

                    if "BUY" in sig["signal"] and "⚠️" not in sig["signal"]:
                        signal_icon = "🟩"
                    elif "⚠️" in sig["signal"]:
                        signal_icon = "🟨"
                    else:
                        signal_icon = "🟥"
                        
                    cap_note = " ⚠️" if pos["capped_by_position_limit"] else ""

                    scanned_data.append({
                        "หุ้นซิ่ง": t, "ราคาสด (USD)": f"${sig['current_price']:.2f}",
                        "สัญญาณวินัยเหล็ก": f"{signal_icon} {sig['signal']}",
                        "เป้ากำไร TP (USD)": f"${sig['tp']:.2f}" if "⚠️" not in sig["signal"] else "-", 
                        "จุดคัท SL (USD)": f"${sig['sl']:.2f}" if "⚠️" not in sig["signal"] else "-",
                        "จำนวนเศษหุ้น": f"{pos['shares']:.4f}" if "⚠️" not in sig["signal"] else "-",
                        "ระบุเงินซื้อใน Dime!": f"{pos['cost_thb']:,.0f} THB{cap_note}" if "⚠️" not in sig["signal"] else "ข้ามไปก่อน",
                        "คิดเป็นดอลลาร์": f"${pos['cost_usd']:.2f}" if "⚠️" not in sig["signal"] else "-"
                    })
                else:
                    scanned_data.append({
                        "หุ้นซิ่ง": t, "ราคาสด (USD)": "-", "สัญญาณวินัยเหล็ก": "⚪ ข้อมูลผันผวนเกินขอบเขต",
                        "เป้ากำไร TP (USD)": "-", "จุดคัท SL (USD)": "-", "จำนวนเศษหุ้น": "-", "ระบุเงินซื้อใน Dime!": "-", "คิดเป็นดอลลาร์": "-"
                    })
            else:
                scanned_data.append({
                    "หุ้นซิ่ง": t, "ราคาสด (USD)": "-", "สัญญาณวินัยเหล็ก": "⚪ ไม่พบดาต้าเทคนิคัล",
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
        hc1.metric("ความเสี่ยงรวมหากโดนกิน Stop Loss ตัวที่เปิดสัญญาณพร้อมกัน", f"{total_committed_risk_thb:,.2f} บาท")
        hc2.metric("สัดส่วนความเสี่ยงต่อพอร์ต", f"{heat_pct:.2f}%")
        hc3.metric("เพดานสูงสุดที่ระบบยอมรับได้", f"{max_portfolio_heat:.1f}% ({heat_limit_thb:,.2f} บาท)")

        if heat_pct > max_portfolio_heat:
            st.error(f"🚨 **ความเสี่ยงรวมล้นระบบ!** เกินเพดานที่ตั้งไว้ แนะนำเลือกซื้อเฉพาะตัวที่มีฐานเทรนด์แข็งแกร่งที่สุด 1-2 ตัวพอครับ")

elif menu == "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)":
    st.title("📐 แผนกลยุทธ์จำกัดความเสี่ยงรายตัว & Dime! Override v13.0")
    
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
            sig = safe_signal_block_v13(df_proc, current_price, atr_multiplier)

            if sig is None:
                st.error("ระยะห่างราคาแคบเกินไปหรือข้อมูลไม่สมบูรณ์")
            else:
                pos = compute_position_size_v13(sig, account_capital_thb, risk_per_trade, max_position_pct, fx_rate, dime_fee_pct)
                
                if "BUY" in sig["signal"] and "⚠️" not in sig["signal"]:
                    signal_icon = "🟩"
                elif "⚠️" in sig["signal"]:
                    signal_icon = "🟨"
                else:
                    signal_icon = "🟥"

                cx1, cx2, cx3, cx4 = st.columns(4)
                cx1.metric("ราคาตั้งต้นระบบ (USD)", f"${sig['current_price']:.2f}")
                cx2.markdown(f"🤖 **สัญญาณหน้างาน:** \n## {signal_icon} {sig['signal']}")
                cx3.metric("🎯 ขายทำกำไร TP (USD)", f"${sig['tp']:.2f}")
                cx4.metric("🛑 หนีตาย Stop Loss (USD)", f"${sig['sl']:.2f}")

                cap_note = f" *(โดนจำกัดด้วยกฎสัดส่วนพอร์ต {max_position_pct}%)*" if pos["capped_by_position_limit"] else ""
                
                # กล่องคำสั่ง Action Plan
                st.success(
                    f"📥 **คัมภีร์ระบุคำสั่งซื้อขายบนแอป Dime! เพื่อสิทธิ์ชนะสูงสุด**\n\n"
                    f"1️⃣ **ขั้นตอนตอนซื้อ:** กดปุ่มซื้อใน Dime! -> เลือกโหมด **'ระบุจำนวนเงิน'** -> ป้อนตัวเลขจำนวนเต็ม **{pos['cost_thb']:,.0f} บาท** ลงไปในแอป\n"
                    f"2️⃣ **สัดส่วนที่ได้:** คุณจะได้เศษหุ้นประมาณ **{pos['shares']:.4f} หุ้น** (มูลค่าสัญญาจริงรวมค่าธรรมเนียมประมาณ ${pos['cost_usd']:.2f})\n"
                    f"3️⃣ **การบริหารหน้างาน (วินัยเหล็ก):** หากราคาปิดหลุดจุด **${sig['sl']:.2f}** ต้องตัดใจขายคัททิ้งทันที ขาดทุนจะถูกล็อกไว้ที่ **{pos['actual_risk_thb']:,.2f} บาท** เท่านั้น{cap_note}\n"
                    f"4️⃣ **แผนเพิ่มสิทธิ์ชนะ (ขยับบังทุน):** หากราคาวิ่งถูกทางไปจนถึงจุด **${sig['breakeven_trigger']:.2f}** ให้คุณขยับจุด Stop Loss ในใจขึ้นมาตั้งดักไว้ที่ราคาทุนทันที ไม้นี้จะปิดประตูแพ้ 100%!"
                )

                # [🏆 ฟีเจอร์เด็ด v13] Quick Trade Plan Exporter
                log_text = f"📋 [PLAN] {t_stock} ({t_frame}) | Action: {sig['signal']} | Buy: {pos['cost_thb']:,.0f} THB (~{pos['shares']:.4f} Shares) | Entry: ${sig['current_price']:.2f} | TP: ${sig['tp']:.2f} | SL: ${sig['sl']:.2f} | Max Loss: {pos['actual_risk_thb']:,.0f} THB"
                st.text_area("📋 คัดลอกข้อความแผนการเทรดด่วนไปเก็บไว้ใน Line / Note:", log_text, height=70)

                # วาดกราฟเชิงเทคนิคัลอัปเกรดแสดงเส้นเทรนด์ใหญ่
                plot_df = df_proc.tail(40)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name='ราคาหุ้น'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_5'], line=dict(color='#2eb85c', width=1.5), name='EMA 5'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#ffc107', width=1.5), name='EMA 20'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_50'], line=dict(color='#007bff', width=2, dash='dot'), name='EMA 50 (เส้นคัดเกรดเทรนด์ใหญ่)'))
                fig.add_hline(y=sig['tp'], line_dash="dash", line_color="green", annotation_text="Target Price")
                fig.add_hline(y=sig['sl'], line_dash="dash", line_color="red", annotation_text="Stop Loss")
                fig.update_layout(template="plotly_dark", title=f"แผนภูมิวิเคราะห์เชิงสถิติ v13 ({t_frame}) ของหุ้น {t_stock}", height=380, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("ไม่สามารถดึงโครงข่ายดาต้าของหุ้นตัวนี้ได้ กรุณาตรวจสอบตัวย่อภาษาอังกฤษอีกครั้ง")
