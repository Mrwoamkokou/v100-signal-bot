import websocket
import json
import pandas as pd
import requests
from ta.momentum import RSIIndicator
from datetime import datetime

BOT_TOKEN = "TON_TOKEN_ICI"
CHAT_ID = "TON_CHAT_ID_ICI"
SYMBOL = "R_100"
COUNT = 200

TIMEFRAMES = {
    "M1": 60,
    "M5": 300,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
    "W1": 604800,
    "MN": 2592000
}

def send_telegram_signal(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    r = requests.post(url, data=data)
    return r.ok

def get_v100_data(granularity):
    holder = {"candles": []}

    def on_message(ws, msg):
        res = json.loads(msg)
        holder["candles"] = res["history"]["candles"]
        ws.close()

    def on_open(ws):
        ws.send(json.dumps({
            "ticks_history": SYMBOL,
            "style": "candles",
            "granularity": granularity,
            "count": COUNT,
            "subscribe": 0
        }))

    ws = websocket.WebSocketApp(
        "wss://ws.derivws.com/websockets/v3?app_id=1089",
        on_open=on_open,
        on_message=on_message
    )
    ws.run_forever()

    df = pd.DataFrame(holder["candles"])
    df["time"] = pd.to_datetime(df["epoch"], unit='s')
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    return df[["time", "Open", "High", "Low", "Close"]]

def analyze_all_timeframes():
    results = {}
    for label, gran in TIMEFRAMES.items():
        try:
            df = get_v100_data(gran)
            df["RSI"] = RSIIndicator(close=df["Close"], window=14).rsi()
            last_rsi = df["RSI"].iloc[-1]
            signal = None
            if last_rsi < 30:
                signal = "🔻 Survente"
            elif last_rsi > 70:
                signal = "🔺 Surachat"
            else:
                signal = "➖ Neutre"
            results[label] = (round(last_rsi, 2), signal)
        except Exception as e:
            results[label] = ("Erreur", f"❌ {e}")
    return results

def send_if_consensus(results):
    achat_count = sum(1 for tf, (val, s) in results.items() if "Survente" in s)
    vente_count = sum(1 for tf, (val, s) in results.items() if "Surachat" in s)

    if achat_count >= 2:
        titre = "✅ *Signal d’ACHAT* confirmé"
    elif vente_count >= 2:
        titre = "🚫 *Signal de VENTE* confirmé"
    else:
        titre = "🔍 *Pas de consensus clair*"

    msg = titre + "\n\n"
    for tf, (val, s) in results.items():
        msg += f"📊 `{tf}` : RSI {val} → {s}\n"

    send_telegram_signal(msg)

if __name__ == "__main__":
    try:
        print("🟡 Script lancé...")
        tf_results = analyze_all_timeframes()
        print("🟢 Analyse OK, envoi Telegram...")
        send_if_consensus(tf_results)
        print("✅ Fini.")
    except Exception as e:
        print(f"❌ Erreur : {e}")
