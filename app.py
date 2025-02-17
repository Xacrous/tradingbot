from flask import Flask, jsonify
import ccxt
import requests
import numpy as np
import pandas as pd
import pandas_ta as ta
import time
import threading
from datetime import datetime, timedelta
import pytz  

app = Flask(__name__)

# ✅ Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7549407247:AAFvjKOpFj55FVPNynb4_EeeRWwtmXEInP0"
TELEGRAM_CHAT_ID = "-1002339266384"

# ✅ Binance API Initialization
binance = ccxt.binance()

# ✅ Prevent duplicate signals within 24 hours
sent_signals = {}

# ✅ Kuwait Timezone
KUWAIT_TZ = pytz.timezone("Asia/Kuwait")
last_disclaimer_sent = None  

# ✅ Function to send alerts to Telegram
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# ✅ Daily Disclaimer at 12 PM Kuwait Time
def send_daily_disclaimer():
    global last_disclaimer_sent
    while True:
        now = datetime.now(KUWAIT_TZ)
        if now.hour == 12 and (last_disclaimer_sent is None or last_disclaimer_sent.date() < now.date()):
            disclaimer_message = (
                "⚠️ *Disclaimer:*\n"
                "This bot uses algorithms to determine signals and Islamic permissibility. "
                "Please DYOR (Do Your Own Research) on every signal, we are not responsible for any losses.\n\n"
                "⚠️ *إخلاء المسؤولية:*\n"
                "يستخدم هذا البوت خوارزميات لتحديد الإشارات والتوافق مع الشريعة الإسلامية.\n"
                "يرجى إجراء بحثك الخاص على كل إشارة، نحن غير مسؤولين عن أي خسائر."
            )
            send_telegram_alert(disclaimer_message)
            last_disclaimer_sent = now
        time.sleep(3600)  

threading.Thread(target=send_daily_disclaimer, daemon=True).start()

# ✅ Function to get trending tokens from CoinGecko
def get_trending_coins():
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        response = requests.get(url).json()
        trending_coins = [coin["item"]["symbol"].upper() + "/USDT" for coin in response["coins"]]
        return trending_coins
    except Exception as e:
        print(f"⚠️ Error fetching trending tokens: {str(e)}")
        return []

# ✅ Function to determine dynamic goals based on strategy (Now Uses 1D for Goals 1 & 2, 1W for Goal 3)
def calculate_dynamic_goals(price, strategy):
    if strategy == "Momentum Breakout 🚀":
        return (round(price * 1.08, 4), round(price * 1.15, 4), round(price * 1.40, 4), round(price * 0.90, 4),
                8, 15, 40, -10)  # Short & Mid from 1D, Long from 1W
    elif strategy == "Trend Continuation 📈":
        return (round(price * 1.06, 4), round(price * 1.12, 4), round(price * 1.30, 4), round(price * 0.92, 4),
                6, 12, 30, -8)
    elif strategy == "Reversal Pattern 🔄":
        return (round(price * 1.05, 4), round(price * 1.10, 4), round(price * 1.25, 4), round(price * 0.93, 4),
                5, 10, 25, -7)
    elif strategy == "Consolidation Breakout ⏸➡🚀":
        return (round(price * 1.06, 4), round(price * 1.14, 4), round(price * 1.35, 4), round(price * 0.94, 4),
                6, 14, 35, -6)
    elif strategy == "News & Social Trend 📰":
        return (round(price * 1.04, 4), round(price * 1.08, 4), round(price * 1.20, 4), round(price * 0.95, 4),
                4, 8, 20, -5)
    return None

def get_technical_indicators(symbol):
    try:
        # Fetch 1-day historical OHLCV data for the token (last 100 days)
        ohlcv = binance.fetch_ohlcv(symbol, timeframe='1d', limit=100)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        # ✅ Technical Indicators
        df["rsi"] = ta.rsi(df["close"], length=14)  # Relative Strength Index
        df["sma_50"] = ta.sma(df["close"], length=50)  # 50-day Simple Moving Average
        df["sma_200"] = ta.sma(df["close"], length=200)  # 200-day Simple Moving Average
        df[["bb_low", "bb_mid", "bb_high"]] = ta.bbands(df["close"], length=20)  # Bollinger Bands
        df["macd"], df["macd_signal"], df["macd_hist"] = ta.macd(df["close"], fast=12, slow=26, signal=9).values.T  # MACD

        return df.iloc[-1]  # Return the latest values
    except Exception as e:
        print(f"⚠️ Error fetching indicators for {symbol}: {e}")
        return None


# ✅ Updated `find_gems()` Function with Technical Analysis
def find_gems():
    try:
        print("🔄 Fetching Binance Market Data...")
        market_data = binance.fetch_tickers()
        usdt_pairs = {symbol: data for symbol, data in market_data.items() if "/USDT" in symbol}

        trending_coins = get_trending_coins()

        signals = []
        today = datetime.now().date()

        for symbol, row in usdt_pairs.items():
            if not all(k in row and row[k] is not None for k in ['quoteVolume', 'open', 'last']):
                continue  

            # ✅ Prevent duplicate signals for the same token on the same day
            if symbol in sent_signals and sent_signals[symbol] == today:
                continue  

            percent_change = ((row['last'] - row['open']) / row['open']) * 100

            # ✅ Fetch Technical Indicators for this Token
            ta_data = get_technical_indicators(symbol)
            if ta_data is None:
                continue  # Skip if TA data is unavailable

            # ✅ Determine Volatility Level
            if abs(percent_change) > 10:
                volatility = "🔴 *High Volatility*"
            elif abs(percent_change) < 5:
                volatility = "🟢 *Low Volatility*"
            else:
                volatility = "🟡 *Moderate Volatility*"

            # ✅ Strategy Selection with Technical Indicators
            strategy_used = None

            # 📌 1. Momentum Breakout 🚀 (High RSI + MACD Bullish Crossover)
            if percent_change > 20 and ta_data["rsi"] > 70 and ta_data["macd"] > ta_data["macd_signal"]:
                strategy_used = "Momentum Breakout 🚀"

            # 📌 2. Trend Continuation 📈 (Price above 50-SMA & 200-SMA)
            elif 10 < percent_change <= 20 and ta_data["close"] > ta_data["sma_50"] > ta_data["sma_200"]:
                strategy_used = "Trend Continuation 📈"

            # 📌 3. Reversal Pattern 🔄 (Low RSI + MACD Bearish)
            elif percent_change < -5 and ta_data["rsi"] < 30 and ta_data["macd"] < ta_data["macd_signal"]:
                strategy_used = "Reversal Pattern 🔄"

            # 📌 4. Consolidation Breakout ⏸➡🚀 (Price near BB lower band + High Volume)
            elif abs(percent_change) < 3 and row['quoteVolume'] > 2000000 and ta_data["close"] <= ta_data["bb_low"]:
                strategy_used = "Consolidation Breakout ⏸➡🚀"

            # 📌 5. News & Social Trend 📰 (Trending CoinGecko + BB Breakout)
            elif symbol in trending_coins and row['quoteVolume'] > 5000000 and ta_data["close"] >= ta_data["bb_high"]:
                strategy_used = "News & Social Trend 📰"

            if strategy_used:
                entry_price = row['last']
                goal_1, goal_2, goal_3, stop_loss, p1, p2, p3, p_loss = calculate_dynamic_goals(entry_price, strategy_used)

                message = (
                    f"*{strategy_used}*\n"
                    f"📌 *Token:* `{symbol}`\n"
                    f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                    f"🎯 *Goal 1:* `{goal_1} USDT` (+{p1}%) (Short-term)\n"
                    f"🎯 *Goal 2:* `{goal_2} USDT` (+{p2}%) (Mid-term)\n"
                    f"⛔ *Stop Loss:* `{stop_loss} USDT` ({p_loss}%)\n"
                    f"📊 *Volatility:* {volatility}\n"
                    f"📈 *RSI:* `{ta_data['rsi']:.2f}` | *MACD:* `{ta_data['macd']:.2f}`\n"
                    f"📊 *50-SMA:* `{ta_data['sma_50']:.2f}` | *200-SMA:* `{ta_data['sma_200']:.2f}`\n"
                )

                send_telegram_alert(message)
                sent_signals[symbol] = today  
                signals.append(message)

        return signals

    except Exception as e:
        print(f"⚠️ Error during scanning: {str(e)}")
        return []

# ✅ Auto-Scanning Every 5 Minutes
def auto_scan():
    while True:
        find_gems()
        time.sleep(300)

threading.Thread(target=auto_scan, daemon=True).start()

@app.route('/scan', methods=['GET'])
def scan_tokens():
    return jsonify({"status": "success", "signals": find_gems()})

if __name__ == "__main__":
    print("🚀 Trading bot is running...")
    app.run(host="0.0.0.0", port=8080, debug=True)
