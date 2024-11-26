import requests
import time
from datetime import datetime
from collections import defaultdict
from typing import Optional
import os
from collections import OrderedDict
import json
from functools import wraps

from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Telegram chat IDs that are authorized to use this bot
AUTHORIZED_CHAT_IDS = [
    # Add your chat ID here
]

# Telegram Bot API Token
TELEGRAM_API_TOKEN = "" # Add your bot token here

# Interval to check for new dates (in seconds)
LOOKUP_INTERVAL_SEC = 60 * 4 # 2 minutes

# Tesla model
MODEL = "m3"

# Condition
CONDITION = "used"

last_prices = OrderedDict()

def restricted(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in AUTHORIZED_CHAT_IDS:
            await update.message.reply_text(f"You (id {user_id}) are not authorized to use this bot.")
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


def request_page(vehicle_id: str):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    }

    params = {
        'titleStatus': CONDITION,
        'redirect': 'no',
    }

    response = requests.get(f'https://www.tesla.com/{MODEL}/order/{vehicle_id}', params=params, headers=headers)
    return response

def get_vehicle_price(text: str) -> Optional[int]:
    textIdx = text.find("InventoryPrice\":")
    if textIdx == -1:
        return None
    
    text = text[textIdx + len("InventoryPrice\":"):]
    text = text[:text.find(",")]
    return int(text)
    

def get_price(vehicle_id: str) -> Optional[int]:
    # send GET request to the DMV Appointments API
    response = request_page(vehicle_id)

    # check if response is valid
    if response.status_code != 200:
        print("Error: Invalid response (HTTP Status Code: " + str(response.status_code) + ")")
        print(response.text)
        return None

    # get the price from the response
    return get_vehicle_price(response.text)

def get_and_update_price(vehicle_id: str) -> Optional[bool]:
    # get the price of the vehicle
    price = get_price(vehicle_id)
    if price is None:
        return None

    # update the price of the vehicle
    if price != last_prices[vehicle_id]:
        print("Price of vehicle " + vehicle_id + " has changed to " + str(price) + ", was " + str(last_prices[vehicle_id]))
        last_prices[vehicle_id] = price
        return True

    return False

async def send_welcome(update, context):
    msg = "Let's hunt a Tesla! 🚗\n"
    msg += "Commands:\n"
    msg += "/add <VIN>: Add a vehicle to the list.\n"
    msg += "/remove <VIN>: Remove a vehicle from the list.\n"
    msg += "/prices: Get the prices of the vehicles in the list.\n"
    msg += "/id: Get your chat ID.\n"

    msg += "\nYour chat ID is " + str(update.message.chat_id) + "."
    await update.message.reply_text(msg)

@restricted
async def add_vehicle(update, context):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /add <VIN>")
        return
    
    if context.args[0] in last_prices:
        await update.message.reply_text(f"Vehicle {context.args[0]} is already in the list.")
        return

    vehicle_id = context.args[0]
    last_prices[vehicle_id] = None
    result = get_and_update_price(vehicle_id)
    if result is None:
        last_prices.pop(vehicle_id)
        await update.message.reply_text(f"Failed to add vehicle {vehicle_id} to the list.")
        return
    write_vins_to_file()
    await update.message.reply_text(f"Added vehicle {vehicle_id} to the list. Current price: ${last_prices[vehicle_id]}.")

@restricted
async def remove_vehicle(update, context):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /remove <VIN>")
        return

    vehicle_id = context.args[0]
    if vehicle_id not in last_prices:
        await update.message.reply_text(f"Vehicle {vehicle_id} is not in the list.")
        return

    last_prices.pop(vehicle_id)
    write_vins_to_file()
    await update.message.reply_text(f"Removed vehicle {vehicle_id} from the list.")

@restricted
async def send_prices(update, context):
    # check if chat ID is valid first
    if update.message.chat_id not in AUTHORIZED_CHAT_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")

    try:
        for v in last_prices:
            get_and_update_price(v)
        
        message = "Prices:\n" + "\n".join([f"{v}: {p}" for v, p in last_prices.items()])
        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text("Sorry, there was an exception.")
        await update.message.reply_text(str(e))
        print(e)
        return


async def callback_minute(context: ContextTypes.DEFAULT_TYPE):
    texts_to_send = []
    
    try:
        for v in last_prices:
            old_price = last_prices[v]
            if get_and_update_price(v):
                texts_to_send.append(f"{v}: {old_price} -> {last_prices[v]}")

    except Exception as e:
        print("Error: There was an exception:", e)
        texts_to_send.append("Error: There was an exception.")
        texts_to_send.append(str(e))
        return        
    
    if texts_to_send:
        for chat_id in AUTHORIZED_CHAT_IDS:
            await context.bot.send_message(chat_id=chat_id, text="Price change detected!\n" + "\n".join(texts_to_send))        

def read_vins_from_file():
    global last_prices
    if not os.path.exists("vehicles.json"):
        with open("vehicles.json", "w") as f:
            json.dump({}, f)
        return
    
    with open("vehicles.json", "r") as f:
        last_prices = json.load(f)

def write_vins_to_file():
    with open("vehicles.json", "w") as f:
        json.dump(last_prices, f)

if __name__ == "__main__":
    if not TELEGRAM_API_TOKEN:
        print("Error: TELEGRAM_API_TOKEN is not set.")
        exit(1)
    
        
    read_vins_from_file()
    app = ApplicationBuilder().token(TELEGRAM_API_TOKEN).build()

    app.add_handler(CommandHandler("help", send_welcome))
    app.add_handler(CommandHandler("start", send_welcome))
    app.add_handler(CommandHandler("add", add_vehicle))
    app.add_handler(CommandHandler("remove", remove_vehicle))
    app.add_handler(CommandHandler("prices", send_prices))

    job_queue = app.job_queue
    job_minute = job_queue.run_repeating(callback_minute, interval=LOOKUP_INTERVAL_SEC, first=5)
    
    app.run_polling()
