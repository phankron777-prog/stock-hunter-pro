import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import time
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Stock Hunter Pro v9.0", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

st.sidebar.markdown("## 🦅 Stock Hunter Pro v9.0")
st.sidebar.markdown("### `Strict Risk Management Edition+`")
st.sidebar.caption("🔒 เน้นป้องกันการหมดตัวและรักษาเงินทุนเป็นหลัก — ไม่ใช่เครื่องมือพยากรณ์ราคา")
st.sidebar.divider()

# ──────────────────────────────────────────────────────────────────────────
# คำเตือนความเสี่ยงถาวร — ต้องเห็นทุกครั้งที่เปิดแอป (เงินจริงห้ามมองข้าม)
# ──────────────────────────────────────────────────────────────────────────
st.sidebar.error(
    "⚠️ **คำเตือน:** ระบบนี้ใช้สูตร EMA Crossover + ATR ซึ่งเป็นอินดิเคเตอร์พื้นฐาน "
    "**ไม่ใช่การพยากรณ์ราคาที่แม่นยำ** ในตลาดไซด์เวย์สัญญาณจะกลับไปกลับมาบ่อย (whipsaw) "
    "และอาจขาดทุนติดต่อกันได้แม้ทำตามระบบทุกข้อ กรุณาอย่าฝากความหวังทั้งหมดไว้กับสัญญาณนี้"
)

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar (หัวใจของการกันล้างพอร์ต)
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต ($):", min_value=100, value=10000, step=500)
risk_per_trade = st.sidebar.slider("ความเสี่ยงที่ยอมรับได้ต่อไม้ (%):", min_value=0.25, max_value=3.0, value=1.0, step=0.25)

# ⬇️ NEW: จำกัดความเสี่ยงรวมทั้งพอร์ต (Portfolio Heat) — กันเปิดหลายไม้พร้อมกันจนเสี่ยงเกิน
max_portfolio_heat = st.sidebar.slider(
    "เพดานความเสี่ยงรวมทั้งพอร์ตหากทุกไม้โดน SL พร้อมกัน (%):",
    min_value=1.0, max_value=10.0, value=5.0, step=0.5,
    help="ถ้าเปิดหลายไม้พร้อมกัน ผลรวมความเสี่ยงของทุกไม้ไม่ควรเกินค่านี้ ของพอร์ตทั้งหมด"
)

# ⬇️ NEW: เพดานสัดส่วนเงินทุนสูงสุดต่อหุ้น 1 ตัว — กันกรณี ATR แคบผิดปกติแล้วระบบแนะนำซื้อเยอะเกินจริง
max_position_pct = st.sidebar.slider(
    "เพดานสัดส่วนเงินทุนสูงสุดต่อหุ้น 1 ตัว (% ของพอร์ต):",
    min_value=5, max_value=50, value=20, step=5,
    help="แม้ความเสี่ยง (ATR) จะแคบจนคำนวณได้จำนวนหุ้นเยอะ ระบบจะไม่แนะนำให้ใช้เงินเกินสัดส่วนนี้ในหุ้นตัวเดียว"
)

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดวิเคราะห์แผนเทรด:",
    [
        "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด",
        "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)",
        "📰 3. ข่าวสารสดเรียลไทม์ & Sentiment Analysis"
    ]
)

st.sidebar.divider()
st.sidebar.caption(
    "📌 เครื่องมือนี้ช่วยคำนวณคณิตศาสตร์ของการจัดการความเสี่ยงเท่านั้น "
    "การตัดสินใจเข้า/ออกไม้สุดท้ายเป็นดุลยพินิจของคุณเสมอ ไม่ใช่คำแนะนำการลงทุน"
)

# ══════════════════════════════════════════════════════════════════════════
# 📦 2. ANTI-CRASH & ANTI-REPAINTING ENGINE
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=15)
def fetch_timeframe_data(ticker, interval="1h", _state_key=0):
    """ ดึงข้อมูลตาม Timeframe ที่เลือกพร้อมระบบ Rate Limiting และ Error Handling """
    time.sleep(0.3)

    period_map = {"15m": "5d", "1h": "1mo", "1d": "6mo"}
    period = period_map.get(interval, "1mo")

    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        # NEW: กรองราคาที่ผิดปกติ (0, ติดลบ, NaN) ทิ้งก่อนคำนวณต่อ
        df = df[(df['Close'] > 0) & (df['High'] > 0) & (df['Low'] > 0)]
        if df.empty:
            return None
        return df
    except Exception:
        return None


def compute_indicators_and_signals(df):
    """ คำนวณระบบคณิตศาสตร์โดยใช้ราคาปิดแท่งที่แล้ว 100% ป้องกันจุดกลับตัวหลอก (No Repainting) """
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


def safe_signal_block(df_proc, current_price):
    """
    NEW: รวม logic คำนวณสัญญาณ + กัน edge case ไว้จุดเดียว ลดโอกาส bug ซ้ำซ้อน
    คืนค่า None ถ้าข้อมูลไม่น่าเชื่อถือพอจะคำนวณ — ดีกว่าคำนวณมั่วแล้วพอร์ตพัง
    """
    if df_proc is None or len(df_proc) < 2:
        return None
    last_valid_row = df_proc.iloc[-2]

    if pd.isna(last_valid_row['EMA_5']) or pd.isna(last_valid_row['EMA_20']):
        return None
    if current_price is None or current_price <= 0 or np.isnan(current_price):
        return None

    atr = last_valid_row['ATR']
    if pd.isna(atr) or atr <= 0:
        # ATR เสีย/แคบผิดปกติ -> ใช้ 2% ของราคาเป็น fallback แทนการปล่อยให้ risk_per_share เป็น 0
        atr = current_price * 0.02

    if last_valid_row['EMA_5'] > last_valid_row['EMA_20']:
        signal = "BUY / LONG"
        tp = current_price + (1.5 * atr)
        sl = current_price - (1.0 * atr)
    else:
        signal = "SELL / SHORT"
        tp = current_price - (1.5 * atr)
        sl = current_price + (1.0 * atr)

    risk_per_share = abs(current_price - sl)
    if risk_per_share <= 0:
        return None

    return {
        "signal": signal,
        "tp": tp,
        "sl": sl,
        "atr": atr,
        "risk_per_share": risk_per_share,
        "current_price": current_price,
    }


def compute_position_size(sig, account_capital, risk_per_trade_pct, max_position_pct):
    """
    NEW: คำนวณจำนวนหุ้น โดยบังคับทั้งสองเพดาน
      1) ขาดทุนสูงสุดต่อไม้ (risk_per_trade_pct ของพอร์ต)
      2) เงินทุนสูงสุดต่อหุ้นตัวเดียว (max_position_pct ของพอร์ต)
    ใช้ค่าที่ "น้อยกว่า" เสมอ กันกรณี ATR แคบจนคำนวณได้หุ้นเยอะเกินจริง
    """
    max_loss_allowed = account_capital * (risk_per_trade_pct / 100)
    shares_by_risk = max_loss_allowed / sig["risk_per_share"]

    max_capital_allowed = account_capital * (max_position_pct / 100)
    shares_by_capital_cap = max_capital_allowed / sig["current_price"]

    final_shares = int(min(shares_by_risk, shares_by_capital_cap))
    capped_by_position_limit = shares_by_capital_cap < shares_by_risk

    return {
        "shares": max(final_shares, 0),
        "cost": max(final_shares, 0) * sig["current_price"],
        "max_loss_allowed": max_loss_allowed,
        "capped_by_position_limit": capped_by_position_limit,
    }


def compute_correlation_matrix(price_data: dict):
    """
    NEW: คำนวณ correlation ของ % การเปลี่ยนแปลงราคาระหว่างหุ้นในลิสต์
    ใช้เตือนผู้ใช้เมื่อหุ้นหลายตัว "วิ่งไปทางเดียวกัน" จริงๆ คือเสี่ยงไม้เดียวซ่อนอยู่
    """
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


# ══════════════════════════════════════════════════════════════════════════
# 🎯 3. MODULE IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────────
# ⚡ MODULE 1: คำนวณขนาดไม้ (Position Sizing) เพื่อกันหมดตัว
# ──────────────────────────────────────────────────────────────────────────
if menu == "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด":
    st.title("🎯 ระบบคำนวณความเสี่ยงและสแกนสัญญาณเทรดแบบจำกัดความเสี่ยง")
    st.markdown(
        "คำนวณปริมาณหุ้นที่ควรซื้อและจุดจำกัดการขาดทุน อ้างอิงกฎ **Risk per Trade** "
        "พร้อมเพดานความเสี่ยงรวมทั้งพอร์ตและเพดานสัดส่วนต่อหุ้น"
    )
    st.caption(
        "⚠️ สัญญาณ BUY/SELL ด้านล่างมาจากการตัดกันของเส้นค่าเฉลี่ย (EMA crossover) เท่านั้น "
        "เป็นข้อมูลเชิงสถิติ ไม่ใช่การการันตีทิศทางราคา"
    )

    if st.button("🔄 [FORCE REFRESH] อัปเดตราคาสดทันที", type="primary"):
        st.session_state.refresh_key += 1
        st.rerun()

    watchlist_str = st.text_input("สัญลักษณ์หุ้นที่ต้องการสแกนหน้างาน (คั่นด้วย ,):", "NVDA, AAPL, TSLA, AMD, MSFT")
    tickers = [t.strip().upper() for t in watchlist_str.split(",") if t.strip()]
    # NEW: กันลิสต์ยาวเกินไปจนยิง request รัวๆ และกันพิมพ์ ticker ซ้ำ
    tickers = list(dict.fromkeys(tickers))[:15]
    tf_choice = st.selectbox("เลือกความละเอียดของแท่งเทียน (Timeframe):", ["1h", "15m", "1d"])

    max_loss_allowed = account_capital * (risk_per_trade / 100)
    max_capital_allowed = account_capital * (max_position_pct / 100)
    st.warning(
        f"🛡️ **ขีดจำกัดต่อไม้:** ขาดทุนสูงสุดต่อไม้ไม่เกิน **${max_loss_allowed:,.2f}** "
        f"และเงินทุนต่อหุ้น 1 ตัวไม่เกิน **${max_capital_allowed:,.2f}** ({max_position_pct}% ของพอร์ต) "
        f"— ระบบจะใช้ค่าที่ต่ำกว่าเสมอเพื่อความปลอดภัย"
    )

    scanned_data = []
    raw_price_data = {}  # NEW: เก็บไว้คำนวณ correlation
    total_committed_risk = 0.0  # NEW: รวมความเสี่ยงสะสมถ้าเข้าทุกไม้ที่สแกนเจอ

    if tickers:
        p_bar = st.progress(0)
        for idx, t in enumerate(tickers):
            raw_df = fetch_timeframe_data(t, interval=tf_choice, _state_key=st.session_state.refresh_key)
            raw_price_data[t] = raw_df
            df_proc = compute_indicators_and_signals(raw_df)

            if df_proc is not None:
                current_price = df_proc['Close'].iloc[-1]
                sig = safe_signal_block(df_proc, current_price)

                if sig is not None:
                    pos = compute_position_size(sig, account_capital, risk_per_trade, max_position_pct)
                    total_committed_risk += min(pos["max_loss_allowed"], pos["shares"] * sig["risk_per_share"])

                    signal_icon = "🟩" if sig["signal"] == "BUY / LONG" else "🟥"
                    cap_note = " (ถูกจำกัดด้วยเพดานสัดส่วนต่อหุ้น)" if pos["capped_by_position_limit"] else ""

                    scanned_data.append({
                        "หุ้น": t,
                        "ราคาปัจจุบัน": f"${sig['current_price']:.2f}",
                        "สัญญาณ (เชิงสถิติ)": f"{signal_icon} {sig['signal']}",
                        "เป้ากำไร (TP)": f"${sig['tp']:.2f}",
                        "จุดตัดขาดทุน (SL)": f"${sig['sl']:.2f}",
                        "จำนวนหุ้นสูงสุดที่คำนวณได้": f"{pos['shares']} หุ้น{cap_note}",
                        "เงินทุนที่ใช้ในไม้นี้": f"${pos['cost']:,.2f}",
                    })
                else:
                    scanned_data.append({
                        "หุ้น": t, "ราคาปัจจุบัน": "-", "สัญญาณ (เชิงสถิติ)": "⚪ ข้อมูลไม่พอ/ไม่น่าเชื่อถือ",
                        "เป้ากำไร (TP)": "-", "จุดตัดขาดทุน (SL)": "-",
                        "จำนวนหุ้นสูงสุดที่คำนวณได้": "-", "เงินทุนที่ใช้ในไม้นี้": "-",
                    })
            else:
                scanned_data.append({
                    "หุ้น": t, "ราคาปัจจุบัน": "-", "สัญญาณ (เชิงสถิติ)": "⚪ ดึงข้อมูลไม่สำเร็จ",
                    "เป้ากำไร (TP)": "-", "จุดตัดขาดทุน (SL)": "-",
                    "จำนวนหุ้นสูงสุดที่คำนวณได้": "-", "เงินทุนที่ใช้ในไม้นี้": "-",
                })
            p_bar.progress((idx + 1) / len(tickers))

    if scanned_data:
        st.dataframe(pd.DataFrame(scanned_data), use_container_width=True, hide_index=True)

        # ──────────────────────────────────────────────────────────────
        # NEW: Portfolio Heat Check — ความเสี่ยงรวมถ้าเข้าทุกไม้พร้อมกัน
        # ──────────────────────────────────────────────────────────────
        st.divider()
        st.subheader("🔥 ตรวจสอบความเสี่ยงรวมทั้งพอร์ต (Portfolio Heat)")
        heat_pct = (total_committed_risk / account_capital * 100) if account_capital > 0 else 0
        heat_limit_dollar = account_capital * (max_portfolio_heat / 100)

        hc1, hc2, hc3 = st.columns(3)
        hc1.metric("ความเสี่ยงรวมถ้าเข้าทุกไม้พร้อมกัน", f"${total_committed_risk:,.2f}")
        hc2.metric("คิดเป็น % ของพอร์ต", f"{heat_pct:.2f}%")
        hc3.metric("เพดานที่ตั้งไว้", f"{max_portfolio_heat:.1f}% (${heat_limit_dollar:,.2f})")

        if heat_pct > max_portfolio_heat:
            st.error(
                f"🚨 **เกินเพดาน!** หากเปิดทุกไม้ในตารางพร้อมกันแล้วโดน SL ทั้งหมด "
                f"จะขาดทุนรวม {heat_pct:.2f}% เกินเพดาน {max_portfolio_heat:.1f}% ที่ตั้งไว้ "
                f"แนะนำให้เลือกเข้าเฉพาะบางไม้ ไม่ใช่เข้าทุกตัวพร้อมกัน"
            )
        else:
            st.success(f"✅ ความเสี่ยงรวมยังอยู่ในเพดานที่ตั้งไว้ ({heat_pct:.2f}% / {max_portfolio_heat:.1f}%)")

        # ──────────────────────────────────────────────────────────────
        # NEW: Correlation Check — เตือนหุ้นที่วิ่งไปทางเดียวกัน
        # ──────────────────────────────────────────────────────────────
        corr_matrix = compute_correlation_matrix(raw_price_data)
        if corr_matrix is not None and len(corr_matrix) >= 2:
            st.subheader("🔗 ตรวจสอบความสัมพันธ์ระหว่างหุ้นในลิสต์ (Correlation)")
            st.caption(
                "ถ้าหุ้นสองตัวมีค่าสหสัมพันธ์ (correlation) สูงกว่า 0.7 แปลว่ามันมักวิ่งไปทางเดียวกัน "
                "การเปิดไม้พร้อมกันในหุ้นกลุ่มนี้ = เพิ่มความเสี่ยงไม้เดียวซ้อนกัน ไม่ใช่กระจายความเสี่ยงจริง"
            )

            high_corr_pairs = []
            cols = corr_matrix.columns
            for i in range(len(cols)):
                for j in range(i + 1, len(cols)):
                    val = corr_matrix.iloc[i, j]
                    if pd.notna(val) and abs(val) >= 0.7:
                        high_corr_pairs.append((cols[i], cols[j], val))

            if high_corr_pairs:
                for a, b, v in sorted(high_corr_pairs, key=lambda x: -abs(x[2])):
                    direction = "วิ่งทางเดียวกัน" if v > 0 else "วิ่งสวนทางกัน"
                    st.warning(f"⚠️ **{a} ↔ {b}**: correlation = {v:.2f} ({direction})")
            else:
                st.info("ไม่พบคู่หุ้นที่มีความสัมพันธ์สูงผิดปกติในลิสต์นี้")

            with st.expander("ดูตาราง Correlation แบบเต็ม"):
                st.dataframe(corr_matrix.round(2), use_container_width=True)

# ──────────────────────────────────────────────────────────────────────────
# 📐 MODULE 2: เจาะลึกแผนเทรดคณิตศาสตร์ (สลับความละเอียดกราฟได้)
# ──────────────────────────────────────────────────────────────────────────
elif menu == "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)":
    st.title("📐 วางแผนและตรวจสอบพฤติกรรมกราฟรายตัวเชิงสถิติ")
    st.caption(
        "⚠️ ผลลัพธ์ด้านล่างคำนวณจากสูตร EMA/ATR เท่านั้น ไม่ใช่การวิเคราะห์ปัจจัยพื้นฐานหรือข่าวสาร "
        "โปรดใช้ประกอบการตัดสินใจ ไม่ใช่ใช้แทนการตัดสินใจ"
    )

    c_t1, c_t2 = st.columns(2)
    t_stock = c_t1.text_input("ป้อนตัวย่อหุ้นสากลที่ต้องการเจาะลึกออเดอร์:", "NVDA").upper().strip()
    t_frame = c_t2.selectbox("เลือกกรอบเวลาวิเคราะห์เทคนิคัล (Timeframe):", ["15m", "1h", "1d"])

    if not t_stock:
        st.info("กรุณาป้อนสัญลักษณ์หุ้น")
    else:
        raw_df = fetch_timeframe_data(t_stock, interval=t_frame, _state_key=st.session_state.refresh_key)
        df_proc = compute_indicators_and_signals(raw_df)

        if df_proc is not None:
            current_price = df_proc['Close'].iloc[-1]
            sig = safe_signal_block(df_proc, current_price)

            if sig is None:
                st.error("ข้อมูลของหุ้นนี้ไม่น่าเชื่อถือพอจะคำนวณสัญญาณ (ราคา/ATR ผิดปกติ) กรุณาลองหุ้นอื่นหรือ Timeframe อื่น")
            else:
                pos = compute_position_size(sig, account_capital, risk_per_trade, max_position_pct)
                signal_icon = "🟩" if sig["signal"] == "BUY / LONG" else "🟥"

                cx1, cx2, cx3, cx4 = st.columns(4)
                cx1.metric("ราคาสดบนกระดาน", f"${sig['current_price']:.2f}")
                cx2.markdown(f"🤖 **สัญญาณเชิงสถิติ (EMA Crossover):** \n## {signal_icon} {sig['signal']}")
                cx3.metric("🎯 เป้าหมายกำไร (TP)", f"${sig['tp']:.2f}")
                cx4.metric("🛑 จุดตัดขาดทุน (SL)", f"${sig['sl']:.2f}")

                cap_note = ""
                if pos["capped_by_position_limit"]:
                    cap_note = (
                        f" *(จำนวนนี้ถูกจำกัดโดยเพดานสัดส่วนต่อหุ้น {max_position_pct}% ของพอร์ต "
                        f"ไม่ใช่คำนวณจาก ATR ตรงๆ เพราะ ATR แคบผิดปกติ)*"
                    )

                st.info(
                    f"🛡️ **ขนาดไม้ตามกฎความเสี่ยง:** ไม่เกิน **{pos['shares']} หุ้น** "
                    f"(ใช้เงิน ~${pos['cost']:,.2f}, ขาดทุนสูงสุดหากโดน SL ≈ ${pos['max_loss_allowed']:,.2f}){cap_note}"
                )

                if df_proc['RSI'].iloc[-2] > 70:
                    st.warning("📌 RSI อยู่ในโซน Overbought (>70) — โมเมนตัมฝั่งซื้ออาจร้อนแรงเกินไปแล้ว ระวังการย่อตัว")
                elif df_proc['RSI'].iloc[-2] < 30:
                    st.warning("📌 RSI อยู่ในโซน Oversold (<30) — โมเมนตัมฝั่งขายอาจร้อนแรงเกินไปแล้ว ระวังการเด้งกลับ")

                plot_df = df_proc.tail(40)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=plot_df.index, open=plot_df['Open'], high=plot_df['High'],
                    low=plot_df['Low'], close=plot_df['Close'], name='แท่งเทียนราคา'
                ))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_5'], line=dict(color='#2eb85c', width=1.5), name='EMA 5'))
                fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#ffc107', width=1.5), name='EMA 20'))

                fig.add_hline(y=sig['tp'], line_dash="dash", line_color="green", annotation_text="Target Price")
                fig.add_hline(y=sig['sl'], line_dash="dash", line_color="red", annotation_text="Stop Loss")

                fig.update_layout(
                    template="plotly_dark",
                    title=f"แผนภูมิราคาสัญญาณปัจจุบัน ({t_frame}) ของหุ้น {t_stock}",
                    height=360, margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("ไม่สามารถเชื่อมข้อมูล Timeframe หลักทรัพย์นี้ได้ กรุณาตรวจสอบสัญลักษณ์หุ้นหรือรอระบบรีเฟรช")

# ──────────────────────────────────────────────────────────────────────────
# 📰 MODULE 3: ดึงข่าวสารล่าสุด
# ──────────────────────────────────────────────────────────────────────────
elif menu == "📰 3. ข่าวสารสดเรียลไทม์ & Sentiment Analysis":
    st.title("📰 ตรวจสอบกระแสข่าวสารรอบด้านสกัดอารมณ์ตลาด")
    st.caption("⚠️ หัวข้อข่าวด้านล่างดึงมาจาก Yahoo Finance ตรงๆ ไม่ได้ผ่านการวิเคราะห์ sentiment จริง กรุณาอ่านเนื้อหาเต็มก่อนใช้ประกอบการตัดสินใจ")
    n_stock = st.text_input("ระบุสัญลักษณ์หุ้นที่ต้องการเช็กข่าวคราว:", "AAPL").upper().strip()

    if st.button("🌐 เชื่อมต่อดึงข้อมูลข่าวสารกระดานจริง"):
        if not n_stock:
            st.info("กรุณาป้อนสัญลักษณ์หุ้น")
        else:
            try:
                tick_obj = yf.Ticker(n_stock)
                feeds = tick_obj.news
                if feeds:
                    for idx, art in enumerate(feeds[:4]):
                        title = art.get('title', 'ไม่มีหัวข้อ')
                        publisher = art.get('publisher', 'Market')
                        link = art.get('link', '#')
                        st.markdown(f"""
                        <div style="background-color:#141923; padding:12px; border-radius:6px; margin-bottom:8px; border-left:4px solid #ffc107;">
                            <b>{idx+1}. {title}</b><br>
                            <small>แหล่งข่าว: {publisher} | <a href="{link}" target="_blank" style="color:#ffc107;">อ่านเนื้อหาเต็ม 🔗</a></small>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("ไม่พบกระแสข่าวสารเด่นชัดในช่วงนี้")
            except Exception as e:
                st.error(f"ไม่สามารถเรียกข่าวสารได้ชั่วคราว: {str(e)}")
