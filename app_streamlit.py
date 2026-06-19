import streamlit as st
import pandas as pd
import yfinance as yf

# ส่วนนี้สำคัญมาก: ต้องดึง spy ก่อนเริ่มใช้งาน
@st.cache_data
def get_market_data():
    spy = yf.Ticker("SPY").history(period="3y")['Close']
    return spy

spy = get_market_data()

# ส่วนที่ทำให้ Error: ต้องเช็คว่า spy มีข้อมูลไหมก่อนใช้ .iloc
if spy is not None and not spy.empty:
    market_bullish = spy.iloc[-1] > spy.ewm(span=200, adjust=False).mean().iloc[-1]
    st.write(f"Market Status: {'Bullish' if market_bullish else 'Bearish'}")
else:
    st.error("Market data not available")
