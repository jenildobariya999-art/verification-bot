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

# ensure file exists
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump({}, f)

with open(DB_FILE, "r") as f:
    devices = json.load(f)

def save():
    with open(DB_FILE, "w") as f:
        json.dump(devices, f)

def make_hash(data):
    return hashlib.md5(data.encode()).hexdigest()

# HOME
@app.route("/")
def home():
    return "Bot Running ✅"

# START
@bot.message_handler(commands=['start'])
def start(msg):
    markup = types.InlineKeyboardMarkup()

    btn = types.InlineKeyboardButton(
        "🔐 Verify Device",
        web_app=types.WebAppInfo(DOMAIN)
    )

    markup.add(btn)

    bot.send_message(
        msg.chat.id,
        "🛡 Click below to verify your device",
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

        # ❌ already used
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
        save()

        bot.send_message(
            user_id,
            "✅ Verified Successfully!\n\n🎉 You can now continue."
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
