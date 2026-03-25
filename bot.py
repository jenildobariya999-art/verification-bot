from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import TeleBot, types
import hashlib, json, os, threading

# CONFIG
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

# create files if not exist
for file in [DB_FILE, USER_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)

# load data
with open(DB_FILE, "r") as f:
    devices = json.load(f)

with open(USER_FILE, "r") as f:
    users = json.load(f)

def save_devices():
    with open(DB_FILE, "w") as f:
        json.dump(devices, f)

def save_users():
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

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

    # ✅ already verified
    if user_id in users:
        bot.send_message(
            msg.chat.id,
            "✅ You are already verified!\n\nWelcome back 🎉"
        )
        return

    # ❌ not verified
    markup = types.InlineKeyboardMarkup()

    btn = types.InlineKeyboardButton(
        "🔐 Verify Device",
        web_app=types.WebAppInfo(DOMAIN)
    )

    markup.add(btn)

    bot.send_message(
        msg.chat.id,
        "🛡 Please verify your device to continue",
        reply_markup=markup
    )

# VERIFY API
@app.route("/verify", methods=["POST"])
def verify():
    try:
        data = request.json

        user_id = str(data.get("user_id"))
        device = data.get("device")

        if not user_id or not device:
            return jsonify({"status": "error"})

        device_id = make_hash(device)

        print(f"USER: {user_id} | DEVICE: {device_id}")

        # ❌ already used device
        if device_id in devices:
            bot.send_message(
                user_id,
                "❌ Verification Failed\n\nDevice already used."
            )
            return jsonify({
                "status": "failed",
                "message": "Device already used"
            })

        # ✅ new device
        devices[device_id] = user_id
        save_devices()

        # ✅ mark user verified
        users[user_id] = True
        save_users()

        bot.send_message(
            user_id,
            "✅ Verified Successfully!\n\n🎉 You can now use the bot."
        )

        return jsonify({
            "status": "success",
            "message": "Verified"
        })

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
print("🌐 Server Running")

app.run(host="0.0.0.0", port=port)
