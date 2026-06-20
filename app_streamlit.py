import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Stock Hunter Pro v22", layout="wide")

# ============================================================
# CONFIG
# ============================================================
BENCHMARK = "SPY"
EARNINGS_BLACKOUT_DAYS = 7  # ผู้ใช้ขอเปลี่ยนจาก 0-3 วัน เป็น 7 วัน

# ============================================================
# DATA LOADING
# ============================================================
@st.cache_data(ttl=3600)
def load_data(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="1y", auto_adjust=True)
        return df if not df.empty else None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def load_earnings_date(ticker):
    """Return next earnings date (or None) and days-to-earnings (or None)."""
    try:
        t = yf.Ticker(ticker)
        cal = t.get_earnings_dates(limit=8)
        if cal is None or cal.empty:
            return None, None
        now = pd.Timestamp.now(tz=cal.index.tz)
        future = cal[cal.index >= now]
        if future.empty:
            return None, None
        next_date = future.index.min()
        days_to = (next_date - now).days
        return next_date.date(), days_to
    except Exception:
        return None, None


# ============================================================
# INDICATORS
# ============================================================
def indicators(df):
    df = df.copy()

    # ATR (14, EWM smoothing as before)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"] - df["Close"].shift(1)).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(span=14).mean()

    # Trend
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["EMA200"] = df["Close"].ewm(span=200).mean()

    # Volume
    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()

    # Breakout reference
    df["High20"] = df["Close"].rolling(20).max()

    # MACD (12, 26, 9 — standard)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    return df


def relative_strength_series(stock_close, bench_close):
    """
    IBD-style simplified RS line: stock/benchmark ratio,
    then turned into a rolling percentile-style RS score (0-100)
    based on the stock's own RS-line trend (63-day, ~quarter).
    """
    aligned = pd.concat([stock_close, bench_close], axis=1).dropna()
    aligned.columns = ["stock", "bench"]
    rs_line = aligned["stock"] / aligned["bench"]

    # Weighted multi-period performance vs benchmark (IBD-like weighting:
    # last quarter weighted heaviest), converted to a 0-100 raw RS value.
    def pct_change_n(series, n):
        if len(series) <= n:
            return np.nan
        return series.iloc[-1] / series.iloc[-1 - n] - 1

    stock_perf = {
        63: pct_change_n(aligned["stock"], 63),
        126: pct_change_n(aligned["stock"], 126),
        189: pct_change_n(aligned["stock"], 189),
        252: pct_change_n(aligned["stock"], 252),
    }
    bench_perf = {
        63: pct_change_n(aligned["bench"], 63),
        126: pct_change_n(aligned["bench"], 126),
        189: pct_change_n(aligned["bench"], 189),
        252: pct_change_n(aligned["bench"], 252),
    }

    # Relative performance (stock minus benchmark) per period; weight
    # the most recent quarter 2x like IBD's methodology.
    weights = {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2}
    rel_score = 0.0
    total_w = 0.0
    for n, w in weights.items():
        if not np.isnan(stock_perf[n]) and not np.isnan(bench_perf[n]):
            rel_score += w * (stock_perf[n] - bench_perf[n])
            total_w += w

    if total_w == 0:
        return rs_line, np.nan

    rel_score = rel_score / total_w
    return rs_line, rel_score


def rs_rank_from_universe(raw_rel_scores: dict):
    """
    Convert raw relative-performance scores for a universe of tickers
    into a 1-99 percentile rank, IBD style.
    """
    valid = {k: v for k, v in raw_rel_scores.items() if not np.isnan(v)}
    if len(valid) <= 1:
        return {k: 50.0 for k in raw_rel_scores}  # not enough data to rank

    series = pd.Series(valid)
    ranks = series.rank(pct=True) * 98 + 1  # scale to 1-99
    result = {k: ranks.get(k, np.nan) for k in raw_rel_scores}
    return result


# ============================================================
# SCORING — 100 point system
# ============================================================
def compute_score(row, rs_rank, spy_bullish):
    """
    Trend            EMA50 > EMA200            = 20
    Relative Strength RS Rank > 80              = 25
    Breakout         Close >= 20D High          = 20
    Volume           RVOL > 1.5                 = 15
    Momentum         MACD > Signal              = 10
    Market Filter    SPY > EMA200               = 10
    ------------------------------------------------
    Total                                       = 100
    """
    score = 0
    breakdown = {}

    # Trend (20)
    pts = 20 if row["Close"] > row["EMA50"] > row["EMA200"] else (10 if row["Close"] > row["EMA50"] else 0)
    breakdown["Trend"] = pts
    score += pts

    # Relative Strength (25) — scaled, not just pass/fail at 80
    if np.isnan(rs_rank):
        pts = 0
    elif rs_rank >= 90:
        pts = 25
    elif rs_rank >= 80:
        pts = 20
    elif rs_rank >= 70:
        pts = 12
    elif rs_rank >= 50:
        pts = 5
    else:
        pts = 0
    breakdown["RS"] = pts
    score += pts

    # Breakout (20) — at/near 20D high
    pts = 20 if row["Close"] >= row["High20"] * 0.99 else (10 if row["Close"] >= row["High20"] * 0.95 else 0)
    breakdown["Breakout"] = pts
    score += pts

    # Volume (15)
    if row["RVOL"] > 1.5:
        pts = 15
    elif row["RVOL"] > 1.1:
        pts = 8
    else:
        pts = 0
    breakdown["Volume"] = pts
    score += pts

    # Momentum (10) — MACD cross
    pts = 10 if row["MACD"] > row["MACD_Signal"] else 0
    breakdown["Momentum"] = pts
    score += pts

    # Market Filter (10) — SPY regime
    pts = 10 if spy_bullish else 0
    breakdown["Market"] = pts
    score += pts

    return score, breakdown


def classify(score):
    if score >= 85:
        return "🚀 ELITE BUY"
    elif score >= 70:
        return "🔥 BUY"
    elif score >= 55:
        return "👀 WATCH"
    else:
        return "❌ AVOID"


# ============================================================
# POSITION SIZING — Risk Per Trade vs Portfolio Heat (separated)
# ============================================================
def position_size(capital, entry_price, atr, risk_per_trade_pct, atr_multiple):
    """
    1R = ATR * atr_multiple (stop distance)
    Risk per trade = capital * risk_per_trade_pct
    Shares = Risk per trade / stop distance
    """
    stop_distance = atr * atr_multiple
    if stop_distance <= 0:
        return 0, 0, 0
    risk_dollars = capital * (risk_per_trade_pct / 100)
    shares = int(risk_dollars / stop_distance)
    position_value = shares * entry_price
    return shares, position_value, risk_dollars


# ============================================================
# UI
# ============================================================
st.title("🦅 Stock Hunter Pro v22")
st.caption("100-point scoring · RS Rank vs SPY · MACD · Market Regime Filter · Portfolio Heat sizing")

user_input = st.text_input(
    "พิมพ์ชื่อหุ้นที่ต้องการ (คั่นด้วยลูกน้ำ เช่น AAPL, MSFT, SMCI):",
    "NVDA, PLTR, AMD, TSLA, META, AAPL, MSFT, GOOGL"
)
tickers = [t.strip().upper() for t in user_input.split(",") if t.strip()]

with st.sidebar:
    st.header("⚙️ Settings")
    capital = st.number_input("Capital ($)", value=100000, step=1000)

    st.subheader("Position Sizing")
    risk_per_trade_pct = st.number_input(
        "Risk Per Trade (%)", value=1.0, min_value=0.1, max_value=10.0, step=0.1,
        help="ความเสี่ยงต่อไม้ (% ของ Capital) — เช่น 1% ต่อไม้"
    )
    portfolio_heat_pct = st.number_input(
        "Portfolio Heat — Max Total Risk (%)", value=5.0, min_value=0.5, max_value=50.0, step=0.5,
        help="ความเสี่ยงรวมทั้งพอร์ตสูงสุดที่ยอมรับได้ ถ้าพร้อมกัน"
    )
    atr_multiple = st.number_input("Stop = ATR ×", value=2.0, min_value=0.5, max_value=5.0, step=0.5)

    max_positions = int(portfolio_heat_pct / risk_per_trade_pct) if risk_per_trade_pct > 0 else 0
    st.info(f"📊 เปิดได้สูงสุด **{max_positions} ไม้** พร้อมกัน (ไม้ละ {risk_per_trade_pct:.1f}% risk, รวมไม่เกิน {portfolio_heat_pct:.1f}% heat)")

    st.subheader("Filters")
    use_market_leader_filter = st.checkbox(
        "Market Leader Filter (Close > EMA200 AND RS Rank > 70)", value=True,
        help="กรองหุ้นขยะออกก่อนคำนวณคะแนน"
    )
    earnings_days_filter = st.number_input(
        "Earnings Blackout (วัน)", value=EARNINGS_BLACKOUT_DAYS, min_value=0, max_value=30, step=1,
        help="ซ่อน/เตือนหุ้นที่มี Earnings ภายในกี่วันข้างหน้า"
    )

# ------------------------------------------------------------
# Load benchmark (SPY) once
# ------------------------------------------------------------
spy_df = load_data(BENCHMARK)
spy_bullish = False
if spy_df is not None:
    spy_df = indicators(spy_df)
    spy_bullish = bool(spy_df["Close"].iloc[-1] > spy_df["EMA200"].iloc[-1])

market_status = "🟢 BULLISH (SPY > EMA200)" if spy_bullish else "🔴 BEARISH (SPY < EMA200)"
st.subheader(f"Market Regime: {market_status}")
if not spy_bullish:
    st.warning("⚠️ ตลาดรวมอยู่ใต้ EMA200 — Market Filter จะหัก 10 คะแนนจากทุกหุ้น และควรพิจารณาลดขนาดการเปิดสถานะใหม่")

# ------------------------------------------------------------
# Load all tickers + compute raw RS first (need full universe)
# ------------------------------------------------------------
ticker_data = {}
raw_rel_scores = {}

for t in tickers:
    df = load_data(t)
    if df is None or len(df) < 30:
        continue
    df = indicators(df)
    ticker_data[t] = df

    if spy_df is not None:
        _, rel_score = relative_strength_series(df["Close"], spy_df["Close"])
        raw_rel_scores[t] = rel_score
    else:
        raw_rel_scores[t] = np.nan

rs_ranks = rs_rank_from_universe(raw_rel_scores)

# ------------------------------------------------------------
# Score each ticker
# ------------------------------------------------------------
results = []
detail_rows = {}

for t, df in ticker_data.items():
    last = df.iloc[-1]
    rs_rank = rs_ranks.get(t, np.nan)

    # Market Leader pre-filter
    is_leader = bool(last["Close"] > last["EMA200"]) and (not np.isnan(rs_rank) and rs_rank > 70)

    earnings_date, days_to_earnings = load_earnings_date(t)
    in_blackout = (days_to_earnings is not None) and (0 <= days_to_earnings <= earnings_days_filter)

    if use_market_leader_filter and not is_leader:
        score, breakdown = 0, {"Trend": 0, "RS": 0, "Breakout": 0, "Volume": 0, "Momentum": 0, "Market": 0}
        action = "❌ AVOID (Not Leader)"
    else:
        score, breakdown = compute_score(last, rs_rank, spy_bullish)
        action = classify(score)
        if in_blackout:
            action += " ⚠️ EARNINGS SOON"

    shares, position_value, risk_dollars = position_size(
        capital, last["Close"], last["ATR"], risk_per_trade_pct, atr_multiple
    )

    results.append({
        "Ticker": t,
        "Action": action,
        "Score": round(score, 1),
        "RS Rank": round(rs_rank, 1) if not np.isnan(rs_rank) else None,
        "Price": round(last["Close"], 2),
        "ATR": round(last["ATR"], 2),
        "Earnings In": f"{days_to_earnings}d" if days_to_earnings is not None else "—",
        "Shares (sized)": shares,
        "Position $": round(position_value, 0),
        "Risk $": round(risk_dollars, 0),
    })
    detail_rows[t] = breakdown

results_df = pd.DataFrame(results).sort_values("Score", ascending=False).reset_index(drop=True)

st.dataframe(results_df, use_container_width=True)

# ------------------------------------------------------------
# Score breakdown expander
# ------------------------------------------------------------
with st.expander("🔍 Score Breakdown (per ticker)"):
    for t in results_df["Ticker"]:
        b = detail_rows[t]
        st.markdown(
            f"**{t}** — Trend {b['Trend']}/20 · RS {b['RS']}/25 · Breakout {b['Breakout']}/20 · "
            f"Volume {b['Volume']}/15 · Momentum {b['Momentum']}/10 · Market {b['Market']}/10 "
            f"→ **Total {sum(b.values())}/100**"
        )

st.divider()
st.caption(
    "Scoring: Trend 20 · RS Rank 25 · Breakout 20 · Volume 15 · Momentum (MACD) 10 · Market Filter 10 = 100 pts | "
    "85+ ELITE BUY · 70-84 BUY · 55-69 WATCH · <55 AVOID"
)
