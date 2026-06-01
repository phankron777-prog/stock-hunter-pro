import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import urllib.request
import xml.etree.ElementTree as ET

# กำหนดหน้าจอหลักของแอป
st.set_page_config(page_title="Stock Hunter Super App v3.0", page_icon="🦅", layout="wide")

# ตกแต่งสไตล์ CSS ให้สวยงามสะดุดตาและอ่านง่ายบนหน้าจอมือถือ
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

# ฟังก์ชันดึงข่าวสารผ่าน Google News RSS Feed (เสถียรสูง ไม่โดนบล็อกบนคลาวด์)
def fetch_stock_news_rss(symbol):
    try:
        url = f"https://news.google.com/rss/search?q={symbol}+stock+when:7d&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        news_items = []
        for item in root.findall('.//item')[:4]:
            title = item.find('title').text
            link = item.find('link').text
            news_items.append({"title": title, "link": link})
        return news_items
    except:
        return []

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
        
        # อัลกอริทึมทำนายราคา (Linear Regression หาโมเมนตัม 15 วันล่าสุด)
        y = close_prices.tail(15).values
        x = np.arange(len(y))
        slope, _ = np.polyfit(x, y, 1)
        
        # คำนวณความผันผวนจริงด้วยระบบ ATR แบบประยุกต์
        atr = (high_prices.tail(14) - low_prices.tail(14)).mean()
        
        return {
            "price": round(close_prices.iloc[-1], 2), "trend": trend, "rsi": round(rsi_now, 2), "rsi_status": rsi_status,
            "support": round(sup_30, 2), "resistance": round(res_30, 2), "fibo": fibo_levels, "vol_signal": vol_signal,
            "roe": round(get_safe_metric(info, ['returnOnEquity']) * 100, 2), "pe": round(get_safe_metric(info, ['trailingPE', 'forwardPE']), 2),
            "net_margin": round(get_safe_metric(info, ['profitMargins']) * 100, 2), "dividend_yield": round(get_safe_metric(info, ['dividendYield']) * 100, 2),
            "company_name": info.get('longName', symbol), "slope": slope, "atr": atr
        }
    except: return None

# --- ส่วนควบคุมหน้าจอหลัก ---
st.title("🦅 STOCK HUNTER SUPER APP v3.0")
st.caption("ระบบมอนิเตอร์กลยุทธ์ 10 มิติ พร้อมโมดูล AI แนะนำจุดเข้าซื้อและพยากรณ์ราคาเรียลไทม์ผ่านมือถือ 24 ชม.")

# เมนูสี่แท็บใหญ่ครบทุกมิติความต้องการ
tab_ai, tab_fundamental, tab_technical, tab_portfolio = st.tabs([
    "🔮 AI แนะนำหุ้น & พยากรณ์ราคา", "📊 มิติพื้นฐาน & คัดหุ้น", "📡 มิติเทคนิคอล & แกะรอย", "🛡️ บริหารพอร์ต & ข่าวสาร"
])

# ================= TAB 1: ระบบ AI ค้นหาพิกัดและประเมินทิศทางรายวัน =================
with tab_ai:
    st.subheader("🎯 ระบบ AI ค้นหาพิกัดและประเมินกรอบเวลาถือครองหุ้นทั่วโลก")
    st.info("ระบุรหัสหุ้นที่ต้องการให้ระบบประเมินจุดเข้าทำกำไร พร้อมเลือกจำนวนวันที่ต้องการถือครองพอร์ต")
    
    c_ai1, c_ai2 = st.columns(2)
    with c_ai1:
        ai_stock = st.text_input("พิมพ์รหัสหุ้นทั่วโลก (เช่น AVGO, NVDA, AAPL):", "AVGO").upper()
    with c_ai2:
        hold_days = st.selectbox("เลือกเป้าหมายกรอบเวลาในการถือครองหุ้น (วัน):", [3, 5, 14, 30, 90])
        
    if st.button("🔮 ยิงสัญญาณ AI วิเคราะห์แนวโน้มและจุดเข้าซื้อหน้างาน"):
        d = analyze_advanced_stock(ai_stock)
        if d:
            st.markdown(f"### 🏢 ผลประเมินสถานะหุ้น: {d['company_name']}")
            
            # คำนวณจุดเข้าซื้อไดนามิกตามความผันผวนจริง (ATR Strategy)
            st.markdown("<div class='ai-box'>", unsafe_allow_html=True)
            st.markdown("#### ⚡ คำแนะนำจุดยุทธศาสตร์ซื้อขาย (AI Entry & Target)")
            
            ideal_entry = round(d["price"] - (d["atr"] * 0.5), 2)
            target_profit = round(d["price"] + (d["atr"] * (hold_days ** 0.5)), 2)
            ai_stoploss = round(ideal_entry - (d["atr"] * 1.5), 2)
            
            st.write(f"🟢 **โซนจุดเข้าซื้อที่ได้เปรียบ (Ideal Entry):** แนะนำพิจารณาเข้าซื้อเมื่อราคาลงมาใกล้ระดับ **${ideal_entry}**")
            st.write(f"🎯 **เป้าหมายทำกำไรคาดการณ์ (Take Profit):** มีโอกาสขึ้นไปทดสอบแถว **${target_profit}** ภายในกรอบเวลาถือครองที่เลือก")
            st.write(f"🚨 **จุดตัดขาดทุนจำกัดความเสี่ยง (AI Stop Loss):** หากราคาปิดหลุดแนว **${ai_stoploss}** แนะนำคัทลอสปกป้องทุน")
            st.markdown("</div>", unsafe_allow_html=True)
            
            # จำลองพยากรณ์ทิศทางราคา
            st.markdown("#### 📈 ผลคาดการณ์ทิศทางราคาอัจฉริยะ")
            predicted_change = d["slope"] * hold_days
            projected_price = round(d["price"] + predicted_change, 2)
            pct_move = round((predicted_change / d["price"]) * 100, 2)
            
            if d["slope"] > 0:
                st.write("🟢 **ทิศทาง: มีแนวโน้มปรับตัว 'ขึ้นต่อ' (Bullish Momentum)**")
            else:
                st.write("🔴 **ทิศทาง: มีแนวโน้มปรับตัว 'พักฐาน/ลง' (Bearish Momentum)**")
                
            st.write(f"📊 สรุปประมาณการ: หากถือครองเป็นเวลา **{hold_days} วัน** ราคาคาดการณ์ทางสถิติจะอยู่ที่ประมาณ **${projected_price}** (ทิศทางเปลี่ยนแปลงราวๆ **{pct_move}%** จากราคานาทีนี้)")
            
            # ข้อแนะนำเสริมจากมูลค่าทางบัญชี
            st.write("---")
            st.markdown("#### 💡 การวิเคราะห์มูลค่าเพิ่มเติมระดับ AI")
            if d["pe"] > 0 and d["pe"] < 30:
                st.success(f"💎 หุ้นตัวนี้มี P/E อยู่ที่ {d['pe']} เท่า มูลค่าอยู่ในโซนไม่แพงเกินไป ได้เปรียบหากถือครองระยะกลาง")
            else:
                st.warning(f"🔥 หุ้นตัวนี้มี P/E อยู่ที่ {d['pe']} เท่า เป็นหุ้นเติบโตสูงราคาวิ่งรับอนาคตไปค่อนข้างมาก เน้นเก็งกำไรเข้าออกไวตามรอบเทคนิคอลจะปลอดภัยที่สุดครับเพื่อน")
        else:
            st.error("ไม่สามารถดึงข้อมูลหุ้นตัวนี้ได้ กรุณาตรวจสอบรหัสหุ้นอีกครั้งครับ")

# ================= TAB 2: วิเคราะห์งบเปรียบเทียบหาหุ้นผู้ชนะ =================
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

# ================= TAB 3: พิกัดราคาแนวรับแม่นยำและ Fibonacci =================
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

# ================= TAB 4: ข่าวสารเรียลไทม์ + ระบบจัดการเงินพอร์ตปรับเปลี่ยนเลขได้เอง =================
with tab_portfolio:
    st.subheader("🛡️ ตรวจสุขภาพพอร์ต & เช็กข่าวสาร Sentiment ล่าสุด (กลยุทธ์มิติที่ 6, 7, 8)")
    n_stock = st.text_input("ระบุหุ้นเพื่อเกาะติดข่าวด่วนผ่าน Google RSS Feed:", "NVDA").upper()
    if st.button("📰 ดึงข้อมูลความเคลื่อนไหวและมุมมองตลาด"):
        news = fetch_stock_news_rss(n_stock)
        if news:
            st.markdown("**ข่าวด่วนบนกระดานข่าวระดับโลกรอบ 7 วันล่าสุด:**")
            for item in news:
                st.markdown(f"📌 [{item['title']}]({item['link']})")
        else:
            st.warning("ไม่มีข่าวด่วนหรือระบบดึงข้อมูลขัดข้องชั่วคราว")
        
    st.markdown("---")
    st.markdown("#### ⚖️ โปรแกรมวางแผนกระจายเงินทุนพอร์ต (ปรับเปลี่ยนตัวเลขเงินทุนได้อิสระในแต่ละรอบ)")
    
    # ช่องให้เพื่อนคลิกกรอกตัวเลขเงินพอร์ตได้เองแบบอิสระในแต่ละรอบ
    user_capital = st.number_input("ระบุจำนวนเงินทุนรวมในพอร์ตเวลานี้ ($):", min_value=1.0, value=767.0, step=10.0)
    
    w_tech = st.slider("1. หุ้นกลุ่มเทคโนโลยี/AI ซิ่งเติบโตสูง (%)", 0, 100, 60)
    w_def = st.slider("2. หุ้นกลุ่มปลอดภัย/บริโภคพื้นฐาน ปันผลดี (%)", 0, 100, 30)
    w_cash = st.slider("3. สินทรัพย์เสี่ยงต่ำมาก/เงินสดคงเหลือ (%)", 0, 100, 10)
    
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
                    f"• 💵 เงินสดสำรองช้อนซื้อ: **{w_cash}%** คิดเป็นเงิน **${amt_cash}**")
            if w_tech > 50:
                st.warning("⚠️ **แจ้งเตือนความเสี่ยงสูง (Sector Concentration):** พอร์ตของเพื่อนพึ่งพาหุ้นกลุ่มเทคโนโลยีมากเกินกึ่งหนึ่งของเงินทุน แนะนำแบ่งกระสุนไปเติมในกลุ่มปลอดภัยเพิ่มขึ้นบ้างเพื่อความอุ่นใจตามวินัยครับ!")
            else:
                st.success("🟢 โครงสร้างกระจายตัวได้ดีและมีความปลอดภัยในระยะยาวแล้วครับเพื่อน!")
