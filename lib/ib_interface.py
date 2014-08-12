__author__ = 'jph'

#TODO: create class that servers as async IB interface for required tasks

import time
import datetime as dt
import copy

from ib.opt import ibConnection
from ib.ext import Contract, Order
import pytz
import pandas as pd

from util import synch


class IBInterface(object):
    def __init__(self, host='localhost', port=7499, clientId=1):
        self.con = ibConnection(host=host, port=port, clientId=clientId)
        #self.con.enableLogging()
        self.con.register(self.account_handler, 'UpdateAccountValue')
        self.con.register(self.portfolio_handler, 'UpdatePortfolio')
        self.con.register(self.orderstatus_handler, 'OrderStatus')
        self.con.register(self.openorder_handler, 'OpenOrder')
        self.con.register(self.historical_handler, 'HistoricalData')
        self.con.register(self.tick_handler, 'TickSize', 'TickPrice')
        self.con.register(self.string_handler, 'TickString')
        self.con.register(self.error_handler, 'Error')
        self.con.register(self.orderid_handler, 'NextValidId')

        self.nextID = 0
        self.prices = {}
        self.request_id = 1
        self.accounts = {}
        self.orders = {}
        self.hist_prices = {}

        self.est = pytz.timezone('US/Eastern')
        self.cet = pytz.timezone('Europe/Berlin')

    def connect(self):
        self.con.connect()
        self.con.reqIds(1)
        self.con.reqAccountUpdates(True, '')

    def disconnect(self):
        self.con.disconnect()

    def reqmktdata(self, symbol, type="STK", exch="SMART", generic="", snapshot=True, **kwargs):
        """
        Requests marketdata and returns a request ID
        symbol: symbol as string
        type: "STK" for Stocks, FUT for Futures
        exch: "SMART" for Stocks, "CME"/"GLOBEX" for futures
        generic: n/a
        snapshot: requests snapshot or continuous data stream
        """
        contract = Contract.Contract()
        contract.m_symbol = symbol
        contract.m_secType = type
        contract.m_exchange = exch
        contract.m_currency = "USD"
        self.prices[self.request_id] = {}
        self.con.reqMktData(self.request_id, contract, generic, snapshot)
        self.request_id += 1
        return self.request_id - 1

    def reqhistdata(self, symbol, rawdate, interval="1 D", resol="1 day", rth=1, type="STK", exch="SMART",
                    show='TRADES', expiry=None, expired=False):
        date = rawdate.strftime("%Y%m%d %H:%M:%S EST")
        contract = Contract.Contract()
        contract.m_symbol = symbol
        contract.m_secType = type
        contract.m_exchange = exch
        contract.m_currency = "USD"
        contract.m_includeExpired = expired
        if expiry:
            contract.m_expiry = expiry #format "201409"
        contract.m_multiplier = 50

        self.con.reqHistoricalData(self.request_id, contract, date, durationStr=interval, barSizeSetting=resol,
                                   useRTH=rth, formatDate=2,
                                   whatToShow=show)
        self.hist_prices[self.request_id] = {}
        self.request_id += 1

        return self.request_id - 1

    def place_order(self, side, symbol, size, ordertype, type="STK", exch="SMART", expiry="201403", stpprice=1400,
                    oca="", goodafter=None, lmtprice=0, rth=0, ignorerth=True, account="", group="All",
                    method="NetLiq", tif="GTC", parentid=0, goodtill=None, transmit=True, orderref=""):
        if goodtill:
            goodtill = goodtill.astimezone(self.est).strftime("%Y%m%d %H:%M:%S EST")
        if goodafter:
            goodafter = goodafter.astimezone(self.est).strftime("%Y%m%d %H:%M:%S EST")
        contract = Contract.Contract()
        contract.m_symbol = symbol
        contract.m_secType = type
        contract.m_exchange = exch
        contract.m_currency = "USD"
        contract.m_expiry = expiry

        order = Order.Order()
        order.m_action = side
        order.m_totalQuantity = size
        order.m_orderType = ordertype
        order.m_lmtPrice = lmtprice
        order.m_auxPrice = stpprice
        order.m_tif = tif
        order.m_goodAfterTime = goodafter
        order.m_goodTillDate = goodtill
        order.m_parentId = parentid
        order.m_outsideRth = ignorerth
        order.m_transmit = transmit
        order.m_ocaGroup = oca
        order.m_ocaType = 3
        order.m_orderRef = orderref
        if account:
            order.m_account = account
        else:
            order.m_faGroup = group
            order.m_faMethod = method

        id = self.nextID
        self.con.placeOrder(id, contract, order)
        self.nextID += 1
        self.orders[id] = {}
        self.con.reqIds(1)
        time.sleep(0.1) #todo: get more IDs so sleep is not necessary
        self.con.reqOpenOrders()
        return id

    def cancel_order(self, orderid):
        self.con.cancelOrder(orderid)

    def tick_handler(self, msg):
        """
        Handler for TickSize and TickPrize callbacks
        """
        if msg.field == 1:
            self.prices[msg.tickerId]['bidprice'] = msg.price
        elif msg.field == 2:
            self.prices[msg.tickerId]['askprice'] = msg.price
        elif msg.field == 4:
            self.prices[msg.tickerId]['last'] = msg.price
        elif msg.field == 6:
            self.prices[msg.tickerId]['high'] = msg.price
        elif msg.field == 7:
            self.prices[msg.tickerId]['low'] = msg.price
        elif msg.field == 14:
            self.prices[msg.tickerId]['open'] = msg.price
        elif msg.field == 0:
            self.prices[msg.tickerId]['bidsize'] = msg.size
        elif msg.field == 3:
            self.prices[msg.tickerId]['asksize'] = msg.size
        elif msg.field == 5:
            self.prices[msg.tickerId]['lastsize'] = msg.size
        elif msg.field == 8:
            self.prices[msg.tickerId]['volume'] = msg.size

    def string_handler(self, msg):
        """
        Handler for TickString callbacks
        """
        if msg.tickType == 45:
            self.prices[msg.tickerId]['timestamp'] = dt.datetime.fromtimestamp(int(msg.value))

    def error_handler(self, msg):
        """
        Handler for Error callbacks
        """
        print msg

    def execution_handler(self, msg):
        pass

    def orderid_handler(self, msg):
        self.nextID = msg.orderId

    def account_handler(self, msg):
        """
        Handler for UpdateAccountValue callbacks
        """
        if msg.accountName not in self.accounts:
            self.accounts[msg.accountName] = {'portfolio': {}}
        if msg.key == 'CashBalance':
            self.accounts[msg.accountName]['cash'] = msg.value
        elif msg.key == "MaintMarginReq":
            self.accounts[msg.accountName]['margin'] = msg.value
        elif msg.key == "NetLiquidation":
            self.accounts[msg.accountName]['netliq'] = msg.value
        elif msg.key == "EquityWithLoanValue":
            self.accounts[msg.accountName]['equity'] = msg.value
        elif msg.key == "PreviousDayEquityWithLoanValue":
            self.accounts[msg.accountName]['prevequity'] = msg.value

    def portfolio_handler(self, msg):
        """
        Handler for UpdatePortfolio callbacks
        """
        symbol = msg.contract.m_symbol
        if msg.accountName not in self.accounts:
            self.accounts[msg.accountName] = {'portfolio': {}} #creates new entry if not already available
        if symbol not in self.accounts[msg.accountName]['portfolio']:
            self.accounts[msg.accountName]['portfolio'][symbol] = {}
        self.accounts[msg.accountName]['portfolio'][symbol]['position'] = msg.position
        self.accounts[msg.accountName]['portfolio'][symbol]['price'] = msg.marketPrice
        self.accounts[msg.accountName]['portfolio'][symbol]['value'] = msg.marketValue
        self.accounts[msg.accountName]['portfolio'][symbol]['cost'] = msg.averageCost
        self.accounts[msg.accountName]['portfolio'][symbol]['unrealpnl'] = msg.unrealizedPNL
        self.accounts[msg.accountName]['portfolio'][symbol]['realpnl'] = msg.realizedPNL

    def orderstatus_handler(self, msg):
        if msg.orderId not in self.orders:
            self.orders[msg.orderId] = {}
        self.orders[msg.orderId]['status'] = msg.status
        self.orders[msg.orderId]['filled'] = msg.filled
        self.orders[msg.orderId]['remaining'] = msg.remaining
        self.orders[msg.orderId]['avgfillprice'] = msg.avgFillPrice
        self.orders[msg.orderId]['lastfillprice'] = msg.lastFillPrice
        self.orders[msg.orderId]['permid'] = msg.permId
        self.orders[msg.orderId]['clientid'] = msg.clientId
        self.orders[msg.orderId]['whyheld'] = msg.whyHeld

    def openorder_handler(self, msg):
        if msg.orderId not in self.orders.keys():
            self.orders[msg.orderId] = {}
        self.orders[msg.orderId]['symbol'] = msg.contract.m_symbol
        self.orders[msg.orderId]['side'] = msg.order.m_action
        self.orders[msg.orderId]['size'] = msg.order.m_totalQuantity
        self.orders[msg.orderId]['type'] = msg.order.m_orderType
        self.orders[msg.orderId]['limit'] = msg.order.m_lmtPrice
        self.orders[msg.orderId]['stpprice'] = msg.order.m_auxPrice
        self.orders[msg.orderId]['oca'] = msg.order.m_ocaGroup
        self.orders[msg.orderId]['orderref'] = msg.order.m_orderRef


    def historical_handler(self, msg):
        if msg.date[:8] == "finished":
            pass
        else:
            date = dt.datetime.fromtimestamp(int(msg.date))
            if date not in self.hist_prices[msg.reqId].keys():
                self.hist_prices[msg.reqId][date] = {}
            self.hist_prices[msg.reqId][date]['open'] = msg.open
            self.hist_prices[msg.reqId][date]['close'] = msg.close
            self.hist_prices[msg.reqId][date]['high'] = msg.high
            self.hist_prices[msg.reqId][date]['low'] = msg.low
            self.hist_prices[msg.reqId][date]['volume'] = msg.volume
            self.hist_prices[msg.reqId][date]['count'] = msg.count
            self.hist_prices[msg.reqId][date]['wap'] = msg.WAP
            self.hist_prices[msg.reqId][date]['gaps'] = msg.hasGaps


class IBComfort(IBInterface):
    def __init__(self, **kwargs):
        super(IBComfort, self).__init__(**kwargs)

    def comf_reqhistdata(self, last_date, first_date, symbol, interval="1 W", resol="1 hour", rth=0, show="TRADES",
                         type="STK", exch="SMART", expiry=None, expired=False):
        resols = {'1 day': dt.timedelta(days=90), '1 hour': dt.timedelta(days=6), '15 mins': dt.timedelta(days=6),
                  '1 min': dt.timedelta(days=2), '1 secs': dt.timedelta(minutes=30)}
        if interval == "1 M": resols['1 hour'] = dt.timedelta(days=28)
        if last_date.hour == 0 and last_date.minute == 0:
            last_date = last_date.replace(hour=23, minute=59)
        if last_date.tzinfo == None:
            last_date = self.est.localize(last_date)
            first_date = self.est.localize(first_date)
        else:
            last_date = last_date.astimezone(self.est)
            first_date = first_date.astimezone(self.est)
        erg = {}
        z = 1
        while last_date >= first_date:
            print last_date.strftime("Getting historical Data for %Y%m%d %H:%M:%S EST ...")
            id = self.reqhistdata(symbol, last_date, interval, resol, rth=rth, show=show, type=type, exch=exch,
                                  expiry=expiry, expired=expired)
            z += 1
            last_date = last_date - resols[resol]
            if not self.wait_for_hist(id, interval): #waits for results
                print "Fehler, keine Daten empfangen"
                print self.hist_prices
                return None
            erg.update(dict((time.mktime(key.timetuple()), value) for (key, value) in self.hist_prices[id].items()))
            if z % 60 == 0:
                time.sleep(590)
            if z % 5 == 0:
                time.sleep(2)
        hist_data = pd.DataFrame.from_dict(erg, orient="index")
        hist_data.index = [dt.datetime.fromtimestamp(x) for x in hist_data.index]
        hist_data = hist_data.tz_localize(self.cet).tz_convert(self.est)
        return hist_data

    def wait_for_hist(self, id, interval):
        quote_fields = ('high', 'close', 'volume', 'low', 'open')
        mindates = {'1 W': 4, '1 D': 1, '1 M': 15, '300 S': 5}
        minlen = mindates[interval] if interval in mindates else 8
        tmp = copy.copy(self.hist_prices[id])
        #checks if histkurse still changing and if all dates in histkurse are complete
        for i in xrange(1000):
            if tmp == self.hist_prices[id]:
                if self.hist_prices[id]:
                    if all(k in tmp[dates] for k in quote_fields for dates in tmp) and len(tmp.keys()) > minlen:
                        return True
            else:
                tmp = copy.copy(self.hist_prices[id])
            time.sleep(0.02)
        return False

    def getspy(self):
        @synch(self.prices,
               required=('last', 'asksize', 'timestamp', 'askprice', 'volume', 'lastsize', 'bidprice', 'bidsize'))
        def synch_mkt_data(*args, **kwargs): return self.reqmktdata(*args, **kwargs)
        return synch_mkt_data('SPY', snapshot=True)

    def getorders(self):
        """
        only for testing
        """
        return self.orders

    def new_bars(self, only_ask=False, freq="1m1d", current_index=None):
        jetzt = self.cet.localize(dt.datetime.today()).astimezone(self.est)
        start_data = jetzt if current_index is None else current_index[-1]
        freqinfo = {
        '15m': {'interva': '1 W', 'resol': '15 mins', 'mindelta': dt.timedelta(minutes=13), 'until': start_data},
        #until koennte auch z.b. spy.index[-1]
        '15m1d': {'interva': '1 D', 'resol': '15 mins', 'mindelta': dt.timedelta(minutes=13), 'until': jetzt},
        '1h': {'interva': '1 W', 'resol': '1 hour', 'mindelta': dt.timedelta(minutes=57), 'until': start_data},
        '1m': {'interva': '2 D', 'resol': '1 min', 'mindelta': dt.timedelta(seconds=50), 'until': start_data},
        '1m1d': {'interva': '300 S', 'resol': '1 min', 'mindelta': dt.timedelta(seconds=50), 'until': jetzt}}
        interva = freqinfo[freq]['interva']
        resol = freqinfo[freq]['resol']
        mindelta = freqinfo[freq]['mindelta']
        until = freqinfo[freq]['until']

        if only_ask:
            newdata = self.comf_reqhistdata(jetzt, jetzt, "SPY", interval=interva, resol=resol, show='ASK')
        else:
            newdata = self.comf_reqhistdata(jetzt, until, "SPY", interval=interva, resol=resol, show='TRADES')
            biddata = self.comf_reqhistdata(jetzt, until, "SPY", interval=interva, resol=resol, show='BID')
            askdata = self.comf_reqhistdata(jetzt, until, "SPY", interval=interva, resol=resol, show='ASK')

            if newdata is not None and biddata is not None and askdata is not None:
                askdata = askdata.reindex(newdata.index)
                biddata = biddata.reindex(newdata.index)
                bed_high = newdata.high > askdata.high
                bed_low = newdata.low < biddata.low
                newdata.high[bed_high] = askdata.high
                newdata.low[bed_low] = biddata.low
                bed_open_high = newdata.open > askdata.high
                bed_open_low = newdata.open < biddata.low
                bed_close_high = newdata.close > askdata.high
                bed_close_low = newdata.close < biddata.low
                newdata.open[bed_open_high] = askdata.high
                newdata.open[bed_open_low] = biddata.low
                newdata.close[bed_close_high] = askdata.high
                newdata.close[bed_close_low] = biddata.low
                newdata.volume = newdata.volume * 100
            else:
                return None

        if newdata is not None:
            now = self.cet.localize(dt.datetime.today()).astimezone(self.est)
            if now - newdata.index[-1] < mindelta:
                newdata = newdata.iloc[:-1, :]
            newdata = newdata.drop(['count', 'gaps', 'wap', 'volume'], 1)
            return newdata
        return None


if __name__ == '__main__':
    #TODO only for testing

    ib = IBComfort(port=7499, clientId=1)
    ib.connect()
    time.sleep(3)


    @synch(ib.prices, timeout=2, required=('last', 'open', 'high', 'low'))
    def synch_mkt_data(*args, **kwargs):
        return ib.reqmktdata(*args, **kwargs)

    a = time.time()
    print synch_mkt_data('SPY', snapshot=True)
    b = time.time()
    print b - a

    #testid = ib.nextID
    #orderid = ib.place_order("BUY", "SPY", 47, "MKT", orderref="testtest")
    #orderid = ib.place_order("BUY", "SPY", 57, "MKT")
    a = time.time()
    #while ib.nextID == testid:
    #    pass
    b = time.time()
    print b - a

    time.sleep(1)
    print ib.orders
    print ib.accounts

    def cancel_orders():
        for order in ib.orders:
            ib.cancel_order(order)

    import pdb

    histdata = ib.comf_reqhistdata(dt.datetime.today(), dt.datetime.today() - dt.timedelta(days=5), 'ES',
                                   interval="1 M", type="FUT", exch="GLOBEX")
    ib.disconnect()
    pdb.set_trace()

    #print histdata
    #pdb.set_trace()