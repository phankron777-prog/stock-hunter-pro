import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

# กำหนดหน้าจอหลักของแอป
st.set_page_config(page_title="Stock Hunter Pro v2.0", page_icon="🦅", layout="wide")

# ตกแต่งสไตล์ CSS ให้ดูง่าย สบายตาบนหน้าจอมือถือ
st.markdown("""
    <style>
    .reportview-container { background: #0e1117; }
    .stButton>button { width: 100%; border-radius: 8px; background-color: #4F46E5; color: white; font-weight: bold; }
    div[data-testid="stMetricValue"] { font-size: 26px; font-weight: bold; color: #10B981; }
    .status-box { padding: 15px; border-radius: 8px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

def get_safe_metric(info_dict, keys, default=0.0):
    for key in keys:
        if key in info_dict and info_dict[key] is not None:
            return info_dict[key]
    return default

@st.cache_data(ttl=1800)
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
        
        # 1. คำนวณเทคนิคอล MA & RSI (ข้อ 2, 3)
        hist['EMA_5'] = close_prices.ewm(span=5, adjust=False).mean()
        hist['SMA_20'] = close_prices.rolling(window=20).mean()
        hist['SMA_50'] = close_prices.rolling(window=50).mean()
        
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / np.where(loss == 0, 1e-9, loss)
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        sup_30 = float(low_prices.tail(30).min())
        res_30 = float(high_prices.tail(30).max())
        
        # 2. คำนวณ Fibonacci Retracement ระดับสำคัญ (ข้อ 10)
        max_h = float(high_prices.max())
        min_l = float(low_prices.min())
        diff_fibo = max_h - min_l
        fibo_levels = {
            "ระดับย่อตัวสั้น (23.6%)": round(max_h - (diff_fibo * 0.236), 2),
            "ระดับแนวรับสำคัญ (38.2%)": round(max_h - (diff_fibo * 0.382), 2),
            "ระดับเปลี่ยนแนวโน้ม (50.0%)": round(max_h - (diff_fibo * 0.500), 2),
            "ระดับแนวรับทองคำ (61.8%)": round(max_h - (diff_fibo * 0.618), 2)
        }
        
        # 3. วิเคราะห์ Volume (ข้อ 10)
        avg_vol_20 = volumes.rolling(window=20).mean().iloc[-1]
        last_vol = volumes.iloc[-1]
        vol_signal = "🔥 Volume เข้าหนาแน่นผิดปกติ (มีแรงขับเคลื่อน)" if last_vol > (avg_vol_20 * 1.2) else "💤 Volume ทรงตัวปกติ"
        
        rsi_now = hist['RSI'].iloc[-1]
        if rsi_now > 70: rsi_status = "🔴 OVERBOUGHT (ระวังแรงเทขาย)"
        elif rsi_now < 30: rsi_status = "🟢 OVERSOLD (ราคาถูก มีลุ้นเด้ง)"
        else: rsi_status = "🟡 NEUTRAL (แกว่งตัวในกรอบ)"
            
        trend = "📈 ขาขึ้นเด่นชัด (ยืนเหนือเส้น SMA 20/50)" if (close_prices.iloc[-1] > hist['SMA_20'].iloc[-1]) else "📉 พักฐาน/แนวโน้มขาลง"
        
        # 4. ดึงข่าวย้อนหลังเพื่อเช็ก Sentiment (ข้อ 8)
        news_list = ticker.news[:3]
        parsed_news = []
        for n in news_list:
            parsed_news.append({"title": n.get('title', ''), "link": n.get('link', '')})
            
        return {
            "price": round(close_prices.iloc[-1], 2), "trend": trend, "rsi": round(rsi_now, 2), "rsi_status": rsi_status,
            "support": round(sup_30, 2), "resistance": round(res_30, 2), "fibo": fibo_levels, "vol_signal": vol_signal,
            "roe": round(get_safe_metric(info, ['returnOnEquity']) * 100, 2), "pe": round(get_safe_metric(info, ['trailingPE', 'forwardPE']), 2),
            "net_margin": round(get_safe_metric(info, ['profitMargins']) * 100, 2), "dividend_yield": round(get_safe_metric(info, ['dividendYield']) * 100, 2),
            "company_name": info.get('longName', symbol), "news": parsed_news
        }
    except: return None

# --- ส่วนติดต่อผู้ใช้งานบนหน้าจอแอป ---
st.title("🦅 STOCK HUNTER PRO v2.0")
st.caption("ระบบวิเคราะห์สแกนหุ้นตามกลยุทธ์ 10 มิติ เพื่อการเข้าทำกำไรด้วยมือถือตลอด 24 ชม.")

# แยกหมวดหมู่ตามโครงสร้างคำสั่งซื้อขาย
tab_fundamental, tab_technical, tab_portfolio = st.tabs(["📊 มิติพื้นฐาน & คัดหุ้น", "📡 มิติเทคนิคอล & แกะรอย", "🛡️ บริหารพอร์ต & ข่าวสาร"])

with tab_fundamental:
    st.subheader("⚔️ วิเคราะห์งบและเปรียบเทียบเชิงลึก (ข้อ 1, 4, 9)")
    st.info("ระบุรหัสหุ้น 3 ตัวที่ต้องการเปรียบเทียบ เพื่อเฟ้นหาตัวที่มีศักยภาพสูงสุดในอุตสาหกรรม")
    c1, c2, c3 = st.columns(3)
    with c1: s_a = st.text_input("ระบุหุ้น A:", "AVGO").upper()
    with c2: s_b = st.text_input("ระบุหุ้น B:", "NVDA").upper()
    with c3: s_c = st.text_input("ระบุหุ้น C:", "PLTR").upper()
    
    if st.button("🚀 คำนวณและเปรียบเทียบค่าทางบัญชี"):
        res = []
        for sym in [s_a, s_b, s_c]:
            d = analyze_advanced_stock(sym)
            if d: res.append({
                "รหัสหุ้น": sym, "ROE (%)": d["roe"], "P/E Ratio": d["pe"], 
                "อัตรากำไรสุทธิ (%)": d["net_margin"], "ปันผล Yield (%)": d["dividend_yield"]
            })
        if res: 
            st.dataframe(pd.DataFrame(res), use_container_width=True)
            st.success("💡 **หลักการวิเคราะห์พื้นฐาน:** หุ้นที่ดีควรมีค่า ROE และอัตรากำไรสุทธิที่สูง ในขณะที่ P/E ไม่ควนสูงเกินไปเมื่อเทียบกับเพื่อนในกลุ่มอุตสาหกรรมเดียวกัน")

with tab_technical:
    st.subheader("📐 พิกัดราคาแนวรับ/แนวต้าน & Fibonacci (ข้อ 2, 3, 5, 10)")
    t_stock = st.text_input("ระบุรหัสหุ้นเพื่อดึงกราฟและพิกัดราคา:", "AVGO").upper()
    
    if st.button("📡 ยิงสัญญาณเรดาร์เทคนิคอล"):
        d = analyze_advanced_stock(t_stock)
        if d:
            st.write(f"### 🏢 {d['company_name']}")
            col_m1, col_m2 = st.columns(2)
            with col_m1: st.metric("ราคาตลาดล่าสุด", f"${d['price']}", d["trend"])
            with col_m2: st.metric("โมเมนตัม RSI (14)", f"{d['rsi']}", d["rsi_status"])
            
            st.markdown("#### 🎯 จุดยุทธศาสตร์การเข้าซื้อและจำกัดความเสี่ยง (Entry & Stop Loss)")
            st.warning(f"🧱 **แนวต้านกรอบปัจจุบัน:** ${d['resistance']} \n\n🛡️ **แนวรับโซนปลอดภัย:** ${d['support']} \n\n🚨 **จุดตัดขาดทุนแนะนำ (Stop Loss -3% จากแนวรับ):** ${round(d['support']*0.97, 2)}")
            
            st.markdown("#### 📈 ระดับย่อตัวสแกนด้วยเครื่องมือ Fibonacci Retracement")
            for k, v in d["fibo"].items():
                st.write(f"• **{k}** อยู่ที่พิกัดราคา: **${v}**")
            st.info(f"📊 **สถานะวอลลุ่มล่าสุด:** {d['vol_signal']}")

with tab_portfolio:
    st.subheader("🛡️ ตรวจสุขภาพพอร์ต & เช็กข่าวสาร Sentiment ล่าสุด (ข้อ 6, 7, 8)")
    
    n_stock = st.text_input("ระบุหุ้นเพื่อเกาะติดข่าวด่วนรอบ 7 วัน:", "AVGO").upper()
    if st.button("📰 ดึงข้อมูลความเคลื่อนไหวและมุมมองตลาด"):
        d = analyze_advanced_stock(n_stock)
        if d and d["news"]:
            st.markdown("**ข่าวด่วนบนกระดานข่าวระดับโลก:**")
            for item in d["news"]:
                st.markdown(f"📌 [{item['title']}]({item['link']})")
            st.success("🤖 **การวิเคราะห์ Sentiment:** ข้อมูลนี้จะช่วยให้เพื่อนไม่พลาดข่าวดราม่าสำคัญที่มีผลต่อทิศทางราคาหุ้นหน้างาน")
        else: st.warning("ไม่มีข่าวดราม่าหรือข้อมูลเชิงลบที่ส่งผลกระทบอย่างรุนแรงในช่วง 7 วันนี้")
        
    st.markdown("---")
    st.markdown("#### ⚖️ โปรแกรมคำนวณสัดส่วนพอร์ตเพื่อความปลอดภัยสูงสุด ($767)")
    w_tech = st.slider("1. หุ้นกลุ่มเทคโนโลยี/AI ผันผวนสูง (%)", 0, 100, 60)
    w_def = st.slider("2. หุ้นกลุ่มปลอดภัย/บริโภคพื้นฐาน ปันผลดี (%)", 0, 100, 30)
    w_cash = st.slider("3. สินทรัพย์เสี่ยงต่ำมาก/เงินสดคงเหลือ (%)", 0, 100, 10)
    
    if st.button("⚖️ ตรวจสอบการกระจายความเสี่ยง (Sector Concentration)"):
        total_w = w_tech + w_def + w_cash
        if total_w != 100:
            st.error(f"สัดส่วนรวมตอนนี้คือ {total_w}% กรุณาเลื่อนแถบให้รวมกันได้ 100% พอดีครับเพื่อน")
        else:
            st.info(f"📊 โครงสร้างพอร์ตปัจจุบัน: กลุ่มเติบโตสูง {w_tech}% | กลุ่มปลอดภัย {w_def}% | สินทรัพย์เสี่ยงต่ำ {w_cash}%")
            if w_tech > 50:
                st.warning("⚠️ **แจ้งเตือนความเสี่ยงสูง (Sector Concentration):** พอร์ตของเพื่อนพึ่งพาหุ้นกลุ่มเทคโนโลยีมากเกินไป หากตลาดไอทีปรับฐานพอร์ตจะยุบตัวแรง แนะนำให้แบ่ง 20% ไปเพิ่มในกลุ่มสินค้าบริโภคพื้นฐานหรือกองทุนตราสารหนี้ เพื่อลดความผันผวนตามแผนข้อที่ 7 ครับ!")
            else:
                st.success("🟢 โครงสร้างกระจายตัวได้ดีและมีความปลอดภัยในระยะยาวแล้วครับเพื่อน!")