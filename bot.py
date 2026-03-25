from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import TeleBot, types
import hashlib, json, os, threading

API_TOKEN = os.environ.get("API_TOKEN")
DOMAIN = "https://verification-beta-five.vercel.app"

if not API_TOKEN:
    print("❌ API_TOKEN missing")
    exit()

bot = TeleBot(API_TOKEN)
bot.remove_webhook()

app = Flask(__name__)
CORS(app)

DB_FILE = "devices.json"
USER_FILE = "users.json"
FAILED_FILE = "failed.json"

# create files
for file in [DB_FILE, USER_FILE, FAILED_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

# load data
devices = json.load(open(DB_FILE))
users = json.load(open(USER_FILE))
failed = json.load(open(FAILED_FILE))

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

def make_hash(data):
    return hashlib.md5(data.encode()).hexdigest()

# HOME
@app.route("/")
def home():
    return "Bot Running ✅"

# START
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = str(msg.chat.id)

    # ✅ VERIFIED USER
    if user_id in users:
        bot.send_message(
            msg.chat.id,
            "✅ You are already verified!\n\nWelcome back 🎉"
        )
        return

    # ❌ FAILED USER
    if user_id in failed:
        bot.send_message(
            msg.chat.id,
            "⚠️ Device already used.\n\nYou can still use the bot."
        )
        return

    # 🆕 NEW USER
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(
        "🔐 Verify Device",
        web_app=types.WebAppInfo(DOMAIN)
    )
    markup.add(btn)

    bot.send_message(
        msg.chat.id,
        "🛡 Please verify your device",
        reply_markup=markup
    )

# VERIFY
@app.route("/verify", methods=["POST"])
def verify():
    try:
        data = request.json
        user_id = str(data.get("user_id"))
        device = data.get("device")

        if not user_id or not device:
            return jsonify({"status": "error"})

        device_id = make_hash(device)

        print(f"{user_id} | {device_id}")

        # ❌ SAME DEVICE
        if device_id in devices:
            failed[user_id] = True
            save(FAILED_FILE, failed)

            bot.send_message(
                user_id,
                "⚠️ Verification Failed\n\nDevice already used.\nYou can still use bot."
            )

            return jsonify({"status": "failed"})

        # ✅ NEW DEVICE
        devices[device_id] = user_id
        save(DB_FILE, devices)

        users[user_id] = True
        save(USER_FILE, users)

        bot.send_message(
            user_id,
            "✅ Verified Successfully!\n\n🎉 Full access unlocked."
        )

        return jsonify({"status": "success"})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error"})

# RUN BOT
def run_bot():
    print("🤖 Bot Started")
    bot.infinity_polling()

threading.Thread(target=run_bot).start()

# RUN SERVER
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
