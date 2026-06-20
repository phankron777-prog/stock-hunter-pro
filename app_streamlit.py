import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from pathlib import Path # แก้ Error NameError: Path

st.set_page_config(page_title="Stock Hunter Pro v20 Ultimate", layout="wide")

# ประกาศตัวแปร Journal แบบปลอดภัย
journal_file = Path("trade_journal.csv")

# ... (ส่วน load_data และ indicators เหมือนเดิม) ...
# เพิ่มการดัก Error ในส่วนการหา market_ok
def get_market_status():
    try:
        spy = yf.Ticker("SPY").history(period="3y")
        qqq = yf.Ticker("QQQ").history(period="3y")
        iwm = yf.Ticker("IWM").history(period="3y")
        
        checks = 0
        for x in [spy, qqq, iwm]:
            if not x.empty:
                ema200 = x["Close"].ewm(span=200, adjust=False).mean().iloc[-1]
                if x["Close"].iloc[-1] > ema200:
                    checks += 1
        return checks >= 2
    except:
        return False

# ส่วนแสดงผล
market_ok = get_market_status()
st.write(f"Market Filter: {'✅ RISK ON' if market_ok else '❌ RISK OFF'}")

# แก้ไขการบันทึก Journal
if not journal_file.exists():
    pd.DataFrame(columns=["Date","Ticker","Entry","Stop","Shares","Risk","Result","R"]).to_csv(journal_file, index=False)
