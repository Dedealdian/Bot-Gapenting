import telebot
from telebot import types
import json
import os

# --- KONFIGURASI ---
TOKEN = "8434915247:AAFqXFnzRNhUR3gt7uU9aQwPAphKv12R0A0"
DB_FILE = "channel_master_pro.json"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# --- DATABASE ENGINE ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {"profiles": {}, "channel_links": {}}
    try:
        with open(DB_FILE, 'r') as f: return json.load(f)
    except: return {"profiles": {}, "channel_links": {}}

def save_db(data):
    with open(DB_FILE, 'w') as f: json.dump(data, f, indent=4)

db = load_db()
user_state = {}

# --- HELPER: PARSER TOMBOL ---
def parse_buttons(raw_text):
    layout = []
    if not raw_text or raw_text.lower() in ['none', 'skip', 'lewati']: return layout
    for line in raw_text.strip().split('\n'):
        row = []
        for part in line.split('&&'):
            if '-' in part:
                try:
                    text, action = part.split('-', 1)
                    row.append({"text": text.strip(), "url": action.strip()})
                except: continue
        if row: layout.append(row)
    return layout

def get_kb(btns_data):
    kb = types.InlineKeyboardMarkup()
    if not btns_data: return None
    for row in btns_data:
        items = [types.InlineKeyboardButton(b['text'], url=b['url']) for b in row]
        kb.row(*items)
    return kb

# --- UI REFRESH HELPER ---
def refresh_profile_list(message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for name in db["profiles"]:
        safe_cb = f"vp:{name}"[:60]
        kb.add(types.InlineKeyboardButton(f"📝 {name}", callback_data=safe_cb))
    kb.add(types.InlineKeyboardButton("➕ Buat Profile Baru", callback_data="set_buat"))
    kb.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="m_start"))
    
    try:
        bot.edit_message_text("<b>DAFTAR PROFILE</b>\nPilih profile atau buat baru:", 
                              message.chat.id, message.message_id, reply_markup=kb)
    except:
        bot.send_message(message.chat.id, "<b>DAFTAR PROFILE</b>\nPilih profile atau buat baru:", reply_markup=kb)

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📋 Kelola Profile", callback_data="list_profile"))
    bot.send_message(message.chat.id, "<b>CHANNEL MASTER PRO</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def cb_handler(call):
    uid = str(call.from_user.id)
    bot.answer_callback_query(call.id)

    # Logika Pembatalan Universal
    if call.data == "cancel_all":
        bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
        user_state.pop(uid, None)
        refresh_profile_list(call.message)
        return

    if call.data == "m_start":
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📋 Kelola Profile", callback_data="list_profile"))
        bot.edit_message_text("<b>CHANNEL MASTER PRO</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif call.data == "list_profile":
        refresh_profile_list(call.message)

    elif call.data == "set_buat":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Batal & Kembali", callback_data="cancel_all"))
        msg = bot.send_message(call.message.chat.id, "✍️ Masukkan <b>Nama Profile</b> baru:", reply_markup=kb)
        bot.register_next_step_handler(msg, step_name)

    elif call.data == "skip_text":
        user_state[uid]["text"] = ""
        ask_media(call.message, uid)

    elif call.data == "skip_media":
        user_state[uid]["media"] = None
        ask_buttons(call.message, uid)

    elif call.data == "skip_btn":
        user_state[uid]["btns"] = []
        ask_target(call.message, uid)

    elif call.data.startswith("vp:"):
        name_part = call.data.split(":")[1]
        name = next((n for n in db["profiles"] if n.startswith(name_part)), name_part)
        p = db["profiles"].get(name)
        if not p: return
        
        text = f"<b>DETAIL PROFILE:</b> <code>{name}</code>\n\n<b>Target:</b> <code>{p.get('target')}</code>"
        kb = types.InlineKeyboardMarkup(row_width=2).add(
            types.InlineKeyboardButton("🗑️ Hapus", callback_data=f"del:{name}"[:60]),
            types.InlineKeyboardButton("🔙 Kembali", callback_data="list_profile")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif call.data.startswith("del:"):
        name_part = call.data.split(":")[1]
        name = next((n for n in db["profiles"] if n.startswith(name_part)), name_part)
        if name in db["profiles"]:
            t = db["profiles"][name].get('target')
            if t in db["channel_links"]: del db["channel_links"][t]
            del db["profiles"][name]
        save_db(db)
        refresh_profile_list(call.message)

# --- FSM STEPS DENGAN NAVIGASI KEMBALI ---
def step_name(message):
    uid = str(message.from_user.id)
    name = message.text.strip().replace(" ", "_")[:25]
    user_state[uid] = {"name": name}
    
    kb = types.InlineKeyboardMarkup().row(
        types.InlineKeyboardButton("⏭️ Lewati", callback_data="skip_text"),
        types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all")
    )
    bot.send_message(message.chat.id, f"✅ Nama <b>{name}</b> disimpan.\n\nMasukkan <b>Teks Tambahan</b>:", reply_markup=kb)
    bot.register_next_step_handler(message, step_text)

def step_text(message):
    uid = str(message.from_user.id)
    user_state[uid]["text"] = message.html_text if message.text else ""
    ask_media(message, uid)

def ask_media(message, uid):
    kb = types.InlineKeyboardMarkup().row(
        types.InlineKeyboardButton("⏭️ Lewati", callback_data="skip_media"),
        types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all")
    )
    bot.send_message(message.chat.id, "Kirim <b>Foto/Video</b> atau klik Lewati:", reply_markup=kb)
    bot.register_next_step_handler(message, step_media)

def step_media(message):
    uid = str(message.from_user.id)
    if message.photo: user_state[uid].update({"media": message.photo[-1].file_id, "type": "photo"})
    elif message.video: user_state[uid].update({"media": message.video.file_id, "type": "video"})
    else: user_state[uid]["media"] = None
    ask_buttons(message, uid)

def ask_buttons(message, uid):
    kb = types.InlineKeyboardMarkup().row(
        types.InlineKeyboardButton("⏭️ Lewati", callback_data="skip_btn"),
        types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all")
    )
    bot.send_message(message.chat.id, "Kirim <b>Format Tombol</b> atau klik Lewati:", reply_markup=kb)
    bot.register_next_step_handler(message, step_btn)

def step_btn(message):
    uid = str(message.from_user.id)
    user_state[uid]["btns"] = parse_buttons(message.text)
    ask_target(message, uid)

def ask_target(message, uid):
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all"))
    bot.send_message(message.chat.id, "Masukkan <b>ID Channel Target</b>:", reply_markup=kb)
    bot.register_next_step_handler(message, step_finish)

def step_finish(message):
    uid = str(message.from_user.id)
    target = message.text.strip()
    data = user_state.get(uid)
    if not data: return
    
    db["profiles"][data["name"]] = {
        "text": data["text"], "media": data.get("media"), 
        "type": data.get("type"), "btns": data["btns"], "target": target
    }
    db["channel_links"][target] = data["name"]
    save_db(db)
    user_state.pop(uid, None)
    bot.send_message(message.chat.id, "✅ Profile Aktif!", 
                     reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Kelola Profile", callback_data="list_profile")))

# --- AUTOPOST LOGIC ---
@bot.channel_post_handler(func=lambda m: True)
def handle_post(message):
    cid = str(message.chat.id)
    prof_name = db["channel_links"].get(cid)
    if not prof_name: return
    p = db["profiles"].get(prof_name)
    
    kb = get_kb(p["btns"])
    orig = message.html_caption if (message.photo or message.video) else message.html_text
    orig = orig if orig else ""
    final_text = f"{orig}\n\n{p['text']}".strip()

    try:
        if p.get("media"):
            bot.delete_message(cid, message.message_id)
            if p["type"] == "photo": bot.send_photo(cid, p["media"], caption=final_text, reply_markup=kb)
            else: bot.send_video(cid, p["media"], caption=final_text, reply_markup=kb)
        else:
            if message.photo or message.video:
                bot.edit_message_caption(final_text, cid, message.message_id, reply_markup=kb)
            else:
                bot.edit_message_text(final_text, cid, message.message_id, reply_markup=kb)
    except: pass

if __name__ == "__main__":
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'channel_post'])
