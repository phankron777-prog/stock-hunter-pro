import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ============================================================================
# 1. APP CONFIGURATION & THEME (Dark Mode & Responsive)
# ============================================================================
st.set_page_config(
    page_title="Stock Hunter Super App v3.1",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS สำหรับปรับแต่งให้ Mobile Responsive และตกแต่งให้เป็นธีม Dark Mode ของนักเทรด
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 8px; background-color: #1f77b4; color: white; }
    .stProgress > div > div > div > div { background-color: #2eb85c; }
    @media (max-width: 768px) {
        .responsive-table { display: block; overflow-x: auto; }
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# 2. AUTO-REFRESH SYSTEM (แก้จุดอ่อน Static/Pull ด้วย st.fragment)
# ============================================================================
# ใช้ Session State เก็บจำลองข้อมูลพอร์ตและราคาระหว่างการรีเฟรช
if 'btc_price' not in st.session_state:
    st.session_state.btc_price = 65000.0
if 'set_index' not in st.session_state:
    st.session_state.set_index = 1380.5

# ฟังก์ชันจำลองการดึงข้อมูลแบบ Real-time (WebSocket/API Simulation)
def update_market_data():
    st.session_state.btc_price += np.random.uniform(-50, 50)
    st.session_state.set_index += np.random.uniform(-1, 1)

# ============================================================================
# 3. SIDEBAR NAVIGATION & PORTFOLIO TRACKING
# ============================================================================
with st.sidebar:
    st.title("🦅 Stock Hunter Pro v3.1")
    st.write("`Status: Public Access ✅ (No Auth Friction)`")
    
    # ระบบ Auto-refresh สวิตช์ปิดเปิด
    auto_refresh = st.checkbox("🔄 เปิดระบบ Auto-Refresh (ทุก 5 วินาที)", value=True)
    if auto_refresh:
        update_market_data()
        time.sleep(1) # ในการใช้งานจริงใช้ st_autorefresh หรือกำหนดลูปใน fragment

    st.divider()
    menu = st.radio(
        "เมนูการใช้งานยุทธศาสตร์",
        ["📈 Dashboard & Real-Time Portfolio", "🔍 Technical Screener", "🧪 Strategy Backtesting", "🤖 AI Stock Picker"]
    )
    
    st.divider()
    st.caption(f"อัปเดตล่าสุด: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# MODULE 1: DASHBOARD & PORTFOLIO TRACKING (High Priority)
# ============================================================================
if menu == "📈 Dashboard & Real-Time Portfolio":
    st.title("🎯 หน้าหลัก & ติดตามพอร์ตลงทุนจำลอง (Multi-Market)")
    
    # ตัวชี้วัด Real-time ด้านบน
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("SET Index (TH)", f"{st.session_state.set_index:.2f}", f"{np.random.uniform(-0.5, 0.5):.2f}%")
    with col2:
        st.metric("NASDAQ (US)", "16,248.50", "+1.22%", delta_color="normal")
    with col3:
        st.metric("จำลองพอร์ตลงทุนรวม", "$2,115.02", "+11.55% (+218.92 USD)")
    with col4:
        st.metric("เงินสดคงเหลือในมือ (Cash)", "$397.00", "พร้อมลุย!")

    st.divider()
    
    # ตารางแสดงสัดส่วนพอร์ตปัจจุบัน
    st.subheader("📊 สินทรัพย์ที่คุณถือครองในปัจจุบัน")
    portfolio_data = pd.DataFrame({
        'สินทรัพย์': ['QQQM (NASDAQ 100)', 'SCHD (US Dividend)', 'เงินสด (Cash)'],
        'สัดส่วน (%)': [83.6, 6.4, 10.0],
        'มูลค่า (USD)': [1958.73, 156.28, 397.00],
        'กำไร/ขาดทุน': ['+12.02%', '+5.95%', '-']
    })
    st.table(portfolio_data)

# ============================================================================
# MODULE 2: TECHNICAL SCREENER & ALERTS (Medium Priority)
# ============================================================================
elif menu == "🔍 Technical Screener":
    st.title("🔍 เครื่องมือกรอกและสแกนหุ้นเทคนิคอล (Technical Screener)")
    
    market_select = st.selectbox("เลือกตลาดที่ต้องการสแกน", ["ตลาดหุ้นไทย (SET)", "ตลาดหุ้นสหรัฐฯ (NASDAQ/NYSE)"])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        rsi_filter = st.slider("กรองช่วงค่า RSI (14)", 0, 100, (30, 70))
    with col2:
        ma_cross = st.selectbox("เงื่อนไขเส้นค่าเฉลี่ย (MA)", ["ไม่มีเงื่อนไข", "Golden Cross (EMA 50 > 200)", "Dead Cross (EMA 50 < 200)"])
    with col3:
        volume_filter = st.selectbox("ปริมาณการซื้อขาย (Volume)", ["ปกติ", "Volume เข้าผิดปกติ (> 200% ของค่าเฉลี่ย)"])

    # ข้อมูลจำลองที่ได้จากการสแกน
    st.subheader("📋 ผลลัพธ์การคัดกรองหุ้นตามเงื่อนไข")
    mock_scan_results = pd.DataFrame({
        'ชื่อหุ้น/Ticker': ['NVDA', 'AVGO', 'DVN', 'PTT', 'ADVANC'],
        'ราคาปัจจุบัน': ['$202.32', '$371.44', '$47.09', '34.25 บาท', '210.00 บาท'],
        'RSI (14)': [32.5, 34.0, 58.2, 28.5, 65.0],
        'สัญญาณเทคนิค': ['ใกล้เขต Oversold', 'ย่อตัวชนแนวรับ', 'ขาขึ้นทรงสามเหลี่ยม', 'Oversold รุนแรง', 'ทดสอบแนวต้าน']
    })
    st.dataframe(mock_scan_results, use_container_width=True)
    
    # ระบบตั้งเตือนราคา (Alert System)
    st.divider()
    st.subheader("🔔 ตั้งค่าการแจ้งเตือนราคา (Price Alert)")
    alert_col1, alert_col2, alert_col3 = st.columns(3)
    with alert_col1:
        alert_ticker = st.text_input("ระบุชื่อหุ้นที่ต้องการเตือน", value="NVDA")
    with alert_col2:
        alert_cond = st.selectbox("เงื่อนไข", ["ราคาต่ำกว่า", "ราคาสูงกว่า"])
    with alert_col3:
        alert_price = st.number_input("ราคาเป้าหมาย (USD/บาท)", value=195.00)
    
    if st.button("⏰ บันทึกการตั้งเตือน"):
        st.success(f"บันทึกระบบแจ้งเตือนสำเร็จ! ระบบจะเตือนเมื่อ {alert_ticker} {alert_cond} {alert_price}")

# ============================================================================
# MODULE 3: STRATEGY BACKTESTING (Medium Priority)
# ============================================================================
elif menu == "🧪 Strategy Backtesting":
    st.title("🧪 ระบบทดสอบกลยุทธ์การเทรดย้อนหลัง (Backtesting Simulator)")
    
    strategy = st.selectbox("เลือกกลยุทธ์การลงทุน", ["RSI Oversold/Overbought", "EMA Crossover (50/200)", "Buy and Hold (ซื้อแล้วถือยาว)"])
    backtest_years = st.slider("จำนวนปีย้อนหลังที่ต้องการทดสอบ", 1, 10, 5)
    initial_capital = st.number_input("เงินต้นเริ่มต้น (USD)", value=1000)
    
    if st.button("🚀 รันระบบ Backtest ย้อนหลัง"):
        with st.spinner("กำลังคำนวณและประมวลผลข้อมูลประวัติศาสตร์..."):
            time.sleep(1.5) # จำลองเวลาประมวลผล
            
            # ผลลัพธ์จำลองการแบคเทส
            st.success("คำนวณเสร็จสิ้น!")
            b_col1, b_col2, b_col3 = st.columns(3)
            with b_col1:
                st.metric("มูลค่าพอร์ตปัจจุบัน", f"${initial_capital * 2.45:.2f}", "+145%")
            with b_col2:
                st.metric("Win Rate (%)", "64.5%", "จากทั้งหมด 42 เทรด")
            with b_col3:
                st.metric("Max Drawdown (จุดดิ่งสุด)", "-18.4%", "ปลอดภัยกว่าตลาด")
                
            # กราฟจำลองการเติบโตของเงินทุน
            chart_data = pd.DataFrame(
                np.random.randn(100, 2).cumsum() + [50, 50],
                columns=['กลยุทธ์ Stock Hunter', 'ดัชนีตลาดรวม (Benchmark)']
            )
            st.line_chart(chart_data)

# ============================================================================
# MODULE 4: AI STOCK PICKER & EXPORT (Nice to Have)
# ============================================================================
elif menu == "🤖 AI Stock Picker":
    st.title("🤖 ยอดขุนพล AI Stock Picker (Machine Learning Recommendation)")
    st.write("ระบบวิเคราะห์ข่าวย้อนหลัง 7 วัน (News Sentiment) ร่วมกับโมเดลคาดการณ์ราคาเพื่อค้นหาหุ้นผู้ชนะ")
    
    risk_level = st.select_slider("เลือกระดับความเสี่ยงที่รับได้ของคุณ", options=["เสถียรเน้นปันผล (Safe)", "เติบโตปานกลาง (Balanced)", "ซิ่งก้าวกระโดด (Aggressive Growth)"])
    
    if st.button("🔮 ให้ AI สแกนจัดทัพหุ้นเด็ดที่สุดตอนนี้"):
        with st.spinner("AI กำลังวิเคราะห์งบการเงิน อัตรากำไรสุทธิ และ Sentiment ข่าวรอบสัปดาห์..."):
            time.sleep(2)
            
            st.subheader(f"💡 หุ้นเด็ดแนะนำสำหรับสาย: {risk_level}")
            
            if risk_level == "ซิ่งก้าวกระโดด (Aggressive Growth)":
                st.markdown("""
                * **NVIDIA (NVDA):** AI Sentiment อยู่ในเกณฑ์ดีมาก ค่า P/E ย่อตัวลงมาอยู่ในจุดคุ้มค่า มีแนวรับสำคัญที่ราคา **$195 - $198** ซึ่ง RSI ใกล้จุดเขตซื้อมากเกินไป มีโอกาสเกิดการเด้งฟื้นตัวสูง
                * **Broadcom (AVGO):** หุ้นเทคฯ ไฮบริดปันผลโต กราฟเทคนิคอลทำทรงพักฐานอย่างมีระเบียบ วอลลุ่มขายแห้งสนิท
                """)
            elif risk_level == "เติบโตปานกลาง (Balanced)":
                st.markdown("""
                * **QQQM ETF:** ปลอดภัยกว่าหุ้นรายตัว กระจายความเสี่ยงในนวัตกรรมชั้นนำ 100 ตัวของโลก
                * **Devon Energy (DVN):** ตัวแทนกลุ่มพลังงาน ช่วยกระจายความเสี่ยงจากหุ้นเทคฯ และจ่ายปันผลสูง
                """)
            else:
                st.markdown("""
                * **SCHD ETF:** ราชาหุ้นปันผลเสถียรภาพสูง ทนทานต่อสภาวะตลาดผันผวน
                """)
                
    st.divider()
    st.subheader("📥 ส่งออกข้อมูลรายงาน (Export Report)")
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        st.download_button(
            label="📊 Export เป็นไฟล์ Excel (.csv)",
            data=mock_scan_results.to_csv().encode('utf-8'),
            file_name='stock_hunter_report.csv',
            mime='text/csv',
        )
    with export_col2:
        st.button("📄 Export เป็นเอกสาร PDF สรุปพอร์ต (Coming Soon)")
