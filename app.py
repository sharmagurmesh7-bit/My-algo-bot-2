# app.py - TOPU TOWER V4 - FINAL - LINE DELETED
import streamlit as st
import pandas as pd
import os
import upstox_client
from upstox_client.api import HistoryApi, MarketQuoteApi
from datetime import datetime, timedelta

st.set_page_config(page_title="TOPU TOWER V4 LIVE", layout="wide", page_icon="🚀")

TOKEN = os.environ.get("UPSTOX_TOKEN")
if not TOKEN:
    st.error("UPSTOX_TOKEN Render Environment me nahi hai!")
    st.stop()

configuration = upstox_client.Configuration()
configuration.access_token = TOKEN
api_client = upstox_client.ApiClient(configuration)
history_api = HistoryApi(api_client)
market_api = MarketQuoteApi(api_client)

INSTRUMENT_MAP = {
    "SENSEX": "BSE_INDEX|SENSEX",
    "NIFTY": "NSE_INDEX|Nifty 50",
}

CONFIG = {
    "SYMBOL": "SENSEX",
    "EMA_FAST": 9,
    "EMA_SLOW": 21,
    "CHANNEL_PERIOD": 20,
    "INITIAL_SL_POINTS": 100
}

def get_live_candles(symbol_key):
    try:
        instrument = INSTRUMENT_MAP.get(symbol_key)
        to_d = datetime.now().date().isoformat()
        from_d = (datetime.now() - timedelta(days=5)).date().isoformat()
        response = history_api.get_historical_candle_data1(
            instrument_key=instrument,
            interval="1minute",
            to_date=to_d,
            from_date=from_d,
            api_version="2.0"
        )
        candles = response.data.candles
        df = pd.DataFrame(candles, columns=['timestamp','open','high','low','close','volume','oi'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        return df
    except Exception as e:
        st.error(f"Candle Error: {e}")
        return pd.DataFrame()

def get_live_ltp(symbol_key):
    try:
        instrument = INSTRUMENT_MAP.get(symbol_key)
        response = market_api.ltp(symbol=instrument, api_version="2.0")
        return float(response.data[instrument].last_price)
    except:
        return 0.0

st.title(f"🚀 {CONFIG['SYMBOL']} TOPU TOWER V4 - LIVE")

if st.button("🔄 LIVE REFRESH"):
    st.cache_data.clear()

@st.cache_data(ttl=20)
def load_live_data(symbol):
    df = get_live_candles(symbol)
    ltp = get_live_ltp(symbol)
    if ltp == 0 and not df.empty:
        ltp = df['close'].iloc[-1]
    return df, ltp

df, live_ltp = load_live_data(CONFIG['SYMBOL'])

if df.empty:
    st.error("Live data nahi aa raha - Market band hai ya Token expire hai.")
    st.stop()

df['ema_fast'] = df['close'].ewm(span=CONFIG["EMA_FAST"]).mean()
df['ema_slow'] = df['close'].ewm(span=CONFIG["EMA_SLOW"]).mean()
df['upper'] = df['high'].rolling(CONFIG["CHANNEL_PERIOD"]).max()
df['lower'] = df['low'].rolling(CONFIG["CHANNEL_PERIOD"]).min()

day_open = df['open'].iloc[0]
ema_trend = "BULLISH" if df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1] else "BEARISH"
open_trend = "BULLISH" if live_ltp > day_open else "BEARISH"

if ema_trend == "BULLISH" and open_trend == "BULLISH":
    final = "FINAL BULLISH ✅"
else:
    final = "FINAL BEARISH ❌" if ema_trend == "BEARISH" and open_trend == "BEARISH" else "SIDEWAYS ⚠️"

c1, c2, c3, c4 = st.columns(4)
c1.metric("LIVE LTP", f"{live_ltp:.1f}", f"{live_ltp-day_open:+.1f}")
c2.metric("DAY OPEN", f"{day_open:.1f}")
c3.metric("EMA", ema_trend)
c4.metric("CHANNEL", f"{df['lower'].iloc[-1]:.0f} - {df['upper'].iloc[-1]:.0f}")

if "BULLISH" in final:
    st.success(f"🟢 {final} - CALL BUY | SL: {live_ltp-CONFIG['INITIAL_SL_POINTS']:.0f}")
    st.balloons()
else:
    st.error(f"🔴 {final} - PUT BUY / WAIT")

st.line_chart(df.set_index('timestamp')['close'].tail(200))
