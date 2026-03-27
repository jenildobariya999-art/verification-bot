from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import TeleBot, types
import hashlib, json, os, threading

# ===== CONFIG =====
API_TOKEN = os.environ.get("API_TOKEN")
DOMAIN = "https://verification-beta-five.vercel.app"

ADMIN_IDS = ["6925391837", "7528813331"]

# ===== INIT =====
bot = TeleBot(API_TOKEN, parse_mode="HTML")
bot.remove_webhook()

app = Flask(__name__)
CORS(app)

# ===== FILES =====
FILES = {
    "devices": "devices.json",
    "users": "users.json",
    "failed": "failed.json",
    "ips": "ips.json",
    "refs": "referrals.json",
    "balance": "balance.json",
    "gift": "gift.json",
    "texts": "texts.json"
}

# ===== CREATE FILES =====
default_texts = {
    "welcome": "🏠 <b>Welcome Back!</b>",
    "verify_msg": "🛡 <b>Please verify first</b>",
    "success": "✅ <b>Verified Successfully!</b>",
    "failed": "⚠️ <b>Device/IP already used</b>",
    "menu": "👇 <b>Choose option:</b>",
    "redeem": "🎁 <b>Enter Gift Code:</b>"
}

for name, f in FILES.items():
    if not os.path.exists(f):
        with open(f, "w") as file:
            json.dump(default_texts if name == "texts" else {}, file)

# ===== LOAD DATA =====
devices = json.load(open(FILES["devices"]))
users = json.load(open(FILES["users"]))
failed = json.load(open(FILES["failed"]))
ips = json.load(open(FILES["ips"]))
refs = json.load(open(FILES["refs"]))
balance = json.load(open(FILES["balance"]))
gift = json.load(open(FILES["gift"]))
texts = json.load(open(FILES["texts"]))

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

# ===== HOME =====
@app.route("/")
def home():
    return "Bot Running ✅"

# ===== MENU =====
def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("💰 Balance", "👥 Refer")
    m.row("🎁 Redeem Code", "📊 My Info")
    return m

# ===== START =====
@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.chat.id)
    args = msg.text.split()

    # referral
    if len(args) > 1:
        ref = args[1]
        if ref != uid and uid not in refs:
            refs[uid] = ref
            refs[ref+"_count"] = refs.get(ref+"_count", 0) + 1
            save("refs", refs)
            bot.send_message(ref, "🎉 <b>New Referral Joined!</b>")

    if uid in users:
        bot.send_message(uid, texts["welcome"], reply_markup=main_menu())
        return

    if uid in failed:
        bot.send_message(uid, texts["failed"], reply_markup=main_menu())
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔐 Verify", web_app=types.WebAppInfo(DOMAIN)))

    bot.send_message(uid, texts["verify_msg"], reply_markup=markup)

# ===== USER BUTTONS =====
@bot.message_handler(func=lambda m: m.text in ["💰 Balance", "👥 Refer", "🎁 Redeem Code", "📊 My Info"])
def user_buttons(msg):
    uid = str(msg.chat.id)

    if msg.text == "💰 Balance":
        bot.send_message(uid, f"💰 <b>Balance:</b> ₹{balance.get(uid,0)}")

    elif msg.text == "👥 Refer":
        link = f"https://t.me/TestingonTop_bot?start={uid}"
        bot.send_message(uid, f"👥 <b>Referrals:</b> {refs.get(uid+'_count',0)}\n\n🔗 {link}")

    elif msg.text == "🎁 Redeem Code":
        bot.clear_step_handler_by_chat_id(uid)
        msg2 = bot.send_message(uid, texts["redeem"])
        bot.register_next_step_handler(msg2, redeem)

    elif msg.text == "📊 My Info":
        bot.send_message(uid, f"🆔 <b>ID:</b> {uid}")

# ===== REDEEM =====
def redeem(msg):
    code = msg.text
    uid = str(msg.chat.id)

    if code in gift:
        amt = gift.pop(code)
        balance[uid] = balance.get(uid, 0) + amt
        save("gift", gift)
        save("balance", balance)
        bot.send_message(uid, f"✅ <b>₹{amt} Added</b>")
    else:
        bot.send_message(uid, "❌ Invalid Code")

# ===== ADMIN PANEL =====
@bot.message_handler(commands=['adminpanel'])
def adminpanel(msg):
    if not is_admin(msg.chat.id):
        return bot.send_message(msg.chat.id, "❌ Denied")

    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("📢 Broadcast", callback_data="bc"))
    m.add(types.InlineKeyboardButton("💰 Add Balance", callback_data="bal"))
    m.add(types.InlineKeyboardButton("✏️ Edit Texts", callback_data="edit"))

    bot.send_message(msg.chat.id, "🎛 <b>Admin Panel</b>", reply_markup=m)

# ===== CALLBACK =====
@bot.callback_query_handler(func=lambda call: True)
def cb(call):
    uid = str(call.from_user.id)

    if not is_admin(uid):
        return

    if call.data == "bc":
        bot.clear_step_handler_by_chat_id(uid)
        msg = bot.send_message(uid, "Send message:")
        bot.register_next_step_handler(msg, broadcast)

    elif call.data == "bal":
        bot.clear_step_handler_by_chat_id(uid)
        msg = bot.send_message(uid, "user_id amount")
        bot.register_next_step_handler(msg, addbal)

    elif call.data == "edit":
        mk = types.InlineKeyboardMarkup()
        for k in texts:
            mk.add(types.InlineKeyboardButton(k, callback_data=f"edit_{k}"))
        bot.send_message(uid, "Select text:", reply_markup=mk)

    elif call.data.startswith("edit_"):
        key = call.data.replace("edit_", "")
        msg = bot.send_message(uid, f"Send new text for <b>{key}</b>")
        bot.register_next_step_handler(msg, save_text, key)

# ===== ADMIN FUNCTIONS =====
def broadcast(msg):
    for u in users:
        try:
            bot.send_message(u, msg.text)
        except:
            pass

def addbal(msg):
    uid, amt = msg.text.split()
    balance[uid] = balance.get(uid, 0) + float(amt)
    save("balance", balance)
    bot.send_message(msg.chat.id, "✅ Done")

def save_text(msg, key):
    texts[key] = msg.text
    save("texts", texts)
    bot.send_message(msg.chat.id, f"✅ Updated <b>{key}</b>")

# ===== VERIFY =====
@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    uid = str(data.get("user_id"))
    dev = make_hash(data.get("device"))
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

    bot.send_message(uid, texts["success"], reply_markup=main_menu())
    return jsonify({"status": "success"})

# ===== RUN =====
def run():
    bot.infinity_polling(skip_pending=True)

threading.Thread(target=run).start()

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
