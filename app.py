from flask import Flask, jsonify
import ccxt
import requests
import time
import threading
from datetime import datetime, timedelta
import pytz  

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
‎                "⚠️ *إخلاء المسؤولية:*\n"
‎                "يستخدم هذا البوت خوارزميات لتحديد الإشارات والتوافق مع الشريعة الإسلامية. "
‎                "يرجى إجراء بحثك الخاص على كل إشارة، نحن غير مسؤولين عن أي خسائر."
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

# ✅ Function to scan for trading opportunities
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

            # ✅ Strategy Selection
            strategy_used = None
            if percent_change > 20:
                strategy_used = "Momentum Breakout 🚀"
            elif 10 < percent_change <= 20:
                strategy_used = "Trend Continuation 📈"
            elif percent_change < -5:
                strategy_used = "Reversal Pattern 🔄"
            elif abs(percent_change) < 3 and row['quoteVolume'] > 2000000:
                strategy_used = "Consolidation Breakout ⏸➡🚀"
            elif symbol in trending_coins and row['quoteVolume'] > 5000000:
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
                    f"🎯 *Goal 3:* `{goal_3} USDT` (+{p3}%) (Long-term)\n"
                    f"⛔ *Stop Loss:* `{stop_loss} USDT` ({p_loss}%)\n"
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
