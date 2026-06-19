# --- 1. แก้ Look-Ahead Bias (เปลี่ยนจากการใช้ iloc[-1] มาเป็น Rolling calculation) ---
def compute_indicators_and_signals_v18(df, spy_ret_90_series):
    df = df.copy()
    # ใช้ Rolling Return จริงๆ ณ วันนั้นๆ เทียบกับ SPY
    df['Stock_Ret_90'] = df['Close'] / df['Close'].shift(90) - 1
    df['Absolute_RS'] = df['Stock_Ret_90'] - spy_ret_90_series
    
    # 2. แก้เรื่อง Percentile แทนแต้มตันที่ 20 เพื่อให้เห็นความต่างของหุ้น
    df['RS_Score'] = df['Absolute_RS'].rolling(252).rank(pct=True) * 20
    
    # ... (คำนวณ EMA, MACD, RSI ตามเดิม) ...
    return df

# --- 2. แก้เรื่อง Position Sizing ที่แม่นยำ 100% ---
# ใช้สูตร: Shares = (Risk_Amount) / (Entry_Price - SL_Price)
# Risk_Amount = Capital * Risk_Pct
# ปรับแก้ในส่วนของสแกนสด:
def get_safe_position(capital, entry, sl, risk_pct):
    risk_money = capital * (risk_pct / 100)
    price_diff = abs(entry - sl)
    if price_diff == 0: return 0
    shares = risk_money / price_diff
    return shares

# --- 3. Portfolio Heat ที่คุมได้จริง (รวมเข้าใน Scan loop) ---
def check_heat(active_trades, account_capital):
    current_risk = sum([pos['risk_amount'] for pos in active_trades.values()])
    return (current_risk / account_capital) * 100
