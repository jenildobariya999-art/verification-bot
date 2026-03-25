from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import TeleBot, types
import hashlib, json, os, threading

# CONFIG
API_TOKEN = os.environ.get("API_TOKEN")
DOMAIN = "https://verification-beta-five.vercel.app"  # replace your webapp
BOT_USERNAME = "TestingOnTop_bot"
CHANNEL_URL = "https://t.me/FASTLIFAFAOFFICIAL"

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
    "refs": "referrals.json",
    "settings": "settings.json",
    "admins": "admins.json"
}

# initialize files
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
settings = json.load(open(FILES["settings"])) if os.path.exists(FILES["settings"]) else {}
admins = json.load(open(FILES["admins"])) if os.path.exists(FILES["admins"]) else {}

def save(name, data):
    with open(FILES[name], "w") as f:
        json.dump(data, f)

def make_hash(data):
    return hashlib.md5(data.encode()).hexdigest()

def get_ip(req):
    if req.headers.get("X-Forwarded-For"):
        return req.headers.get("X-Forwarded-For").split(",")[0]
    return req.remote_addr

# check if user is admin
def is_admin(user_id):
    return str(user_id) in admins

# START COMMAND
@bot.message_handler(commands=['start'])
def start(msg):
    user_id = str(msg.chat.id)
    args = msg.text.split()

    # Referral
    if len(args) > 1:
        ref = args[1]
        if ref != user_id and user_id not in referrals:
            referrals[user_id] = ref
            referrals[ref + "_count"] = referrals.get(ref + "_count", 0) + 1
            save("refs", referrals)
            bot.send_message(ref, "🎉 New referral joined!")

    # Already verified → show main menu
    if user_id in users:
        show_main_menu(user_id, "✅ You are already verified!")
        return

    # Failed users
    if user_id in failed:
        bot.send_message(user_id, "⚠️ Device/IP already used.\nYou can still use bot.")
        return

    # Step 1: Join channel
    join_channel_btn = types.InlineKeyboardMarkup()
    join_btn = types.InlineKeyboardButton("➡ Join Channel", url=CHANNEL_URL)
    join_channel_btn.add(join_btn)
    bot.send_message(user_id, "🚀 Please join our channel first:", reply_markup=join_channel_btn)

    # Step 2: Verify device
    verify_btn = types.InlineKeyboardMarkup()
    btn_verify = types.InlineKeyboardButton("🔐 Verify Device", web_app=types.WebAppInfo(DOMAIN))
    verify_btn.add(btn_verify)
    bot.send_message(user_id, "🛡 Verify your device:", reply_markup=verify_btn)

# Show main menu after verification
def show_main_menu(user_id, text="✅ Verified Successfully!"):
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu.add("💰 Balance", "👥 Refer & Earn")
    menu.add("🎁 Bonus", "💸 Withdraw")
    menu.add("🛠 Set Wallet")
    bot.send_message(user_id, text, reply_markup=menu)

# HANDLE REPLY KEYBOARD
@bot.message_handler(func=lambda m: True)
def handle_buttons(msg):
    user_id = str(msg.chat.id)
    text = msg.text

    if text == "💰 Balance":
        balance = settings.get("balances", {}).get(user_id, 0)
        bot.send_message(user_id, f"💰 Your balance: ₹{balance}")
    elif text == "👥 Refer & Earn":
        count = referrals.get(user_id + "_count", 0)
        link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        bot.send_message(user_id, f"👥 Referrals: {count}\n🔗 Link: {link}")
    elif text == "🎁 Bonus":
        daily_bonus = settings.get("daily_bonus", 0)
        bot.send_message(user_id, f"🎁 Your daily bonus: ₹{daily_bonus}")
    elif text == "💸 Withdraw":
        withdraw_status = settings.get("withdraw_on", True)
        bot.send_message(user_id, f"💸 Withdrawals are {'enabled' if withdraw_status else 'disabled'}")
    elif text == "🛠 Set Wallet":
        bot.send_message(user_id, "Please send your wallet address now.")

# ADMIN PANEL INLINE BUTTONS
@bot.message_handler(commands=['adminpanel'])
def admin_panel(msg):
    user_id = str(msg.chat.id)
    if not is_admin(user_id):
        bot.send_message(user_id, "❌ You are not an admin!")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Add Admin", callback_data="admin_add"),
        types.InlineKeyboardButton("Remove Admin", callback_data="admin_remove"),
        types.InlineKeyboardButton("Bot On/Off", callback_data="bot_toggle"),
        types.InlineKeyboardButton("Withdraw On/Off", callback_data="withdraw_toggle"),
        types.InlineKeyboardButton("Add Balance", callback_data="balance_add"),
        types.InlineKeyboardButton("Remove Balance", callback_data="balance_remove"),
        types.InlineKeyboardButton("Manage Channels", callback_data="channel_manage"),
        types.InlineKeyboardButton("Set Per Refer", callback_data="set_per_refer"),
        types.InlineKeyboardButton("Manage Bot Texts", callback_data="bot_texts"),
        types.InlineKeyboardButton("Broadcast", callback_data="broadcast"),
        types.InlineKeyboardButton("Daily Bonus", callback_data="daily_bonus"),
        types.InlineKeyboardButton("Gift Code", callback_data="gift_code"),
        types.InlineKeyboardButton("New User Notif", callback_data="user_notif"),
        types.InlineKeyboardButton("Gateway Setup", callback_data="gateway_setup")
    )
    bot.send_message(user_id, "🛠 Admin Panel:", reply_markup=markup)

# HANDLE CALLBACK QUERIES
@bot.callback_query_handler(func=lambda call: True)
def admin_callback(call):
    user_id = str(call.message.chat.id)
    data = call.data

    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ You are not an admin!")
        return

    # Simple example toggle
    if data == "bot_toggle":
        settings["bot_on"] = not settings.get("bot_on", True)
        save("settings", settings)
        bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=f"Bot is now {'ON' if settings['bot_on'] else 'OFF'}")
    elif data == "withdraw_toggle":
        settings["withdraw_on"] = not settings.get("withdraw_on", True)
        save("settings", settings)
        bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=f"Withdrawals are now {'ON' if settings['withdraw_on'] else 'OFF'}")
    else:
        bot.answer_callback_query(call.id, f"You clicked: {data} (logic to implement)")

# RUN BOT
def run_bot():
    print("🤖 Bot Started")
    bot.infinity_polling(timeout=30, long_polling_timeout=30)

threading.Thread(target=run_bot).start()

# FLASK SERVER
port = int(os.environ.get("PORT", 5000))
app = Flask(__name__)
CORS(app)
app.run(host="0.0.0.0", port=port)
