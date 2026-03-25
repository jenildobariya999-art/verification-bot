from flask import Flask, request, jsonify
from telebot import TeleBot, types
import hashlib, json, os
import threading

# 🔑 TOKEN (Render env variable)
API_TOKEN = os.environ.get("API_TOKEN")

if not API_TOKEN:
    print("❌ ERROR: API_TOKEN missing")
    exit()

# 🌐 DOMAIN (temporary, change later)
DOMAIN = os.environ.get("DOMAIN", "https://example.com")

bot = TeleBot(API_TOKEN)
app = Flask(__name__)

DB_FILE = "devices.json"

# create file if not exists
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump({}, f)

# load data
with open(DB_FILE, "r") as f:
    devices = json.load(f)

def save():
    with open(DB_FILE, "w") as f:
        json.dump(devices, f)

def make_hash(data):
    return hashlib.md5(data.encode()).hexdigest()

# START COMMAND
@bot.message_handler(commands=['start'])
def start(msg):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton(
        "🔐 Verify Device",
        web_app=types.WebAppInfo(DOMAIN)
    )
    markup.add(btn)

    bot.send_message(msg.chat.id, "Click to verify device", reply_markup=markup)

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

        if device_id in devices:
            return jsonify({"status": "failed"})

        devices[device_id] = user_id
        save()

        bot.send_message(user_id, "✅ Verified Successfully!")

        return jsonify({"status": "success"})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error"})

# RUN BOT (THREAD)
def run_bot():
    print("🤖 Bot Started")
    bot.infinity_polling()

threading.Thread(target=run_bot).start()

# RUN SERVER
port = int(os.environ.get("PORT", 5000))
print("🌐 Server Running on port", port)

app.run(host="0.0.0.0", port=port)
