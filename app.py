from flask import Flask, jsonify
import ccxt
import pandas as pd
import requests
import numpy as np

app = Flask(__name__)

# ✅ Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7783208307:AAEWER2ylltWGd6g5I9XAH17yNmp7Imivbo"
TELEGRAM_CHAT_ID = "1002324780762"

# ✅ Binance API Initialization
binance = ccxt.binance()

# ✅ Function to send alerts to Telegram
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# ✅ Function to calculate RSI
def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ✅ Function to calculate MACD
def calculate_macd(prices, short_window=12, long_window=26, signal_window=9):
    short_ema = prices.ewm(span=short_window, adjust=False).mean()
    long_ema = prices.ewm(span=long_window, adjust=False).mean()
    macd = short_ema - long_ema
    signal = macd.ewm(span=signal_window, adjust=False).mean()
    return macd, signal

# ✅ Function to fetch OHLCV (candlestick) data from Binance
def fetch_ohlcv(symbol, timeframe, limit=100):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching OHLCV for {symbol}: {str(e)}")
        return None

# ✅ Function to determine dynamic goals based on strategy
def calculate_goals(price, percent_change, rsi, macd, macd_signal):
    if percent_change > 20 and rsi > 70 and macd > macd_signal:  # 🚀 Momentum Breakout
        goal_1 = round(price * 1.12, 4)  # +12%
        goal_2 = round(price * 1.25, 4)  # +25%
        goal_3 = round(price * 1.40, 4)  # +40%
        stop_loss = round(price * 0.92, 4)  # -8%
        strategy_used = "Momentum Breakout 🚀"
    
    elif 10 < percent_change <= 20 and macd > macd_signal:  # 📈 Trend Continuation
        goal_1 = round(price * 1.08, 4)  # +8%
        goal_2 = round(price * 1.15, 4)  # +15%
        goal_3 = round(price * 1.25, 4)  # +25%
        stop_loss = round(price * 0.94, 4)  # -6%
        strategy_used = "Trend Continuation 📈"
    
    elif rsi < 30 and macd < macd_signal:  # 🔍 Reversal Pattern
        goal_1 = round(price * 1.06, 4)  # +6%
        goal_2 = round(price * 1.12, 4)  # +12%
        goal_3 = round(price * 1.18, 4)  # +18%
        stop_loss = round(price * 0.95, 4)  # -5%
        strategy_used = "Reversal Pattern 🔍"
    
    else:  # Default conservative strategy
        goal_1 = round(price * 1.05, 4)  # +5%
        goal_2 = round(price * 1.10, 4)  # +10%
        goal_3 = round(price * 1.15, 4)  # +15%
        stop_loss = round(price * 0.97, 4)  # -3%
        strategy_used = "Standard Trend ✅"

    return goal_1, goal_2, goal_3, stop_loss, strategy_used

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

            df_1d['RSI'] = calculate_rsi(df_1d['close'])
            df_1d['MACD'], df_1d['Signal'] = calculate_macd(df_1d['close'])

            latest_data = df_1d.iloc[-1]
            entry_price = latest_data['close']
            rsi = latest_data['RSI']
            macd = latest_data['MACD']
            macd_signal = latest_data['Signal']
            percent_change = ((entry_price - df_1d['close'].iloc[-2]) / df_1d['close'].iloc[-2]) * 100

            goal_1, goal_2, goal_3, stop_loss, strategy_used = calculate_goals(
                entry_price, percent_change, rsi, macd, macd_signal
            )

            message = (
                f"*{strategy_used} Detected!* 🔥"
"
                f"📌 *Token:* `{symbol}`
"
                f"💰 *Entry Price:* `{entry_price:.4f} USDT`
"
                f"📊 *RSI:* `{rsi:.2f}` | *MACD:* `{macd:.4f}`
"
                f"🎯 *Goals:*
"
                f"  1️⃣ `{goal_1} USDT`
"
                f"  2️⃣ `{goal_2} USDT`
"
                f"  3️⃣ `{goal_3} USDT`
"
                f"⛔ *Stop Loss:* `{stop_loss} USDT`
"
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
