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

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    application.run_polling()
