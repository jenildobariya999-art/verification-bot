from flask import Flask, request, jsonify
from telebot import TeleBot, types
import hashlib, json, os, threading

# 🔑 CONFIG
API_TOKEN = os.environ.get("8274297339:AAGUQjlgSRPct_u9JdBIaJJYs3AjhbyQ_q0")  # Render env variable
DOMAIN = "https://yourapp.onrender.com"  # change after deploy

bot = TeleBot(API_TOKEN)
app = Flask(__name__)

DB_FILE = "devices.json"

# 📦 Load DB
if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        devices = json.load(f)
else:
    devices = {}

# 💾 Save DB
def save():
    with open(DB_FILE, "w") as f:
        json.dump(devices, f)

# 🔐 Hash
def make_hash(data):
    return hashlib.md5(data.encode()).hexdigest()

# 🚀 START
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

# 🌐 VERIFY API
@app.route("/verify", methods=["POST"])
def verify():
    try:
        data = request.json

        user_id = str(data.get("user_id"))
        device_raw = data.get("device")

        if not user_id or not device_raw:
            return jsonify({"status": "error"})

        device_id = make_hash(device_raw)

        # ❌ already used
        if device_id in devices:
            return jsonify({
                "status": "failed",
                "message": "Device already used"
            })

        # ✅ new device
        devices[device_id] = user_id
        save()

        # 📩 bot message
        try:
            bot.send_message(
                user_id,
                "✅ Verified Successfully!\n\n🎉 Now you can use the bot."
            )
        except:
            pass

        return jsonify({
            "status": "success",
            "message": "Device verified"
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error"})

# 🤖 RUN BOT + SERVER
def run_bot():
    bot.infinity_polling()

threading.Thread(target=run_bot).start()

# 🔥 Render compatible port
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)