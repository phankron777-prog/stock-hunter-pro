import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import urllib.request
import xml.etree.ElementTree as ET

# กำหนดหน้าจอหลักของแอป
st.set_page_config(page_title="Stock Hunter Super App v3.1", page_icon="🦅", layout="wide")

# ตกแต่งสไตล์ CSS ให้สวยงามสะดุดตาบนหน้าจอมือถือ
st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    .stButton>button { width: 100%; border-radius: 8px; background-color: #4F46E5; color: white; font-weight: bold; }
    div[data-testid="stMetricValue"] { font-size: 26px; font-weight: bold; color: #10B981; }
    .ai-box { padding: 15px; background-color: #1E1B4B; border-left: 5px solid #818CF8; border-radius: 8px; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

def get_safe_metric(info_dict, keys, default=0.0):
    for key in keys:
        if key in info_dict and info_dict[key] is not None:
            return info_dict[key]
    return default

# ฟังก์ชันดึงข่าวสารผ่าน Google News RSS Feed (เสถียรสูง ย้อนหลัง 7 วัน)
def fetch_stock_news_rss(symbol):
    try:
        url = f"https://news.google.com/rss/search?q={symbol}+stock+when:7d&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        news_items = []
        for item in root.findall('.//item')[:6]: # ดึงมา 6 ข่าวด่วนล่าสุด
            title = item.find('title').text
            link = item.find('link').text
            news_items.append({"title": title, "link": link})
        return news_items
    except:
        return []

# ฟังก์ชันนวัตกรรมใหม่: คำนวณอารมณ์ตลาดจากคีย์เวิร์ดข่าว 7 วันล่าสุด (Sentiment Analyzer)
def analyze_news_sentiment(news_list):
    if not news_list:
        return 0.0 # ถ้าไม่มีข่าว ให้ค่าน้ำหนักเป็นกลาง
    
    # คีย์เวิร์ดนำร่องในการประเมินเชิงบวกและเชิงลบของตลาดหุ้นโลก
    positive_words = ['bull', 'growth', 'surge', 'buy', 'beat', 'record', 'gain', 'unveil', 'ai', 'profit', 'rise', 'highest', 'upgrade']
    negative_words = ['bear', 'drop', 'fall', 'sink', 'loss', 'risk', 'investigate', 'lawsuit', 'decline', 'cut', 'slump', 'downgrade', 'warn']
    
    score = 0.0
    for item in news_list:
        title_lower = item['title'].lower()
        # เช็กคำบวก
        for word in positive_words:
            if word in title_lower: score += 0.2
        # เช็กคำลบ
        for word in negative_words:
            if word in title_lower: score -= 0.25
            
    # จำกัดขอบเขตคะแนนให้อยู่ระหว่าง -0.5 ถึง +0.5 เพื่อไม่ให้กราฟพยากรณ์เพี้ยนเกินจริง
    return max(min(score, 0.5), -0.5)

@st.cache_data(ttl=900)
def analyze_advanced_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y", interval="1d")
        if hist.empty: return None
            
        info = ticker.info
        close_prices = hist['Close']
        high_prices = hist['High']
        low_prices = hist['Low']
        volumes = hist['Volume']
        
        # คำนวณเทคนิคอลพื้นฐาน
        hist['SMA_20'] = close_prices.rolling(window=20).mean()
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / np.where(loss == 0, 1e-9, loss)
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        sup_30 = float(low_prices.tail(30).min())
        res_30 = float(high_prices.tail(30).max())
        
        # คำนวณ Fibonacci Retracement
        max_h = float(high_prices.max())
        min_l = float(low_prices.min())
        diff_fibo = max_h - min_l
        fibo_levels = {
            "ระดับย่อตัวสั้น (23.6%)": round(max_h - (diff_fibo * 0.236), 2),
            "ระดับแนวรับสำคัญ (38.2%)": round(max_h - (diff_fibo * 0.382), 2),
            "ระดับเปลี่ยนแนวโน้ม (50.0%)": round(max_h - (diff_fibo * 0.500), 2),
            "ระดับแนวรับทองคำ (61.8%)": round(max_h - (diff_fibo * 0.618), 2)
        }
        
        avg_vol_20 = volumes.rolling(window=20).mean().iloc[-1]
        last_vol = volumes.iloc[-1]
        vol_signal = "🔥 Volume เข้าหนาแน่นผิดปกติ" if last_vol > (avg_vol_20 * 1.2) else "💤 Volume ทรงตัวปกติ"
        
        rsi_now = hist['RSI'].iloc[-1]
        if rsi_now > 70: rsi_status = "🔴 OVERBOUGHT"
        elif rsi_now < 30: rsi_status = "🟢 OVERSOLD"
        else: rsi_status = "🟡 NEUTRAL"
            
        trend = "📈 ขาขึ้นเด่นชัด" if (close_prices.iloc[-1] > hist['SMA_20'].iloc[-1]) else "📉 พักฐาน/แนวโน้มขาลง"
        
        # โมเมนตัมเทคนิคอล (Slope 15 วัน)
        y = close_prices.tail(15).values
        x = np.arange(len(y))
        slope, _ = np.polyfit(x, y, 1)
        
        atr = (high_prices.tail(14) - low_prices.tail(14)).mean()
        
        return {
            "price": round(close_prices.iloc[-1], 2), "trend": trend, "rsi": round(rsi_now, 2), "rsi_status": rsi_status,
            "support": round(sup_30, 2), "resistance": round(res_30, 2), "fibo": fibo_levels, "vol_signal": vol_signal,
            "roe": round(get_safe_metric(info, ['returnOnEquity']) * 100, 2), "pe": round(get_safe_metric(info, ['trailingPE', 'forwardPE']), 2),
            "net_margin": round(get_safe_metric(info, ['profitMargins']) * 100, 2), "dividend_yield": round(get_safe_metric(info, ['dividendYield']) * 100, 2),
            "company_name": info.get('longName', symbol), "slope": slope, "atr": atr
        }
    except: return None

# --- หน้าจอหลักระบบควบคุม ---
st.title("🦅 STOCK HUNTER SUPER APP v3.1")
st.caption("ระบบคุมทัพกลยุทธ์ 10 มิติ อัปเกรดโมดูล AI พยากรณ์ราคาโดยดึงข่าวด่วนรอบ 7 วันมาประมวลผลร่วมเชิงสถิติ")

tab_ai, tab_fundamental, tab_technical, tab_portfolio = st.tabs([
    "🔮 AI แนะนำหุ้น & พยากรณ์ราคา", "📊 มิติพื้นฐาน & คัดหุ้น", "📡 มิติเทคนิคอล & แกะรอย", "🛡️ บริหารพอร์ต & ข่าวสาร"
])

# ================= TAB 1: ระบบทำนายอัจฉริยะ (แก้ไขให้แม่นยำขึ้นตามไอเดียเพื่อน) =================
with tab_ai:
    st.subheader("🎯 ระบบ AI ค้นหาพิกัดและประเมินทิศทางราคาอิงกระแสข่าวโลก")
    st.info("ระบบจะนำข่าวด่วนรอบ 7 วันของหุ้นตัวนั้นๆ มาสแกนหา Sentiment เพื่อนำมาถ่วงน้ำหนักร่วมกับโมเมนตัมกราฟ")
    
    c_ai1, c_ai2 = st.columns(2)
    with c_ai1:
        ai_stock = st.text_input("พิมพ์รหัสหุ้นที่ต้องการล่า (เช่น NVDA, AVGO, AAPL):", "NVDA").upper()
    with c_ai2:
        hold_days = st.selectbox("เลือกกรอบเวลาที่คาดว่าจะถือครอง (วัน):", [3, 5, 14, 30, 90])
        
    if st.button("🔮 ยิงเรดาร์ AI ประมวลผลร่วม (ข่าวล่าสุด + สถิติกราฟ)"):
        with st.spinner("🤖 AI กำลังอ่านข่าวด่วนรอบ 7 วันและคำนวณโมเมนตัมกราฟราคา..."):
            d = analyze_advanced_stock(ai_stock)
            news_data = fetch_stock_news_rss(ai_stock)
            
        if d:
            st.markdown(f"### 🏢 สรุปผลวิเคราะห์อัจฉริยะ: {d['company_name']}")
            
            # คำนวณ Sentiment Score จากข่าว 7 วัน
            sentiment_modifier = analyze_news_sentiment(news_data)
            
            # ปรับปรุงสูตรคำนวณแนวโน้มราคา โดยเอาค่า Sentiment ข่าวเข้าไปถ่วงน้ำหนักด้วย! (แก้ไขให้แม่นยำขึ้น)
            # ตัวคูณข่าวจะช่วยเพิ่มหรือลดความชันของสถิติตามอารมณ์ตลาดจริงเวลานั้น
            adjusted_slope = d["slope"] * (1.0 + sentiment_modifier)
            predicted_change = adjusted_slope * hold_days
            projected_price = round(d["price"] + predicted_change, 2)
            pct_move = round((predicted_change / d["price"]) * 100, 2)
            
            # แสดงสถานะอารมณ์ข่าวสารรอบ 7 วันให้เราเห็นหน้าจอเลย
            if sentiment_modifier > 0.1:
                st.success(f"📰 **AI Sentiment Analysis:** กระแสข่าวด่วนรอบ 7 วันค่อนข้างเป็น **'บวก' (+{round(sentiment_modifier,2)})** มีแรงหนุนผลักดันราคา")
            elif sentiment_modifier < -0.1:
                st.error(f"📰 **AI Sentiment Analysis:** กระแสข่าวด่วนรอบ 7 วันค่อนข้างเป็น **'ลบ' ({round(sentiment_modifier,2)})** ควรระวังแรงเทขาย")
            else:
                st.warning(f"📰 **AI Sentiment Analysis:** กระแสข่าวสารรอบ 7 วันอยู่ในเกณฑ์ **'ทรงตัว/ผสมผสาน' ({round(sentiment_modifier,2)})** ราคาจะวิ่งตามเทคนิคอลล้วนๆ")
            
            # คำแนะนำจุดยุทธศาสตร์ซื้อขาย (ATR Strategy)
            st.markdown("<div class='ai-box'>", unsafe_allow_html=True)
            st.markdown("#### ⚡ พิกัดจุดยุทธศาสตร์ซื้อขายหน้างาน (AI Entry & Target)")
            ideal_entry = round(d["price"] - (d["atr"] * 0.5), 2)
            target_profit = round(projected_price, 2)
            ai_stoploss = round(ideal_entry - (d["atr"] * 1.5), 2)
            
            st.write(f"🟢 **โซนตั้งรับซื้อที่ได้เปรียบ (Ideal Entry):** รอเข้าซื้อแถวๆ **${ideal_entry}**")
            st.write(f"🎯 **เป้าหมายคาดการณ์ (Take Profit):** ถือครอง **{hold_days} วัน** เป้าหมายราคาอยู่ที่ประมาณ **${target_profit}** (ขยับราวๆ **{pct_move}%**)")
            st.write(f"🚨 **จุดตัดขาดทุนจำกัดความเสี่ยง (AI Stop Loss):** หลุดแนว **${ai_stoploss}** ต้องยอมหมอบ")
            st.markdown("</div>", unsafe_allow_html=True)
            
            # สรุปข่าวด่วน 7 วันให้เห็นคาตาเพื่อใช้ตรวจสอบความแม่นยำของ AI
            if news_data:
                st.markdown("#### 📌 หัวข้อข่าวด่วนรอบ 7 วันที่ AI นำมาประมวลผลอ้างอิง:")
                for item in news_data:
                    st.markdown(f"• [{item['title']}]({item['link']})")
        else:
            st.error("ไม่สามารถดึงข้อมูลหุ้นตัวนี้ได้ กรุณาเช็กตัวย่อหุ้นอีกครั้งครับเพื่อน")

# ================= TAB 2: วิเคราะห์งบเปรียบเทียบหาหุ้นผู้ชนะ (ตามเดิม) =================
with tab_fundamental:
    st.subheader("⚔️ วิเคราะห์งบและเปรียบเทียบเชิงลึก (กลยุทธ์มิติที่ 1, 4, 9)")
    c1, c2, c3 = st.columns(3)
    with c1: s_a = st.text_input("ระบุหุ้น ตัวที่ A:", "AVGO").upper()
    with c2: s_b = st.text_input("ระบุหุ้น ตัวที่ B:", "NVDA").upper()
    with c3: s_c = st.text_input("ระบุหุ้น ตัวที่ C:", "PLTR").upper()
    
    if st.button("🚀 คำนวณและเปรียบเทียบค่าทางบัญชี"):
        res = []
        for sym in [s_a, s_b, s_c]:
            d = analyze_advanced_stock(sym)
            if d: res.append({
                "รหัสหุ้น": sym, "ROE (%)": d["roe"], "P/E Ratio": d["pe"], 
                "อัตรากำไรสุทธิ (%)": d["net_margin"], "ปันผล Yield (%)": d["dividend_yield"]
            })
        if res: st.dataframe(pd.DataFrame(res), use_container_width=True)

# ================= TAB 3: พิกัดราคาแนวรับแม่นยำและ Fibonacci (ตามเดิม) =================
with tab_technical:
    st.subheader("📐 พิกัดราคาแนวรับ/แนวต้าน & Fibonacci (กลยุทธ์มิติที่ 2, 3, 5, 10)")
    t_stock = st.text_input("ระบุรหัสหุ้นเพื่อเจาะลึกราคาเทคนิคอล:", "AVGO").upper()
    
    if st.button("📡 ยิงสัญญาณเรดาร์เทคนิคอล"):
        d = analyze_advanced_stock(t_stock)
        if d:
            st.write(f"### 🏢 {d['company_name']}")
            col_m1, col_m2 = st.columns(2)
            with col_m1: st.metric("ราคาปัจจุบัน", f"${d['price']}", d["trend"])
            with col_m2: st.metric("โมเมนตัม RSI (14)", f"{d['rsi']}", d["rsi_status"])
            
            st.warning(f"🧱 **แนวต้านกรอบปัจจุบัน:** ${d['resistance']} | 🛡️ **แนวรับโซนปลอดภัย:** ${d['support']}")
            st.markdown("#### 📈 ระดับย่อตัวสแกนด้วยเครื่องมือ Fibonacci Retracement")
            for k, v in d["fibo"].items():
                st.write(f"• **{k}** อยู่ที่พิกัดราคา: **${v}**")

# ================= TAB 4: ระบบจัดการเงินพอร์ตปรับเปลี่ยนเลขได้เอง (ตามเดิม) =================
with tab_portfolio:
    st.subheader("🛡️ ตรวจสุขภาพพอร์ต & วางแผนหน้าตัก (กลยุทธ์มิติที่ 6, 7)")
    st.markdown("#### ⚖️ โปรแกรมวางแผนกระจายเงินทุนพอร์ต (ปรับเปลี่ยนตัวเลขเงินทุนได้อิสระในแต่ละรอบ)")
    
    user_capital = st.number_input("ระบุจำนวนเงินทุนรวมในพอร์ตเวลานี้ ($):", min_value=1.0, value=2625.0, step=10.0)
    
    w_tech = st.slider("1. หุ้นกลุ่มเทคโนโลยี/AI เติบโตสูง (%)", 0, 100, 71)
    w_def = st.slider("2. หุ้นกลุ่มปลอดภัย/ปันผลดี (%)", 0, 100, 6)
    w_cash = st.slider("3. หุ้นซิ่ง/เงินสด/สินทรัพย์อื่นๆ (%)", 0, 100, 23)
    
    if st.button("⚖️ ประเมินน้ำหนักคำนวณสัดส่วนเงินจริง"):
        if (w_tech + w_def + w_cash) != 100:
            st.error("สัดส่วนรวมตอนนี้ยังไม่เท่ากับ 100% พอดีครับเพื่อน")
        else:
            amt_tech = round(user_capital * (w_tech / 100), 2)
            amt_def = round(user_capital * (w_def / 100), 2)
            amt_cash = round(user_capital * (w_cash / 100), 2)
            st.info(f"📊 **การจัดสรรเม็ดเงินจริงจากพอร์ตมูลค่า ${user_capital}:** \n\n"
                    f"• 💻 กลุ่มเทคโนโลยี/AI: **{w_tech}%** คิดเป็นเงิน **${amt_tech}** \n\n"
                    f"• 🛒 กลุ่มปลอดภัย/ปันผล: **{w_def}%** คิดเป็นเงิน **${amt_def}** \n\n"
                    f"• 💵 หุ้นซิ่ง/เงินสดสำรอง: **{w_cash}%** คิดเป็นเงิน **${amt_cash}**")
