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
                "⚠️ *إخلاء المسؤولية:*\n"
                "يستخدم هذا البوت خوارزميات لتحديد الإشارات والتوافق مع الشريعة الإسلامية. "
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
        return [coin["item"]["symbol"].upper() + "/USDT" for coin in response["coins"]]
    except Exception as e:
        print(f"⚠️ Error fetching trending tokens: {str(e)}")
        return []

# ✅ Function to fetch 1-week historical price data for long-term goals
def get_weekly_high(symbol):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe='1w', limit=2)
        if ohlcv and len(ohlcv) > 1:
            return max(ohlcv[-1][2], ohlcv[-2][2])  
        return None
    except Exception as e:
        print(f"⚠️ Error fetching weekly data for {symbol}: {str(e)}")
        return None

# ✅ Function to determine dynamic goals based on strategy
def calculate_dynamic_goals(price, symbol, strategy):
    weekly_high = get_weekly_high(symbol) or round(price * 1.75, 4)

    goals = {
        "Momentum Breakout 🚀": (1.12, 1.25, weekly_high, 0.90),
        "Trend Continuation 📈": (1.08, 1.18, weekly_high, 0.92),
        "Reversal Pattern 🔄": (1.06, 1.15, weekly_high, 0.93),
        "Consolidation Breakout ⏸➡🚀": (1.08, 1.20, weekly_high, 0.94),
        "News & Social Trend 📰": (1.05, 1.12, weekly_high, 0.95)
    }

    g1, g2, g3, sl = goals[strategy]
    return round(price * g1, 4), round(price * g2, 4), g3, round(price * sl, 4), (g1 - 1) * 100, (g2 - 1) * 100, (g3 / price - 1) * 100, (sl - 1) * 100

# ✅ Function to scan for trading opportunities
def find_gems():
    try:
        print("🔄 Fetching Binance Market Data...")
        market_data = binance.fetch_tickers()
        usdt_pairs = {symbol: data for symbol, data in market_data.items() if "/USDT" in symbol}
        trending_coins = get_trending_coins()
        today = datetime.now().date()

        for symbol, row in usdt_pairs.items():
            if symbol in sent_signals and sent_signals[symbol] == today:
                continue  

            percent_change = ((row['last'] - row['open']) / row['open']) * 100

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
                goal_1, goal_2, goal_3, stop_loss, p1, p2, p3, p_loss = calculate_dynamic_goals(entry_price, symbol, strategy_used)

                message = (
                    f"*{strategy_used}*\n"
                    f"📌 *Token:* `{symbol}`\n"
                    f"💰 *Entry Price:* `{entry_price:.4f} USDT`\n"
                    f"🎯 *Goal 1:* `{goal_1} USDT` (+{p1:.2f}%) (Short-term)\n"
                    f"🎯 *Goal 2:* `{goal_2} USDT` (+{p2:.2f}%) (Mid-term)\n"
                    f"🎯 *Goal 3:* `{goal_3} USDT` (+{p3:.2f}%) (Long-term, based on 1-week chart)\n"
                    f"⛔ *Stop Loss:* `{stop_loss} USDT` ({p_loss:.2f}%)\n"
                )

                send_telegram_alert(message)
                sent_signals[symbol] = today  

    except Exception as e:
        print(f"⚠️ Error: {str(e)}")

# ✅ Auto-Scanning Every 5 Minutes
threading.Thread(target=find_gems, daemon=True).start()
