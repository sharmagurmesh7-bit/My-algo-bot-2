import streamlit as st
import pandas as pd
import pandas_ta as ta
import os
from dotenv import load_dotenv
from config import CONFIG
import upstox_client
from upstox_client.rest import ApiException
from datetime import datetime, timedelta

load_dotenv()
st.set_page_config(page_title="TOPU TOWER V4 LIVE", layout="wide", page_icon="🚀")

# --- UPSTOX SETUP ---
TOKEN = os.getenv("UPSTOX_TOKEN")
if not TOKEN:
    st.error("⚠️.env me UPSTOX_TOKEN nahi hai! Token daal pehle.")
    st.stop()

configuration = upstox_client.Configuration()
configuration.access_token = TOKEN
api_client = upstox_client.ApiClient(configuration)
history_api = upstox_client.HistoryApi(api_client)
market_api = upstox_client.MarketQuoteApi(api_client)
option_api = upstox_client.OptionsApi(api_client)

# --- SYMBOL MAP - SENSEX, NIFTY sabke liye ---
INSTRUMENT_MAP = {
    "SENSEX": "BSE_INDEX|SENSEX",
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "RELIANCE": "NSE_EQ|INE002A01018",
}

def get_live_candles(symbol_key, interval="5minute"):
    """LIVE CANDLE - Upstox History API se"""
    try:
        instrument = INSTRUMENT_MAP.get(symbol_key, f"NSE_EQ|{symbol_key}")
        today = datetime.now()
        from_date = (today - timedelta(days=5)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")

        response = history_api.get_historical_candle_data1(
            instrument_key=instrument,
            interval=interval,
            to_date=to_date,
            from_date=from_date,
            api_version="2.0"
        )
        candles = response.data.candles
        df = pd.DataFrame(candles, columns=['timestamp','open','high','low','close','volume','oi'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        return df
    except ApiException as e:
        st.error(f"Upstox Candle Error: {e}")
        return pd.DataFrame()

def get_live_ltp(symbol_key):
    """LIVE SPOT PRICE"""
    try:
        instrument = INSTRUMENT_MAP.get(symbol_key, f"NSE_EQ|{symbol_key}")
        response = market_api.ltp(instrument_key=instrument, api_version="2.0")
        return float(response.data.last_price)
    except:
        return 0.0

def get_live_option_chain(symbol_key, spot):
    """LIVE ATM ke aas-paas CHAIN - Upstox Option Chain API"""
    try:
        # SENSEX ke liye BSE, NIFTY ke liye NSE
        if "SENSEX" in symbol_key:
            instrument = "BSE_INDEX|SENSEX"
        else:
            instrument = "NSE_INDEX|Nifty 50"

        response = option_api.get_put_call_option_chain(instrument_key=instrument, api_version="2.0")
        chain_data = []
        for item in response.data:
            chain_data.append({
                "strike": item.strike_price,
                "ce_oi": item.call_options.market_data.oi if item.call_options else 0,
                "pe_oi": item.put_options.market_data.oi if item.put_options else 0,
                "ce_ltp": item.call_options.market_data.ltp if item.call_options else 0,
                "pe_ltp": item.put_options.market_data.ltp if item.put_options else 0,
            })
        df = pd.DataFrame(chain_data)
        # ATM ke 5 upar 5 niche filter
        df['diff'] = abs(df['strike'] - spot)
        atm_idx = df['diff'].idxmin()
        start = max(0, atm_idx - CONFIG["ATM_STRIKES"])
        end = atm_idx + CONFIG["ATM_STRIKES"] + 1
        return df.iloc[start:end], df
    except ApiException as e:
        st.warning(f"Option Chain Error (Market band ho sakta hai): {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- UI ---
st.title(f"🚀 {CONFIG['SYMBOL']} TOPU TOWER V4 - LIVE")
if st.button("🔄 LIVE REFRESH"):
    st.cache_data.clear()

@st.cache_data(ttl=30) # Har 30 sec live refresh
def load_live_data(symbol):
    df = get_live_candles(symbol)
    ltp = get_live_ltp(symbol)
    if ltp == 0 and not df.empty:
        ltp = df['close'].iloc[-1]
    atm_chain, full_chain = get_live_option_chain(symbol, ltp)
    return df, ltp, atm_chain, full_chain

df, live_ltp, atm_chain, full_chain = load_live_data(CONFIG['SYMBOL'])

if df.empty:
    st.error("Live data nahi aa raha - Market band hai ya Token expire hai. Token check kar.")
    st.stop()

# --- TREND LOGIC - LIVE DF PE ---
df['ema_fast'] = ta.ema(df['close'], length=CONFIG["EMA_FAST"])
df['ema_slow'] = ta.ema(df['close'], length=CONFIG["EMA_SLOW"])
df['upper'] = df['high'].rolling(CONFIG["CHANNEL_PERIOD"]).max()
df['lower'] = df['low'].rolling(CONFIG["CHANNEL_PERIOD"]).min()

day_open = df['open'].iloc[0]
ema_trend = "BULLISH" if df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1] else "BEARISH"
open_trend = "BULLISH" if live_ltp > day_open else "BEARISH"
final = "FINAL BULLISH ✅" if ema_trend == "BULLISH" and open_trend == "BULLISH" else "FINAL BEARISH ❌" if ema_trend == "BEARISH" and open_trend == "BEARISH" else "SIDEWAYS ⚠️"

# --- BADGE ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("LIVE LTP", f"{live_ltp:.1f}", f"{live_ltp-day_open:+.1f}")
c2.metric("DAY OPEN", f"{day_open:.1f}")
c3.metric("EMA", ema_trend)
c4.metric("CHANNEL", f"{df['lower'].iloc[-1]:.0f} - {df['upper'].iloc[-1]:.0f}")

if "BULLISH" in final:
    st.success(f"🟢 {final} - {CONFIG['SYMBOL']} | MANUAL BUY kar de Topu bhai | SL: {live_ltp-CONFIG['INITIAL_SL_POINTS']}")
else:
    st.error(f"🔴 {final} - {CONFIG['SYMBOL']} | WAIT / SELL STAR PLUS")

# --- CHART + LIVE CHAIN ---
left, right = st.columns([2, 1])
with left:
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close']))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_fast'], name="EMA 9"))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['upper'], line=dict(dash='dash'), name="Upper Channel"))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['lower'], line=dict(dash='dash'), name="Lower Channel"))
    fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader(f"💰 LIVE ATM Chain - {CONFIG['SYMBOL']}")
    if not atm_chain.empty:
        st.dataframe(atm_chain[['strike','ce_oi','pe_oi','ce_ltp','pe_ltp']], use_container_width=True, hide_index=True)
        max_ce = atm_chain.loc[atm_chain['ce_oi'].idxmax()]['strike']
        max_pe = atm_chain.loc[atm_chain['pe_oi'].idxmax()]['strike']
        st.info(f"Strong Support (Max PE OI): {max_pe}\n\nStrong Resistance (Max CE OI): {max_ce}")
        pcr = atm_chain['pe_oi'].sum() / atm_chain['ce_oi'].sum() if atm_chain['ce_oi'].sum()>0 else 0
        st.metric("LIVE PCR", f"{pcr:.2f}")
    else:
        
