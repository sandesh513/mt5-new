import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ==================================================
# SETTINGS
# ==================================================
LOT_SIZE = 0.01

RR_RATIO = 1.0

TIMEFRAME_ENTRY = mt5.TIMEFRAME_M5
TIMEFRAME_TREND = mt5.TIMEFRAME_M15

LOOKBACK_SR = 20
SCAN_INTERVAL = 20

MAGIC = 999999
DEVIATION = 20

SL_GOLD = 200
SL_SILVER = 300

MAX_SPREAD_GOLD = 35
MAX_SPREAD_SILVER = 50

# ==================================================
# CONNECT MT5
# ==================================================

if not mt5.initialize():
    print("MT5 INIT FAILED")
    quit()

print("MT5 CONNECTED")

# ==================================================
# SYMBOL DETECTION
# ==================================================

symbols = [s.name for s in mt5.symbols_get()]

gold_symbol = None
silver_symbol = None

for s in symbols:

    up = s.upper()

    if gold_symbol is None:
        if "XAU" in up or "GOLD" in up:
            gold_symbol = s

    if silver_symbol is None:
        if "XAG" in up or "SILVER" in up or "HEXAGON" in up:
            silver_symbol = s

SYMBOLS = []

if gold_symbol:
    SYMBOLS.append(gold_symbol)

if silver_symbol:
    SYMBOLS.append(silver_symbol)

print("GOLD :", gold_symbol)
print("SILVER:", silver_symbol)

if len(SYMBOLS) == 0:
    print("NO SYMBOLS FOUND")
    quit()

# ==================================================
# DATA
# ==================================================

def get_data(symbol, timeframe, bars=200):

    rates = mt5.copy_rates_from_pos(
        symbol,
        timeframe,
        0,
        bars
    )

    if rates is None:
        return None

    df = pd.DataFrame(rates)

    df['time'] = pd.to_datetime(
        df['time'],
        unit='s'
    )

    return df

# ==================================================
# SUPPORT / RESISTANCE
# ==================================================

def get_support_resistance(df):

    support = (
        df['low']
        .rolling(LOOKBACK_SR)
        .min()
        .iloc[-2]
    )

    resistance = (
        df['high']
        .rolling(LOOKBACK_SR)
        .max()
        .iloc[-2]
    )

    return support, resistance

# ==================================================
# TRENDLINE DIRECTION
# ==================================================

def get_trend(symbol):

    df = get_data(
        symbol,
        TIMEFRAME_TREND,
        100
    )

    if df is None:
        return None

    highs = df['high'].iloc[-10:]
    lows = df['low'].iloc[-10:]

    # simple trendline approximation
    high_slope = np.polyfit(
        range(len(highs)),
        highs,
        1
    )[0]

    low_slope = np.polyfit(
        range(len(lows)),
        lows,
        1
    )[0]

    if high_slope > 0 and low_slope > 0:
        return "BUY"

    elif high_slope < 0 and low_slope < 0:
        return "SELL"

    return None

# ==================================================
# SIGNAL
# ==================================================

def get_signal(symbol):

    trend = get_trend(symbol)

    if trend is None:
        return None

    df = get_data(
        symbol,
        TIMEFRAME_ENTRY,
        100
    )

    if df is None:
        return None

    support, resistance = get_support_resistance(df)

    last = df.iloc[-2]
    prev = df.iloc[-3]

    # BUY BREAKOUT
    if trend == "BUY":

        breakout = (
            prev['close'] <= resistance
            and last['close'] > resistance
        )

        bullish_close = (
            last['close'] > last['open']
        )

        if breakout and bullish_close:
            return "BUY"

    # SELL BREAKDOWN
    if trend == "SELL":

        breakdown = (
            prev['close'] >= support
            and last['close'] < support
        )

        bearish_close = (
            last['close'] < last['open']
        )

        if breakdown and bearish_close:
            return "SELL"

    return None

# ==================================================
# POSITION CHECK
# ==================================================

def has_position(symbol):

    positions = mt5.positions_get(
        symbol=symbol
    )

    return (
        positions is not None
        and len(positions) > 0
    )

# ==================================================
# TRADE
# ==================================================

def place_trade(symbol, signal):

    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)

    if tick is None or info is None:
        return

    point = info.point

    spread = (
        tick.ask - tick.bid
    ) / point

    # GOLD
    if "XAU" in symbol.upper() or "GOLD" in symbol.upper():

        if spread > MAX_SPREAD_GOLD:
            print(symbol, "SPREAD TOO HIGH")
            return

        sl_points = SL_GOLD

    # SILVER
    else:

        if spread > MAX_SPREAD_SILVER:
            print(symbol, "SPREAD TOO HIGH")
            return

        sl_points = SL_SILVER

    tp_points = sl_points * RR_RATIO

    if signal =="BUY":

        price = tick.ask
        sl = price - (sl_points * point)
        tp = price + (tp_points * point)

        order_type = mt5.ORDER_TYPE_BUY

    else:

        price = tick.bid
        sl = price + (sl_points * point)
        tp = price - (tp_points * point)

        order_type = mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": LOT_SIZE,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": DEVIATION,
        "magic": MAGIC,
        "comment": "SR Trendline Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:

        print("\nTRADE EXECUTED")
        print("SYMBOL :", symbol)
        print("TYPE   :", signal)
        print("ENTRY  :", price)
        print("SL     :", sl)
        print("TP     :", tp)
        print("TIME   :", datetime.now())

    else:
        print("ORDER FAILED")
        print(result)

# ==================================================
# MAIN LOOP
# ==================================================

print("\nBOT STARTED")

while True:

    try:

        for symbol in SYMBOLS:

            print(f"\nSCANNING {symbol}")

            if has_position(symbol):
                print("POSITION OPEN")
                continue

            signal = get_signal(symbol)

            if signal:

                print(signal, "SIGNAL FOUND")

                place_trade(
                    symbol,
                    signal
                )

            else:
                print("NO SIGNAL")

        time.sleep(SCAN_INTERVAL)

    except Exception as e:

        print("ERROR:", e)
        time.sleep(5)