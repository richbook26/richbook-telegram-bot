import os
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

dispatcher = Dispatcher(bot, None, workers=0)

def start(update, context):
    keyboard = [
        [InlineKeyboardButton("📶 Buy MTN Data", callback_data="mtn")],
        [InlineKeyboardButton("📱 Buy AirtelTigo Data", callback_data="airteltigo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "👋 Welcome to RichBook Data Bot 🇬🇭\n\nChoose network:",
        reply_markup=reply_markup
    )

def button(update, context):
    query = update.callback_query
    query.answer()

    if query.data == "mtn":
        query.edit_message_text(
            "📶 MTN DATA\n\n1GB - 10gh\n2GB - 18gh\n\nSend amount (10 or 18)"
        )

def handle_message(update, context):
    text = update.message.text
    chat_id = update.message.chat_id

    if text.isdigit():
        amount = int(text)
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

        update.message.reply_text(f"Click below to pay:\n{payment_link}")

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    bot.set_webhook(f"https://richbook-telegram-bot.onrender.com/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
