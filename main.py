import os
import telebot
import requests
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("📶 Buy MTN Data", callback_data="mtn"),
        telebot.types.InlineKeyboardButton("📱 Buy AirtelTigo Data", callback_data="airteltigo")
    )
    bot.send_message(
        message.chat.id,
        "👋 Welcome to RichBook Data Bot 🇬🇭\n\nChoose network:",
        reply_markup=markup
    )

# Button handler
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "mtn":
        bot.send_message(
            call.message.chat.id,
            "📶 MTN DATA\n\n1GB - 10gh\n2GB - 18gh\n\nSend amount (10 or 18)"
        )

# Handle amount input
@bot.message_handler(func=lambda message: message.text.isdigit())
def handle_payment(message):
    amount = int(message.text)
    chat_id = message.chat.id

    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }
    data = {
        "email": f"user{chat_id}@richbook.com",
        "amount": amount * 100,
        "callback_url": "https://google.com"
    }

    response = requests.post(url, json=data, headers=headers)
    payment_link = response.json()["data"]["authorization_url"]

    bot.send_message(chat_id, f"Click below to pay:\n{payment_link}")

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://richbook-telegram-bot.onrender.com/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
