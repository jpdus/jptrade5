__author__ = 'jph'
import json
import pdb

import pandas as pd


def json_to_workfile(json_list):
    workfile = pd.DataFrame(json_list)
    workfile = workfile.set_index(pd.to_datetime(workfile.timestamp))
    workfile = workfile.drop('timestamp', 1)
    return workfile


def read_logfile(log='log.txt'):
    with open(log, 'r') as logfile:
        market = []
        signal = []
        order = []
        fill = []
        for line in logfile:
            elements = line.split(',', 2)
            if elements[1] == "MARKET":
                market.append(json.loads(elements[2]))
            elif elements[1] == "SIGNAL":
                signal.append(json.loads(elements[2]))
            elif elements[1] == "ORDER":
                order.append(json.loads(elements[2]))
            elif elements[1] == "FILL":
                fill.append(json.loads(elements[2]))
    print "Market: %s" % len(market)
    print "Signal: %s" % len(signal)
    print "Order: %s" % len(order)
    print "Fill: %s" % len(fill)
    market = json_to_workfile(market)
    signal = json_to_workfile(signal)
    order = json_to_workfile(order)
    fill = json_to_workfile(fill)
    return market, signal, order, fill


def calc_costs(fill, signal):
    fills_compare = pd.merge(fill, signal, left_on='signalid', right_on='id', how='left', left_index=True)
    difference = abs(fills_compare.trigger - fills_compare.price)
    geskost = (difference * fills_compare.quantity + fills_compare.total_cost) / (
        fills_compare.quantity * fills_compare.price)

    return fills_compare, geskost


if __name__ == "__main__":
    market, signal, order, fill = read_logfile('E:\Dev\jptrade5\log_22082014.txt')
    fills_compare, geskost = calc_costs(fill, signal)
    print fills_compare.total_cost.describe()
    print geskost.describe()
    print geskost[fills_compare.side_x == "BUY"].describe()
    print geskost[fills_compare.side_x == "SELL"].describe()

    #todo workaround, sollte gefixt sein
    #commissions = (fills_compare.quantity * 0.005) + (
    #    (fills_compare.quantity * fills_compare.price * 0.0000221).apply(lambda x: round(x, 2)) * (
    #        fills_compare.side_x == "SELL"))
    #geskost2 = (difference * fills_compare.quantity + commissions) / (fills_compare.quantity * fills_compare.price)

    pdb.set_trace()

    print


