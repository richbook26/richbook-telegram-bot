import telebot
import requests
import os

# ===============================
# ENVIRONMENT VARIABLES
# ===============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")

ADMIN_ID = 8415879298
users = set()

bot = telebot.TeleBot(BOT_TOKEN)

# ===============================
# START COMMAND
# ===============================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    users.add(message.chat.id)

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

# ===============================
# HANDLE BUTTON CLICKS
# ===============================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.send_message(call.message.chat.id, "Enter amount in GHS (Example: 10)")

# ===============================
# HANDLE PAYMENT AMOUNT
# ===============================

@bot.message_handler(func=lambda message: message.text.isdigit())
def handle_payment(message):
    amount = int(message.text) * 100  # Convert to kobo/pesewas

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    data = {
        "email": f"user{message.chat.id}@richbook.com",
        "amount": amount
    }

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=data,
        headers=headers
    )

    result = response.json()

    if result.get("status"):
        payment_link = result["data"]["authorization_url"]
        bot.send_message(
            message.chat.id,
            f"💳 Click below to pay:\n{payment_link}"
        )
    else:
        bot.send_message(message.chat.id, "❌ Payment link failed. Try again.")

# ===============================
# ADMIN PANEL
# ===============================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return

    bot.send_message(
        message.chat.id,
        f"📊 Admin Panel\n\nTotal Users: {len(users)}\n\nSend:\n/broadcast Your message"
    )

# ===============================
# BROADCAST
# ===============================

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.chat.id != ADMIN_ID:
        return

    text = message.text.replace("/broadcast ", "")

    for user in users:
        try:
            bot.send_message(user, f"📢 Announcement:\n\n{text}")
        except:
            pass

    bot.send_message(message.chat.id, "✅ Broadcast sent.")

# ===============================
# RUN BOT
# ===============================

bot.infinity_polling()

import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    bot.infinity_polling()

threading.Thread(target=run_bot).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

bot.delete_webhook()
bot.infinity_polling()
