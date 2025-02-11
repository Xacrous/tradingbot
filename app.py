import os
import ccxt
import requests
import time
import threading
import schedule
import pandas as pd
from flask import Flask, jsonify
from datetime import datetime, timedelta
import pytz
import talib

# ✅ Load credentials from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ✅ Initialize Flask app
app = Flask(__name__)

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

# ✅ Function to send daily disclaimer message
def send_daily_disclaimer():
    global last_disclaimer_sent
    now = datetime.now(KUWAIT_TZ)
    if now.hour == 12 and (last_disclaimer_sent is None or last_disclaimer_sent.date() < now.date()):
        disclaimer_message = (
            "⚠️ *Disclaimer:*\n"
            "This bot uses algorithms to determine signals and Islamic permissibility. "
            "Please DYOR (Do Your Own Research) on every signal, we are not responsible for any losses.\n\n"
            "⚠️ *إخلاء المسؤولية:*\n"
            "يستخدم هذا البوت خوارزميات لتحديد الإشارات والتوافق مع الشريعة الإسلامية. "
            "يرجى إجراء بحثك الخاص على كل إشارة، نحن غير مسؤولين عن أي خسائر."
        )
        send_telegram_alert(disclaimer_message)
        last_disclaimer_sent = now

# ✅ Function to fetch Binance market data
def fetch_binance_data():
    return binance.fetch_tickers()

# ✅ Function to get trending tokens from CoinGecko
def get_trending_coins():
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        response = requests.get(url).json()
        return [coin["item"]["symbol"].upper() + "/USDT" for coin in response["coins"]]
    except Exception as e:
        print(f"⚠️ Error fetching trending tokens: {str(e)}")
        return []

# ✅ Function to compute technical indicators
def compute_indicators(symbol):
    ohlcv = binance.fetch_ohlcv(symbol, timeframe="1h", limit=50)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])

    df["ema_50"] = talib.EMA(df["close"], timeperiod=50)
    df["ema_200"] = talib.EMA(df["close"], timeperiod=200)
    df["rsi"] = talib.RSI(df["close"], timeperiod=14)
    df["macd"], df["macd_signal"], _ = talib.MACD(df["close"], fastperiod=12, slowperiod=26, signalperiod=9)
    df["upper_bb"], df["middle_bb"], df["lower_bb"] = talib.BBANDS(df["close"], timeperiod=20)
    df["adx"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=14)
    df["stoch_rsi"] = talib.STOCHRSI(df["close"], timeperiod=14)
    
    return df.iloc[-1]

# ✅ Function to calculate price targets
def calculate_goals(entry, strategy):
    multipliers = {
        "Momentum Breakout 🚀": (1.08, 1.15, 1.40, 0.90),
        "Trend Continuation 📈": (1.06, 1.12, 1.30, 0.92),
        "Reversal Pattern 🔄": (1.05, 1.10, 1.25, 0.93),
        "Consolidation Breakout ⏸➡🚀": (1.06, 1.14, 1.35, 0.94),
        "News & Social Trend 📰": (1.04, 1.08, 1.20, 0.95),
    }
    return tuple(round(entry * x, 4) for x in multipliers[strategy])

# ✅ Function to scan for trading opportunities
def find_gems():
    market_data = fetch_binance_data()
    trending_coins = get_trending_coins()
    today = datetime.now().date()
    
    for symbol, row in market_data.items():
        if symbol in sent_signals and sent_signals[symbol] == today:
            continue  

        percent_change = ((row['last'] - row['open']) / row['open']) * 100
        indicators = compute_indicators(symbol)

        strategy_used = None
        if (
            percent_change > 20 and 
            55 <= indicators["rsi"] <= 75 and 
            indicators["macd"] > indicators["macd_signal"] and 
            row["last"] > indicators["upper_bb"]
        ):
            strategy_used = "Momentum Breakout 🚀"

        elif (
            10 < percent_change <= 20 and 
            row["last"] > indicators["ema_50"] and 
            indicators["adx"] > 25
        ):
            strategy_used = "Trend Continuation 📈"

        elif (
            percent_change < -5 and 
            indicators["rsi"] < 30 and 
            indicators["macd"] < indicators["macd_signal"]
        ):
            strategy_used = "Reversal Pattern 🔄"

        elif (
            abs(percent_change) < 3 and 
            row["quoteVolume"] > 2000000 and 
            indicators["middle_bb"] - indicators["lower_bb"] < 0.05 * row["last"]
        ):
            strategy_used = "Consolidation Breakout ⏸➡🚀"

        elif (
            symbol in trending_coins and 
            row["quoteVolume"] > 5000000 and 
            row["last"] > indicators["middle_bb"]
        ):
            strategy_used = "News & Social Trend 📰"

        if strategy_used:
            entry_price = row["last"]
            goal_1, goal_2, goal_3, stop_loss = calculate_goals(entry_price, strategy_used)

            message = (
                f"*{strategy_used}*\n"
                f"📌 *Token:* `{symbol}`\n"
                f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                f"🎯 *Goal 1:* `{goal_1} USDT` (Short-term) 📅 1-Day\n"
                f"🎯 *Goal 2:* `{goal_2} USDT` (Mid-term) 📅 1-Day\n"
                f"🎯 *Goal 3:* `{goal_3} USDT` (Long-term) 📅 1-Week\n"
                f"⛔ *Stop Loss:* `{stop_loss} USDT`\n"
            )

            send_telegram_alert(message)
            sent_signals[symbol] = today

# ✅ Auto-Scanning Every 5 Minutes using Schedule
def auto_scan():
    find_gems()
    schedule.every(5).minutes.do(find_gems)
    schedule.every().day.at("12:00").do(send_daily_disclaimer)
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=auto_scan, daemon=True).start()
