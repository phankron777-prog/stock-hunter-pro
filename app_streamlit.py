"""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║        🦅  S T O C K   H U N T E R   S U P E R   A P P   v 4 . 0        ║
║                                                                          ║
║   ✨ แนะนำการเทรดระยะสั้นรายวัน/รายสัปดาห์ (จากข้อมูลจริง)           ║
║   🔌 เชื่อมต่อ Yahoo Finance API + SET API จริง                       ║
║   📊 Technical Analysis: RSI, MACD, EMA, Bollinger, ATR, Pivot        ║
║   📰 News Sentiment Analysis (Yahoo Finance + Google News)             ║
║   🧪 Backtesting + Portfolio Simulator                                 ║
║   ☁️  พร้อม Deploy บน Streamlit Cloud                                  ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pytz
import time
import sys
import os

# ── Path setup ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import (
    fetch_stock_data,
    fetch_realtime_price,
    fetch_market_overview,
    fetch_finance_news,
    fetch_stock_news,
    TH_POPULAR_STOCKS,
    US_POPULAR_STOCKS,
    TH_TZ,
    get_thai_date,
    is_market_open,
    get_trading_days_until_friday,
)
from daily_signal_engine import (
    generate_signal,
    generate_daily_recommendations,
    generate_weekly_plan,
    analyze_news_impact,
    calc_rsi,
    calc_ema,
    calc_macd,
    calc_bollinger_bands,
    calc_atr,
)

# ══════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Stock Hunter Super App v4.0",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════════
st.markdown(
    """
    <style>
    .main  { background-color: #0e1117; color: #ffffff; }

    .stButton>button {
        width: 100%; border-radius: 8px; font-weight: 600;
        background: linear-gradient(135deg, #1f77b4, #2eb85c);
        color: white; border: none; padding: 10px 16px;
        transition: all 0.3s;
    }
    .stButton>button:hover { filter: brightness(1.25); transform: translateY(-1px); }

    .stProgress>div>div>div>div { background-color: #2eb85c; }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #1a1f2e; border-radius: 12px; padding: 16px;
        border: 1px solid #2a3040; transition: 0.3s;
    }
    [data-testid="stMetric"]:hover { border-color: #2eb85c; }

    /* Signal badges */
    .signal-strong-buy  { background: #0d5c2e; color: #2eb85c; padding: 4px 12px;
                          border-radius: 20px; font-weight: bold; }
    .signal-buy         { background: #0d3d1f; color: #5cf08a; padding: 4px 12px;
                          border-radius: 20px; font-weight: bold; }
    .signal-sell        { background: #5c0d0d; color: #f05c5c; padding: 4px 12px;
                          border-radius: 20px; font-weight: bold; }
    .signal-hold        { background: #3d3d0d; color: #f0e05c; padding: 4px 12px;
                          border-radius: 20px; font-weight: bold; }

    /* Live dot */
    .live-dot {
        display: inline-block; width: 10px; height: 10px;
        background: #2eb85c; border-radius: 50%;
        animation: blink 1.5s ease-in-out infinite;
    }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }

    /* Responsive */
    @media (max-width: 768px) {
        [data-testid="stMetric"] { margin-bottom: 8px; }
    }

    /* News card */
    .news-card {
        background: #1a1f2e; border-radius: 8px; padding: 12px;
        border-left: 3px solid #2eb85c; margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════
for key, default in [
    ("alerts",            []),
    ("portfolio_sim",     []),
    ("lang",             "TH"),
    ("custom_watchlist", ["NVDA", "AVGO", "PTT", "ADVANC", "AOT"]),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ══════════════════════════════════════════════════════════════════════════
# TRANSLATION
# ══════════════════════════════════════════════════════════════════════════
T = {
    "dashboard":    {"TH": "📈 แดชบอร์ดตลาด",         "EN": "📈 Market Dashboard"},
    "daily":        {"TH": "📅 สัญญาณเทรดรายวัน",     "EN": "📅 Daily Trading Signals"},
    "weekly":       {"TH": "📆 แผนเทรดรายสัปดาห์",   "EN": "📆 Weekly Trading Plan"},
    "screener":     {"TH": "🔍 สแกนเนอร์เทคนิคอล",   "EN": "🔍 Technical Screener"},
    "backtest":     {"TH": "🧪 ทดสอบกลยุทธ์",         "EN": "🧪 Strategy Backtesting"},
    "simulator":    {"TH": "🎮 จำลองการลงทุน",        "EN": "🎮 Portfolio Simulator"},
    "news":         {"TH": "📰 ข่าว & Sentiment",       "EN": "📰 News & Sentiment"},
    "settings":     {"TH": "⚙️ ตั้งค่า",               "EN": "⚙️ Settings"},
}

def t(key):
    return T.get(key, {}).get(st.session_state.lang, key)

# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🦅 Stock Hunter Pro")
    st.markdown("### `v4.0 — Real Data Edition`")

    now = datetime.now(TH_TZ)
    market_th = is_market_open("TH")
    market_us = is_market_open("US")

    st.markdown(
        f"<small>"
        f"<span class='live-dot'></span> ไทย: {'🟢 เปิด' if market_th else '🔴 ปิด'} | "
        f"US: {'🟢 เปิด' if market_us else '🔴 ปิด'}"
        f"</small>",
        unsafe_allow_html=True,
    )

    st.divider()

    # Language
    st.session_state.lang = st.radio(
        "🌐 ภาษา / Language", ["TH", "EN"],
        horizontal=True,
        index=0 if st.session_state.lang == "TH" else 1,
    )

    st.divider()

    # Navigation
    menu = st.radio(
        "🧭 เมนู / Menu",
        [
            t("dashboard"),
            t("daily"),
            t("weekly"),
            t("screener"),
            t("backtest"),
            t("simulator"),
            t("news"),
            t("settings"),
        ],
        index=0,
    )

    st.divider()
    st.caption(f"🇹🇭 {get_thai_date()}")
    st.caption(f"🕐 {now.strftime('%H:%M:%S')} (ICT)")
    st.caption("v4.0 — Built with ❤️ by OWL")


# ══════════════════════════════════════════════════════════════════════════
# HELPER: Format helpers
# ══════════════════════════════════════════════════════════════════════════
def fmt(val, decimals=2):
    return f"{val:,.{decimals}f}"

def fmt_pct(val, decimals=2):
    sign = "+" if val >= 0 else ""
    emoji = "🟢" if val >= 0 else "🔴"
    return f"{emoji} {sign}{val:.{decimals}f}%"

def score_bar(score, width=20):
    """สร้าง progress bar ด้วย emoji"""
    filled = int((score + 100) / 200 * width)  # score -100 to +100
    filled = max(0, min(width, filled))
    empty = width - filled
    return "🟩" * filled + "⬜" * empty


# ══════════════════════════════════════════════════════════════════════════
# MODULE 1: MARKET DASHBOARD
# ══════════════════════════════════════════════════════════════════════════
if menu == t("dashboard"):
    st.title(t("dashboard"))

    # ── Live market overview ──
    with st.spinner("📡 กำลังดึงข้อมูลตลาดล่าสุด..."):
        markets = fetch_market_overview()

    if markets:
        cols = st.columns(5)
        idx = 0
        for name, data in markets.items():
            if idx >= 10:
                break
            col = cols[idx % 5]
            with col:
                currency = data.get("currency", "")
                symbol = "$" if currency in ("USD", "") else ""
                st.metric(
                    name,
                    f"{symbol}{data['price']:,.2f}",
                    fmt_pct(data["pct_change"]),
                )
            idx += 1

    st.divider()

    # ── Quick chart: SET Index ──
    st.subheader("📊 SET Index — 6 เดือน")
    with st.spinner("กำลังดึงข้อมูล SET Index..."):
        set_df = fetch_stock_data("^SET.BK", period="6mo")

    if set_df is not None and len(set_df) > 0:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=set_df.index, y=set_df["Close"],
            mode="lines", name="SET Index",
            line=dict(color="#2eb85c", width=2),
            fill="tozeroy", fillcolor="rgba(46,184,92,0.1)",
        ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#1a1f2e",
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            xaxis=dict(gridcolor="#2a3040"),
            yaxis=dict(gridcolor="#2a3040"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("⚠️ ไม่สามารถดึงข้อมูล SET Index ได้ — ใช้ข้อมูลจำลอง")
        # Fallback chart
        dates = pd.date_range(end=datetime.today(), periods=120, freq="D")
        fallback = pd.DataFrame({
            "Date": dates,
            "SET Index": 1380 + np.cumsum(np.random.randn(120) * 3),
        })
        st.line_chart(fallback.set_index("Date"))

    st.divider()

    # ── Top movers (TH + US) ──
    col_th, col_us = st.columns(2)

    with col_th:
        st.subheader("🇹🇭 หุ้นไทยยอดนิยม")
        th_data = []
        for name, ticker in list(TH_POPULAR_STOCKS.items())[:8]:
            info = fetch_realtime_price(ticker)
            if info:
                th_data.append({
                    "Ticker": name,
                    "Price": f"{info['price']:.2f}",
                    "Change": fmt_pct(info["pct_change"]),
                })
        if th_data:
            st.table(pd.DataFrame(th_data))

    with col_us:
        st.subheader("🇺🇸 หุ้น US ยอดนิยม")
        us_data = []
        for name, ticker in list(US_POPULAR_STOCKS.items())[:8]:
            info = fetch_realtime_price(ticker)
            if info:
                us_data.append({
                    "Ticker": name,
                    "Price": f"${info['price']:.2f}",
                    "Change": fmt_pct(info["pct_change"]),
                })
        if us_data:
            st.table(pd.DataFrame(us_data))


# ══════════════════════════════════════════════════════════════════════════
# MODULE 2: DAILY TRADING SIGNALS (ฟีเจอร์หลักใหม่!)
# ══════════════════════════════════════════════════════════════════════════
elif menu == t("daily"):
    st.title(t("daily"))
    st.markdown("### 🧠 สัญญาณเทรดระยะสั้นจากข้อมูลจริง (Real-time Technical Analysis)")
    st.markdown(
        f"📅 {get_thai_date()} | "
        f"⏰ {datetime.now(TH_TZ).strftime('%H:%M')} ICT | "
        f"📊 วันเทรดที่เหลือ: **{get_trading_days_until_friday()} วัน** (จนถึงศุกร์)"
    )

    st.divider()

    # ── เลือกกลุ่มหุ้น ──
    tab1, tab2, tab3 = st.tabs(["🇹🇭 หุ้นไทย (SET)", "🇺🇸 หุ้น US", "✏️ กำหนดเอง"])

    with tab1:
        target_watchlist = TH_POPULAR_STOCKS
        market_label = "ตลาดหุ้นไทย (SET)"
    with tab2:
        target_watchlist = US_POPULAR_STOCKS
        market_label = "ตลาดหุ้นสหรัฐฯ (US)"
    with tab3:
        custom_input = st.text_input(
            "ใส่ Ticker (คั่นด้วย comma)",
            value=", ".join(st.session_state.custom_watchlist),
        )
        custom_tickers = [t.strip().upper() for t in custom_input.split(",") if t.strip()]
        target_watchlist = {t: t for t in custom_tickers}
        st.session_state.custom_watchlist = custom_tickers
        market_label = "Custom Watchlist"

    # ── ตั้งค่า ──
    col1, col2, col3 = st.columns(3)
    with col1:
        top_n = st.slider("จำนวนหุ้นแนะนำ", 3, 10, 5)
    with col2:
        min_score = st.slider("คะแนนขั้นต่ำ", 0, 50, 15)
    with col3:
        include_news = st.checkbox("📰 รวม News Sentiment", value=True)

    if st.button(f"🔍 สแกนสัญญาณเทรด: {market_label}", type="primary"):
        progress = st.progress(0, text="กำลังดึงข้อมูลราคา...")
        all_recs = []
        tickers_list = list(target_watchlist.items())

        for i, (name, ticker) in enumerate(tickers_list):
            progress.progress(
                int((i + 0.5) / len(tickers_list) * 100),
                text=f"วิเคราะห์ {name} ({i+1}/{len(tickers_list)})...",
            )

            df = fetch_stock_data(ticker, period="6mo")
            if df is None or len(df) < 50:
                continue

            sig = generate_signal(df)
            sig["ticker"] = name
            sig["ticker_yf"] = ticker
            sig["df"] = df

            # News sentiment boost
            if include_news:
                news_result = analyze_news_impact(ticker)
                sig["news_sentiment"] = news_result["sentiment"]
                sig["news_score"] = news_result["score"]
                sig["news_latest"] = news_result["latest"]
                # ปรับคะแนนตาม sentiment
                sig["score"] += news_result["score"] * 0.2  # weight 20%
            else:
                sig["news_sentiment"] = "N/A"
                sig["news_score"] = 0
                sig["news_latest"] = []

            all_recs.append(sig)

        progress.progress(100, text="เสร็จสิ้น!")
        time.sleep(0.3)
        progress.empty()

        # กรองและเรียง
        filtered = [r for r in all_recs if r["score"] >= min_score]
        filtered.sort(key=lambda x: x["score"], reverse=True)
        top_recs = filtered[:top_n]

        if not top_recs:
            st.warning("⚠️ ไม่พบหุ้นที่ผ่านเกณฑ์ — ลองลดคะแนนขั้นต่ำหรือเพิ่มหุ้นใน watchlist")
        else:
            st.success(f"✅ พบ {len(top_recs)} หุ้นที่ผ่านเกณฑ์ (คะแนน ≥ {min_score})")

            # ── แสดงผลแต่ละหุ้น ──
            for rec in top_recs:
                with st.container():
                    # Header row
                    h1, h2, h3, h4 = st.columns([2, 2, 2, 1])
                    with h1:
                        st.markdown(f"### {rec['ticker']}")
                        st.markdown(f"**{rec['signal']}**")
                    with h2:
                        st.metric(
                            "ราคาปัจจุบัน",
                            f"${rec['last_price']:.2f}",
                            f"ATR: {rec['atr']:.2f}",
                        )
                    with h3:
                        st.markdown(f"**คะแนน: {rec['score']:.0f}/100**")
                        st.markdown(score_bar(rec["score"]))
                    with h4:
                        st.markdown(f"📰 {rec['news_sentiment']}")

                    # Detail columns
                    d1, d2, d3 = st.columns(3)

                    with d1:
                        st.markdown("**💰 Entry / Target / SL**")
                        st.markdown(f"""
                        | | ราคา |
                        |---|---|
                        | 🟢 Entry (Low) | `{rec['entry_range'][0]:.2f}` |
                        | 🟢 Entry (High) | `{rec['entry_range'][1]:.2f}` |
                        | 🎯 Target 1 | `{rec['target_1']:.2f}` |
                        | 🎯 Target 2 | `{rec['target_2']:.2f}` |
                        | 🛑 Stop-Loss | `{rec['stop_loss']:.2f}` ({rec['sl_pct']:.1f}%) |
                        | ⚖️ R:R | `1:{rec['rr_ratio']:.1f}` |
                        """)

                    with d2:
                        st.markdown("**📊 Indicators**")
                        st.markdown(f"""
                        | Indicator | ค่า |
                        |---|---|
                        | RSI (14) | {rec['rsi']:.1f} |
                        | EMA 10 | {rec['ema_10']:.2f} |
                        | EMA 20 | {rec['ema_20']:.2f} |
                        | EMA 50 | {rec['ema_50']:.2f} |
                        | BB Upper | {rec['bb_upper']:.2f} |
                        | BB Lower | {rec['bb_lower']:.2f} |
                        | Volume Ratio | {rec['volume_ratio']:.1f}x |
                        """)

                    with d3:
                        st.markdown("**📋 เหตุผล / Reasons**")
                        for reason in rec["reasons"]:
                            st.markdown(f"- {reason}")

                    # กราฟราคา
                    with st.expander(f"📈 กราฟ {rec['ticker']} — ดูเพิ่มเติม"):
                        df_chart = rec["df"].copy()

                        fig = go.Figure()

                        # Candlestick
                        fig.add_trace(go.Candlestick(
                            x=df_chart.index,
                            open=df_chart["Open"],
                            high=df_chart["High"],
                            low=df_chart["Low"],
                            close=df_chart["Close"],
                            name="Price",
                            increasing_line_color="#2eb85c",
                            decreasing_line_color="#ff4444",
                        ))

                        # EMA lines
                        fig.add_trace(go.Scatter(
                            x=df_chart.index, y=calc_ema(df_chart["Close"], 10),
                            name="EMA 10", line=dict(color="#ffa500", width=1),
                        ))
                        fig.add_trace(go.Scatter(
                            x=df_chart.index, y=calc_ema(df_chart["Close"], 20),
                            name="EMA 20", line=dict(color="#00bfff", width=1),
                        ))
                        fig.add_trace(go.Scatter(
                            x=df_chart.index, y=calc_ema(df_chart["Close"], 50),
                            name="EMA 50", line=dict(color="#ff69b4", width=1),
                        ))

                        # Bollinger Bands
                        bb_u, bb_m, bb_l = calc_bollinger_bands(df_chart["Close"])
                        fig.add_trace(go.Scatter(
                            x=df_chart.index, y=bb_u,
                            name="BB Upper", line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"),
                        ))
                        fig.add_trace(go.Scatter(
                            x=df_chart.index, y=bb_l,
                            name="BB Lower", line=dict(color="rgba(255,255,255,0.3)", width=1, dash="dot"),
                            fill="tonexty", fillcolor="rgba(255,255,255,0.03)",
                        ))

                        # Entry / SL lines
                        fig.add_hline(y=rec["entry_range"][0], line_dash="dash",
                                     line_color="#2eb85c", annotation_text="Entry Low")
                        fig.add_hline(y=rec["stop_loss"], line_dash="dash",
                                     line_color="#ff4444", annotation_text="Stop-Loss")
                        fig.add_hline(y=rec["target_2"], line_dash="dash",
                                     line_color="#ffa500", annotation_text="Target 2")

                        fig.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="#0e1117",
                            plot_bgcolor="#1a1f2e",
                            margin=dict(l=0, r=0, t=20, b=0),
                            height=450,
                            xaxis=dict(gridcolor="#2a3040", rangeslider=dict(visible=False)),
                            yaxis=dict(gridcolor="#2a3040"),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # RSI chart
                        rsi_series = calc_rsi(df_chart["Close"])
                        fig_rsi = go.Figure()
                        fig_rsi.add_trace(go.Scatter(
                            x=df_chart.index, y=rsi_series,
                            name="RSI", line=dict(color="#ffa500", width=2),
                        ))
                        fig_rsi.add_hline(y=70, line_dash="dash", line_color="#ff4444")
                        fig_rsi.add_hline(y=30, line_dash="dash", line_color="#2eb85c")
                        fig_rsi.add_hrect(y0=70, y1=100, fillcolor="rgba(255,68,68,0.1)", line_width=0)
                        fig_rsi.add_hrect(y0=0, y1=30, fillcolor="rgba(46,184,92,0.1)", line_width=0)
                        fig_rsi.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="#0e1117",
                            plot_bgcolor="#1a1f2e",
                            margin=dict(l=0, r=0, t=10, b=0),
                            height=150,
                            xaxis=dict(gridcolor="#2a3040"),
                            yaxis=dict(range=[0, 100], gridcolor="#2a3040"),
                        )
                        st.plotly_chart(fig_rsi, use_container_width=True)

                    # News
                    if include_news and rec.get("news_latest"):
                        with st.expander(f"📰 ข่าว {rec['ticker']} ล่าสุด"):
                            for item in rec["news_latest"][:3]:
                                st.markdown(
                                    f"<div class='news-card'>"
                                    f"<small>{item.get('published', '')} | {item.get('source', '')}</small>"
                                    f"<br><b>{item.get('title', '')}</b>"
                                    f"</div>",
                                    unsafe_allow_html=True,
                                )

                    st.divider()


# ══════════════════════════════════════════════════════════════════════════
# MODULE 3: WEEKLY TRADING PLAN (ฟีเจอร์ใหม่!)
# ══════════════════════════════════════════════════════════════════════════
elif menu == t("weekly"):
    st.title(t("weekly"))
    st.markdown("### 📆 แผนเทรดรายสัปดาห์ — กระจาย Entry ทุกวัน")
    st.markdown(
        f"📅 {get_thai_date()} | "
        f"📊 วันเทรดที่เหลือ: **{get_trading_days_until_friday()} วัน**"
    )

    st.divider()

    # เลือกตลาด
    market_choice = st.radio(
        "เลือกตลาด",
        ["🇹🇭 หุ้นไทย (SET)", "🇺🇸 หุ้น US", "🌍 ผสม (TH + US)"],
        horizontal=True,
    )

    if "ไทย" in market_choice:
        wl = TH_POPULAR_STOCKS
    elif "US" in market_choice:
        wl = US_POPULAR_STOCKS
    else:
        wl = {**dict(list(TH_POPULAR_STOCKS.items())[:10]),
              **dict(list(US_POPULAR_STOCKS.items())[:10])}

    if st.button("📋 สร้างแผนเทรดรายสัปดาห์", type="primary"):
        with st.spinner("🧠 กำลังวิเคราะห์ทุกตัว..."):
            recs = generate_daily_recommendations(wl, top_n=10, min_score=10)

        if recs:
            # สร้างแผนรายวัน
            weekly_df = generate_weekly_plan(recs)
            st.dataframe(weekly_df, use_container_width=True, hide_index=True)

            st.divider()

            # แสดงรายละเอียดแต่ละวัน
            days_th = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]
            now = datetime.now(TH_TZ)
            today_idx = now.weekday()

            st.subheader("📌 แผนวันนี้ / Today's Plan")
            today_name = days_th[today_idx] if today_idx < 5 else None

            if today_name:
                today_plan = weekly_df[weekly_df["วัน"] == today_name]
                if not today_plan.empty:
                    for _, row in today_plan.iterrows():
                        with st.container():
                            c1, c2, c3 = st.columns([2, 3, 3])
                            with c1:
                                st.markdown(f"### {row['Ticker']}")
                                st.markdown(f"**{row['สัญญาณ']}**")
                            with c2:
                                st.markdown(f"""
                                - 🟢 Entry: **{row['Entry (Low)']} - {row['Entry (High)']}**
                                - 🎯 Target: **{row['Target 1']}** / {row['Target 2']}
                                - 🛑 SL: **{row['Stop-Loss']}**
                                """)
                            with c3:
                                st.markdown(f"""
                                - ⚖️ R:R: **{row['R:R']}**
                                - 📊 คะแนน: **{row['คะแนน']}**
                                """)
                            st.divider()
                else:
                    st.info(f"ไม่มีสัญญาณสำหรับวัน{today_name}")
            else:
                st.info("วันนี้วันหยุด — ไม่มีการเทรด")

            # สรุปความเสี่ยง
            st.divider()
            st.subheader("⚠️ สรุปความเสี่ยง / Risk Summary")
            n_buy = sum(1 for r in recs if "BUY" in r["signal"])
            n_sell = sum(1 for r in recs if "SELL" in r["signal"])
            avg_rr = np.mean([r["rr_ratio"] for r in recs])
            avg_sl = np.mean([r["sl_pct"] for r in recs])

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("🟢 Buy Signals", f"{n_buy}")
            r2.metric("🔴 Sell Signals", f"{n_sell}")
            r3.metric("⚖️ Avg R:R", f"1:{avg_rr:.1f}")
            r4.metric("🛑 Avg Stop-Loss", f"{avg_sl:.1f}%")

            st.warning(
                "⚠️ **คำเตือน:** สัญญาณเหล่านี้เป็นการวิเคราะห์เทคนิคอลเบื้องต้น "
                "ไม่ใช่คำแนะนำการลงทุน — ศึกษาข้อมูลเพิ่มเติมก่อนตัดสินใจทุกครั้ง"
            )
        else:
            st.warning("ไม่พบสัญญาณที่ผ่านเกณฑ์ — ลองขยาย watchlist หรือลดคะแนนขั้นต่ำ")


# ══════════════════════════════════════════════════════════════════════════
# MODULE 4: TECHNICAL SCREENER
# ══════════════════════════════════════════════════════════════════════════
elif menu == t("screener"):
    st.title(t("screener"))

    with st.expander("⚙️ ตั้งค่าตัวกรอง", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            sc_market = st.selectbox("ตลาด", ["หุ้นไทย (TH)", "หุ้น US", "ทั้งหมด"])
        with col2:
            rsi_range = st.slider("RSI (14)", 0, 100, (20, 70))
        with col3:
            sc_ma = st.selectbox("MA Signal", [
                "ทั้งหมด", "Golden Cross", "Dead Cross", "EMA10 > EMA20",
            ])
        with col4:
            min_vol = st.select_slider("Volume", ["ทั้งหมด", "> 1.3x", "> 2.0x"])

    if sc_market == "หุ้นไทย (TH)":
        wl = TH_POPULAR_STOCKS
    elif sc_market == "หุ้น US":
        wl = US_POPULAR_STOCKS
    else:
        wl = {**TH_POPULAR_STOCKS, **US_POPULAR_STOCKS}

    if st.button("🔍 สแกนหุ้น", type="primary"):
        results = []
        progress = st.progress(0)

        for i, (name, ticker) in enumerate(wl.items()):
            progress.progress(int((i + 1) / len(wl) * 100))
            df = fetch_stock_data(ticker, period="3mo")
            if df is None or len(df) < 30:
                continue

            sig = generate_signal(df)

            # Filter RSI
            if not (rsi_range[0] <= sig["rsi"] <= rsi_range[1]):
                continue

            # Filter Volume
            if min_vol == "> 1.3x" and sig["volume_ratio"] < 1.3:
                continue
            if min_vol == "> 2.0x" and sig["volume_ratio"] < 2.0:
                continue

            results.append({
                "Ticker": name,
                "Price": f"{sig['last_price']:.2f}",
                "Signal": sig["signal"],
                "Score": f"{sig['score']:.0f}",
                "RSI": f"{sig['rsi']:.1f}",
                "Vol": f"{sig['volume_ratio']:.1f}x",
                "Entry": f"{sig['entry_range'][0]:.2f}-{sig['entry_range'][1]:.2f}",
                "Target": f"{sig['target_2']:.2f}",
                "SL": f"{sig['stop_loss']:.2f}",
                "R:R": f"1:{sig['rr_ratio']:.1f}",
            })

        progress.empty()

        if results:
            results.sort(key=lambda x: float(x["Score"]), reverse=True)
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        else:
            st.info("ไม่พบหุ้นที่ตรงเงื่อนไข")


# ══════════════════════════════════════════════════════════════════════════
# MODULE 5: BACKTESTING
# ══════════════════════════════════════════════════════════════════════════
elif menu == t("backtest"):
    st.title(t("backtest"))

    bt_col1, bt_col2, bt_col3 = st.columns(3)
    with bt_col1:
        bt_ticker = st.selectbox(
            "เลือกหุ้น",
            list({**US_POPULAR_STOCKS, **TH_POPULAR_STOCKS}.keys()),
        )
    with bt_col2:
        bt_capital = st.number_input("เงินต้น (USD/THB)", value=10000, step=5000)
    with bt_col3:
        bt_period = st.selectbox("ช่วงทดสอบ", ["3mo", "6mo", "1y", "2y"], index=1)

    if st.button("🚀 รัน Backtest", type="primary"):
        # หา ticker
        all_tickers = {**US_POPULAR_STOCKS, **TH_POPULAR_STOCKS}
        yf_ticker = all_tickers.get(bt_ticker, bt_ticker)

        with st.spinner(f"กำลังดึงข้อมูล {bt_ticker}..."):
            df = fetch_stock_data(yf_ticker, period=bt_period)

        if df is not None and len(df) > 50:
            close = df["Close"]
            initial = bt_capital
            shares = initial / close.iloc[0]
            equity = shares * close
            total_ret = (equity.iloc[-1] / initial - 1) * 100

            # Buy & Hold benchmark
            benchmark_ret = total_ret  # same for buy & hold

            # RSI Strategy
            rsi = calc_rsi(close)
            position = False
            cash = initial
            qty = 0
            trades = []
            for i in range(2, len(close)):
                if rsi.iloc[i] < 30 and not position and cash > 0:
                    qty = cash * 0.95 / close.iloc[i]
                    cash = 0
                    position = True
                    trades.append(("BUY", close.iloc[i], df.index[i]))
                elif rsi.iloc[i] > 70 and position:
                    cash = qty * close.iloc[i] * 0.998
                    qty = 0
                    position = False
                    trades.append(("SELL", close.iloc[i], df.index[i]))

            final_rsi = cash + (qty * close.iloc[-1] if position else 0)
            rsi_ret = (final_rsi / initial - 1) * 100

            # Metrics
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Buy & Hold", f"${equity.iloc[-1]:,.2f}", fmt_pct(total_ret))
            m2.metric("RSI Strategy", f"${final_rsi:,.2f}", fmt_pct(rsi_ret))
            m3.metric("จำนวนเทรด", f"{len(trades)}")
            m4.metric("ส่วนต่าง", fmt_pct(rsi_ret - total_ret))

            # Equity curve
            chart_data = pd.DataFrame({
                "Date": df.index,
                "Buy & Hold": equity.values,
                "RSI Strategy": [
                    # Simplified equity curve for RSI
                    initial * (1 + rsi_ret/100 * i/len(close))
                    for i in range(len(close))
                ],
            })
            st.line_chart(chart_data.set_index("Date"), use_container_width=True)

            # Trade log
            if trades:
                with st.expander("📋 ประวัติการเทรด"):
                    trades_df = pd.DataFrame(trades, columns=["Type", "Price", "Date"])
                    st.dataframe(trades_df, hide_index=True, use_container_width=True)
        else:
            st.error("ไม่สามารถดึงข้อมูลได้")


# ══════════════════════════════════════════════════════════════════════════
# MODULE 6: PORTFOLIO SIMULATOR
# ══════════════════════════════════════════════════════════════════════════
elif menu == t("simulator"):
    st.title(t("simulator"))

    s1, s2 = st.columns([1, 2])
    with s1:
        st.markdown("#### 📝 สั่งซื้อ")
        sim_ticker = st.text_input("Ticker", value="NVDA", key="sim_t")
        sim_price  = st.number_input("ราคา", value=202.0, key="sim_p")
        sim_qty    = st.number_input("จำนวน", value=10, min_value=1, key="sim_q")
        sim_fee    = st.number_input("ค่าธรรมเนียม", value=5.0, key="sim_f")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("🟢 ซื้อ (Buy)", type="primary", use_container_width=True):
                st.session_state.portfolio_sim.append({
                    "Type": "BUY", "Ticker": sim_ticker.upper(),
                    "Price": sim_price, "Qty": sim_qty,
                    "Fee": sim_fee, "Total": sim_price * sim_qty + sim_fee,
                    "Time": datetime.now(TH_TZ).strftime("%H:%M:%S"),
                })
                st.rerun()
        with b2:
            if st.button("🔴 ขาย (Sell)", use_container_width=True):
                st.session_state.portfolio_sim.append({
                    "Type": "SELL", "Ticker": sim_ticker.upper(),
                    "Price": sim_price, "Qty": sim_qty,
                    "Fee": sim_fee, "Total": sim_price * sim_qty - sim_fee,
                    "Time": datetime.now(TH_TZ).strftime("%H:%M:%S"),
                })
                st.rerun()

        if st.button("🗑️ ล้างพอร์ต", use_container_width=True):
            st.session_state.portfolio_sim.clear()
            st.rerun()

    with s2:
        if st.session_state.portfolio_sim:
            hist = pd.DataFrame(st.session_state.portfolio_sim)
            st.dataframe(hist, hide_index=True, use_container_width=True)

            buys  = hist[hist["Type"] == "BUY"]["Total"].sum()
            sells = hist[hist["Type"] == "SELL"]["Total"].sum()
            fees  = hist["Fee"].sum()
            pnl   = sells - buys

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ลงทุน", f"${buys:,.2f}")
            c2.metric("ขายได้", f"${sells:,.2f}")
            c3.metric("ค่าธรรมเนียม", f"${fees:,.2f}")
            c4.metric("P&L", f"${pnl:,.2f}", fmt_pct(pnl/buys*100 if buys else 0))
        else:
            st.info("💡 เริ่มจำลองซื้อขายได้เลย!")


# ══════════════════════════════════════════════════════════════════════════
# MODULE 7: NEWS & SENTIMENT
# ══════════════════════════════════════════════════════════════════════════
elif menu == t("news"):
    st.title(t("news"))

    news_tab1, news_tab2 = st.tabs(["🌍 ข่าวทั่วโลก", "📌 ข่าวหุ้นเฉพาะตัว"])

    with news_tab1:
        with st.spinner("กำลังดึงข่าว..."):
            news = fetch_finance_news(max_items=15)

        if news:
            for item in news:
                st.markdown(
                    f"<div class='news-card'>"
                    f"<small>{item.get('published', '')} | "
                    f"<b>{item.get('source', '')}</b></small>"
                    f"<br><b>{item.get('title', '')}</b>"
                    f"<br><small>{item.get('summary', '')}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("ไม่สามารถดึงข่าวได้")

    with news_tab2:
        news_ticker = st.text_input("ใส่ Ticker", value="NVDA")
        if st.button("🔍 ดึงข่าว"):
            with st.spinner(f"ดึงข่าว {news_ticker.upper()}..."):
                stock_news = fetch_stock_news(news_ticker.upper())

            if stock_news:
                for item in stock_news:
                    st.markdown(
                        f"<div class='news-card'>"
                        f"<small>{item.get('published', '')} | "
                        f"<b>{item.get('source', '')}</b></small>"
                        f"<br><b>{item.get('title', '')}</b>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info(f"ไม่พบข่าวสำหรับ {news_ticker.upper()}")


# ══════════════════════════════════════════════════════════════════════════
# MODULE 8: SETTINGS
# ══════════════════════════════════════════════════════════════════════════
elif menu == t("settings"):
    st.title(t("settings"))

    st.subheader("📋 Watchlist ของฉัน")
    wl_text = st.text_area(
        "รายชื่อหุ้น (คั่นด้วย comma)",
        value=", ".join(st.session_state.custom_watchlist),
        height=100,
    )
    if st.button("💾 บันทึก Watchlist"):
        st.session_state.custom_watchlist = [
            t.strip().upper() for t in wl_text.split(",") if t.strip()
        ]
        st.success("✅ บันทึกแล้ว!")

    st.divider()

    st.subheader("🔔 ประวัติ Alert")
    if st.session_state.alerts:
        st.dataframe(pd.DataFrame(st.session_state.alerts), hide_index=True)
    else:
        st.info("ยังไม่มี Alert")

    st.divider()

    st.subheader("ℹ️ เกี่ยวกับแอป")
    st.markdown("""
    **🦅 Stock Hunter Super App v4.0**

    - 📊 ข้อมูลจริงจาก Yahoo Finance API
    - 🧠 Technical Analysis Engine (RSI, MACD, EMA, Bollinger, ATR, Pivot)
    - 📰 News Sentiment Analysis
    - 📅 แผนเทรดรายวัน/รายสัปดาห์
    - 🧪 Backtesting + Portfolio Simulator

    ⚠️ **ข้อมูลเพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน**

    Built with ❤️ by OWL
    """)


# ══════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════
st.divider()
st.markdown(
    "<div style='text-align:center; color:#555; font-size:0.75em;'>"
    "🦅 Stock Hunter Super App v4.0 | "
    "⚠️ ข้อมูลเพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน | "
    "Data: Yahoo Finance"
    "</div>",
    unsafe_allow_html=True,
)
