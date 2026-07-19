import telebot
import requests
import json
import os
import re
import shutil
import time
import subprocess
import sys
import signal
import hashlib
import sqlite3
import threading
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from github import Github

# ==================== الإعدادات الأساسية ====================
API_TOKEN = "7999963241:AAHBao1UN5tFQOyP9GkYr7Yfprg2WR1oGhw"
ADMIN_ID = 7947679527
DEVELOPER = "@ggzh9"
CHANNEL = "https://t.me/kayo_i"
BOT_CHANNEL = "https://t.me/botkayo"

# إعدادات GitHub
GITHUB_TOKEN = "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"
GITHUB_REPO = "yesssssssie-debug/bot-kayo"

OWNER_TEXT = f"""👑 المطور: {DEVELOPER}
📢 قناة المطور: {CHANNEL}
📢 قناة البوت: {BOT_CHANNEL}"""

# ==================== تهيئة البوت ====================
bot = telebot.TeleBot(API_TOKEN)

# ==================== إعدادات المسارات ====================
DATA_PATH = "data/"
BACKUP_PATH = "backups/"
BOTS_PATH = "bots/"
FILES_PATH = "files/"
LOGS_PATH = "logs/"

for path in [DATA_PATH, BACKUP_PATH, BOTS_PATH, FILES_PATH, LOGS_PATH]:
    os.makedirs(path, exist_ok=True)

# ==================== قاعدة البيانات ====================
DB_PATH = "bot_data.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS app_config (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS statistics (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bots_manager (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, join_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_points (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, bot_days INTEGER DEFAULT 0, expiry_date TEXT, level TEXT DEFAULT "برونز")''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (referrer_id INTEGER, referred_id INTEGER, points_earned INTEGER DEFAULT 50, date TEXT, PRIMARY KEY (referrer_id, referred_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, file_name TEXT, file_path TEXT, file_hash TEXT, file_size INTEGER, upload_date TEXT, file_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()

def db_save_data(table: str, key: str, value: Any):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"REPLACE INTO {table} (key, value) VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def db_load_data(table: str, key: str, default: Any = None) -> Any:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"SELECT value FROM {table} WHERE key = ?", (key,))
        result = c.fetchone()
        conn.close()
        if result:
            return json.loads(result[0])
        return default
    except:
        return default

# ==================== دوال رفع الملفات إلى GitHub ====================
def upload_to_github(file_path: str, file_name: str, commit_message: str = "رفع بوت جديد"):
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        
        with open(file_path, "rb") as f:
            content = f.read()
        
        encoded_content = base64.b64encode(content).decode("utf-8")
        path_in_repo = f"bots/{file_name}"
        
        try:
            contents = repo.get_contents(path_in_repo)
            repo.update_file(path_in_repo, commit_message, encoded_content, contents.sha, branch="main")
        except:
            repo.create_file(path_in_repo, commit_message, encoded_content, branch="main")
        
        return True
    except Exception as e:
        print(f"❌ خطأ في رفع الملف إلى GitHub: {e}")
        return False

def upload_bot_to_github(bot_folder: str, bot_name: str, bot_id: str):
    try:
        bot_file = os.path.join(bot_folder, "bot.py")
        if os.path.exists(bot_file):
            upload_to_github(bot_file, f"{bot_name}/{bot_id}/bot.py", f"رفع بوت {bot_name}")
        
        req_file = os.path.join(bot_folder, "requirements.txt")
        if os.path.exists(req_file):
            upload_to_github(req_file, f"{bot_name}/{bot_id}/requirements.txt", f"رفع متطلبات {bot_name}")
        return True
    except Exception as e:
        print(f"❌ خطأ في رفع البوت إلى GitHub: {e}")
        return False

# ==================== دوال المستخدمين ====================
def get_user_points(user_id: int) -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT points FROM user_points WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except:
        return 0

def add_user_points(user_id: int, points: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        current = get_user_points(user_id)
        c.execute("REPLACE INTO user_points (user_id, points) VALUES (?, ?)", (user_id, current + points))
        conn.commit()
        conn.close()
    except:
        pass

def get_user_bot_days(user_id: int) -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT bot_days FROM user_points WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except:
        return 0

def get_user_expiry_date(user_id: int) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT expiry_date FROM user_points WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None

def set_user_expiry(user_id: int, days: int):
    try:
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE user_points SET expiry_date = ?, bot_days = ? WHERE user_id = ?", (expiry, days, user_id))
        conn.commit()
        conn.close()
    except:
        pass

def add_user_bot_days(user_id: int, days: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        current = get_user_bot_days(user_id)
        c.execute("REPLACE INTO user_points (user_id, bot_days) VALUES (?, ?)", (user_id, current + days))
        conn.commit()
        conn.close()
    except:
        pass

def use_bot_day(user_id: int) -> bool:
    days = get_user_bot_days(user_id)
    if days <= 0:
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE user_points SET bot_days = bot_days - 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_referral_count(user_id: int) -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except:
        return 0

def add_referral(referrer_id: int, referred_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO referrals (referrer_id, referred_id, date) VALUES (?, ?, ?)", 
                  (referrer_id, referred_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        add_user_points(referrer_id, 50)
        return True
    except:
        return False

# ==================== تحميل وحفظ البيانات ====================
def load_data(file_name: str, default: dict = None) -> dict:
    table_map = {"bot.json": "bot_config", "app.json": "app_config", "statistics.json": "statistics", "bots_manager.json": "bots_manager"}
    table = table_map.get(file_name, "bot_config")
    key = file_name.replace(".json", "")
    return db_load_data(table, key, default or {})

def save_data(file_name: str, data: dict):
    table_map = {"bot.json": "bot_config", "app.json": "app_config", "statistics.json": "statistics", "bots_manager.json": "bots_manager"}
    table = table_map.get(file_name, "bot_config")
    key = file_name.replace(".json", "")
    db_save_data(table, key, data)

def save_all():
    global bot_data, app_data, stats_data, bots_manager
    save_data("bot.json", bot_data)
    save_data("app.json", app_data)
    save_data("statistics.json", stats_data)
    save_data("bots_manager.json", bots_manager)

# ==================== تهيئة البيانات ====================
init_database()

bot_data = load_data("bot.json", {})
app_data = load_data("app.json", {})
stats_data = load_data("statistics.json", {"users": [], "groups": []})
bots_manager = load_data("bots_manager.json", {"bots": {}, "running": [], "logs": {}, "processes": {}})

def init_defaults():
    if "admins" not in bot_data:
        bot_data["admins"] = [ADMIN_ID]
    if ADMIN_ID not in bot_data["admins"]:
        bot_data["admins"].append(ADMIN_ID)
    
    bot_data.setdefault("banned", [])
    bot_data.setdefault("promotionn", [])
    bot_data.setdefault("folder", "bots")
    bot_data.setdefault("upload", "on")
    bot_data.setdefault("check", "on")
    bot_data.setdefault("tak", "on")
    bot_data.setdefault("tawgeh", "on")
    bot_data.setdefault("bott", "on")
    bot_data.setdefault("premium", "off")
    bot_data.setdefault("VIP_button", "on")
    bot_data.setdefault("numberfiles", 7)
    bot_data.setdefault("numberban", 3)
    bot_data.setdefault("stabilizing", "off")
    bot_data.setdefault("directing", "off")
    bot_data.setdefault("radio_g_or_p", "private")
    bot_data.setdefault("from_php", {})
    bot_data.setdefault("from_json", {})
    bot_data.setdefault("from_text", {})
    bot_data.setdefault("from_py", {})
    bot_data.setdefault("from_other", {})
    bot_data.setdefault("from_ban", {})
    bot_data.setdefault("php", 0)
    bot_data.setdefault("json", 0)
    bot_data.setdefault("text", 0)
    bot_data.setdefault("py", 0)
    bot_data.setdefault("other", 0)
    bot_data.setdefault("file", 0)
    bot_data.setdefault("php_ban", 0)
    bot_data.setdefault("json_ban", 0)
    bot_data.setdefault("text_ban", 0)
    bot_data.setdefault("py_ban", 0)
    bot_data.setdefault("ban", 0)
    bot_data.setdefault("Info_uploads", {"telegram": 0, "not_telegram": 0, "curl": 0})
    
    app_data.setdefault("twasol", {})
    app_data.setdefault("mode", {})
    
    stats_data.setdefault("stats", {
        "total_users": 0,
        "total_groups": 0,
        "today": {"date": datetime.now().strftime("%Y-%m-%d"), "users": 0, "groups": 0},
        "yesterday": {"date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"), "users": 0, "groups": 0},
        "new_today": 0,
        "new_groups_today": 0,
    })
    
    bots_manager.setdefault("bots", {})
    bots_manager.setdefault("running", [])
    bots_manager.setdefault("logs", {})
    bots_manager.setdefault("processes", {})

init_defaults()
save_all()

# ==================== دوال الأزرار ====================
def create_colored_button(text: str, callback_data: str = None, url: str = None, style: str = "primary"):
    try:
        if url:
            return telebot.types.InlineKeyboardButton(text=text, url=url, style=style)
        else:
            return telebot.types.InlineKeyboardButton(text=text, callback_data=callback_data, style=style)
    except TypeError:
        if url:
            return telebot.types.InlineKeyboardButton(text=text, url=url)
        else:
            return telebot.types.InlineKeyboardButton(text=text, callback_data=callback_data)

# ==================== القوائم ====================
def main_menu_keyboard(user_id: int):
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    points = get_user_points(user_id)
    days = get_user_bot_days(user_id)
    
    keyboard.add(
        create_colored_button(f"⭐ نقاطي: {points}", callback_data="show_points", style="primary"),
        create_colored_button(f"📅 أيام البوت: {days}", callback_data="show_days", style="success")
    )
    keyboard.add(
        create_colored_button("📤 رفع بوت", callback_data="upload_bot", style="success"),
        create_colored_button("📁 بوتاتي", callback_data="my_bots", style="primary")
    )
    keyboard.add(
        create_colored_button("📢 نشر بوتي", callback_data="publish_bot", style="primary"),
        create_colored_button("💰 أسعار الاشتراك", callback_data="prices", style="success")
    )
    keyboard.add(
        create_colored_button("👑 المطور", url="https://t.me/ggzh9", style="primary"),
        create_colored_button("📢 قناة البوت", url=BOT_CHANNEL, style="primary")
    )
    return keyboard

def admin_panel_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        create_colored_button("📤 رفع بوت جديد", callback_data="admin_upload_bot", style="success"),
        create_colored_button("🤖 إدارة البوتات", callback_data="bots_manager_menu", style="primary")
    )
    keyboard.add(
        create_colored_button("📢 إذاعة", callback_data="msg", style="primary"),
        create_colored_button("⚙️ إعدادات", callback_data="abdo", style="primary")
    )
    keyboard.add(
        create_colored_button("📊 إحصائيات", callback_data="statistics", style="primary"),
        create_colored_button("🔒 الحظر", callback_data="ksmblock", style="danger")
    )
    keyboard.add(
        create_colored_button("👥 الادمنية", callback_data="ksmadmin", style="primary"),
        create_colored_button("⭐ VIP", callback_data="ksmvip", style="success")
    )
    keyboard.add(
        create_colored_button("📦 نسخ احتياطي", callback_data="backup_menu", style="primary"),
        create_colored_button("👑 المطور", url="https://t.me/ggzh9", style="primary")
    )
    return keyboard

def back_button():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(create_colored_button("🔙 رجوع", callback_data="back", style="primary"))
    return keyboard

def back_to_admin():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(create_colored_button("🔙 رجوع للوحة التحكم", callback_data="admin_panel", style="primary"))
    return keyboard

def bots_manager_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    running_count = len(bots_manager.get("running", []))
    total_bots = len(bots_manager.get("bots", {}))
    
    keyboard.add(create_colored_button(f"📊 إجمالي البوتات: {total_bots}", callback_data="bots_total", style="primary"))
    keyboard.add(create_colored_button(f"🟢 المشغلة: {running_count}", callback_data="bots_running", style="success"))
    keyboard.add(create_colored_button("📋 قائمة البوتات", callback_data="bots_list", style="primary"))
    keyboard.add(create_colored_button("📤 رفع بوت جديد", callback_data="admin_upload_bot", style="success"))
    keyboard.add(create_colored_button("🔄 إعادة تشغيل بوت", callback_data="restart_bot", style="primary"))
    keyboard.add(create_colored_button("⏹ إيقاف بوت", callback_data="stop_bot", style="danger"))
    keyboard.add(create_colored_button("🗑 حذف بوت", callback_data="delete_bot", style="danger"))
    keyboard.add(create_colored_button("🔙 رجوع", callback_data="admin_panel", style="primary"))
    return keyboard

# ==================== دوال المساعدة ====================
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID or user_id in bot_data.get("admins", [])

def is_vip(user_id: int) -> bool:
    return user_id in bot_data.get("promotionn", [])

def is_banned(user_id: int) -> bool:
    return user_id in bot_data.get("banned", [])

def get_user_folder(user_id: int) -> str:
    return os.path.join(FILES_PATH, str(user_id))

def get_current_folder(user_id: int) -> str:
    return os.path.join(get_user_folder(user_id), bot_data.get("folder", "bots"))

def create_folder_if_needed(user_id: int):
    base = get_user_folder(user_id)
    os.makedirs(base, exist_ok=True)
    current = get_current_folder(user_id)
    os.makedirs(current, exist_ok=True)

def get_file_link(file_name: str, user_id: int) -> str:
    return f"https://mindful-elegance.up.railway.app/{get_current_folder(user_id)}/{file_name}"

def extract_token(content: str):
    match = re.search(r'(\d{6,14}:[\w-]{35,75})', content)
    return match.group(1) if match else None

# ==================== إدارة العمليات ====================
running_processes = {}
process_lock = threading.Lock()

def start_bot_process(bot_id: str, bot_file: str) -> bool:
    try:
        if not os.path.exists(bot_file):
            return False
        
        cmd = f"python3 {bot_file} &"
        os.system(cmd)
        
        with process_lock:
            running_processes[bot_id] = {'pid': 0, 'started': datetime.now().isoformat(), 'status': 'running'}
            if "processes" not in bots_manager:
                bots_manager["processes"] = {}
            bots_manager["processes"][bot_id] = {'pid': 0, 'started': datetime.now().isoformat()}
            if bot_id not in bots_manager.get("running", []):
                if "running" not in bots_manager:
                    bots_manager["running"] = []
                bots_manager["running"].append(bot_id)
            if bot_id in bots_manager.get("bots", {}):
                bots_manager["bots"][bot_id]["status"] = "running"
            save_all()
        return True
    except Exception as e:
        print(f"❌ خطأ في تشغيل البوت {bot_id}: {e}")
        return False

def stop_bot_process(bot_id: str) -> bool:
    try:
        with process_lock:
            if bot_id in running_processes:
                del running_processes[bot_id]
            if bot_id in bots_manager.get("running", []):
                bots_manager["running"].remove(bot_id)
            if bot_id in bots_manager.get("bots", {}):
                bots_manager["bots"][bot_id]["status"] = "stopped"
            save_all()
        return True
    except:
        return False

def monitor_bots():
    while True:
        try:
            # مراقبة انتهاء صلاحية البوتات
            for bot_id, data in list(bots_manager.get("bots", {}).items()):
                user_id = data.get("user_id")
                if user_id:
                    days = get_user_bot_days(user_id)
                    if days <= 0:
                        if bot_id in bots_manager.get("running", []):
                            stop_bot_process(bot_id)
                            bots_manager["bots"][bot_id]["status"] = "expired"
                            save_all()
            time.sleep(60)
        except:
            time.sleep(60)

# ==================== رسالة الترحيب ====================
def get_welcome_message(user_id: int, first_name: str) -> str:
    points = get_user_points(user_id)
    days = get_user_bot_days(user_id)
    
    return f"""
🌟 <b>اهلاً بك في استضافه بوتات كايو</b>

━━━━━━━━━━━━━━━━━━
👤 <b>الاسم:</b> {first_name}
🆔 <b>ايديك:</b> <code>{user_id}</code>
⭐ <b>نقاطك:</b> {points}
📅 <b>أيام البوت:</b> {days}
━━━━━━━━━━━━━━━━━━

<b>📌 الخدمات:</b>
• 🚀 رفع وتشغيل بوتات تليجرام
• 💰 اشتراكات شهرية وسنوية

👑 <b>المطور:</b> <a href='https://t.me/ggzh9'>@ggzh9</a>
📢 <b>القناة:</b> <a href='{CHANNEL}'>قناة المطور</a>
"""

# ==================== الأوامر ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    create_folder_if_needed(user_id)
    
    if message.text and "start=ref_" in message.text:
        try:
            ref_id = int(message.text.split("ref_")[1])
            if ref_id != user_id:
                if add_referral(ref_id, user_id):
                    bot.send_message(user_id, "🎁 تمت إضافة 50 نقطة لك من الدعوة!")
                    bot.send_message(ref_id, f"🎁 تم دعوة مستخدم جديد بواسطتك! +50 نقطة")
        except:
            pass
    
    if user_id not in stats_data["users"]:
        stats_data["users"].append(user_id)
        stats_data["stats"]["total_users"] = len(stats_data["users"])
        stats_data["stats"]["today"]["users"] += 1
        stats_data["stats"]["new_today"] += 1
        save_all()
        try:
            bot.send_message(ADMIN_ID, f"🆕 مستخدم جديد\nالايدي: {user_id}\nاليوزر: @{message.from_user.username or 'لا يوجد'}\nالاسم: {first_name}", parse_mode="HTML")
        except:
            pass
    
    welcome_msg = get_welcome_message(user_id, first_name)
    
    if is_admin(user_id):
        bot.reply_to(message, welcome_msg, parse_mode="HTML", reply_markup=admin_panel_keyboard())
    else:
        bot.reply_to(message, welcome_msg, parse_mode="HTML", reply_markup=main_menu_keyboard(user_id))

@bot.message_handler(commands=['points'])
def points_cmd(message):
    user_id = message.from_user.id
    points = get_user_points(user_id)
    days = get_user_bot_days(user_id)
    
    text = f"""
⭐ <b>نقاطي</b>

💰 النقاط: <b>{points}</b>
📅 أيام البوت: <b>{days}</b>

📌 <b>طريقة الحصول على النقاط:</b>
• دعوة صديق: +50 نقطة
"""
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=back_button())

@bot.message_handler(commands=['my_bots'])
def my_bots_cmd(message):
    user_id = message.from_user.id
    show_user_bots(message, user_id)

# ==================== رفع البوتات ====================
@bot.message_handler(commands=['upload_bot'])
def upload_bot_start(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        bot.reply_to(message, "⛔ أنت محظور")
        return
    
    if not is_admin(user_id):
        days = get_user_bot_days(user_id)
        if days <= 0:
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(
                create_colored_button("💰 شراء أيام", callback_data="prices", style="success"),
                create_colored_button("👑 التواصل مع المطور", url="https://t.me/ggzh9", style="primary")
            )
            bot.reply_to(
                message,
                "⚠️ ليس لديك أيام بوت كافية!\n\n"
                "📌 يمكنك شراء أيام من خلال زر الأسعار أدناه.\n"
                "📌 أو التواصل مع المطور لتفعيل اشتراكك.",
                reply_markup=keyboard
            )
            return
    
    if bot_data.get("upload") != "on" and not is_admin(user_id):
        bot.reply_to(message, "⛔ رفع البوتات معطل حالياً")
        return
    
    msg = bot.reply_to(
        message,
        "📤 أرسل ملف البوت (bot.py) لرفعه.\n\n"
        f"📅 الأيام المتبقية: {get_user_bot_days(user_id)}",
        reply_markup=back_button()
    )
    bot.register_next_step_handler(msg, process_bot_file)

def process_bot_file(message):
    user_id = message.from_user.id
    
    if not message.document:
        bot.reply_to(message, "❌ يرجى إرسال ملف bot.py", reply_markup=back_button())
        return
    
    if not message.document.file_name.endswith('.py'):
        bot.reply_to(message, "❌ يرجى إرسال ملف Python (.py)", reply_markup=back_button())
        return
    
    if not is_admin(user_id):
        if not use_bot_day(user_id):
            bot.reply_to(message, "❌ لا يوجد أيام كافية!", reply_markup=back_button())
            return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        bot_name = message.document.file_name.replace('.py', '')
        bot_id = f"bot_{int(time.time())}_{user_id}"
        
        bot_folder = os.path.join(BOTS_PATH, bot_id)
        os.makedirs(bot_folder, exist_ok=True)
        
        bot_file_path = os.path.join(bot_folder, "bot.py")
        with open(bot_file_path, "wb") as f:
            f.write(downloaded_file)
        
        bot_info = {
            "id": bot_id, 
            "name": bot_name, 
            "file": f"{bot_id}/bot.py", 
            "status": "waiting", 
            "created": datetime.now().isoformat(), 
            "user_id": user_id, 
            "username": message.from_user.username or "لا يوجد"
        }
        bots_manager["bots"][bot_id] = bot_info
        save_all()
        
        msg = bot.reply_to(
            message,
            f"✅ تم استلام ملف البوت: {bot_name}\n🆔 المعرف: {bot_id}\n📤 أرسل الآن ملف requirements.txt",
            reply_markup=back_button()
        )
        bot.register_next_step_handler(msg, process_requirements_file, bot_id, bot_folder, bot_name)
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}", reply_markup=back_button())

def process_requirements_file(message, bot_id, bot_folder, bot_name):
    user_id = message.from_user.id
    
    if not message.document:
        bot.reply_to(message, "❌ يرجى إرسال ملف requirements.txt", reply_markup=back_button())
        return
    
    if not message.document.file_name.endswith('.txt'):
        bot.reply_to(message, "❌ يرجى إرسال ملف requirements.txt", reply_markup=back_button())
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        req_file_path = os.path.join(bot_folder, "requirements.txt")
        with open(req_file_path, "wb") as f:
            f.write(downloaded_file)
        
        status_msg = bot.reply_to(message, "⏳ جاري تثبيت المتطلبات وتشغيل البوت...")
        
        subprocess.run(['pip', 'install', '-r', req_file_path, '--user'], capture_output=True, text=True)
        
        bot_file_path = os.path.join(bot_folder, "bot.py")
        
        if start_bot_process(bot_id, bot_file_path):
            bots_manager["bots"][bot_id]["status"] = "running"
            save_all()
            
            upload_bot_to_github(bot_folder, bot_name, bot_id)
            
            bot.edit_message_text(
                f"✅ تم رفع وتشغيل البوت الجديد بنجاح!\n\n"
                f"🆔 المعرف: {bot_id}\n"
                f"📝 الاسم: {bot_name}\n"
                f"👤 المالك: {message.from_user.full_name}\n"
                f"📊 الحالة: 🟢 شغال\n"
                f"📅 الأيام المتبقية: {get_user_bot_days(user_id)}",
                status_msg.chat.id,
                status_msg.message_id,
                reply_markup=back_to_admin() if is_admin(user_id) else back_button()
            )
        else:
            bot.edit_message_text(
                f"❌ فشل في تشغيل البوت {bot_id}",
                status_msg.chat.id,
                status_msg.message_id,
                reply_markup=back_button()
            )
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}", reply_markup=back_button())

def show_user_bots(message, user_id):
    user_bots = []
    for bot_id, data in bots_manager.get("bots", {}).items():
        if data.get("user_id") == user_id:
            user_bots.append((bot_id, data))
    
    if not user_bots:
        bot.reply_to(message, "📭 لا يوجد لديك بوتات.", reply_markup=back_button())
        return
    
    text = "<b>🤖 بوتاتي:</b>\n\n"
    for bot_id, data in user_bots:
        status = "🟢 شغال" if bot_id in bots_manager.get("running", []) else "🔴 متوقف"
        text += f"🆔 <code>{bot_id}</code>\n"
        text += f"📝 {data.get('name', 'غير معروف')}\n"
        text += f"📊 {status}\n"
        text += f"📅 {data.get('created', 'غير معروف')[:10]}\n\n"
    
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=back_button())

# ==================== معالجات الأزرار ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    # ===== رجوع =====
    if call.data == "back":
        try:
            if is_admin(user_id):
                welcome_msg = get_welcome_message(user_id, call.from_user.first_name)
                bot.edit_message_text(welcome_msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=admin_panel_keyboard())
            else:
                welcome_msg = get_welcome_message(user_id, call.from_user.first_name)
                bot.edit_message_text(welcome_msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=main_menu_keyboard(user_id))
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== لوحة الأدمن =====
    if call.data == "admin_panel":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            welcome_msg = get_welcome_message(user_id, call.from_user.first_name)
            bot.edit_message_text(welcome_msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=admin_panel_keyboard())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== نقاطي =====
    if call.data == "show_points":
        points = get_user_points(user_id)
        days = get_user_bot_days(user_id)
        
        text = f"""
⭐ <b>نقاطي</b>

💰 النقاط: <b>{points}</b>
📅 أيام البوت: <b>{days}</b>
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_button())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== أيام البوت =====
    if call.data == "show_days":
        days = get_user_bot_days(user_id)
        bot.answer_callback_query(call.id, f"📅 أيام البوت المتبقية: {days} يوم", show_alert=True)
        return
    
    # ===== نشر بوتي =====
    if call.data == "publish_bot":
        text = """
📢 <b>نشر بوتي</b>

━━━━━━━━━━━━━━━━━━
📌 <b>للنشر والتشغيل:</b>

📤 قم برفع ملفات البوت (bot.py + requirements.txt)
💰 اختر الباقة المناسبة
⏳ سيتم تشغيل بوتك فوراً

━━━━━━━━━━━━━━━━━━
💬 <b>للتواصل مع المطور:</b>
<a href='https://t.me/ggzh9'>@ggzh9</a>

📢 <b>قناة المطور:</b>
<a href='{CHANNEL}'>قناة كايو</a>
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_button())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== أسعار الاشتراك =====
    if call.data == "prices":
        text = """
💰 <b>أسعار الاشتراك</b>

━━━━━━━━━━━━━━━━━━
📅 <b>الباقات المتاحة:</b>

• 🟢 <b>أسبوع</b> — 3 أسيا
• 🔵 <b>شهر</b> — 6 أسيا
• 🟣 <b>سنة</b> — 70 أسيا

━━━━━━━━━━━━━━━━━━
💬 <b>للاشتراك والتواصل:</b>
<a href='https://t.me/ggzh9'>@ggzh9</a>

📢 <b>قناة المطور:</b>
<a href='{CHANNEL}'>قناة كايو</a>
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_button())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== رفع بوت =====
    if call.data == "upload_bot":
        if not is_admin(user_id):
            days = get_user_bot_days(user_id)
            if days <= 0:
                keyboard = telebot.types.InlineKeyboardMarkup()
                keyboard.add(
                    create_colored_button("💰 شراء أيام", callback_data="prices", style="success"),
                    create_colored_button("👑 التواصل مع المطور", url="https://t.me/ggzh9", style="primary")
                )
                bot.edit_message_text(
                    "⚠️ ليس لديك أيام بوت كافية!\n\n📌 يمكنك شراء أيام من خلال زر الأسعار.\n📌 أو التواصل مع المطور لتفعيل اشتراكك.",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard
                )
                bot.answer_callback_query(call.id)
                return
        
        try:
            msg = bot.edit_message_text("📤 أرسل ملف البوت (bot.py) لرفعه.", call.message.chat.id, call.message.message_id, reply_markup=back_button())
            bot.register_next_step_handler(msg, process_bot_file)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== بوتاتي =====
    if call.data == "my_bots":
        show_user_bots(call.message, user_id)
        bot.answer_callback_query(call.id)
        return
    
    # ===== إدارة البوتات (للأدمن) =====
    if call.data == "bots_manager_menu":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            bot.edit_message_text(
                f"<b>🤖 إدارة البوتات</b>\n\n📊 إجمالي البوتات: {len(bots_manager.get('bots', {}))}\n🟢 المشغلة: {len(bots_manager.get('running', []))}\n🔴 المتوقفة: {len(bots_manager.get('bots', {})) - len(bots_manager.get('running', []))}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=bots_manager_keyboard()
            )
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_upload_bot":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📤 أرسل ملف البوت (bot.py) لرفعه.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_bot_file)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "bots_list":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        
        bots = bots_manager.get("bots", {})
        if not bots:
            try:
                bot.edit_message_text("📭 لا توجد بوتات.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            except:
                pass
            bot.answer_callback_query(call.id)
            return
        
        text = "<b>🤖 قائمة البوتات:</b>\n\n"
        for bot_id, data in list(bots.items())[:20]:
            status = "🟢 شغال" if bot_id in bots_manager.get("running", []) else "🔴 متوقف"
            text += f"🆔 <code>{bot_id}</code>\n📝 {data.get('name', 'غير معروف')}\n👤 {data.get('username', 'غير معروف')}\n📊 {status}\n\n"
        
        if len(bots) > 20:
            text += f"\n... وعرض {len(bots) - 20} بوتات أخرى"
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_to_admin())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "restart_bot":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📝 أرسل معرف البوت الذي تريد إعادة تشغيله.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_restart_bot)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "stop_bot":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📝 أرسل معرف البوت الذي تريد إيقافه.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_stop_bot)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "delete_bot":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📝 أرسل معرف البوت الذي تريد حذفه.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_delete_bot)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== إذاعة =====
    if call.data == "msg":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📨 أرسل محتوى الإذاعة.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_broadcast)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== إعدادات =====
    if call.data == "abdo":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        
        check_status = bot_data.get("check") == "on"
        upload_status = bot_data.get("upload") == "on"
        folder_status = bot_data.get("folder") == "on"
        numberfiles = bot_data.get("numberfiles", 7)
        numberban = bot_data.get("numberban", 3)
        
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            create_colored_button(f"فحص {'✅' if check_status else '❌'}", callback_data="check", style="success" if check_status else "danger"),
            create_colored_button(f"رفع {'✅' if upload_status else '❌'}", callback_data="upload", style="success" if upload_status else "danger")
        )
        keyboard.add(
            create_colored_button(f"فولدرات {'✅' if folder_status else '❌'}", callback_data="folder", style="success" if folder_status else "danger")
        )
        keyboard.add(
            create_colored_button(f"📄 {numberfiles}", callback_data="set_numberfiles", style="primary"),
            create_colored_button(f"⚠️ {numberban}", callback_data="set_numberban", style="primary")
        )
        keyboard.add(
            create_colored_button("🔙 رجوع", callback_data="admin_panel", style="primary")
        )
        
        try:
            bot.edit_message_text(f"<b>⚙️ إعدادات البوت</b>\n\n{OWNER_TEXT}", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=keyboard)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data in ["check", "upload", "folder"]:
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot_data[call.data] = "off" if bot_data.get(call.data) == "on" else "on"
        save_all()
        bot.answer_callback_query(call.id, f"✅ تم {'تفعيل' if bot_data[call.data]=='on' else 'تعطيل'}")
        
        check_status = bot_data.get("check") == "on"
        upload_status = bot_data.get("upload") == "on"
        folder_status = bot_data.get("folder") == "on"
        numberfiles = bot_data.get("numberfiles", 7)
        numberban = bot_data.get("numberban", 3)
        
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            create_colored_button(f"فحص {'✅' if check_status else '❌'}", callback_data="check", style="success" if check_status else "danger"),
            create_colored_button(f"رفع {'✅' if upload_status else '❌'}", callback_data="upload", style="success" if upload_status else "danger")
        )
        keyboard.add(
            create_colored_button(f"فولدرات {'✅' if folder_status else '❌'}", callback_data="folder", style="success" if folder_status else "danger")
        )
        keyboard.add(
            create_colored_button(f"📄 {numberfiles}", callback_data="set_numberfiles", style="primary"),
            create_colored_button(f"⚠️ {numberban}", callback_data="set_numberban", style="primary")
        )
        keyboard.add(
            create_colored_button("🔙 رجوع", callback_data="admin_panel", style="primary")
        )
        
        try:
            bot.edit_message_text(f"<b>⚙️ إعدادات البوت</b>\n\n{OWNER_TEXT}", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=keyboard)
        except:
            pass
        return
    
    if call.data == "set_numberfiles":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📝 أرسل العدد الجديد للملفات المسموحة.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_set_number, "numberfiles")
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "set_numberban":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📝 أرسل العدد الجديد للتحذيرات.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_set_number, "numberban")
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== إحصائيات =====
    if call.data == "statistics":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        stats = stats_data["stats"]
        msg = (
            "<b>📊 الإحصائيات العامة</b>\n\n"
            f"👥 المستخدمون: <b>{stats['total_users']}</b>\n"
            f"📁 الملفات: <b>{bot_data.get('file', 0)}</b>\n"
            f"🔒 المحظورين: <b>{len(bot_data.get('banned', []))}</b>\n"
            f"⭐ VIP: <b>{len(bot_data.get('promotionn', []))}</b>\n"
            f"👑 الادمنية: <b>{len(bot_data.get('admins', []))}</b>\n"
            f"🤖 البوتات: <b>{len(bots_manager.get('bots', {}))}</b>\n"
            f"🟢 المشغلة: <b>{len(bots_manager.get('running', []))}</b>"
        )
        try:
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_to_admin())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== حظر =====
    if call.data == "ksmblock":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            create_colored_button("🔒 حظر", callback_data="block", style="danger"),
            create_colored_button("🔓 إلغاء حظر", callback_data="unblock", style="success")
        )
        keyboard.add(create_colored_button("📋 المحظورين", callback_data="blocks", style="primary"))
        keyboard.add(create_colored_button("🔙 رجوع", callback_data="admin_panel", style="primary"))
        try:
            bot.edit_message_text("<b>🔒 قسم الحظر</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=keyboard)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "block" or call.data == "unblock":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        mode = "حظره" if call.data == "block" else "إلغاء حظره"
        try:
            msg = bot.edit_message_text(f"📝 أرسل ايدي المستخدم لـ {mode}", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_block_user, call.data)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "blocks":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        banned = bot_data.get("banned", [])
        if not banned:
            text = "📭 لا يوجد محظورين."
        else:
            text = "<b>🚫 المحظورين:</b>\n" + "\n".join([f"🆔 {uid}" for uid in banned])
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_to_admin())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== إدارة الأدمن =====
    if call.data == "ksmadmin":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            create_colored_button("⬆️ رفع ادمن", callback_data="admins", style="success"),
            create_colored_button("⬇️ حذف ادمن", callback_data="unadmins", style="danger")
        )
        keyboard.add(create_colored_button("📋 الادمنية", callback_data="adminss", style="primary"))
        keyboard.add(create_colored_button("🔙 رجوع", callback_data="admin_panel", style="primary"))
        try:
            bot.edit_message_text("<b>👥 قسم الادمنية</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=keyboard)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admins" or call.data == "unadmins":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        mode = "رفعه ادمن" if call.data == "admins" else "حذف ادمنيته"
        try:
            msg = bot.edit_message_text(f"📝 أرسل ايدي المستخدم لـ {mode}", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_admin_user, call.data)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "adminss":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        admins = bot_data.get("admins", [])
        if not admins:
            text = "📭 لا يوجد ادمنية."
        else:
            text = "<b>👥 الادمنية:</b>\n"
            for uid in admins:
                try:
                    chat_member = bot.get_chat_member(uid, uid)
                    name = chat_member.user.full_name
                    text += f"• {name} - 🆔 {uid}\n"
                except:
                    text += f"• 🆔 {uid}\n"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_to_admin())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== إدارة VIP =====
    if call.data == "ksmvip":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            create_colored_button("➕ إضافة VIP", callback_data="addvip", style="success"),
            create_colored_button("➖ حذف VIP", callback_data="removevip", style="danger")
        )
        keyboard.add(create_colored_button("📋 عرض VIP", callback_data="viewvips", style="primary"))
        keyboard.add(create_colored_button("🔙 رجوع", callback_data="admin_panel", style="primary"))
        try:
            bot.edit_message_text("<b>⭐ قسم VIP</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=keyboard)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "addvip" or call.data == "removevip":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        mode = "إضافته إلى VIP" if call.data == "addvip" else "حذفه من VIP"
        try:
            msg = bot.edit_message_text(f"📝 أرسل ايدي المستخدم لـ {mode}", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_vip_user, call.data)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "viewvips":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        vips = bot_data.get("promotionn", [])
        if not vips:
            text = "📭 لا يوجد أعضاء VIP."
        else:
            text = "<b>⭐ أعضاء VIP:</b>\n"
            for uid in vips:
                try:
                    chat_member = bot.get_chat_member(uid, uid)
                    name = chat_member.user.full_name
                    text += f"• {name} - 🆔 {uid}\n"
                except:
                    text += f"• 🆔 {uid}\n"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_to_admin())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== نسخ احتياطي =====
    if call.data == "backup_menu":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(create_colored_button("📦 إنشاء نسخة", callback_data="create_backup", style="success"))
        keyboard