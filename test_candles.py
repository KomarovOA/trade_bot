from trade import Invest
import pandas as pd
import matplotlib.pyplot as plt

if __name__ == '__main__':
    Invest = Invest()
    Invest.update_instruments()
    for _ticker in Invest.params['tickers']:
        candles = Invest.get_candles(_ticker)

        candles_df = pd.Series(candles)

        candles_df_ema_fast = candles_df.ewm(span=9, adjust=False).mean().values.tolist()

        candles_df_ema_long = candles_df.ewm(span=21, adjust=False).mean().values.tolist()

        plt.plot(list(range(len(candles))), candles, 'blue')
        plt.plot(list(range(len(candles_df_ema_fast))), candles_df_ema_fast, 'green')
        plt.plot(list(range(len(candles_df_ema_long))), candles_df_ema_long, 'red')

        plt.show()
