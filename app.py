import os
import ccxt
import requests
import time
import threading
import schedule
import pandas as pd
import pandas_ta as ta  # ✅ Using pandas_ta correctly
from flask import Flask, jsonify
from datetime import datetime
import pytz

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

# ✅ Function to compute technical indicators (FIXED)
def compute_indicators(symbol):
    ohlcv = binance.fetch_ohlcv(symbol, timeframe="1h", limit=50)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])

    # ✅ Fix: Explicitly initialize pandas_ta
    df.ta.strategy("all")

    # ✅ Use correct `pandas_ta` syntax
    df["ema_50"] = ta.ema(df["close"], length=50)
    df["ema_200"] = ta.ema(df["close"], length=200)
    df["rsi"] = ta.rsi(df["close"], length=14)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df["macd"] = macd["MACD_12_26_9"]
    df["macd_signal"] = macd["MACDs_12_26_9"]
    bbands = ta.bbands(df["close"], length=20)
    df["upper_bb"] = bbands["BBU_20_2.0"]
    df["middle_bb"] = bbands["BBM_20_2.0"]
    df["lower_bb"] = bbands["BBL_20_2.0"]
    df["adx"] = ta.adx(df["high"], df["low"], df["close"], length=14)["ADX_14"]

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

# ✅ Function to determine market status (Bearish, Sideway, Bullish)
def determine_market_status(indicators):
    if indicators["ema_50"] < indicators["ema_200"]:
        return "📉 *Bearish Market*"
    elif abs(indicators["ema_50"] - indicators["ema_200"]) < 0.5:
        return "➡️ *Sideway Market*"
    else:
        return "📈 *Bullish Market*"

# ✅ Function to determine volatility status (Low, Mid, High)
def determine_volatility(indicators):
    if indicators["adx"] < 20:
        return "🟢 *Low Volatility*"
    elif 20 <= indicators["adx"] < 40:
        return "🟡 *Mid Volatility*"
    else:
        return "🔴 *High Volatility*"

# ✅ Function to scan for trading opportunities
def find_gems():
    market_data = fetch_binance_data()
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

        if strategy_used:
            entry_price = row["last"]
            goal_1, goal_2, goal_3, stop_loss = calculate_goals(entry_price, strategy_used)
            market_status = determine_market_status(indicators)
            volatility_status = determine_volatility(indicators)

            message = (
                f"*{strategy_used}*\n"
                f"📌 *Token:* `{symbol}`\n"
                f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                f"🎯 *Goal 1:* `{goal_1} USDT` (Short-term) 📅 1-Day\n"
                f"🎯 *Goal 2:* `{goal_2} USDT` (Mid-term) 📅 1-Day\n"
                f"⛔ *Stop Loss:* `{stop_loss} USDT`\n"
                f"{volatility_status}\n"
                f"{market_status}\n"
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

# ✅ Start Flask App with Correct Port
if __name__ == "__main__":
    print("🚀 Trading bot is running...")
    app.run(host="0.0.0.0", port=8080, debug=False)
