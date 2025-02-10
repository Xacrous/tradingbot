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

# ✅ Function to fetch OHLCV (candlestick) data from Binance
def fetch_ohlcv(symbol, timeframe, limit=100):
    try:
        time.sleep(2)  # Avoid API rate limits
        ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching OHLCV for {symbol}: {str(e)}")
        return None

# ✅ Function to determine dynamic goals based on strategy
def calculate_goals(price, percent_change):
    """
    Determine target goals dynamically based on market strategy.
    - Short-term (1-15% increase) → 1-day timeframe
    - Mid-term (15-45% increase) → 1-day timeframe
    - Long-term (45-150% increase) → 1-week timeframe
    """

    if percent_change > 20:
        strategy_used = "Momentum Breakout 🚀"
        goal_1 = round(price * 1.12, 4)  # +12%
        goal_2 = round(price * 1.35, 4)  # +35%
        goal_3 = round(price * 2.00, 4)  # +100%
        stop_loss = round(price * 0.90, 4)  # -10%

    elif percent_change > 10:
        strategy_used = "Trend Continuation 📈"
        goal_1 = round(price * 1.08, 4)  # +8%
        goal_2 = round(price * 1.25, 4)  # +25%
        goal_3 = round(price * 1.75, 4)  # +75%
        stop_loss = round(price * 0.92, 4)  # -8%

    elif percent_change < -5:
        strategy_used = "Reversal Opportunity 🔄"
        goal_1 = round(price * 1.05, 4)  # +5%
        goal_2 = round(price * 1.18, 4)  # +18%
        goal_3 = round(price * 1.50, 4)  # +50%
        stop_loss = round(price * 0.93, 4)  # -7%

    else:
        strategy_used = "Standard Investment ✅"
        goal_1 = round(price * 1.03, 4)  # +3%
        goal_2 = round(price * 1.12, 4)  # +12%
        goal_3 = round(price * 1.50, 4)  # +50%
        stop_loss = round(price * 0.95, 4)  # -5%

    return goal_1, goal_2, goal_3, stop_loss, strategy_used

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

                # ✅ Calculate dynamic goals
                goal_1, goal_2, goal_3, stop_loss, strategy_used = calculate_goals(entry_price, percent_change)

                # ✅ **Logging detected coins**
                print(f"🚀 {strategy_used}: {symbol} detected with {percent_change:.2f}% change.")

                message = (
                    f"🔥 *{strategy_used}*\n"
                    f"📌 *Token:* `{symbol}`\n"
                    f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                    f"🎯 *Goals:*\n"
                    f"  1️⃣ `{goal_1} USDT` (Short-Term)\n"
                    f"  2️⃣ `{goal_2} USDT` (Mid-Term)\n"
                    f"  3️⃣ `{goal_3} USDT` (Long-Term)\n"
                    f"⛔ *Stop Loss:* `{stop_loss} USDT`\n"
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

