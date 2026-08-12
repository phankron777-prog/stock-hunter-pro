import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import concurrent.futures

st.set_page_config(
    page_title="🦅 นักล่าหุ้น Swing",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Sarabun', sans-serif; background-color: #0d1117; color: #e6edf3; }
.main { background-color: #0d1117; }
h1, h2, h3 { font-family: 'Sarabun', sans-serif; font-weight: 700; }
.hero-header { background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%); border: 1px solid #30363d; border-radius: 12px; padding: 24px 32px; margin-bottom: 24px; position: relative; overflow: hidden; }
.hero-header::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #238636, #2ea043, #3fb950); }
.hero-title { font-size: 28px; font-weight: 700; color: #e6edf3; margin: 0 0 4px 0; }
.hero-subtitle { font-size: 14px; color: #8b949e; margin: 0; font-family: 'IBM Plex Mono', monospace; }
.signal-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.signal-elite { border-left: 4px solid #3fb950; background: linear-gradient(90deg, #0d2117 0%, #161b22 100%); }
.signal-buy { border-left: 4px solid #2ea043; }
.signal-watch { border-left: 4px solid #d29922; background: linear-gradient(90deg, #1d1a0d 0%, #161b22 100%); }
.signal-avoid { border-left: 4px solid #da3633; background: linear-gradient(90deg, #1d0d0d 0%, #161b22 100%); }
.metric-box { flex: 1; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px 16px; text-align: center; }
.metric-label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.metric-value { font-family: 'IBM Plex Mono', monospace; font-size: 22px; font-weight: 600; color: #e6edf3; }
.metric-value.green { color: #3fb950; }
.metric-value.red { color: #f85149; }
.top5-header { background: linear-gradient(135deg, #0d2117, #161b22); border: 1px solid #238636; border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; display: flex; align-items: center; gap: 12px; }
.top5-badge { background: #238636; color: white; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.top5-title { font-size: 18px; font-weight: 700; color: #3fb950; margin: 0; }
.ticker-pill { display: inline-block; background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 2px 10px; font-family: 'IBM Plex Mono', monospace; font-size: 14px; font-weight: 600; color: #58a6ff; }
.score-bar-wrap { background: #21262d; border-radius: 4px; height: 8px; margin-top: 6px; overflow: hidden; }
.score-bar-fill { height: 100%; border-radius: 4px; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 4px; }
.tag-green { background: #0d2117; color: #3fb950; border: 1px solid #238636; }
.tag-red { background: #1d0d0d; color: #f85149; border: 1px solid #da3633; }
.tag-yellow { background: #1d1a0d; color: #d29922; border: 1px solid #9e6a03; }
.tag-blue { background: #0d1d2e; color: #58a6ff; border: 1px solid #1f6feb; }
.section-title { font-size: 13px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin: 24px 0 12px 0; padding-bottom: 8px; border-bottom: 1px solid #21262d; }
.probability-badge { font-family: 'IBM Plex Mono', monospace; font-size: 16px; font-weight: 700; padding: 6px 14px; border-radius: 6px; }
.prob-high { background: #0d2117; color: #3fb950; }
.prob-med { background: #1d1a0d; color: #d29922; }
.prob-low { background: #1d0d0d; color: #f85149; }
.disclaimer { background: #1d0d0d; border: 1px solid #da3633; border-radius: 8px; padding: 12px 16px; font-size: 12px; color: #8b949e; margin-top: 8px; }
.stTabs [data-baseweb="tab-list"] { background: #161b22; border-radius: 8px; padding: 4px; gap: 4px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #8b949e; border-radius: 6px; font-family: 'Sarabun', sans-serif; font-size: 14px; }
.stTabs [aria-selected="true"] { background: #21262d !important; color: #e6edf3 !important; }
.stButton > button { background: #238636; color: white; border: none; border-radius: 8px; font-family: 'Sarabun', sans-serif; font-size: 15px; font-weight: 600; padding: 10px 24px; }
.stButton > button:hover { background: #2ea043; }
.stTextInput > div > div > input { background: #161b22; border: 1px solid #30363d; color: #e6edf3; border-radius: 8px; }
.stNumberInput > div > div > input { background: #161b22; border: 1px solid #30363d; color: #e6edf3; }
.stSelectbox > div > div { background: #161b22; border: 1px solid #30363d; color: #e6edf3; }
div[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; font-size: 24px; color: #e6edf3; }
div[data-testid="stMetricLabel"] { font-family: 'Sarabun', sans-serif; color: #8b949e; }
</style>
""", unsafe_allow_html=True)

BENCHMARK = "SPY"
EARNINGS_BLACKOUT = 5

REFERENCE_UNIVERSE = [
    "AAPL","MSFT","GOOGL","AMZN","META","NVDA","AVGO","TSLA","AMD","TSM",
    "CRM","ORCL","ADBE","NOW","PLTR","SNOW","INTC","QCOM","MU","ARM",
    "JPM","BAC","GS","MS","V","MA","AXP",
    "UNH","LLY","JNJ","PFE","ABBV","MRK",
    "XOM","CVX","OXY","SLB",
    "WMT","COST","HD","MCD","NKE",
    "DIS","NFLX","BA","CAT","GE",
]

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
        tz = getattr(cal.index, "tz", None)
        now = pd.Timestamp.now(tz=tz) if tz is not None else pd.Timestamp.now()
        future = cal[cal.index >= now]
        if future.empty:
            return None, None
        nxt = future.index.min()
        days = (nxt - now).days
        return nxt.date(), int(days)
    except Exception:
        return None, None

def calc_indicators(df):
    df = df.copy()
    c = df["Close"]
    df["EMA9"]  = c.ewm(span=9).mean()
    df["EMA20"] = c.ewm(span=20).mean()
    df["EMA50"] = c.ewm(span=50).mean()
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - c.shift(1)).abs(),
        (df["Low"]  - c.shift(1)).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(span=14).mean()
    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["High10"] = c.rolling(10).max().shift(1)
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Sig"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Sig"]
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(span=14).mean()
    loss = (-delta.clip(upper=0)).ewm(span=14).mean()
    rs_rsi = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - 100 / (1 + rs_rsi)
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["BB_Up"]  = sma20 + 2 * std20
    df["BB_Low"] = sma20 - 2 * std20
    df["Mom5"] = c.pct_change(5) * 100
    return df

def _safe_float(val):
    """แปลง numpy/python value เป็น float อย่างปลอดภัย — คืน None ถ้าเป็น NaN/Inf"""
    try:
        f = float(val)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None

def swing_score(row, rs_rank, spy_ok):
    s = 0
    bd = {}

    if row["Close"] > row["EMA9"] > row["EMA20"] > row["EMA50"]:
        pts = 15
    elif row["Close"] > row["EMA20"] > row["EMA50"]:
        pts = 10
    elif row["Close"] > row["EMA50"]:
        pts = 5
    else:
        pts = 0
    bd["แนวโน้ม EMA"] = pts; s += pts

    rs = _safe_float(rs_rank)
    if rs is None: pts = 0
    elif rs >= 90: pts = 25
    elif rs >= 80: pts = 20
    elif rs >= 70: pts = 12
    elif rs >= 55: pts = 5
    else: pts = 0
    bd["RS Rank"] = pts; s += pts

    h10 = _safe_float(row["High10"])
    close = _safe_float(row["Close"])
    if h10 and h10 > 0 and close:
        ratio = close / h10
        if ratio >= 0.99: pts = 15
        elif ratio >= 0.96: pts = 8
        else: pts = 0
    else:
        pts = 0
    bd["Breakout"] = pts; s += pts

    rvol = _safe_float(row["RVOL"]) or 0
    if rvol > 2.0: pts = 15
    elif rvol > 1.5: pts = 10
    elif rvol > 1.1: pts = 5
    else: pts = 0
    bd["วอลุ่ม"] = pts; s += pts

    macd = _safe_float(row["MACD"]) or 0
    msig = _safe_float(row["MACD_Sig"]) or 0
    if macd > msig and macd > 0: pts = 10
    elif macd > msig: pts = 5
    else: pts = 0
    bd["MACD"] = pts; s += pts

    rsi = _safe_float(row["RSI"]) or 50
    if 50 <= rsi <= 70: pts = 10
    elif 40 <= rsi < 50 or 70 < rsi <= 75: pts = 5
    elif 30 <= rsi < 40: pts = 2
    else: pts = 0
    bd["RSI Zone"] = pts; s += pts

    m5 = _safe_float(row["Mom5"]) or 0
    if 1 <= m5 <= 8: pts = 5
    elif 0 < m5 or (8 < m5 <= 12): pts = 2
    else: pts = 0
    bd["Momentum 5วัน"] = pts; s += pts

    pts = 5 if spy_ok else 0
    bd["ตลาดรวม"] = pts; s += pts

    if rvol < 0.8:
        s = min(s, 35)
        bd["_chop"] = True
    else:
        bd["_chop"] = False

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

def uptrend_probability(df, rs_rank, spy_ok):
    if df is None or len(df) < 20:
        return 0, []
    last = df.iloc[-1]
    signals = []
    score = 0

    close = _safe_float(last["Close"]) or 0
    ema9  = _safe_float(last["EMA9"]) or 0
    ema20 = _safe_float(last["EMA20"]) or 0

    if close > ema9 > ema20 > 0:
        score += 20
        signals.append(("✅", "EMA ซ้อน Bullish (EMA9>20)"))
    elif close > ema20 > 0:
        score += 10
        signals.append(("🟡", "ราคาเหนือ EMA20"))

    rvol = _safe_float(last["RVOL"]) or 0
    if rvol > 2.0:
        score += 20
        signals.append(("✅", f"วอลุ่มพุ่ง {rvol:.1f}x — มีแรงซื้อจริง"))
    elif rvol > 1.5:
        score += 12
        signals.append(("🟡", f"วอลุ่มสูงกว่าปกติ {rvol:.1f}x"))

    h10 = _safe_float(last["High10"])
    if h10 and h10 > 0 and close:
        if close >= h10 * 0.99:
            score += 20
            signals.append(("✅", "Breakout ผ่าน High 10 วัน"))
        elif close >= h10 * 0.97:
            score += 10
            signals.append(("🟡", "ใกล้ High 10 วัน — เฝ้าดู"))

    macd = _safe_float(last["MACD"]) or 0
    msig = _safe_float(last["MACD_Sig"]) or 0
    mhist = _safe_float(last["MACD_Hist"]) or 0
    if macd > msig and mhist > 0:
        if macd > 0:
            score += 15
            signals.append(("✅", "MACD ตัด Signal ขึ้น (บวก)"))
        else:
            score += 8
            signals.append(("🟡", "MACD กำลังฟื้น (ยังติดลบ)"))

    rsi = _safe_float(last["RSI"]) or 50
    if 50 <= rsi <= 65:
        score += 15
        signals.append(("✅", f"RSI {rsi:.0f} — โซนเหมาะสม ไม่ร้อนเกิน"))
    elif 40 <= rsi < 50:
        score += 8
        signals.append(("🟡", f"RSI {rsi:.0f} — กำลังฟื้น"))
    elif rsi > 75:
        score -= 10
        signals.append(("❌", f"RSI {rsi:.0f} — Overbought เสี่ยงสูง"))

    rs = _safe_float(rs_rank)
    if rs and rs >= 80:
        score += 10
        signals.append(("✅", f"RS Rank {rs:.0f} — แข็งแกร่งกว่าตลาด"))

    if not spy_ok:
        score -= 15
        signals.append(("❌", "ตลาดรวมอยู่ในขาลง — ลดน้ำหนัก"))

    return max(0, min(score, 100)), signals

def calc_rs(stock_close, bench_close):
    aligned = pd.concat([stock_close, bench_close], axis=1).dropna()
    aligned.columns = ["s", "b"]
    if len(aligned) < 21:
        return np.nan
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

def calc_position(capital, price, atr, risk_pct=1.0, atr_mult=2.0, max_pct=20.0):
    """
    แปลงทุกค่าเป็น Python float และตรวจ NaN/Inf ก่อนคำนวณ
    NaN เกิดขึ้นเมื่อหุ้น (เช่น NBIS, SDCH) มีข้อมูลไม่ครบในช่วงที่ดึงมา
    """
    try:
        capital  = float(capital)
        price    = float(price)
        atr      = float(atr)
        risk_pct = float(risk_pct)
        atr_mult = float(atr_mult)
        max_pct  = float(max_pct)
    except (TypeError, ValueError):
        return 0, 0.0, 0.0

    # ตรวจ NaN/Inf — ถ้าค่าใดไม่ใช่เลขปกติให้คืน 0 ทันที
    if not all(np.isfinite(v) for v in [capital, price, atr, risk_pct, atr_mult, max_pct]):
        return 0, 0.0, 0.0
    if price <= 0 or atr <= 0:
        return 0, 0.0, 0.0

    stop_dist = atr * atr_mult
    if stop_dist <= 0:
        return 0, 0.0, 0.0

    risk_usd   = capital * risk_pct / 100.0
    shares     = max(0, int(risk_usd / stop_dist))
    max_shares = max(0, int(capital * max_pct / 100.0 / price))
    shares     = min(shares, max_shares)
    return shares, float(shares) * price, float(risk_usd)

# ============================================================
# HEADER
# ============================================================
st.markdown("""
<div class="hero-header">
    <div class="hero-title">🦅 นักล่าหุ้น Swing</div>
    <div class="hero-subtitle">สำหรับสไตล์ถือ 1-2 อาทิตย์ · เหมาะกับแอป Dime · อัปเดตทุกครั้งที่กด Scan</div>
</div>
""", unsafe_allow_html=True)

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

if tickers:
    spy_df = load_data(BENCHMARK)
    spy_ok = False
    if spy_df is not None:
        spy_df = calc_indicators(spy_df)
        spy_ok = bool((_safe_float(spy_df["Close"].iloc[-1]) or 0) > (_safe_float(spy_df["EMA50"].iloc[-1]) or 0))

    ranking_uni = list(dict.fromkeys(tickers + [r for r in REFERENCE_UNIVERSE if r not in tickers]))
    raw_rs = {}
    all_dfs = {}

    def fetch_and_prep(ticker):
        df = load_data(ticker)
        if df is not None and len(df) > 30:
            return ticker, calc_indicators(df)
        return ticker, None

    prog = st.progress(0.0, text="⚡ กำลังโหลดข้อมูลแบบรวดเร็ว...")
    completed = 0
    total = len(ranking_uni)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        future_map = {executor.submit(fetch_and_prep, t): t for t in ranking_uni}
        for future in concurrent.futures.as_completed(future_map):
            ticker, df = future.result()
            if df is not None:
                all_dfs[ticker] = df
                raw_rs[ticker] = calc_rs(df["Close"], spy_df["Close"]) if spy_df is not None else np.nan
            completed += 1
            prog.progress(completed / total, text=f"⚡ โหลดแล้ว {completed}/{total} หุ้น...")
    prog.empty()

    rs_ranks = rank_universe(raw_rs)

    results = []
    for t in tickers:
        if t not in all_dfs:
            continue
        df = all_dfs[t]
        last = df.iloc[-1]
        rs_rank = rs_ranks.get(t, np.nan)

        # แปลงทุกค่าเป็น Python float — ใช้ _safe_float เพื่อดัก NaN/Inf ด้วย
        price_f    = _safe_float(last["Close"])
        atr_f      = _safe_float(last["ATR"])
        rvol_f     = _safe_float(last["RVOL"]) or 0.0
        rsi_f      = _safe_float(last["RSI"]) or 50.0
        mom5_f     = _safe_float(last["Mom5"]) or 0.0
        macd_f     = _safe_float(last["MACD"]) or 0.0
        macd_sig_f = _safe_float(last["MACD_Sig"]) or 0.0
        rs_f       = _safe_float(rs_rank)

        # ข้ามหุ้นที่ราคาหรือ ATR เป็น NaN — ไม่สามารถคำนวณได้
        if price_f is None or atr_f is None:
            continue

        score, breakdown = swing_score(last, rs_rank, spy_ok)
        action = classify(score)
        prob, signals = uptrend_probability(df, rs_rank, spy_ok)

        shares, pos_val, risk_usd = calc_position(capital, price_f, atr_f, risk_pct, atr_mult)
        stop_price = round(price_f - atr_f * float(atr_mult), 2)
        target1    = round(price_f + atr_f * float(atr_mult) * 1.5, 2)
        target2    = round(price_f + atr_f * float(atr_mult) * 3.0, 2)

        live_price = load_live_price(t)
        gap_pct = None
        if live_price and price_f > 0:
            gap_pct = round((live_price - price_f) / price_f * 100, 2)

        earn_date, earn_days = load_earnings(t)

        results.append({
            "ticker": t,
            "score": score,
            "action": action,
            "prob": prob,
            "signals": signals,
            "breakdown": breakdown,
            "price": price_f,
            "live_price": live_price,
            "gap_pct": gap_pct,
            "rsi": rsi_f,
            "rvol": rvol_f,
            "atr": atr_f,
            "rs_rank": rs_f if rs_f is not None else float("nan"),
            "mom5": mom5_f,
            "macd": macd_f,
            "macd_sig": macd_sig_f,
            "shares": shares,
            "pos_val": pos_val,
            "risk_usd": risk_usd,
            "stop": stop_price,
            "target1": target1,
            "target2": target2,
            "earn_days": earn_days,
            "earn_date": earn_date,
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        mc = "green" if spy_ok else "red"
        mt = "🟢 ขาขึ้น" if spy_ok else "🔴 ขาลง"
        st.markdown(f'<div class="metric-box"><div class="metric-label">สภาพตลาด (SPY)</div><div class="metric-value {mc}">{mt}</div></div>', unsafe_allow_html=True)
    with col2:
        ts = results[0]["score"] if results else 0
        st.markdown(f'<div class="metric-box"><div class="metric-label">คะแนนสูงสุด</div><div class="metric-value">{ts}</div></div>', unsafe_allow_html=True)
    with col3:
        nb = len([r for r in results if r["score"] >= 68])
        st.markdown(f'<div class="metric-box"><div class="metric-label">หุ้นน่าซื้อ</div><div class="metric-value green">{nb} ตัว</div></div>', unsafe_allow_html=True)
    with col4:
        nt = datetime.now().strftime("%H:%M น.")
        st.markdown(f'<div class="metric-box"><div class="metric-label">อัปเดตล่าสุด</div><div class="metric-value" style="font-size:16px">{nt}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🏆 Top 5 หุ้นเด่นวันนี้","📊 ผลทุกตัว","🎯 วิเคราะห์แต่ละตัว","💰 คำนวณไม้"])

    with tab1:
        st.markdown('<div class="top5-header"><span class="top5-badge">TOP 5</span><span class="top5-title">หุ้นที่มีแนวโน้มขึ้น 3-10% ใน 2 อาทิตย์</span></div>', unsafe_allow_html=True)
        st.caption("⚠️ โอกาสขึ้นประเมินจากสัญญาณเทคนิคัล ไม่ใช่การรับประกัน — ใช้ประกอบการตัดสินใจเท่านั้น")
        top5 = [r for r in results if r["score"] >= 50][:5]
        if not top5:
            st.warning("⚠️ ยังไม่มีหุ้นที่ผ่านเกณฑ์ขั้นต่ำ (คะแนน ≥ 50)")
        else:
            for rank_i, r in enumerate(top5):
                prob = r["prob"]
                pc = "prob-high" if prob >= 70 else ("prob-med" if prob >= 50 else "prob-low")
                sc = classify_color(r["score"])
                cc = ("signal-elite" if r["score"] >= 82 else "signal-buy" if r["score"] >= 68 else "signal-watch")
                tags = []
                if r["rvol"] > 1.5: tags.append('<span class="tag tag-green">วอลุ่มสูง</span>')
                rs_v = r["rs_rank"]
                if not np.isnan(rs_v) and rs_v >= 80: tags.append('<span class="tag tag-blue">RS แข็ง</span>')
                if r["macd"] > r["macd_sig"] and r["macd"] > 0: tags.append('<span class="tag tag-green">MACD ขึ้น</span>')
                if r["earn_days"] and r["earn_days"] <= EARNINGS_BLACKOUT: tags.append('<span class="tag tag-red">⚠️ Earnings ใกล้</span>')
                if r["gap_pct"] and abs(r["gap_pct"]) >= 3:
                    d = "⬆️" if r["gap_pct"] > 0 else "⬇️"
                    tags.append(f'<span class="tag tag-yellow">{d} Gap {r["gap_pct"]:+.1f}%</span>')
                th = " ".join(tags)
                sh = "".join(f"<div style='font-size:13px;color:#8b949e;margin:2px 0'>{e} {tx}</div>" for e, tx in r["signals"][:4])
                st.markdown(f"""
                <div class="signal-card {cc}">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
                    <div style="flex:1;min-width:200px">
                      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                        <span style="font-size:20px;font-weight:700;color:#8b949e">#{rank_i+1}</span>
                        <span class="ticker-pill">{r["ticker"]}</span>
                        <span style="font-size:14px;color:{sc};font-weight:700">{r["action"]}</span>
                        <span style="font-size:13px;color:#8b949e">{r["score"]}/100</span>
                      </div>
                      <div style="margin-bottom:8px">{th}</div>
                      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:#8b949e;margin-bottom:8px">
                        ราคา: <span style="color:#e6edf3">${r['price']:.2f}</span> &nbsp;|&nbsp;
                        Stop: <span style="color:#f85149">${r['stop']:.2f}</span> &nbsp;|&nbsp;
                        เป้า1: <span style="color:#3fb950">${r['target1']:.2f}</span> &nbsp;|&nbsp;
                        เป้า2: <span style="color:#3fb950">${r['target2']:.2f}</span>
                      </div>
                      <div>{sh}</div>
                    </div>
                    <div style="text-align:center;min-width:100px">
                      <div style="font-size:11px;color:#8b949e;margin-bottom:4px">โอกาสขึ้น 3-10%</div>
                      <div class="probability-badge {pc}">{prob:.0f}%</div>
                      <div style="font-size:10px;color:#8b949e;margin-top:4px">RSI {r['rsi']:.0f} &nbsp;|&nbsp; RVOL {r['rvol']:.1f}x</div>
                    </div>
                  </div>
                  <div class="score-bar-wrap" style="margin-top:10px">
                    <div class="score-bar-fill" style="width:{r['score']}%;background:{sc}"></div>
                  </div>
                </div>""", unsafe_allow_html=True)
            st.markdown('<div class="disclaimer">📋 <strong>อ่านก่อน:</strong> "โอกาสขึ้น" คือการประเมินจากสัญญาณเทคนิคัลที่ตั้งค่าไว้ ไม่ใช่ความน่าจะเป็นที่พิสูจน์ทางสถิติ · ข้อมูลล่าช้า 15+ นาที · ควรตรวจข่าว/ปัจจัยพื้นฐาน + ราคาจาก Dime ก่อนตัดสินใจซื้อเสมอ</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="section-title">ผล Scan ทั้งหมด</div>', unsafe_allow_html=True)
        filtered = [r for r in results if r["score"] >= min_score]
        if not filtered:
            st.info("ไม่มีหุ้นที่ผ่านเกณฑ์คะแนนที่ตั้งไว้ — ลองลดคะแนนขั้นต่ำใน sidebar")
        else:
            table_data = []
            for r in filtered:
                rs_v = r["rs_rank"]
                table_data.append({
                    "หุ้น": r["ticker"], "สัญญาณ": r["action"], "คะแนน": r["score"],
                    "โอกาสขึ้น%": f"{r['prob']:.0f}%",
                    "ราคา": f"${r['price']:.2f}", "Stop": f"${r['stop']:.2f}",
                    "เป้าหมาย": f"${r['target1']:.2f}",
                    "RS Rank": f"{rs_v:.0f}" if not np.isnan(rs_v) else "—",
                    "RSI": f"{r['rsi']:.0f}", "RVOL": f"{r['rvol']:.1f}x",
                    "Momentum5วัน": f"{r['mom5']:.1f}%",
                    "Gap": f"{r['gap_pct']:+.1f}%" if r['gap_pct'] else "—",
                    "Earnings": f"{r['earn_days']}วัน" if r['earn_days'] is not None else "—",
                })
            df_table = pd.DataFrame(table_data)
            st.dataframe(df_table, use_container_width=True, hide_index=True)
            csv = df_table.to_csv(index=False).encode("utf-8-sig")
            st.download_button("⬇️ ดาวน์โหลด CSV", csv, f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", "text/csv")

    with tab3:
        st.markdown('<div class="section-title">วิเคราะห์รายตัว</div>', unsafe_allow_html=True)
        ticker_options = [r["ticker"] for r in results]
        if not ticker_options:
            st.info("ไม่มีข้อมูลหุ้น")
        else:
            selected = st.selectbox("เลือกหุ้นที่ต้องการดูรายละเอียด", ticker_options)
            sel_data = next((r for r in results if r["ticker"] == selected), None)
            if sel_data:
                r = sel_data
                sc = classify_color(r["score"])
                st.markdown(f'<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px"><span class="ticker-pill" style="font-size:20px;padding:6px 16px">{r["ticker"]}</span><span style="font-size:22px;font-weight:700;color:{sc}">{r["action"]}</span><span style="font-size:18px;color:#8b949e">{r["score"]}/100 คะแนน</span></div>', unsafe_allow_html=True)
                c1,c2,c3,c4,c5 = st.columns(5)
                c1.metric("ราคาปิด", f"${r['price']:.2f}")
                rs_v = r["rs_rank"]
                c2.metric("RS Rank", f"{rs_v:.0f}" if not np.isnan(rs_v) else "—")
                c3.metric("RSI", f"{r['rsi']:.0f}")
                c4.metric("RVOL", f"{r['rvol']:.1f}x")
                c5.metric("Momentum 5วัน", f"{r['mom5']:+.1f}%")
                st.divider()
                cl, cr = st.columns(2)
                with cl:
                    st.markdown("**📋 คะแนนแยกรายหัวข้อ**")
                    if r["breakdown"].get("_chop", False):
                        st.warning("⚠️ วอลุ่มต่ำมาก — คะแนนถูกจำกัดไว้ที่ 35")
                    maxes = {"แนวโน้ม EMA":15,"RS Rank":25,"Breakout":15,"วอลุ่ม":15,"MACD":10,"RSI Zone":10,"Momentum 5วัน":5,"ตลาดรวม":5}
                    for key, val in r["breakdown"].items():
                        if key.startswith("_"): continue
                        mx = maxes.get(key, 10)
                        try: vn = int(val)
                        except: continue
                        bw = int(vn/mx*100) if mx>0 else 0
                        bc = "#3fb950" if vn==mx else ("#d29922" if vn>0 else "#f85149")
                        st.markdown(f'<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:13px"><span style="color:#e6edf3">{key}</span><span style="color:{bc};font-family:\'IBM Plex Mono\',monospace">{vn}/{mx}</span></div><div class="score-bar-wrap" style="margin-top:4px"><div class="score-bar-fill" style="width:{bw}%;background:{bc}"></div></div></div>', unsafe_allow_html=True)
                with cr:
                    st.markdown("**🎯 แผนเทรด**")
                    r2r = (r["target1"]-r["price"])/(r["price"]-r["stop"]) if r["price"]!=r["stop"] else 0
                    st.markdown(f"""
                    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px">
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">จุดเข้า (ราคาปิด)</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#e6edf3">${r['price']:.2f}</div></div>
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">Stop Loss (ATR×{atr_mult})</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#f85149">${r['stop']:.2f} <span style="font-size:12px">(-{(r['price']-r['stop'])/r['price']*100:.1f}%)</span></div></div>
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">เป้าหมาย 1 (1.5R) ≈ +{(r['target1']-r['price'])/r['price']*100:.1f}%</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#3fb950">${r['target1']:.2f}</div></div>
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">เป้าหมาย 2 (3R) ≈ +{(r['target2']-r['price'])/r['price']*100:.1f}%</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#3fb950">${r['target2']:.2f}</div></div>
                        <div style="border-top:1px solid #30363d;padding-top:10px;margin-top:4px"><div style="font-size:12px;color:#8b949e">อัตราส่วน Risk:Reward</div><div style="font-size:16px;font-weight:700;color:#58a6ff">1 : {r2r:.1f}</div></div>
                    </div>""", unsafe_allow_html=True)
                    if r["earn_days"] is not None and r["earn_days"] <= 14:
                        st.warning(f"⚠️ มี Earnings ใน {r['earn_days']} วัน ({r['earn_date']}) — ราคาอาจผันผวนรุนแรง")
                st.markdown("**🔍 สัญญาณที่พบ**")
                for emoji, txt in r["signals"]:
                    color = "#3fb950" if emoji=="✅" else ("#f85149" if emoji=="❌" else "#d29922")
                    st.markdown(f'<div style="padding:6px 0;color:{color};font-size:14px">{emoji} {txt}</div>', unsafe_allow_html=True)
                if selected in all_dfs:
                    chart_df = all_dfs[selected][["Close","EMA9","EMA20","EMA50"]].tail(60)
                    st.markdown("**📈 กราฟราคา 60 วัน**")
                    st.line_chart(chart_df, height=220)

    with tab4:
        st.markdown('<div class="section-title">💰 คำนวณขนาดไม้ก่อนเข้าเทรด</div>', unsafe_allow_html=True)
        ticker_options = [r["ticker"] for r in results]
        if not ticker_options:
            st.info("ไม่มีข้อมูลหุ้น")
        else:
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
                    stop_dist = custom_entry - custom_stop
                    risk_usd  = custom_cap * custom_risk / 100.0
                    if stop_dist > 0:
                        shares_calc  = int(risk_usd / stop_dist)
                        pos_val_calc = shares_calc * custom_entry
                        t1c = custom_entry + (custom_entry - custom_stop) * 1.5
                        t2c = custom_entry + (custom_entry - custom_stop) * 3.0
                        rr  = (t1c - custom_entry) / stop_dist
                        st.markdown(f"""
                        <div style="background:#161b22;border:1px solid #238636;border-radius:10px;padding:20px;margin-top:8px">
                            <div style="font-size:16px;font-weight:700;color:#3fb950;margin-bottom:16px">ผลคำนวณ</div>
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                                <div><div style="font-size:11px;color:#8b949e">จำนวนหุ้น</div><div style="font-family:'IBM Plex Mono',monospace;font-size:22px;color:#e6edf3">{shares_calc:,}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">มูลค่าไม้</div><div style="font-family:'IBM Plex Mono',monospace;font-size:22px;color:#e6edf3">${pos_val_calc:,.0f}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">ความเสี่ยงสูงสุด</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#f85149">${risk_usd:,.0f}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">R:R Ratio</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#58a6ff">1:{rr:.1f}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">เป้า 1 (+{(t1c-custom_entry)/custom_entry*100:.1f}%)</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#3fb950">${t1c:.2f}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">เป้า 2 (+{(t2c-custom_entry)/custom_entry*100:.1f}%)</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#3fb950">${t2c:.2f}</div></div>
                            </div>
                            <div style="margin-top:14px;padding-top:12px;border-top:1px solid #30363d;font-size:13px;color:#8b949e">% ของพอร์ตที่ใช้: {pos_val_calc/custom_cap*100:.1f}%</div>
                        </div>""", unsafe_allow_html=True)
                        if rr < 1.5:
                            st.warning("⚠️ R:R ต่ำกว่า 1:1.5 — ควรขยับ Stop หรือเลื่อนเป้าหมายใหม่")
                    else:
                        st.error("❌ ราคาเข้าต้องสูงกว่า Stop Loss")

    st.divider()
    st.caption("⚠️ ระบบนี้เป็นเครื่องมือช่วยวิเคราะห์เทคนิคัลเท่านั้น · ข้อมูลล่าช้า 15+ นาที (Yahoo Finance) · ไม่ใช่คำแนะนำการลงทุน · ตรวจสอบราคาจริงบนแอป Dime ก่อนส่งคำสั่งทุกครั้ง")

else:
    st.info("👆 พิมพ์ชื่อหุ้น (เช่น NVDA, AAPL, TSLA) แล้วกด Scan")
