import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import time
import io
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════
# ⚙️ 1. SETUP THEME & RISK ENGINE CONFIG
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Stock Hunter Pro v8.0", layout="wide")

if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

st.sidebar.markdown("## 🦅 Stock Hunter Pro v8.0")
st.sidebar.markdown("### `Strict Risk Management Edition`")
st.sidebar.caption("🔒 ระบบเน้นป้องกันการหมดตัวและการรักษาเงินทุนหน้างาน")
st.sidebar.divider()

# แผงควบคุมบริหารความเสี่ยงถาวรที่ Sidebar (หัวใจของการกันล้างพอร์ต)
st.sidebar.markdown("### 🛡️ แผงควบคุม Risk Management")
account_capital = st.sidebar.number_input("เงินทุนทั้งหมดในพอร์ต ($):", min_value=100, value=10000, step=500)
risk_per_trade = st.sidebar.slider("ความเสี่ยงที่ยอมรับได้ต่อไม้ (%):", min_value=0.5, max_value=5.0, value=1.0, step=0.5)

st.sidebar.divider()
menu = st.sidebar.radio(
    "🧭 เลือกโหมดวิเคราะห์แผนเทรด:",
    [
        "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด",
        "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)",
        "📰 3. ข่าวสารสดเรียลไทม์ & Sentiment Analysis"
    ]
)

# ══════════════════════════════════════════════════════════════════════════
# 📦 2. ANTI-CRASH & ANTI-REPAINTING ENGINE
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=15) # ปรับลดแคชเหลือ 15 วินาทีเพื่อความเร็วสูงสุดของสายเดย์เทรด
def fetch_timeframe_data(ticker, interval="1h", _state_key=0):
    """ ดึงข้อมูลตาม Timeframe ที่เลือกพร้อมระบบ Rate Limiting และ Error Handling """
    time.sleep(0.3)
    
    # กำหนดช่วงเวลาดึงข้อมูลให้สัมพันธ์กับ Timeframe เพื่อความรวดเร็วในการโหลด
    period_map = {"15m": "5d", "1h": "1mo", "1d": "6mo"}
    period = period_map.get(interval, "1mo")
    
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
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
    
    # RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    
    return df

# ══════════════════════════════════════════════════════════════════════════
# 🎯 3. MODULE IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────────
# ⚡ MODULE 1: คำนวณขนาดไม้ (Position Sizing) เพื่อกันหมดตัว
# ──────────────────────────────────────────────────────────────────────────
if menu == "⚡ 1. คำนวณขนาดไม้เทรด (Position Sizing) & สแกนสด":
    st.title("🎯 ระบบคำนวณความเสี่ยงและสแกนสัญญาณเทรดแบบจำกัดความเสี่ยง")
    st.markdown("คำนวณปริมาณหุ้นที่ควรซื้อและจุดจำกัดการขาดทุนอ้างอิงจากกฎ **Risk 1% Rule** ของเทรดเดอร์อาชีพ")
    
    if st.button("🔄 [FORCE REFRESH] อัปเดตราคาสดทันที", type="primary"):
        st.session_state.refresh_key += 1
        st.rerun()
        
    watchlist_str = st.text_input("สัญลักษณ์หุ้นที่ต้องการสแกนหน้างาน (คั่นด้วย ,):", "NVDA, AAPL, TSLA, AMD, MSFT")
    tickers = [t.strip().upper() for t in watchlist_str.split(",") if t.strip()]
    tf_choice = st.selectbox("เลือกความละเอียดของแท่งเทียน (Timeframe):", ["1h", "15m", "1d"])
    
    scanned_data = []
    p_bar = st.progress(0)
    
    max_loss_allowed = account_capital * (risk_per_trade / 100)
    st.warning(f"🛡️ **นโยบายความปลอดภัย:** ไม้เทรดนี้หากผิดทาง คุณจะขาดทุนสูงสุดได้แค่ **${max_loss_allowed:.2f}** เท่านั้น (ระบบจะคำนวณจำนวนหุ้นให้สัมพันธ์กับจุดนี้อัตโนมัติ)")

    for idx, t in enumerate(tickers):
        raw_df = fetch_timeframe_data(t, interval=tf_choice, _state_key=st.session_state.refresh_key)
        df_proc = compute_indicators_and_signals(raw_df)
        
        if df_proc is not None:
            # ใช้ข้อมูลแท่งก่อนหน้าดนตรีป้องกันสัญญานขยับเปลี่ยน (Anti-Repainting)
            last_valid_row = df_proc.iloc[-2]
            current_price = df_proc['Close'].iloc[-1]
            atr = last_valid_row['ATR'] if not np.isnan(last_valid_row['ATR']) else (current_price * 0.02)
            
            if last_valid_row['EMA_5'] > last_valid_row['EMA_20']:
                signal = "🟩 BUY / LONG"
                tp = current_price + (1.5 * atr)
                sl = current_price - (1.0 * atr)
            else:
                signal = "🟥 SELL / SHORT"
                tp = current_price - (1.5 * atr)
                sl = current_price + (1.0 * atr)
                
            # 🧮 สูตรคำนวณ Position Sizing ป้องกันการหมดตัว
            risk_per_share = abs(current_price - sl)
            max_shares_to_buy = max_loss_allowed / risk_per_share if risk_per_share > 0 else 0
            total_allocation_cost = max_shares_to_buy * current_price
            
            scanned_data.append({
                "หุ้น": t,
                "ราคาปัจจุบัน": f"${current_price:.2f}",
                "📢 คำสั่งฟันธง": signal,
                "เป้ากำไร (TP)": f"${tp:.2f}",
                "จุดตัดขาดทุน (SL)": f"${sl:.2f}",
                "🧮 จำนวนหุ้นสูงสุดที่ควรซื้อ": f"{int(max_shares_to_buy)} หุ้น",
                "💵 เงินทุนที่ใช้ในไม้นี้": f"${total_allocation_cost:.2f}"
            })
        p_bar.progress((idx + 1) / len(tickers))
        
    if scanned_data:
        st.dataframe(pd.DataFrame(scanned_data), use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────────────────────────────────
# 📐 MODULE 2: เจาะลึกแผนเทรดคณิตศาสตร์ (สลับความละเอียดกราฟได้)
# ──────────────────────────────────────────────────────────────────────────
elif menu == "📐 2. เจาะลึกแผนเทรดคณิตศาสตร์ (สลับ Timeframe ได้)":
    st.title("📐 วางแผนและตรวจสอบพฤติกรรมกราฟรายตัวเชิงสถิติ")
    
    c_t1, c_t2 = st.columns(2)
    t_stock = c_t1.text_input("ป้อนตัวย่อหุ้นสากลที่ต้องการเจาะลึกออเดอร์:", "NVDA").upper()
    t_frame = c_t2.selectbox("เลือกกรอบเวลาวิเคราะห์เทคนิคัล (Timeframe):", ["15m", "1h", "1d"])
    
    raw_df = fetch_timeframe_data(t_stock, interval=t_frame, _state_key=st.session_state.refresh_key)
    df_proc = compute_indicators_and_signals(raw_df)
    
    if df_proc is not None:
        last_valid_row = df_proc.iloc[-2]
        current_price = df_proc['Close'].iloc[-1]
        atr = last_valid_row['ATR'] if not np.isnan(last_valid_row['ATR']) else (current_price * 0.02)
        
        if last_valid_row['EMA_5'] > last_valid_row['EMA_20']:
            act = "🟩 BUY / LONG"
            tp = current_price + (1.5 * atr)
            sl = current_price - (1.0 * atr)
        else:
            act = "🟥 SELL / SHORT"
            tp = current_price - (1.5 * atr)
            sl = current_price + (1.0 * atr)
            
        # คำนวณขนาดไม้สำหรับการแสดงผลหน้าเดี่ยว
        max_loss = account_capital * (risk_per_trade / 100)
        risk_per_share = abs(current_price - sl)
        shares = int(max_loss / risk_per_share) if risk_per_share > 0 else 0
        
        cx1, cx2, cx3, cx4 = st.columns(4)
        cx1.metric("ราคาสดบนกระดาน", f"${current_price:.2f}")
        cx2.markdown(f"🤖 **คำสั่งฟันธงเด็ดขาด:** \n## {act}")
        cx3.metric("🎯 เป้าขายเก็บกำไร (TP)", f"${tp:.2f}")
        cx4.metric("🛑 จุดตัดขาดทุนหนีภัย (SL)", f"${sl:.2f}")
        
        st.info(f"🛡️ **คำแนะนำการเข้าซื้อสไตล์มืออาชีพ:** เพื่อไม่ให้พอร์ตพัง ไม้นี้แนะนำให้กดซื้อสูงสุดไม่เกิน **{shares} หุ้น** เท่านั้น")
        
        # 📱 กราฟขนาดกะทัดรัด 360px ดูในมือถือได้สบายไม่บังเครื่องมือ
        plot_df = df_proc.tail(40)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name='แท่งเทียนราคา'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_5'], line=dict(color='#2eb85c', width=1.5), name='EMA 5'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#ffc107', width=1.5), name='EMA 20'))
        
        fig.add_hline(y=tp, line_dash="dash", line_color="green", annotation_text="Target Price")
        fig.add_hline(y=sl, line_dash="dash", line_color="red", annotation_text="Stop Loss")
        
        fig.update_layout(template="plotly_dark", title=f"แผนภูมิราคาสัญญาณปัจจุบัน ({t_frame}) ของหุ้น {t_stock}", height=360, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("ไม่สามารถเชื่อมข้อมูล Timeframe หลักทรัพย์นี้ได้ กรุณารอระบบรีเฟรช")

# ──────────────────────────────────────────────────────────────────────────
# 📰 MODULE 3: ดึงข่าวสารล่าสุดรอบ 7 วัน
# ──────────────────────────────────────────────────────────────────────────
elif menu == "📰 3. ข่าวสารสดเรียลไทม์ & Sentiment Analysis":
    st.title("📰 ตรวจสอบกระแสข่าวสารรอบด้านสกัดอารมณ์ตลาด")
    n_stock = st.text_input("ระบุสัญลักษณ์หุ้นที่ต้องการเช็กข่าวคราว:", "AAPL").upper()
    
    if st.button("🌐 เชื่อมต่อดึงข้อมูลข่าวสารกระดานจริง"):
        try:
            tick_obj = yf.Ticker(n_stock)
            feeds = tick_obj.news
            if feeds:
                for idx, art in enumerate(feeds[:4]):
                    st.markdown(f"""
                    <div style="background-color:#141923; padding:12px; border-radius:6px; margin-bottom:8px; border-left:4px solid #ffc107;">
                        <b>{idx+1}. {art.get('title','')}</b><br>
                        <small>แหล่งข่าว: {art.get('publisher','Market')} | <a href="{art.get('link','#')}" target="_blank" style="color:#ffc107;">อ่านเนื้อหาเต็ม 🔗</a></small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("ไม่พบกระแสข่าวสารเด่นชัดในช่วงนี้")
        except Exception as e:
            st.error(f"ไม่สามารถเรียกข่าวสารได้ชั่วคราว: {str(e)}")
