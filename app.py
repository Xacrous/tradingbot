from flask import Flask, jsonify
import ccxt
import pandas as pd
import requests
import numpy as np
import time
import threading
from datetime import datetime, timedelta
import pytz  # To handle Kuwait timezone

app = Flask(__name__)

# ✅ Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7783208307:AAEWER2ylltWGd6g5I9XAH17yNmp7Imivbo"
TELEGRAM_CHAT_ID = "-1002324780762"  # Ensure it's negative for groups

# ✅ Binance API Initialization
binance = ccxt.binance()

# ✅ Prevent duplicate signals within 24 hours
sent_signals = {}  # Dictionary to store last sent signal time

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

# ✅ Function to determine dynamic goals based on strategy
def calculate_goals(price):
    goal_1 = round(price * 1.10, 4)  # Short-term (10% increase)
    goal_2 = round(price * 1.30, 4)  # Mid-term (30% increase)
    goal_3 = round(price * 2.00, 4)  # Long-term (100% increase)
    stop_loss = round(price * 0.90, 4)  # Stop loss (10% below entry)
    
    return goal_1, goal_2, goal_3, stop_loss

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
                continue  # ✅ Skip if required data is missing

            if row['last'] is None or row['open'] is None:
                print(f"⚠️ Skipping {symbol}: Missing 'last' or 'open' price data.")
                continue  # ✅ Skip tokens with missing price data

            # ✅ Prevent duplicate signals within 24 hours
            if symbol in sent_signals and current_time - sent_signals[symbol] < 86400:  # 86400 sec = 24 hours
                print(f"🔄 Skipping {symbol}: Signal already sent within 24 hours")
                continue

            # ✅ Calculate percentage change
            percent_change = ((row['last'] - row['open']) / row['open']) * 100

            # ✅ Signal condition
            if percent_change > 3 and row['quoteVolume'] > 1000000:
                entry_price = row['last']
                goal_1, goal_2, goal_3, stop_loss = calculate_goals(entry_price)

                print(f"🚀 Signal Detected: {symbol}")

                message = (
                    f"📌 *New Signal Detected!*\n"
                    f"✅ *Token:* `{symbol}`\n"
                    f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                    f"🎯 *Goals:*\n"
                    f"  1️⃣ `{goal_1} USDT` (+10%)\n"
                    f"  2️⃣ `{goal_2} USDT` (+30%)\n"
                    f"  3️⃣ `{goal_3} USDT` (+100%)\n"
                    f"⛔ *Stop Loss:* `{stop_loss} USDT` (-10%)\n"
                )
                
                send_telegram_alert(message)

                # ✅ Store timestamp to prevent duplicate signals for 24 hours
                sent_signals[symbol] = current_time
                signals.append(message)

        return signals

    except Exception as e:
        print(f"⚠️ Error during scanning: {str(e)}")
        return []

# ✅ Function to Automatically Scan Every 5 Minutes
def auto_scan():
    while True:
        print("🔄 Running automatic scan...")
        find_gems()
        time.sleep(300)  # Wait 5 minutes before next scan

# ✅ Start Auto-Scanning in a Background Thread
threading.Thread(target=auto_scan, daemon=True).start()

@app.route('/scan', methods=['GET'])
def scan_tokens():
    signals = find_gems()
    return jsonify({"status": "success", "signals": signals})

if __name__ == "__main__":
    print("🚀 Trading bot is running...")
    app.run(host="0.0.0.0", port=8080, debug=True)
