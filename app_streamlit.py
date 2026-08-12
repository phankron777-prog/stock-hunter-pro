import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
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
.signal-blocked { border-left: 4px solid #f85149; background: linear-gradient(90deg, #2d0d0d 0%, #161b22 100%); opacity: 0.92; }
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
.block-banner { background: #2d0d0d; border: 1px solid #f85149; border-radius: 6px; padding: 8px 12px; margin-top: 10px; font-size: 12px; color: #f85149; font-weight: 600; line-height: 1.6; }
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

# --- Earnings blackout thresholds (Fix #2) ---
EARNINGS_BLOCK_DAYS = 3      # <= this many days to earnings -> hard block on new entries
EARNINGS_REDUCE_DAYS = 7     # <= this many days -> score penalty + watch
EARNINGS_REDUCE_PENALTY = 15

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
    except Exception:
        return None

@st.cache_data(ttl=300)
def load_live_price(ticker):
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        price = getattr(fi, "last_price", None)
        return float(price) if price else None
    except Exception:
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

# ============================================================
# INDICATORS  (Fix #9: RSI/ATR now use Wilder's RMA, alpha = 1/14,
# instead of a plain ewm(span=14), so values line up with
# TradingView / most brokers)
# ============================================================

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
    df["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()  # Wilder RMA

    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()
    df["High10"] = c.rolling(10).max().shift(1)

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Sig"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Sig"]

    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()   # Wilder RMA
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()  # Wilder RMA
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

# ============================================================
# SCORING  (Fix #6: True Breakout vs Near Breakout)
# ============================================================

def swing_score(row, rs_rank, spy_ok):
    """คืนค่า (score, breakdown_dict, breakout_status)
    breakout_status: 'true' | 'near' | 'none'
    """
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

    # --- True Breakout logic ---
    # เดิม: close/High10 >= 0.99 ก็นับเป็น Breakout ทั้งที่ยังไม่ทะลุจริง
    # ใหม่: ต้องทะลุ High10 จริง (>100%) พร้อมวอลุ่มยืนยัน ถึงจะเป็น "Breakout จริง"
    h10 = _safe_float(row["High10"])
    close = _safe_float(row["Close"])
    rvol_for_breakout = _safe_float(row["RVOL"]) or 0
    breakout_status = "none"
    if h10 and h10 > 0 and close:
        ratio = close / h10
        if ratio > 1.0 and rvol_for_breakout > 1.5:
            pts = 15
            breakout_status = "true"
        elif ratio >= 0.98:
            pts = 8
            breakout_status = "near"
        else:
            pts = 0
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

    return s, bd, breakout_status

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

def trend_strength_score(df, rs_rank, spy_ok):
    """เดิมชื่อ uptrend_probability — เปลี่ยนแนวคิดจาก 'ความน่าจะเป็นทางสถิติ'
    มาเป็น 'คะแนนความแข็งแกร่งของแนวโน้ม' (Fix #5) เพราะยังไม่ผ่าน backtest จริง
    ค่าที่คืนยังเป็น 0-100 เท่าเดิม แต่ต้องไม่สื่อว่าเป็น win-rate
    """
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
        if close > h10:
            score += 20
            signals.append(("✅", "ทะลุ High 10 วัน (Breakout จริง)"))
        elif close >= h10 * 0.98:
            score += 10
            signals.append(("🟡", "ใกล้ High 10 วัน — ยังไม่ทะลุ"))

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

# ============================================================
# POSITION SIZING — single shared engine used by BOTH the main
# scan results AND the manual calculator (Fix #7), now includes
# slippage (Fix #10) and a configurable max-position cap (Fix #7)
# ============================================================

def calc_position(capital, price, atr, risk_pct=1.0, atr_mult=2.0, max_pct=20.0, slippage_pct=0.15):
    """
    คืนค่า (shares, position_value, risk_usd, effective_entry_price)
    - effective_entry_price = ราคาที่คาดว่าจะได้จริงหลังคิด slippage
    - risk_usd คิดจากระยะ stop (ATR*mult) บวก slippage ต่อหุ้น เพื่อให้ Risk ใกล้เคียงความจริงมากขึ้น
    """
    try:
        capital  = float(capital)
        price    = float(price)
        atr      = float(atr)
        risk_pct = float(risk_pct)
        atr_mult = float(atr_mult)
        max_pct  = float(max_pct)
        slippage_pct = float(slippage_pct)
    except (TypeError, ValueError):
        return 0, 0.0, 0.0, price

    if not all(np.isfinite(v) for v in [capital, price, atr, risk_pct, atr_mult, max_pct, slippage_pct]):
        return 0, 0.0, 0.0, price
    if price <= 0 or atr <= 0:
        return 0, 0.0, 0.0, price

    stop_dist = atr * atr_mult
    if stop_dist <= 0:
        return 0, 0.0, 0.0, price

    slip_amount = price * slippage_pct / 100.0
    effective_entry = price + slip_amount
    risk_per_share = stop_dist + slip_amount  # ระยะ stop จริง + ต้นทุนแฝงจาก slippage

    risk_usd   = capital * risk_pct / 100.0
    shares     = max(0, int(risk_usd / risk_per_share)) if risk_per_share > 0 else 0
    max_shares = max(0, int(capital * max_pct / 100.0 / effective_entry)) if effective_entry > 0 else 0
    shares     = min(shares, max_shares)

    pos_val     = float(shares) * effective_entry
    actual_risk = float(shares) * risk_per_share
    return shares, pos_val, actual_risk, effective_entry

# ============================================================
# EARNINGS BLACKOUT — real entry block, not just a warning tag (Fix #2)
# ============================================================

def earnings_status(days):
    """คืนค่า (status, score_penalty, message)
    status: 'ok' | 'reduce' | 'block'
    """
    if days is None:
        return "ok", 0, None
    if days <= 0:
        return "block", 0, "🚫 วันประกาศงบ (หรือผ่านไปแล้วในรอบล่าสุด) — ห้ามเข้าไม้ใหม่"
    if days <= EARNINGS_BLOCK_DAYS:
        return "block", 0, f"🚫 Earnings ใน {days} วัน — ห้ามเข้าไม้ใหม่ (Blackout ≤{EARNINGS_BLOCK_DAYS} วัน)"
    if days <= EARNINGS_REDUCE_DAYS:
        return "reduce", EARNINGS_REDUCE_PENALTY, f"⚠️ Earnings ใน {days} วัน — ลดคะแนน {EARNINGS_REDUCE_PENALTY} แต้ม"
    return "ok", 0, None

# ============================================================
# LIVE PRICE RECONCILIATION — don't chase, recalc entry/stop/target
# off the live price when it's within tolerance (Fix #3)
# ============================================================

def resolve_entry(signal_price, live_price, max_chase_pct):
    """คืนค่า (entry_price, chase_blocked, gap_pct)"""
    if live_price is None or live_price <= 0 or signal_price is None or signal_price <= 0:
        return signal_price, False, None
    gap_pct = (live_price - signal_price) / signal_price * 100.0
    if gap_pct > max_chase_pct:
        return signal_price, True, gap_pct
    return live_price, False, gap_pct

# ============================================================
# DERIVED RESULT BUILDER — everything here depends only on the
# sidebar settings (capital / risk / slippage / etc.), NOT on the
# network, so it recomputes instantly on every rerun without
# needing a new Scan (Fix #1 + Fix #3 combined)
# ============================================================

def build_derived(raw, capital, risk_pct, atr_mult, max_position_pct, slippage_pct, max_chase_pct):
    r = dict(raw)

    e_status, e_penalty, e_msg = earnings_status(raw["earn_days"])
    score = max(0, raw["base_score"] - e_penalty)

    block_reasons = []
    if e_status == "block":
        block_reasons.append(e_msg)

    entry_price, chase_blocked, gap_pct = resolve_entry(raw["price"], raw["live_price"], max_chase_pct)
    if chase_blocked:
        block_reasons.append(f"🚫 ราคาปัจจุบันสูงกว่าสัญญาณ {gap_pct:+.1f}% (เกินลิมิต {max_chase_pct:.1f}%) — ห้ามไล่ราคา")

    if chase_blocked:
        shares, pos_val, risk_usd, eff_entry = 0, 0.0, 0.0, raw["price"]
    else:
        shares, pos_val, risk_usd, eff_entry = calc_position(
            capital, entry_price, raw["atr"], risk_pct, atr_mult, max_position_pct, slippage_pct
        )

    stop_price = round(entry_price - raw["atr"] * atr_mult, 2)
    target1    = round(entry_price + raw["atr"] * atr_mult * 1.5, 2)
    target2    = round(entry_price + raw["atr"] * atr_mult * 3.0, 2)

    r.update({
        "score": score,
        "earnings_msg": e_msg,
        "earnings_status": e_status,
        "entry_price": entry_price,
        "gap_pct": gap_pct,
        "chase_blocked": chase_blocked,
        "shares": shares,
        "pos_val": pos_val,
        "risk_usd": risk_usd,
        "stop": stop_price,
        "target1": target1,
        "target2": target2,
        "block_reasons": block_reasons,
    })
    return r

def apply_portfolio_risk(results, max_portfolio_risk_pct, capital):
    """จำลองว่าถ้าเข้าไม้ตามลำดับคะแนนสูง->ต่ำ Risk รวมจะเกิน limit ตอนไหน
    แล้ว Block ไม้ที่ทำให้เกิน (Fix #4)
    """
    cum_risk_pct = 0.0
    for r in results:
        if r["block_reasons"]:
            r["portfolio_blocked"] = False
            continue
        trade_risk_pct = (r["risk_usd"] / capital * 100.0) if capital > 0 else 0.0
        if cum_risk_pct + trade_risk_pct > max_portfolio_risk_pct:
            r["block_reasons"].append(
                f"🚫 Portfolio Risk เต็ม (สะสม {cum_risk_pct:.1f}% จาก max {max_portfolio_risk_pct:.1f}% ถ้าเข้าไม้ก่อนหน้าตามลำดับคะแนนแล้ว)"
            )
            r["portfolio_blocked"] = True
        else:
            cum_risk_pct += trade_risk_pct
            r["portfolio_blocked"] = False
    return cum_risk_pct

def final_action(r):
    if r["block_reasons"]:
        return "🚫 ห้ามเข้าไม้ใหม่"
    return classify(r["score"])

# ============================================================
# LIGHTWEIGHT HISTORICAL BACKTEST (Fix: "Statistical Validation")
# ไม่ใช่ backtest แบบเต็มระบบ (ไม่มี cross-sectional RS rank ราย
# วันในอดีต, ไม่รวมค่าธรรมเนียม/slippage) — ใช้เพื่อดู "แนวโน้ม
# คร่าวๆ" ว่าคะแนนสูงมีโอกาสตามมาด้วยผลตอบแทนบวกมากกว่าจริงหรือไม่
# ============================================================

def backtest_scores(all_dfs, spy_df, forward_days=10, target_pct=3.0):
    rows = []
    if spy_df is None or "EMA50" not in spy_df.columns:
        return pd.DataFrame()
    spy_close = spy_df["Close"]
    spy_ema50 = spy_df["EMA50"]

    for ticker, df in all_dfs.items():
        if df is None or len(df) < 90:
            continue
        n = len(df)
        for i in range(60, n - forward_days):
            row = df.iloc[i]
            try:
                s_ret = df["Close"].iloc[i] / df["Close"].iloc[i - 21] - 1
                b_ret = spy_close.iloc[i] / spy_close.iloc[i - 21] - 1 if i < len(spy_close) else 0
                rel = s_ret - b_ret
            except Exception:
                rel = 0
            # ไม่มี cross-sectional rank ย้อนหลังแบบ real-time จึงใช้ proxy RS แบบหยาบ
            if rel > 0.05: proxy_rs = 90
            elif rel > 0.02: proxy_rs = 75
            elif rel > 0: proxy_rs = 55
            else: proxy_rs = 30
            try:
                spy_ok_i = bool(spy_close.iloc[i] > spy_ema50.iloc[i])
            except Exception:
                spy_ok_i = True
            try:
                score, _, _ = swing_score(row, proxy_rs, spy_ok_i)
            except Exception:
                continue
            try:
                fwd_ret = (df["Close"].iloc[i + forward_days] / row["Close"] - 1) * 100
            except Exception:
                continue
            if not np.isfinite(fwd_ret):
                continue
            rows.append({"ticker": ticker, "score": score, "fwd_ret": fwd_ret})

    return pd.DataFrame(rows)

def bucket_score(s):
    if s >= 82: return "🚀 ซื้อเลย (82-100)"
    if s >= 68: return "🔥 น่าซื้อ (68-81)"
    if s >= 52: return "👀 จับตาดู (52-67)"
    return "❌ หลีกเลี่ยง (0-51)"

# ============================================================
# HEADER
# ============================================================
st.markdown("""
<div class="hero-header">
    <div class="hero-title">🦅 นักล่าหุ้น Swing</div>
    <div class="hero-subtitle">สำหรับสไตล์ถือ 1-2 อาทิตย์ · เหมาะกับแอป Dime · ข้อมูลอัปเดตเฉพาะตอนกด Scan</div>
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
    st.markdown("**🛡️ ควบคุมความเสี่ยง**")
    max_position_pct = st.slider("Max Position ต่อไม้ (% ของทุน)", 5.0, 50.0, 20.0, 5.0,
                                  help="ใช้ทั้งในผลสแกนหลักและแท็บคำนวณไม้ด้วยกัน — ไม่ให้ตัวเลขสองที่ไม่ตรงกัน")
    max_portfolio_risk_pct = st.slider("Max Portfolio Risk รวม (%)", 1.0, 10.0, 3.0, 0.5,
                                        help="ถ้าเข้าไม้ตามลำดับคะแนนแล้ว Risk รวมเกินนี้ ไม้ถัดไปจะถูก Block")
    slippage_pct = st.slider("Slippage ประมาณ (%)", 0.0, 1.0, 0.15, 0.05,
                              help="ต้นทุนแฝงจากราคาที่ได้จริงเทียบราคาสัญญาณ ใช้ปรับ Risk ให้ใกล้ความจริง")
    max_chase_pct = st.slider("ห้ามไล่ราคาเกิน (%)", 0.5, 5.0, 1.5, 0.5,
                               help="ถ้าราคาปัจจุบัน (Dime) สูงกว่าราคาสัญญาณเกินนี้ จะ Block ไม่ให้เข้าไม้ใหม่")

    st.divider()
    st.markdown("**ℹ️ คำเตือน**")
    st.caption(
        "ข้อมูลล่าช้า 15+ นาที · ไม่ใช่คำแนะนำการลงทุน · คะแนนยังเป็น Trend Strength ไม่ใช่ Win Rate ที่พิสูจน์ทางสถิติ "
        "· ตรวจสอบราคาจริงกับ broker ก่อนส่งคำสั่งทุกครั้ง"
    )

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

# ------------------------------------------------------------
# Fix #1: Scan button actually gates computation. Data is only
# fetched/re-scored on an explicit Scan click (or on first load).
# Everything else (sliders etc.) just recomputes cheap, local,
# non-network-dependent derived values from session_state below.
# ------------------------------------------------------------
if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
    st.session_state.all_dfs = {}
    st.session_state.spy_df = None
    st.session_state.spy_ok = False
    st.session_state.scan_tickers = []
    st.session_state.scan_time = None

should_scan = bool(tickers) and (scan_btn or st.session_state.scan_results is None)

if should_scan:
    spy_df = load_data(BENCHMARK)
    spy_ok = False
    if spy_df is not None:
        spy_df = calc_indicators(spy_df)
        spy_ok = bool((_safe_float(spy_df["Close"].iloc[-1]) or 0) > (_safe_float(spy_df["EMA50"].iloc[-1]) or 0))

    ranking_uni = list(dict.fromkeys(tickers + [t for t in REFERENCE_UNIVERSE if t not in tickers]))
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

    raw_results = []
    for t in tickers:
        if t not in all_dfs:
            continue
        df = all_dfs[t]
        last = df.iloc[-1]
        rs_rank = rs_ranks.get(t, np.nan)

        price_f = _safe_float(last["Close"])
        atr_f   = _safe_float(last["ATR"])
        rvol_f  = _safe_float(last["RVOL"]) or 0.0
        rsi_f   = _safe_float(last["RSI"]) or 50.0
        mom5_f  = _safe_float(last["Mom5"]) or 0.0
        macd_f  = _safe_float(last["MACD"]) or 0.0
        macd_sig_f = _safe_float(last["MACD_Sig"]) or 0.0
        rs_f    = _safe_float(rs_rank)

        if price_f is None or atr_f is None:
            continue

        base_score, breakdown, breakout_status = swing_score(last, rs_rank, spy_ok)
        strength, signals = trend_strength_score(df, rs_rank, spy_ok)

        live_price = load_live_price(t)
        earn_date, earn_days = load_earnings(t)

        raw_results.append({
            "ticker": t,
            "base_score": base_score,
            "breakdown": breakdown,
            "breakout_status": breakout_status,
            "strength": strength,
            "signals": signals,
            "price": price_f,
            "live_price": live_price,
            "rsi": rsi_f,
            "rvol": rvol_f,
            "atr": atr_f,
            "rs_rank": rs_f if rs_f is not None else float("nan"),
            "mom5": mom5_f,
            "macd": macd_f,
            "macd_sig": macd_sig_f,
            "earn_days": earn_days,
            "earn_date": earn_date,
        })

    st.session_state.scan_results = raw_results
    st.session_state.all_dfs = all_dfs
    st.session_state.spy_df = spy_df
    st.session_state.spy_ok = spy_ok
    st.session_state.scan_tickers = tickers
    st.session_state.scan_time = datetime.now()

if tickers and st.session_state.scan_results is not None:
    stale = set(tickers) != set(st.session_state.scan_tickers)
    scan_time_str = st.session_state.scan_time.strftime("%H:%M:%S") if st.session_state.scan_time else "-"
    if stale:
        st.info(
            f"🔄 คุณเปลี่ยนรายชื่อหุ้นแล้ว แต่ผลลัพธ์ด้านล่างยังเป็นของการ Scan ล่าสุด "
            f"({', '.join(st.session_state.scan_tickers)}) เมื่อ {scan_time_str} — กด 🔍 Scan เพื่ออัปเดต"
        )
    else:
        st.caption(f"📌 ผลลัพธ์จากการ Scan เมื่อ {scan_time_str} · หุ้น: {', '.join(st.session_state.scan_tickers)}")

    all_dfs = st.session_state.all_dfs
    spy_ok = st.session_state.spy_ok
    spy_df = st.session_state.spy_df

    results = [
        build_derived(raw, capital, risk_pct, atr_mult, max_position_pct, slippage_pct, max_chase_pct)
        for raw in st.session_state.scan_results
    ]
    results.sort(key=lambda x: x["score"], reverse=True)
    used_portfolio_risk_pct = apply_portfolio_risk(results, max_portfolio_risk_pct, capital)
    for r in results:
        r["action"] = final_action(r)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        mc = "green" if spy_ok else "red"
        mt = "🟢 ขาขึ้น" if spy_ok else "🔴 ขาลง"
        st.markdown(f'<div class="metric-box"><div class="metric-label">สภาพตลาด (SPY)</div><div class="metric-value {mc}">{mt}</div></div>', unsafe_allow_html=True)
    with col2:
        ts = results[0]["score"] if results else 0
        st.markdown(f'<div class="metric-box"><div class="metric-label">คะแนนสูงสุด</div><div class="metric-value">{ts}</div></div>', unsafe_allow_html=True)
    with col3:
        nb = len([r for r in results if r["score"] >= 68 and not r["block_reasons"]])
        st.markdown(f'<div class="metric-box"><div class="metric-label">หุ้นน่าซื้อ (ไม่ติด Block)</div><div class="metric-value green">{nb} ตัว</div></div>', unsafe_allow_html=True)
    with col4:
        pr_color = "red" if used_portfolio_risk_pct >= max_portfolio_risk_pct else "green"
        st.markdown(f'<div class="metric-box"><div class="metric-label">Portfolio Risk ใช้ไป</div><div class="metric-value {pr_color}">{used_portfolio_risk_pct:.1f}% / {max_portfolio_risk_pct:.1f}%</div></div>', unsafe_allow_html=True)
    with col5:
        nt = datetime.now().strftime("%H:%M น.")
        st.markdown(f'<div class="metric-box"><div class="metric-label">เวลาปัจจุบัน</div><div class="metric-value" style="font-size:16px">{nt}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["🏆 Top 5 หุ้นเด่นวันนี้", "📊 ผลทุกตัว", "🎯 วิเคราะห์แต่ละตัว", "💰 คำนวณไม้", "📉 Backtest เบื้องต้น"]
    )

    with tab1:
        st.markdown('<div class="top5-header"><span class="top5-badge">TOP 5</span><span class="top5-title">หุ้นคะแนนสูงสุดที่ผ่านเกณฑ์ (เรียงตาม Trend Strength)</span></div>', unsafe_allow_html=True)
        st.caption("⚠️ 'Trend Strength' ประเมินจากสัญญาณเทคนิคัลเท่านั้น ไม่ใช่ความน่าจะเป็นทางสถิติที่ผ่านการ Backtest ยืนยัน — ดูผล Backtest เบื้องต้นได้ที่แท็บสุดท้าย")
        top5 = [r for r in results if r["score"] >= 50][:5]
        if not top5:
            st.warning("⚠️ ยังไม่มีหุ้นที่ผ่านเกณฑ์ขั้นต่ำ (คะแนน ≥ 50)")
        else:
            for rank_i, r in enumerate(top5):
                strength = r["strength"]
                pc = "prob-high" if strength >= 70 else ("prob-med" if strength >= 50 else "prob-low")
                sc = classify_color(r["score"])
                blocked = bool(r["block_reasons"])
                if blocked:
                    cc = "signal-blocked"
                else:
                    cc = ("signal-elite" if r["score"] >= 82 else "signal-buy" if r["score"] >= 68 else "signal-watch")

                tags = []
                if r["rvol"] > 1.5: tags.append('<span class="tag tag-green">วอลุ่มสูง</span>')
                rs_v = r["rs_rank"]
                if not np.isnan(rs_v) and rs_v >= 80: tags.append('<span class="tag tag-blue">RS แข็ง</span>')
                if r["macd"] > r["macd_sig"] and r["macd"] > 0: tags.append('<span class="tag tag-green">MACD ขึ้น</span>')
                if r["breakout_status"] == "true": tags.append('<span class="tag tag-green">Breakout จริง</span>')
                elif r["breakout_status"] == "near": tags.append('<span class="tag tag-yellow">ใกล้ Breakout</span>')
                if r["earnings_status"] == "reduce": tags.append('<span class="tag tag-yellow">⚠️ Earnings ใกล้</span>')
                if r["earnings_status"] == "block": tags.append('<span class="tag tag-red">🚫 Earnings Blackout</span>')
                if r["chase_blocked"]: tags.append('<span class="tag tag-red">🚫 ห้ามไล่ราคา</span>')
                if r["gap_pct"] is not None and abs(r["gap_pct"]) >= 3 and not r["chase_blocked"]:
                    d = "⬆️" if r["gap_pct"] > 0 else "⬇️"
                    tags.append(f'<span class="tag tag-yellow">{d} Gap {r["gap_pct"]:+.1f}%</span>')
                th = " ".join(tags)
                sh = "".join(f"<div style='font-size:13px;color:#8b949e;margin:2px 0'>{e} {tx}</div>" for e, tx in r["signals"][:4])

                action_display = r["action"] if not blocked else "🚫 ห้ามเข้าไม้ใหม่"
                action_color = "#f85149" if blocked else sc

                block_html = ""
                if blocked:
                    reasons_html = "<br>".join(r["block_reasons"])
                    block_html = f'<div class="block-banner">{reasons_html}</div>'

                st.markdown(f"""
                <div class="signal-card {cc}">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px">
                    <div style="flex:1;min-width:200px">
                      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                        <span style="font-size:20px;font-weight:700;color:#8b949e">#{rank_i+1}</span>
                        <span class="ticker-pill">{r["ticker"]}</span>
                        <span style="font-size:14px;color:{action_color};font-weight:700">{action_display}</span>
                        <span style="font-size:13px;color:#8b949e">{r["score"]}/100</span>
                      </div>
                      <div style="margin-bottom:8px">{th}</div>
                      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:#8b949e;margin-bottom:8px">
                        Entry: <span style="color:#e6edf3">${r['entry_price']:.2f}</span> &nbsp;|&nbsp;
                        Stop: <span style="color:#f85149">${r['stop']:.2f}</span> &nbsp;|&nbsp;
                        เป้า1: <span style="color:#3fb950">${r['target1']:.2f}</span> &nbsp;|&nbsp;
                        เป้า2: <span style="color:#3fb950">${r['target2']:.2f}</span>
                      </div>
                      <div>{sh}</div>{block_html}
                    </div>
                    <div style="text-align:center;min-width:100px">
                      <div style="font-size:11px;color:#8b949e;margin-bottom:4px">Trend Strength</div>
                      <div class="probability-badge {pc}">{strength:.0f}/100</div>
                      <div style="font-size:10px;color:#8b949e;margin-top:4px">RSI {r['rsi']:.0f} &nbsp;|&nbsp; RVOL {r['rvol']:.1f}x</div>
                    </div>
                  </div>
                  <div class="score-bar-wrap" style="margin-top:10px">
                    <div class="score-bar-fill" style="width:{r['score']}%;background:{sc}"></div>
                  </div>
                </div>""", unsafe_allow_html=True)
            st.markdown('<div class="disclaimer">📋 <strong>อ่านก่อน:</strong> "Trend Strength" คือการประเมินจากสัญญาณเทคนิคัลที่ตั้งค่าไว้ ไม่ใช่ความน่าจะเป็นที่พิสูจน์ทางสถิติ · ข้อมูลล่าช้า 15+ นาที · ป้าย 🚫 หมายถึงระบบไม่แนะนำให้เข้าไม้ใหม่ ไม่ว่าคะแนนจะสูงแค่ไหน · ควรตรวจข่าว/ปัจจัยพื้นฐาน + ราคาจาก Dime ก่อนตัดสินใจซื้อเสมอ</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="section-title">ผล Scan ทั้งหมด</div>', unsafe_allow_html=True)
        filtered = [r for r in results if r["score"] >= min_score]
        if not filtered:
            st.info("ไม่มีหุ้นที่ผ่านเกณฑ์คะแนนที่ตั้งไว้ — ลองลดคะแนนขั้นต่ำใน sidebar")
        else:
            table_data = []
            for r in filtered:
                rs_v = r["rs_rank"]
                status = "🚫 " + " / ".join(r["block_reasons"]) if r["block_reasons"] else "✅ ผ่าน"
                table_data.append({
                    "หุ้น": r["ticker"], "สัญญาณ": r["action"], "สถานะ": status, "คะแนน": r["score"],
                    "Trend Strength": f"{r['strength']:.0f}/100",
                    "Entry": f"${r['entry_price']:.2f}", "Stop": f"${r['stop']:.2f}",
                    "เป้าหมาย": f"${r['target1']:.2f}",
                    "Breakout": {"true": "Breakout จริง", "near": "ใกล้ Breakout", "none": "-"}[r["breakout_status"]],
                    "RS Rank": f"{rs_v:.0f}" if not np.isnan(rs_v) else "—",
                    "RSI": f"{r['rsi']:.0f}", "RVOL": f"{r['rvol']:.1f}x",
                    "Momentum5วัน": f"{r['mom5']:.1f}%",
                    "Gap ราคา": f"{r['gap_pct']:+.1f}%" if r['gap_pct'] is not None else "—",
                    "Earnings": f"{r['earn_days']}วัน" if r['earn_days'] is not None else "—",
                    "Risk ($)": f"${r['risk_usd']:,.0f}",
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
                blocked = bool(r["block_reasons"])
                action_display = r["action"] if not blocked else "🚫 ห้ามเข้าไม้ใหม่"
                action_color = "#f85149" if blocked else sc
                st.markdown(f'<div style="display:flex;align-items:center;gap:16px;margin-bottom:8px"><span class="ticker-pill" style="font-size:20px;padding:6px 16px">{r["ticker"]}</span><span style="font-size:22px;font-weight:700;color:{action_color}">{action_display}</span><span style="font-size:18px;color:#8b949e">{r["score"]}/100 คะแนน</span></div>', unsafe_allow_html=True)
                if blocked:
                    reasons_html = "<br>".join(r["block_reasons"])
                    st.markdown(f'<div class="block-banner">{reasons_html}</div>', unsafe_allow_html=True)
                st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)
                c1,c2,c3,c4,c5 = st.columns(5)
                c1.metric("Entry (Live/Signal)", f"${r['entry_price']:.2f}")
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
                    if r["earnings_status"] == "reduce":
                        st.warning(f"⚠️ หักคะแนน {EARNINGS_REDUCE_PENALTY} แต้มจาก Earnings ที่ใกล้เข้ามา")
                    maxes = {"แนวโน้ม EMA":15,"RS Rank":25,"Breakout":15,"วอลุ่ม":15,"MACD":10,"RSI Zone":10,"Momentum 5วัน":5,"ตลาดรวม":5}
                    for key, val in r["breakdown"].items():
                        if key.startswith("_"): continue
                        mx = maxes.get(key, 10)
                        try: vn = int(val)
                        except Exception: continue
                        bw = int(vn/mx*100) if mx>0 else 0
                        bc = "#3fb950" if vn==mx else ("#d29922" if vn>0 else "#f85149")
                        st.markdown(f'<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:13px"><span style="color:#e6edf3">{key}</span><span style="color:{bc};font-family:\'IBM Plex Mono\',monospace">{vn}/{mx}</span></div><div class="score-bar-wrap" style="margin-top:4px"><div class="score-bar-fill" style="width:{bw}%;background:{bc}"></div></div></div>', unsafe_allow_html=True)
                with cr:
                    st.markdown("**🎯 แผนเทรด**")
                    r2r = (r["target1"]-r["entry_price"])/(r["entry_price"]-r["stop"]) if r["entry_price"]!=r["stop"] else 0
                    st.markdown(f"""
                    <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px">
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">จุดเข้า (Live ถ้ามี ไม่งั้นใช้ราคาปิดสัญญาณ)</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#e6edf3">${r['entry_price']:.2f}</div></div>
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">Stop Loss (ATR×{atr_mult})</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#f85149">${r['stop']:.2f} <span style="font-size:12px">(-{(r['entry_price']-r['stop'])/r['entry_price']*100:.1f}%)</span></div></div>
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">เป้าหมาย 1 (1.5R) ≈ +{(r['target1']-r['entry_price'])/r['entry_price']*100:.1f}%</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#3fb950">${r['target1']:.2f}</div></div>
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">เป้าหมาย 2 (3R) ≈ +{(r['target2']-r['entry_price'])/r['entry_price']*100:.1f}%</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#3fb950">${r['target2']:.2f}</div></div>
                        <div style="margin-bottom:10px"><div style="font-size:12px;color:#8b949e">จำนวนหุ้น / มูลค่าไม้ / Risk</div><div style="font-family:'IBM Plex Mono',monospace;font-size:16px;color:#e6edf3">{r['shares']:,} หุ้น &nbsp;·&nbsp; ${r['pos_val']:,.0f} &nbsp;·&nbsp; <span style="color:#f85149">${r['risk_usd']:,.0f}</span></div></div>
                        <div style="border-top:1px solid #30363d;padding-top:10px;margin-top:4px"><div style="font-size:12px;color:#8b949e">อัตราส่วน Risk:Reward</div><div style="font-size:16px;font-weight:700;color:#58a6ff">1 : {r2r:.1f}</div></div>
                    </div>""", unsafe_allow_html=True)
                    st.markdown("""
                    <div style="background:#0d1d2e;border:1px solid #1f6feb;border-radius:8px;padding:14px;margin-top:10px;font-size:12px;color:#8b949e;line-height:1.7">
                        <strong style="color:#58a6ff">📐 แนวทาง Trailing Stop (ทำเองหลังเข้าไม้):</strong><br>
                        • กำไรถึง +1R → เลื่อน Stop มาที่จุดเข้า (Break-even)<br>
                        • กำไรถึง +1.5R (เป้า 1) → พิจารณาขาย 30-50% ล็อกกำไรบางส่วน<br>
                        • ส่วนที่เหลือ → ใช้ Trailing Stop = ราคาปิดสูงสุดนับจากเข้าไม้ − (ATR × 2)
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
        st.caption("ใช้ Position Sizing Engine เดียวกับผลสแกนหลัก (รวม Max Position % และ Slippage) เพื่อให้ตัวเลขตรงกันทุกหน้า")
        ticker_options = [r["ticker"] for r in results]
        if not ticker_options:
            st.info("ไม่มีข้อมูลหุ้น")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                calc_ticker = st.selectbox("เลือกหุ้น", ticker_options, key="calc_t")
                cal = next((r for r in results if r["ticker"] == calc_ticker), None)
                if cal:
                    custom_entry = st.number_input("ราคาเข้าจริง ($)", value=float(cal["entry_price"]), step=0.5, min_value=0.01)
                    custom_atr   = st.number_input("ATR ปัจจุบัน ($)", value=float(cal["atr"]), step=0.1, min_value=0.01,
                                                    help="ดึงมาจากผลสแกน แก้ไขได้ถ้าต้องการทดลองค่าอื่น")
                    custom_cap   = st.number_input("เงินทุน ($)", value=float(capital), step=500.0, min_value=100.0)
                    custom_risk  = st.slider("ความเสี่ยงต่อไม้ (%)", 0.5, 3.0, float(risk_pct), 0.25)
            with col_b:
                if cal:
                    shares_calc, pos_val_calc, risk_usd_calc, eff_entry_calc = calc_position(
                        custom_cap, custom_entry, custom_atr, custom_risk, atr_mult, max_position_pct, slippage_pct
                    )
                    custom_stop = round(custom_entry - custom_atr * atr_mult, 2)
                    t1c = custom_entry + custom_atr * atr_mult * 1.5
                    t2c = custom_entry + custom_atr * atr_mult * 3.0
                    stop_dist_calc = custom_entry - custom_stop
                    rr = (t1c - custom_entry) / stop_dist_calc if stop_dist_calc > 0 else 0
                    if shares_calc > 0:
                        st.markdown(f"""
                        <div style="background:#161b22;border:1px solid #238636;border-radius:10px;padding:20px;margin-top:8px">
                            <div style="font-size:16px;font-weight:700;color:#3fb950;margin-bottom:16px">ผลคำนวณ</div>
                            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                                <div><div style="font-size:11px;color:#8b949e">จำนวนหุ้น</div><div style="font-family:'IBM Plex Mono',monospace;font-size:22px;color:#e6edf3">{shares_calc:,}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">มูลค่าไม้ (รวม Slippage)</div><div style="font-family:'IBM Plex Mono',monospace;font-size:22px;color:#e6edf3">${pos_val_calc:,.0f}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">ความเสี่ยงจริง</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#f85149">${risk_usd_calc:,.0f}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">R:R Ratio</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#58a6ff">1:{rr:.1f}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">Stop Loss</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#f85149">${custom_stop:.2f}</div></div>
                                <div><div style="font-size:11px;color:#8b949e">เป้า 1 (+{(t1c-custom_entry)/custom_entry*100:.1f}%)</div><div style="font-family:'IBM Plex Mono',monospace;font-size:18px;color:#3fb950">${t1c:.2f}</div></div>
                            </div>
                            <div style="margin-top:14px;padding-top:12px;border-top:1px solid #30363d;font-size:13px;color:#8b949e">% ของพอร์ตที่ใช้: {pos_val_calc/custom_cap*100:.1f}% (จำกัดที่ {max_position_pct:.0f}% จาก sidebar)</div>
                        </div>""", unsafe_allow_html=True)
                        if rr < 1.5:
                            st.warning("⚠️ R:R ต่ำกว่า 1:1.5 — ควรขยับ Stop หรือเลื่อนเป้าหมายใหม่")
                    else:
                        st.error("❌ ไม่สามารถเข้าไม้ได้ตามเงื่อนไขปัจจุบัน (ราคา/ATR ผิดปกติ หรือ Max Position ไม่พอสำหรับ 1 หุ้น)")

    with tab5:
        st.markdown('<div class="section-title">📉 Backtest เบื้องต้น (ทดสอบย้อนหลัง ~6 เดือน)</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="disclaimer">⚠️ นี่คือการทดสอบแบบง่าย ใช้ข้อมูล 6 เดือนของหุ้นที่ scan รวมกับ universe อ้างอิง '
            'ไม่มีการจัดอันดับ RS แบบ cross-sectional รายวันในอดีตจริง (ใช้ค่าประมาณแทน) และไม่รวมค่าธรรมเนียม/slippage จริง '
            '· ผลลัพธ์นี้ <strong>ไม่ใช่</strong> การยืนยันทางสถิติที่สมบูรณ์ ใช้เพื่อดูแนวโน้มคร่าวๆ ก่อนตัดสินใจเชื่อคะแนนเต็มที่เท่านั้น</div>',
            unsafe_allow_html=True
        )
        if spy_df is None or not all_dfs:
            st.info("ต้องกด 🔍 Scan อย่างน้อย 1 ครั้งก่อน เพื่อให้มีข้อมูลราคาสำหรับ Backtest")
        else:
            run_bt = st.button("▶️ รัน Backtest (อาจใช้เวลาสักครู่)")
            if run_bt:
                with st.spinner("กำลังทดสอบย้อนหลัง..."):
                    bt_df = backtest_scores(all_dfs, spy_df, forward_days=10, target_pct=3.0)
                if bt_df.empty:
                    st.warning("ข้อมูลไม่พอสำหรับ Backtest")
                else:
                    bt_df["bucket"] = bt_df["score"].apply(bucket_score)
                    summary = bt_df.groupby("bucket").agg(
                        จำนวนตัวอย่าง=("fwd_ret", "count"),
                        Win_Rate_เกิน3พัน=("fwd_ret", lambda x: (x >= 3.0).mean() * 100),
                        ผลตอบแทนเฉลี่ย=("fwd_ret", "mean"),
                        ผลตอบแทนแย่สุด=("fwd_ret", "min"),
                        ผลตอบแทนดีสุด=("fwd_ret", "max"),
                    ).round(2)
                    order = ["🚀 ซื้อเลย (82-100)", "🔥 น่าซื้อ (68-81)", "👀 จับตาดู (52-67)", "❌ หลีกเลี่ยง (0-51)"]
                    summary = summary.reindex([o for o in order if o in summary.index])
                    st.dataframe(summary, use_container_width=True)
                    st.caption(
                        "Win Rate = สัดส่วนครั้งที่ราคาขึ้น ≥3% ภายใน 10 วันทำการถัดไป (ประมาณ 2 สัปดาห์) นับจากวันที่ให้คะแนนนั้นในอดีต · "
                        f"รวมตัวอย่างทั้งหมด {len(bt_df):,} จุดข้อมูล จาก {bt_df['ticker'].nunique()} หุ้น"
                    )

    st.divider()
    st.caption("⚠️ ระบบนี้เป็นเครื่องมือช่วยวิเคราะห์เทคนิคัลเท่านั้น · ข้อมูลล่าช้า 15+ นาที (Yahoo Finance) · ไม่ใช่คำแนะนำการลงทุน · ตรวจสอบราคาจริงบนแอป Dime ก่อนส่งคำสั่งทุกครั้ง")

elif not tickers:
    st.info("👆 พิมพ์ชื่อหุ้น (เช่น NVDA, AAPL, TSLA) แล้วกด Scan")
else:
    st.info("👆 กด 🔍 Scan เพื่อเริ่มการวิเคราะห์ (ครั้งแรกต้องกดปุ่มก่อนถึงจะมีข้อมูล)")
