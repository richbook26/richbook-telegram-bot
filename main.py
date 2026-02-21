import os
import telebot
import sqlite3
import requests
import time
from flask import Flask
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")

GROUP_ID = -1003180892286

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ================= DATABASE =================

conn = sqlite3.connect("richbook.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ad_text TEXT,
    phone TEXT,
    ad_type TEXT,
    amount INTEGER,
    reference TEXT,
    status TEXT DEFAULT 'pending'
)
""")
conn.commit()

# ================= SESSION =================

sessions = {}

AD_PRICES = {
    "normal": 5,
    "pinned": 10,
    "spotlight": 20
}

# ================= START =================

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Welcome to RichBook Market Bot 🇬🇭\nUse /postad to post advert.")

# ================= POST AD FLOW =================

@bot.message_handler(commands=['postad'])
def post_ad(message):
    sessions[message.chat.id] = {}
    bot.send_message(message.chat.id, "📝 Send your ad text:")

@bot.message_handler(func=lambda m: m.chat.id in sessions and "ad_text" not in sessions[m.chat.id])
def get_text(message):
    sessions[message.chat.id]["ad_text"] = message.text
    bot.send_message(message.chat.id, "📱 Enter contact phone number:")

@bot.message_handler(func=lambda m: m.chat.id in sessions and "phone" not in sessions[m.chat.id])
def get_phone(message):
    sessions[message.chat.id]["phone"] = message.text

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("₵5 Normal", callback_data="ad_normal"),
        telebot.types.InlineKeyboardButton("₵10 Pinned", callback_data="ad_pinned"),
        telebot.types.InlineKeyboardButton("₵20 Spotlight", callback_data="ad_spotlight")
    )

    bot.send_message(message.chat.id, "💰 Choose ad type:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ad_"))
def payment(call):
    ad_type = call.data.split("_")[1]
    amount = AD_PRICES.get(ad_type)

    session = sessions.get(call.message.chat.id)
    if not session:
        return

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    data = {
        "email": f"user{call.from_user.id}@richbook.com",
        "amount": amount * 100
    }

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=data,
        headers=headers
    ).json()

    if response.get("status"):
        reference = response["data"]["reference"]

        cur.execute("""
        INSERT INTO ads (user_id, ad_text, phone, ad_type, amount, reference)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            call.from_user.id,
            session["ad_text"],
            session["phone"],
            ad_type,
            amount,
            reference
        ))
        conn.commit()

        bot.send_message(
            call.message.chat.id,
            f"✅ Complete payment below:\n{response['data']['authorization_url']}"
        )

        sessions.pop(call.message.chat.id, None)

# ================= PAYMENT CHECKER =================

def check_payments():
    while True:
        cur.execute("SELECT id, reference, ad_type, ad_text, phone FROM ads WHERE status='pending'")
        ads = cur.fetchall()

        for ad in ads:
            ad_id, reference, ad_type, ad_text, phone = ad

            headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}
            verify = requests.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers=headers
            ).json()

            if verify.get("data", {}).get("status") == "success":
                cur.execute("UPDATE ads SET status='paid' WHERE id=?", (ad_id,))
                conn.commit()

                tag = "✅ VERIFIED AD"
                if ad_type == "pinned":
                    tag = "📌 PINNED VERIFIED AD"
                elif ad_type == "spotlight":
                    tag = "🌟 SPOTLIGHT VERIFIED AD"

                msg = bot.send_message(
                    GROUP_ID,
                    f"<b>{tag}</b>\n\n{ad_text}\n\n📞 {phone}"
                )

                if ad_type in ["pinned", "spotlight"]:
                    bot.pin_chat_message(GROUP_ID, msg.message_id)

        time.sleep(20)

# ================= FLASK ROUTE =================

@app.route('/')
def home():
    return "RichBook Market Bot Running"

# ================= RUN =================

def run_bot():
    bot.delete_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == "__main__":
    Thread(target=run_bot).start()
    Thread(target=check_payments).start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
