__author__ = 'jph'

import datetime as dt
import random

from lib.events import FillEvent


class TradingHandler(object):
    """
    Handles interface between orders, generated by a portfolio and fills
    uses connection to brokerage
    """

    def __init__(self, queue):
        self.queue = queue

    def execute_order(self, event):
        """
        executes order
        """
        raise NotImplementedError


class FakeInstantTradingHandler(TradingHandler):
    """
    simulates instant fills
    """

    def __init__(self, queue):
        super(FakeInstantTradingHandler, self).__init__(queue=queue)
        self.fakeid = 37

    def execute_order(self, event):
        price = 190 + round(random.random() * 10, 2)
        fill_event = FillEvent(dt.datetime.today(), event.symbol,
                               'BATS', event.quantity, event.side, 2, self.fakeid, price, ordereventid=event.id)
        self.fakeid += 1
        self.queue.put(fill_event)


class FakeBacktestTradingHandler(TradingHandler):
    """
    simulates fills in a backtesting environment
    """

    def __init__(self, queue):
        super(FakeBacktestTradingHandler, self).__init__(queue=queue)
        self.fakeid = 37
        self.lastprice = None

    def update_prices(self, datahandler):
        self.lastprice = datahandler.get_execution_data()

    def execute_order(self, event):
        if event.order_type == "MKT":
            if event.trigger is None:
                #MKT Order without Trigger
                price = self.lastprice['open']
                fill_event = FillEvent(dt.datetime.today(), event.symbol,
                                       'BATS', event.quantity, event.side, event.quantity * 0.01, self.fakeid, price,
                                       ordereventid=event.id)
                self.fakeid += 1
                self.queue.put(fill_event)
            else:
                #Trigger set
                if event.side == "BUY":
                    if event.trigger < self.lastprice['high']:
                        if event.trigger < self.lastprice['open']:
                            price = self.lastprice['open']
                        else:
                            price = event.trigger
                        fill_event = FillEvent(dt.datetime.today(), event.symbol,
                                               'BATS', event.quantity, event.side, event.quantity * 0.01, self.fakeid,
                                               price, ordereventid=event.id)
                        self.fakeid += 1
                        self.queue.put(fill_event)
                if event.side == "SELL":
                    if event.trigger > self.lastprice['low']:
                        if event.trigger > self.lastprice['open']:
                            price = self.lastprice['open']
                        else:
                            price = event.trigger
                        fill_event = FillEvent(dt.datetime.today(), event.symbol,
                                               'BATS', event.quantity, event.side, event.quantity * 0.01, self.fakeid,
                                               price, ordereventid=event.id)
                        self.fakeid += 1
                        self.queue.put(fill_event)

        elif event.order_type == "LMT":
            if event.side == "BUY":
                if event.limit > self.lastprice['low']:
                    if event.limit > self.lastprice['open']:
                        price = self.lastprice['open']
                    else:
                        price = event.limit
                    fill_event = FillEvent(dt.datetime.today(), event.symbol,
                                           'BATS', event.quantity, event.side, event.quantity * 0.01, self.fakeid,
                                           price, ordereventid=event.id)
                    self.fakeid += 1
                    self.queue.put(fill_event)
            elif event.side == "SELL":
                if event.limit < self.lastprice['high']:
                    if event.limit < self.lastprice['open']:
                        price = self.lastprice['open']
                    else:
                        price = event.limit
                    fill_event = FillEvent(dt.datetime.today(), event.symbol,
                                           'BATS', event.quantity, event.side, event.quantity * 0.01, self.fakeid,
                                           price, ordereventid=event.id)
                    self.fakeid += 1
                    self.queue.put(fill_event)
