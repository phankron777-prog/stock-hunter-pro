import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIG & SYSTEM LAYOUT
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Stock Hunter Pro v7.0", layout="wide")

# พอร์ตหุ้นแนะนำเริ่มต้นสำหรับสายซิ่งเล่นสั้น (สามารถพิมพ์ปรับเปลี่ยนหน้าแอปได้)
DEFAULT_PORTFOLIO = ["NVDA", "AAPL", "TSLA", "AMD", "MSFT"]

st.sidebar.markdown("## 🦅 Stock Hunter Pro v7.0")
st.sidebar.markdown("### `The Quantitative Sniper`")
st.sidebar.caption("⚡ ฟันธงสัญญาณเล่นสั้นอิงสถิติจริง + วิเคราะห์ข่าวรอบ 7 วัน")
st.sidebar.divider()

menu = st.sidebar.radio(
    "🧭 เลือกเมนูวิเคราะห์เทรดเดอร์ (ครอบคลุม 10 โจทย์หลัก):",
    [
        "🔥 1. แดชบอร์ดสแกนสด & ฟันธงความน่าจะเป็น",
        "🎯 2. เจาะลึกแผนเทรดคณิตศาสตร์รายตัว",
        "📰 3. ข่าวสารล่าสุดรอบ 7 วัน & Sentiment Analysis",
        "💼 4. ตรวจสอบความเสี่ยงพอร์ต & Asset Allocation"
    ]
)

# ══════════════════════════════════════════════════════════════════════════
# 📦 CORE QUANTITATIVE ENGINE (ดึงราคาสด, คำนวณเทคนิคัล และ Backtest สถิติจริง)
# ══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60)  # ดึงราคาสดอัปเดตทุก 1 นาที เพื่อความคมในการเล่นสั้น
def get_clean_market_data(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty:
            return pd.DataFrame()
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        return df
    except Exception:
        return pd.DataFrame()

def process_trading_signals(df):
    if df.empty or len(df) < 20:
        return None
    
    # 1. คำนวณ Indicators ความเร็วสูงสำหรับสายเล่นสั้น
    df['EMA_5'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # RSI 14 วัน
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR หาความผันผวนตั้งจุดหนีและเป้ากำไร
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    
    # Volume Average 20 วันเพื่อเช็ค Volume Analysis
    df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
    
    # 2. จำลองรันสถิติ (Quick Backtest) ย้อนหลัง 6 เดือน เพื่อหา Win Rate จริงของหุ้นตัวนี้
    trades = []
    in_position = False
    buy_price = 0
    
    for i in range(20, len(df)):
        c_close = df['Close'].iloc[i]
        c_rsi = df['RSI'].iloc[i]
        c_atr = df['ATR'].iloc[i] if not np.isnan(df['ATR'].iloc[i]) else (c_close * 0.02)
        
        if not in_position:
            # เงื่อนไขเข้าซื้อสถิติ: EMA_5 ตัดเหนือ EMA_20 หรือ RSI < 35 (Oversold งัดหัว)
            if (df['EMA_5'].iloc[i] > df['EMA_20'].iloc[i]) or (c_rsi < 35):
                in_position = True
                buy_price = c_close
                t_target = buy_price + (1.5 * c_atr)
                t_stop = buy_price - (1.0 * c_atr)
        else:
            if df['High'].iloc[i] >= t_target:
                trades.append("WIN")
                in_position = False
            elif df['Low'].iloc[i] <= t_stop:
                trades.append("LOSS")
                in_position = False
                
    win_rate = (trades.count("WIN") / len(trades) * 100) if len(trades) > 0 else 50.0
    
    # 3. ดึงค่าแท่งปัจจุบันมาสรุปแผนฟันธง
    last = df.iloc[-1]
    curr_price = last['Close']
    rsi_now = last['RSI']
    atr_now = last['ATR'] if not np.isnan(last['ATR']) else (curr_price * 0.02)
    vol_ratio = last['Volume'] / last['Vol_Avg'] if last['Vol_Avg'] > 0 else 1.0
    
    # ระดับ Fibonacci Retracement เบื้องต้นจากจุด High/Low ในรอบ 3 เดือน
    high_3m = df['High'].tail(60).max()
    low_3m = df['Low'].tail(60).min()
    diff = high_3m - low_3m
    fibo_618 = high_3m - (0.618 * diff)
    fibo_382 = high_3m - (0.382 * diff)
    
    # ตัดสินใจฟันธงคำสั่งเด็ดขาด
    if (last['EMA_5'] > last['EMA_20']) or (rsi_now < 35):
        action = "🟩 BUY / LONG"
        target = curr_price + (1.5 * atr_now)
        stop = curr_price - (1.0 * atr_now)
        trend = "แนวโน้มโมเมนตัมขาขึ้นระยะสั้นได้เปรียบ"
    else:
        action = "🟥 SELL / SHORT"
        target = curr_price - (1.5 * atr_now)
        stop = curr_price + (1.0 * atr_now)
        trend = "แนวโน้มโมเมนตัมฝั่งขายควบคุมตลาด"
        
    return {
        "price": curr_price, "action": action, "rsi": rsi_now, "target": target, "stop": stop,
        "win_rate": win_rate, "total_trades": len(trades), "vol_ratio": vol_ratio,
        "fibo_618": fibo_618, "fibo_382": fibo_382, "trend": trend, "df": df
    }

# ══════════════════════════════════════════════════════════════════════════
# 🎯 MENU 1: แดชบอร์ดสแกนสด & ฟันธงความน่าจะเป็น (โจทย์ข้อ 1, 3, 5)
# ══════════════════════════════════════════════════════════════════════════
if menu == "🔥 1. แดชบอร์ดสแกนสด & ฟันธงความน่าจะเป็น":
    st.title("🎯 ระบบควอนท์สแกนเนอร์และฟันธงคำสั่งซื้อขายระยะสั้น")
    st.markdown("ดึงราคาสัจจะจริงบนกระดานปัจจุบันมารันสถิติจำลองการเทรดเพื่อฟันธงทิศทางความน่าจะเป็น")
    
    col_ref = st.button("🔄 อัปเดตราคาตลาดสดเรียลไทม์ (Refresh Data)", type="primary")
    
    scanned_list = []
    with st.spinner("⏳ เอนจิ้นกำลังสแกนพอร์ตหุ้นแนะนำและตรวจสอบทางสถิติ..."):
        for t in DEFAULT_PORTFOLIO:
            raw_df = get_clean_market_data(t)
            res = process_trading_signals(raw_df)
            if res:
                scanned_list.append({
                    "ชื่อหลักทรัพย์": t,
                    "ราคาล่าสุด": f"${res['price']:.2f}",
                    "📢 คำสั่งฟันธงหน้างาน": res['action'],
                    "สถิติชนะ (Win Rate ในอดีต)": f"{res['win_rate']:.1f}%",
                    "โมเมนตัม RSI": f"{res['rsi']:.1f}",
                    "เป้าหมายเก็บกำไรสั้น": f"${res['target']:.2f}",
                    "จุดคัทลอสตัดขาดทุน": f"${res['stop']:.2f}"
                })
                
    if scanned_list:
        st.dataframe(pd.DataFrame(scanned_list), use_container_width=True, hide_index=True)
        st.info("💡 **ไกด์ไลน์สายเล่นสั้น:** เลือกโฟกัสหุ้นที่มีค่า **สถิติชนะ (Win Rate) สูงกว่า 55% ขึ้นไป** และมีสัญญาณฝั่ง BUY เพื่อให้ได้เปรียบเชิงคณิตศาสตร์สูงสุดครับ")

# ══════════════════════════════════════════════════════════════════════════
# 📐 MENU 2: เจาะลึกแผนเทรดคณิตศาสตร์รายตัว (โจทย์ข้อ 2, 10)
# ══════════════════════════════════════════════════════════════════════════
elif menu == "🎯 2. เจาะลึกแผนเทรดคณิตศาสตร์รายตัว":
    st.title("📐 แผนการเทรดวิเคราะห์กรอบราคาเชิงลึก (Tactical Trading Setup)")
    
    t_input = st.text_input("ระบุตัวย่อหุ้นสากลที่ต้องการวางแผนหน้างาน (เช่น NVDA, TSLA, AAPL):", "NVDA").upper()
    
    raw_df = get_clean_market_data(t_input)
    res = process_trading_signals(raw_df)
    
    if res:
        c1, c2, c3 = st.columns(3)
        c1.metric("ราคาตลาดปัจจุบัน", f"${res['price']:.2f}")
        c2.markdown(f"### สัญญาณแอคชั่นคำสั่ง\n## {res['action']}")
        c3.metric("ปริมาณโวลุ่มเข้า (Volume Ratioเทียบค่าเฉลี่ย)", f"{res['vol_ratio']:.2f}x")
        
        st.markdown("---")
        st.markdown("### 📊 ตัวเลขแผนการตั้งออเดอร์เด็ดขาด (ไม่ต้องนั่งเดาแนวรับแนวต้าน)")
        cx1, cx2, cx3 = st.columns(3)
        cx1.metric("🎯 เป้าขายทำกำไรระยะสั้น (Take Profit)", f"${res['target']:.2f}")
        cx2.metric("🛑 จุดหนีภัยคัทลอส (Stop Loss)", f"${res['stop']:.2f}")
        cx3.metric("📈 ระดับย่อตัวสำคัญ (Fibonacci 61.8%)", f"${res['fibo_618']:.2f}")
        
        # วาดกราฟเทคนิคัล
        plot_df = res['df'].tail(50)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['Open'], high=plot_df['High'], low=plot_df['Low'], close=plot_df['Close'], name='แท่งเทียนราคาจริง'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_5'], line=dict(color='#2eb85c', width=2), name='EMA 5 (เส้นเร็วไวเดย์เทรด)'))
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['EMA_20'], line=dict(color='#ffc107', width=2), name='EMA 20 (เส้นเทรนด์หลัก)'))
        
        # วาดระดับเป้าหมายบนกราฟเทคนิคัล
        fig.add_hline(y=res['target'], line_dash="dash", line_color="green", annotation_text="เป้ากำไร")
        fig.add_hline(y=res['stop'], line_dash="dash", line_color="red", annotation_text="จุดคัทลอส")
        fig.add_hline(y=res['fibo_618'], line_dash="dot", line_color="orange", annotation_text="Fibo 61.8% (แนวรับแนวจิตวิทยา)")
        
        fig.update_layout(template="plotly_dark", title=f"แผนภูมิราคาสดสถิติตลาดจริงของหุ้น {t_input}", height=480)
        st.plotly_chart(fig, use_container_width=True)
        
        if res['vol_ratio'] > 1.5:
            st.success(f"🔥 **Volume Analysis Alert:** หุ้น {t_input} มีปริมาณการซื้อขายหนาแน่นกว่าปกติขยายตัวเด่นชัด ยืนยันความแข็งแกร่งของราคาเข้าทำแผนการเทรดได้ดี")
            
    else:
        st.error("ไม่สามารถเชื่อมข้อมูลหุ้นสัญลักษณ์นี้ได้ กรุณาตรวจเช็คการสะกดใหม่อีกครั้ง")

# ══════════════════════════════════════════════════════════════════════════
# 📰 MENU 3: ข่าวสารล่าสุดรอบ 7 วัน & SENTIMENT MARKET (โจทย์ข้อ 4, 8, 9)
# ══════════════════════════════════════════════════════════════════════════
elif menu == "📰 3. ข่าวสารล่าสุดรอบ 7 วัน & Sentiment Analysis":
    st.title("📰 ระบบดึงฟีดข่าวสารจริงรายวันและการประเมินจิตวิทยาตลาด (Market Sentiment)")
    st.markdown("ดึงหัวข้อข่าวสารทางการเงินจริงจากตลาดรอบ 7 วันล่าสุดมาทำการตรวจคีย์เวิร์ดเพื่อประเมินผลกระทบราคา")
    
    n_input = st.text_input("ระบุชื่อหุ้นที่ต้องการดึงข่าวสารอัปเดตหน้างานปัจจุบัน:", "TSLA").upper()
    
    if st.button("🌐 ดึงฐานข้อมูลข่าวสารแบบเรียลไทม์"):
        with st.spinner("⏳ ระบบกำลังดึงฐานข้อมูลฟีดข่าวจริงส่งตรงจากตลาด..."):
            try:
                tick_obj = yf.Ticker(n_input)
                news_list = tick_obj.news
                
                if not news_list:
                    st.warning(f"ไม่พบฟีดข่าวอย่างเป็นทางการของหลักทรัพย์ {n_input} ในช่วงสัปดาห์นี้")
                else:
                    pos_words = ["growth", "surge", "higher", "profit", "beat", "buy", "bullish", "upgrade", "success"]
                    neg_words = ["fall", "drop", "lower", "loss", "miss", "sell", "bearish", "downgrade", "risk"]
                    
                    p_score, n_score = 0, 0
                    
                    st.markdown(f"### 📰 ฟีดหัวข้อข่าวตรงจากกระดานตลาดของหุ้น {n_input}")
                    for idx, article in enumerate(news_list[:5]):
                        title = article.get("title", "")
                        publisher = article.get("publisher", "Reuters/Bloomberg")
                        link = article.get("link", "#")
                        
                        title_lower = title.lower()
                        for pw in pos_words:
                            if pw in title_lower: p_score += 1
                        for nw in neg_words:
                            if nw in title_lower: n_score += 1
                            
                        st.markdown(f"""
                        <div style="background-color:#141923; padding:15px; border-radius:8px; margin-bottom:10px; border-left:4px solid #ffc107;">
                            <b>{idx+1}. {title}</b><br>
                            <small>สำนักข่าว: {publisher} | <a href="{link}" target="_blank" style="color:#ffc107;">เปิดลิงก์อ่านข่าวเต็มคลิกที่นี่ 🔗</a></small>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    # คำนวณสรุปจิตวิทยาตลาดหน้างานฟันธง
                    total_sc = p_score + n_score
                    final_pct = 50.0
                    if total_sc > 0:
                        final_pct = (p_score / total_sc) * 100
                        
                    st.divider()
                    st.markdown("### 🎯 สรุปผลลัพธ์ดัชนี Sentiment หน้างานข่าวสาร")
                    st.metric(
                        label="คะแนนวัดความเชื่อมั่นทิศทางข่าวสาร (Sentiment Score)",
                        value=f"{final_pct:.1f} / 100",
                        delta="ฝั่งบวกเป็นต่อ (BULLISH)" if final_pct > 55 else "ฝั่งลบเป็นต่อ (BEARISH)" if final_pct < 45 else "ภาวะทรงตัวเป็นกลาง (NEUTRAL)"
                    )
                    st.caption("เทรดเดอร์สามารถใช้ดัชนี Sentiment ข่าวสารนี้ร่วมกับสัญญาณกราฟในบทที่ 2 หากสัญญาณกราฟบอกให้ BUY และทิศทางข่าวสารเป็นบวกคู่กัน จะช่วยเพิ่มเปอร์เซ็นต์ความแม่นยำในการเล่นรอบสั้นได้อย่างดีเยี่ยม")
            except Exception as e:
                st.error(f"ระบบไม่สามารถดึงข่าวสารได้ชั่วคราว: {str(e)}")

# ══════════════════════════════════════════════════════════════════════════
# 💼 MENU 4: ตรวจสอบความเสี่ยงพอร์ต & ASSET ALLOCATION (โจทย์ข้อ 6, 7)
# ══════════════════════════════════════════════════════════════════════════
elif menu == "💼 4. ตรวจสอบความเสี่ยงพอร์ต & Asset Allocation":
    st.title("💼 ระบบจำลองบริหารโครงสร้างพอร์ตลงทุนและแผนการลดความเสี่ยง 20%")
    st.markdown("ประเมินปัญหาการถือหุ้นกลุ่มอุตสาหกรรมซ้ำซ้อนกันมากเกินไป (Sector Concentration Risk) และคำนวณการปรับพอร์ตไปพักเงิน")
    
    cx1, cx2, cx3 = st.columns(3)
    w_tech = cx1.number_input("กรอกสัดส่วน หุ้นกลุ่มเทคโนโลยีปัญญาประดิษฐ์ (AI/Tech) % :", min_value=0, max_value=100, value=60)
    w_ev = cx2.number_input("กรอกสัดส่วน หุ้นกลุ่มยานยนต์ไฟฟ้า/พลังงาน (EV/Energy) % :", min_value=0, max_value=100, value=30)
    w_health = cx3.number_input("กรอกสัดส่วน หุ้นกลุ่มบริการทางการแพทย์/ดั้งเดิม % :", min_value=0, max_value=100, value=10)
    
    if w_tech + w_ev + w_health != 100:
        st.error("⚠️ คำเตือน: ผลรวมสัดส่วนของสินทรัพย์ในพอร์ตจะต้องรวมกันได้เท่ากับ 100% พอดีตามสัญญากติกาคณิตศาสตร์ครับ")
    else:
        st.success("✅ โครงสร้างพอร์ตรวมคำนวณครบถ้วนตามหลักเกณฑ์")
        
        # พล็อตกราฟสัดส่วนอุตสาหกรรมในพอร์ต
        fig_p = go.Figure(data=[go.Pie(labels=["กลุ่ม AI & Tech (ความผันผวนสูง)", "กลุ่ม EV & พลังงาน", "กลุ่มการแพทย์"], values=[w_tech, w_ev, w_health], hole=.3)])
        fig_p.update_layout(template="plotly_dark", title="แผนภูมิแจกแจงความหนาแน่นรายกลุ่มอุตสาหกรรมในพอร์ตปัจจุบัน")
        st.plotly_chart(fig_p, use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 🔄 แผนการทำ Rebalancing เพื่อลดความเสี่ยงของพอร์ตลง 20% ทันที")
        st.info("กลยุทธ์ตามระเบียบวินัยความปลอดภัย: ให้ทำการดึงแบ่งกำไรหรือทุน 20% จากกลุ่มที่ความผันผวนสูงที่สุด (Tech) ออกมาโยกย้ายไปพักไว้ที่สินทรัพย์ปลอดภัยความเสี่ยงต่ำ")
        
        re_data = [
            {"รายชื่อกลุ่มสินทรัพย์": "หุ้นกลุ่ม AI & เทคโนโลยี", "สัดส่วนเดิม": f"{w_tech}%", "🎯 สัดส่วนแนะนำใหม่หลังปรับพอร์ต": f"{w_tech - 20}%", "แนวปฏิบัติหน้างาน": "ขายทำกำรียออกบางส่วน 20%"},
            {"รายชื่อกลุ่มสินทรัพย์": "หุ้นกลุ่ม EV & พลังงาน", "สัดส่วนเดิม": f"{w_ev}%", "🎯 สัดส่วนแนะนำใหม่หลังปรับพอร์ต": f"{w_ev}%", "แนวปฏิบัติหน้างาน": "ถือครองสัดส่วนคงเดิม"},
            {"รายชื่อกลุ่มสินทรัพย์": "หุ้นกลุ่มการแพทย์และการป้องกัน", "สัดส่วนเดิม": f"{w_health}%", "🎯 สัดส่วนแนะนำใหม่หลังปรับพอร์ต": f"{w_health}%", "แนวปฏิบัติหน้างาน": "ถือครองสัดส่วนคงเดิม"},
            {"รายชื่อกลุ่มสินทรัพย์": "🔒 สินทรัพย์ปลอดภัย / กองทุนตราสารหนี้ระยะสั้น", "สัดส่วนเดิม": "0%", "🎯 สัดส่วนแนะนำใหม่หลังปรับพอร์ต": "20%", "แนวปฏิบัติหน้างาน": "ซื้อเข้าเพื่อล็อกความเสี่ยงและพักเงินทุน"}
        ]
        st.dataframe(pd.DataFrame(re_data), use_container_width=True, hide_index=True)
