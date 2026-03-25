from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from telebot import TeleBot, types
import hashlib, json, os, threading

# CONFIG
API_TOKEN = os.environ.get("API_TOKEN")
DOMAIN = "https://verification-beta-five.vercel.app"

ADMIN_PASSWORD = "admin123"
RESET_KEY = "MY_SECRET_123"

if not API_TOKEN:
    print("❌ API_TOKEN missing")
    exit()

bot = TeleBot(API_TOKEN)
bot.remove_webhook()

app = Flask(__name__)
CORS(app)

# FILES
FILES = {
    "devices": "devices.json",
    "users": "users.json",
    "failed": "failed.json",
    "ips": "ips.json",
    "refs": "referrals.json"
}

# create files if missing
for f in FILES.values():
    if not os.path.exists(f):
        with open(f, "w") as file:
            json.dump({}, file)

# load data
devices = json.load(open(FILES["devices"]))
users = json.load(open(FILES["users"]))
failed = json.load(open(FILES["failed"]))
ips = json.load(open(FILES["ips"]))
referrals = json.load(open(FILES["refs"]))

def save(name, data):
    with open(FILES[name], "w") as f:
        json.dump(data, f)

def make_hash(data):
    return hashlib.md5(data.encode()).hexdigest()

def get_ip(req):
    if req.headers.get("X-Forwarded-For"):
        return req.headers.get("X-Forwarded-For").split(",")[0]
    return req.remote_addr

# HOME
@app.route("/")
def home():
    return "Bot Running ✅"

# START
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = str(msg.chat.id)
    args = msg.text.split()

    # 🎯 REFERRAL
    if len(args) > 1:
        ref = args[1]
        if ref != user_id and user_id not in referrals:
            referrals[user_id] = ref
            referrals[ref + "_count"] = referrals.get(ref + "_count", 0) + 1
            save("refs", referrals)
            bot.send_message(ref, "🎉 New referral joined!")

    # ✅ VERIFIED
    if user_id in users:
        bot.send_message(msg.chat.id, "✅ You are already verified!")
        return

    # ❌ FAILED
    if user_id in failed:
        bot.send_message(msg.chat.id, "⚠️ Device/IP already used.\nYou can still use bot.")
        return

    # 🆕 NEW
    # Inline button for web verification
    markup_inline = types.InlineKeyboardMarkup()
    btn_verify = types.InlineKeyboardButton(
        "🔐 Verify Device",
        web_app=types.WebAppInfo(DOMAIN)
    )
    markup_inline.add(btn_verify)

    # Reply keyboard for other actions
    markup_reply = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_ref = types.KeyboardButton("👥 Show Referrals")
    markup_reply.add(btn_ref)

    # Send message with both keyboards
    bot.send_message(
        msg.chat.id,
        "🛡 Please verify your device",
        reply_markup=markup_inline
    )

    bot.send_message(
        msg.chat.id,
        "Select an option below 👇",
        reply_markup=markup_reply
    )

# HANDLE REPLY KEYBOARD BUTTON
@bot.message_handler(func=lambda message: True)
def handle_buttons(msg):
    if msg.text == "👥 Show Referrals":
        user_id = str(msg.chat.id)
        count = referrals.get(user_id + "_count", 0)
        link = f"https://t.me/YOUR_BOT_USERNAME?start={user_id}"
        bot.send_message(
            msg.chat.id,
            f"👥 Referrals: {count}\n\n🔗 Link:\n{link}"
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
        ip = get_ip(request)

        print(user_id, device_id, ip)

        # ❌ DEVICE USED
        if device_id in devices:
            failed[user_id] = True
            save("failed", failed)

            bot.send_message(user_id, "⚠️ Device already used.\nYou can still use bot.")
            return jsonify({"status": "failed"})

        # ❌ IP USED
        if ip in ips:
            failed[user_id] = True
            save("failed", failed)

            bot.send_message(user_id, "⚠️ Multiple accounts detected.\nYou can still use bot.")
            return jsonify({"status": "failed"})

        # ✅ SUCCESS
        devices[device_id] = user_id
        save("devices", devices)

        ips[ip] = user_id
        save("ips", ips)

        users[user_id] = True
        save("users", users)

        bot.send_message(user_id, "✅ Verified Successfully!\n🎉 Full access unlocked.")
        return jsonify({"status": "success"})

    except Exception as e:
        print(e)
        return jsonify({"status": "error"})

# 🔐 RESET (SECRET URL)
@app.route("/reset-data")
def reset():
    key = request.args.get("key")

    if key != RESET_KEY:
        return "❌ Access Denied"

    for f in FILES.values():
        with open(f, "w") as file:
            json.dump({}, file)

    return "✅ All data reset"

# 🎛️ ADMIN PANEL
@app.route("/admin")
def admin():
    password = request.args.get("pass")

    if password != ADMIN_PASSWORD:
        return "❌ Access Denied"

    total_users = len(users)
    verified = len(users)
    failed_users = len(failed)
    total_ips = len(ips)
    total_devices = len(devices)
    total_refs = sum([v for k, v in referrals.items() if "_count" in k])

    return render_template_string(f"""
    <html>
    <body style="background:#0a0f1c;color:white;text-align:center;font-family:Arial;">
    <h1>⚙️ Admin Panel</h1>

    <p>👥 Users: {total_users}</p>
    <p>✅ Verified: {verified}</p>
    <p>❌ Failed: {failed_users}</p>
    <p>🌍 IPs: {total_ips}</p>
    <p>📱 Devices: {total_devices}</p>
    <p>💰 Referrals: {total_refs}</p>

    <br>
    <a href="/reset-data?key={RESET_KEY}">
    <button style="padding:10px;background:red;color:white;">RESET</button>
    </a>

    </body>
    </html>
    """)

# RUN BOT
def run_bot():
    print("🤖 Bot Started")
    bot.remove_webhook()
    bot.infinity_polling(timeout=30, long_polling_timeout=30)

threading.Thread(target=run_bot).start()

# RUN SERVER
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
