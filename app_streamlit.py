import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Stock Hunter Pro", layout="wide")
st.title("🦅 ระบบสแกนหุ้น อาหวัง Pro Max")

@st.cache_data
def get_data(ticker):
    return yf.Ticker(ticker).history(period="1y")

# 1. ตรวจสอบ Market Regime
spy = get_data("SPY")
market_bullish = spy.iloc[-1]['Close'] > spy['Close'].ewm(span=200).mean().iloc[-1]
st.info(f"สภาวะตลาดปัจจุบัน: {'ขาขึ้น (Bullish)' if market_bullish else 'ขาลง (Bearish)'}")

# 2. เพิ่มช่องให้คุณเลือกหุ้น
tickers = st.multiselect("เลือกหุ้นที่ต้องการสแกน:", ["NVDA", "PLTR", "AMD", "TSLA", "META", "AAPL"], default=["NVDA"])

# 3. แสดงตารางผลลัพธ์แบบง่าย
if tickers:
    data_list = []
    for t in tickers:
        df = get_data(t)
        last = df.iloc[-1]
        data_list.append({
            "Ticker": t,
            "Price": round(last['Close'], 2),
            "High_20": round(df['High'].rolling(20).max().iloc[-1], 2)
        })
    st.table(pd.DataFrame(data_list))
