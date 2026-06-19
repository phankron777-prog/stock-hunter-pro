import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Stock Hunter Pro v11.0 (Trade Sheet Ready)", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

st.sidebar.markdown("## 🦅 Stock Hunter Pro v11.0")
st.sidebar.markdown("### `The Action List Engine`")
st.sidebar.caption("🔒 โฟกัสเฉพาะคณิตศาสตร์การคุมเงินทุน — แยกหน้างาน 3 แท็บชัดเจน")
st.sidebar.divider()

st.sidebar.error(
    "⚠️ คำเตือนระบบ: ระบบนี้ใช้สูตร EMA Crossover + ATR สำหรับคำนวณขนาดไม้หน้างาน "
    "หัวใจสำคัญคือการคุมขนาดไม้เพื่อไม่ให้พอร์ตเสียหายหนักเมื่อผิดทาง"
)

# แผงควบคุมบริหารความเสี่ยงที่ Sidebar (ดึงมาจาก v10.0 เดิมของพี่)
st.sidebar.markdown("### 💰 MM & Risk Parameters")
account_capital = st.sidebar.number_input("เงินทุนรวมในพอร์ต ($):", value=100000, step=5000)
base_risk_pct = st.sidebar.slider("ความเสี่ยงสูงสุดต่อไม้ (1R %):", 0.25, 2.0, 1.0, 0.25)
atr_multiplier = st.sidebar.slider("ATR Stop Loss Multiplier:", 1.5, 3.5, 2.0, 0.5)

# รายชื่อหุ้นผู้นำตลาด
tickers_pool = ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "COIN", "ASTS", "SMCI", "AVGO", "CMG"]

# ══════════════════════════════════════════════════════════════════════════
# 🧠 2. CORE RISK ENGINE FUNCTIONS (โครงสร้างคณิตศาสตร์เดิมของพี่)
# ══════════════════════════════════════════════════════════════════════════
def get_stock_data(ticker):
    try:
        df = yf.Ticker(ticker).history(period="1y")
        if df.empty: return None
        df['EMA_Fast'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA_Slow'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        # คำนวณ ATR เพื่อใช้ทำ Position Sizing และ Stop Loss
        high_low = df['High'] - df['Low']
        high_cp = np.abs(df['High'] - df['Close'].shift())
        low_cp = np.abs(df['Low'] - df['Close'].shift())
        df['TR'] = np.max([high_low, high_cp, low_cp], axis=0)
        df['ATR'] = df['TR'].rolling(window=14).mean()
        return df
    except:
        return None

# ══════════════════════════════════════════════════════════════════════════
# 🎯 3. INTERFACE ระดับ \"ใช้ง่ายมาก\" (Trade Sheet & Action List Ready)
# ══════════════════════════════════════════════════════════════════════════
st.title("🦅 แผงควบคุมปฏิบัติการเทรด (Action List Dashboard)")
st.caption("หน้างานจริงตื่นเช้ามาเปิดโปรแกรม แล้วเลือกดูสถานะหุ้นตามแท็บด้านล่างนี้ได้ทันที")

# ส่วนคำนวณคัดแยกกลุ่มข้อมูล (Background Processing)
buy_today_data = []
watchlist_data = []
banned_data = []

with st.spinner("กำลังตรวจสอบสัญญาณและคำนวณขนาดไม้ประจำวัน..."):
    for ticker in tickers_pool:
        df = get_stock_data(ticker)
        if df is not None and len(df) > 21:
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            
            current_price = last_row['Close']
            current_atr = last_row['ATR'] if not np.isnan(last_row['ATR']) else (current_price * 0.03)
            
            # คำนวณจุด Stop Loss และขนาดหุ้น (Position Sizing) ตามกฎเดิมของพี่
            stop_loss_distance = current_atr * atr_multiplier
            stop_loss_price = current_price - stop_loss_distance
            
            risk_cash = account_capital * (base_risk_pct / 100)
            shares_to_buy = risk_cash / stop_loss_distance if stop_loss_distance > 0 else 0
            total_cost = shares_to_buy * current_price
            
            # ตรรกะตรวจจับสัญญาณ EMA Crossover
            is_bullish_trend = last_row['EMA_Fast'] > last_row['EMA_Slow']
            had_just_crossed = (prev_row['EMA_Fast'] <= prev_row['EMA_Slow']) and (last_row['EMA_Fast'] > last_row['EMA_Slow'])
            
            payload = {
                "ชื่อหุ้น (Ticker)": ticker,
                "ราคาสดปัจจุบัน": f"${current_price:.2f}",
                "จำนวนหุ้นที่ต้องคีย์ (Shares)": int(shares_to_buy) if shares_to_buy > 0 else 0,
                "ตั้งจุดตัดขาดทุน (Stop Loss)": f"${stop_loss_price:.2f}",
                "วงเงินที่ใช้เงินจริง ($)": f"${total_cost:,.2f}",
                "เป้าทำกำไรขั้นต่ำ (Take Profit)": f"${current_price + (stop_loss_distance * 2):.2f}"
            }
            
            # คัดแยกกลุ่มเข้า 3 แท็บเด็ดขาดตามเงื่อนไขหน้างาน
            if is_bullish_trend and had_just_crossed:
                # 🟢 สัญญาณพึ่งตัดขึ้นสดๆ ร้อนๆ วันนี้ -> ยัดเข้าหน้า BUY TODAY ทันที
                buy_today_data.append(payload)
            elif is_bullish_trend:
                # ⚠️ แนวโน้มยังดีอยู่แต่ราคาขึ้นไปแล้ว หรือรอจังหวะย่อ -> ยัดเข้า WATCHLIST
                watchlist_data.append({
                    "ชื่อหุ้น (Ticker)": ticker,
                    "ราคาสดปัจจุบัน": f"${current_price:.2f}",
                    "สถานะหน้างาน": "EMA ขาขึ้น (ถือครอง/เฝ้าระวัง)"
                })
            else:
                # ❌ เส้นค่าเฉลี่ยตัดลง เป็นเทรนด์ขาลง ห้ามยุ่งเด็ดขาด -> ยัดเข้า BANNED ZONE
                banned_data.append({
                    "ชื่อหุ้น (Ticker)": ticker,
                    "ราคาสดปัจจุบัน": f"${current_price:.2f}",
                    "สถานะหน้างาน": "EMA ขาลง (อันตราย ห้ามเทรด)"
                })

# 🚀 แสดงผลหน้าจอแยก 3 แท็บชัดเจนระดับ "ใช้ง่ายมาก"
tab_buy, tab_watch, tab_ban = st.tabs([
    "🟢 แผ่นงานส่งคำสั่งซื้อวันนี้ (BUY TODAY)", 
    "⚠️ รายการหุ้นเฝ้าระวัง (WATCHLIST)", 
    "❌ หุ้นห้ามจับต้องเด็ดขาด (BANNED ZONE)"
])

with tab_buy:
    st.markdown("### 🎯 แผ่นใบงานส่งคำสั่งซื้อ (Trade Sheet หน้างาน)")
    if buy_today_data:
        st.success("พบสัญญาณซื้อที่สมบูรณ์แบบในเช้านี้! พี่สามารถลอกตารางช่อง **Shares** และ **Stop Loss** ไปคีย์ส่งคำสั่งซื้อจริงได้ทันทีครับ")
        st.dataframe(pd.DataFrame(buy_today_data), use_container_width=True, hide_index=True)
    else:
        st.info("⬜ เช้านี้ระบบตรวจสอบแล้ว 'ไม่มีหุ้นตัวใดเกิดสัญญาณซื้อร่วมที่ตัดขึ้นใหม่' นอนทับมือ ถือเงินสดไว้ให้ปลอดภัยครับพี่")

with tab_watch:
    st.markdown("### 👀 รายการหุ้นแนวโน้มขาขึ้น (ถือครองต่อเนื่องหรือรอจังหวะ)")
    if watchlist_data:
        st.dataframe(pd.DataFrame(watchlist_data), use_container_width=True, hide_index=True)
    else:
        st.info("ไม่มีหุ้นในรายการเฝ้าระวัง")

with tab_ban:
    st.markdown("### ❌ รายการหุ้นอันตรายห้ามเข้าซื้อเด็ดขาด")
    if banned_data:
        st.dataframe(pd.DataFrame(banned_data), use_container_width=True, hide_index=True)
    else:
        st.info("ยินดีด้วยครับ ไม่มีหุ้นตัวใดอยู่ในโซนอันตราย")
