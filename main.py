import os
import telebot
import psycopg2
import requests
import threading
import time
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")

GROUP_ID = -1003180892286

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ================= DATABASE =================

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    verified BOOLEAN DEFAULT FALSE
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS ads (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    ad_text TEXT,
    phone TEXT,
    ad_type TEXT,
    amount INTEGER,
    reference TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()

# ================= USER SESSIONS =================

sessions = {}

AD_PRICES = {
    "normal": 500,
    "pinned": 1000,
    "spotlight": 2000
}

# ================= MEMBER JOIN VERIFICATION =================

@bot.message_handler(content_types=['new_chat_members'])
def verify_user(message):
    for member in message.new_chat_members:
        bot.restrict_chat_member(
            message.chat.id,
            member.id,
            can_send_messages=False
        )

        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton(
                "✅ Verify",
                callback_data=f"verify_{member.id}"
            )
        )

        bot.send_message(
            message.chat.id,
            f"Welcome {member.first_name} 👋\nClick verify to access group.",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_"))
def handle_verify(call):
    user_id = int(call.data.split("_")[1])

    if call.from_user.id == user_id:
        bot.restrict_chat_member(
            call.message.chat.id,
            user_id,
            can_send_messages=True
        )

        cur.execute(
            "INSERT INTO users (user_id, verified) VALUES (%s, TRUE) ON CONFLICT DO NOTHING;",
            (user_id,)
        )
        conn.commit()

        bot.answer_callback_query(call.id, "Verified!")
        bot.delete_message(call.message.chat.id, call.message.message_id)

# ================= POST AD FLOW =================

@bot.message_handler(commands=['postad'])
def start_ad(message):
    sessions[message.chat.id] = {}
    bot.send_message(message.chat.id, "Send your ad text:")

@bot.message_handler(func=lambda m: m.chat.id in sessions and "ad_text" not in sessions[m.chat.id])
def get_ad_text(message):
    sessions[message.chat.id]["ad_text"] = message.text
    bot.send_message(message.chat.id, "Enter contact phone number:")

@bot.message_handler(func=lambda m: m.chat.id in sessions and "phone" not in sessions[m.chat.id])
def get_phone(message):
    sessions[message.chat.id]["phone"] = message.text

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("₵5 Normal", callback_data="ad_normal"),
        telebot.types.InlineKeyboardButton("₵10 Pinned", callback_data="ad_pinned"),
        telebot.types.InlineKeyboardButton("₵20 Spotlight", callback_data="ad_spotlight")
    )

    bot.send_message(message.chat.id, "Choose ad type:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ad_"))
def process_payment(call):
    ad_type = call.data.split("_")[1]
    amount = AD_PRICES[ad_type]

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
    )

    result = response.json()

    if result.get("status"):
        reference = result["data"]["reference"]

        cur.execute("""
        INSERT INTO ads (user_id, ad_text, phone, ad_type, amount, reference)
        VALUES (%s, %s, %s, %s, %s, %s);
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
            f"Complete payment:\n{result['data']['authorization_url']}"
        )

        del sessions[call.message.chat.id]

# ================= PAYMENT VERIFICATION =================

def check_payments():
    while True:
        cur.execute("SELECT id, reference, ad_type, ad_text, phone FROM ads WHERE status='pending';")
        pending_ads = cur.fetchall()

        for ad in pending_ads:
            ad_id, reference, ad_type, ad_text, phone = ad

            headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}
            res = requests.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers=headers
            ).json()

            if res.get("data", {}).get("status") == "success":
                cur.execute("UPDATE ads SET status='paid' WHERE id=%s;", (ad_id,))
                conn.commit()

                tag = "✅ VERIFIED AD"
                if ad_type == "spotlight":
                    tag = "🌟 SPOTLIGHT VERIFIED AD"
                elif ad_type == "pinned":
                    tag = "📌 PINNED VERIFIED AD"

                msg = bot.send_message(
                    GROUP_ID,
                    f"{tag}\n\n{ad_text}\n\n📱 Contact: {phone}"
                )

                if ad_type in ["pinned", "spotlight"]:
                    bot.pin_chat_message(GROUP_ID, msg.message_id)

        time.sleep(30)

# ================= START BOT =================

@app.route('/')
def home():
    return "RichBook Market Bot Running"

def run_bot():
    bot.infinity_polling()

threading.Thread(target=run_bot).start()
threading.Thread(target=check_payments).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
