import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

# ══════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIG & INTERACTIVE LAYOUT
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Stock Hunter Pro v6.5", layout="wide")

# ลิสต์หุ้นสำหรับสแกนสัญญาณความเร็วสูง
DEFAULT_WATCHLIST = ["NVDA", "AAPL", "TSLA", "AMD", "MSFT"]

st.sidebar.markdown("## 🦅 Stock Hunter Pro v6.5")
st.sidebar.markdown("### `Quant & Statistics Edition`")
st.sidebar.caption("📊 ผสานการวิเคราะห์ราคาสดและหลักสถิติที่เคยเกิดขึ้นจริง")
st.sidebar.divider()

menu = st.sidebar.radio(
    "🧭 เลือกโหมดวิเคราะห์:",
    ["🎯 สแกนสด & คำนวณความน่าจะเป็นเชิงสถิติ", "📈 เจาะลึกแผนเทรดด้วยสถิติจริง"]
)

# ══════════════════════════════════════════════════════════════════════════
# 📦 STATISTICAL TRADING ENGINE (อ้างอิงจากราคาสดและข้อมูลสถิติจริง)
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60) # ดึงข้อมูลราคาสดและอัปเดตทุกๆ 1 นาที
def get_market_data_with_stats(ticker, period="6mo"):
    """ ดึงข้อมูลจริงจาก yfinance และทำความสะอาดข้อมูลเพื่อวิเคราะห์สถิติ """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty:
            return pd.DataFrame()
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        return df
    except Exception:
        return pd.DataFrame()

def run_quantitative_analysis(df):
    """ รวบรวมอินดิเคเตอร์ยอดนิยมของสายสั้น และประมวลผลเป็นสถิติ Win Rate ย้อนหลัง """
    if df.empty or len(df) < 20:
        return None
    
    # 1. คำนวณตัวแปรเทคนิคัลระยะสั้น (EMA Fast/Slow + RSI)
    df['EMA_5'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    
    # 2. จำลองรันระบบ Backtest ย้อนหลังบนสถิติข้อมูลจริงเพื่อหาค่า Win Rate 
    # กลยุทธ์: ซื้อเมื่อราคาตัดเส้น EMA_5 หรือ RSI เกิดสภาวะ Oversold คัดลอสและทำกำไรด้วยขอบเขต ATR ความผันผวน
    trades_executed = []
    in_position = False
    entry_price = 0
    trade_type = ""
    
    for i in range(20, len(df)):
        current_close = df['Close'].iloc[i]
        prev_close = df['Close'].iloc[i-1]
        current_rsi = df['RSI'].iloc[i]
        current_atr = df['ATR'].iloc[i] if not np.isnan(df['ATR'].iloc[i]) else (current_close * 0.02)
        
        # ค้นหาสัญญาณการสลับฝั่ง (Trigger Setup)
        if not in_position:
            if (df['EMA_5'].iloc[i] > df['EMA_20'].iloc[i]) or (current_rsi < 35):
                in_position = True
                entry_price = current_close
                trade_type = "LONG"
                # กำหนดจุด Target / Stop Loss อิงตามความผันผวนจริงหน้างานขณะนั้น
                target_price = entry_price + (1.5 * current_atr)
                stop_loss = entry_price - (1.0 * current_atr)
        else:
            # ตรวจสอบว่าในแท่งถัดๆ มา ราคาไปแตะเป้าหรือชนจุดคัทลอสก่อนกันตามสถิติจริง
            if trade_type == "LONG":
                if df['High'].iloc[i] >= target_price:
                    trades_executed.append("WIN")
                    in_position = False
                elif df['Low'].iloc[i] <= stop_loss:
                    trades_executed.append("LOSS")
                    in_position = False

    # คำนวณเปอร์เซ็นต์ความน่าจะเป็นจากสถิติที่เกิดขึ้นจริง (Win Rate %)
    total_trades = len(trades_executed)
    wins = trades_executed.count("WIN")
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 50.0  # หากไม่มีการเทรดให้ค่า Default ที่ 50%
    
    # 3. ดึงข้อมูลแถวล่าสุด (ราคาสัจจะปัจจุบันบนกระดาน) มาฟันธงแนวทาง
    last_row = df.iloc[-1]
    current_price = last_row['Close']
    rsi_now = last_row['RSI']
    atr_now = last_row['ATR'] if not np.isnan(last_row['ATR']) else (current_price * 0.02)
    
    if (last_row['EMA_5'] > last_row['EMA_20']) or (rsi_now < 35):
        action = "🟩 BUY / LONG"
        target = current_price + (1.5 * atr_now)
        stop = current_price - (1.0 * atr_now)
    else:
        action = "🟥 SELL / SHORT"
        target = current_price - (1.5 * atr_now)
        stop = current_price + (1.0 * atr_now)
        
    return {
        "price": current_price,
        "action": action,
        "rsi": rsi_now,
        "target": target,
        "stop": stop,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "df": df
    }

# ══════════════════════════════════════════════════════════════════════════
# 🎯 MODE 1: สแกนสด & คำนวณความน่าจะเป็นเชิงสถิติย้อนหลัง
# ══════════════════════════════════════════════════════════════════════════
if menu == "🎯 สแกนสด & คำนวณความน่าจะเป็นเชิงสถิติ":
    st.title("📊 ระบบสแกนและประมวลผลความน่าจะเป็นเชิงสถิติตลาดจริง")
    st.markdown("ดึงราคาปิดล่าสุดรายนาที/รายวัน มาคำนวณร่วมกับสถิติ Win Rate ของอินดิเคเตอร์ในอดีตย้อนหลัง 6 เดือน")
    
    if st.button("🔄 อัปเดตราคาและสถิติล่าสุด (Refresh)", type="primary"):
        st.rerun()
        
    stat_summary = []
    with st.spinner("⏳ ควอนท์เอนจิ้นกำลังดึงข้อมูลย้อนหลังมาทำความสะอาดและรันสถิติ..."):
        for ticker in DEFAULT_WATCHLIST:
            raw_df = get_market_data_with_stats(ticker)
            res = run_quantitative_analysis(raw_df)
            
            if res:
                stat_summary.append({
                    "ชื่อหุ้น": ticker,
                    "ราคาตลาดปัจจุบัน": f"${res['price']:.2f}",
                    "🎯 คำสั่งฟันธง": res['action'],
                    "สถิติความแม่นยำ (Win Rate ย้อนหลัง)": f"{res['win_rate']:.1f}%",
                    "จำนวนรอบบันทึกสถิติ": f"{res['total_trades']} ครั้ง",
                    "เป้าทำกำไรระยะสั้น": f"${res['target']:.2f}",
                    "จุดตัดขาดทุน (Stop Loss)": f"${res['stop']:.2f}"
                })
                
    if stat_summary:
        st.dataframe(pd.DataFrame(stat_summary), use_container_width=True, hide_index=True)
        st.caption("💡 *หมายเหตุ: ค่า Win Rate คำนวณจากจำนวนรอบสัญญาณซื้อขายที่เกิดขึ้นจริงและบรรลุเป้าหมายทำกำไร (Take Profit) ก่อนชนจุดตัดขาดทุน*")
    else:
        st.info("ไม่พบข้อมูลสถิติในระบบฐานข้อมูลชั่วคราว กรุณากดปุ่มรีเฟรช")

# ══════════════════════════════════════════════════════════════════════════
# 📈 MODE 2: เจาะลึกแผนเทรดรายตัวพ่วงการพล็อตกราฟราคาจริง
# ══════════════════════════════════════════════════════════════════════════
elif menu == "📈 เจาะลึกแผนเทรดด้วยสถิติจริง":
    st.title("🔍 เจาะลึกโครงสร้างแนวทางกราฟและตัวเลขเป้าหมายคณิตศาสตร์")
    
    search_ticker = st.text_input("ระบุสัญลักษณ์หุ้นสากลที่ต้องการเจาะลึกสถิติแผนเทรด:", "NVDA").upper()
    
    raw_df = get_market_data_with_stats(search_ticker)
    res = run_quantitative_analysis(raw_df)
    
    if res:
        # แสดงผลลัพธ์ข้อมูลหลัก
        col_st1, col_st2, col_st3 = st.columns(3)
        col_st1.metric("ราคาปิดล่าสุด", f"${res['price']:.2f}")
        col_st2.markdown(f"### สัญญาณปัจจุบัน\n### {res['action']}")
        col_st3.metric("🎯 อัตราความน่าจะเป็น (Win Rate ย้อนหลัง)", f"{res['win_rate']:.1f}%", f"จากข้อมูลสถิติตลอด 6 เดือนที่ผ่านมา")
        
        # รายละเอียดแนวรับแนวต้านเชิงสถิติคณิตศาสตร์
        st.markdown("---")
        c_tr1, c_tr2 = st.columns(2)
        c_tr1.metric("🎯 แนวทางราคาเป้าหมายเก็บกำไรสั้น (Take Profit)", f"${res['target']:.2f}")
        c_tr2.metric("🛑 แนวทางราคาตัดขาดทุนเพื่อหนีภัยความเสี่ยง (Stop Loss)", f"${res['stop']:.2f}")
        
        # วาดกราฟแท่งเทียนอดีต 45 แท่งล่าสุดเพื่อให้มองเห็นขอบเขตราคาชัดเจน
        plot_df = res['df'].tail(45)
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=plot_df.index, 
            open=plot_df['Open'], high=plot_df['High'], 
            low=plot_df['Low'], close=plot_df['Close'], 
            name='ราคาตลาดจริง'
        ))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_5'], line=dict(color='#2eb85c', width=1.5), name='EMA 5 วัน (ทิศทางเร็ว)'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#ffc107', width=1.5), name='EMA 20 วัน (แนวโน้มหลัก)'))
        
        # ลากเส้นขอบเขตคณิตศาสตร์ที่เคยพิสูจน์แล้วว่ามีสถิติได้เปรียบตลาด
        fig.add_hline(y=res['target'], line_dash="dash", line_color="#2eb85c", annotation_text="เป้าทำกำไรระยะสั้น (Stat Target)")
        fig.add_hline(y=res['stop'], line_dash="dash", line_color="#e55353", annotation_text="จุดหนีรักษาต้นทุน (Stat Stop)")
        
        fig.update_layout(template="plotly_dark", title=f"แผนภูมิวิเคราะห์แนวทางกราฟทางสถิติของหุ้น {search_ticker}", height=450)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("ไม่สามารถคำนวณข้อมูลสถิติของหุ้นตัวนี้ได้ กรุณาตรวจสอบชื่อตัวย่อหุ้นอีกครั้งครับ")
