# Tesla Inventory Monitor Bot

> [!TIP]
> If you are to purchase a new Tesla vehicle, please consider using my referral code [here](https://ts.la/yesheng394959) to get up to $2,000 off!

A telegram bot to monitor price changes of vehicles in Tesla's inventory.

1. First, create a bot using [BotFather](https://t.me/BotFather) and obtain the token. Fill your token in `bot.py`.
    ```python
    TELEGRAM_API_TOKEN = "..."
    ```
2. You will also need to add your own chat id in `bot.py` to receive notifications, which can be obtained by sending `/id` to [userinfobot](https://t.me/userinfobot).
    ```python
    AUTHORIZED_CHAT_IDS = [
        # Add your chat ID here
        "..."
    ]
    ```
3. You can change the model and condition by setting `MODEL` and `CONDITION`.
   ```python
    MODEL = "m3"
    CONDITION = "new"
    ```
4. Install dependencies by running `pip install -r requirements.txt`,
5. and then simply `python bot.py`.

For usage of the bot, send `/start` to the bot and follow the instructions.
