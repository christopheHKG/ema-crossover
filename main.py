# libraries
import backtrader as bt
import datetime

import matplotlib

# import matplotlib.pyplot as plt
# plt.style.use("seaborn")

import pandas as pd
import json

# parameters:
START_CASH = 1_000
COMM = 0.001
SIZER = 99

# datafile = "./data/BTC-1D-from-20140917-to-20230506.csv"
datafile = "./data/ETH-1D-from-20171109-to-20230506.csv"

# load data feed

data = bt.feeds.YahooFinanceCSVData(
    dataname=datafile,
    #     fromdate=datetime.datetime(2011,11,9),
    #     todate=datetime.datetime(2023,5,6),
    reverse=False,
)


# code the strategies
class EMA_Crossover(bt.Strategy):
    # params
    params = dict(
        sma_period=200, short_ema_period=21, long_ema_period=55, verbose=False
    )

    def log(self, txt):
        if self.params.verbose:
            # logging text with date
            dt = self.datas[0].datetime.date(0)
            print(f"{dt}: {txt}")

    def __init__(self):
        # keep a reference to the 'open' and 'close' lines
        self.data_open = self.datas[0].open
        self.data_close = self.datas[0].close

        # keep track
        self.order = None
        self.exec_price = None
        self.comm = None
        self.buy_trade_date = None
        self.sell_trade_date = None

        # SMA - trend line
        self.sma = bt.indicators.SimpleMovingAverage(
            self.data_close, period=self.params.sma_period
        )

        # EMAs - crossover signal
        self.short_ema = bt.indicators.MovingAverageExponential(
            self.data_close, period=self.params.short_ema_period
        )
        self.long_ema = bt.indicators.MovingAverageExponential(
            self.data_close, period=self.params.long_ema_period
        )

        self.ema_diff = self.short_ema - self.long_ema

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # order submitted/accepted to/buy broker, nothing to do
            return

        # check if an order has been completed:
        if order.status in [order.Completed]:
            self.exec_price = order.executed.price
            self.comm = order.executed.comm

            if order.isbuy():
                self.log(f"BUY EXECUTED, price: {self.exec_price}")
                self.log(f"Cash amount: {order.executed.value:.2f}")
                self.log(f"Commissions paid: {self.comm:.2f}")
                self.buy_trade_date = len(self)

            else:  # sell order
                self.log(f"SELL EXECUTED, price: {self.exec_price}")
                self.log(f"Commissions paid: {self.comm:.2f}")
                self.sell_trade_date = len(self)

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # issue with the order
            self.log("Order canceled/margin/rejected")

        # clear
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log(f"TRADE duration: {self.sell_trade_date-self.buy_trade_date} days")
        self.log(f"TRADE PNL: Gross: {trade.pnl:.2f}")
        self.log(f"TRADE PNL: Net: {trade.pnlcomm:.2f}\n")

    def next(self):
        # log the open & close price
        #         self.log(f'Open:{self.dataopen[0]}')
        #         self.log(f'Close {self.dataclose[0]}')

        # check if an order is pending:
        if self.order:
            return

        # check if we are in the market
        if not self.position:
            # not yet, might BUY if:
            if (self.ema_diff > 0) and (self.data_close[0] > self.sma[0]):
                self.log("STRATEGY OPENS LONG POSITION")
                # keep track and avoid second order:
                self.order = self.buy()

        else:
            # we might sell if:
            if self.ema_diff < 0:
                self.log("STRATEGY CLOSES LONG POSITION")
                # keep track and avoid a second order
                self.order = self.sell()

    def stop(self):
        print(
            f"SMA: {self.params.sma_period}, End portfolio value: {self.broker.getvalue()}"
        )


# instantiate the cerebro engine
cerebro = bt.Cerebro()

# add the data feed to cerebro
cerebro.adddata(data)

# add a strategy
# cerebro.optstrategy(EMA_Crossover, sma_period=range(175, 225))
cerebro.addstrategy(EMA_Crossover)

# set start cash at $1,000
cerebro.broker.set_cash(START_CASH)
print(f"start portfolio value: {cerebro.broker.getvalue():.1f}")

# set a commission rate of 0.1%:
cerebro.broker.setcommission(commission=COMM)

# position sizing:
cerebro.addsizer(bt.sizers.PercentSizer, percents=SIZER)


# Plotting the value and drawdown lines

cerebro.addobserver(bt.observers.Value)
cerebro.addobserver(bt.observers.DrawDown)

backtest = cerebro.run()

cerebro.plot()
