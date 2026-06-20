import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Stock Hunter Pro v24", layout="wide")

# ============================================================
# CONFIG
# ============================================================
BENCHMARK = "SPY"
EARNINGS_BLACKOUT_DAYS = 7  # ผู้ใช้ขอเปลี่ยนจาก 0-3 วัน เป็น 7 วัน

# Sector / theme groupings — used for Sector Rotation view (avg RS Rank
# per group tells you where money is actually flowing). Extend freely;
# any ticker not listed here falls into "Other".
SECTOR_TICKERS = {
    "SEMI": ["NVDA", "AMD", "AVGO", "TSM", "SMCI", "MU", "QCOM", "INTC", "ARM"],
    "MEGA_TECH": ["AAPL", "MSFT", "GOOGL", "GOOG", "META", "AMZN"],
    "AI_SOFTWARE": ["PLTR", "CRM", "NOW", "SNOW", "AI", "PATH"],
    "EV_AUTO": ["TSLA", "RIVN", "LCID", "F", "GM"],
    "FINANCE": ["JPM", "BAC", "GS", "MS", "V", "MA"],
    "ENERGY": ["XOM", "CVX", "OXY", "SLB"],
    "HEALTHCARE": ["UNH", "LLY", "JNJ", "PFE", "ABBV"],
}


def get_sector(ticker):
    for sector, members in SECTOR_TICKERS.items():
        if ticker in members:
            return sector
    return "Other"

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


@st.cache_data(ttl=300)  # 5-min cache — short enough to stay reasonably fresh intraday
def load_live_price(ticker):
    """
    Best-effort fetch of the most current tradable price (regular session,
    pre-market, or post-market), used only to detect gaps vs yesterday's
    close. yfinance's free data is delayed (~15 min, sometimes more) and
    pre/post-market fields are not guaranteed to be populated for every
    ticker — this is NOT true real-time data. Returns:
        (live_price, source_label) or (None, None) if nothing usable.
    """
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        live = None
        source = None

        # fast_info.last_price is usually the most current trade price
        # yfinance can obtain (often includes pre/post market).
        last_price = getattr(fi, "last_price", None)
        if last_price:
            live = float(last_price)
            source = "last trade (delayed ~15min+)"

        # Try to get explicit pre/post market fields for a clearer label
        info = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}

        pre = info.get("preMarketPrice")
        post = info.get("postMarketPrice")
        market_state = info.get("marketState", "")

        if market_state == "PRE" and pre:
            live = float(pre)
            source = "pre-market (delayed)"
        elif market_state in ("POST", "POSTPOST") and post:
            live = float(post)
            source = "post-market (delayed)"
        elif market_state == "REGULAR" and last_price:
            source = "regular session (delayed ~15min+)"

        if live is None:
            return None, None
        return live, source
    except Exception:
        return None, None


def detect_gap(prev_close, live_price, threshold_pct=3.0):
    """
    Compare live/extended-hours price to the most recent daily close.
    Returns (gap_pct, is_high_gap).
    """
    if prev_close is None or live_price is None or prev_close == 0:
        return None, False
    gap_pct = (live_price - prev_close) / prev_close * 100
    return round(gap_pct, 2), abs(gap_pct) >= threshold_pct


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
def is_choppy(row):
    """
    Hard volatility/volume gate. If RVOL <= 1.0, "no one is trading this"
    today — ATR can look tight and R:R can look great on paper while the
    move has no real participation behind it. Stocks that fail this gate
    are force-capped regardless of how good the rest of the score looks.
    """
    return row["RVOL"] <= 1.0


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

    Hard gate: RVOL <= 1.0 caps the total score regardless of other
    factors (see is_choppy). This stops "great score, no volume" chop
    days from showing up as BUY/ELITE BUY.
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

    # Hard chop gate — RVOL <= 1.0 means no real participation today.
    # Cap the score so it can never read as BUY/ELITE BUY on paper-only setups.
    chopped = is_choppy(row)
    if chopped:
        score = min(score, 40)

    breakdown["Chop Capped"] = chopped
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


def trade_levels(entry_price, atr, atr_multiple, current_price=None):
    """
    Initial Stop      = entry - 1R
    1R                = atr * atr_multiple
    Break-even Trigger = entry + 2R  (move stop to entry once hit)
    Trailing logic     = once price >= entry + 2R, recommended stop
                          becomes break-even (entry price); beyond that
                          a simple chandelier-style trail (current - 1R)
                          can be used to lock in further gains.
    If current_price is supplied, also returns how many R the trade
    is currently up and the recommended stop given that progress.
    """
    r = atr * atr_multiple
    if r <= 0:
        return None

    initial_stop = entry_price - r
    breakeven_trigger = entry_price + 2 * r  # move stop to BE at +2R

    levels = {
        "1R_distance": round(r, 2),
        "initial_stop": round(initial_stop, 2),
        "breakeven_trigger_price": round(breakeven_trigger, 2),
        "breakeven_stop": round(entry_price, 2),
    }

    if current_price is not None:
        r_multiple = (current_price - entry_price) / r if r > 0 else 0
        levels["current_R"] = round(r_multiple, 2)

        if current_price >= breakeven_trigger:
            # At/above +2R: stop trails at break-even or better,
            # using a simple chandelier trail (current price - 1R)
            # whichever is higher, so it never gives back below BE.
            trail_stop = max(entry_price, current_price - r)
            levels["recommended_stop"] = round(trail_stop, 2)
            levels["stop_stage"] = "🔒 TRAILING (≥2R — stop at/above break-even)"
        elif current_price > entry_price:
            levels["recommended_stop"] = round(initial_stop, 2)
            levels["stop_stage"] = "⏳ INITIAL (below +2R — keep original stop)"
        else:
            levels["recommended_stop"] = round(initial_stop, 2)
            levels["stop_stage"] = "⚠️ UNDER WATER (below entry)"

    return levels


# ============================================================
# UI
# ============================================================
st.title("🦅 Stock Hunter Pro v24")
st.caption("100-point scoring · RS Rank vs SPY · MACD · Market Regime Filter · Portfolio Heat sizing · Sector Rotation · Trailing Stop · Gap Warning · RS Line Chart · Trade Journal")

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
    gap_threshold_pct = st.number_input(
        "Gap Warning Threshold (%)", value=3.0, min_value=0.5, max_value=20.0, step=0.5,
        help="ถ้าราคาล่าสุด (pre/post market หรือ delayed) ต่างจากราคาปิดเมื่อวานเกินกี่ % ให้ขึ้นเตือน HIGH GAP"
    )

    st.subheader("📓 Trade Journal")
    journal_enabled = st.checkbox(
        "เปิดใช้ Trade Journal (บันทึกลง CSV)", value=True,
        help="บันทึก Score/Action ณ วันที่ตัดสินใจ พร้อมเหตุผล เพื่อย้อนกลับมาดูผลลัพธ์ภายหลัง"
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
rs_lines = {}        # ticker -> RS line series (stock/SPY ratio), for charting
gap_info = {}        # ticker -> (gap_pct, is_high_gap, live_price, source_label)

for t in tickers:
    df = load_data(t)
    if df is None or len(df) < 30:
        continue
    df = indicators(df)
    ticker_data[t] = df

    if spy_df is not None:
        rs_line, rel_score = relative_strength_series(df["Close"], spy_df["Close"])
        raw_rel_scores[t] = rel_score
        rs_lines[t] = rs_line
    else:
        raw_rel_scores[t] = np.nan
        rs_lines[t] = None

    prev_close = float(df["Close"].iloc[-1])
    live_price, source = load_live_price(t)
    gap_pct, is_high_gap = detect_gap(prev_close, live_price, threshold_pct=gap_threshold_pct)
    gap_info[t] = {
        "prev_close": prev_close,
        "live_price": live_price,
        "source": source,
        "gap_pct": gap_pct,
        "is_high_gap": is_high_gap,
    }

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

    gap = gap_info.get(t, {})
    if gap.get("is_high_gap"):
        direction = "⬆️" if gap["gap_pct"] > 0 else "⬇️"
        action += f" ⚠️ HIGH GAP {direction}{abs(gap['gap_pct']):.1f}%"

    shares, position_value, risk_dollars = position_size(
        capital, last["Close"], last["ATR"], risk_per_trade_pct, atr_multiple
    )
    levels = trade_levels(last["Close"], last["ATR"], atr_multiple, current_price=last["Close"])

    results.append({
        "Ticker": t,
        "Sector": get_sector(t),
        "Action": action,
        "Score": round(score, 1),
        "RS Rank": round(rs_rank, 1) if not np.isnan(rs_rank) else None,
        "Price (Close)": round(last["Close"], 2),
        "Live/Pre-Post Price": round(gap["live_price"], 2) if gap.get("live_price") else None,
        "Gap %": gap.get("gap_pct"),
        "ATR": round(last["ATR"], 2),
        "RVOL": round(last["RVOL"], 2),
        "Earnings In": f"{days_to_earnings}d" if days_to_earnings is not None else "—",
        "Initial Stop": levels["initial_stop"] if levels else None,
        "BE Trigger (+2R)": levels["breakeven_trigger_price"] if levels else None,
        "Shares (sized)": shares,
        "Position $": round(position_value, 0),
        "Risk $": round(risk_dollars, 0),
    })
    detail_rows[t] = breakdown

results_df = pd.DataFrame(results).sort_values("Score", ascending=False).reset_index(drop=True)

st.dataframe(results_df, use_container_width=True)

# Honest disclosure about data freshness for the gap feature
st.caption(
    "⚠️ \"Live/Pre-Post Price\" มาจาก yfinance แบบ best-effort (มักดีเลย์ 15+ นาที และไม่ใช่ทุกหุ้นที่มีราคา pre/post-market "
    "ครบ) ใช้เพื่อ **เตือน** ว่าราคาน่าจะกระโดดไปจากปิดเมื่อวานเท่านั้น ไม่ใช่ราคาที่ใช้คำนวณ Entry/Stop จริง — "
    "ก่อนส่งคำสั่งจริงควรเช็คราคาจาก broker/platform ของคุณอีกที"
)

high_gap_tickers = [r["Ticker"] for r in results if gap_info.get(r["Ticker"], {}).get("is_high_gap")]
if high_gap_tickers:
    st.warning(
        f"⚠️ HIGH GAP: {', '.join(high_gap_tickers)} — ราคาล่าสุดต่างจากปิดเมื่อวานเกิน {gap_threshold_pct:.1f}% "
        "ระวังการไล่ราคา (FOMO) ตำแหน่ง Entry/Stop ที่คำนวณจากราคาปิดอาจไม่ทันสถานการณ์แล้ว"
    )

# ------------------------------------------------------------
# Sector Rotation view — avg RS Rank / Score per group shows
# where money is actually flowing today.
# ------------------------------------------------------------
if not results_df.empty:
    st.subheader("🔄 Sector Rotation")
    sector_summary = (
        results_df.dropna(subset=["RS Rank"])
        .groupby("Sector")
        .agg(
            Tickers=("Ticker", "count"),
            **{"Avg RS Rank": ("RS Rank", "mean")},
            **{"Avg Score": ("Score", "mean")},
        )
        .sort_values("Avg RS Rank", ascending=False)
        .round(1)
        .reset_index()
    )
    if not sector_summary.empty:
        st.dataframe(sector_summary, use_container_width=True)
        st.caption("Avg RS Rank สูง = เงินไหลเข้ากลุ่มนี้มากกว่าตลาดโดยรวม")
    else:
        st.caption("ไม่มีข้อมูล RS Rank พอสำหรับสรุปตาม Sector")

# ------------------------------------------------------------
# RS Line chart — stock/SPY ratio over time. Rising = stock leading
# the market; falling = stock losing relative strength, often BEFORE
# price itself rolls over.
# ------------------------------------------------------------
st.subheader("📈 Relative Strength (RS) Line vs SPY")
chartable = [t for t in results_df["Ticker"] if rs_lines.get(t) is not None]
if chartable:
    rs_chart_ticker = st.selectbox("เลือกหุ้นเพื่อดู RS Line", chartable, key="rs_chart_select")
    rs_series = rs_lines[rs_chart_ticker].copy()
    rs_series.name = f"{rs_chart_ticker}/SPY"
    st.line_chart(rs_series)
    st.caption(
        "เส้นพุ่งขึ้น = หุ้นแข็งแกร่งกว่า SPY (เงินไหลเข้า) · เส้นหักหัวลง = หุ้นเริ่มอ่อนแรงเทียบตลาด "
        "มักเป็นสัญญาณเตือนล่วงหน้าก่อนราคาจริงจะร่วง"
    )
else:
    st.caption("ไม่มีข้อมูล RS Line (ต้องมีข้อมูล SPY และหุ้นที่เลือกพร้อมกัน)")

# ------------------------------------------------------------
# Trailing Stop / Break-even Tracker — for positions already open
# ------------------------------------------------------------
st.subheader("🎯 Break-even / Trailing Stop Tracker")
st.caption("ใส่ราคาที่เข้าซื้อจริง เพื่อดูว่าควรขยับ Stop ไปที่ไหนตามความคืบหน้าของเทรด (กฎ: ถึง +2R → ขยับ Stop เป็น Break-even หรือดีกว่า)")

trackable = [t for t in results_df["Ticker"] if t in ticker_data]
if trackable:
    col1, col2 = st.columns([1, 2])
    with col1:
        track_ticker = st.selectbox("เลือกหุ้น", trackable)
    with col2:
        default_entry = float(ticker_data[track_ticker]["Close"].iloc[-1])
        entry_price_input = st.number_input(
            f"ราคาที่เข้าซื้อจริงสำหรับ {track_ticker}", value=default_entry, step=0.5
        )

    last_row = ticker_data[track_ticker].iloc[-1]
    lv = trade_levels(entry_price_input, last_row["ATR"], atr_multiple, current_price=last_row["Close"])

    if lv:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("ราคาปัจจุบัน", f"${last_row['Close']:.2f}")
        c2.metric("กำไรตอนนี้ (R)", f"{lv['current_R']}R")
        c3.metric("Stop ที่แนะนำตอนนี้", f"${lv['recommended_stop']:.2f}")
        c4.metric("จุด Trigger Break-even (+2R)", f"${lv['breakeven_trigger_price']:.2f}")
        st.info(f"สถานะ: **{lv['stop_stage']}**")

# ------------------------------------------------------------
# Trade Journal — log the decision (Score/Action/reason) at the
# moment of the trade, so you can later answer: "Stocks I traded
# at Score 85+ — how did they actually do?"
# ------------------------------------------------------------
if journal_enabled:
    st.subheader("📓 Trade Journal")
    st.caption(
        "บันทึก Score/Action ณ วันที่ตัดสินใจ พร้อมเหตุผลสั้นๆ — ดาวน์โหลดเป็น CSV เก็บไว้เอง "
        "⚠️ ข้อมูลจะหายเมื่อปิด/รีเฟรชแอป ต้องดาวน์โหลด CSV แล้วอัปโหลดกลับเข้ามาทุกครั้งที่เปิดแอปใหม่ เพื่อบันทึกต่อเนื่อง"
    )

    JOURNAL_COLUMNS = ["Date", "Ticker", "Score", "Action", "Price", "Entry", "Stop", "Shares", "Reason"]

    if "journal_df" not in st.session_state:
        st.session_state.journal_df = pd.DataFrame(columns=JOURNAL_COLUMNS)

    uploaded_journal = st.file_uploader(
        "อัปโหลด Trade Journal เดิม (CSV) เพื่อบันทึกต่อ — ไม่บังคับ", type=["csv"], key="journal_upload"
    )
    if uploaded_journal is not None:
        try:
            loaded = pd.read_csv(uploaded_journal)
            missing = [c for c in JOURNAL_COLUMNS if c not in loaded.columns]
            if missing:
                st.error(f"ไฟล์ CSV ขาดคอลัมน์: {missing}")
            else:
                st.session_state.journal_df = loaded[JOURNAL_COLUMNS]
                st.success(f"โหลด Trade Journal แล้ว ({len(loaded)} แถว)")
        except Exception as e:
            st.error(f"อ่านไฟล์ไม่สำเร็จ: {e}")

    jc1, jc2 = st.columns([1, 2])
    with jc1:
        journal_ticker = st.selectbox("หุ้นที่จะบันทึก", trackable if trackable else ["—"], key="journal_ticker_select")
    with jc2:
        journal_reason = st.text_input(
            "เหตุผลสั้นๆ", placeholder="เช่น Breakout 20D + High Volume + RS Rank 92", key="journal_reason_input"
        )

    if st.button("💾 บันทึกลง Journal", disabled=(journal_ticker not in ticker_data)):
        row_match = results_df[results_df["Ticker"] == journal_ticker]
        if not row_match.empty:
            r = row_match.iloc[0]
            lv_j = trade_levels(r["Price (Close)"], ticker_data[journal_ticker]["ATR"].iloc[-1], atr_multiple)
            new_entry = pd.DataFrame([{
                "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                "Ticker": journal_ticker,
                "Score": r["Score"],
                "Action": r["Action"],
                "Price": r["Price (Close)"],
                "Entry": r["Price (Close)"],
                "Stop": lv_j["initial_stop"] if lv_j else None,
                "Shares": r["Shares (sized)"],
                "Reason": journal_reason,
            }])
            st.session_state.journal_df = pd.concat([st.session_state.journal_df, new_entry], ignore_index=True)
            st.success(f"บันทึก {journal_ticker} ลง Journal แล้ว")

    if not st.session_state.journal_df.empty:
        st.dataframe(st.session_state.journal_df, use_container_width=True)
        csv_bytes = st.session_state.journal_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ ดาวน์โหลด Trade Journal (CSV)",
            data=csv_bytes,
            file_name=f"trade_journal_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.caption("ยังไม่มีรายการบันทึก")

# ------------------------------------------------------------
# Score breakdown expander
# ------------------------------------------------------------
with st.expander("🔍 Score Breakdown (per ticker)"):
    for t in results_df["Ticker"]:
        b = detail_rows[t]
        chop_note = " ⚠️ **RVOL≤1.0 — score capped at 40 (chop/no participation)**" if b.get("Chop Capped") else ""
        st.markdown(
            f"**{t}** — Trend {b['Trend']}/20 · RS {b['RS']}/25 · Breakout {b['Breakout']}/20 · "
            f"Volume {b['Volume']}/15 · Momentum {b['Momentum']}/10 · Market {b['Market']}/10 "
            f"→ **Total {sum(v for k,v in b.items() if k != 'Chop Capped')}/100**{chop_note}"
        )

st.divider()
st.caption(
    "Scoring: Trend 20 · RS Rank 25 · Breakout 20 · Volume 15 · Momentum (MACD) 10 · Market Filter 10 = 100 pts "
    "(capped at 40 if RVOL≤1.0 — chop guard) | "
    "85+ ELITE BUY · 70-84 BUY · 55-69 WATCH · <55 AVOID"
)
