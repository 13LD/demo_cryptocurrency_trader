import urllib, http.client
import time
import json
import hmac, hashlib

API_KEY = 'K-4d71fae7b9232c96e1e1c1e10ff4adf34f012308'
API_SECRET = 'S-d3597bc1a4d9b53fe6a3a1b54ce07838974c2d40'


CURRENCY_1 = 'ETC'
CURRENCY_2 = 'USD'

CURRENCY_1_MIN_QUANTITY = 0.01 

ORDER_LIFE_TIME = 1 
STOCK_FEE = 0.002 
AVG_PRICE_PERIOD = 30 
CAN_SPEND = 20 
PROFIT_MARKUP = 0.001 
DEBUG = False 

STOCK_TIME_OFFSET = 0 

API_URL = 'api.exmo.com'
API_VERSION = 'v1'

class ScriptError(Exception):
    pass
class ScriptQuitCondition(Exception):
    pass

CURRENT_PAIR = CURRENCY_1 + '_' + CURRENCY_2

def call_api(api_method, http_method="POST", **kwargs):

    payload = {'nonce': int(round(time.time()*1000))}

    if kwargs:
        payload.update(kwargs)
    payload =  urllib.parse.urlencode(payload)

    H = hmac.new(key=b'S-d3597bc1a4d9b53fe6a3a1b54ce07838974c2d40', digestmod=hashlib.sha512)
    H.update(payload.encode('utf-8'))
    sign = H.hexdigest()

    headers = {"Content-type": "application/x-www-form-urlencoded",
           "Key":API_KEY,
           "Sign":sign}
    conn = http.client.HTTPSConnection(API_URL, timeout=60)
    conn.request(http_method, "/"+API_VERSION + "/" + api_method, payload, headers)
    response = conn.getresponse().read()

    conn.close()

    try:
        obj = json.loads(response.decode('utf-8'))

        if 'error' in obj and obj['error']:
            raise ScriptError(obj['error'])
        return obj
    except json.decoder.JSONDecodeError:
        raise ScriptError('Error', response)

def main_flow():

    try:
        try:
            opened_orders = call_api('user_open_orders')[CURRENCY_1 + '_' + CURRENCY_2]
        except KeyError:
            if DEBUG:
                print('No open orders')
            opened_orders = []

        sell_orders = []
        for order in opened_orders:
            if order['type'] == 'sell':
                raise ScriptQuitCondition('Exit and wait orders')
            else:
                sell_orders.append(order)

        if sell_orders: 
            for order in sell_orders:
                if DEBUG:
                    print('Check orders', order['order_id'])
                try:
                    order_history = call_api('order_trades', order_id=order['order_id'])
                    raise ScriptQuitCondition('Wait to buy on the same coutrse')
                except ScriptError as e:
                    if DEBUG:
                        print('No part orders')

                    time_passed = time.time() + STOCK_TIME_OFFSET*60*60 - int(order['created'])

                    if time_passed > ORDER_LIFE_TIME * 60:
                        call_api('order_cancel', order_id=order['order_id'])
                        raise ScriptQuitCondition('Cancel order for' + str(ORDER_LIFE_TIME) + ' min cant buy '+ str(CURRENCY_1))
                    else:
                        raise ScriptQuitCondition('Exit %s sec' % str(time_passed))


        else: 
            balances = call_api('user_info')['balances']
            if float(balances[CURRENCY_1]) >= CURRENCY_1_MIN_QUANTITY: 
                wanna_get = CAN_SPEND + CAN_SPEND * (STOCK_FEE + PROFIT_MARKUP)  
                print('sell', balances[CURRENCY_1], wanna_get, (wanna_get/float(balances[CURRENCY_1])))
                new_order = call_api(
                    'order_create',
                    pair=CURRENT_PAIR,
                    quantity = balances[CURRENCY_1],
                    price=wanna_get/float(balances[CURRENCY_1]),
                    type='sell'
                )
                print(new_order)
                if DEBUG:
                    print('Created order', CURRENCY_1, new_order['order_id'])
            else:
                if float(balances[CURRENCY_2]) >= CAN_SPEND:
                    deals = call_api('trades', pair=CURRENT_PAIR)
                    prices = []
                    for deal in deals[CURRENT_PAIR]:
                        time_passed = time.time() + STOCK_TIME_OFFSET*60*60 - int(deal['date'])
                        if time_passed < AVG_PRICE_PERIOD*60:
                            prices.append(float(deal['price']))
                    try:
                        avg_price = sum(prices)/len(prices)
                
                        my_need_price = avg_price
                        my_amount = CAN_SPEND / my_need_price

                        print('buy', my_amount, my_need_price)

                        if my_amount >= CURRENCY_1_MIN_QUANTITY:
                            new_order = call_api(
                                'order_create',
                                pair=CURRENT_PAIR,
                                quantity = my_amount,
                                price=my_need_price,
                                type='buy'
                            )
                            print(new_order)
                            if DEBUG:
                                print('Order for buy', new_order['order_id'])

                        else: 
                            ScriptQuitCondition('No money for order')
                    except ZeroDivisionError:
                        print('cant count avv price', prices)
                else:
                    raise ScriptQuitCondition('exit mot enough money')

    except ScriptError as e:
        print(e)
    except ScriptQuitCondition as e:
        if DEBUG:
            print(e)
        pass
    except Exception as e:
        print("!!!!",e)

while(True):
    main_flow()
    time.sleep(1)
