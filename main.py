from datetime import datetime, timedelta
from time import sleep
from uuid import uuid4

from tinkoff.invest import Client, CandleInterval
from tinkoff.invest.grpc.orders_pb2 import (
    ORDER_DIRECTION_SELL,
    ORDER_DIRECTION_BUY,
    ORDER_TYPE_MARKET,
)

import json
import pandas as pd


def account_access_level(access_level):
    if access_level == 0:
        access_in_text = 'Уровень доступа не определён.'
    elif access_level == 1:
        access_in_text = 'Полный доступ к счёту.'
    elif access_level == 2:
        access_in_text = 'Доступ с уровнем прав "только чтение".'
    elif access_level == 3:
        access_in_text = 'Доступ отсутствует.'
    else:
        access_in_text = 'ОШИБКА ПОЛУЧЕНИЯ УРОВНЯ ДОСТУПА'

    return access_in_text


class Invest:

    def __init__(self):
        self.file_name = 'params.json'
        with open(self.file_name, 'r') as f:  # открыли файл с данными
            self.params = json.load(f)  # загнали все, что получилось в переменную
        # with Client(self.params['token']) as client:
        #     self.client = client
        self.client = Client(self.params['token']).__enter__()

    @staticmethod
    def money_to_float(item):
        return float(f'{item.units}.{item.nano}')

    def account_info(self):
        account_list = self.client.users.get_accounts()  # Возвращает массив аккаунтов
        for _account in account_list.accounts:
            access_text = account_access_level(_account.access_level)
            account_id = _account.id

            account_info = f'{_account.name}. {access_text} {account_id}'

            if _account.access_level == 1:
                self.params['account_id'] = account_id
                print(account_info)

            with open(self.file_name, 'w') as outfile:
                outfile.write(json.dumps(self.params, indent=4, ensure_ascii=False))

    def update_position(self, _ticker):
        positions = self.client.operations.get_portfolio(account_id=self.params['account_id']).positions
        ticker = self.params['tickers'][_ticker]
        update = False
        for instrument in positions:
            if instrument.figi == ticker['figi']:
                if self.money_to_float(instrument.quantity_lots):
                    ticker['quantity_lots'] = int(self.money_to_float(instrument.quantity_lots))
                else:
                    ticker['quantity_lots'] = 0
                update = True
        if not update:
            ticker['quantity_lots'] = 0

        with open(self.file_name, 'w') as outfile:
            outfile.write(json.dumps(self.params, indent=4, ensure_ascii=False))

    def update_instruments(self):

        shares_list = self.client.instruments.shares()
        count_instruments = len(self.params['tickers'])
        count_control_instruments = 0
        for _instrument in shares_list.instruments:
            ticker = self.params['tickers'].get(_instrument.ticker)
            if ticker:
                count_control_instruments += 1
                ticker['figi'] = _instrument.figi
                ticker['name'] = _instrument.name
                if _instrument.short_enabled_flag:
                    ticker['short_enabled_flag'] = 1,
            if count_control_instruments == count_instruments:
                break

        for _ticker in self.params['tickers']:
            self.update_position(_ticker)

    def trade(self, ema, ticker):
        action = None
        position_quantity = abs(self.params['tickers'][ticker]['delta_lots'])

        if ema['ema_fast']['last'] > ema['ema_long']['last']:
            action = 'buy'
        elif ema['ema_fast']['last'] < ema['ema_long']['last']:
            action = 'sell'

        # print(f'Вычисляем направление покупки, продажи: {action}')

        self.update_position(ticker)

        if action:
            trade = None
            if self.params['tickers'][ticker]['quantity_lots'] == 0:
                if action == 'buy':
                    trade = ORDER_DIRECTION_BUY
                elif action == 'sell' and self.params['tickers'][ticker]['short_enabled_flag']:
                    trade = ORDER_DIRECTION_SELL
            elif self.params['tickers'][ticker]['quantity_lots'] > 0:
                if action == 'sell':
                    trade = ORDER_DIRECTION_SELL
            elif self.params['tickers'][ticker]['quantity_lots'] < 0:
                if action == 'buy':
                    trade = ORDER_DIRECTION_BUY

            # print(trade)

            if trade:
                try:
                    print(f'{ticker}')
                    print(f'Направление торговли: {action}')
                    print(f'{ema["ema_fast"]["last"]} {ema["ema_long"]["last"]}')
                    posted_order = self.client.orders.post_order(
                        order_id=str(uuid4()),
                        figi=self.params['tickers'][ticker]['figi'],
                        direction=trade,
                        quantity=position_quantity,
                        order_type=ORDER_TYPE_MARKET,
                        account_id=self.params['account_id'],
                    )
                    self.update_position(ticker)

                    print(posted_order)
                    print('\n')

                except Exception as ex:
                    print(ex)

    def get_candles(self, ticker):
        with Client(self.params['token']) as client:
            time_now = datetime.now()
            time_day_ago = datetime.now() - timedelta(hours=1)

            candles_response = client.market_data.get_candles(from_=time_day_ago,
                                                              to=time_now,
                                                              interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
                                                              figi=self.params['tickers'][ticker]['figi'])

            candles_list = []
            for i in candles_response.candles:
                # candles_list.append({'close': self.money_to_float(i.close),
                #                      'high': self.money_to_float(i.high),
                #                      'low': self.money_to_float(i.low),
                #                      'open': self.money_to_float(i.open)})
                candles_list.append(self.money_to_float(i.close))
            return candles_list

    @staticmethod
    def ema(candles):
        candles_df = pd.DataFrame({'candles': candles})

        candles_df_ema_fast = candles_df.ewm(span=9, adjust=False).mean().values.tolist()
        last_candle_ema_fast = candles_df_ema_fast[-1][-1]
        pre_last_candle_ema_fast = candles_df_ema_fast[-2][-1]

        candles_df_ema_long = candles_df.ewm(span=21, adjust=False).mean().values.tolist()
        last_candle_ema_long = candles_df_ema_long[-1][-1]
        pre_last_candle_ema_long = candles_df_ema_long[-2][-1]

        return {'ema_fast': {'pre_last': pre_last_candle_ema_fast,
                             'last': last_candle_ema_fast},
                'ema_long': {'pre_last': pre_last_candle_ema_long,
                             'last': last_candle_ema_long},
                'candle': candles[-1]}

    def ensure_market_open(self, ticker):
        with Client(self.params['token']) as client:
            trading_status = client.market_data.get_trading_status(figi=self.params['tickers'][ticker]['figi'])
            while not (
                    trading_status.market_order_available_flag and trading_status.api_trade_available_flag
            ):
                print(f"Waiting for the market to open. {ticker}")
                sleep(60)
                trading_status = client.market_data.get_trading_status(figi=self.params['tickers'][ticker]['figi'])

    def main(self):
        self.account_info()
        self.update_instruments()
        while True:
            for ticker in self.params['tickers']:
                self.ensure_market_open(ticker)
                candles = self.get_candles(ticker)
                ema = self.ema(candles)

                # print(f'{ticker}')
                # print(f'pre: fast: {round(ema["ema_fast"]["pre_last"], 2)}  long: {round(ema["ema_long"]["pre_last"], 2)}')
                # print(f'last: fast: {round(ema["ema_fast"]["last"], 2)}  long: {round(ema["ema_long"]["last"], 2)}')

                self.trade(ema, ticker)

            sleep(10)


if __name__ == '__main__':
    Invest().main()
