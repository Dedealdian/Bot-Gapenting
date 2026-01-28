import telebot
from telebot import types
import json
import os
import logging
import hashlib

# --- KONFIGURASI ---
TOKEN = "8434915247:AAFqXFnzRNhUR3gt7uU9aQwPAphKv12R0A0"
DB_FILE = "channel_master_pro.json"
LOG_FILE = "bot_activity.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# --- DATABASE ENGINE ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {"profiles": {}, "channel_links": {}, "stats": {"total_processed": 0}, "last_hashes": {}}
    try:
        with open(DB_FILE, 'r') as f:
            data = json.load(f)
            if "stats" not in data: data["stats"] = {"total_processed": 0}
            if "last_hashes" not in data: data["last_hashes"] = {}
            return data
    except:
        return {"profiles": {}, "channel_links": {}, "stats": {"total_processed": 0}, "last_hashes": {}}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- HELPER FUNCTIONS ---
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

# --- STATE MANAGEMENT ---
user_state = {}

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = str(message.from_user.id)
    kb = types.InlineKeyboardMarkup(row_width=2).add(
        types.InlineKeyboardButton("📋 Profile Saya", callback_data="list_profile"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="bc_all"),
        types.InlineKeyboardButton("📊 Statistik", callback_data="view_stats"),
        types.InlineKeyboardButton("📜 Lihat Log", callback_data="view_log")
    )
    bot.send_message(message.chat.id, "<b>CHANNEL MASTER PRO V3</b>\n<i>Security & Navigasi Aktif</i>", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def cb_handler(call):
    uid = str(call.from_user.id)
    db = load_db()
    bot.answer_callback_query(call.id)

    # Logika Batal Universal
    if call.data == "m_start" or call.data == "cancel_all":
        bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
        user_state.pop(uid, None)
        kb = types.InlineKeyboardMarkup(row_width=2).add(
            types.InlineKeyboardButton("📋 Profile Saya", callback_data="list_profile"),
            types.InlineKeyboardButton("📢 Broadcast", callback_data="bc_all"),
            types.InlineKeyboardButton("📊 Statistik", callback_data="view_stats"),
            types.InlineKeyboardButton("📜 Lihat Log", callback_data="view_log")
        )
        try: bot.edit_message_text("<b>CHANNEL MASTER PRO V3</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)
        except: bot.send_message(call.message.chat.id, "<b>CHANNEL MASTER PRO V3</b>", reply_markup=kb)

    elif call.data == "list_profile":
        kb = types.InlineKeyboardMarkup(row_width=1)
        owned = {n: p for n, p in db["profiles"].items() if str(p.get("owner_id")) == uid}
        for name in owned:
            kb.add(types.InlineKeyboardButton(f"📝 {name}", callback_data=f"vp:{name}"[:60]))
        
        kb.add(types.InlineKeyboardButton("➕ Buat Profile Baru", callback_data="set_buat"))
        kb.add(types.InlineKeyboardButton("🔙 Kembali", callback_data="m_start"))
        bot.edit_message_text(f"<b>DAFTAR PROFILE ANDA</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif call.data == "set_buat":
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all"))
        msg = bot.send_message(call.message.chat.id, "✍️ Masukkan <b>Nama Profile</b> baru:", reply_markup=kb)
        bot.register_next_step_handler(msg, step_name)

    elif call.data.startswith("vp:"):
        name_part = call.data.split(":")[1]
        name = next((n for n in db["profiles"] if n.startswith(name_part)), None)
        p = db["profiles"].get(name)
        if not p or str(p.get("owner_id")) != uid: return
        
        text = f"<b>DETAIL PROFILE:</b> <code>{name}</code>\nTarget: <code>{p.get('target')}</code>"
        kb = types.InlineKeyboardMarkup().row(
            types.InlineKeyboardButton("🗑️ Hapus", callback_data=f"del:{name}"[:60]),
            types.InlineKeyboardButton("🔙 Kembali", callback_data="list_profile")
        )
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif call.data.startswith("del:"):
        name_part = call.data.split(":")[1]
        name = next((n for n in db["profiles"] if n.startswith(name_part)), None)
        p = db["profiles"].get(name)
        if p and str(p.get("owner_id")) == uid:
            target = p.get('target')
            if target in db["channel_links"]: del db["channel_links"][target]
            del db["profiles"][name]
            save_db(db)
        # Kembali ke list setelah hapus
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Kembali ke List", callback_data="list_profile"))
        bot.edit_message_text("✅ Profile Berhasil Dihapus", call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif call.data == "view_stats":
        total_p = len(db["profiles"])
        proc = db["stats"]["total_processed"]
        text = f"<b>📊 STATISTIK</b>\nTotal Profile: {total_p}\nTotal Post: {proc}"
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Kembali", callback_data="m_start"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif call.data == "view_log":
        content = "Belum ada log."
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f: content = "".join(f.readlines()[-10:])
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Kembali", callback_data="m_start"))
        bot.edit_message_text(f"<b>📜 LOG:</b>\n<code>{content}</code>", call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif call.data == "bc_all":
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all"))
        msg = bot.send_message(call.message.chat.id, "📢 Kirim pesan Broadcast:", reply_markup=kb)
        bot.register_next_step_handler(msg, step_broadcast)

# --- FSM STEPS (DENGAN TOMBOL BATAL) ---
def step_name(message):
    uid = str(message.from_user.id)
    if message.text == "/start": return cmd_start(message)
    user_state[uid] = {"name": message.text.strip().replace(" ", "_"), "owner_id": uid}
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all"))
    bot.send_message(message.chat.id, "📄 Masukkan <b>Teks Template</b>:", reply_markup=kb)
    bot.register_next_step_handler(message, step_text)

def step_text(message):
    uid = str(message.from_user.id)
    user_state[uid]["text"] = message.html_text
    kb = types.InlineKeyboardMarkup().row(
        types.InlineKeyboardButton("⏭️ Lewati", callback_data="skip_media"),
        types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all")
    )
    bot.send_message(message.chat.id, "🖼️ Kirim <b>Foto/Video</b> atau klik Lewati:", reply_markup=kb)
    bot.register_next_step_handler(message, step_media)

@bot.callback_query_handler(func=lambda call: call.data == "skip_media")
def skip_media(call):
    uid = str(call.from_user.id)
    user_state[uid]["media"] = None
    ask_buttons(call.message, uid)

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
    bot.send_message(message.chat.id, "🔘 Masukkan <b>Format Tombol</b> (Nama-Link):", reply_markup=kb)
    bot.register_next_step_handler(message, step_btn)

@bot.callback_query_handler(func=lambda call: call.data == "skip_btn")
def skip_btn(call):
    uid = str(call.from_user.id)
    user_state[uid]["btns"] = []
    ask_target(call.message, uid)

def step_btn(message):
    uid = str(message.from_user.id)
    user_state[uid]["btns"] = parse_buttons(message.text)
    ask_target(message, uid)

def ask_target(message, uid):
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Batal", callback_data="cancel_all"))
    bot.send_message(message.chat.id, "🆔 Masukkan <b>ID Channel</b> (Bisa banyak dipisah spasi):", reply_markup=kb)
    bot.register_next_step_handler(message, step_finish)

def step_finish(message):
    uid = str(message.from_user.id)
    db = load_db()
    targets = message.text.strip().split()
    data = user_state.get(uid)
    if not data: return

    for target in targets:
        final_name = f"{data['name']}_{target.replace('-', '')}"
        db["profiles"][final_name] = {
            "text": data["text"], "media": data.get("media"),
            "type": data.get("type"), "btns": data["btns"],
            "target": target, "owner_id": uid
        }
        db["channel_links"][target] = final_name
    
    save_db(db)
    user_state.pop(uid, None)
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="m_start"))
    bot.send_message(message.chat.id, "✅ Profil Berhasil Disimpan!", reply_markup=kb)

def step_broadcast(message):
    uid = str(message.from_user.id)
    db = load_db()
    my_channels = list(set([p["target"] for p in db["profiles"].values() if str(p.get("owner_id")) == uid]))
    success = 0
    for cid in my_channels:
        try:
            bot.copy_message(cid, message.chat.id, message.message_id)
            success += 1
        except: continue
    bot.send_message(message.chat.id, f"🚀 Broadcast selesai: {success} channel.", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Menu", callback_data="m_start")))

# --- AUTOPOST ---
@bot.channel_post_handler(func=lambda m: True)
def handle_post(message):
    try:
        db = load_db()
        cid = str(message.chat.id)
        prof_name = db["channel_links"].get(cid)
        if not prof_name: return
        p = db["profiles"].get(prof_name)

        content = message.text or message.caption or "empty"
        msg_hash = hashlib.md5(content.encode()).hexdigest()
        if db.get("last_hashes", {}).get(cid) == msg_hash: return

        db["last_hashes"][cid] = msg_hash
        db["stats"]["total_processed"] += 1
        save_db(db)

        kb = get_kb(p["btns"])
        orig = message.html_caption if (message.photo or message.video) else message.html_text
        final_text = f"{orig if orig else ''}\n\n{p['text']}".strip()

        if p.get("media"):
            bot.delete_message(cid, message.message_id)
            if p["type"] == "photo": bot.send_photo(cid, p["media"], caption=final_text, reply_markup=kb)
            else: bot.send_video(cid, p["media"], caption=final_text, reply_markup=kb)
        else:
            if message.photo or message.video: bot.edit_message_caption(final_text, cid, message.message_id, reply_markup=kb)
            else: bot.edit_message_text(final_text, cid, message.message_id, reply_markup=kb)
    except: pass

if __name__ == "__main__":
    bot.infinity_polling(timeout=20)
