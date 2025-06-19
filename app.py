import os
import json
from flask import Flask, request, jsonify
from pybit.unified_trading import HTTP

# Загружаем TP/SL из config.json
cfg = json.load(open('config.json'))

# Читаем ключи и флаг демо-режима из окружения
api_key    = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')
use_demo   = os.getenv('USE_DEMO', 'false').lower() == 'true'

if not api_key or not api_secret:
    raise RuntimeError("API_KEY и API_SECRET не заданы в переменных окружения")

# Создаём HTTP-клиент: тестнет (demo) или mainnet
client = HTTP(
    testnet=use_demo,
    api_key=api_key,
    api_secret=api_secret,
)

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify(status='alive', mode=('demo' if use_demo else 'main')), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        payload = request.data.decode('utf-8')
        data    = json.loads(payload)
    except Exception as e:
        return jsonify(error=f'Неверный JSON: {e}'), 400

    sig = data.get('signal','').lower()
    try:
        price = float(data.get('price',0))
    except:
        return jsonify(error='Price не число'), 400
    ticker = data.get('ticker','')

    # 1% от баланса USDT
    bal    = client.get_wallet_balance(coin="USDT")["result"]["USDT"]["wallet_balance"]
    equity = float(bal)
    qty    = round((equity * 0.01) / price, 4)

    # открытие
    if 'open' in sig:
        side = 'Buy' if 'long' in sig else 'Sell'
        client.place_active_order(
            category="linear",
            symbol=ticker,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        tp = price * (1 + cfg['take_profit_pct']/100 if side=='Buy' else 1 - cfg['take_profit_pct']/100)
        sl = price * (1 - cfg['stop_loss_pct']/100 if side=='Buy' else 1 + cfg['stop_loss_pct']/100)
        client.set_trading_stop(
            category="linear",
            symbol=ticker,
            side=side,
            take_profit=tp,
            stop_loss=sl
        )
        return jsonify(status='opened'), 200

    # закрытие
    if 'close' in sig:
        side = 'Sell' if 'long' in sig else 'Buy'
        client.place_active_order(
            category="linear",
            symbol=ticker,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GoodTillCancel"
        )
        return jsonify(status='closed'), 200

    return jsonify(status='ignored'), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
