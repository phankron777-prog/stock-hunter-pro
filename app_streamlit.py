import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

st.set_page_config(
    page_title="🦅 นักล่าหุ้น Swing",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS — Dark trading terminal look, Thai-first
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Sarabun', sans-serif;
    background-color: #0d1117;
    color: #e6edf3;
}

.main { background-color: #0d1117; }

h1, h2, h3 { font-family: 'Sarabun', sans-serif; font-weight: 700; }

/* === HERO HEADER === */
.hero-header {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 24px 32px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #238636, #2ea043, #3fb950);
}
.hero-title {
    font-size: 28px;
    font-weight: 700;
    color: #e6edf3;
    margin: 0 0 4px 0;
}
.hero-subtitle {
    font-size: 14px;
    color: #8b949e;
    margin: 0;
    font-family: 'IBM Plex Mono', monospace;
}

/* === SIGNAL CARDS === */
.signal-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.signal-card:hover { border-color: #58a6ff; }

.signal-elite {
    border-left: 4px solid #3fb950;
    background: linear-gradient(90deg, #0d2117 0%, #161b22 100%);
}
.signal-buy {
    border-left: 4px solid #2ea043;
}
.signal-watch {
    border-left: 4px solid #d29922;
    background: linear-gradient(90deg, #1d1a0d 0%, #161b22 100%);
}
.signal-avoid {
    border-left: 4px solid #da3633;
    background: linear-gradient(90deg, #1d0d0d 0%, #161b22 100%);
}

/* === METRIC BOXES === */
.metric-row {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
}
.metric-box {
    flex: 1;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}
.metric-label {
    font-size: 11px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.metric-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 22px;
    font-weight: 600;
    color: #e6edf3;
}
.metric-value.green { color: #3fb950; }
.metric-value.red { color: #f85149; }
.metric-value.yellow { color: #d29922; }

/* === TOP 5 SECTION === */
.top5-header {
    background: linear-gradient(135deg, #0d2117, #161b22);
    border: 1px solid #238636;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.top5-badge {
    background: #238636;
    color: white;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    white-space: nowrap;
}
.top5-title {
    font-size: 18px;
    font-weight: 700;
    color: #3fb950;
    margin: 0;
}

/* === TICKER PILL === */
.ticker-pill {
    display: inline-block;
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 2px 10px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 14px;
    font-weight: 600;
    color: #58a6ff;
}

/* === SCORE BAR === */
.score-bar-wrap {
    background: #21262d;
    border-radius: 4px;
    height: 8px;
    margin-top: 6px;
    overflow: hidden;
}
.score-bar-fill {
    height: 100%;
    border-radius: 4px;
}

/* === TAGS === */
.tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    margin-right: 4px;
}
.tag-green { background: #0d2117; color: #3fb950; border: 1px solid #238636; }
.tag-red { background: #1d0d0d; color: #f85149; border: 1px solid #da3633; }
.tag-yellow { background: #1d1a0d; color: #d29922; border: 1px solid #9e6a03; }
.tag-blue { background: #0d1d2e; color: #58a6ff; border: 1px solid #1f6feb; }
.tag-gray { background: #21262d; color: #8b949e; border: 1px solid #30363d; }

/* === SECTION DIVIDER === */
.section-title {
    font-size: 13px;
    font-weight: 600;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 24px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #21262d;
}

/* === UPTREND SCANNER === */
.scanner-result {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.probability-badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 16px;
    font-weight: 700;
    padding: 6px 14px;
    border-radius: 6px;
}
.prob-high { background: #0d2117; color: #3fb950; }
.prob-med { background: #1d1a0d; color: #d29922; }
.prob-low { background: #1d0d0d; color: #f85149; }

/* === DISCLAIMER === */
.disclaimer {
    background: #1d0d0d;
    border: 1px solid #da3633;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 12px;
    color: #8b949e;
    margin-top: 8px;
}

/* === TABS === */
.stTabs [data-baseweb="tab-list"] {
    background: #161b22;
    border-radius: 8px;
    padding: 4px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #8b949e;
    border-radius: 6px;
    font-family: 'Sarabun', sans-serif;
    font-size: 14px;
}
.stTabs [aria-selected="true"] {
    background: #21262d !important;
    color: #e6edf3 !important;
}

/* Override streamlit defaults */
.stButton > button {
    background: #238636;
    color: white;
    border: none;
    border-radius: 8px;
    font-family: 'Sarabun', sans-serif;
    font-size: 15px;
    font-weight: 600;
    padding: 10px 24px;
    transition: background 0.2s;
}
.stButton > button:hover { background: #2ea043; }

.stTextInput > div > div > input {
    background: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
    border-radius: 8px;
    font-family: 'Sarabun', sans-serif;
}

.stNumberInput > div > div > input {
    background: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
}

.stSelectbox > div > div {
    background: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
}

.stDataFrame { border-radius: 8px; overflow: hidden; }

div[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 24px;
    color: #e6edf3;
}
div[data-testid="stMetricLabel"] {
    font-family: 'Sarabun', sans-serif;
    color: #8b949e;
}

.stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONSTANTS
# ============================================================
BENCHMARK = "SPY"
EARNINGS_BLACKOUT = 5  # วัน

# Universe อ้างอิงสำหรับ RS Rank
REFERENCE_UNIVERSE = [
    "AAPL","MSFT","GOOGL","AMZN","META","NVDA","AVGO","TSLA","AMD","TSM",
    "CRM","ORCL","ADBE","NOW","PLTR","SNOW","INTC","QCOM","MU","ARM",
    "JPM","BAC","GS","MS","V","MA","AXP",
    "UNH","LLY","JNJ","PFE","ABBV","MRK",
    "XOM","CVX","OXY","SLB",
    "WMT","COST","HD","MCD","NKE",
    "DIS","NFLX","BA","CAT","GE",
]

# ============================================================
# DATA LOADING
# ============================================================
@st.cache_data(ttl=1800)
def load_data(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="6mo", auto_adjust=True)
        return df if len(df) > 20 else None
    except:
        return None

@st.cache_data(ttl=300)
def load_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        price = getattr(fi, "last_price", None)
        return float(price) if price else None
    except:
        return None

@st.cache_data(ttl=3600)
def load_earnings(ticker):
    try:
        t = yf.Ticker(ticker)
        cal = t.get_earnings_dates(limit=4)
        if cal is None or cal.empty:
            return None, None
        now = pd.Timestamp.now(tz=cal.index.tz)
        future = cal[cal.index >= now]
        if future.empty:
            return None, None
        nxt = future.index.min()
        days = (nxt - now).days
        return nxt.date(), days
    except:
        return None, None

# ============================================================
# INDICATORS — ปรับสำหรับ Swing 1-2 อาทิตย์
# ============================================================
def calc_indicators(df):
    df = df.copy()
    c = df["Close"]

    # EMA
    df["EMA9"]  = c.ewm(span=9).mean()
    df["EMA20"] = c.ewm(span=20).mean()
    df["EMA50"] = c.ewm(span=50).mean()

    # ATR
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - c.shift(1)).abs(),
        (df["Low"]  - c.shift(1)).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(span=14).mean()

    # RVOL
    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()

    # Breakout (10 วัน — ปรับสำหรับ swing สั้น)
    df["High10"] = c.rolling(10).max().shift(1)

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Sig"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Sig"]

    # RSI
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(span=14).mean()
    loss = (-delta.clip(upper=0)).ewm(span=14).mean()
    rs_rsi = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - 100 / (1 + rs_rsi)

    # Bollinger Bands
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["BB_Up"]  = sma20 + 2 * std20
    df["BB_Low"] = sma20 - 2 * std20
    df["BB_Pct"] = (c - df["BB_Low"]) / (df["BB_Up"] - df["BB_Low"]).replace(0, np.nan)

    # Momentum 5 วัน (สำคัญสำหรับ swing)
    df["Mom5"] = c.pct_change(5) * 100

    return df

# ============================================================
# SCORING — ปรับสำหรับ Swing 1-2 อาทิตย์ (100 คะแนน)
# ============================================================
def swing_score(row, rs_rank, spy_ok):
    """
    ระบบคะแนน Swing Trading 1-2 อาทิตย์:
    EMA Trend     : 15 คะแนน (ใช้ EMA9/20 แทน 50/200 — เร็วกว่าสำหรับ swing)
    RS Rank       : 25 คะแนน
    Breakout 10วัน: 15 คะแนน (หน้าต่างสั้นลง)
    RVOL          : 15 คะแนน
    MACD          : 10 คะแนน
    RSI Zone      : 10 คะแนน (40-70 คือโซน swing ที่ดี)
    Momentum 5วัน : 5 คะแนน
    Market Filter : 5 คะแนน
    """
    s = 0
    bd = {}

    # 1. EMA Trend (15) — EMA9 > EMA20 > EMA50 = bullish stack for swing
    if row["Close"] > row["EMA9"] > row["EMA20"] > row["EMA50"]:
        pts = 15
    elif row["Close"] > row["EMA20"] > row["EMA50"]:
        pts = 10
    elif row["Close"] > row["EMA50"]:
        pts = 5
    else:
        pts = 0
    bd["แนวโน้ม EMA"] = pts; s += pts

    # 2. RS Rank (25)
    if np.isnan(rs_rank):
        pts = 0
    elif rs_rank >= 90: pts = 25
    elif rs_rank >= 80: pts = 20
    elif rs_rank >= 70: pts = 12
    elif rs_rank >= 55: pts = 5
    else: pts = 0
    bd["RS Rank"] = pts; s += pts

    # 3. Breakout 10 วัน (15)
    if not np.isnan(row["High10"]) and row["High10"] > 0:
        ratio = row["Close"] / row["High10"]
        if ratio >= 0.99: pts = 15
        elif ratio >= 0.96: pts = 8
        else: pts = 0
    else:
        pts = 0
    bd["Breakout"] = pts; s += pts

    # 4. Volume (15)
    if row["RVOL"] > 2.0: pts = 15
    elif row["RVOL"] > 1.5: pts = 10
    elif row["RVOL"] > 1.1: pts = 5
    else: pts = 0
    bd["วอลุ่ม"] = pts; s += pts

    # 5. MACD (10)
    if row["MACD"] > row["MACD_Sig"] and row["MACD"] > 0: pts = 10
    elif row["MACD"] > row["MACD_Sig"]: pts = 5
    else: pts = 0
    bd["MACD"] = pts; s += pts

    # 6. RSI Zone (10) — 40-70 คือโซนดีสำหรับ swing ไม่ Overbought
    rsi = row["RSI"]
    if 50 <= rsi <= 70: pts = 10
    elif 40 <= rsi < 50 or 70 < rsi <= 75: pts = 5
    elif 30 <= rsi < 40: pts = 2
    else: pts = 0
    bd["RSI Zone"] = pts; s += pts

    # 7. Momentum 5 วัน (5) — ต้องบวกแต่ไม่วิ่งเกินไปแล้ว
    m5 = row["Mom5"]
    if 1 <= m5 <= 8: pts = 5
    elif 0 < m5 or (8 < m5 <= 12): pts = 2
    else: pts = 0
    bd["Momentum 5วัน"] = pts; s += pts

    # 8. Market Filter (5)
    pts = 5 if spy_ok else 0
    bd["ตลาดรวม"] = pts; s += pts

    # Hard gate: วอลุ่มต่ำมาก cap ที่ 35
    if row["RVOL"] < 0.8:
        s = min(s, 35)
        bd["⚠️ วอลุ่มต่ำ"] = True

    return s, bd

def classify(score):
    if score >= 82: return "🚀 ซื้อเลย"
    elif score >= 68: return "🔥 น่าซื้อ"
    elif score >= 52: return "👀 จับตาดู"
    else:             return "❌ หลีกเลี่ยง"

def classify_color(score):
    if score >= 82: return "#3fb950"
    elif score >= 68: return "#2ea043"
    elif score >= 52: return "#d29922"
    else:             return "#f85149"

# ============================================================
# UPTREND PROBABILITY — คำนวณโอกาสขึ้น 3-10% ใน 10 วัน
# ============================================================
def uptrend_probability(df, rs_rank, spy_ok):
    """
    ประเมินโอกาสที่หุ้นจะขึ้น 3-10% ใน 10 วันทำการข้างหน้า
    จากสัญญาณเทคนิคัล (ไม่ใช่ความน่าจะเป็นทางสถิติที่พิสูจน์แล้ว)
    """
    if df is None or len(df) < 20:
        return 0, []

    last = df.iloc[-1]
    signals = []
    score = 0

    # 1. EMA Stack bullish
    if last["Close"] > last["EMA9"] > last["EMA20"]:
        score += 20
        signals.append(("✅", "EMA ซ้อน Bullish (EMA9>20)"))
    elif last["Close"] > last["EMA20"]:
        score += 10
        signals.append(("🟡", "ราคาเหนือ EMA20"))

    # 2. วอลุ่มพุ่ง
    if last["RVOL"] > 2.0:
        score += 20
        signals.append(("✅", f"วอลุ่มพุ่ง {last['RVOL']:.1f}x — มีแรงซื้อจริง"))
    elif last["RVOL"] > 1.5:
        score += 12
        signals.append(("🟡", f"วอลุ่มสูงกว่าปกติ {last['RVOL']:.1f}x"))

    # 3. Breakout ใกล้ High
    if not np.isnan(last["High10"]) and last["High10"] > 0:
        if last["Close"] >= last["High10"] * 0.99:
            score += 20
            signals.append(("✅", "Breakout ผ่าน High 10 วัน"))
        elif last["Close"] >= last["High10"] * 0.97:
            score += 10
            signals.append(("🟡", "ใกล้ High 10 วัน — เฝ้าดู"))

    # 4. MACD cross
    if last["MACD"] > last["MACD_Sig"] and last["MACD_Hist"] > 0:
        if last["MACD"] > 0:
            score += 15
            signals.append(("✅", "MACD ตัด Signal ขึ้น (บวก)"))
        else:
            score += 8
            signals.append(("🟡", "MACD กำลังฟื้น (ยังติดลบ)"))

    # 5. RSI ไม่ Overbought
    rsi = last["RSI"]
    if 50 <= rsi <= 65:
        score += 15
        signals.append(("✅", f"RSI {rsi:.0f} — โซนเหมาะสม ไม่ร้อนเกิน"))
    elif 40 <= rsi < 50:
        score += 8
        signals.append(("🟡", f"RSI {rsi:.0f} — กำลังฟื้น"))
    elif rsi > 75:
        score -= 10
        signals.append(("❌", f"RSI {rsi:.0f} — Overbought เสี่ยงสูง"))

    # 6. RS Rank
    if not np.isnan(rs_rank) and rs_rank >= 80:
        score += 10
        signals.append(("✅", f"RS Rank {rs_rank:.0f} — แข็งแกร่งกว่าตลาด"))

    # 7. SPY Regime
    if not spy_ok:
        score -= 15
        signals.append(("❌", "ตลาดรวมอยู่ในขาลง — ลดน้ำหนัก"))

    # Normalize to 0-100
    prob = max(0, min(score, 100))
    return prob, signals

# ============================================================
# RS RANK
# ============================================================
def calc_rs(stock_close, bench_close):
    aligned = pd.concat([stock_close, bench_close], axis=1).dropna()
    aligned.columns = ["s", "b"]
    if len(aligned) < 21:
        return np.nan
    # น้ำหนัก swing: เน้นระยะสั้น-กลาง
    periods = {21: 0.5, 42: 0.3, 63: 0.2}
    rel = 0; tw = 0
    for n, w in periods.items():
        if len(aligned) > n:
            sr = aligned["s"].iloc[-1] / aligned["s"].iloc[-1-n] - 1
            br = aligned["b"].iloc[-1] / aligned["b"].iloc[-1-n] - 1
            rel += w * (sr - br)
            tw += w
    return (rel / tw) if tw > 0 else np.nan

def rank_universe(scores: dict):
    valid = {k: v for k, v in scores.items() if not np.isnan(v)}
    if len(valid) <= 1:
        return {k: 50.0 for k in scores}
    s = pd.Series(valid)
    ranks = s.rank(pct=True) * 98 + 1
    return {k: ranks.get(k, np.nan) for k in scores}

# ============================================================
# POSITION SIZING
# ============================================================
def calc_position(capital, price, atr, risk_pct=1.0, atr_mult=2.0, max_pct=20.0):
    stop_dist = atr * atr_mult
    if stop_dist <= 0 or price <= 0:
        return 0, 0, 0
    risk_usd = capital * risk_pct / 100
    shares = int(risk_usd / stop_dist)
    max_shares = int(capital * max_pct / 100 / price)
    shares = min(shares, max_shares)
    return shares, shares * price, risk_usd

# ============================================================
# HEADER
# ============================================================
st.markdown("""
<div class="hero-header">
    <div class="hero-title">🦅 นักล่าหุ้น Swing</div>
    <div class="hero-subtitle">สำหรับสไตล์ถือ 1-2 อาทิตย์ · เหมาะกับแอป Dime · อัปเดตทุกครั้งที่กด Scan</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR — ตั้งค่าง่าย ๆ
# ============================================================
with st.sidebar:
    st.markdown("### ⚙️ ตั้งค่า")
    capital = st.number_input("เงินทุน ($)", value=10000.0, step=500.0, min_value=100.0, max_value=10000000.0,
                               help="ใช้คำนวณขนาดไม้")
    risk_pct = st.slider("ความเสี่ยงต่อไม้ (%)", 0.5, 3.0, 1.0, 0.5,
                          help="1% = สูญได้มากที่สุด 1% ต่อไม้")
    atr_mult = st.slider("Stop = ATR ×", 1.5, 3.0, 2.0, 0.5)
    min_score = st.slider("คะแนนขั้นต่ำที่แสดง", 0, 80, 40, 5)

    st.divider()
    st.markdown("**ℹ️ คำเตือน**")
    st.caption("ข้อมูลล่าช้า 15+ นาที · ไม่ใช่คำแนะนำการลงทุน · ตรวจสอบกับ broker ของคุณก่อนทุกครั้ง")

# ============================================================
# INPUT — ชื่อหุ้น
# ============================================================
col_inp, col_btn = st.columns([4, 1])
with col_inp:
    user_input = st.text_input(
        "🔍 ชื่อหุ้นที่ต้องการ Scan (คั่นด้วยลูกน้ำ)",
        "NVDA, PLTR, AMD, TSLA, META, AAPL, MSFT, SMCI, MSTR, COIN",
        label_visibility="visible"
    )
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    scan_btn = st.button("🔍 Scan", use_container_width=True)

tickers = [t.strip().upper() for t in user_input.split(",") if t.strip()]

# ============================================================
# LOAD + COMPUTE (ทำทุกครั้งที่ render หรือกด Scan)
# ============================================================
if tickers:
    # 1. Load SPY
    spy_df = load_data(BENCHMARK)
    spy_ok = False
    if spy_df is not None:
        spy_df = calc_indicators(spy_df)
        spy_ok = bool(spy_df["Close"].iloc[-1] > spy_df["EMA50"].iloc[-1])

    # 2. Load reference universe สำหรับ RS Rank
    ranking_uni = list(dict.fromkeys(tickers + [r for r in REFERENCE_UNIVERSE if r not in tickers]))

    raw_rs = {}
    all_dfs = {}

    prog = st.progress(0.0, text="กำลังโหลดข้อมูล...")
    for i, t in enumerate(ranking_uni):
        df = load_data(t)
        if df is not None and len(df) > 30:
            df = calc_indicators(df)
            all_dfs[t] = df
            if spy_df is not None:
                raw_rs[t] = calc_rs(df["Close"], spy_df["Close"])
            else:
                raw_rs[t] = np.nan
        prog.progress((i + 1) / len(ranking_uni))
    prog.empty()

    rs_ranks = rank_universe(raw_rs)

    # 3. Score หุ้นที่ user ต้องการ
    results = []
    for t in tickers:
        if t not in all_dfs:
            continue
        df = all_dfs[t]
        last = df.iloc[-1]
        rs_rank = rs_ranks.get(t, np.nan)

        score, breakdown = swing_score(last, rs_rank, spy_ok)
        action = classify(score)
        prob, signals = uptrend_probability(df, rs_rank, spy_ok)

        shares, pos_val, risk_usd = calc_position(capital, last["Close"],
                                                    last["ATR"], risk_pct, atr_mult)
        stop_price = last["Close"] - last["ATR"] * atr_mult
        target1    = last["Close"] + last["ATR"] * atr_mult * 1.5  # 1.5R
        target2    = last["Close"] + last["ATR"] * atr_mult * 3.0  # 3R

        live_price = load_live_price(t)
        gap_pct = None
        if live_price and last["Close"] > 0:
            gap_pct = (live_price - last["Close"]) / last["Close"] * 100

        earn_date, earn_days = load_earnings(t)

        results.append({
            "ticker": t,
            "score": score,
            "action": action,
            "prob": prob,
            "signals": signals,
            "breakdown": breakdown,
            "price": last["Close"],
            "live_price": live_price,
            "gap_pct": gap_pct,
            "rsi": last["RSI"],
            "rvol": last["RVOL"],
            "atr": last["ATR"],
            "rs_rank": rs_rank,
            "mom5": last["Mom5"],
            "macd": last["MACD"],
            "macd_sig": last["MACD_Sig"],
            "shares": shares,
            "pos_val": pos_val,
            "risk_usd": risk_usd,
            "stop": round(stop_price, 2),
            "target1": round(target1, 2),
            "target2": round(target2, 2),
            "earn_days": earn_days,
            "earn_date": earn_date,
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    # ============================================================
    # MARKET STATUS BAR
    # ============================================================
    spy_last = spy_df.iloc[-1] if spy_df is not None else None
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        market_color = "green" if spy_ok else "red"
        market_text  = "🟢 ขาขึ้น" if spy_ok else "🔴 ขาลง"
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">สภาพตลาด (SPY)</div>
            <div class="metric-value {market_color}">{market_text}</div>
        </div>""", unsafe_allow_html=True)

    with col2:
        top_score = results[0]["score"] if results else 0
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">คะแนนสูงสุด</div>
            <div class="metric-value">{top_score}</div>
        </div>""", unsafe_allow_html=True)

    with col3:
        n_buy = len([r for r in results if r["score"] >= 68])
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">หุ้นน่าซื้อ</div>
            <div class="metric-value green">{n_buy} ตัว</div>
        </div>""", unsafe_allow_html=True)

    with col4:
        now_th = datetime.now().strftime("%H:%M น.")
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-label">อัปเดตล่าสุด</div>
            <div class="metric-value" style="font-size:16px">{now_th}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ============================================================
    # TABS หลัก
    # ============================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏆 Top 5 หุ้นเด่นวันนี้",
        "📊 ผลทุกตัว",
        "🎯 วิเคราะห์แต่ละตัว",
        "💰 คำนวณไม้"
    ])

    # ============================================================
    # TAB 1 — TOP 5
    # ============================================================
    with tab1:
        st.markdown("""
        <div class="top5-header">
            <span class="top5-badge">TOP 5</span>
            <span class="top5-title">หุ้นที่มีแนวโน้มขึ้น 3-10% ใน 2 อาทิตย์</span>
        </div>
        """, unsafe_allow_html=True)

        st.caption("⚠️ โอกาสขึ้นประเมินจากสัญญาณเทคนิคัล ไม่ใช่การรับประกัน — ใช้ประกอบการตัดสินใจเท่านั้น")

        top5 = [r for r in results if r["score"] >= 50][:5]

        if not top5:
            st.warning("⚠️ ยังไม่มีหุ้นที่ผ่านเกณฑ์ขั้นต่ำ (คะแนน ≥ 50) — ลองเพิ่มชื่อหุ้นในช่องด้านบน")
        else:
            for rank_i, r in enumerate(top5):
                prob = r["prob"]
                prob_class = "prob-high" if prob >= 70 else ("prob-med" if prob >= 50 else "prob-low")
                prob_text = f"{prob:.0f}%"

                signal_color = classify_color(r["score"])
                card_class = ("signal-elite" if r["score"] >= 82 else
                              "signal-buy" if r["score"] >= 68 else "signal-watch")

                # สร้าง tags
                tags = []
                if r["rvol"] > 1.5:
                    tags.append('<span class="tag tag-green">วอลุ่มสูง</span>')
                if not np.isnan(r["rs_rank"]) and r["rs_rank"] >= 80:
                    tags.append('<span class="tag tag-blue">RS แข็ง</span>')
                if r["macd"] > r["macd_sig"] and r["macd"] > 0:
                    tags.append('<span class="tag tag-green">MACD ขึ้น</span>')
                if r["earn_days"] and r["earn_days"] <= EARNINGS_BLACKOUT:
                    tags.append('<span class="tag tag-red">⚠️ Earnings ใกล้</span>')
                if r["gap_pct"] and abs(r["gap_pct"]) >= 3:
                    dir_s = "⬆️" if r["gap_pct"] > 0 else "⬇️"
                    tags.append(f'<span class="tag tag-yellow">{dir_s} Gap {r["gap_pct"]:+.1f}%</span>')
                tags_html = " ".join(tags)

                # RSI color
                rsi_color = "#3fb950" if 50 <= r["rsi"] <= 70 else ("#f85149" if r["rsi"] > 75 else "#d29922")

                # Signals top 3
                sig_html = ""
                for emoji, txt in r["signals"][:4]:
                    sig_html += f"<div style='font-size:13px; color:#8b949e; margin:2px 0'>{emoji} {txt}</div>"

                st.markdown(f"""
                <div class="signal-card {card_class}">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px">
                    <div style="flex:1; min-width:200px">
                      <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px">
                        <span style="font-size:20px; font-weight:700; color:#8b949e">#{rank_i+1}</span>
                        <span class="ticker-pill">{r["ticker"]}</span>
                        <span style="font-size:14px; color:{signal_color}; font-weight:700">{r["action"]}</span>
                        <span style="font-size:13px; color:#8b949e">{r["score"]}/100</span>
                      </div>
                      <div style="margin-bottom:8px">{tags_html}</div>
                      <div style="font-family:'IBM Plex Mono',monospace; font-size:13px; color:#8b949e; margin-bottom:8px">
                        ราคา: <span style="color:#e6edf3">${r['price']:.2f}</span> &nbsp;|&nbsp;
                        Stop: <span style="color:#f85149">${r['stop']:.2f}</span> &nbsp;|&nbsp;
                        เป้า1: <span style="color:#3fb950">${r['target1']:.2f}</span> &nbsp;|&nbsp;
                        เป้า2: <span style="color:#3fb950">${r['target2']:.2f}</span>
                      </div>
                      <div>{sig_html}</div>
                    </div>
                    <div style="text-align:center; min-width:100px">
                      <div style="font-size:11px; color:#8b949e; margin-bottom:4px">โอกาสขึ้น 3-10%</div>
                      <div class="probability-badge {prob_class}">{prob_text}</div>
                      <div style="font-size:10px; color:#8b949e; margin-top:4px">RSI {r['rsi']:.0f} &nbsp;|&nbsp; RVOL {r['rvol']:.1f}x</div>
                    </div>
                  </div>
                  <div class="score-bar-wrap" style="margin-top:10px">
                    <div class="score-bar-fill" style="width:{r['score']}%; background:{signal_color}"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            # คำเตือนสำคัญ
            st.markdown("""
            <div class="disclaimer">
                📋 <strong>อ่านก่อน:</strong> "โอกาสขึ้น" คือการประเมินจากสัญญาณเทคนิคัลที่ตั้งค่าไว้
                ไม่ใช่ความน่าจะเป็นที่พิสูจน์ทางสถิติ · ข้อมูลล่าช้า 15+ นาที ·
                ควรตรวจข่าว/ปัจจัยพื้นฐาน + ราคาจาก Dime ก่อนตัดสินใจซื้อเสมอ
            </div>
            """, unsafe_allow_html=True)

    # ============================================================
    # TAB 2 — ผลทุกตัว
    # ============================================================
    with tab2:
        st.markdown('<div class="section-title">ผล Scan ทั้งหมด</div>', unsafe_allow_html=True)

        filtered = [r for r in results if r["score"] >= min_score]
        if not filtered:
            st.info("ไม่มีหุ้นที่ผ่านเกณฑ์คะแนนที่ตั้งไว้ — ลองลดคะแนนขั้นต่ำใน sidebar")
        else:
            table_data = []
            for r in filtered:
                rs_str = f"{r['rs_rank']:.0f}" if not np.isnan(r['rs_rank']) else "—"
                gap_str = f"{r['gap_pct']:+.1f}%" if r['gap_pct'] else "—"
                earn_str = f"{r['earn_days']}วัน" if r['earn_days'] is not None else "—"
                table_data.append({
                    "หุ้น": r["ticker"],
                    "สัญญาณ": r["action"],
                    "คะแนน": r["score"],
                    "โอกาสขึ้น%": f"{r['prob']:.0f}%",
                    "ราคา": f"${r['price']:.2f}",
                    "Stop": f"${r['stop']:.2f}",
                    "เป้าหมาย": f"${r['target1']:.2f}",
                    "RS Rank": rs_str,
                    "RSI": f"{r['rsi']:.0f}",
                    "RVOL": f"{r['rvol']:.1f}x",
                    "Momentum5วัน": f"{r['mom5']:.1f}%",
                    "Gap": gap_str,
                    "Earnings": earn_str,
                })

            df_table = pd.DataFrame(table_data)
            st.dataframe(df_table, use_container_width=True, hide_index=True)

            # Download
            csv = df_table.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ ดาวน์โหลด CSV",
                csv,
                f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "text/csv"
            )

    # ============================================================
    # TAB 3 — วิเคราะห์แต่ละตัว
    # ============================================================
    with tab3:
        st.markdown('<div class="section-title">วิเคราะห์รายตัว</div>', unsafe_allow_html=True)

        ticker_options = [r["ticker"] for r in results]
        selected = st.selectbox("เลือกหุ้นที่ต้องการดูรายละเอียด", ticker_options)

        sel_data = next((r for r in results if r["ticker"] == selected), None)
        if sel_data:
            r = sel_data
            signal_color = classify_color(r["score"])

            # Header
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:16px; margin-bottom:20px">
                <span class="ticker-pill" style="font-size:20px; padding:6px 16px">{r['ticker']}</span>
                <span style="font-size:22px; font-weight:700; color:{signal_color}">{r['action']}</span>
                <span style="font-size:18px; color:#8b949e">{r['score']}/100 คะแนน</span>
            </div>
            """, unsafe_allow_html=True)

            # Metrics row
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("ราคาปิด", f"${r['price']:.2f}")
            c2.metric("RS Rank", f"{r['rs_rank']:.0f}" if not np.isnan(r['rs_rank']) else "—")
            c3.metric("RSI", f"{r['rsi']:.0f}")
            c4.metric("RVOL", f"{r['rvol']:.1f}x")
            c5.metric("Momentum 5วัน", f"{r['mom5']:+.1f}%")

            st.divider()
            col_left, col_right = st.columns(2)

            with col_left:
                st.markdown("**📋 คะแนนแยกรายหัวข้อ**")
                for key, val in r["breakdown"].items():
                    if key == "⚠️ วอลุ่มต่ำ":
                        st.warning("⚠️ วอลุ่มต่ำ — คะแนนถูกจำกัดที่ 35")
                        continue
                    maxes = {
                        "แนวโน้ม EMA": 15, "RS Rank": 25, "Breakout": 15,
                        "วอลุ่ม": 15, "MACD": 10, "RSI Zone": 10,
                        "Momentum 5วัน": 5, "ตลาดรวม": 5
                    }
                    mx = maxes.get(key, 10)
                    bar_w = int(val / mx * 100) if mx > 0 else 0
                    bar_color = "#3fb950" if val == mx else ("#d29922" if val > 0 else "#f85149")
                    st.markdown(f"""
                    <div style="margin-bottom:10px">
                        <div style="display:flex; justify-content:space-between; font-size:13px">
                            <span style="color:#e6edf3">{key}</span>
                            <span style="color:{bar_color}; font-family:'IBM Plex Mono',monospace">{val}/{mx}</span>
                        </div>
                        <div class="score-bar-wrap" style="margin-top:4px">
                            <div class="score-bar-fill" style="width:{bar_w}%; background:{bar_color}"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col_right:
                st.markdown("**🎯 แผนเทรด**")
                r2r = (r["target1"] - r["price"]) / (r["price"] - r["stop"]) if r["price"] != r["stop"] else 0
                st.markdown(f"""
                <div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px">
                    <div style="margin-bottom:10px">
                        <div style="font-size:12px; color:#8b949e">จุดเข้า (ราคาปิด)</div>
                        <div style="font-family:'IBM Plex Mono',monospace; font-size:18px; color:#e6edf3">${r['price']:.2f}</div>
                    </div>
                    <div style="margin-bottom:10px">
                        <div style="font-size:12px; color:#8b949e">Stop Loss (ATR×{atr_mult})</div>
                        <div style="font-family:'IBM Plex Mono',monospace; font-size:18px; color:#f85149">${r['stop']:.2f} <span style="font-size:12px">(-{(r['price']-r['stop'])/r['price']*100:.1f}%)</span></div>
                    </div>
                    <div style="margin-bottom:10px">
                        <div style="font-size:12px; color:#8b949e">เป้าหมาย 1 (1.5R) ≈ +{(r['target1']-r['price'])/r['price']*100:.1f}%</div>
                        <div style="font-family:'IBM Plex Mono',monospace; font-size:18px; color:#3fb950">${r['target1']:.2f}</div>
                    </div>
                    <div style="margin-bottom:10px">
                        <div style="font-size:12px; color:#8b949e">เป้าหมาย 2 (3R) ≈ +{(r['target2']-r['price'])/r['price']*100:.1f}%</div>
                        <div style="font-family:'IBM Plex Mono',monospace; font-size:18px; color:#3fb950">${r['target2']:.2f}</div>
                    </div>
                    <div style="border-top:1px solid #30363d; padding-top:10px; margin-top:4px">
                        <div style="font-size:12px; color:#8b949e">อัตราส่วน Risk:Reward</div>
                        <div style="font-size:16px; font-weight:700; color:#58a6ff">1 : {r2r:.1f}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Earnings warning
                if r["earn_days"] is not None and r["earn_days"] <= 14:
                    st.warning(f"⚠️ มี Earnings ใน {r['earn_days']} วัน ({r['earn_date']}) — ราคาอาจผันผวนรุนแรง")

            # Signals
            st.markdown("**🔍 สัญญาณที่พบ**")
            for emoji, txt in r["signals"]:
                color = "#3fb950" if emoji == "✅" else ("#f85149" if emoji == "❌" else "#d29922")
                st.markdown(f'<div style="padding:6px 0; color:{color}; font-size:14px">{emoji} {txt}</div>',
                           unsafe_allow_html=True)

            # Price chart (streamlit native)
            if selected in all_dfs:
                chart_df = all_dfs[selected][["Close","EMA9","EMA20","EMA50"]].tail(60)
                st.markdown("**📈 กราฟราคา 60 วัน**")
                st.line_chart(chart_df, height=220)

    # ============================================================
    # TAB 4 — คำนวณไม้
    # ============================================================
    with tab4:
        st.markdown('<div class="section-title">💰 คำนวณขนาดไม้ก่อนเข้าเทรด</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            calc_ticker = st.selectbox("เลือกหุ้น", ticker_options, key="calc_t")
            cal = next((r for r in results if r["ticker"] == calc_ticker), None)
            if cal:
                custom_entry = st.number_input("ราคาเข้าจริง ($)", value=float(cal["price"]), step=0.5, min_value=0.01)
                custom_stop  = st.number_input("Stop Loss ($)", value=float(cal["stop"]), step=0.5, min_value=0.01)
                custom_cap   = st.number_input("เงินทุน ($)", value=float(capital), step=500.0, min_value=100.0)
                custom_risk  = st.slider("ความเสี่ยงต่อไม้ (%)", 0.5, 3.0, float(risk_pct), 0.25)

        with col_b:
            if cal:
                stop_dist  = custom_entry - custom_stop
                risk_usd   = custom_cap * custom_risk / 100
                if stop_dist > 0:
                    shares_calc  = int(risk_usd / stop_dist)
                    pos_val_calc = shares_calc * custom_entry
                    target1_calc = custom_entry + (custom_entry - custom_stop) * 1.5
                    target2_calc = custom_entry + (custom_entry - custom_stop) * 3.0
                    rr_ratio     = (target1_calc - custom_entry) / stop_dist

                    st.markdown(f"""
                    <div style="background:#161b22; border:1px solid #238636; border-radius:10px; padding:20px; margin-top:8px">
                        <div style="font-size:16px; font-weight:700; color:#3fb950; margin-bottom:16px">ผลคำนวณ</div>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px">
                            <div>
                                <div style="font-size:11px; color:#8b949e">จำนวนหุ้น</div>
                                <div style="font-family:'IBM Plex Mono',monospace; font-size:22px; color:#e6edf3">{shares_calc:,}</div>
                            </div>
                            <div>
                                <div style="font-size:11px; color:#8b949e">มูลค่าไม้</div>
                                <div style="font-family:'IBM Plex Mono',monospace; font-size:22px; color:#e6edf3">${pos_val_calc:,.0f}</div>
                            </div>
                            <div>
                                <div style="font-size:11px; color:#8b949e">ความเสี่ยงสูงสุด</div>
                                <div style="font-family:'IBM Plex Mono',monospace; font-size:18px; color:#f85149">${risk_usd:,.0f}</div>
                            </div>
                            <div>
                                <div style="font-size:11px; color:#8b949e">R:R Ratio</div>
                                <div style="font-family:'IBM Plex Mono',monospace; font-size:18px; color:#58a6ff">1:{rr_ratio:.1f}</div>
                            </div>
                            <div>
                                <div style="font-size:11px; color:#8b949e">เป้า 1 (+{(target1_calc-custom_entry)/custom_entry*100:.1f}%)</div>
                                <div style="font-family:'IBM Plex Mono',monospace; font-size:18px; color:#3fb950">${target1_calc:.2f}</div>
                            </div>
                            <div>
                                <div style="font-size:11px; color:#8b949e">เป้า 2 (+{(target2_calc-custom_entry)/custom_entry*100:.1f}%)</div>
                                <div style="font-family:'IBM Plex Mono',monospace; font-size:18px; color:#3fb950">${target2_calc:.2f}</div>
                            </div>
                        </div>
                        <div style="margin-top:14px; padding-top:12px; border-top:1px solid #30363d; font-size:13px; color:#8b949e">
                            % ของพอร์ตที่ใช้: {pos_val_calc/custom_cap*100:.1f}%
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if rr_ratio < 1.5:
                        st.warning("⚠️ R:R ต่ำกว่า 1:1.5 — ควรขยับ Stop หรือเลือนเป้าหมายใหม่")
                else:
                    st.error("❌ ราคาเข้าต้องสูงกว่า Stop Loss")

    # ============================================================
    # DISCLAIMER ท้ายหน้า
    # ============================================================
    st.divider()
    st.caption(
        "⚠️ ระบบนี้เป็นเครื่องมือช่วยวิเคราะห์เทคนิคัลเท่านั้น · ข้อมูลล่าช้า 15+ นาที (Yahoo Finance) · "
        "ไม่ใช่คำแนะนำการลงทุน · ผลย้อนหลังไม่ได้รับประกันอนาคต · "
        "ตรวจสอบราคาจริงบนแอป Dime ก่อนส่งคำสั่งทุกครั้ง"
    )

else:
    st.info("👆 พิมพ์ชื่อหุ้น (เช่น NVDA, AAPL, TSLA) แล้วกด Scan")
