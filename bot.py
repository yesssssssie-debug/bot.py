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
API_TOKEN = os.environ.get("API_TOKEN", "7999963241:AAHBao1UN5tFQOyP9GkYr7Yfprg2WR1oGhw")
ADMIN_ID = 7947679527
DEVELOPER = "@ggzh9"
CHANNEL = "https://t.me/kayo_i"
BOT_CHANNEL = "https://t.me/botkayo"

# إعدادات GitHub
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "yesssssssie-debug/bot-kayo")

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
    c.execute('''CREATE TABLE IF NOT EXISTS user_points (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, bot_days INTEGER DEFAULT 0, last_daily TEXT, level TEXT DEFAULT "برونز")''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (referrer_id INTEGER, referred_id INTEGER, points_earned INTEGER DEFAULT 50, date TEXT, PRIMARY KEY (referrer_id, referred_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (channel_id TEXT PRIMARY KEY, channel_name TEXT, points INTEGER DEFAULT 10)''')
    c.execute('''CREATE TABLE IF NOT EXISTS channel_subscriptions (user_id INTEGER, channel_id TEXT, subscribed_date TEXT, points_earned INTEGER DEFAULT 10, PRIMARY KEY (user_id, channel_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, file_name TEXT, file_path TEXT, file_hash TEXT, file_size INTEGER, upload_date TEXT, file_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS warnings (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_challenges (user_id INTEGER PRIMARY KEY, last_daily TEXT, streak INTEGER DEFAULT 0)''')
    
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
    """رفع ملف إلى GitHub"""
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN غير موجود")
        return False
    
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        
        with open(file_path, "rb") as f:
            content = f.read()
        
        encoded_content = base64.b64encode(content).decode("utf-8")
        path_in_repo = f"bots/{file_name}"
        
        try:
            contents = repo.get_contents(path_in_repo)
            repo.update_file(
                path_in_repo,
                commit_message,
                encoded_content,
                contents.sha,
                branch="main"
            )
        except:
            repo.create_file(
                path_in_repo,
                commit_message,
                encoded_content,
                branch="main"
            )
        
        print(f"✅ تم رفع الملف {file_name} إلى GitHub")
        return True
    except Exception as e:
        print(f"❌ خطأ في رفع الملف إلى GitHub: {e}")
        return False

def upload_bot_to_github(bot_folder: str, bot_id: str):
    """رفع مجلد البوت بالكامل إلى GitHub"""
    try:
        bot_file = os.path.join(bot_folder, "bot.py")
        if os.path.exists(bot_file):
            upload_to_github(bot_file, f"{bot_id}/bot.py", f"رفع بوت {bot_id}")
        
        req_file = os.path.join(bot_folder, "requirements.txt")
        if os.path.exists(req_file):
            upload_to_github(req_file, f"{bot_id}/requirements.txt", f"رفع متطلبات {bot_id}")
        
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

def get_user_level(user_id: int) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT level FROM user_points WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else "برونز"
    except:
        return "برونز"

def update_user_level(user_id: int):
    points = get_user_points(user_id)
    if points >= 5000:
        level = "بلاتيني"
    elif points >= 2000:
        level = "ذهبي"
    elif points >= 500:
        level = "فضي"
    else:
        level = "برونز"
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE user_points SET level = ? WHERE user_id = ?", (level, user_id))
        conn.commit()
        conn.close()
    except:
        pass
    return level

def get_daily_challenge(user_id: int) -> Dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT last_daily, streak FROM daily_challenges WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            return {"last_daily": result[0], "streak": result[1]}
        return {"last_daily": None, "streak": 0}
    except:
        return {"last_daily": None, "streak": 0}

def update_daily_challenge(user_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    data = get_daily_challenge(user_id)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if data["last_daily"] == today:
            conn.close()
            return False
        
        if data["last_daily"] == (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"):
            streak = data["streak"] + 1
        else:
            streak = 1
        
        c.execute("REPLACE INTO daily_challenges (user_id, last_daily, streak) VALUES (?, ?, ?)", 
                  (user_id, today, streak))
        conn.commit()
        conn.close()
        
        bonus = 10 + (streak * 2)
        add_user_points(user_id, bonus)
        return True
    except:
        return False

# ==================== دوال قنوات الاشتراك ====================
def get_all_subscription_channels() -> List[Dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT channel_id, channel_name, points FROM subscriptions")
        results = c.fetchall()
        conn.close()
        return [{"id": r[0], "name": r[1] or r[0], "points": r[2] if r[2] else 10} for r in results]
    except:
        return []

def add_subscription_channel(channel_id: str, channel_name: str, points: int = 10):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("REPLACE INTO subscriptions (channel_id, channel_name, points) VALUES (?, ?, ?)",
                  (channel_id, channel_name, points))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def remove_subscription_channel(channel_id: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM subscriptions WHERE channel_id = ?", (channel_id,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_channel_subscriptions(user_id: int) -> List[str]:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT channel_id FROM channel_subscriptions WHERE user_id = ?", (user_id,))
        results = c.fetchall()
        conn.close()
        return [r[0] for r in results]
    except:
        return []

def add_channel_subscription(user_id: int, channel_id: str) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM channel_subscriptions WHERE user_id = ? AND channel_id = ?", (user_id, channel_id))
        if c.fetchone():
            conn.close()
            return False
        c.execute("INSERT INTO channel_subscriptions (user_id, channel_id, subscribed_date) VALUES (?, ?, ?)",
                  (user_id, channel_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        add_user_points(user_id, 10)
        return True
    except:
        return False

def check_user_subscription(user_id: int, channel_id: str) -> bool:
    try:
        chat_member = bot.get_chat_member(int(channel_id), user_id)
        return chat_member.status in ["member", "administrator", "creator"]
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
    level = get_user_level(user_id)
    
    keyboard.add(
        create_colored_button(f"⭐ نقاطي: {points}", callback_data="show_points", style="primary"),
        create_colored_button(f"📅 أيام البوت: {days}", callback_data="show_days", style="success")
    )
    keyboard.add(
        create_colored_button("📤 رفع بوت", callback_data="upload_bot", style="success"),
        create_colored_button("📁 بوتاتي", callback_data="my_bots", style="primary")
    )
    keyboard.add(
        create_colored_button("🎁 تجميع نقاط", callback_data="points_menu", style="primary")
    )
    keyboard.add(
        create_colored_button("📢 نشر بوتي", callback_data="publish_bot", style="primary"),
        create_colored_button(f"🏆 مستواي: {level}", callback_data="my_level", style="primary")
    )
    keyboard.add(
        create_colored_button("📅 تحديات يومية", callback_data="daily_challenge", style="success"),
        create_colored_button("👑 المطور", url="https://t.me/ggzh9", style="primary")
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
        create_colored_button("📢 قنوات الاشتراك", callback_data="admin_subscriptions", style="primary")
    )
    keyboard.add(
        create_colored_button("👑 المطور", url="https://t.me/ggzh9", style="primary"),
        create_colored_button("📢 القناة", url=CHANNEL, style="primary")
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

def points_menu_keyboard(user_id: int):
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    points = get_user_points(user_id)
    days = get_user_bot_days(user_id)
    ref_count = get_referral_count(user_id)
    level = get_user_level(user_id)
    
    keyboard.add(
        create_colored_button(f"⭐ نقاطي: {points}", callback_data="show_points", style="primary"),
        create_colored_button(f"📅 أيامي: {days}", callback_data="show_days", style="success")
    )
    keyboard.add(
        create_colored_button("📤 رابط دعوة (+50)", callback_data="referral_link", style="success"),
        create_colored_button("📢 اشتراك قنوات (+10)", callback_data="subscription_channels", style="primary")
    )
    keyboard.add(
        create_colored_button("🛒 شراء أيام", callback_data="buy_days", style="primary"),
        create_colored_button(f"👥 المدعوين: {ref_count}", callback_data="referral_count", style="primary")
    )
    keyboard.add(
        create_colored_button(f"🏆 مستواي: {level}", callback_data="my_level", style="primary"),
        create_colored_button("🔙 رجوع", callback_data="back", style="primary")
    )
    return keyboard

def buy_days_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        create_colored_button("📅 يوم واحد - 100 نقطة", callback_data="buy_1day", style="primary"),
        create_colored_button("📅 3 أيام - 280 نقطة", callback_data="buy_3days", style="primary")
    )
    keyboard.add(
        create_colored_button("📅 أسبوع - 650 نقطة", callback_data="buy_7days", style="success"),
        create_colored_button("📅 شهر - 2500 نقطة", callback_data="buy_30days", style="success")
    )
    keyboard.add(
        create_colored_button("🔙 رجوع", callback_data="points_menu", style="primary")
    )
    return keyboard

def subscription_channels_keyboard(user_id: int):
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    channels = get_all_subscription_channels()
    
    if not channels:
        keyboard.add(create_colored_button("📭 لا توجد قنوات", callback_data="no_channels", style="primary"))
    else:
        subscribed = get_channel_subscriptions(user_id)
        for channel in channels:
            is_sub = channel["id"] in subscribed
            status = "✅" if is_sub else "❌"
            keyboard.add(
                create_colored_button(
                    f"{status} {channel['name']} (+{channel['points']} نقطة)",
                    callback_data=f"sub_channel:{channel['id']}",
                    style="success" if is_sub else "primary"
                )
            )
    
    keyboard.add(create_colored_button("🔙 رجوع", callback_data="points_menu", style="primary"))
    return keyboard

def admin_subscriptions_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    channels = get_all_subscription_channels()
    
    if not channels:
        keyboard.add(create_colored_button("📭 لا توجد قنوات", callback_data="no_channels", style="primary"))
    else:
        for channel in channels:
            keyboard.add(
                create_colored_button(f"🗑 {channel['name']}", callback_data=f"remove_channel:{channel['id']}", style="danger")
            )
    
    keyboard.add(create_colored_button("➕ إضافة قناة", callback_data="add_channel", style="success"))
    keyboard.add(create_colored_button("🔙 رجوع", callback_data="admin_panel", style="primary"))
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
        process = subprocess.Popen(['python3', bot_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=os.path.dirname(bot_file) or ".")
        with process_lock:
            running_processes[bot_id] = {'process': process, 'pid': process.pid, 'started': datetime.now().isoformat(), 'status': 'running'}
            if "processes" not in bots_manager:
                bots_manager["processes"] = {}
            bots_manager["processes"][bot_id] = {'pid': process.pid, 'started': datetime.now().isoformat()}
            if bot_id not in bots_manager.get("running", []):
                if "running" not in bots_manager:
                    bots_manager["running"] = []
                bots_manager["running"].append(bot_id)
            if bot_id in bots_manager.get("bots", {}):
                bots_manager["bots"][bot_id]["status"] = "running"
            save_all()
        return True
    except:
        return False

def stop_bot_process(bot_id: str) -> bool:
    try:
        with process_lock:
            if bot_id in running_processes:
                process = running_processes[bot_id]['process']
                if process.poll() is None:
                    process.terminate()
                    time.sleep(2)
                    if process.poll() is None:
                        process.kill()
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
            with process_lock:
                for bot_id in list(running_processes.keys()):
                    process_info = running_processes.get(bot_id)
                    if process_info:
                        process = process_info['process']
                        if process.poll() is not None:
                            running_processes.pop(bot_id, None)
                            if bot_id in bots_manager.get("running", []):
                                bots_manager["running"].remove(bot_id)
                            if bot_id in bots_manager.get("bots", {}):
                                bot_file = os.path.join(BOTS_PATH, bots_manager["bots"][bot_id]["file"])
                                if os.path.exists(bot_file):
                                    start_bot_process(bot_id, bot_file)
            time.sleep(10)
        except:
            time.sleep(30)

# ==================== رسالة الترحيب ====================
def get_welcome_message(user_id: int, first_name: str) -> str:
    points = get_user_points(user_id)
    days = get_user_bot_days(user_id)
    level = get_user_level(user_id)
    
    return f"""
🌟 <b>اهلاً بك في استضافه بوتات كايو</b> 🌟

━━━━━━━━━━━━━━━━━━
👤 <b>الاسم:</b> {first_name}
🆔 <b>ايديك:</b> <code>{user_id}</code>
🏆 <b>مستواك:</b> {level}
⭐ <b>نقاطك:</b> {points}
📅 <b>أيام البوت:</b> {days}
━━━━━━━━━━━━━━━━━━

<b>📌 ماذا يمكنك أن تفعل؟</b>
• 🚀 رفع وتشغيل بوتات تليجرام
• 🎁 جمع النقاط من الدعوات والاشتراكات
• 📅 شراء أيام إضافية لرفع البوتات
• 🏆 رفع مستواك للحصول على مكافآت

<b>📢 قنواتنا:</b>
👑 <b>المطور:</b> <a href='https://t.me/ggzh9'>Click here</a>
📢 <b>قناة المطور:</b> <a href='{CHANNEL}'>Click here</a>
📢 <b>قناة البوت:</b> <a href='{BOT_CHANNEL}'>Click here</a>

━━━━━━━━━━━━━━━━━━
💡 <i>ابدأ برفع بوتك الأول الآن!</i>
"""

# ==================== الأوامر ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    create_folder_if_needed(user_id)
    
    # معالجة رابط الدعوة
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
    ref_count = get_referral_count(user_id)
    level = get_user_level(user_id)
    
    text = f"""
⭐ <b>نقاطي</b>

💰 النقاط: <b>{points}</b>
📅 أيام البوت: <b>{days}</b>
👥 عدد المدعوين: <b>{ref_count}</b>
🏆 مستواي: <b>{level}</b>

━━━━━━━━━━━━━━━━━━
📌 <b>طرق جمع النقاط:</b>
• دعوة صديق: +50 نقطة
• الاشتراك في قناة: +10 نقاط
• التحدي اليومي: +10 نقاط + مكافأة الاستمرار

🛒 <b>شراء الأيام:</b>
• يوم واحد: 100 نقطة
• 3 أيام: 280 نقطة
• أسبوع: 650 نقطة
• شهر: 2500 نقطة
"""
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=points_menu_keyboard(user_id))

@bot.message_handler(commands=['referral'])
def referral_cmd(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    count = get_referral_count(user_id)
    
    text = f"""
🎁 <b>رابط الدعوة الخاص بك</b>

🔗 <code>{link}</code>

📊 عدد المدعوين: <b>{count}</b>
💰 النقاط المكتسبة: <b>{count * 50}</b>

📌 <i>كل مدعو يمنحك 50 نقطة!</i>
"""
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=back_button())

@bot.message_handler(commands=['my_bots'])
def my_bots_cmd(message):
    user_id = message.from_user.id
    show_user_bots(message, user_id)

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
                create_colored_button("🛒 شراء أيام", callback_data="buy_days", style="success"),
                create_colored_button("🎁 تجميع نقاط", callback_data="points_menu", style="primary")
            )
            bot.reply_to(
                message,
                "⚠️ ليس لديك أيام بوت كافية!\n\n"
                "📌 يمكنك الحصول على أيام عن طريق:\n"
                "• دعوة أصدقائك (50 نقطة لكل دعوة)\n"
                "• الاشتراك في القنوات (10 نقاط لكل قناة)\n"
                "• التحدي اليومي (نقاط يومية)\n"
                "• شراء أيام باستخدام النقاط",
                reply_markup=keyboard
            )
            return
    
    if bot_data.get("upload") != "on" and not is_admin(user_id):
        bot.reply_to(message, "⛔ رفع البوتات معطل حالياً")
        return
    
    msg = bot.reply_to(
        message,
        "📤 أرسل ملف البوت (bot.py) لرفعه.\n\n"
        "📌 سيتم تثبيت المتطلبات وتشغيله تلقائياً.\n"
        f"📅 الأيام المتبقية: {get_user_bot_days(user_id)}",
        reply_markup=back_button()
    )
    bot.register_next_step_handler(msg, process_bot_file)

# ==================== رفع البوتات (الميزة الجديدة مع GitHub) ====================
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
        
        # إنشاء مجلد للبوت
        bot_folder = os.path.join(BOTS_PATH, bot_id)
        os.makedirs(bot_folder, exist_ok=True)
        
        # حفظ ملف البوت
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
        bot.register_next_step_handler(msg, process_requirements_file, bot_id, bot_folder)
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}", reply_markup=back_button())

def process_requirements_file(message, bot_id, bot_folder):
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
        
        # تثبيت المتطلبات
        subprocess.run(['pip', 'install', '-r', req_file_path, '--user'], capture_output=True, text=True)
        
        bot_file_path = os.path.join(bot_folder, "bot.py")
        
        if start_bot_process(bot_id, bot_file_path):
            bots_manager["bots"][bot_id]["status"] = "running"
            save_all()
            
            # رفع البوت إلى GitHub
            upload_bot_to_github(bot_folder, bot_id)
            
            bot.edit_message_text(
                f"✅ تم رفع وتشغيل البوت الجديد بنجاح!\n\n"
                f"🆔 المعرف: {bot_id}\n"
                f"📝 الاسم: {bots_manager['bots'][bot_id]['name']}\n"
                f"👤 المالك: {message.from_user.full_name}\n"
                f"📊 الحالة: 🟢 شغال\n"
                f"📅 الأيام المتبقية: {get_user_bot_days(user_id)}\n"
                f"📁 تم رفعه إلى GitHub",
                status_msg.chat.id,
                status_msg.message_id,
                reply_markup=back_to_admin() if is_admin(user_id) else back_button()
            )
        else:
            bot.edit_message_text(
                f"❌ فشل في تشغيل البوت {bot_id}\n\n"
                f"⚠️ تأكد من تشغيل البوت على سيرفر وليس هاتف.",
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
        bot.reply_to(message, "📭 لا يوجد لديك بوتات.\n\n📤 استخدم /upload_bot لرفع بوت جديد.", reply_markup=back_button())
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
        ref_count = get_referral_count(user_id)
        level = get_user_level(user_id)
        
        text = f"""
⭐ <b>نقاطي</b>

💰 النقاط: <b>{points}</b>
📅 أيام البوت: <b>{days}</b>
👥 عدد المدعوين: <b>{ref_count}</b>
🏆 مستواي: <b>{level}</b>
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=points_menu_keyboard(user_id))
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== أيام البوت =====
    if call.data == "show_days":
        days = get_user_bot_days(user_id)
        bot.answer_callback_query(call.id, f"📅 أيام البوت المتبقية: {days} يوم", show_alert=True)
        return
    
    # ===== قائمة النقاط (تجميع نقاط) =====
    if call.data == "points_menu":
        points = get_user_points(user_id)
        days = get_user_bot_days(user_id)
        ref_count = get_referral_count(user_id)
        level = get_user_level(user_id)
        
        text = f"""
🎁 <b>تجميع نقاط</b>

💰 نقاطي: <b>{points}</b>
📅 أيامي: <b>{days}</b>
👥 المدعوين: <b>{ref_count}</b>
🏆 مستواي: <b>{level}</b>

━━━━━━━━━━━━━━━━━━
📌 <b>طرق تجميع النقاط:</b>
• 📤 دعوة صديق: +50 نقطة
• 📢 الاشتراك في قناة: +10 نقاط
• 📅 التحدي اليومي: +10 نقاط + مكافأة الاستمرار

🛒 <b>شراء الأيام:</b>
• يوم واحد: 100 نقطة
• 3 أيام: 280 نقطة
• أسبوع: 650 نقطة
• شهر: 2500 نقطة
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=points_menu_keyboard(user_id))
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== عدد المدعوين =====
    if call.data == "referral_count":
        count = get_referral_count(user_id)
        bot.answer_callback_query(call.id, f"👥 عدد المدعوين: {count}")
        return
    
    # ===== رابط الدعوة =====
    if call.data == "referral_link":
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        count = get_referral_count(user_id)
        
        text = f"""
🎁 <b>رابط الدعوة الخاص بك</b>

🔗 <code>{link}</code>

📊 عدد المدعوين: <b>{count}</b>
💰 النقاط المكتسبة: <b>{count * 50}</b>

📌 <i>كل مدعو يمنحك 50 نقطة!</i>
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=points_menu_keyboard(user_id))
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== قنوات الاشتراك (تجميع نقاط) =====
    if call.data == "subscription_channels":
        channels = get_all_subscription_channels()
        if not channels:
            text = "📭 لا توجد قنوات اشتراك متاحة حالياً."
        else:
            text = "📢 <b>قنوات الاشتراك</b>\n\n"
            text += "📌 اشترك في القنوات التالية واحصل على نقاط!\n"
            text += "• كل قناة تمنحك 10 نقاط\n\n"
            for channel in channels:
                text += f"📌 {channel['name']}\n"
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=subscription_channels_keyboard(user_id))
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== اشتراك قناة (مع التحقق) =====
    if call.data.startswith("sub_channel:"):
        channel_id = call.data.split(":", 1)[1]
        
        if check_user_subscription(user_id, channel_id):
            if add_channel_subscription(user_id, channel_id):
                bot.answer_callback_query(call.id, "✅ تم الاشتراك! +10 نقاط", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "⚠️ أنت مشترك بالفعل في هذه القناة!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ يرجى الاشتراك في القناة أولاً!", show_alert=True)
        
        channels = get_all_subscription_channels()
        if not channels:
            text = "📭 لا توجد قنوات اشتراك متاحة حالياً."
        else:
            text = "📢 <b>قنوات الاشتراك</b>\n\n"
            text += "📌 اشترك في القنوات التالية واحصل على نقاط!\n"
            text += "• كل قناة تمنحك 10 نقاط\n\n"
            for channel in channels:
                text += f"📌 {channel['name']}\n"
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=subscription_channels_keyboard(user_id))
        except:
            pass
        return
    
    # ===== مستواي =====
    if call.data == "my_level":
        level = get_user_level(user_id)
        points = get_user_points(user_id)
        
        if level == "برونز":
            next_level = "فضي"
            points_needed = 500 - points
        elif level == "فضي":
            next_level = "ذهبي"
            points_needed = 2000 - points
        elif level == "ذهبي":
            next_level = "بلاتيني"
            points_needed = 5000 - points
        else:
            next_level = "الحد الأقصى"
            points_needed = 0
        
        text = f"""
🏆 <b>مستواي</b>

مستواك الحالي: <b>{level}</b>
💰 نقاطك: <b>{points}</b>

📌 <b>مميزات كل مستوى:</b>
• 🥉 برونز: 0-500 نقطة (مميزات أساسية)
• 🥈 فضي: 500-2000 نقطة (خصم 5% على الأيام)
• 🥇 ذهبي: 2000-5000 نقطة (خصم 10% + مميزات إضافية)
• 💎 بلاتيني: 5000+ نقطة (خصم 15% + مميزات حصرية)

"""
        if points_needed > 0:
            text += f"🎯 النقاط المطلوبة للوصول إلى {next_level}: <b>{points_needed}</b> نقطة"
        else:
            text += "🎉 أنت في أعلى مستوى!"
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=points_menu_keyboard(user_id))
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== التحدي اليومي =====
    if call.data == "daily_challenge":
        data = get_daily_challenge(user_id)
        
        if data["last_daily"] == datetime.now().strftime("%Y-%m-%d"):
            text = f"""
📅 <b>التحدي اليومي</b>

✅ لقد قمت بالتحدي اليومي اليوم!
🔥 سلسلة التحديات: <b>{data['streak']}</b> يوم
📅 استمر في التحدي غداً للحصول على مكافآت أكبر!
"""
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=points_menu_keyboard(user_id))
            except:
                pass
            bot.answer_callback_query(call.id)
            return
        
        if update_daily_challenge(user_id):
            new_data = get_daily_challenge(user_id)
            bonus = 10 + (new_data["streak"] * 2)
            text = f"""
📅 <b>التحدي اليومي</b>

✅ تم إكمال التحدي اليومي بنجاح!
🎁 المكافأة: <b>{bonus}</b> نقطة
🔥 سلسلة التحديات: <b>{new_data['streak']}</b> يوم

📌 كل يوم استمرار يزيد المكافأة بمقدار 2 نقطة!
"""
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=points_menu_keyboard(user_id))
            except:
                pass
            bot.answer_callback_query(call.id, "✅ تم إكمال التحدي! +نقاط", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ حدث خطأ، حاول مرة أخرى", show_alert=True)
        return
    
    # ===== شراء أيام =====
    if call.data == "buy_days":
        points = get_user_points(user_id)
        level = get_user_level(user_id)
        
        discount = 0
        if level == "فضي":
            discount = 5
        elif level == "ذهبي":
            discount = 10
        elif level == "بلاتيني":
            discount = 15
        
        text = f"""
🛒 <b>شراء أيام البوت</b>

💰 نقاطك الحالية: <b>{points}</b>
🏆 مستواك: <b>{level}</b>
🎁 الخصم: <b>{discount}%</b>

📅 <b>الأسعار بعد الخصم:</b>
• يوم واحد: {100 - (100 * discount // 100)} نقطة
• 3 أيام: {280 - (280 * discount // 100)} نقطة
• أسبوع: {650 - (650 * discount // 100)} نقطة
• شهر: {2500 - (2500 * discount // 100)} نقطة
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=buy_days_keyboard())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== شراء يوم =====
    if call.data.startswith("buy_"):
        level = get_user_level(user_id)
        
        discount = 0
        if level == "فضي":
            discount = 5
        elif level == "ذهبي":
            discount = 10
        elif level == "بلاتيني":
            discount = 15
        
        if "1day" in call.data:
            days = 1
            cost = 100 - (100 * discount // 100)
        elif "3days" in call.data:
            days = 3
            cost = 280 - (280 * discount // 100)
        elif "7days" in call.data:
            days = 7
            cost = 650 - (650 * discount // 100)
        elif "30days" in call.data:
            days = 30
            cost = 2500 - (2500 * discount // 100)
        else:
            days = 1
            cost = 100 - (100 * discount // 100)
        
        points = get_user_points(user_id)
        
        if points < cost:
            bot.answer_callback_query(call.id, f"❌ ليس لديك نقاط كافية! تحتاج {cost} نقطة", show_alert=True)
            return
        
        add_user_points(user_id, -cost)
        add_user_bot_days(user_id, days)
        
        new_points = get_user_points(user_id)
        new_days = get_user_bot_days(user_id)
        
        text = f"""
✅ <b>تم الشراء بنجاح!</b>

📅 تم إضافة <b>{days}</b> أيام
💰 النقاط المتبقية: <b>{new_points}</b>
📅 أيام البوت: <b>{new_days}</b>
🏆 مستواك: <b>{level}</b>
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=points_menu_keyboard(user_id))
        except:
            pass
        bot.answer_callback_query(call.id, "✅ تم الشراء بنجاح!", show_alert=True)
        return
    
    # ===== نشر بوتي =====
    if call.data == "publish_bot":
        points = get_user_points(user_id)
        days = get_user_bot_days(user_id)
        level = get_user_level(user_id)
        
        discount = 0
        if level == "فضي":
            discount = 5
        elif level == "ذهبي":
            discount = 10
        elif level == "بلاتيني":
            discount = 15
        
        text = f"""
📢 <b>نشر بوتي</b>

━━━━━━━━━━━━━━━━━━
📊 <b>إحصائياتك:</b>
💰 نقاطك: <b>{points}</b>
📅 أيام البوت: <b>{days}</b>
🏆 مستواك: <b>{level}</b>
🎁 خصمك: <b>{discount}%</b>
━━━━━━━━━━━━━━━━━━

📌 <b>أسعار الأيام مع الخصم:</b>
• 📅 يوم واحد: {100 - (100 * discount // 100)} نقطة
• 📅 3 أيام: {280 - (280 * discount // 100)} نقطة
• 📅 أسبوع: {650 - (650 * discount // 100)} نقطة
• 📅 شهر: {2500 - (2500 * discount // 100)} نقطة

💡 <b>ملاحظة:</b>
• كل 100 نقطة = يوم واحد لرفع البوتات
• يمكنك جمع النقاط عبر الدعوات والاشتراكات
• المستوى الأعلى = خصم أكبر على الأيام
"""
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=buy_days_keyboard())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== بوتاتي =====
    if call.data == "my_bots":
        show_user_bots(call.message, user_id)
        bot.answer_callback_query(call.id)
        return
    
    # ===== رفع بوت =====
    if call.data == "upload_bot":
        if not is_admin(user_id):
            days = get_user_bot_days(user_id)
            if days <= 0:
                bot.answer_callback_query(call.id, "❌ ليس لديك أيام كافية! استخدم /points للشراء", show_alert=True)
                return
        
        try:
            msg = bot.edit_message_text("📤 أرسل ملف البوت (bot.py) لرفعه.\n\n📌 سيتم تثبيت المتطلبات وتشغيله تلقائياً.", call.message.chat.id, call.message.message_id, reply_markup=back_button())
            bot.register_next_step_handler(msg, process_bot_file)
        except:
            pass
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
            msg = bot.edit_message_text("📤 أرسل ملف البوت (bot.py) لرفعه.\n\n📌 سيتم تثبيت المتطلبات وتشغيله تلقائياً.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
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
    
    # ===== إدارة قنوات الاشتراك (للأدمن فقط) =====
    if call.data == "admin_subscriptions":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            bot.edit_message_text("📢 <b>إدارة قنوات الاشتراك</b>\n\n📌 هنا يمكنك إضافة أو حذف قنوات الاشتراك.\n📌 يجب أن يكون البوت أدمن في القناة للتحقق من الاشتراك.", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=admin_subscriptions_keyboard())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "add_channel":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📝 أرسل معرف القناة (مثال: @channel_username)\n\n📌 تأكد من أن البوت أدمن في القناة.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
            bot.register_next_step_handler(msg, process_add_channel)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("remove_channel:"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        channel_id = call.data.split(":", 1)[1]
        remove_subscription_channel(channel_id)
        bot.answer_callback_query(call.id, "✅ تم حذف القناة", show_alert=True)
        try:
            bot.edit_message_text("📢 <b>إدارة قنوات الاشتراك</b>\n\n📌 هنا يمكنك إضافة أو حذف قنوات الاشتراك.\n📌 يجب أن يكون البوت أدمن في القناة للتحقق من الاشتراك.", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=admin_subscriptions_keyboard())
        except:
            pass
        return
    
    # ===== إذاعة =====
    if call.data == "msg":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            msg = bot.edit_message_text("📨 أرسل محتوى الإذاعة.\n\n📌 يدعم: نص، صورة، فيديو، مستند، صوت.", call.message.chat.id, call.message.message_id, reply_markup=back_to_admin())
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
        keyboard.add(create_colored_button("📋 عرض النسخ", callback_data="list_backups", style="primary"))
        keyboard.add(create_colored_button("🔙 رجوع", callback_data="admin_panel", style="primary"))
        try:
            bot.edit_message_text("<b>📦 قسم النسخ الاحتياطي</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=keyboard)
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "create_backup":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            bot.edit_message_text("⏳ جاري إنشاء النسخة الاحتياطية...", call.message.chat.id, call.message.message_id)
        except:
            pass
        backup_file = create_backup()
        try:
            bot.edit_message_text(f"✅ تم إنشاء النسخة الاحتياطية:\n<code>{os.path.basename(backup_file)}</code>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_to_admin())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "list_backups":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        backups = sorted([f for f in os.listdir(BACKUP_PATH) if f.endswith('.json')])
        if not backups:
            text = "📭 لا توجد نسخ احتياطية."
        else:
            text = "<b>📦 النسخ الاحتياطية:</b>\n"
            for i, b in enumerate(backups, 1):
                size = os.path.getsize(os.path.join(BACKUP_PATH, b)) / 1024
                text += f"{i}. {b} - {size:.1f} كيلوبايت\n"
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=back_to_admin())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    # ===== إحصائيات البوتات =====
    if call.data == "bots_total":
        bot.answer_callback_query(call.id, f"📊 إجمالي البوتات: {len(bots_manager.get('bots', {}))}")
        return
    
    if call.data == "bots_running":
        bot.answer_callback_query(call.id, f"🟢 البوتات المشغلة: {len(bots_manager.get('running', []))}")
        return
    
    if call.data == "no_channels":
        bot.answer_callback_query(call.id, "📭 لا توجد قنوات")
        return
    
    bot.answer_callback_query(call.id, "⚠️ جاري التطوير...")

# ==================== دوال المعالجة الإضافية ====================
def process_add_channel(message):
    """إضافة قناة اشتراك (للأدمن فقط)"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    channel_input = message.text.strip()
    channel_id = None
    channel_name = channel_input
    
    if channel_input.startswith('@'):
        try:
            chat = bot.get_chat(channel_input)
            channel_id = str(chat.id)
            channel_name = chat.title or channel_input
        except:
            bot.reply_to(message, "❌ لم أتمكن من العثور على القناة.", reply_markup=back_to_admin())
            return
    elif channel_input.startswith('-100'):
        channel_id = channel_input
        try:
            chat = bot.get_chat(int(channel_id))
            channel_name = chat.title or channel_id
        except:
            pass
    else:
        try:
            chat = bot.get_chat(int(channel_input))
            channel_id = str(chat.id)
            channel_name = chat.title or channel_input
        except:
            bot.reply_to(message, "❌ معرف القناة غير صحيح.", reply_markup=back_to_admin())
            return
    
    if not channel_id:
        bot.reply_to(message, "❌ لم أتمكن من استخراج معرف القناة.", reply_markup=back_to_admin())
        return
    
    try:
        bot_member = bot.get_chat_member(int(channel_id), bot.get_me().id)
        if bot_member.status not in ["administrator", "creator"]:
            bot.reply_to(message, "❌ البوت ليس أدمن في هذه القناة! يرجى رفع البوت مشرفاً في القناة.", reply_markup=back_to_admin())
            return
    except:
        bot.reply_to(message, "❌ لا يمكن التحقق من صلاحيات البوت في القناة.", reply_markup=back_to_admin())
        return
    
    add_subscription_channel(channel_id, channel_name)
    
    bot.reply_to(
        message,
        f"✅ تم إضافة القناة <b>{channel_name}</b> بنجاح!\n"
        f"🆔 المعرف: <code>{channel_id}</code>\n"
        f"📌 أصبحت القناة متاحة في قسم تجميع النقاط.",
        parse_mode="HTML",
        reply_markup=back_to_admin()
    )

def process_broadcast(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    targets = stats_data["users"]
    if not targets:
        bot.reply_to(message, "❌ لا يوجد مستهدفون للإذاعة.", reply_markup=back_to_admin())
        return
    
    status_msg = bot.reply_to(message, f"⏳ جاري بدء الإذاعة لـ {len(targets)} مستخدم...")
    
    succeeded = 0
    failed = 0
    
    for target in targets[:100]:
        try:
            if message.text:
                bot.send_message(target, message.text)
            elif message.photo:
                bot.send_photo(target, message.photo[-1].file_id, caption=message.caption)
            elif message.document:
                bot.send_document(target, message.document.file_id, caption=message.caption)
            elif message.video:
                bot.send_video(target, message.video.file_id, caption=message.caption)
            elif message.audio:
                bot.send_audio(target, message.audio.file_id, caption=message.caption)
            elif message.voice:
                bot.send_voice(target, message.voice.file_id, caption=message.caption)
            elif message.sticker:
                bot.send_sticker(target, message.sticker.file_id)
            succeeded += 1
        except:
            failed += 1
        time.sleep(0.1)
    
    try:
        bot.edit_message_text(
            f"✅ اكتملت الإذاعة\n• تم الإرسال: {succeeded}\n• فشل: {failed}",
            status_msg.chat.id,
            status_msg.message_id,
            reply_markup=back_to_admin()
        )
    except:
        pass

def process_set_number(message, key):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        bot.reply_to(message, "⚠️ يرجى إرسال رقم صحيح موجب.", reply_markup=back_to_admin())
        return
    bot_data[key] = int(text)
    save_all()
    bot.reply_to(message, f"✅ تم تعيين العدد الجديد: <b>{bot_data[key]}</b>", parse_mode="HTML", reply_markup=back_to_admin())

def process_block_user(message, mode):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    target_id_str = message.text.strip()
    if not re.match(r'\b\d{8,12}\b', target_id_str):
        bot.reply_to(message, "❌ ايدي غير صحيح.", reply_markup=back_to_admin())
        return
    target_id = int(target_id_str)
    
    if mode == "block":
        if target_id in bot_data.get("banned", []):
            bot.reply_to(message, "⚠️ المستخدم محظور بالفعل.", reply_markup=back_to_admin())
            return
        bot_data["banned"].append(target_id)
        bot.reply_to(message, f"✅ تم حظر المستخدم.", reply_markup=back_to_admin())
    else:
        if target_id not in bot_data.get("banned", []):
            bot.reply_to(message, "⚠️ المستخدم غير محظور.", reply_markup=back_to_admin())
            return
        bot_data["banned"].remove(target_id)
        bot.reply_to(message, f"✅ تم إلغاء حظر المستخدم.", reply_markup=back_to_admin())
    save_all()

def process_admin_user(message, mode):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    target_id_str = message.text.strip()
    if not re.match(r'\b\d{8,12}\b', target_id_str):
        bot.reply_to(message, "❌ ايدي غير صحيح.", reply_markup=back_to_admin())
        return
    target_id = int(target_id_str)
    
    if mode == "admins":
        if target_id in bot_data.get("admins", []):
            bot.reply_to(message, "⚠️ المستخدم بالفعل ادمن.", reply_markup=back_to_admin())
            return
        bot_data["admins"].append(target_id)
        bot.reply_to(message, f"✅ تم رفع المستخدم ادمن.", reply_markup=back_to_admin())
        try:
            bot.send_message(target_id, "✅ تم رفعك ادمن في البوت.")
        except:
            pass
    else:
        if target_id not in bot_data.get("admins", []):
            bot.reply_to(message, "⚠️ المستخدم ليس ادمن.", reply_markup=back_to_admin())
            return
        if target_id == ADMIN_ID:
            bot.reply_to(message, "⚠️ لا يمكن حذف المالك.", reply_markup=back_to_admin())
            return
        bot_data["admins"].remove(target_id)
        bot.reply_to(message, f"✅ تم سحب الادمن من المستخدم.", reply_markup=back_to_admin())
        try:
            bot.send_message(target_id, "❌ تم سحب الادمنية منك.")
        except:
            pass
    save_all()

def process_vip_user(message, mode):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    target_id_str = message.text.strip()
    if not re.match(r'\b\d{8,12}\b', target_id_str):
        bot.reply_to(message, "❌ ايدي غير صحيح.", reply_markup=back_to_admin())
        return
    target_id = int(target_id_str)
    
    if mode == "addvip":
        if target_id in bot_data.get("promotionn", []):
            bot.reply_to(message, "⚠️ المستخدم بالفعل في VIP.", reply_markup=back_to_admin())
            return
        bot_data["promotionn"].append(target_id)
        bot.reply_to(message, f"✅ تم إضافة المستخدم إلى VIP.", reply_markup=back_to_admin())
        try:
            bot.send_message(target_id, "✅ تم ترقيتك إلى VIP.")
        except:
            pass
    else:
        if target_id not in bot_data.get("promotionn", []):
            bot.reply_to(message, "⚠️ المستخدم ليس في VIP.", reply_markup=back_to_admin())
            return
        bot_data["promotionn"].remove(target_id)
        bot.reply_to(message, f"✅ تم حذف المستخدم من VIP.", reply_markup=back_to_admin())
        try:
            bot.send_message(target_id, "❌ تم سحب عضوية VIP منك.")
        except:
            pass
    save_all()

def process_restart_bot(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    bot_id = message.text.strip()
    if bot_id not in bots_manager.get("bots", {}):
        bot.reply_to(message, "❌ البوت غير موجود.", reply_markup=back_to_admin())
        return
    
    stop_bot_process(bot_id)
    time.sleep(2)
    
    if bot_id in bots_manager.get("bots", {}):
        bot_file = os.path.join(BOTS_PATH, bots_manager["bots"][bot_id]["file"])
        if os.path.exists(bot_file):
            if start_bot_process(bot_id, bot_file):
                bot.reply_to(message, f"✅ تم إعادة تشغيل البوت {bot_id} بنجاح.", reply_markup=back_to_admin())
            else:
                bot.reply_to(message, f"❌ فشل في إعادة تشغيل البوت {bot_id}.", reply_markup=back_to_admin())
        else:
            bot.reply_to(message, f"❌ ملف البوت {bot_id} غير موجود.", reply_markup=back_to_admin())

def process_stop_bot(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    bot_id = message.text.strip()
    if bot_id not in bots_manager.get("bots", {}):
        bot.reply_to(message, "❌ البوت غير موجود.", reply_markup=back_to_admin())
        return
    
    if stop_bot_process(bot_id):
        bot.reply_to(message, f"✅ تم إيقاف البوت {bot_id} بنجاح.", reply_markup=back_to_admin())
    else:
        bot.reply_to(message, f"❌ فشل في إيقاف البوت {bot_id}.", reply_markup=back_to_admin())

def process_delete_bot(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    bot_id = message.text.strip()
    if bot_id not in bots_manager.get("bots", {}):
        bot.reply_to(message, "❌ البوت غير موجود.", reply_markup=back_to_admin())
        return
    
    stop_bot_process(bot_id)
    
    if bot_id in bots_manager.get("bots", {}):
        bot_file = os.path.join(BOTS_PATH, bots_manager["bots"][bot_id]["file"])
        req_file = os.path.join(BOTS_PATH, f"{bot_id}_requirements.txt")
        
        if os.path.exists(bot_file):
            os.remove(bot_file)
        if os.path.exists(req_file):
            os.remove(req_file)
        
        del bots_manager["bots"][bot_id]
        if bot_id in bots_manager.get("logs", {}):
            del bots_manager["logs"][bot_id]
        if bot_id in bots_manager.get("processes", {}):
            del bots_manager["processes"][bot_id]
        
        save_all()
        bot.reply_to(message, f"✅ تم حذف البوت {bot_id} بنجاح.", reply_markup=back_to_admin())

# ==================== نسخ احتياطي ====================
def create_backup():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_PATH, f"backup_{timestamp}.json")
    
    all_data = {
        "bot_data": bot_data,
        "app_data": app_data,
        "stats_data": stats_data,
        "bots_manager": bots_manager,
        "timestamp": timestamp
    }
    
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    
    backups = sorted([f for f in os.listdir(BACKUP_PATH) if f.endswith('.json')])
    for old in backups[:-5]:
        os.remove(os.path.join(BACKUP_PATH, old))
    
    return backup_file

# ==================== التوجيه ====================
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/') and m.chat.type == 'private')
def forward_to_admin(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        return
    if bot_data.get("tawgeh") == "on":
        try:
            forward = bot.forward_message(ADMIN_ID, user_id, message.message_id)
            app_data["twasol"][str(forward.message_id)] = user_id
            save_data("app.json", app_data)
        except:
            pass

# ==================== تشغيل البوت ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 جاري تشغيل بوت استضافة البوتات...")
    print(f"👑 المطور: {DEVELOPER}")
    print(f"📢 قناة المطور: {CHANNEL}")
    print(f"📢 قناة البوت: {BOT_CHANNEL}")
    print("=" * 60)
    print("")
    print("✅ تم تشغيل البوت بنجاح!")
    print("📱 البوت يعمل الآن...")
    
    bot.remove_webhook()
    
    monitor_thread = threading.Thread(target=monitor_bots, daemon=True)
    monitor_thread.start()
    print("✅ تم تشغيل مراقبة البوتات")
    
    for bot_id in bots_manager.get("running", []):
        if bot_id in bots_manager.get("bots", {}):
            bot_file = os.path.join(BOTS_PATH, bots_manager["bots"][bot_id]["file"])
            if os.path.exists(bot_file):
                start_bot_process(bot_id, bot_file)
                print(f"✅ تم إعادة تشغيل البوت {bot_id}")
    
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ خطأ: {e}")