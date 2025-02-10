from flask import Flask, jsonify
import ccxt
import pandas as pd
import requests
import numpy as np
import time

app = Flask(__name__)

# ✅ Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7783208307:AAEWER2ylltWGd6g5I9XAH17yNmp7Imivbo"
TELEGRAM_CHAT_ID = "-1002324780762"

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

# ✅ Function to scan for trading opportunities
def find_gems():
    try:
        market_data = binance.fetch_tickers()
        usdt_pairs = {symbol: data for symbol, data in market_data.items() if "/USDT" in symbol}

        signals = []
        for symbol in usdt_pairs.keys():
            df_1d = fetch_ohlcv(symbol, '1d', 50)
            df_1w = fetch_ohlcv(symbol, '1w', 50)

            if df_1d is None or df_1w is None:
                continue

            latest_data = df_1d.iloc[-1]
            entry_price = latest_data['close']
            percent_change = ((entry_price - df_1d['close'].iloc[-2]) / df_1d['close'].iloc[-2]) * 100

            message = (
                f"*Potential Trade Detected!* 🔥\n"
                f"📌 *Token:* `{symbol}`\n"
                f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                f"📊 *24h Change:* `{percent_change:.2f}%`\n"
            )

            send_telegram_alert(message)
            signals.append(message)

        return signals

    except Exception as e:
        send_telegram_alert(f"⚠️ Error: {str(e)}")
        return [str(e)]

@app.route('/scan', methods=['GET'])
def scan_tokens():
    signals = find_gems()
    return jsonify({"status": "success", "signals": signals})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
