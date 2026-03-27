from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import TeleBot, types
import hashlib, json, os, threading

# ===== CONFIG =====
API_TOKEN = os.environ.get("API_TOKEN")
DOMAIN = "https://verification-beta-five.vercel.app"

ADMIN_IDS = ["6925391837"]  # CHANGE
bot_status = True

# ===== INIT =====
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

# load data
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

# ===== HOME ROUTE (FIXED 404) =====
@app.route("/")
def home():
    return "Bot Running ✅"

# ===== USER MENU =====
def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("💰 Balance", "👥 Refer")
    m.row("🎁 Redeem Code", "📊 My Info")
    return m

# ===== START =====
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = str(msg.chat.id)
    args = msg.text.split()

    # referral
    if len(args) > 1:
        ref = args[1]
        if ref != user_id and user_id not in refs:
            refs[user_id] = ref
            refs[ref+"_count"] = refs.get(ref+"_count", 0) + 1
            save("refs", refs)
            bot.send_message(ref, "🎉 New referral!")

    # verified
    if user_id in users:
        bot.send_message(msg.chat.id, "🏠 Welcome Back!", reply_markup=main_menu())
        return

    # failed
    if user_id in failed:
        bot.send_message(msg.chat.id, "⚠️ Device/IP already used\nLimited access", reply_markup=main_menu())
        return

    # new user
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔐 Verify", web_app=types.WebAppInfo(DOMAIN)))

    bot.send_message(msg.chat.id, "🛡 Please verify first", reply_markup=markup)

# ===== USER BUTTON HANDLER (FIXED) =====
@bot.message_handler(func=lambda m: m.text in ["💰 Balance", "👥 Refer", "🎁 Redeem Code", "📊 My Info"])
def user_buttons(msg):
    user_id = str(msg.chat.id)
    text = msg.text

    if text == "💰 Balance":
        bal = balance.get(user_id, 0)
        bot.send_message(user_id, f"💰 Balance: ₹{bal}")

    elif text == "👥 Refer":
        count = refs.get(user_id+"_count", 0)
        link = f"https://t.me/YOUR_BOT_USERNAME?start={user_id}"
        bot.send_message(user_id, f"👥 Referrals: {count}\n\n🔗 {link}")

    elif text == "🎁 Redeem Code":
        bot.clear_step_handler_by_chat_id(msg.chat.id)
        msg2 = bot.send_message(user_id, "Enter Gift Code:")
        bot.register_next_step_handler(msg2, redeem_code)

    elif text == "📊 My Info":
        bot.send_message(user_id, f"🆔 ID: {user_id}")

# ===== REDEEM =====
def redeem_code(msg):
    code = msg.text
    user_id = str(msg.chat.id)

    if code in gift:
        amount = gift.pop(code)
        balance[user_id] = balance.get(user_id, 0) + amount

        save("gift", gift)
        save("balance", balance)

        bot.send_message(user_id, f"✅ ₹{amount} Added")
    else:
        bot.send_message(user_id, "❌ Invalid Code")

# ===== ADMIN PANEL =====
@bot.message_handler(commands=['adminpanel'])
def adminpanel(msg):
    if not is_admin(msg.chat.id):
        return bot.send_message(msg.chat.id, "❌ Denied")

    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="bc"))
    m.add(types.InlineKeyboardButton("💰 Add Balance", callback_data="addbal"))

    bot.send_message(msg.chat.id, "🎛 Admin Panel", reply_markup=m)

# ===== CALLBACK (FIXED SINGLE HANDLER) =====
@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    uid = str(call.from_user.id)

    if not is_admin(uid):
        return

    if call.data == "bc":
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        msg = bot.send_message(uid, "Send message:")
        bot.register_next_step_handler(msg, broadcast)

    elif call.data == "addbal":
        bot.clear_step_handler_by_chat_id(call.message.chat.id)
        msg = bot.send_message(uid, "Send: user_id amount")
        bot.register_next_step_handler(msg, addbal)

# ===== ADMIN FUNCTIONS =====
def broadcast(msg):
    for u in users:
        try:
            bot.send_message(u, msg.text)
        except:
            pass
    bot.send_message(msg.chat.id, "✅ Broadcast Done")

def addbal(msg):
    uid, amt = msg.text.split()
    balance[uid] = balance.get(uid, 0) + float(amt)
    save("balance", balance)
    bot.send_message(msg.chat.id, "✅ Balance Added")

# ===== VERIFY =====
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
        return jsonify({"status": "failed"})

    devices[dev] = uid
    ips[ip] = uid
    users[uid] = True

    save("devices", devices)
    save("ips", ips)
    save("users", users)

    bot.send_message(uid, "✅ Verified!", reply_markup=main_menu())
    return jsonify({"status": "success"})

# ===== RUN =====
def run():
    bot.infinity_polling(skip_pending=True)

threading.Thread(target=run).start()

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
