import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="อาหวัง Pro Max v16.3 - Portfolio Core", layout="wide")

# ==========================================================================
# 📊 1. PORTFOLIO HEAT & SESSION STATE JOURNAL
# ==========================================================================
if "trade_journal" not in st.session_state:
    st.session_state.trade_journal = [
        {"date": "2026-06-15", "ticker": "AMD", "pnl_r": -1.0},
        {"date": "2026-06-16", "ticker": "TSLA", "pnl_r": -1.0},
        {"date": "2026-06-17", "ticker": "AAPL", "pnl_r": 1.5},
    ]

def calculate_consecutive_losses(journal):
    if not journal: return 0
    count = 0
    for trade in reversed(journal):
        if trade["pnl_r"] < 0: count += 1
        else: break
    return count

current_consecutive_losses = calculate_consecutive_losses(st.session_state.trade_journal)

# แผงควบคุมบริหารความเสี่ยงระดับหัวกะทิ (Sidebar)
st.sidebar.markdown("## 🦅 อาหวัง Pro Max v16.3")
st.sidebar.markdown("### `Hedge Fund Risk Architecture`")
st.sidebar.divider()

st.sidebar.markdown("### 🛡️ Global Risk Settings")
account_capital = st.sidebar.number_input("เงินทุนรวมในพอร์ต (บาท THB):", value=100000, step=10000)
base_risk_pct = st.sidebar.slider("ความเสี่ยงพื้นฐานต่อไม้ (Base Risk %):", 0.25, 2.0, 1.0, 0.25)
max_portfolio_heat = st.sidebar.slider("เพดานความเสี่ยงรวมพอร์ต (Max Open Risk %):", 3.0, 10.0, 5.0, 0.5)
current_open_risk = st.sidebar.slider("ความเสี่ยงรวมของไม้ที่ถืออยู่ปัจจุบัน (%):", 0.0, 7.0, 2.0, 0.5)

st.sidebar.markdown("### 🛑 Automated Kill Switch")
st.sidebar.write(f"จำนวนไม้ที่แพ้ติดกันปัจจุบัน: **{current_consecutive_losses} ไม้**")

kill_switch = False
if current_consecutive_losses >= 4 or current_open_risk >= max_portfolio_heat:
    st.sidebar.error("🚨 ALERT: ระบบล็อกการซื้อขายถาวร (Heat เกิน หรือแพ้ติดกัน)")
    kill_switch = True

menu = st.sidebar.radio("🧭 โหมดการทำงาน:", ["⚡ 1. สแกนสดระดับ PM (Interactive)", "📊 2. Backtest วินัยเหล็ก (Fixed Risk)"])

# ==========================================================================
# 📦 2. QUANT MATHEMATICAL ENGINE (SAFE PIPELINE STANDARD)
# ==========================================================================
@st.cache_data(ttl=60)
def fetch_clean_data(ticker, period="3y"):
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df is None or df.empty: return None
        df.index = df.index.tz_localize(None) if df.index.tz else df.index
        return df
    except: return None

def compute_v16_indicators(df, spy_ret_90=0.0):
    if df is None or len(df) < 200: return None
    try:
        df = df.copy()
        
        # 1. คำนวณเส้นค่าเฉลี่ยแบ่งโซนแนวโน้ม (EMA Stage 2)
        df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # 2. คำนวณโมเมนตัม MACD & RSI
        df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA_12'] - df['EMA_26']
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9)) + 1e-9))
        
        # 3. คำนวณหาค่า ATR แบบปลอดภัยแบบเรียงลำดับ ป้องกัน KeyError
        df['Prev_Close'] = df['Close'].shift(1)
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Prev_Close']).abs()
        tr3 = (df['Low'] - df['Prev_Close']).abs()
        
        df['True_Range'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = df['True_Range'].ewm(span=14, adjust=False).mean()
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
        
        # 4. คำนวณหาค่า Relative Strength เพื่อส่งข้อมูลไปจัดลำดับ
        stock_ret_90 = (df['Close'].iloc[-1] - df['Close'].iloc[-90]) / (df['Close'].iloc[-90] + 1e-9)
        df['Absolute_RS'] = stock_ret_90 - spy_ret_90
        
        return df
    except Exception as e:
        return None

def run_fixed_risk_backtest(df, initial_capital=100000, risk_pct=1.0):
    if df is None or len(df) < 200: return None
    try:
        capital = initial_capital
        in_pos, entry_p, sl_p, risk_amt, shares_to_buy = False, 0, 0, 0, 0
        trades = []
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            
            # การตรวจเช็คอินดิเคเตอร์ของวันก่อนหน้าผ่าน Pipeline ใหม่
            trend_aligned = (prev['Close'] > prev['EMA_20']) and (prev['EMA_20'] > prev['EMA_50']) and (prev['EMA_50'] > prev['EMA_200'])
            setup_ok = trend_aligned and (prev['MACD'] > prev['Signal_Line']) and (50 <= prev['RSI'] <= 75)
            
            if not in_pos and setup_ok:
                in_pos = True
                entry_p = row['Open']
                sl_distance = prev['ATR'] * 2.0
                sl_p = entry_p - sl_distance
                risk_amt = capital * (risk_pct / 100)
                shares_to_buy = risk_amt / (sl_distance + 1e-9)
                continue
                
            if in_pos:
                # ระบบ Trailing Stop อิงตาม ATR
                trail_sl = row['High'] - (row['ATR'] * 2.0)
                if trail_sl > sl_p: sl_p = trail_sl
                
                if row['Low'] <= sl_p:
                    in_pos = False
                    exit_p = min(row['Open'], sl_p)
                    trade_pnl = (exit_p - entry_p) * shares_to_buy
                    capital += trade_pnl
                    trades.append({"pnl": trade_pnl, "capital": capital})
                    
        if not trades: return None
        df_tr = pd.DataFrame(trades)
        win_rate = (len(df_tr[df_tr['pnl'] > 0]) / len(df_tr)) * 100
        max_dd = ((df_tr['capital'].cummax() - df_tr['capital']) / df_tr['capital'].cummax()).max() * 100
        return {"win_rate": win_rate, "max_dd": max_dd, "final_bal": capital, "total_trades": len(df_tr)}
    except Exception as e:
        return None

# ==========================================================================
# 🎯 3. MAIN INTERFACE CONTROLLER
# ==========================================================================
spy = fetch_clean_data("SPY", "1y")
spy_ret_90 = (spy['Close'].iloc[-1] - spy['Close'].iloc[-90]) / spy['Close'].iloc[-90] if spy is not None else 0.0

if menu == "⚡ 1. สแกนสดระดับ PM (Interactive)":
    st.title("⚡ แผงควบคุมจัดลำดับผู้นำตลาด (อาหวัง Pro Max v16.3)")
    
    # 🎛️ PM Interactive Dynamic Control Panel
    st.markdown("### 🎛️ PM Interactive Dynamic Control")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
    
    with c1:
        selected_tickers = st.multiselect(
            "เลือกรายชื่อหุ้นเข้าตะกร้าสแกน (เพิ่ม/ลด ได้อิสระ):",
            ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "COIN", "ASTS"],
            default=["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL"]
        )
    with c2:
        min_score_cutoff = st.slider("คะแนน Quant ขั้นต่ำที่ยอมรับได้:", 0, 100, 50, step=5)
    with c3:
        enforce_stage2 = st.toggle("ต้องผ่าน Stage 2 เท่านั้น (EMA20>50>200)", value=True)
    with c4:
        rsi_range = st.slider("ระบุช่วง RSI วินัยหน้างาน:", 0, 100, (45, 80))

    st.divider()

    results = []
    
    if selected_tickers:
        for t in selected_tickers:
            raw = fetch_clean_data(t, "1y")
            df_p = compute_v16_indicators(raw, spy_ret_90)
            
            if df_p is not None and not df_p.empty:
                last = df_p.iloc[-1]
                
                # คิดเกณฑ์คะแนนตามสมการโมเดลคณิตศาสตร์
                score = 0
                is_stage_2 = (last['Close'] > last['EMA_20'] > last['EMA_50'] > last['EMA_200'])
                if is_stage_2: score += 40
                if last['MACD'] > last['Signal_Line']: score += 20
                if 50 <= last['RSI'] <= 75: score += 20
                
                # คะแนนความแกร่งสัมพัทธ์ (RS Score)
                rs_bonus = min(max(last['Absolute_RS'] * 100, 0), 20)
                score += rs_bonus
                
                # เช็คเงื่อนไขฟิลเตอร์จากหน้าเว็บที่ PM เลือกปรับเอง
                pass_score = (score >= min_score_cutoff)
                pass_trend = True if not enforce_stage2 else is_stage_2
                pass_rsi = (rsi_range[0] <= last['RSI'] <= rsi_range[1])
                
                if kill_switch:
                    signal = "🛑 LOCK SYSTEM"
                elif pass_score and pass_trend and pass_rsi:
                    signal = "🟢 BUY / LONG"
                else:
                    signal = "⬜ NO TRADE"
                    
                dynamic_risk = base_risk_pct * 1.5 if score >= 80 else (base_risk_pct if score >= 60 else base_risk_pct * 0.5)
                
                results.append({
                    "Ticker": t,
                    "คะแนน Quant": round(score, 1),
                    "RS Bonus": round(rs_bonus, 1),
                    "ราคาสด": f"${last['Close']:.2f}",
                    "RSI": round(last['RSI'], 1),
                    "สัญญาณตามเกณฑ์ PM": signal,
                    "เสี่ยงต่อไม้": f"{dynamic_risk}%",
                    "ATR Trailing Stop": f"${last['Close'] - (last['ATR'] * 2.0):.2f}"
                })
                
        if results:
            rank_df = pd.DataFrame(results).sort_values(by="คะแนน Quant", ascending=False)
            st.subheader("🏆 ผลลัพธ์การจัดอันดับและการคุมวินัยพอร์ตโฟลิโอ")
            st.dataframe(rank_df, use_container_width=True, hide_index=True)
        else:
            st.info("💡 ไม่มีหุ้นตัวไหนผ่านเกณฑ์ที่คุณปรับฟิลเตอร์ไว้ ลองขยายกรอบเงื่อนไขด้านบน")
    else:
        st.warning("⚠️ กรุณาเลือกหุ้นในช่องตระกร้าสแกนอย่างน้อย 1 ตัว")

elif menu == "📊 2. Backtest วินัยเหล็ก (Fixed Risk)":
    st.title("📊 ระบบทดสอบกลยุทธ์จำลองพอร์ตเสมือนจริง (Fixed Risk Engine)")
    tk = st.text_input("ระบุชื่อหุ้นเทสย้อนหลัง 3 ปี:", "NVDA").upper().strip()
    
    if tk:
        data = fetch_clean_data(tk, "3y")
        proc = compute_v16_indicators(data, spy_ret_90)
        stats = run_fixed_risk_backtest(proc, initial_capital=account_capital, risk_pct=base_risk_pct)
        
        if stats:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Win Rate จริง", f"{stats['win_rate']:.1f}%")
            m2.metric("Max Drawdown จริง", f"{stats['max_dd']:.1f}%")
            m3.metric("จำนวนไม้เทรดทั้งหมด", f"{stats['total_trades']} ไม้")
            m4.metric("เงินพอร์ตปลายทาง", f"{stats['final_bal']:,.2f} บาท")
        else:
            st.info("ไม่พบจังหวะเทรดตามระบบวินัยเหล็กในช่วง 3 ปีนี้ หรือข้อมูลระบบขัดข้อง")
