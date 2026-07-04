import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Stock Hunter Pro v26", layout="wide")

# ============================================================
# CONFIG
# ============================================================
BENCHMARK = "SPY"
EARNINGS_BLACKOUT_DAYS = 7  # ผู้ใช้ขอเปลี่ยนจาก 0-3 วัน เป็น 7 วัน

JOURNAL_COLUMNS = ["Date", "Ticker", "Score", "Action", "Price", "Entry", "Stop",
                   "Shares", "Reason", "Status", "Exit", "Exit Date", "PnL"]

# ------------------------------------------------------------
# TRADING STYLE PRESETS — v26
# Same 100-point scoring skeleton, but the underlying lookback
# windows shift depending on whether the user is hunting short-term
# swings (days-to-weeks) or long-term positions (months). A 20-day
# breakout / 50-200 EMA setup is tuned for swing trading; someone
# holding for months benefits from slower EMAs and a longer breakout
# reference so normal short-term noise doesn't flip the signal.
# ------------------------------------------------------------
TRADE_STYLE_PRESETS = {
    "สั้น (Swing 1-3 สัปดาห์)": {
        "ema_fast": 20, "ema_slow": 50,
        "breakout_window": 10,
        "rs_weights": {21: 0.5, 42: 0.25, 63: 0.15, 126: 0.10},
        "default_forward_days": 5,
        "desc": "เน้นจังหวะสั้น — EMA20/50, Breakout 10 วัน, ให้น้ำหนัก momentum ล่าสุดมากกว่า",
    },
    "ยาว (Position หลายเดือน)": {
        "ema_fast": 50, "ema_slow": 200,
        "breakout_window": 55,
        "rs_weights": {63: 0.2, 126: 0.3, 189: 0.25, 252: 0.25},
        "default_forward_days": 40,
        "desc": "เน้นเทรนด์ใหญ่ — EMA50/200, Breakout 55 วัน, กระจายน้ำหนักไปช่วงยาวกว่า ลด noise ระยะสั้น",
    },
    "ทั้งสอง (ค่าเริ่มต้นเดิม)": {
        "ema_fast": 50, "ema_slow": 200,
        "breakout_window": 20,
        "rs_weights": {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2},
        "default_forward_days": 20,
        "desc": "ค่ามาตรฐานของ v25 เดิม — สมดุลระหว่างสั้นและยาว",
    },
}

# ------------------------------------------------------------
# REFERENCE UNIVERSE — v26
# RS Rank is a PERCENTILE, so it is only meaningful when ranked
# against a reasonably large, diverse universe. In v25, if a user
# only typed 3-5 tickers, "RS Rank 92" just meant "best of 5" —
# nearly meaningless. These ~50 liquid large-caps across sectors
# are always pulled in as a ranking backdrop (loaded quietly,
# NOT shown in the results table unless the user also typed them),
# so RS Rank reflects real standing vs the broad market.
# ------------------------------------------------------------
REFERENCE_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AVGO", "TSLA", "AMD", "TSM",
    "CRM", "ORCL", "ADBE", "NOW", "PLTR", "SNOW", "INTC", "QCOM", "MU", "ARM",
    "JPM", "BAC", "GS", "MS", "V", "MA", "AXP",
    "UNH", "LLY", "JNJ", "PFE", "ABBV", "MRK",
    "XOM", "CVX", "OXY", "SLB",
    "WMT", "COST", "HD", "MCD", "NKE", "SBUX",
    "F", "GM", "RIVN",
    "DIS", "NFLX", "BA", "CAT", "GE",
]

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
def load_data_long(ticker, period="3y"):
    """
    Longer-history loader used only for backtesting. Kept separate from
    load_data() (which stays at 1y for fast live scoring) since pulling
    3y for every ticker on every live scan would be unnecessarily slow.
    """
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, auto_adjust=True)
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
def indicators(df, ema_fast=50, ema_slow=200, breakout_window=20):
    """
    ema_fast/ema_slow/breakout_window are configurable (v26) so the same
    function serves both the "short" and "long" Trading Style presets
    without duplicating logic. Defaults match the original v25 behavior
    (50/200 EMA, 20-day breakout) so nothing changes unless a preset
    other than "ทั้งสอง (ค่าเริ่มต้นเดิม)" is selected.
    """
    df = df.copy()

    # ATR (14, EWM smoothing as before)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift(1)).abs(),
        (df["Low"] - df["Close"].shift(1)).abs()
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(span=14).mean()

    # Trend — column names stay EMA50/EMA200 for backward compatibility
    # with the rest of the codebase (journal CSVs, breakdown labels),
    # even though the actual spans are now configurable per style.
    df["EMA50"] = df["Close"].ewm(span=ema_fast).mean()
    df["EMA200"] = df["Close"].ewm(span=ema_slow).mean()

    # Volume
    df["RVOL"] = df["Volume"] / df["Volume"].rolling(20).mean()

    # Breakout reference — shift(1) so "N-day high" means the highest
    # close over the PRIOR N days, excluding today. Without the shift,
    # today's own close feeds into its own rolling max, so almost any
    # up-day falsely looks like a breakout (today's Close >= max that
    # includes today's Close is true by construction on up-moves).
    df["High20"] = df["Close"].rolling(breakout_window).max().shift(1)

    # MACD (12, 26, 9 — standard)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    return df


def relative_strength_series(stock_close, bench_close, weights=None):
    """
    IBD-style simplified RS line: stock/benchmark ratio,
    then turned into a rolling percentile-style RS score (0-100)
    based on the stock's own RS-line trend.

    v26: `weights` is now a parameter (dict of {lookback_days: weight})
    instead of hardcoded, so the "short" Trading Style preset can weight
    the last 1-3 months heavily (swing trading), while "long" spreads
    weight across 3-12 months (position trading). Defaults to the
    original v25 weighting if not supplied.
    """
    if weights is None:
        weights = {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2}

    aligned = pd.concat([stock_close, bench_close], axis=1).dropna()
    aligned.columns = ["stock", "bench"]
    rs_line = aligned["stock"] / aligned["bench"]

    def pct_change_n(series, n):
        if len(series) <= n:
            return np.nan
        return series.iloc[-1] / series.iloc[-1 - n] - 1

    stock_perf = {n: pct_change_n(aligned["stock"], n) for n in weights}
    bench_perf = {n: pct_change_n(aligned["bench"], n) for n in weights}

    # Relative performance (stock minus benchmark) per period, weighted
    # per the style preset's `weights` dict.
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

    # Breakout (20) — at/near the PRIOR 20-day high (High20 already
    # excludes today via shift(1), so this is a real breakout check,
    # not today's close comparing against itself).
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

    # Momentum (10) — MACD cross AND MACD itself above zero.
    # A MACD-above-signal cross while MACD is still negative just means
    # "less bad than before" — it can fire during a downtrend bounce,
    # not a confirmed uptrend. Requiring MACD > 0 too means the stock's
    # short-term EMA is genuinely above its long-term EMA, not just
    # decelerating its decline.
    pts = 10 if (row["MACD"] > row["MACD_Signal"] and row["MACD"] > 0) else 0
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


def plain_language_summary(ticker, score, breakdown, rs_rank, is_leader):
    """
    v26: One-sentence, non-jargon explanation of WHY a ticker scored what
    it scored — the single biggest "easier to understand" gap in v25,
    where a beginner sees "Score 62, RS 12/25, Breakout 0/20" and has no
    idea what to actually DO with that. This does not add new signal —
    it just translates the existing breakdown into plain Thai.
    """
    if not is_leader:
        return f"{ticker}: ยังไม่ผ่านเกณฑ์ผู้นำตลาด (ราคาต่ำกว่า EMA ยาว หรือ RS Rank ต่ำ) — ยังไม่ควรพิจารณาซื้อ"

    parts = []
    if breakdown.get("Trend", 0) == 20:
        parts.append("เทรนด์ขึ้นชัดเจน")
    elif breakdown.get("Trend", 0) == 10:
        parts.append("เทรนด์เริ่มดีขึ้นแต่ยังไม่ชัด")
    else:
        parts.append("เทรนด์ยังไม่ดี")

    if not np.isnan(rs_rank):
        if rs_rank >= 90:
            parts.append("แข็งแกร่งกว่าตลาดมาก (RS Rank ติดกลุ่มบนสุด)")
        elif rs_rank >= 80:
            parts.append("แข็งแกร่งกว่าตลาด")
        elif rs_rank >= 70:
            parts.append("แข็งแกร่งกว่าตลาดพอประมาณ")
        else:
            parts.append("อ่อนแรงกว่าตลาด")

    if breakdown.get("Breakout", 0) == 20:
        parts.append("ราคากำลังทำจุดสูงใหม่ (breakout)")
    elif breakdown.get("Breakout", 0) == 10:
        parts.append("ใกล้จุดสูงเดิม")

    if breakdown.get("Volume", 0) == 15:
        parts.append("มีวอลุ่มหนุนชัดเจน")
    elif breakdown.get("Chop Capped"):
        parts.append("⚠️ วอลุ่มน้อยวันนี้ — คะแนนถูกจำกัดไว้ที่ 40 เพราะไม่มีแรงซื้อขายจริงรองรับ")

    if breakdown.get("Momentum", 0) == 10:
        parts.append("โมเมนตัม (MACD) เป็นบวก")

    if breakdown.get("Market", 0) == 0:
        parts.append("แต่ตลาดรวมยังอยู่ในช่วงขาลง (ควรระวัง/ลดขนาดไม้)")

    verdict = classify(score)
    return f"{ticker} ({verdict}, {score}/100): " + " · ".join(parts)


# ============================================================
# POSITION SIZING — Risk Per Trade vs Portfolio Heat (separated)
# ============================================================
def position_size(capital, entry_price, atr, risk_per_trade_pct, atr_multiple, max_position_pct=100.0):
    """
    1R = ATR * atr_multiple (stop distance)
    Risk per trade = capital * risk_per_trade_pct
    Shares = Risk per trade / stop distance

    The risk-based share count alone can produce a position whose
    dollar value exceeds available capital — this happens whenever
    the stop is tight relative to price (e.g. a high-priced, low-ATR
    stock), since risk-based sizing has no awareness of price itself.
    max_position_pct caps the position's dollar value as a percentage
    of capital (default 100% = never use leverage / never exceed
    available cash) and shares are reduced accordingly if the
    risk-based count would breach that cap.
    """
    stop_distance = atr * atr_multiple
    if stop_distance <= 0 or entry_price <= 0:
        return 0, 0, 0, False

    risk_dollars = capital * (risk_per_trade_pct / 100)
    shares_by_risk = int(risk_dollars / stop_distance)

    max_position_value = capital * (max_position_pct / 100)
    max_shares_by_capital = int(max_position_value / entry_price)

    capped = shares_by_risk > max_shares_by_capital
    shares = min(shares_by_risk, max_shares_by_capital)

    position_value = shares * entry_price
    return shares, position_value, risk_dollars, capped


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
# BACKTEST ENGINE
# ============================================================
def run_backtest(ticker_dfs: dict, spy_df_full: pd.DataFrame, forward_days: int,
                  rebalance_every: int = 5, min_history: int = 260,
                  market_leader_filter: bool = True, progress_callback=None,
                  ema_fast: int = 50, ema_slow: int = 200, breakout_window: int = 20,
                  rs_weights: dict = None):
    """
    Walk-forward backtest. For each evaluation date T (every
    `rebalance_every` trading days, to keep runtime reasonable), for
    every ticker:
      1. Compute indicators using ONLY data up to and including T
         (indicators() and High20.shift(1) already prevent the
         indicator itself from leaking T+1 information).
      2. Compute that day's RS Rank cross-sectionally against every
         other ticker in the universe ON THAT SAME DATE (not today's
         rank applied retroactively — each date gets its own rank).
      3. Score the setup and classify it (ELITE BUY / BUY / WATCH / AVOID).
      4. Look FORWARD `forward_days` trading days and record the
         realized return from T's close to T+forward_days's close.
         If T+forward_days doesn't exist yet (too close to the most
         recent date), that row is skipped — it has no resolved outcome.

    This directly tests the claim the scoring system makes: "a higher
    score should predict better forward returns." It does not simulate
    position sizing, stops, or slippage — it isolates the SIGNAL itself.

    v26: ema_fast/ema_slow/breakout_window/rs_weights let the backtest
    mirror whichever Trading Style preset is active live, instead of
    always testing the old fixed 50/200/20 setup regardless of what's
    actually being used to scan.

    Returns a DataFrame with one row per (date, ticker) evaluation.
    """
    # Pre-compute indicators once per ticker (uses full history, but
    # indicators at row i only ever depend on rows <= i, so slicing to
    # i for cross-sectional scoring on date i is still leakage-free).
    prepped = {}
    for tkr, df in ticker_dfs.items():
        if df is None or len(df) < min_history:
            continue
        prepped[tkr] = indicators(df, ema_fast, ema_slow, breakout_window)

    if spy_df_full is None or len(spy_df_full) < min_history:
        return pd.DataFrame()
    spy_prepped = indicators(spy_df_full, ema_fast, ema_slow, breakout_window)

    if not prepped:
        return pd.DataFrame()

    # Common date index — only dates where SPY has data; individual
    # tickers are matched by nearest available date via reindex/ffill
    # is NOT used here (no leakage tolerance), we use direct index
    # intersection instead so a missing day just skips that ticker.
    all_dates = spy_prepped.index

    rows = []
    eval_positions = list(range(min_history, len(all_dates) - forward_days, rebalance_every))
    total_steps = len(eval_positions)

    for step_i, i in enumerate(eval_positions):
        eval_date = all_dates[i]
        target_idx = i + forward_days
        if target_idx >= len(all_dates):
            continue
        target_date = all_dates[target_idx]

        spy_row = spy_prepped.loc[eval_date]
        spy_bullish = bool(spy_row["Close"] > spy_row["EMA200"]) if not pd.isna(spy_row["EMA200"]) else False

        # Cross-sectional RS for this date only
        raw_rel = {}
        last_rows = {}
        for tkr, df in prepped.items():
            if eval_date not in df.index:
                continue
            # Slice strictly up to eval_date — no future leakage
            df_upto = df.loc[:eval_date]
            if len(df_upto) < min_history:
                continue
            spy_upto = spy_prepped.loc[:eval_date]
            _, rel_score = relative_strength_series(df_upto["Close"], spy_upto["Close"], rs_weights)
            raw_rel[tkr] = rel_score
            last_rows[tkr] = df_upto.iloc[-1]

        if not raw_rel:
            continue
        rs_ranks_today = rs_rank_from_universe(raw_rel)

        for tkr, row in last_rows.items():
            rs_rank = rs_ranks_today.get(tkr, np.nan)
            is_leader = bool(row["Close"] > row["EMA200"]) and (not np.isnan(rs_rank) and rs_rank > 70)

            if market_leader_filter and not is_leader:
                score = 0
                action = "❌ AVOID (Not Leader)"
            else:
                score, _ = compute_score(row, rs_rank, spy_bullish)
                action = classify(score)

            # Forward return: entry at eval_date close, exit at target_date close
            df_full = prepped[tkr]
            if target_date not in df_full.index:
                continue
            entry_price = row["Close"]
            exit_price = df_full.loc[target_date, "Close"]
            if entry_price <= 0:
                continue
            fwd_return_pct = (exit_price - entry_price) / entry_price * 100

            rows.append({
                "Date": eval_date,
                "Ticker": tkr,
                "Score": score,
                "Action": action,
                "RS Rank": round(rs_rank, 1) if not np.isnan(rs_rank) else None,
                "Entry": round(entry_price, 2),
                "Exit": round(exit_price, 2),
                "Forward Return %": round(fwd_return_pct, 2),
            })

        if progress_callback and total_steps > 0:
            progress_callback((step_i + 1) / total_steps)

    return pd.DataFrame(rows)


def summarize_backtest(bt_df: pd.DataFrame):
    """
    Aggregate backtest results by Action bucket: count, win rate
    (forward return > 0), average forward return, median forward
    return. This is the table that answers "does ELITE BUY actually
    outperform AVOID, or do they look the same?"
    """
    if bt_df.empty:
        return pd.DataFrame()

    def win_rate(s):
        return (s > 0).mean() * 100

    summary = (
        bt_df.groupby("Action")["Forward Return %"]
        .agg(
            Trades="count",
            Win_Rate=win_rate,
            Avg_Return="mean",
            Median_Return="median",
            Std_Dev="std",
        )
        .round(2)
    )
    # Order buckets logically rather than alphabetically
    order = ["🚀 ELITE BUY", "🔥 BUY", "👀 WATCH", "❌ AVOID", "❌ AVOID (Not Leader)"]
    summary = summary.reindex([o for o in order if o in summary.index])
    summary = summary.rename(columns={
        "Win_Rate": "Win Rate %",
        "Avg_Return": "Avg Return %",
        "Median_Return": "Median Return %",
        "Std_Dev": "Std Dev %",
    })
    return summary.reset_index()


# ============================================================
# UI
# ============================================================
st.title("🦅 Stock Hunter Pro v26")
st.caption("100-point scoring · RS Rank vs SPY (จัดอันดับเทียบ universe กว้าง) · MACD(0-confirmed) · Market Regime Filter · Capital-capped Sizing · Sector Rotation+Chart · Trailing Stop · Gap Warning · RS Line Chart · Trade Journal · Equity Curve")
st.caption(
    "⚠️ เครื่องมือนี้เป็น**เทคนิคัลสกรีนเนอร์** ช่วยจัดลำดับความน่าสนใจตามกฎที่ตั้งไว้ล่วงหน้า "
    "ไม่มีระบบใดพยากรณ์ราคาได้แม่นยำ 100% — ใช้ประกอบการตัดสินใจ ไม่ใช่คำแนะนำการลงทุน "
    "และควรทดสอบ (ดูแท็บ Backtest) ก่อนใช้เงินจริงเสมอ"
)

with st.sidebar:
    st.header("⚙️ Settings")

    display_mode = st.radio(
        "โหมดแสดงผล", ["ง่าย (Simple)", "ละเอียด (Advanced)"], index=0, horizontal=True,
        help="โหมดง่าย: ซ่อนการตั้งค่าที่ซับซ้อน ใช้ค่าที่แนะนำให้อัตโนมัติ เหมาะกับผู้เริ่มต้น"
    )
    simple_mode = display_mode.startswith("ง่าย")

    trade_style = st.selectbox(
        "🎯 สไตล์การเทรด (Trading Style)",
        list(TRADE_STYLE_PRESETS.keys()),
        index=2,
        help="ปรับ EMA / ระยะ Breakout / น้ำหนัก RS ให้เหมาะกับกรอบเวลาที่คุณจะถือ — ไม่ใช่แค่เปลี่ยน UI แต่เปลี่ยนตัวเลขจริงที่ใช้คำนวณคะแนน"
    )
    preset = TRADE_STYLE_PRESETS[trade_style]
    st.caption(f"ℹ️ {preset['desc']}")

    capital = st.number_input("Capital ($)", value=100000, step=1000)

    if simple_mode:
        # Simple mode: sensible fixed defaults, no extra knobs to confuse
        # a beginner. Advanced users can switch to see/tune everything.
        risk_per_trade_pct = 1.0
        portfolio_heat_pct = 5.0
        atr_multiple = 2.0
        max_position_pct = 20.0
        use_market_leader_filter = True
        earnings_days_filter = EARNINGS_BLACKOUT_DAYS
        gap_threshold_pct = 3.0
        journal_enabled = True
        st.caption(
            "โหมดง่าย: ใช้ค่ามาตรฐาน (Risk 1%/ไม้, Heat รวม 5%, Stop = ATR×2, "
            "Max position 20% ของทุน) — สลับเป็น 'ละเอียด' ด้านบนเพื่อปรับเอง"
        )
    else:
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
        max_position_pct = st.number_input(
            "Max Position Size (% of Capital)", value=20.0, min_value=1.0, max_value=100.0, step=1.0,
            help="จำกัดมูลค่า Position สูงสุดต่อไม้ ไม่ให้เกิน % นี้ของ Capital ทั้งหมด — ป้องกัน Risk-based sizing คำนวณ shares เยอะเกินจนเกินเงินที่มีจริง (เช่น หุ้นแพงแต่ ATR แคบ)"
        )

        st.subheader("Filters")
        use_market_leader_filter = st.checkbox(
            "Market Leader Filter (Close > EMA ยาว AND RS Rank > 70)", value=True,
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

    max_positions = int(portfolio_heat_pct / risk_per_trade_pct) if risk_per_trade_pct > 0 else 0
    st.info(f"📊 เปิดได้สูงสุด **{max_positions} ไม้** พร้อมกัน (ไม้ละ {risk_per_trade_pct:.1f}% risk, รวมไม่เกิน {portfolio_heat_pct:.1f}% heat)")

user_input = st.text_input(
    "พิมพ์ชื่อหุ้นที่ต้องการ (คั่นด้วยลูกน้ำ เช่น AAPL, MSFT, SMCI):",
    "NVDA, PLTR, AMD, TSLA, META, AAPL, MSFT, GOOGL"
)
tickers = [t.strip().upper() for t in user_input.split(",") if t.strip()]
if len(set(tickers)) < 5:
    st.caption(
        "💡 พิมพ์หุ้นน้อยกว่า 5 ตัว ไม่เป็นไร — RS Rank ยังคำนวณเทียบกับ universe อ้างอิง ~50 หุ้นใหญ่เบื้องหลังให้อัตโนมัติ "
        "(v26) เพื่อให้เปอร์เซ็นไทล์มีความหมายจริง ไม่ใช่แค่จัดอันดับในหุ้นไม่กี่ตัวที่คุณพิมพ์"
    )

# Initialize journal state immediately so any section (e.g. Portfolio
# Dashboard, which appears before the Trade Journal UI further down)
# can safely read st.session_state.journal_df without a KeyError.
if "journal_df" not in st.session_state:
    st.session_state.journal_df = pd.DataFrame(columns=JOURNAL_COLUMNS)

# ------------------------------------------------------------
# Load benchmark (SPY) once
# ------------------------------------------------------------
spy_df = load_data(BENCHMARK)
spy_bullish = False
if spy_df is not None:
    spy_df = indicators(spy_df, preset["ema_fast"], preset["ema_slow"], preset["breakout_window"])
    spy_bullish = bool(spy_df["Close"].iloc[-1] > spy_df["EMA200"].iloc[-1])
else:
    st.error(
        "❌ โหลดข้อมูล SPY (benchmark) ไม่สำเร็จ — อาจเป็นปัญหาการเชื่อมต่อกับ Yahoo Finance ชั่วคราว "
        "ลองรีเฟรชหน้าอีกครั้งใน 1-2 นาที คะแนนทั้งหมดด้านล่างจะไม่แม่นยำจนกว่าจะโหลด SPY ได้"
    )

market_status = "🟢 BULLISH (SPY > EMA ยาว)" if spy_bullish else "🔴 BEARISH (SPY < EMA ยาว)"
st.subheader(f"Market Regime: {market_status}")
if not spy_bullish:
    st.warning("⚠️ ตลาดรวมอยู่ใต้ EMA ยาว — Market Filter จะหัก 10 คะแนนจากทุกหุ้น และควรพิจารณาลดขนาดการเปิดสถานะใหม่")

# ------------------------------------------------------------
# Load all tickers + compute raw RS first (need full universe).
# v26: also silently load a fixed REFERENCE_UNIVERSE alongside the
# user's tickers, purely to make the RS Rank percentile meaningful
# (see comment on REFERENCE_UNIVERSE above). Reference tickers are
# NOT added to ticker_data/results — they never appear in the output
# table unless the user also typed them explicitly.
# ------------------------------------------------------------
ticker_data = {}
raw_rel_scores = {}
rs_lines = {}        # ticker -> RS line series (stock/SPY ratio), for charting
gap_info = {}        # ticker -> (gap_pct, is_high_gap, live_price, source_label)
failed_tickers = []  # tickers that failed to load, shown to the user instead of silently vanishing

ranking_universe = list(dict.fromkeys(tickers + [r for r in REFERENCE_UNIVERSE if r not in tickers]))

progress = st.progress(0.0, text="กำลังโหลดข้อมูลหุ้น...")
for i, t in enumerate(ranking_universe):
    is_user_ticker = t in tickers
    df = load_data(t)
    if df is None or len(df) < 30:
        if is_user_ticker:
            failed_tickers.append(t)
        progress.progress((i + 1) / len(ranking_universe))
        continue
    df = indicators(df, preset["ema_fast"], preset["ema_slow"], preset["breakout_window"])

    if spy_df is not None:
        rs_line, rel_score = relative_strength_series(df["Close"], spy_df["Close"], preset["rs_weights"])
        raw_rel_scores[t] = rel_score
    else:
        rel_score = np.nan
        rs_line = None
        raw_rel_scores[t] = np.nan

    # Everything below this line is only needed for tickers the user
    # actually asked about — reference-universe tickers stop here.
    if is_user_ticker:
        ticker_data[t] = df
        rs_lines[t] = rs_line
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
    progress.progress((i + 1) / len(ranking_universe))
progress.empty()

if failed_tickers:
    st.warning(
        f"⚠️ โหลดข้อมูลไม่สำเร็จ: {', '.join(failed_tickers)} — ตรวจสอบว่าสะกดชื่อ ticker ถูกต้อง "
        "(ใช้ symbol แบบ Yahoo Finance เช่น BRK-B ไม่ใช่ BRK.B), หุ้นยังซื้อขายอยู่จริง, หรือมีข้อมูลย้อนหลังพอ (≥30 วัน)"
    )

rs_ranks = rs_rank_from_universe(raw_rel_scores)

# ------------------------------------------------------------
# Score each ticker
# ------------------------------------------------------------
results = []
detail_rows = {}
leader_map = {}

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

    shares, position_value, risk_dollars, size_capped = position_size(
        capital, last["Close"], last["ATR"], risk_per_trade_pct, atr_multiple, max_position_pct
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
        "Size Capped": "⚠️ Capital cap" if size_capped else "",
    })
    detail_rows[t] = breakdown
    leader_map[t] = is_leader

results_df = pd.DataFrame(results).sort_values("Score", ascending=False).reset_index(drop=True)

st.dataframe(results_df, use_container_width=True)

# ------------------------------------------------------------
# Plain-language summaries (v26) — translates the breakdown into a
# one-line, jargon-free sentence per ticker so a beginner doesn't
# need to decode "RS 12/25, Breakout 0/20" themselves.
# ------------------------------------------------------------
if not results_df.empty:
    with st.expander("💬 สรุปง่ายๆ ทีละตัว (Plain-language Summary)", expanded=simple_mode):
        for t in results_df["Ticker"]:
            rs_rank_t = rs_ranks.get(t, np.nan)
            score_t = results_df.loc[results_df["Ticker"] == t, "Score"].iloc[0]
            summary_line = plain_language_summary(t, score_t, detail_rows[t], rs_rank_t, leader_map.get(t, False))
            st.markdown(f"- {summary_line}")

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
# Backtest — v26. The v25 file already contained a full walk-forward
# backtest engine (run_backtest / summarize_backtest) but it was NEVER
# called from the UI — dead code. This is the single biggest lever for
# "accurate prediction that actually helps real trading": it directly
# answers "does a higher Score actually predict better forward returns
# for THESE stocks?" instead of just trusting the scoring rules on
# faith. Opt-in via a button since it re-downloads longer history and
# can take a while for many tickers.
# ------------------------------------------------------------
st.subheader("🧪 Backtest — เช็คว่า Score นี้เคยทำนายผลตอบแทนได้จริงหรือไม่")
st.caption(
    "รันทดสอบย้อนหลังกับหุ้นที่พิมพ์ไว้ด้านบน เพื่อดูว่ากลุ่ม ELITE BUY/BUY ในอดีตให้ผลตอบแทน "
    "ไปข้างหน้าดีกว่ากลุ่ม AVOID จริงหรือไม่ (ทดสอบเฉพาะ 'สัญญาณ' ไม่รวม stop-loss/ค่าคอมมิชชั่น/slippage "
    "จึงไม่ใช่ผลตอบแทนที่จะได้จริงจากการเทรด — ใช้เพื่อประเมินว่าคะแนนมีความหมายหรือไม่เท่านั้น)"
)
with st.expander("⚙️ ตั้งค่า & รัน Backtest", expanded=False):
    bt_forward_days = st.number_input(
        "มองไปข้างหน้ากี่วันทำการ (Forward Days)", value=preset["default_forward_days"],
        min_value=1, max_value=120, step=1,
        help="ระยะเวลาถือหลังสัญญาณก่อนวัดผลตอบแทน — ตั้งให้ใกล้เคียงกับที่ตั้งใจจะถือจริงตามสไตล์การเทรด"
    )
    bt_rebalance = st.number_input("ประเมินทุกกี่วันทำการ (Rebalance Every)", value=5, min_value=1, max_value=20, step=1)
    bt_period = st.selectbox("ช่วงข้อมูลย้อนหลัง", ["2y", "3y", "5y"], index=1)
    bt_use_reference = st.checkbox(
        "รวม Reference Universe (~50 หุ้น) ใน RS Rank ของ Backtest ด้วย",
        value=False,
        help="แม่นยำกว่า (RS Rank เทียบตลาดกว้างเหมือนตอนใช้งานจริง) แต่ช้ากว่ามาก — ถ้าปิดไว้ RS Rank ในการทดสอบจะจัดอันดับเฉพาะในกลุ่มหุ้นที่พิมพ์เท่านั้น"
    )
    run_bt = st.button("▶️ รัน Backtest")

if run_bt:
    if len(tickers) < 3:
        st.warning("ควรพิมพ์หุ้นอย่างน้อย 3 ตัว เพื่อให้การจัดอันดับ RS Rank แบบ cross-sectional มีความหมาย")
    else:
        bt_universe = list(dict.fromkeys(tickers + REFERENCE_UNIVERSE)) if bt_use_reference else tickers
        with st.spinner(f"กำลังโหลดข้อมูล {bt_period} และรัน backtest ({len(bt_universe)} หุ้น)..."):
            bt_ticker_dfs = {t: load_data_long(t, period=bt_period) for t in bt_universe}
            spy_full = load_data_long(BENCHMARK, period=bt_period)
            bt_progress_bar = st.progress(0.0)
            bt_df = run_backtest(
                bt_ticker_dfs, spy_full, forward_days=bt_forward_days,
                rebalance_every=bt_rebalance, market_leader_filter=use_market_leader_filter,
                progress_callback=lambda p: bt_progress_bar.progress(p),
                ema_fast=preset["ema_fast"], ema_slow=preset["ema_slow"],
                breakout_window=preset["breakout_window"], rs_weights=preset["rs_weights"],
            )
            bt_progress_bar.empty()

        if bt_df.empty:
            st.warning("ไม่มีข้อมูลพอสำหรับ backtest — ลองเพิ่มช่วงข้อมูลย้อนหลัง หรือลด Forward Days")
        else:
            # Only keep rows for tickers the user actually typed, even if
            # the reference universe was included for RS Rank purposes.
            bt_df_display = bt_df[bt_df["Ticker"].isin(tickers)].reset_index(drop=True)
            summary = summarize_backtest(bt_df_display)
            st.dataframe(summary, use_container_width=True)
            if not summary.empty and "Avg Return %" in summary.columns:
                st.bar_chart(summary.set_index("Action")["Avg Return %"])
            st.caption(
                "อ่านผล: ถ้า ELITE BUY/BUY มี Win Rate และ Avg Return สูงกว่า AVOID อย่างชัดเจน แปลว่า "
                "คะแนนมีความหมายจริงสำหรับหุ้นและช่วงเวลานี้ — แต่ผลย้อนหลังไม่การันตีอนาคต และตัวเลขจากไม้น้อย "
                "ยังไม่มีนัยสำคัญทางสถิติ ควรดูจำนวน Trades ประกอบเสมอ"
            )
            st.download_button(
                "⬇️ ดาวน์โหลดผล Backtest แบบละเอียด (CSV)",
                data=bt_df_display.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"backtest_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

# ------------------------------------------------------------
# Portfolio Dashboard — the at-a-glance view a trader checks every
# day: current heat, exposure, cash remaining, open positions. Built
# from the Trade Journal's OPEN rows (if journal is enabled and has
# data), since that's the actual record of what's currently held —
# the scanner table above is candidates, not your real positions.
# ------------------------------------------------------------
st.subheader("📊 Portfolio Dashboard")

if journal_enabled and "journal_df" in st.session_state and not st.session_state.journal_df.empty:
    open_now = st.session_state.journal_df[st.session_state.journal_df["Status"] == "Open"].copy()
else:
    open_now = pd.DataFrame()

if not open_now.empty:
    open_now["Entry"] = pd.to_numeric(open_now["Entry"], errors="coerce")
    open_now["Shares"] = pd.to_numeric(open_now["Shares"], errors="coerce")
    open_now["Position Value"] = open_now["Entry"] * open_now["Shares"]
    total_exposure = open_now["Position Value"].sum()
    cash_remaining = capital - total_exposure

    # Current heat = sum of risk $ per open position, using each position's
    # own ATR-based stop distance recomputed from current data if available,
    # otherwise fall back to the recorded Stop at entry time.
    current_risk_total = 0.0
    for _, r in open_now.iterrows():
        tkr = r["Ticker"]
        entry_p = r["Entry"]
        stop_p = pd.to_numeric(r.get("Stop"), errors="coerce")
        shares_n = r["Shares"]
        if pd.notna(stop_p) and pd.notna(entry_p) and pd.notna(shares_n):
            current_risk_total += abs(entry_p - stop_p) * shares_n

    current_heat_pct = (current_risk_total / capital * 100) if capital > 0 else 0

    pc1, pc2, pc3, pc4, pc5 = st.columns(5)
    pc1.metric("Open Positions", f"{len(open_now)}")
    pc2.metric("Total Exposure", f"${total_exposure:,.0f}")
    pc3.metric("Cash Remaining", f"${cash_remaining:,.0f}")
    pc4.metric("Current Risk ($)", f"${current_risk_total:,.0f}")
    pc5.metric("Current Heat", f"{current_heat_pct:.1f}%",
               delta=f"จำกัด {portfolio_heat_pct:.1f}%", delta_color="off")

    if current_heat_pct > portfolio_heat_pct:
        st.error(f"🚨 Current Heat ({current_heat_pct:.1f}%) เกิน Portfolio Heat ที่ตั้งไว้ ({portfolio_heat_pct:.1f}%) — พิจารณาลด position หรืองดเปิดไม้ใหม่")
    elif cash_remaining < 0:
        st.error(f"🚨 Exposure รวม (${total_exposure:,.0f}) เกิน Capital ที่มี (${capital:,.0f})")

    st.dataframe(
        open_now[["Ticker", "Entry", "Stop", "Shares", "Position Value", "Date"]],
        use_container_width=True
    )
else:
    st.caption(
        "ยังไม่มีสถานะที่เปิดอยู่ใน Trade Journal — Portfolio Dashboard จะแสดงเมื่อมีการบันทึก 'เปิดสถานะ' "
        "ในส่วน Trade Journal ด้านล่าง (ต้องเปิดใช้ Trade Journal ใน sidebar ก่อน)"
    )

# ------------------------------------------------------------
# Sector Rotation view — avg RS Rank / Score per group shows
# where money is actually flowing today.
# v26: tucked behind Advanced mode — genuinely useful, but one more
# table a beginner has to parse before finding "should I buy this."
# ------------------------------------------------------------
if not simple_mode and not results_df.empty:
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
        st.bar_chart(sector_summary.set_index("Sector")["Avg RS Rank"])
        st.caption("Avg RS Rank สูง = เงินไหลเข้ากลุ่มนี้มากกว่าตลาดโดยรวม")
    else:
        st.caption("ไม่มีข้อมูล RS Rank พอสำหรับสรุปตาม Sector")

# ------------------------------------------------------------
# RS Line chart — stock/SPY ratio over time. Rising = stock leading
# the market; falling = stock losing relative strength, often BEFORE
# price itself rolls over. Kept behind Advanced mode for the same
# reason as Sector Rotation above.
# ------------------------------------------------------------
if not simple_mode:
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

    # JOURNAL_COLUMNS already defined at module level (top of file)
    if "journal_df" not in st.session_state:
        st.session_state.journal_df = pd.DataFrame(columns=JOURNAL_COLUMNS)

    uploaded_journal = st.file_uploader(
        "อัปโหลด Trade Journal เดิม (CSV) เพื่อบันทึกต่อ — ไม่บังคับ", type=["csv"], key="journal_upload"
    )
    if uploaded_journal is not None:
        try:
            loaded = pd.read_csv(uploaded_journal)
            # Backward-compatible: old journals (v24) won't have the new
            # Status/Exit/Exit Date/PnL columns — add them as empty/Open.
            for col in JOURNAL_COLUMNS:
                if col not in loaded.columns:
                    loaded[col] = "Open" if col == "Status" else None
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

    if st.button("💾 บันทึกลง Journal (เปิดสถานะ)", disabled=(journal_ticker not in ticker_data)):
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
                "Status": "Open",
                "Exit": None,
                "Exit Date": None,
                "PnL": None,
            }])
            st.session_state.journal_df = pd.concat([st.session_state.journal_df, new_entry], ignore_index=True)
            st.success(f"บันทึก {journal_ticker} ลง Journal แล้ว (Open)")

    # ------------------------------------------------------------
    # Close a trade — required to compute realized P&L and plot the
    # equity curve. Without an exit price there is no "result" to
    # measure, so the equity curve only includes Closed trades.
    # ------------------------------------------------------------
    open_trades = st.session_state.journal_df[st.session_state.journal_df["Status"] == "Open"]
    if not open_trades.empty:
        st.markdown("**ปิดสถานะที่เปิดอยู่ (เพื่อบันทึกผลลัพธ์จริง):**")
        oc1, oc2, oc3 = st.columns([1, 1, 1])
        with oc1:
            close_idx = st.selectbox(
                "เลือกรายการที่จะปิด",
                open_trades.index,
                format_func=lambda i: f"{open_trades.loc[i, 'Ticker']} @ {open_trades.loc[i, 'Date']}",
                key="close_trade_select",
            )
        with oc2:
            exit_price_input = st.number_input("ราคาที่ขายจริง", value=float(open_trades.loc[close_idx, "Entry"]), step=0.5, key="exit_price_input")
        with oc3:
            if st.button("✅ ปิดสถานะนี้"):
                entry_p = float(st.session_state.journal_df.loc[close_idx, "Entry"])
                shares_n = float(st.session_state.journal_df.loc[close_idx, "Shares"]) if st.session_state.journal_df.loc[close_idx, "Shares"] else 0
                pnl = (exit_price_input - entry_p) * shares_n
                st.session_state.journal_df.loc[close_idx, "Exit"] = exit_price_input
                st.session_state.journal_df.loc[close_idx, "Exit Date"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                st.session_state.journal_df.loc[close_idx, "Status"] = "Closed"
                st.session_state.journal_df.loc[close_idx, "PnL"] = round(pnl, 2)
                st.success(f"ปิดสถานะแล้ว P&L = ${pnl:,.2f}")

    if not st.session_state.journal_df.empty:
        st.dataframe(st.session_state.journal_df, use_container_width=True)
        csv_bytes = st.session_state.journal_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ ดาวน์โหลด Trade Journal (CSV)",
            data=csv_bytes,
            file_name=f"trade_journal_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

        # --------------------------------------------------------
        # Equity Curve — cumulative realized P&L over closed trades,
        # ordered by exit date. Only Closed trades have a real P&L;
        # Open trades aren't included since their result isn't known.
        # --------------------------------------------------------
        closed = st.session_state.journal_df[st.session_state.journal_df["Status"] == "Closed"].copy()
        if not closed.empty:
            closed["PnL"] = pd.to_numeric(closed["PnL"], errors="coerce")
            closed = closed.dropna(subset=["PnL"])
            closed["Exit Date"] = pd.to_datetime(closed["Exit Date"], errors="coerce")
            closed = closed.sort_values("Exit Date")
            closed["Cumulative PnL"] = closed["PnL"].cumsum()

            st.subheader("📈 Equity Curve (Cumulative Realized P&L)")
            equity_series = closed.set_index("Exit Date")["Cumulative PnL"]
            st.line_chart(equity_series)
            total_pnl = closed["PnL"].sum()
            win_rate = (closed["PnL"] > 0).mean() * 100
            ec1, ec2, ec3 = st.columns(3)
            ec1.metric("Total Realized P&L", f"${total_pnl:,.2f}")
            ec2.metric("Win Rate", f"{win_rate:.0f}%")
            ec3.metric("Closed Trades", f"{len(closed)}")
            st.caption("เฉพาะรายการที่ปิดสถานะแล้ว (Status = Closed) เท่านั้นที่นำมาคำนวณ — รายการ Open ยังไม่มีผลลัพธ์จริง")

            # ----------------------------------------------------
            # Journal Analytics — the question ChatGPT flagged as
            # more valuable than more indicators: "Score 90+ trades —
            # what was the actual win rate and average gain?" This
            # uses YOUR real closed trades, not a theoretical backtest.
            # ----------------------------------------------------
            st.subheader("🔬 Journal Analytics — Win Rate by Score Band")
            closed["Score"] = pd.to_numeric(closed["Score"], errors="coerce")
            closed["Return %"] = (closed["PnL"] / (closed["Entry"].astype(float) * closed["Shares"].astype(float))) * 100

            def score_band(s):
                if pd.isna(s):
                    return "Unknown"
                if s >= 90:
                    return "90-100"
                elif s >= 80:
                    return "80-89"
                elif s >= 70:
                    return "70-79"
                elif s >= 55:
                    return "55-69"
                else:
                    return "<55"

            closed["Score Band"] = closed["Score"].apply(score_band)
            band_order = ["90-100", "80-89", "70-79", "55-69", "<55", "Unknown"]

            band_summary = (
                closed.groupby("Score Band")
                .agg(
                    Trades=("PnL", "count"),
                    Win_Rate=("PnL", lambda s: (s > 0).mean() * 100),
                    Avg_Gain_Pct=("Return %", "mean"),
                    Avg_PnL=("PnL", "mean"),
                )
                .round(2)
                .reindex([b for b in band_order if b in closed["Score Band"].unique()])
                .rename(columns={"Win_Rate": "Win Rate %", "Avg_Gain_Pct": "Avg Gain %", "Avg_PnL": "Avg PnL $"})
                .reset_index()
            )
            st.dataframe(band_summary, use_container_width=True)
            st.caption(
                "ตอบคำถาม: 'หุ้นที่ Score 90+ ที่ผมเข้าเทรดจริง Win Rate เท่าไหร่ กำไรเฉลี่ยเท่าไหร่' "
                "จากข้อมูลการเทรดจริงของคุณเอง ไม่ใช่ทฤษฎี — ยิ่งสะสมข้อมูลเยอะ ยิ่งเชื่อถือได้มากขึ้น "
                "(ตัวเลขจากไม้น้อยๆ ยังไม่มีนัยสำคัญทางสถิติ)"
            )
        else:
            st.caption("ยังไม่มีรายการที่ปิดสถานะ — Equity Curve จะแสดงเมื่อมีการปิดสถานะอย่างน้อย 1 รายการ")
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
