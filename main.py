import os
import requests
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")

app = Flask(__name__)

application = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📶 Buy MTN Data", callback_data="mtn")],
        [InlineKeyboardButton("📱 Buy AirtelTigo Data", callback_data="airteltigo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Welcome to RichBook Data Bot 🇬🇭\n\nChoose network:",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "mtn":
        await query.edit_message_text(
            "📶 MTN DATA\n\n1GB - 10gh\n2GB - 18gh\n\nSend amount (10 or 18)"
        )

def create_payment_link(amount, chat_id):
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
    return response.json()["data"]["authorization_url"]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    if text.isdigit():
        amount = int(text)
        payment_link = create_payment_link(amount, chat_id)
        await update.message.reply_text(
            f"Click below to pay:\n{payment_link}"
        )

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    import asyncio

    asyncio.get_event_loop().run_until_complete(
        application.bot.set_webhook(
            url=f"https://richbook-telegram-bot.onrender.com/{BOT_TOKEN}"
        )
    )

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
