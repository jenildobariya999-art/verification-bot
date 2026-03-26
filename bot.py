from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import TeleBot, types
import hashlib, json, os, threading

# ================= CONFIG =================
API_TOKEN = os.environ.get("API_TOKEN")
DOMAIN = "https://verification-beta-five.vercel.app"

ADMIN_IDS = ["6925391837"]  # CHANGE
bot_status = True

# ================= INIT =================
bot = TeleBot(API_TOKEN)
bot.remove_webhook()

app = Flask(__name__)
CORS(app)

FILES = {
    "devices": "devices.json",
    "users": "users.json",
    "failed": "failed.json",
    "ips": "ips.json",
    "refs": "referrals.json",
    "balance": "balance.json",
    "gift": "gift.json"
}

# create files
for f in FILES.values():
    if not os.path.exists(f):
        with open(f, "w") as file:
            json.dump({}, file)

# load
devices = json.load(open(FILES["devices"]))
users = json.load(open(FILES["users"]))
failed = json.load(open(FILES["failed"]))
ips = json.load(open(FILES["ips"]))
refs = json.load(open(FILES["refs"]))
balance = json.load(open(FILES["balance"]))
gift = json.load(open(FILES["gift"]))

def save(name, data):
    with open(FILES[name], "w") as f:
        json.dump(data, f)

def is_admin(uid):
    return str(uid) in ADMIN_IDS

def make_hash(data):
    return hashlib.md5(data.encode()).hexdigest()

def get_ip(req):
    if req.headers.get("X-Forwarded-For"):
        return req.headers.get("X-Forwarded-For").split(",")[0]
    return req.remote_addr

# ================= START =================
@bot.message_handler(commands=['start'])
def start(msg):
    if not bot_status:
        return

    user_id = str(msg.chat.id)
    args = msg.text.split()

    # referral
    if len(args) > 1:
        ref = args[1]
        if ref != user_id and user_id not in refs:
            refs[user_id] = ref
            refs[ref+"_count"] = refs.get(ref+"_count", 0) + 1
            save("refs", refs)
            bot.send_message(ref, "🎉 New referral joined!")

    if user_id in users:
        bot.send_message(msg.chat.id, "✅ Already Verified")
        return

    if user_id in failed:
        bot.send_message(msg.chat.id, "⚠️ Device/IP used\nYou can still use bot")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔐 Verify", web_app=types.WebAppInfo(DOMAIN)))

    bot.send_message(msg.chat.id, "Verify your device", reply_markup=markup)

# ================= REF =================
@bot.message_handler(commands=['ref'])
def ref(msg):
    uid = str(msg.chat.id)
    count = refs.get(uid+"_count", 0)
    bot.send_message(uid, f"👥 Referrals: {count}")

# ================= ADMIN PANEL =================
@bot.message_handler(commands=['adminpanel'])
def adminpanel(msg):
    if not is_admin(msg.chat.id):
        return bot.send_message(msg.chat.id, "❌ Denied")

    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("👤 Add Admin", callback_data="add_admin"),
        types.InlineKeyboardButton("❌ Remove Admin", callback_data="remove_admin"),
        types.InlineKeyboardButton("🤖 Bot ON/OFF", callback_data="bot"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="bc"),
        types.InlineKeyboardButton("💰 Add Balance", callback_data="addbal"),
        types.InlineKeyboardButton("💸 Remove Balance", callback_data="rembal"),
        types.InlineKeyboardButton("🎁 Gift Code", callback_data="gift")
    )

    bot.send_message(msg.chat.id, "🎛️ Admin Panel", reply_markup=m)

# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    uid = str(call.from_user.id)

    if not is_admin(uid):
        return

    if call.data == "bot":
        global bot_status
        bot_status = not bot_status
        bot.send_message(uid, f"Bot {'ON' if bot_status else 'OFF'}")

    elif call.data == "add_admin":
        msg = bot.send_message(uid, "Send ID")
        bot.register_next_step_handler(msg, add_admin)

    elif call.data == "remove_admin":
        msg = bot.send_message(uid, "Send ID")
        bot.register_next_step_handler(msg, rem_admin)

    elif call.data == "bc":
        msg = bot.send_message(uid, "Send broadcast msg")
        bot.register_next_step_handler(msg, broadcast)

    elif call.data == "addbal":
        msg = bot.send_message(uid, "Send: user_id amount")
        bot.register_next_step_handler(msg, add_balance)

    elif call.data == "rembal":
        msg = bot.send_message(uid, "Send: user_id amount")
        bot.register_next_step_handler(msg, rem_balance)

    elif call.data == "gift":
        msg = bot.send_message(uid, "Send: code amount")
        bot.register_next_step_handler(msg, create_gift)

# ================= ADMIN ACTIONS =================
def add_admin(msg):
    ADMIN_IDS.append(msg.text)
    bot.send_message(msg.chat.id, "Added")

def rem_admin(msg):
    if msg.text in ADMIN_IDS:
        ADMIN_IDS.remove(msg.text)
    bot.send_message(msg.chat.id, "Removed")

def broadcast(msg):
    text = msg.text
    for u in users:
        try:
            bot.send_message(u, text)
        except:
            pass
    bot.send_message(msg.chat.id, "Done")

def add_balance(msg):
    uid, amt = msg.text.split()
    balance[uid] = balance.get(uid, 0) + float(amt)
    save("balance", balance)
    bot.send_message(msg.chat.id, "Added")

def rem_balance(msg):
    uid, amt = msg.text.split()
    balance[uid] = balance.get(uid, 0) - float(amt)
    save("balance", balance)
    bot.send_message(msg.chat.id, "Removed")

def create_gift(msg):
    code, amt = msg.text.split()
    gift[code] = float(amt)
    save("gift", gift)
    bot.send_message(msg.chat.id, f"Gift Created: {code}")

# ================= VERIFY =================
@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    uid = str(data.get("user_id"))
    device = data.get("device")

    dev = make_hash(device)
    ip = get_ip(request)

    if dev in devices or ip in ips:
        failed[uid] = True
        save("failed", failed)
        bot.send_message(uid, "⚠️ Already used")
        return jsonify({"status": "failed"})

    devices[dev] = uid
    ips[ip] = uid
    users[uid] = True

    save("devices", devices)
    save("ips", ips)
    save("users", users)

    bot.send_message(uid, "✅ Verified")
    return jsonify({"status": "success"})

# ================= RUN =================
def run():
    bot.infinity_polling()

threading.Thread(target=run).start()

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
