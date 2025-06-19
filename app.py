from flask import Flask, request
import json
from pybit import HTTP

# Загрузка конфига
cfg = json.load(open('config.json'))
client = HTTP('https://api.bybit.com', api_key=cfg['api_key'], api_secret=cfg['api_secret'])

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    sig = data.get('signal', '').lower()
    price = float(data.get('price', 0))

    # 1% от капитала
    bal = client.get_wallet_balance(coin="USDT")["result"]["USDT"]["wallet_balance"]
    equity = float(bal)
    qty = round((equity * 0.01) / price, 4)

    # Открытие
    if 'open' in sig:
        side = 'Buy' if 'long' in sig else 'Sell'
        client.place_active_order(
            symbol=data['ticker'],
            side=side,
            order_type='Market',
            qty=qty,
            time_in_force='GoodTillCancel'
        )
        tp = price * (1 + cfg['take_profit_pct']/100 if side=='Buy' else 1 - cfg['take_profit_pct']/100)
        sl = price * (1 - cfg['stop_loss_pct']/100 if side=='Buy' else 1 + cfg['stop_loss_pct']/100)
        client.set_trading_stop(
            symbol=data['ticker'],
            side=side,
            stop_loss=sl,
            take_profit=tp
        )
        return {'status': 'opened'}, 200

    # Закрытие
    elif 'close' in sig:
        side = 'Sell' if 'long' in sig else 'Buy'
        client.place_active_order(
            symbol=data['ticker'],
            side=side,
            order_type='Market',
            qty=qty,
            time_in_force='GoodTillCancel'
        )
        return {'status': 'closed'}, 200

    return {'status': 'ignored'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
