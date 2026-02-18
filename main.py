import os
import telebot
import requests
import threading
import psycopg2
from flask import Flask

# ===============================
# ENVIRONMENT VARIABLES
# ===============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMIN_ID = 8415879298

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ===============================
# DATABASE CONNECTION
# ===============================

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Create tables if not exist
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    network TEXT,
    bundle TEXT,
    phone TEXT,
    amount INTEGER,
    status TEXT DEFAULT 'pending'
);
""")

conn.commit()

# ===============================
# DATA PLANS (EDIT PRICES HERE)
# ===============================

DATA_PLANS = {
    "mtn_1gb": {"network": "MTN", "bundle": "1GB", "amount": 600},
    "mtn_2gb": {"network": "MTN", "bundle": "2GB", "amount": 1100},
    "airteltigo_1gb": {"network": "AirtelTigo", "bundle": "1GB", "amount": 500},
}

user_sessions = {}

# ===============================
# START COMMAND
# ===============================

@bot.message_handler(commands=['start'])
def start(message):
    cur.execute("INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING;", (message.chat.id,))
    conn.commit()

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("📶 MTN", callback_data="network_mtn"),
        telebot.types.InlineKeyboardButton("📱 AirtelTigo", callback_data="network_airteltigo")
    )

    bot.send_message(message.chat.id, "Choose Network:", reply_markup=markup)

# ===============================
# NETWORK SELECTION
# ===============================

@bot.callback_query_handler(func=lambda call: call.data.startswith("network_"))
def choose_bundle(call):
    network = call.data.split("_")[1]

    markup = telebot.types.InlineKeyboardMarkup()

    for key, plan in DATA_PLANS.items():
        if plan["network"].lower() == network:
            markup.add(
                telebot.types.InlineKeyboardButton(
                    f'{plan["bundle"]} - ₵{plan["amount"]/100}',
                    callback_data=f"plan_{key}"
                )
            )

    bot.send_message(call.message.chat.id, "Choose Bundle:", reply_markup=markup)

# ===============================
# PLAN SELECTION
# ===============================

@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_"))
def ask_phone(call):
    plan_key = call.data.split("_", 1)[1]
    user_sessions[call.message.chat.id] = {"plan": plan_key}

    bot.send_message(call.message.chat.id, "Enter phone number to receive data:")

# ===============================
# PHONE INPUT
# ===============================

@bot.message_handler(func=lambda message: message.chat.id in user_sessions)
def save_order(message):
    session = user_sessions[message.chat.id]
    plan = DATA_PLANS[session["plan"]]

    phone = message.text.strip()

    cur.execute("""
        INSERT INTO orders (user_id, network, bundle, phone, amount)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (message.chat.id, plan["network"], plan["bundle"], phone, plan["amount"]))

    order_id = cur.fetchone()[0]
    conn.commit()

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET}",
        "Content-Type": "application/json"
    }

    data = {
        "email": f"user{message.chat.id}@richbook.com",
        "amount": plan["amount"]
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
            f"""
🛒 Order Created

Network: {plan["network"]}
Bundle: {plan["bundle"]}
Number: {phone}
Amount: ₵{plan["amount"]/100}

Click below to pay:
{payment_link}
"""
        )

        bot.send_message(
            ADMIN_ID,
            f"""
🆕 New Order

Order ID: {order_id}
Network: {plan["network"]}
Bundle: {plan["bundle"]}
Number: {phone}
Amount: ₵{plan["amount"]/100}
Status: Pending
"""
        )
    else:
        bot.send_message(message.chat.id, "Payment initialization failed.")

    del user_sessions[message.chat.id]

# ===============================
# ADMIN PANEL
# ===============================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return

    cur.execute("SELECT COUNT(*) FROM users;")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders;")
    total_orders = cur.fetchone()[0]

    bot.send_message(
        message.chat.id,
        f"""
📊 Admin Panel

Total Users: {total_users}
Total Orders: {total_orders}
"""
    )

# ===============================
# FLASK SERVER
# ===============================

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    bot.delete_webhook()
    bot.infinity_polling()

threading.Thread(target=run_bot).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
