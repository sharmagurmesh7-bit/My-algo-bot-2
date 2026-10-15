# app.py - TOPU TOWER FINAL - FULL COMBO - LIVE + ALERT + EXECUTION + TRAILING
import streamlit as st
import pandas as pd
import os
import upstox_client
from upstox_client.api import HistoryApi, MarketQuoteApi, OrderApi
from upstox_client.models import PlaceOrderRequest
from datetime import datetime, timedelta

st.set_page_config(page_title="TOPU TOWER FINAL", layout="wide", page_icon="🚀")

TOKEN = os.environ.get("UPSTOX_TOKEN")
if not TOKEN:
    st.error("UPSTOX_TOKEN Render me nahi hai!")
    st.stop()

configuration = upstox_client.Configuration()
configuration.access_token = TOKEN
api_client = upstox_client.ApiClient(configuration)
history_api = HistoryApi(api_client)
market_api = MarketQuoteApi(api_client)
order_api = OrderApi(api_client)

INSTRUMENT_MAP = {
    "SENSEX": "BSE_INDEX|SENSEX",
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
}

OPTION_MAP = {
    "SENSEX_CALL": "BSE_FO|SENSEX24OCT72700CE",
    "SENSEX_PUT": "BSE_FO|SENSEX24OCT72700PE",
}

def get_live_candles(symbol_key):
    try:
        instrument = INSTRUMENT_MAP.get(symbol_key)
        to_d = datetime.now().date().isoformat()
        from_d = (datetime.now() - timedelta(days=5)).date().isoformat()
        response = history_api.get_historical_candle_data1(
            instrument_key=instrument, interval="1minute",
            to_date=to_d, from_date=from_d, api_version="2.0"
        )
        df = pd.DataFrame(response.data.candles, columns=['timestamp','open','high','low','close','volume','oi'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        return df
    except Exception as e:
        return pd.DataFrame()

def get_live_ltp(symbol_key):
    try:
        instrument = INSTRUMENT_MAP.get(symbol_key)
        response = market_api.ltp(symbol=instrument, api_version="2.0")
        return float(response.data[instrument].last_price)
    except:
        return 0.0

def place_order(instrument_key, qty, side):
    try:
        req = PlaceOrderRequest(
            quantity=qty, product="D", validity="DAY", price=0, tag="TOPU_TOWER",
            instrument_token=instrument_key, order_type="MARKET",
            transaction_type=side, disclosed_quantity=0, trigger_price=0, is_amo=False
        )
        response = order_api.place_order(req, api_version="2.0")
        return True, str(response)
    except Exception as e:
        return False, str(e)

# --- SESSION STATE ---
if 'confirm' not in st.session_state:
    st.session_state.confirm = False
if 'trailing_active' not in st.session_state:
    st.session_state.trailing_active = False
    st.session_state.entry_price = 0
    st.session_state.highest_profit = 0
    st.session_state.current_sl = 0

# --- UI ---
st.title("🚀 TOPU TOWER - FINAL SUPER COMBO")

top1, top2, top3, top4 = st.columns(4)
SYMBOL = top1.selectbox("INDEX", ["SENSEX", "NIFTY", "BANKNIFTY"])
QTY = top2.number_input("LOT QTY", min_value=1, value=1)
SL_POINTS = top3.number_input("SL POINTS", value=100)
TRAILING_GAP = top4.number_input("TRAILING GAP", value=50)

if st.button("🔄 LIVE REFRESH"):
    st.cache_data.clear()

@st.cache_data(ttl=20)
def load_live_data(symbol):
    df = get_live_candles(symbol)
    ltp = get_live_ltp(symbol)
    if ltp == 0 and not df.empty:
        ltp = df['close'].iloc[-1]
    return df, ltp

df, live_ltp = load_live_data(SYMBOL)

if df.empty:
    st.error("Market band hai ya Token expire!")
    st.stop()

df['ema_fast'] = df['close'].ewm(span=9).mean()
df['ema_slow'] = df['close'].ewm(span=21).mean()
df['upper'] = df['high'].rolling(20).max()
df['lower'] = df['low'].rolling(20).min()

day_open = df['open'].iloc[0]
ema_trend = "BULLISH" if df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1] else "BEARISH"
open_trend = "BULLISH" if live_ltp > day_open else "BEARISH"

if ema_trend == "BULLISH" and open_trend == "BULLISH":
    final = "FINAL BULLISH ✅"
else:
    final = "FINAL BEARISH ❌"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(f"{SYMBOL} LTP", f"{live_ltp:.1f}", f"{live_ltp-day_open:+.1f}")
c2.metric("DAY OPEN", f"{day_open:.1f}")
c3.metric("EMA TREND", ema_trend)
c4.metric("OPEN TREND", open_trend)
c5.metric("CHANNEL", f"{df['lower'].iloc[-1]:.0f}-{df['upper'].iloc[-1]:.0f}")

# --- ALERT BOX ---
st.divider()
if "BULLISH" in final:
    st.success(f"🔔 ALERT: {SYMBOL} {final} - CALL READY | LTP {live_ltp:.0f}")
else:
    st.error(f"🔔 ALERT: {SYMBOL} {final} - PUT READY | LTP {live_ltp:.0f}")

# --- EXECUTION PANEL WITH YES/NO ---
st.subheader("⚔️ EXECUTION PANEL - YES/NO")
ec1, ec2 = st.columns(2)
with ec1:
    if st.button(f"🟢 BUY CALL {SYMBOL} - YES", use_container_width=True, type="primary"):
        st.session_state.confirm = "CALL"
with ec2:
    if st.button(f"🔴 BUY PUT {SYMBOL} - YES", use_container_width=True):
        st.session_state.confirm = "PUT"

if st.session_state.confirm:
    st.warning(f"⚠️ CONFIRM: {st.session_state.confirm} BUY? QTY: {QTY} | LTP: {live_ltp:.0f} | SL: {SL_POINTS}")
    yes_col, no_col = st.columns(2)
    with yes_col:
        if st.button("✅ YES, EXECUTE NOW", use_container_width=True, type="primary"):
            instrument_to_trade = OPTION_MAP.get("SENSEX_CALL") if st.session_state.confirm == "CALL" else OPTION_MAP.get("SENSEX_PUT")
            with st.spinner("Order ja raha hai..."):
                success, msg = place_order(instrument_to_trade, QTY, "BUY")
            if success:
                st.balloons()
                st.success(f"ORDER SUCCESS! {msg}")
                st.session_state.trailing_active = True
                st.session_state.entry_price = live_ltp
                st.session_state.current_sl = live_ltp - SL_POINTS
                st.session_state.highest_profit = live_ltp
            else:
                st.error(f"FAILED: {msg}")
            st.session_state.confirm = False
    with no_col:
        if st.button("❌ NO, CANCEL", use_container_width=True):
            st.session_state.confirm = False
            st.info("Cancelled!")

# --- TRAILING SL MANAGER ---
st.divider()
st.subheader("📈 TRAILING SL MANAGER")

ct1, ct2 = st.columns(2)
with ct1:
    if st.button("🔒 Activate Trailing", use_container_width=True):
        st.session_state.trailing_active = True
        st.session_state.entry_price = live_ltp
        st.session_state.current_sl = live_ltp - SL_POINTS
        st.session_state.highest_profit = live_ltp
        st.success(f"Trailing ON! Entry {live_ltp:.0f}")
with ct2:
    if st.button("❌ Stop Trailing", use_container_width=True):
        st.session_state.trailing_active = False
        st.info("Trailing OFF")

if st.session_state.trailing_active:
    if live_ltp > st.session_state.highest_profit:
        st.session_state.highest_profit = live_ltp

    new_sl = st.session_state.highest_profit - TRAILING_GAP
    if new_sl > st.session_state.current_sl:
        st.session_state.current_sl = new_sl

    profit = live_ltp - st.session_state.entry_price
    tm1, tm2, tm3, tm4 = st.columns(4)
    tm1.metric("Entry", f"{st.session_state.entry_price:.0f}")
    tm2.metric("Trailing SL", f"{st.session_state.current_sl:.0f}")
    tm3.metric("Highest", f"{st.session_state.highest_profit:.0f}")
    tm4.metric("PnL", f"{profit:.0f}", f"{profit:.0f}")

    if live_ltp <= st.session_state.current_sl:
        st.error(f"🚨 TRAILING SL HIT! Exit at {live_ltp:.0f}")
        st.session_state.trailing_active = False

# --- CHART ---
st.area_chart(df.tail(100).set_index('timestamp')['close'])
st.caption(f"SL: {live_ltp - SL_POINTS:.0f} | TGT: {live_ltp + (SL_POINTS*1.5):.0f} | LIVE: {SYMBOL}")
