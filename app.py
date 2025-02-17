from flask import Flask, jsonify
import ccxt
import requests
import numpy as np  # ✅ Import numpy BEFORE pandas_ta
import pandas as pd
import time
import threading
from datetime import datetime, timedelta
import pytz

# ✅ Import pandas_ta last
import pandas_ta as ta

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

import pandas as pd
import pandas_ta as ta

# ✅ Function to fetch OHLCV (candlestick) data and apply technical indicators
import pandas as pd
import pandas_ta as ta

def get_technical_indicators(symbol):
    try:
        # ✅ Fetch 1-day OHLCV historical data (last 100 days)
        ohlcv = binance.fetch_ohlcv(symbol, timeframe='1d', limit=100)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        # ✅ Print raw OHLCV data to debug missing values
        print(f"📊 {symbol} OHLCV Data:\n", df.head())

        # ✅ Check if we have enough data (at least 50 days)
        if df.shape[0] < 50:
            print(f"⚠️ Not enough historical data for {symbol} - Skipping.")
            return None

        # ✅ Calculate Technical Indicators
        df["rsi"] = ta.rsi(df["close"], length=14)
        df["sma_50"] = ta.sma(df["close"], length=50)
        df["sma_200"] = ta.sma(df["close"], length=200)
        
        # ✅ Handle Bollinger Bands
        bb = ta.bbands(df["close"], length=20)
        if bb is not None and bb.shape[1] == 3:
            df["bb_low"], df["bb_mid"], df["bb_high"] = bb.iloc[:, 0], bb.iloc[:, 1], bb.iloc[:, 2]
        else:
            df["bb_low"], df["bb_mid"], df["bb_high"] = None, None, None

        # ✅ Handle MACD
        macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
        if macd is not None and macd.shape[1] >= 3:
            df["macd"], df["macd_signal"], df["macd_hist"] = macd.iloc[:, 0], macd.iloc[:, 1], macd.iloc[:, 2]
        else:
            df["macd"], df["macd_signal"], df["macd_hist"] = None, None, None

        # ✅ Print computed TA values to debug missing data
        print(f"📈 TA Indicators for {symbol}:\n{df.tail(1)}")

        # ✅ Fill missing values with safe defaults instead of skipping
        df.fillna({
            "rsi": 50,  # Neutral RSI
            "sma_50": df["close"].mean(),
            "sma_200": df["close"].mean(),
            "bb_low": df["close"].min(),
            "bb_mid": df["close"].mean(),
            "bb_high": df["close"].max(),
            "macd": 0,
            "macd_signal": 0,
            "macd_hist": 0,
        }, inplace=True)

        return df.iloc[-1]  # Return the latest row
    except Exception as e:
        print(f"⚠️ Error fetching indicators for {symbol}: {e}")
        return None

# ✅ Updated `find_gems()` Function with Technical Analysis
def find_gems():
    try:
        print("🔄 Fetching Binance Market Data...")
        market_data = binance.fetch_tickers()
        usdt_pairs = {symbol: data for symbol, data in market_data.items() if "/USDT" in symbol}

        print(f"📊 Found {len(usdt_pairs)} USDT trading pairs.")

        trending_coins = get_trending_coins()
        print(f"🔥 Trending Coins: {trending_coins}")

        signals = []
        today = datetime.now().date()

        for symbol, row in usdt_pairs.items():
            try:
                if not all(k in row and row[k] is not None for k in ['quoteVolume', 'open', 'last']):
                    print(f"⚠️ Skipping {symbol} due to missing data.")
                    continue  

                # ✅ Prevent duplicate signals for the same token on the same day
                if symbol in sent_signals and sent_signals[symbol] == today:
                    print(f"🛑 {symbol} already sent today. Skipping.")
                    continue  

                percent_change = ((row['last'] - row['open']) / row['open']) * 100

                # ✅ Fetch Technical Indicators for this Token
                print(f"📊 Fetching TA for {symbol}...")
                # Fetch TA indicators
                ta_data = get_technical_indicators(symbol)
                if ta_data is None or ta_data.isnull().any():
                    print(f"⚠️ {symbol} has missing TA data - Using default values.")
                    continue  # Skipping this ensures only valid values are used

                
                # ✅ Ensure all indicators have valid float values
                required_indicators = ["rsi", "sma_50", "sma_200", "bb_low", "bb_mid", "bb_high", "macd", "macd_signal", "macd_hist"]
                if any(ta_data[ind] is None or not isinstance(ta_data[ind], float) for ind in required_indicators):
                    print(f"⚠️ TA data for {symbol} contains None values - Skipping.")
                    continue


                # ✅ Determine Volatility Level
                if abs(percent_change) > 10:
                    volatility = "🔴 *High Volatility*"
                elif abs(percent_change) < 5:
                    volatility = "🟢 *Low Volatility*"
                else:
                    volatility = "🟡 *Moderate Volatility*"

                # ✅ Strategy Selection with Technical Indicators
                strategy_used = None

                # 📌 1. Momentum Breakout 🚀
                if percent_change > 20 and ta_data["rsi"] > 70 and ta_data["macd"] > ta_data["macd_signal"]:
                    strategy_used = "Momentum Breakout 🚀"

                # 📌 2. Trend Continuation 📈
                elif 10 < percent_change <= 20 and ta_data["close"] > ta_data["sma_50"] > ta_data["sma_200"]:
                    strategy_used = "Trend Continuation 📈"

                # 📌 3. Reversal Pattern 🔄
                elif percent_change < -5 and ta_data["rsi"] < 30 and ta_data["macd"] < ta_data["macd_signal"]:
                    strategy_used = "Reversal Pattern 🔄"

                # 📌 4. Consolidation Breakout ⏸➡🚀
                elif abs(percent_change) < 3 and row['quoteVolume'] > 2000000 and ta_data["close"] <= ta_data["bb_low"]:
                    strategy_used = "Consolidation Breakout ⏸➡🚀"

                # 📌 5. News & Social Trend 📰
                elif symbol in trending_coins and row['quoteVolume'] > 5000000 and ta_data["close"] >= ta_data["bb_high"]:
                    strategy_used = "News & Social Trend 📰"

                if strategy_used:
                    print(f"✅ Strategy Selected for {symbol}: {strategy_used}")
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
                else:
                    print(f"⏳ No valid strategy for {symbol}, skipping.")

            except Exception as e:
                print(f"⚠️ Error processing {symbol}: {e}")

        print(f"✅ Scan completed. {len(signals)} signals sent.")
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
