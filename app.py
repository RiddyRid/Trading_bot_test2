import os, json
from flask import Flask, request
from pybit.unified_trading import HTTP

# TP/SL из config.json
cfg = json.load(open('config.json'))

# Ключи из переменных среды
api_key    = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')
if not api_key or not api_secret:
    raise RuntimeError("Не заданы API_KEY/API_SECRET в переменных окружения")

# Клиент ByBit unified_trading
client = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

app = Flask(__name__)

# Простая проверка «живости» сервиса
@app.route('/', methods=['GET'])
def home():
    return {'status':'alive'}, 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data   = request.get_json()
        sig    = data.get('signal','').lower()
        price  = float(data.get('price', 0))
        ticker = data.get('ticker','')

        # 1% от капитала
        bal    = client.get_wallet_balance(coin="USDT")["result"]["USDT"]["wallet_balance"]
        equity = float(bal)
        qty    = round((equity*0.01)/price, 4)

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
            tp = price*(1 + cfg['take_profit_pct']/100 if side=='Buy' else 1 - cfg['take_profit_pct']/100)
            sl = price*(1 - cfg['stop_loss_pct']/100 if side=='Buy' else 1 + cfg['stop_loss_pct']/100)
            client.set_trading_stop(
                category="linear",
                symbol=ticker,
                side=side,
                take_profit=tp,
                stop_loss=sl
            )
            return {'status':'opened'}, 200

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
            return {'status':'closed'}, 200

        return {'status':'ignored'}, 200

    except Exception as e:
        # Вернём текст ошибки, чтобы увидеть, что именно падало
        return {'error': str(e)}, 500

if __name__=='__main__':
    app.run(host='0.0.0.0', port=5000)
