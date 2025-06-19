import os, json
from flask import Flask, request, jsonify
from pybit.unified_trading import HTTP

# Загрузка настроек TP/SL
cfg = json.load(open('config.json'))

# Переменные окружения
API_KEY    = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
USE_DEMO   = os.getenv('USE_DEMO', 'false').lower() == 'true'
if not API_KEY or not API_SECRET:
    raise RuntimeError("API_KEY и API_SECRET должны быть заданы")

# Инициализация клиента ByBit (demo→testnet, иначе mainnet)
client = HTTP(testnet=USE_DEMO, api_key=API_KEY, api_secret=API_SECRET)

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify(status='alive', mode=('demo' if USE_DEMO else 'main')), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    # Парсим JSON
    try:
        data = json.loads(request.data.decode('utf-8'))
    except Exception as e:
        return jsonify(error=f'Invalid JSON: {e}'), 400

    sig = data.get('signal','').lower()
    try:
        price = float(data.get('price',0))
    except:
        return jsonify(error='Price is not a number'), 400
    ticker = data.get('ticker','')

    # Получаем баланс из UNIFIED-кошелька
    try:
        resp = client.get_wallet_balance(coin="USDT", accountType="UNIFIED")
        bal  = resp["result"]["list"][0]["wallet_balance"]
        equity = float(bal)
        qty = round((equity * 0.01) / price, 4)
    except Exception as e:
        return jsonify(error=f'Balance fetch failed: {e}'), 500

    # Открытие позиции
    if 'open' in sig:
        try:
            side = 'Buy' if 'long' in sig else 'Sell'
            client.place_active_order(
                category="linear", symbol=ticker, side=side,
                order_type="Market", qty=qty, time_in_force="GoodTillCancel"
            )
            tp = price * (1 + cfg['take_profit_pct']/100 if side=='Buy' else 1 - cfg['take_profit_pct']/100)
            sl = price * (1 - cfg['stop_loss_pct']/100 if side=='Buy' else 1 + cfg['stop_loss_pct']/100)
            client.set_trading_stop(
                category="linear", symbol=ticker, side=side,
                take_profit=tp, stop_loss=sl
            )
            return jsonify(status='opened'), 200
        except Exception as e:
            return jsonify(error=f'Open order failed: {e}'), 500

    # Закрытие позиции
    if 'close' in sig:
        try:
            side = 'Sell' if 'long' in sig else 'Buy'
            client.place_active_order(
                category="linear", symbol=ticker, side=side,
                order_type="Market", qty=qty, time_in_force="GoodTillCancel"
            )
            return jsonify(status='closed'), 200
        except Exception as e:
            return jsonify(error=f'Close order failed: {e}'), 500

    return jsonify(status='ignored'), 200

if __name__=='__main__':
    app.run(host='0.0.0.0', port=5000)
