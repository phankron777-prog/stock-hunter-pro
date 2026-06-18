import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

# ══════════════════════════════════════════════════════════════════════════
# ⚙️ SYSTEM SETTINGS & LAYOUT
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Stock Hunter Pro v6.0", layout="wide")

# รายชื่อหุ้นเฝ้าระวังสำหรับการเล่นสั้น (ปรับเปลี่ยนสัญลักษณ์ได้ตรงนี้)
WATCHLIST = ["NVDA", "AAPL", "TSLA", "AMD", "MSFT"]

st.sidebar.markdown("## 🦅 Stock Hunter Pro v6.0")
st.sidebar.markdown("### `Short-Term Sniper Edition`")
st.sidebar.caption("⚡ ระบบฟันธงสัญญาณเข้า-ออก สำหรับสายเล่นสั้น")
st.sidebar.divider()

menu = st.sidebar.radio(
    "🧭 เลือกโหมดใช้งาน:",
    ["📊 หน้าแรก: สแกนและฟันธงสัญญาณสด", "🔍 ค้นหา & เจาะลึกรายตัว"]
)

# ══════════════════════════════════════════════════════════════════════════
# 📦 CORE TRADING ENGINE (คำนวณสัญญาณและฟันธงตัวเลข)
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60) # อัปเดตข้อมูลทุกๆ 1 นาที เพื่อความสดใหม่สายเล่นสั้น
def fetch_short_term_data(ticker):
    """ ดึงข้อมูลราคารายวันย้อนหลังเพื่อคำนวณสัญญาณเทรดระยะสั้น """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="3mo") # ใช้ข้อมูลย้อนหลัง 3 เดือนเพื่อให้โหลดเร็วและสะท้อนภาพปัจจุบัน
        if df.empty:
            return pd.DataFrame()
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        return df
    except Exception:
        return pd.DataFrame()

def analyze_and_decision(df):
    """ สูตรคำนวณความเร่งระยะสั้นเพื่อ 'ฟันธง' จุดเข้าทำกำไรและจุดตัดขาดทุน """
    if df.empty or len(df) < 20:
        return None
    
    # คำนวณเส้นค่าเฉลี่ยระยะสั้นมากสำหรับ Day Trade/Swing Trade
    df['EMA_5'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # คำนวณ RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # คำนวณกรอบความผันผวนย้อนหลัง (ATR) เพื่อใช้ตั้งจุด Stop Loss ที่ไม่แคบจนโดนสะบัดหลุด
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    
    # ดึงข้อมูลแถวล่าสุด (ราคาปัจจุบันปัจจุบัน)
    last_row = df.iloc[-1]
    current_price = last_row['Close']
    ema5 = last_row['EMA_5']
    ema20 = last_row['EMA_20']
    rsi = last_row['RSI']
    atr = last_row['ATR'] if not np.isnan(last_row['ATR']) else (current_price * 0.02)
    
    # 🎯 LOGIC ฟันธงสัญญาณ (SHORT-TERM TRADING RULES)
    # เงื่อนไขฝั่งซื้อ: เส้นเร็วตัดเหนือเส้นช้า (Bullish Momentum) หรือ RSI เกิดภาวะ Oversold รุนแรงแล้วเริ่มงัดหัวขึ้น
    if (ema5 > ema20) or (rsi < 35):
        action = "🟩 BUY / LONG"
        reason = "โมเมนตัมระยะสั้นเปลี่ยนทิศเป็นขาขึ้น (EMA 5 > 20) หรือราคาลงแรงเข้าเขตซื้อกลับ"
        target_price = current_price + (1.5 * atr)  # เป้ากำไรระยะสั้นตามกรอบความผันผวน
        stop_loss = current_price - (1.0 * atr)    # จุดหนีหากผิดทาง
    else:
        action = "🟥 SELL / SHORT"
        reason = "แนวโน้มระยะสั้นอยู่ในฝั่งอ่อนแรง (EMA 5 < 20) ความเสี่ยงขาลงยังคงได้เปรียบ"
        target_price = current_price - (1.5 * atr)
        stop_loss = current_price + (1.0 * atr)
        
    return {
        "price": current_price,
        "action": action,
        "reason": reason,
        "rsi": rsi,
        "target": target_price,
        "stop": stop_loss,
        "df": df
    }

# ══════════════════════════════════════════════════════════════════════════
# 📊 MODE 1: แดชบอร์ดสแกนและฟันธงสัญญาณทันที
# ══════════════════════════════════════════════════════════════════════════
if menu == "📊 หน้าแรก: สแกนและฟันธงสัญญาณสด":
    st.title("🎯 แดชบอร์ดฟันธงสัญญาณเทรดระยะสั้น (Short-Term Tactical Scan)")
    st.markdown("ระบบจะดึงราคาสด ล่าสุด และประมวลผลคำสั่งที่ต้องปฏิบัติทันทีตามเงื่อนไขทางเทคนิค")
    
    if st.button("🔄 กดเพื่อสแกนและอัปเดตสัญญาณสด (Refresh)", type="primary"):
        st.rerun()
        
    summary_data = []
    
    with st.spinner("⏳ กำลังดึงราคาสดสแกนตลาด..."):
        for ticker in WATCHLIST:
            df = fetch_short_term_data(ticker)
            result = analyze_and_decision(df)
            
            if result:
                summary_data.append({
                    "ชื่อหุ้น": ticker,
                    "ราคาล่าสุด": f"${result['price']:.2f}",
                    "🚨 ฟันธงคำสั่ง": result['action'],
                    "ค่า RSI": f"{result['rsi']:.1f}",
                    "🎯 เป้าทำกำไร (Target)": f"${result['target']:.2f}",
                    "🛑 จุดหนี (Stop Loss)": f"${result['stop']:.2f}",
                    "เหตุผลทางเทคนิค": result['reason']
                })
                
    if summary_data:
        st.dataframe(
            pd.DataFrame(summary_data), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("กำลังรอการเชื่อมต่อหรือไม่มีข้อมูลใน Watchlist ขณะนี้")

# ══════════════════════════════════════════════════════════════════════════
# 🔍 MODE 2: เจาะลึกกราฟเทคนิคัลและคำนวณแผนการเทรดรายตัว
# ══════════════════════════════════════════════════════════════════════════
elif menu == "🔍 ค้นหา & เจาะลึกรายตัว":
    st.title("🔍 วิเคราะห์แผนการเทรดและวางกรอบราคาซื้อขายรายตัว")
    
    search_ticker = st.text_input("ระบุชื่อหุ้นที่ต้องการเจาะลึกแผนเทรดระยะสั้น:", "NVDA").upper()
    
    df = fetch_short_term_data(search_ticker)
    result = analyze_and_decision(df)
    
    if result:
        # แบ่งคอลัมน์แสดงตัวเลขฟันธงขนาดใหญ่
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ราคาปิดล่าสุด", f"${result['price']:.2f}")
        c2.markdown(f"### คำสั่งฟันธง\n### {result['action']}")
        c3.metric("🎯 เป้าหมายทำกำไรสั้น", f"${result['target']:.2f}")
        c4.metric("🛑 จุดตัดขาดทุน (Stop Loss)", f"${result['stop']:.2f}")
        
        st.info(f"**เหตุผลประกอบการตัดสินใจ:** {result['reason']}")
        
        # วาดกราฟแท่งเทียนระยะสั้นพร้อมเส้น EMA ไว้วางแผนหน้างาน
        plot_df = result['df'].tail(45) # ดูย้อนหลังแค่อดีต 45 แท่งเพื่อให้เห็นภาพขยายสำหรับการเล่นรอบสั้น
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=plot_df.index, 
            open=plot_df['Open'], high=plot_df['High'], 
            low=plot_df['Low'], close=plot_df['Close'], 
            name='ราคาแท่งเทียน'
        ))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_5'], line=dict(color='#2eb85c', width=2), name='EMA 5 วัน (เส้นเร็ว)'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#ffc107', width=2), name='EMA 20 วัน (เส้นช้า)'))
        
        # ลากเส้นแนวราคาเป้าหมายในกราฟให้เห็นภาพชัดเจน
        fig.add_hline(y=result['target'], line_dash="dash", line_color="#2eb85c", annotation_text="Target Price")
        fig.add_hline(y=result['stop'], line_dash="dash", line_color="#e55353", annotation_text="Stop Loss")
        
        fig.update_layout(template="plotly_dark", title=f"แผนภูมิราคาระยะสั้นสำหรับการเข้าทำกำไรหุ้น {search_ticker}", height=450)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("ไม่พบข้อมูลหุ้นตัวดังกล่าว กรุณาตรวจสอบการสะกดชื่อสัญลักษณ์อีกครั้งครับ")
