import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime, time as dt_time

# ==========================================
# TELEGRAM
# ==========================================
BOT_TOKEN = "8433212155:AAFKSFzLC193PIhGmdPzks1elppScji1ofY"
CHAT_ID = "8866037210"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        print("Telegram:", message)
    except Exception as e:
        print("Telegram error:", e)


# ==========================================
# STRATEGY SETTINGS
# ==========================================
SYMBOL = "^NSEI"
INTERVAL = "15m"

TARGET = 35
SL = 60

REFERENCE_TIME = "09:45"

# ==========================================
# DAILY VARIABLES
# ==========================================
current_date = None

reference_high = None
reference_low = None

breakout_time = None
direction = None

entry_price = None
target_price = None
sl_price = None

trade_active = False
trade_completed = False


# ==========================================
# DOWNLOAD DATA
# ==========================================
def get_data():

    data = yf.download(
        SYMBOL,
        period="1d",
        interval=INTERVAL,
        progress=False,
        auto_adjust=False
    )

    if data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data.index = pd.to_datetime(data.index)

    return data


# ==========================================
# RESET NEW DAY
# ==========================================
def reset_day(new_date):

    global current_date
    global reference_high
    global reference_low
    global breakout_time
    global direction
    global entry_price
    global target_price
    global sl_price
    global trade_active
    global trade_completed

    current_date = new_date

    reference_high = None
    reference_low = None

    breakout_time = None
    direction = None

    entry_price = None
    target_price = None
    sl_price = None

    trade_active = False
    trade_completed = False

    print()
    print("====================================")
    print("NEW TRADING DAY:", new_date)
    print("====================================")


# ==========================================
# MAIN LOOP
# ==========================================
print("====================================")
print(" NIFTY 50 PAPER TRADING ALGO")
print("====================================")
print("Target :", TARGET)
print("SL     :", SL)
print("Reference Candle: 09:45 - 10:00")
print("Above High = PE")
print("Below Low  = CE")
print()


while True:

    try:

        data = get_data()

        if data is None:
            print("No data. Retrying...")
            time.sleep(60)
            continue

        # --------------------------------------
        # Remove current incomplete candle
        # --------------------------------------
        now = datetime.now()

        completed = []

        for index in data.index:

            candle_time = index.to_pydatetime()

            if candle_time.replace(tzinfo=None) < now:
                completed.append(index)

        if not completed:
            time.sleep(60)
            continue

        data = data.loc[completed]

        today = data.index[-1].date()

        # --------------------------------------
        # NEW DAY
        # --------------------------------------
        if current_date != today:
            reset_day(today)

        # --------------------------------------
        # 1. FIND 09:45 REFERENCE CANDLE
        # --------------------------------------
        if reference_high is None:

            ref = data[
                (data.index.date == today) &
                (data.index.strftime("%H:%M") == REFERENCE_TIME)
            ]

            if not ref.empty:

                candle = ref.iloc[0]

                reference_high = float(candle["High"])
                reference_low = float(candle["Low"])

                message = (
                    "📌 NIFTY REFERENCE CANDLE\n\n"
                    "Time: 09:45 - 10:00\n"
                    f"High: {reference_high:.2f}\n"
                    f"Low: {reference_low:.2f}"
                )

                print(message)
                send_telegram(message)

        # --------------------------------------
        # 2. FIND BREAKOUT
        # --------------------------------------
        if (
            reference_high is not None
            and breakout_time is None
            and not trade_completed
        ):

            after_reference = data[
                (data.index.date == today) &
                (data.index.strftime("%H:%M") > REFERENCE_TIME)
            ]

            for index, candle in after_reference.iterrows():

                close_price = float(candle["Close"])

                # ABOVE HIGH = PE
                if close_price > reference_high:

                    breakout_time = index
                    direction = "PE"

                    message = (
                        "🔴 PAPER SIGNAL\n\n"
                        "Breakout: ABOVE Reference High\n"
                        "Direction: PE\n\n"
                        f"Breakout Candle: {index.strftime('%H:%M')}\n"
                        f"Close: {close_price:.2f}\n"
                        f"Reference High: {reference_high:.2f}\n\n"
                        "Entry = NEXT 15M Candle OPEN"
                    )

                    print(message)
                    send_telegram(message)

                    break

                # BELOW LOW = CE
                elif close_price < reference_low:

                    breakout_time = index
                    direction = "CE"

                    message = (
                        "🟢 PAPER SIGNAL\n\n"
                        "Breakout: BELOW Reference Low\n"
                        "Direction: CE\n\n"
                        f"Breakout Candle: {index.strftime('%H:%M')}\n"
                        f"Close: {close_price:.2f}\n"
                        f"Reference Low: {reference_low:.2f}\n\n"
                        "Entry = NEXT 15M Candle OPEN"
                    )

                    print(message)
                    send_telegram(message)

                    break

        # --------------------------------------
        # 3. NEXT CANDLE OPEN = ENTRY
        # --------------------------------------
        if (
            breakout_time is not None
            and entry_price is None
        ):

            next_candles = data[
                data.index > breakout_time
            ]

            if not next_candles.empty:

                entry_candle = next_candles.iloc[0]
                entry_time = next_candles.index[0]

                entry_price = float(entry_candle["Open"])

                if direction == "CE":

                    target_price = entry_price + TARGET
                    sl_price = entry_price - SL

                else:

                    target_price = entry_price - TARGET
                    sl_price = entry_price + SL

                trade_active = True

                message = (
                    "🚀 PAPER ENTRY\n\n"
                    f"Direction: {direction}\n"
                    f"Entry Time: {entry_time.strftime('%H:%M')}\n"
                    f"Entry: {entry_price:.2f}\n"
                    f"Target: {target_price:.2f}\n"
                    f"SL: {sl_price:.2f}\n\n"
                    "⚠️ PAPER TRADE ONLY"
                )

                print(message)
                send_telegram(message)

        # --------------------------------------
        # 4. MONITOR TARGET / SL
        # --------------------------------------
        if trade_active and not trade_completed:

            trade_candles = data[
                data.index >= breakout_time
            ]

            # Start checking from ENTRY candle
            if entry_price is not None:

                for index, candle in trade_candles.iterrows():

                    if index <= breakout_time:
                        continue

                    high = float(candle["High"])
                    low = float(candle["Low"])

                    # Conservative rule:
                    # If both target and SL are touched
                    # in same candle -> SL first

                    if direction == "CE":

                        if low <= sl_price:

                            message = (
                                "🛑 STOP LOSS HIT\n\n"
                                f"Direction: {direction}\n"
                                f"Entry: {entry_price:.2f}\n"
                                f"SL: {sl_price:.2f}\n"
                                f"Time: {index.strftime('%H:%M')}"
                            )

                            print(message)
                            send_telegram(message)

                            trade_completed = True
                            trade_active = False
                            break

                        elif high >= target_price:

                            message = (
                                "🎯 TARGET HIT\n\n"
                                f"Direction: {direction}\n"
                                f"Entry: {entry_price:.2f}\n"
                                f"Target: {target_price:.2f}\n"
                                f"Time: {index.strftime('%H:%M')}"
                            )

                            print(message)
                            send_telegram(message)

                            trade_completed = True
                            trade_active = False
                            break

                    else:  # PE

                        if high >= sl_price:

                            message = (
                                "🛑 STOP LOSS HIT\n\n"
                                f"Direction: {direction}\n"
                                f"Entry: {entry_price:.2f}\n"
                                f"SL: {sl_price:.2f}\n"
                                f"Time: {index.strftime('%H:%M')}"
                            )

                            print(message)
                            send_telegram(message)

                            trade_completed = True
                            trade_active = False
                            break

                        elif low <= target_price:

                            message = (
                                "🎯 TARGET HIT\n\n"
                                f"Direction: {direction}\n"
                                f"Entry: {entry_price:.2f}\n"
                                f"Target: {target_price:.2f}\n"
                                f"Time: {index.strftime('%H:%M')}"
                            )

                            print(message)
                            send_telegram(message)

                            trade_completed = True
                            trade_active = False
                            break

        # --------------------------------------
        # STATUS
        # --------------------------------------
        print(
            datetime.now().strftime("%H:%M:%S"),
            "| Data OK"
        )

        time.sleep(60)

    except KeyboardInterrupt:

        print()
        print("Paper Algo stopped manually.")
        break

    except Exception as e:

        print("Error:", e)
        time.sleep(60)