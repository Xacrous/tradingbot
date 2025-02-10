from flask import Flask, jsonify
import ccxt
import pandas as pd
import requests
import numpy as np
import time
import threading
from datetime import datetime, timedelta
import pytz  # Timezone handling

app = Flask(__name__)

# ✅ Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7783208307:AAEWER2ylltWGd6g5I9XAH17yNmp7Imivbo"
TELEGRAM_CHAT_ID = "-1002324780762"

# ✅ Binance API Initialization
binance = ccxt.binance()

# ✅ Prevent duplicate signals within 24 hours
sent_signals = {}

# ✅ Kuwait Timezone
KUWAIT_TZ = pytz.timezone("Asia/Kuwait")
last_disclaimer_sent = None  # Track last disclaimer message time

# ✅ Function to send alerts to Telegram
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# ✅ Function to send daily disclaimer at 12 PM Kuwait time
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
                "يستخدم هذا البوت خوارزميات لتحديد الإشارات والتوافق مع الشريعة الإسلامية. "
                "يرجى إجراء بحثك الخاص على كل إشارة، نحن غير مسؤولين عن أي خسائر."
            )
            send_telegram_alert(disclaimer_message)
            last_disclaimer_sent = now
        time.sleep(3600)  # Check every hour to ensure it's sent at 12 PM

# ✅ Start the disclaimer function in a separate thread
threading.Thread(target=send_daily_disclaimer, daemon=True).start()

# ✅ Function to check financial halal compliance
def is_financially_halal(symbol, market_data):
    try:
        # 🚀 Exclude low liquidity tokens (high speculation risk)
        if market_data[symbol]['quoteVolume'] < 500000:
            return False

        # 🚀 Exclude interest-based staking/yield farming tokens
        if "stake" in symbol.lower() or "yield" in symbol.lower():
            return False

        return True  # Default to Halal if no red flags
    except KeyError:
        return None  # Unable to determine

# ✅ Function to determine dynamic goals based on strategy
def calculate_dynamic_goals(price, strategy):
    if strategy == "Momentum Breakout 🚀":
        return round(price * 1.12, 4), round(price * 1.25, 4), round(price * 1.50, 4), round(price * 0.90, 4)
    elif strategy == "Trend Continuation 📈":
        return round(price * 1.08, 4), round(price * 1.18, 4), round(price * 1.35, 4), round(price * 0.92, 4)
    elif strategy == "Reversal Pattern 🔄":
        return round(price * 1.06, 4), round(price * 1.15, 4), round(price * 1.30, 4), round(price * 0.93, 4)
    return round(price * 1.05, 4), round(price * 1.12, 4), round(price * 1.25, 4), round(price * 0.95, 4)

# ✅ Function to scan for trading opportunities
def find_gems():
    try:
        print("🔄 Fetching Binance Market Data...")
        market_data = binance.fetch_tickers()
        usdt_pairs = {symbol: data for symbol, data in market_data.items() if "/USDT" in symbol}

        signals = []
        current_time = time.time()

        for symbol, row in usdt_pairs.items():
            if 'quoteVolume' not in row or 'open' not in row or 'last' not in row:
                continue

            if row['last'] is None or row['open'] is None:
                print(f"⚠️ Skipping {symbol}: Missing 'last' or 'open' price data.")
                continue

            # ✅ Financial Screening for Halal Compliance
            if not is_financially_halal(symbol, market_data):
                print(f"❌ Skipping {symbol}: Fails financial screening")
                continue

            # ✅ Prevent duplicate signals within 24 hours
            if symbol in sent_signals and current_time - sent_signals[symbol] < 86400:
                print(f"🔄 Skipping {symbol}: Signal already sent within 24 hours")
                continue

            # ✅ Calculate percentage change
            percent_change = ((row['last'] - row['open']) / row['open']) * 100

            # ✅ Assign strategy based on movement
            if percent_change > 20:
                strategy_used = "Momentum Breakout 🚀"
            elif 10 < percent_change <= 20:
                strategy_used = "Trend Continuation 📈"
            elif percent_change < -5:
                strategy_used = "Reversal Pattern 🔄"
            else:
                strategy_used = "Standard Trend ✅"

            # ✅ Signal condition
            if percent_change > 3 and row['quoteVolume'] > 1000000:
                entry_price = row['last']
                goal_1, goal_2, goal_3, stop_loss = calculate_dynamic_goals(entry_price, strategy_used)

                print(f"🚀 {strategy_used}: {symbol} detected!")

                message = (
                    f"📌 *{strategy_used}*\n"
                    f"✅ *Token:* `{symbol}`\n"
                    f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                    f"🎯 *Goals:*\n"
                    f"  1️⃣ `{goal_1} USDT` (Short-term)\n"
                    f"  2️⃣ `{goal_2} USDT` (Mid-term)\n"
                    f"  3️⃣ `{goal_3} USDT` (Long-term)\n"
                    f"⛔ *Stop Loss:* `{stop_loss} USDT`\n"
                )

                send_telegram_alert(message)
                sent_signals[symbol] = current_time
                signals.append(message)

        return signals

    except Exception as e:
        print(f"⚠️ Error during scanning: {str(e)}")
        return []

# ✅ Auto-Scanning Every 5 Minutes
def auto_scan():
    while True:
        print("🔄 Running automatic scan...")
        find_gems()
        time.sleep(300)

threading.Thread(target=auto_scan, daemon=True).start()

@app.route('/scan', methods=['GET'])
def scan_tokens():
    return jsonify({"status": "success", "signals": find_gems()})

if __name__ == "__main__":
    print("🚀 Trading bot is running...")
    app.run(host="0.0.0.0", port=8080, debug=True)
