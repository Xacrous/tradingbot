from flask import Flask, jsonify
import ccxt
import pandas as pd
import requests
import numpy as np
import time
import threading

app = Flask(__name__)

# ✅ Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7783208307:AAEWER2ylltWGd6g5I9XAH17yNmp7Imivbo"
TELEGRAM_CHAT_ID = "-1002324780762"  # Ensure it's negative for groups

# ✅ Binance API Initialization
binance = ccxt.binance()

# ✅ Function to send alerts to Telegram
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# ✅ Function to scan for trading opportunities
def find_gems():
    try:
        print("🔄 Fetching Binance Market Data...")
        market_data = binance.fetch_tickers()
        usdt_pairs = {symbol: data for symbol, data in market_data.items() if "/USDT" in symbol}

        signals = []
        print(f"✅ Found {len(usdt_pairs)} USDT pairs. Scanning...")

        for symbol, row in usdt_pairs.items():
            if 'quoteVolume' not in row or 'open' not in row or 'last' not in row:
                continue  # ✅ Skip if required data is missing

            if row['last'] is None or row['open'] is None:
                print(f"⚠️ Skipping {symbol}: Missing 'last' or 'open' price data.")
                continue  # ✅ Skip tokens with missing price data

            # ✅ Safe calculation to prevent NoneType errors
            percent_change = ((row['last'] - row['open']) / row['open']) * 100

            # ✅ **Lowered thresholds for more signals**
            if percent_change > 3 and row['quoteVolume'] > 1000000:  
                entry_price = row['last']

                # ✅ **Logging detected coins**
                print(f"🚀 {symbol} detected with {percent_change:.2f}% change and {row['quoteVolume']} volume.")

                message = (
                    f"🔥 *New Trading Signal Detected!*\n"
                    f"📌 *Token:* `{symbol}`\n"
                    f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                    f"📊 *24h Change:* `{percent_change:.2f}%`\n"
                )

                send_telegram_alert(message)
                signals.append(message)

        if not signals:
            print("⚠️ No strong signals found. Waiting for next scan...")

        return signals

    except Exception as e:
        error_msg = f"⚠️ Error during scanning: {str(e)}"
        print(error_msg)
        send_telegram_alert(error_msg)
        return [error_msg]

# ✅ Function to Automatically Scan Every 5 Minutes
def auto_scan():
    while True:
        print("🔄 Running automatic scan...")
        find_gems()
        time.sleep(300)  # Wait 5 minutes before the next scan

# ✅ Start Auto-Scanning in a Background Thread
threading.Thread(target=auto_scan, daemon=True).start()

@app.route('/scan', methods=['GET'])
def scan_tokens():
    signals = find_gems()
    return jsonify({"status": "success", "signals": signals})

if __name__ == "__main__":
    print("🚀 Trading bot is running...")
    app.run(host="0.0.0.0", port=8080, debug=True)
