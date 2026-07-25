import asyncio
import os
import random
import string
import time
import threading
import sqlite3
import hashlib
import json
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import requests
import zipfile
import shutil
import io
import base64

TOKEN = "8350116285:AAFsUbBbk6laHMgdxRQMXpykGa2nBxC18zQ"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

OWNER_ID = 7947679527
ADMIN_ID_1 = 1432561705
ADMIN_ID_2 = 7467458321
RIGHTS_CHANNEL = "https://t.me/kayo_i"
BOT_CHANNEL = "https://t.me/kayo_c"

ADMINS = {OWNER_ID, ADMIN_ID_1, ADMIN_ID_2}
UPLOAD_FOLDER = "uploads/"
VIDEO_FOLDER = "videos/"
TEMP_FOLDER = "temp/"
BACKUP_FOLDER = "backups/"
DATA_FOLDER = "data/"
PERMANENT_FOLDER = "permanent/"

for folder in [UPLOAD_FOLDER, VIDEO_FOLDER, TEMP_FOLDER, BACKUP_FOLDER, DATA_FOLDER, PERMANENT_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# ========== STATES ==========
class BotStates(StatesGroup):
    waiting_for_enemy_name = State()
    waiting_for_ticket = State()
    waiting_for_ticket_reply = State()
    waiting_for_admin_id = State()
    waiting_for_block_user = State()
    waiting_for_unblock_user = State()
    waiting_for_channel = State()
    waiting_for_broadcast_text = State()
    waiting_for_broadcast_photo = State()
    waiting_for_broadcast_video = State()
    waiting_for_restore_backup = State()
    waiting_for_welcome_message = State()
    waiting_for_edit_admin_name = State()

# ========== DATABASE FUNCTIONS ==========
def get_db_connection():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    tables = [
        '''CREATE TABLE IF NOT EXISTS permanent_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_id TEXT UNIQUE,
            file_path TEXT,
            file_type TEXT,
            enemy_name TEXT,
            admin_id INTEGER,
            created_at TIMESTAMP,
            views INTEGER DEFAULT 0,
            is_video INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            file_data TEXT,
            source_chat_id TEXT,
            source_message_id INTEGER
        )''',
        '''CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT,
            added_by INTEGER,
            added_at TIMESTAMP,
            admin_name TEXT DEFAULT 'Sword'
        )''',
        '''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_seen TIMESTAMP,
            last_active TIMESTAMP,
            links_created INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0
        )''',
        '''CREATE TABLE IF NOT EXISTS admin_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            channel_name TEXT,
            added_by INTEGER,
            added_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )''',
        '''CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP,
            resolved_at TIMESTAMP,
            admin_response TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            user_id INTEGER,
            ip_address TEXT,
            details TEXT,
            created_at TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS broadcast_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            media_type TEXT,
            media_path TEXT,
            status TEXT DEFAULT 'pending',
            created_by INTEGER,
            created_at TIMESTAMP,
            sent_at TIMESTAMP
        )''',
        '''CREATE TABLE IF NOT EXISTS deleted_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_id TEXT,
            file_path TEXT,
            file_type TEXT,
            enemy_name TEXT,
            admin_id INTEGER,
            created_at TIMESTAMP,
            views INTEGER DEFAULT 0,
            is_video INTEGER DEFAULT 0,
            deleted_at TIMESTAMP,
            file_data TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT
        )'''
    ]
    
    for table in tables:
        try:
            cursor.execute(table)
        except:
            pass
    
    # إضافة أعمدة جديدة
    try:
        cursor.execute("ALTER TABLE permanent_links ADD COLUMN is_active INTEGER DEFAULT 1")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE permanent_links ADD COLUMN file_data TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE deleted_links ADD COLUMN file_data TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE permanent_links ADD COLUMN source_chat_id TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE permanent_links ADD COLUMN source_message_id INTEGER")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE admins ADD COLUMN admin_name TEXT DEFAULT 'Sword'")
    except:
        pass
    
    conn.commit()
    conn.close()

init_database()

# ========== DATABASE HELPERS ==========
def get_welcome_message():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'welcome_message'")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None

def set_welcome_message(message):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('welcome_message', ?)", (message,))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def load_admins_from_db():
    global ADMINS
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    db_admins = cursor.fetchall()
    conn.close()
    ADMINS = {OWNER_ID, ADMIN_ID_1, ADMIN_ID_2}
    for admin in db_admins:
        ADMINS.add(admin[0])
    save_admins_to_db()

def save_admins_to_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    for admin_id in ADMINS:
        cursor.execute("INSERT OR IGNORE INTO admins (user_id, role, added_by, added_at) VALUES (?, ?, ?, ?)",
                      (admin_id, 'admin', OWNER_ID, datetime.now()))
    conn.commit()
    conn.close()

def get_admin_name(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT admin_name FROM admins WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if (result and result[0]) else "Sword"
    except:
        return "Sword"

def set_admin_name(user_id, name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE admins SET admin_name = ? WHERE user_id = ?", (name, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def add_user(user_id, username=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_seen, last_active) VALUES (?, ?, ?, ?)",
                      (user_id, username, datetime.now(), datetime.now()))
        cursor.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (datetime.now(), user_id))
        conn.commit()
        conn.close()
    except:
        pass

def get_users_count():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
        result = cursor.fetchone()[0]
        conn.close()
        return result
    except:
        return 0

def get_total_links():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM permanent_links WHERE is_active = 1")
        result = cursor.fetchone()[0]
        conn.close()
        return result
    except:
        return 0

def generate_unique_id(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def save_permanent_link(unique_id, file_path, file_type, enemy_name, admin_id, is_video=0, file_data=None, source_chat_id=None, source_message_id=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO permanent_links 
                         (unique_id, file_path, file_type, enemy_name, admin_id, created_at, is_video, is_active, file_data, source_chat_id, source_message_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (unique_id, file_path, file_type, enemy_name, admin_id, datetime.now(), is_video, 1, file_data, source_chat_id, source_message_id))
        conn.commit()
        conn.close()
        return unique_id
    except Exception as e:
        print(f"Error saving link: {e}")
        return None

def get_link_by_id(unique_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM permanent_links WHERE unique_id = ? AND is_active = 1", (unique_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except:
        return None

def get_link_by_name(enemy_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM permanent_links WHERE enemy_name = ? AND is_active = 1 ORDER BY created_at DESC LIMIT 1", (enemy_name,))
        result = cursor.fetchone()
        conn.close()
        return result
    except:
        return None

def search_links_by_name(search_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM permanent_links WHERE enemy_name LIKE ? AND is_active = 1 ORDER BY created_at DESC", (f'%{search_name}%',))
        results = cursor.fetchall()
        conn.close()
        return results
    except:
        return []

def increment_views(unique_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE permanent_links SET views = views + 1 WHERE unique_id = ?", (unique_id,))
        conn.commit()
        conn.close()
    except:
        pass

def log_security_event(event_type, user_id, details, ip_address=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO security_logs (event_type, user_id, ip_address, details, created_at)
                         VALUES (?, ?, ?, ?, ?)''',
                      (event_type, user_id, ip_address, details, datetime.now()))
        conn.commit()
        conn.close()
    except:
        pass

def is_user_blocked(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result and result[0] == 1
    except:
        return False

def block_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def unblock_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def add_admin_channel(channel_id, channel_name, admin_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO admin_channels (channel_id, channel_name, added_by, added_at)
                         VALUES (?, ?, ?, ?)''',
                      (channel_id, channel_name, admin_id, datetime.now()))
        conn.commit()
        conn.close()
    except:
        pass

def get_admin_channels():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id, channel_name FROM admin_channels WHERE is_active = 1")
        result = cursor.fetchall()
        conn.close()
        return result
    except:
        return []

def create_support_ticket(user_id, message):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO support_tickets (user_id, message, created_at, status)
                         VALUES (?, ?, ?, ?)''',
                      (user_id, message, datetime.now(), 'open'))
        conn.commit()
        ticket_id = cursor.lastrowid
        conn.close()
        return ticket_id
    except:
        return None

def get_open_tickets():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, message, created_at FROM support_tickets WHERE status = 'open' ORDER BY created_at")
        result = cursor.fetchall()
        conn.close()
        return result
    except:
        return []

def resolve_ticket(ticket_id, admin_response):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''UPDATE support_tickets 
                         SET status = 'resolved', resolved_at = ?, admin_response = ?
                         WHERE id = ?''',
                      (datetime.now(), admin_response, ticket_id))
        conn.commit()
        conn.close()
    except:
        pass

def add_to_broadcast_queue(message, media_type, media_path, created_by):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO broadcast_queue (message, media_type, media_path, created_by, created_at)
                         VALUES (?, ?, ?, ?, ?)''',
                      (message, media_type, media_path, created_by, datetime.now()))
        conn.commit()
        conn.close()
    except:
        pass

def get_pending_broadcasts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, message, media_type, media_path FROM broadcast_queue WHERE status = 'pending'")
        result = cursor.fetchall()
        conn.close()
        return result
    except:
        return []

def mark_broadcast_sent(broadcast_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE broadcast_queue SET status = 'sent', sent_at = ? WHERE id = ?",
                      (datetime.now(), broadcast_id))
        conn.commit()
        conn.close()
    except:
        pass

def delayed_destroyer(chat_id, message_ids):
    time.sleep(5)
    for msg_id in message_ids:
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception:
            pass

# ========== KEYBOARD FUNCTIONS ==========
def get_main_keyboard(user_id):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 قناة المطور", url=RIGHTS_CHANNEL, style="primary"),
            InlineKeyboardButton(text="📢 قناة البوت", url=BOT_CHANNEL, style="primary")
        ],
        [
            InlineKeyboardButton(text="👑 قائمة الأدمن", callback_data="view_admins_list", style="success"),
            InlineKeyboardButton(text="💬 تواصل مع المطور", callback_data="support", style="danger")
        ]
    ])
    
    if user_id in ADMINS:
        markup.inline_keyboard.append([
            InlineKeyboardButton(text="⚡ SYSTEM CONTROL", callback_data="admin_panel", style="danger")
        ])
    
    return markup

def get_admin_panel_keyboard(user_id):
    markup = InlineKeyboardMarkup(inline_keyboard=[])
    
    if user_id == OWNER_ID:
        markup.inline_keyboard.append([
            InlineKeyboardButton(text="👑 إضافة أدمن", callback_data="owner_add_admin", style="primary"),
            InlineKeyboardButton(text="✏️ تعديل أسماء الأدمن", callback_data="edit_admin_names", style="primary")
        ])
        markup.inline_keyboard.append([
            InlineKeyboardButton(text="📝 تغيير رسالة الترحيب", callback_data="change_welcome", style="primary"),
            InlineKeyboardButton(text="📦 استرجاع نسخة", callback_data="restore_backup", style="primary")
        ])
        markup.inline_keyboard.append([
            InlineKeyboardButton(text="🚫 حظر مستخدم", callback_data="block_user", style="danger"),
            InlineKeyboardButton(text="🔓 فك حظر", callback_data="unblock_user", style="success")
        ])
        markup.inline_keyboard.append([
            InlineKeyboardButton(text="▶️ تشغيل الروابط", callback_data="play_all_links", style="success"),
            InlineKeyboardButton(text="🔄 استرجاع الروابط", callback_data="restore_all_links", style="primary")
        ])
        markup.inline_keyboard.append([
            InlineKeyboardButton(text="📥 مسح رسائل الأدمن", callback_data="scan_admin_messages", style="danger")
        ])
    
    markup.inline_keyboard.append([
        InlineKeyboardButton(text="📢 إضافة قناة", callback_data="add_channel", style="primary"),
        InlineKeyboardButton(text="📋 قائمة القنوات", callback_data="list_channels", style="success")
    ])
    markup.inline_keyboard.append([
        InlineKeyboardButton(text="📨 البث المباشر", callback_data="broadcast", style="danger"),
        InlineKeyboardButton(text="📊 إحصائيات الروابط", callback_data="link_stats", style="primary")
    ])
    markup.inline_keyboard.append([
        InlineKeyboardButton(text="📋 تذاكر الدعم", callback_data="admin_tickets", style="success"),
        InlineKeyboardButton(text="🛡️ سجل الأمان", callback_data="security_logs", style="danger")
    ])
    markup.inline_keyboard.append([
        InlineKeyboardButton(text="📊 إحصائيات عامة", callback_data="general_stats", style="primary")
    ])
    markup.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_to_main", style="danger")
    ])
    
    return markup

def get_support_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📩 فتح تذكرة دعم", callback_data="open_ticket", style="primary"),
            InlineKeyboardButton(text="📋 تذاكري المفتوحة", callback_data="my_tickets", style="success")
        ],
        [
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_to_main", style="danger")
        ]
    ])

def get_forward_keyboard(share_link, unique_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔗 بـث الـرابـط فـوراً", url=f"https://t.me/share/url?url={share_link}", style="primary")
        ],
        [
            InlineKeyboardButton(text="📊 الإحصائيات", callback_data=f"stats_{unique_id}", style="success"),
            InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_to_main", style="danger")
        ]
    ])

def get_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تأكيد البث", callback_data="confirm_broadcast", style="success"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_broadcast", style="danger")
        ]
    ])

def get_back_keyboard(callback):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 العودة", callback_data=callback, style="primary")
        ]
    ])

def get_tickets_keyboard(tickets):
    keyboard = []
    for ticket in tickets[:5]:
        keyboard.append([
            InlineKeyboardButton(text=f"📩 رد على تذكرة #{ticket[0]}", callback_data=f"reply_ticket_{ticket[0]}", style="primary")
        ])
    keyboard.append([
        InlineKeyboardButton(text="🔙 العودة للوحة", callback_data="admin_panel", style="danger")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_broadcast_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 إرسال نص", callback_data="broadcast_text", style="primary"),
            InlineKeyboardButton(text="🖼️ إرسال صورة", callback_data="broadcast_photo", style="success")
        ],
        [
            InlineKeyboardButton(text="📹 إرسال فيديو", callback_data="broadcast_video", style="danger"),
            InlineKeyboardButton(text="📋 قائمة الانتظار", callback_data="broadcast_queue", style="primary")
        ],
        [
            InlineKeyboardButton(text="🔙 العودة للوحة", callback_data="admin_panel", style="danger")
        ]
    ])

def get_admin_list_keyboard():
    keyboard = []
    
    owner_name = get_admin_name(OWNER_ID)
    keyboard.append([
        InlineKeyboardButton(text=f"👑 {owner_name} (المالك)", callback_data="admin_info_owner", style="danger")
    ])
    
    admin1_name = get_admin_name(ADMIN_ID_1)
    admin2_name = get_admin_name(ADMIN_ID_2)
    keyboard.append([
        InlineKeyboardButton(text=f"⚡ {admin1_name} (أدمن 1)", callback_data="admin_info_1", style="primary"),
        InlineKeyboardButton(text=f"⚡ {admin2_name} (أدمن 2)", callback_data="admin_info_2", style="primary")
    ])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, admin_name FROM admins WHERE user_id NOT IN (?, ?, ?)", (OWNER_ID, ADMIN_ID_1, ADMIN_ID_2))
    extra_admins = cursor.fetchall()
    conn.close()
    
    for admin in extra_admins:
        admin_name = admin[1] if admin[1] else "Sword"
        keyboard.append([
            InlineKeyboardButton(text=f"👤 {admin_name}", callback_data=f"admin_info_{admin[0]}", style="success")
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="back_to_main", style="danger")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_edit_admin_names_keyboard():
    keyboard = []
    
    keyboard.append([
        InlineKeyboardButton(text="✏️ تغيير اسم المالك", callback_data="edit_owner_name", style="danger")
    ])
    keyboard.append([
        InlineKeyboardButton(text="✏️ تغيير اسم أدمن 1", callback_data="edit_admin1_name", style="primary"),
        InlineKeyboardButton(text="✏️ تغيير اسم أدمن 2", callback_data="edit_admin2_name", style="primary")
    ])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, admin_name FROM admins WHERE user_id NOT IN (?, ?, ?)", (OWNER_ID, ADMIN_ID_1, ADMIN_ID_2))
    extra_admins = cursor.fetchall()
    conn.close()
    
    for admin in extra_admins:
        admin_name = admin[1] if admin[1] else "Sword"
        keyboard.append([
            InlineKeyboardButton(text=f"✏️ تغيير اسم {admin_name}", callback_data=f"edit_admin_{admin[0]}", style="success")
        ])
    
    keyboard.append([
        InlineKeyboardButton(text="🔙 العودة للوحة", callback_data="admin_panel", style="danger")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ========== ENCODE/DECODE FUNCTIONS ==========
def encode_file_to_base64(file_path):
    try:
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except:
        return None

def decode_base64_to_file(base64_string, output_path):
    try:
        data = base64.b64decode(base64_string)
        with open(output_path, 'wb') as f:
            f.write(data)
        return True
    except:
        return False

# ========== SCAN FUNCTIONS ==========
async def scan_all_messages(chat_id, user_id):
    try:
        scanned = 0
        saved = 0
        
        for msg_id in range(1, 3000):
            try:
                msg = await bot.forward_message(chat_id, chat_id, msg_id)
                if msg:
                    scanned += 1
                    
                    if msg.photo:
                        try:
                            photo_file = msg.photo[-1]
                            file_info = await bot.get_file(photo_file.file_id)
                            downloaded_file = await bot.download_file(file_info.file_path)
                            
                            unique_id = generate_unique_id()
                            photo_path = os.path.join(UPLOAD_FOLDER, f"scan_{unique_id}.jpg")
                            
                            with open(photo_path, 'wb') as f:
                                f.write(downloaded_file)
                            
                            file_data = encode_file_to_base64(photo_path)
                            enemy_name = f"من المحادثة {chat_id}_{msg_id}"
                            
                            save_permanent_link(unique_id, photo_path, 'photo', enemy_name, user_id, 0, file_data, str(chat_id), msg_id)
                            saved += 1
                        except:
                            pass
                    
                    if msg.video:
                        try:
                            video_file = msg.video
                            file_info = await bot.get_file(video_file.file_id)
                            downloaded_file = await bot.download_file(file_info.file_path)
                            
                            unique_id = generate_unique_id()
                            video_path = os.path.join(VIDEO_FOLDER, f"scan_{unique_id}.mp4")
                            
                            with open(video_path, 'wb') as f:
                                f.write(downloaded_file)
                            
                            file_data = encode_file_to_base64(video_path)
                            enemy_name = f"من المحادثة {chat_id}_{msg_id}"
                            
                            save_permanent_link(unique_id, video_path, 'video', enemy_name, user_id, 1, file_data, str(chat_id), msg_id)
                            saved += 1
                        except:
                            pass
                    
                    if msg.text:
                        links = re.findall(r'https?://[^\s]+', msg.text)
                        for link in links:
                            if "t.me" in link or "telegram" in link:
                                try:
                                    unique_id = generate_unique_id()
                                    enemy_name = f"رابط من المحادثة {chat_id}_{msg_id}"
                                    save_permanent_link(unique_id, link, 'link', enemy_name, user_id, 0, None, str(chat_id), msg_id)
                                    saved += 1
                                except:
                                    pass
                    
                    try:
                        await bot.delete_message(chat_id, msg.message_id)
                    except:
                        pass
                        
            except Exception as e:
                if "message to forward not found" in str(e) or "MESSAGE_ID_INVALID" in str(e):
                    break
                continue
            
            await asyncio.sleep(0.2)
        
        return scanned, saved
    except Exception as e:
        print(f"Scan error: {e}")
        return 0, 0

async def scan_all_admins_messages():
    total_scanned = 0
    total_saved = 0
    
    for admin_id in ADMINS:
        try:
            scanned, saved = await scan_all_messages(admin_id, admin_id)
            total_scanned += scanned
            total_saved += saved
        except:
            pass
    
    return total_scanned, total_saved

# ========== RESTORE FUNCTIONS ==========
def restore_all_links():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT unique_id, file_path, file_data, is_video FROM permanent_links WHERE is_active = 1")
        links = cursor.fetchall()
        conn.close()
        
        restored = 0
        failed = 0
        
        for link in links:
            unique_id, file_path, file_data, is_video = link
            
            if os.path.exists(file_path):
                continue
            
            if file_data:
                try:
                    success = decode_base64_to_file(file_data, file_path)
                    if success:
                        restored += 1
                    else:
                        failed += 1
                except:
                    failed += 1
            else:
                failed += 1
        
        return restored, failed
    except Exception as e:
        print(f"Restore error: {e}")
        return 0, 0

def restore_deleted_links():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT unique_id, file_path, file_data, is_video, file_type, enemy_name, admin_id, created_at, views FROM deleted_links")
        deleted = cursor.fetchall()
        
        restored = 0
        
        for link in deleted:
            unique_id, file_path, file_data, is_video, file_type, enemy_name, admin_id, created_at, views = link
            
            if file_data:
                try:
                    success = decode_base64_to_file(file_data, file_path)
                    if success:
                        cursor.execute('''INSERT OR REPLACE INTO permanent_links 
                                         (unique_id, file_path, file_type, enemy_name, admin_id, created_at, views, is_video, is_active, file_data)
                                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                      (unique_id, file_path, file_type, enemy_name, admin_id, created_at, views, is_video, 1, file_data))
                        cursor.execute("DELETE FROM deleted_links WHERE unique_id = ?", (unique_id,))
                        conn.commit()
                        restored += 1
                except:
                    pass
        
        conn.close()
        return restored
    except Exception as e:
        print(f"Restore deleted error: {e}")
        return 0

# ========== PLAY ALL LINKS ==========
async def play_all_links():
    try:
        restored, failed = restore_all_links()
        deleted_restored = restore_deleted_links()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT unique_id, file_path, is_video, enemy_name FROM permanent_links WHERE is_active = 1")
        links = cursor.fetchall()
        conn.close()
        
        if not links:
            await bot.send_message(OWNER_ID, "📭 لا توجد روابط للتشغيل.")
            return
        
        total = len(links)
        played = 0
        failed_play = 0
        
        await bot.send_message(
            OWNER_ID,
            f"🔄 **بدء تشغيل جميع الروابط**\n\n"
            f"📊 إجمالي الروابط: {total}\n"
            f"✅ تم استرجاع: {restored} رابط\n"
            f"🗑️ تم استرجاع محذوف: {deleted_restored} رابط\n"
            f"⏱️ الوقت: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        for link in links:
            try:
                unique_id, file_path, is_video, enemy_name = link
                
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        if is_video == 1:
                            await bot.send_video(OWNER_ID, f, caption=f"🎯 {enemy_name}\n🔗 {unique_id}")
                        else:
                            await bot.send_photo(OWNER_ID, f, caption=f"🎯 {enemy_name}\n🔗 {unique_id}")
                    played += 1
                else:
                    conn2 = get_db_connection()
                    cursor2 = conn2.cursor()
                    cursor2.execute("SELECT file_data FROM permanent_links WHERE unique_id = ?", (unique_id,))
                    result = cursor2.fetchone()
                    conn2.close()
                    
                    if result and result[0]:
                        success = decode_base64_to_file(result[0], file_path)
                        if success:
                            with open(file_path, 'rb') as f:
                                if is_video == 1:
                                    await bot.send_video(OWNER_ID, f, caption=f"🎯 {enemy_name}\n🔗 {unique_id}")
                                else:
                                    await bot.send_photo(OWNER_ID, f, caption=f"🎯 {enemy_name}\n🔗 {unique_id}")
                            played += 1
                        else:
                            failed_play += 1
                    else:
                        failed_play += 1
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                failed_play += 1
                continue
        
        await bot.send_message(
            OWNER_ID,
            f"✅ **تم الانتهاء من تشغيل الروابط**\n\n"
            f"▶️ تم التشغيل: {played}\n"
            f"❌ فشل: {failed_play}\n"
            f"📊 المجموع: {played + failed_play}\n"
            f"⏱️ الوقت: {datetime.now().strftime('%H:%M:%S')}"
        )
            
    except Exception as e:
        await bot.send_message(OWNER_ID, f"❌ خطأ في التشغيل: {str(e)}")

def auto_play_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        try:
            loop.run_until_complete(play_all_links())
            time.sleep(10 * 3600)
        except Exception as e:
            print(f"Auto play error: {e}")
            time.sleep(3600)

# ========== BACKUP FUNCTIONS ==========
def backup_all_data():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_FOLDER, f"backup_{timestamp}.zip")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    tables = ['permanent_links', 'admins', 'users', 'admin_channels', 
              'support_tickets', 'security_logs', 'broadcast_queue', 'deleted_links', 'settings']
    data = {}
    for table in tables:
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        data[table] = [dict(zip(columns, row)) for row in rows]
    conn.close()
    
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        json_data = json.dumps(data, default=str, indent=2)
        zipf.writestr('data.json', json_data)
        
        for folder in [UPLOAD_FOLDER, VIDEO_FOLDER]:
            if os.path.exists(folder):
                for root, _, files in os.walk(folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join(os.path.basename(folder), file)
                        zipf.write(file_path, arcname)
    return backup_path

def restore_backup_file(zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            json_data = zipf.read('data.json')
            data = json.loads(json_data)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            tables = ['permanent_links', 'admins', 'users', 'admin_channels', 
                      'support_tickets', 'security_logs', 'broadcast_queue', 'deleted_links', 'settings']
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            
            for table, rows in data.items():
                if not rows:
                    continue
                columns = list(rows[0].keys())
                placeholders = ','.join(['?' for _ in columns])
                col_names = ','.join(columns)
                for row in rows:
                    values = [row[col] for col in columns]
                    query = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"
                    cursor.execute(query, values)
            conn.commit()
            conn.close()
            
            for folder in [UPLOAD_FOLDER, VIDEO_FOLDER]:
                if os.path.exists(folder):
                    shutil.rmtree(folder)
                os.makedirs(folder, exist_ok=True)
            
            for file_info in zipf.infolist():
                if file_info.filename == 'data.json':
                    continue
                if file_info.filename.startswith('uploads/'):
                    target_folder = UPLOAD_FOLDER
                elif file_info.filename.startswith('videos/'):
                    target_folder = VIDEO_FOLDER
                else:
                    continue
                filename = os.path.basename(file_info.filename)
                if filename:
                    zipf.extract(file_info, path=target_folder)
        return True
    except Exception as e:
        print(f"Restore error: {e}")
        return False

# ========== START THREADS ==========
load_admins_from_db()

play_thread = threading.Thread(target=auto_play_loop, daemon=True)
play_thread.start()

# ========== BOT HANDLERS ==========
@dp.message(Command("start"))
async def handle_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username
    
    if is_user_blocked(user_id):
        await bot.send_message(chat_id, "🚫 تم حظرك من استخدام هذا البوت.")
        return
    
    add_user(user_id, username)
    text_split = message.text.split()
    
    if len(text_split) > 1:
        unique_id = text_split[1]
        link_data = get_link_by_id(unique_id)
        
        if link_data:
            file_path = link_data[2]
            is_video = link_data[8]
            
            increment_views(unique_id)
            
            try:
                if os.path.exists(file_path):
                    if is_video == 1:
                        with open(file_path, 'rb') as video:
                            sent = await bot.send_video(chat_id, video)
                    else:
                        with open(file_path, 'rb') as photo:
                            sent = await bot.send_photo(chat_id, photo)
                    
                    threading.Thread(target=delayed_destroyer, args=(chat_id, [sent.message_id]), daemon=True).start()
                    return
            except:
                pass
            
            try:
                if link_data[9]:
                    decoded = decode_base64_to_file(link_data[9], file_path)
                    if decoded:
                        if is_video == 1:
                            with open(file_path, 'rb') as video:
                                sent = await bot.send_video(chat_id, video)
                        else:
                            with open(file_path, 'rb') as photo:
                                sent = await bot.send_photo(chat_id, photo)
                        threading.Thread(target=delayed_destroyer, args=(chat_id, [sent.message_id]), daemon=True).start()
                        return
            except:
                pass
            
            await bot.send_message(chat_id, "❌ حدث خطأ في فتح الرابط.")
            return
        else:
            await bot.send_message(chat_id, "❌ الرابط غير موجود أو تم حذفه.")
            return

    users_count = get_users_count()
    
    welcome_msg = get_welcome_message()
    if welcome_msg:
        welcome_text = welcome_msg.replace("{users_count}", str(users_count))
    else:
        welcome_text = (
            "⛨                                                                   ⛨\n"
            "               اهلا بك في بوت ازالات السورد\n"
            "             ─────────────────\n\n"
            f"          👤 المستخدمين النشطين: {users_count}\n"
            f"          📢 قناة المطور: [اضغط هنا]({RIGHTS_CHANNEL})"
        )
    
    await bot.send_message(
        chat_id,
        welcome_text,
        reply_markup=get_main_keyboard(user_id),
        disable_web_page_preview=True
    )

# ========== PHOTO HANDLER ==========
@dp.message(lambda message: message.photo and message.from_user.id in ADMINS)
async def handle_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if is_user_blocked(user_id):
        await bot.send_message(chat_id, "🚫 تم حظرك.")
        return
    
    try:
        photo_file = message.photo[-1]
        file_info = await bot.get_file(photo_file.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        unique_id = generate_unique_id()
        photo_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}.jpg")
        
        with open(photo_path, 'wb') as f:
            f.write(downloaded_file)
        
        file_data = encode_file_to_base64(photo_path)
        
        await state.set_state(BotStates.waiting_for_enemy_name)
        await state.update_data(unique_id=unique_id, file_path=photo_path, file_data=file_data, is_video=0)
        
        await bot.send_message(chat_id, "👤 أرسل اسم الخصم:")
        
    except Exception as e:
        log_security_event('error', user_id, f'Photo error: {str(e)}')
        await bot.send_message(chat_id, f"❌ خطأ: {str(e)}")

# ========== VIDEO HANDLER ==========
@dp.message(lambda message: message.video and message.from_user.id in ADMINS)
async def handle_video(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if is_user_blocked(user_id):
        await bot.send_message(chat_id, "🚫 تم حظرك.")
        return
    
    try:
        video_file = message.video
        file_info = await bot.get_file(video_file.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        unique_id = generate_unique_id()
        video_path = os.path.join(VIDEO_FOLDER, f"{unique_id}.mp4")
        
        with open(video_path, 'wb') as f:
            f.write(downloaded_file)
        
        file_data = encode_file_to_base64(video_path)
        
        await state.set_state(BotStates.waiting_for_enemy_name)
        await state.update_data(unique_id=unique_id, file_path=video_path, file_data=file_data, is_video=1)
        
        await bot.send_message(chat_id, "👤 أرسل اسم الخصم:")
        
    except Exception as e:
        log_security_event('error', user_id, f'Video error: {str(e)}')
        await bot.send_message(chat_id, f"❌ خطأ: {str(e)}")

# ========== ENEMY NAME HANDLER ==========
@dp.message(BotStates.waiting_for_enemy_name)
async def process_enemy_name(message: Message, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.from_user.id
    enemy_name = message.text.strip()
    
    if not enemy_name:
        await bot.send_message(chat_id, "⚠️ اسم غير صالح، تم إلغاء العملية.")
        await state.clear()
        return
    
    data = await state.get_data()
    unique_id = data.get('unique_id')
    file_path = data.get('file_path')
    file_data = data.get('file_data')
    is_video = data.get('is_video', 0)
    file_type = 'video' if is_video == 1 else 'photo'
    
    save_permanent_link(unique_id, file_path, file_type, enemy_name, user_id, is_video, file_data)
    
    bot_username = (await bot.get_me()).username
    share_link = f"https://t.me/{bot_username}?start={unique_id}"
    
    success_text = f"{enemy_name}\n[Click here]({share_link})"
    
    await bot.send_message(
        chat_id,
        success_text,
        reply_markup=get_forward_keyboard(share_link, unique_id)
    )
    
    await state.clear()

# ========== TEXT HANDLER ==========
@dp.message(lambda message: message.text and message.from_user.id in ADMINS and not message.text.startswith('/'))
async def handle_text(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    
    if is_user_blocked(user_id):
        return
    
    add_user(user_id)
    
    link = get_link_by_name(text)
    
    if link:
        file_path = link[2]
        is_video = link[8]
        unique_id = link[1]
        
        increment_views(unique_id)
        
        try:
            if os.path.exists(file_path):
                if is_video == 1:
                    with open(file_path, 'rb') as video:
                        await bot.send_video(chat_id, video)
                else:
                    with open(file_path, 'rb') as photo:
                        await bot.send_photo(chat_id, photo)
                return
        except:
            pass
        
        try:
            if link[9]:
                decoded = decode_base64_to_file(link[9], file_path)
                if decoded:
                    if is_video == 1:
                        with open(file_path, 'rb') as video:
                            await bot.send_video(chat_id, video)
                    else:
                        with open(file_path, 'rb') as photo:
                            await bot.send_photo(chat_id, photo)
                    return
        except:
            pass
        
        await bot.send_message(chat_id, "❌ حدث خطأ في فتح الرابط.")
        return
    
    results = search_links_by_name(text)
    if results and len(results) > 1:
        result_text = f"🔍 **نتائج البحث عن '{text}':**\n\n"
        for res in results[:10]:
            result_text += f"• {res['enemy_name']} - `{res['unique_id']}`\n"
        if len(results) > 10:
            result_text += f"...و {len(results) - 10} نتيجة أخرى"
        await bot.send_message(chat_id, result_text)
        return

# ========== CALLBACK HANDLERS ==========
@dp.callback_query()
async def handle_callbacks(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    users_count = get_users_count()
    total_links = get_total_links()
    
    await call.answer()
    
    if is_user_blocked(user_id):
        await bot.answer_callback_query(call.id, "🚫 تم حظرك.", show_alert=True)
        return
    
    # ===== BACK TO MAIN =====
    if call.data == "back_to_main":
        welcome_msg = get_welcome_message()
        if welcome_msg:
            welcome_text = welcome_msg.replace("{users_count}", str(users_count))
        else:
            welcome_text = (
                "⛨                                                                   ⛨\n"
                "               اهلا بك في بوت ازالات السورد\n"
                "             ─────────────────\n\n"
                f"          👤 المستخدمين النشطين: {users_count}\n"
                f"          📢 قناة المطور: [اضغط هنا]({RIGHTS_CHANNEL})"
            )
        
        await bot.edit_message_text(
            welcome_text,
            chat_id, message_id,
            reply_markup=get_main_keyboard(user_id),
            disable_web_page_preview=True
        )
    
    # ===== SUPPORT =====
    elif call.data == "support":
        await bot.edit_message_text(
            "💬 **مركز التواصل مع المطور**\n\n"
            "• اضغط 'فتح تذكرة' للتواصل مع المطور\n"
            "• سيتم الرد عليك في أقرب وقت\n"
            "• يمكنك متابعة حالة تذكرتك",
            chat_id, message_id,
            reply_markup=get_support_keyboard()
        )
    
    # ===== OPEN TICKET =====
    elif call.data == "open_ticket":
        await state.set_state(BotStates.waiting_for_ticket)
        await bot.send_message(chat_id, "📝 اكتب رسالتك للمطور:")
    
    # ===== MY TICKETS =====
    elif call.data == "my_tickets":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, message, status, created_at FROM support_tickets WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (user_id,))
        tickets = cursor.fetchall()
        conn.close()
        
        if tickets:
            text = "📋 **تذاكر الدعم الخاصة بك:**\n\n"
            for ticket in tickets:
                status_emoji = "🟢" if ticket[2] == 'open' else "🔴"
                text += f"{status_emoji} #{ticket[0]} - {ticket[1][:30]}...\n"
                text += f"   📅 {ticket[3][:10]} - الحالة: {ticket[2]}\n\n"
        else:
            text = "📭 ليس لديك تذاكر دعم."
        
        await bot.edit_message_text(
            text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("support")
        )
    
    # ===== VIEW ADMINS LIST =====
    elif call.data == "view_admins_list":
        await bot.edit_message_text(
            "👑 **قائمة الإدارة والوصول المعتمد:**\n\n"
            "⚡ جميع الحقوق محفوظة لـ كايو.",
            chat_id, message_id,
            reply_markup=get_admin_list_keyboard()
        )
    
    # ===== ADMIN INFO =====
    elif call.data.startswith("admin_info_"):
        admin_id = call.data.replace("admin_info_", "")
        admin_name = get_admin_name(admin_id)
        
        if admin_id == "owner":
            text = f"👑 **{admin_name} (المالك)**\n"
            text += f"🆔 المعرف: `{OWNER_ID}`\n"
            text += "🔰 الصلاحية: كاملة"
        elif admin_id == "1":
            text = f"⚡ **{admin_name} (أدمن 1)**\n"
            text += f"🆔 المعرف: `{ADMIN_ID_1}`\n"
            text += "🔰 الصلاحية: أدمن نظام"
        elif admin_id == "2":
            text = f"⚡ **{admin_name} (أدمن 2)**\n"
            text += f"🆔 المعرف: `{ADMIN_ID_2}`\n"
            text += "🔰 الصلاحية: أدمن نظام"
        else:
            try:
                admin_id_int = int(admin_id)
                text = f"👤 **{admin_name}**\n"
                text += f"🆔 المعرف: `{admin_id_int}`\n"
                text += "🔰 الصلاحية: أدمن إضافي"
            except:
                text = "❌ معلومات غير متوفرة"
        
        await bot.edit_message_text(
            text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("view_admins_list")
        )
    
    # ===== ADMIN PANEL =====
    elif call.data == "admin_panel":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ صلاحيات الحماية تمنعك.", show_alert=True)
            return
        
        await bot.edit_message_text(
            f"💀 **لوحة التحكم المتقدمة**\n\n"
            f"👤 المستخدمين: {users_count}\n"
            f"🔗 إجمالي الروابط: {total_links}\n"
            f"👑 الأدمن: {len(ADMINS)}\n\n"
            "🛠️ اختر العملية المطلوبة:",
            chat_id, message_id,
            reply_markup=get_admin_panel_keyboard(user_id)
        )
    
    # ===== CHANGE WELCOME =====
    elif call.data == "change_welcome":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه تغيير رسالة الترحيب!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_welcome_message)
        await bot.send_message(
            chat_id,
            "📝 **أرسل رسالة الترحيب الجديدة:**\n\n"
            "💡 يمكنك استخدام:\n"
            "- `{users_count}` لعدد المستخدمين"
        )
    
    # ===== EDIT ADMIN NAMES =====
    elif call.data == "edit_admin_names":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه تعديل أسماء الأدمن!", show_alert=True)
            return
        
        await bot.edit_message_text(
            "✏️ **تعديل أسماء الأدمن**\n\n"
            "اختر الأدمن الذي تريد تغيير اسمه:",
            chat_id, message_id,
            reply_markup=get_edit_admin_names_keyboard()
        )
    
    # ===== EDIT ADMIN NAME =====
    elif call.data in ["edit_owner_name", "edit_admin1_name", "edit_admin2_name"]:
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        if call.data == "edit_owner_name":
            edit_id = OWNER_ID
            name = "المالك"
        elif call.data == "edit_admin1_name":
            edit_id = ADMIN_ID_1
            name = "أدمن 1"
        else:
            edit_id = ADMIN_ID_2
            name = "أدمن 2"
        
        await state.set_state(BotStates.waiting_for_edit_admin_name)
        await state.update_data(edit_user_id=edit_id)
        await bot.send_message(chat_id, f"✏️ أرسل الاسم الجديد لـ {name}:")
    
    elif call.data.startswith("edit_admin_"):
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        edit_id = int(call.data.replace("edit_admin_", ""))
        await state.set_state(BotStates.waiting_for_edit_admin_name)
        await state.update_data(edit_user_id=edit_id)
        await bot.send_message(chat_id, f"✏️ أرسل الاسم الجديد للأدمن:")
    
    # ===== PLAY ALL LINKS =====
    elif call.data == "play_all_links":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه تشغيل جميع الروابط!", show_alert=True)
            return
        
        await bot.edit_message_text("⏳ جاري تشغيل جميع الروابط...", chat_id, message_id)
        await bot.edit_message_text("✅ بدأ تشغيل جميع الروابط!", chat_id, message_id)
        asyncio.create_task(play_all_links())
    
    # ===== RESTORE ALL LINKS =====
    elif call.data == "restore_all_links":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه الاسترجاع!", show_alert=True)
            return
        
        await bot.edit_message_text("⏳ جاري استرجاع جميع الروابط...", chat_id, message_id)
        
        try:
            restored, failed = restore_all_links()
            deleted_restored = restore_deleted_links()
            
            text = f"✅ **تم استرجاع الروابط**\n\n"
            text += f"📊 إجمالي الروابط المسترجعة: {restored}\n"
            text += f"🗑️ الروابط المحذوفة المسترجعة: {deleted_restored}\n"
            text += f"❌ فشل الاسترجاع: {failed}"
            
            await bot.edit_message_text(
                text,
                chat_id, message_id,
                reply_markup=get_back_keyboard("admin_panel")
            )
        except Exception as e:
            await bot.edit_message_text(f"❌ خطأ: {str(e)}", chat_id, message_id)
    
    # ===== SCAN ADMIN MESSAGES =====
    elif call.data == "scan_admin_messages":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه مسح الرسائل!", show_alert=True)
            return
        
        await bot.edit_message_text("⏳ جاري مسح جميع رسائل الأدمن والمالك...", chat_id, message_id)
        
        try:
            scanned, saved = await scan_all_admins_messages()
            
            text = f"✅ **تم مسح الرسائل**\n\n"
            text += f"📊 عدد الرسائل الممسوحة: {scanned}\n"
            text += f"💾 عدد الملفات والروابط المستخرجة: {saved}"
            
            await bot.edit_message_text(
                text,
                chat_id, message_id,
                reply_markup=get_back_keyboard("admin_panel")
            )
        except Exception as e:
            await bot.edit_message_text(f"❌ خطأ: {str(e)}", chat_id, message_id)
    
    # ===== RESTORE BACKUP =====
    elif call.data == "restore_backup":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه الاسترجاع!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_restore_backup)
        await bot.send_message(chat_id, "📤 أرسل ملف النسخة الاحتياطية (ZIP):")
    
    # ===== OWNER ADD ADMIN =====
    elif call.data == "owner_add_admin":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ صلاحيات المالك مفقودة!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_admin_id)
        await bot.send_message(chat_id, "👤 أرسل الرقم التعريفي (ID) للترقية:")
    
    # ===== BLOCK USER =====
    elif call.data == "block_user":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه الحظر!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_block_user)
        await bot.send_message(chat_id, "🚫 أرسل معرف المستخدم لحظره:")
    
    # ===== UNBLOCK USER =====
    elif call.data == "unblock_user":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه فك الحظر!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_unblock_user)
        await bot.send_message(chat_id, "🔓 أرسل معرف المستخدم لفك حظره:")
    
    # ===== ADD CHANNEL =====
    elif call.data == "add_channel":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_channel)
        await bot.send_message(chat_id, "📢 أرسل معرف القناة (مثال: @kayo_c):")
    
    # ===== LIST CHANNELS =====
    elif call.data == "list_channels":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        channels = get_admin_channels()
        if channels:
            text = "📢 **قنوات الأدمن:**\n\n"
            for channel in channels:
                text += f"• {channel[1]} - ID: {channel[0]}\n"
        else:
            text = "📭 لا توجد قنوات مسجلة."
        
        await bot.edit_message_text(
            text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("admin_panel")
        )
    
    # ===== BROADCAST =====
    elif call.data == "broadcast":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        await bot.edit_message_text(
            "📨 **لوحة البث المباشر**\n\n"
            "اختر نوع المحتوى لإرساله لجميع المستخدمين:",
            chat_id, message_id,
            reply_markup=get_broadcast_keyboard()
        )
    
    # ===== BROADCAST TEXT =====
    elif call.data == "broadcast_text":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_broadcast_text)
        await bot.send_message(chat_id, "📝 أرسل النص الذي تريد بثه:")
    
    # ===== BROADCAST PHOTO =====
    elif call.data == "broadcast_photo":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_broadcast_photo)
        await bot.send_message(chat_id, "🖼️ أرسل الصورة التي تريد بثها (مع النص اختياري):")
    
    # ===== BROADCAST VIDEO =====
    elif call.data == "broadcast_video":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        await state.set_state(BotStates.waiting_for_broadcast_video)
        await bot.send_message(chat_id, "📹 أرسل الفيديو الذي تريد بثه (مع النص اختياري):")
    
    # ===== BROADCAST QUEUE =====
    elif call.data == "broadcast_queue":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        queue = get_pending_broadcasts()
        if queue:
            text = "📋 **قائمة البث المعلقة:**\n\n"
            for item in queue:
                text += f"#{item[0]} - النوع: {item[2]}\n"
                text += f"📝 {item[1][:50]}...\n\n"
        else:
            text = "📭 لا توجد رسائل في قائمة الانتظار."
        
        await bot.edit_message_text(
            text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("broadcast")
        )
    
    # ===== CONFIRM BROADCAST =====
    elif call.data == "confirm_broadcast":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        queue = get_pending_broadcasts()
        
        if not queue:
            await bot.answer_callback_query(call.id, "📭 لا توجد رسائل في قائمة الانتظار.", show_alert=True)
            return
        
        await bot.edit_message_text("⏳ جاري إرسال البث...", chat_id, message_id)
        
        total_sent = 0
        total_failed = 0
        
        for item in queue:
            broadcast_id, message_text, media_type, media_path = item
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE is_blocked = 0")
            users = cursor.fetchall()
            conn.close()
            
            for user in users:
                target_id = user[0]
                try:
                    if media_type == 'text':
                        await bot.send_message(target_id, message_text)
                    elif media_type == 'photo':
                        with open(media_path, 'rb') as photo:
                            await bot.send_photo(target_id, photo, caption=message_text)
                    elif media_type == 'video':
                        with open(media_path, 'rb') as video:
                            await bot.send_video(target_id, video, caption=message_text)
                    total_sent += 1
                except:
                    total_failed += 1
                
                await asyncio.sleep(0.3)
            
            mark_broadcast_sent(broadcast_id)
            
            if media_path and os.path.exists(media_path) and media_type != 'text':
                os.remove(media_path)
        
        result_text = f"✅ **تم إرسال البث بنجاح**\n\n"
        result_text += f"📨 تم الإرسال: {total_sent}\n"
        result_text += f"❌ فشل الإرسال: {total_failed}\n"
        result_text += f"📊 المجموع الكلي: {total_sent + total_failed}"
        
        await bot.edit_message_text(
            result_text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("admin_panel")
        )
        
        log_security_event('broadcast_sent', user_id, f'Sent to {total_sent} users, failed: {total_failed}')
    
    # ===== CANCEL BROADCAST =====
    elif call.data == "cancel_broadcast":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE broadcast_queue SET status = 'cancelled' WHERE status = 'pending'")
        conn.commit()
        conn.close()
        
        await bot.edit_message_text(
            "❌ تم إلغاء البث.",
            chat_id, message_id,
            reply_markup=get_back_keyboard("admin_panel")
        )
    
    # ===== LINK STATS =====
    elif call.data == "link_stats":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(views) FROM permanent_links WHERE is_active = 1")
        total_links, total_views = cursor.fetchone()
        cursor.execute("SELECT enemy_name, views, created_at FROM permanent_links WHERE is_active = 1 ORDER BY views DESC LIMIT 10")
        top_links = cursor.fetchall()
        conn.close()
        
        total_links = total_links or 0
        total_views = total_views or 0
        
        text = f"📊 **إحصائيات الروابط:**\n\n"
        text += f"🔗 إجمالي الروابط: {total_links}\n"
        text += f"👁️ إجمالي المشاهدات: {total_views}\n\n"
        text += "🏆 **أكثر 10 روابط مشاهدة:**\n"
        
        if top_links:
            for i, link in enumerate(top_links, 1):
                text += f"{i}. {link[0]} - {link[1]} مشاهدة\n"
        else:
            text += "📭 لا توجد روابط."
        
        await bot.edit_message_text(
            text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("admin_panel")
        )
    
    # ===== ADMIN TICKETS =====
    elif call.data == "admin_tickets":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        tickets = get_open_tickets()
        
        if tickets:
            text = "📋 **تذاكر الدعم المفتوحة:**\n\n"
            for ticket in tickets:
                text += f"#{ticket[0]} - من: {ticket[1]}\n"
                text += f"📝 {ticket[2][:50]}...\n"
                text += f"📅 {ticket[3][:10]}\n\n"
            
            await bot.edit_message_text(
                text,
                chat_id, message_id,
                reply_markup=get_tickets_keyboard(tickets)
            )
        else:
            text = "📭 لا توجد تذاكر مفتوحة."
            await bot.edit_message_text(
                text,
                chat_id, message_id,
                reply_markup=get_back_keyboard("admin_panel")
            )
    
    # ===== REPLY TICKET =====
    elif call.data.startswith("reply_ticket_"):
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        ticket_id = int(call.data.split("_")[2])
        await state.set_state(BotStates.waiting_for_ticket_reply)
        await state.update_data(ticket_id=ticket_id)
        await bot.send_message(chat_id, f"📝 اكتب ردك على التذكرة #{ticket_id}:")
    
    # ===== SECURITY LOGS =====
    elif call.data == "security_logs":
        if user_id != OWNER_ID:
            await bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه رؤية سجل الأمان!", show_alert=True)
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, user_id, details, created_at FROM security_logs ORDER BY created_at DESC LIMIT 20")
        logs = cursor.fetchall()
        conn.close()
        
        text = "🛡️ **سجل الأمان (آخر 20 حدث):**\n\n"
        for log in logs:
            text += f"• {log[0]} - من: {log[1]}\n"
            text += f"  {log[2][:50]}...\n"
            text += f"  📅 {log[3]}\n\n"
        
        await bot.edit_message_text(
            text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("admin_panel")
        )
    
    # ===== GENERAL STATS =====
    elif call.data == "general_stats":
        if user_id not in ADMINS:
            await bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        blocked_users = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM permanent_links WHERE is_active = 1")
        total_links = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(views) FROM permanent_links WHERE is_active = 1")
        total_views = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM admins")
        total_admins = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
        open_tickets = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM deleted_links")
        deleted_links = cursor.fetchone()[0] or 0
        
        conn.close()
        
        text = f"📊 **إحصائيات عامة:**\n\n"
        text += f"👥 المستخدمين الكلي: {total_users}\n"
        text += f"🚫 المحظورين: {blocked_users}\n"
        text += f"👑 الأدمن: {total_admins}\n"
        text += f"🔗 الروابط النشطة: {total_links}\n"
        text += f"🗑️ الروابط المحذوفة: {deleted_links}\n"
        text += f"👁️ المشاهدات الكلية: {total_views}\n"
        text += f"📩 التذاكر المفتوحة: {open_tickets}\n"
        text += f"⏰ وقت النظام: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        await bot.edit_message_text(
            text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("admin_panel")
        )
    
    # ===== STATS =====
    elif call.data.startswith("stats_"):
        unique_id = call.data.split("_")[1]
        link_data = get_link_by_id(unique_id)
        
        if link_data:
            text = f"📊 **إحصائيات الرابط:**\n\n"
            text += f"🔗 المعرف: {link_data[1]}\n"
            text += f"🎯 الاسم: {link_data[4]}\n"
            text += f"👁️ المشاهدات: {link_data[6]}\n"
            text += f"📅 تاريخ الإنشاء: {link_data[5][:10]}\n"
            text += f"📂 النوع: {'فيديو' if link_data[8] == 1 else 'صورة'}\n"
        else:
            text = "❌ الرابط غير موجود."
        
        await bot.edit_message_text(
            text,
            chat_id, message_id,
            reply_markup=get_back_keyboard("back_to_main")
        )

# ========== STATE HANDLERS ==========
@dp.message(BotStates.waiting_for_ticket)
async def process_ticket(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    ticket_text = message.text.strip()
    
    if not ticket_text:
        await bot.send_message(chat_id, "⚠️ الرسالة فارغة، تم إلغاء التذكرة.")
        await state.clear()
        return
    
    ticket_id = create_support_ticket(user_id, ticket_text)
    
    if ticket_id:
        await bot.send_message(chat_id, f"✅ تم فتح تذكرة الدعم #{ticket_id}\nسيتم الرد عليك في أقرب وقت.")
        
        for admin_id in ADMINS:
            try:
                await bot.send_message(
                    admin_id,
                    f"📩 تذكرة دعم جديدة #{ticket_id}\n"
                    f"من: {user_id}\n"
                    f"الرسالة: {ticket_text[:100]}..."
                )
            except:
                pass
    
    await state.clear()

@dp.message(BotStates.waiting_for_ticket_reply)
async def process_ticket_reply(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    reply_text = message.text.strip()
    
    if not reply_text:
        await bot.send_message(chat_id, "⚠️ الرد فارغ.")
        await state.clear()
        return
    
    data = await state.get_data()
    ticket_id = data.get('ticket_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, message FROM support_tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    
    if ticket:
        target_id = ticket[0]
        original_message = ticket[1]
        
        resolve_ticket(ticket_id, reply_text)
        
        try:
            await bot.send_message(
                target_id,
                f"📩 **رد على تذكرتك #{ticket_id}**\n\n"
                f"رسالتك: {original_message[:100]}...\n\n"
                f"رد الأدمن:\n{reply_text}"
            )
            await bot.send_message(chat_id, f"✅ تم الرد على التذكرة #{ticket_id}")
        except:
            await bot.send_message(chat_id, f"⚠️ تعذر إرسال الرد للمستخدم.")
    
    await state.clear()

@dp.message(BotStates.waiting_for_admin_id)
async def process_add_admin(message: Message, state: FSMContext):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    try:
        new_id = int(message.text.strip())
        if new_id in ADMINS:
            await bot.reply_to(message, "ℹ️ هذا المعرف يمتلك وصولاً مسبقاً.")
            await state.clear()
            return
        
        ADMINS.add(new_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO admins (user_id, role, added_by, added_at, admin_name) VALUES (?, ?, ?, ?, ?)",
                      (new_id, 'admin', user_id, datetime.now(), 'Sword'))
        conn.commit()
        conn.close()
        log_security_event('admin_added', new_id, f'Added by {user_id}')
        await bot.reply_to(message, f"✅ تم ترفيع الأدمن بنجاح: `{new_id}`")
    except ValueError:
        await bot.reply_to(message, "❌ خطأ في الإدخال.")
    
    await state.clear()

@dp.message(BotStates.waiting_for_block_user)
async def process_block(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    try:
        target_id = int(message.text.strip())
        block_user(target_id)
        log_security_event('user_blocked', target_id, f'Blocked by {user_id}')
        await bot.reply_to(message, f"✅ تم حظر المستخدم: `{target_id}`")
    except ValueError:
        await bot.reply_to(message, "❌ خطأ في الإدخال.")
    
    await state.clear()

@dp.message(BotStates.waiting_for_unblock_user)
async def process_unblock(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    try:
        target_id = int(message.text.strip())
        unblock_user(target_id)
        log_security_event('user_unblocked', target_id, f'Unblocked by {user_id}')
        await bot.reply_to(message, f"✅ تم فك الحظر عن المستخدم: `{target_id}`")
    except ValueError:
        await bot.reply_to(message, "❌ خطأ في الإدخال.")
    
    await state.clear()

@dp.message(BotStates.waiting_for_channel)
async def process_channel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    channel_input = message.text.strip()
    channel_id = channel_input.replace('@', '')
    
    add_admin_channel(channel_id, channel_input, user_id)
    log_security_event('channel_added', user_id, f'Added channel: {channel_input}')
    await bot.reply_to(message, f"✅ تم إضافة القناة: {channel_input}")
    await state.clear()

@dp.message(BotStates.waiting_for_broadcast_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    
    if not text:
        await bot.send_message(chat_id, "⚠️ النص فارغ.")
        await state.clear()
        return
    
    add_to_broadcast_queue(text, 'text', None, user_id)
    await bot.send_message(chat_id, "✅ تم إضافة النص إلى قائمة البث.")
    await bot.send_message(
        chat_id,
        "⚠️ هل تريد تأكيد إرسال البث لجميع المستخدمين؟",
        reply_markup=get_confirm_keyboard()
    )
    await state.clear()

@dp.message(BotStates.waiting_for_broadcast_photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not message.photo:
        await bot.send_message(chat_id, "⚠️ يرجى إرسال صورة.")
        return
    
    photo_file = message.photo[-1]
    file_info = await bot.get_file(photo_file.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    
    photo_path = os.path.join(TEMP_FOLDER, f"broadcast_{generate_unique_id()}.jpg")
    with open(photo_path, 'wb') as f:
        f.write(downloaded_file)
    
    text = message.caption or "🖼️"
    add_to_broadcast_queue(text, 'photo', photo_path, user_id)
    await bot.send_message(chat_id, "✅ تم إضافة الصورة إلى قائمة البث.")
    await bot.send_message(
        chat_id,
        "⚠️ هل تريد تأكيد إرسال البث لجميع المستخدمين؟",
        reply_markup=get_confirm_keyboard()
    )
    await state.clear()

@dp.message(BotStates.waiting_for_broadcast_video)
async def process_broadcast_video(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not message.video:
        await bot.send_message(chat_id, "⚠️ يرجى إرسال فيديو.")
        return
    
    video_file = message.video
    file_info = await bot.get_file(video_file.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    
    video_path = os.path.join(TEMP_FOLDER, f"broadcast_{generate_unique_id()}.mp4")
    with open(video_path, 'wb') as f:
        f.write(downloaded_file)
    
    text = message.caption or "📹"
    add_to_broadcast_queue(text, 'video', video_path, user_id)
    await bot.send_message(chat_id, "✅ تم إضافة الفيديو إلى قائمة البث.")
    await bot.send_message(
        chat_id,
        "⚠️ هل تريد تأكيد إرسال البث لجميع المستخدمين؟",
        reply_markup=get_confirm_keyboard()
    )
    await state.clear()

@dp.message(BotStates.waiting_for_restore_backup)
async def process_restore(message: Message, state: FSMContext):
    chat_id = message.chat.id
    
    if not message.document:
        await bot.send_message(chat_id, "⚠️ يرجى إرسال ملف ZIP.")
        return
    
    file_id = message.document.file_id
    file_info = await bot.get_file(file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    
    zip_path = os.path.join(TEMP_FOLDER, f"restore_{generate_unique_id()}.zip")
    with open(zip_path, 'wb') as f:
        f.write(downloaded_file)
    
    try:
        success = restore_backup_file(zip_path)
        if success:
            await bot.send_message(chat_id, "✅ تم استرجاع النسخة الاحتياطية بنجاح!")
            log_security_event('restore_backup', message.from_user.id, f'Restored from {message.document.file_name}')
            load_admins_from_db()
        else:
            await bot.send_message(chat_id, "❌ فشل استرجاع النسخة الاحتياطية!")
    except Exception as e:
        await bot.send_message(chat_id, f"❌ خطأ في الاسترجاع: {str(e)}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    
    await state.clear()

@dp.message(BotStates.waiting_for_welcome_message)
async def process_welcome(message: Message, state: FSMContext):
    chat_id = message.chat.id
    welcome_text = message.text
    
    if not welcome_text:
        await bot.send_message(chat_id, "⚠️ الرسالة فارغة!")
        await state.clear()
        return
    
    set_welcome_message(welcome_text)
    await bot.send_message(chat_id, "✅ تم تغيير رسالة الترحيب بنجاح!")
    await state.clear()

@dp.message(BotStates.waiting_for_edit_admin_name)
async def process_edit_admin_name(message: Message, state: FSMContext):
    chat_id = message.chat.id
    new_name = message.text.strip()
    
    if not new_name:
        await bot.send_message(chat_id, "⚠️ الاسم فارغ!")
        await state.clear()
        return
    
    data = await state.get_data()
    edit_user_id = data.get('edit_user_id')
    
    if set_admin_name(edit_user_id, new_name):
        await bot.send_message(chat_id, f"✅ تم تغيير اسم الأدمن بنجاح إلى `{new_name}`")
    else:
        await bot.send_message(chat_id, "❌ فشل تغيير الاسم!")
    
    await state.clear()

# ========== SECURITY MONITOR ==========
def security_monitor():
    while True:
        try:
            time.sleep(60)
        except:
            time.sleep(60)

monitor_thread = threading.Thread(target=security_monitor, daemon=True)
monitor_thread.start()

# ========== MAIN ==========
async def main():
    print("=" * 50)
    print("🚀 تم تطوير البوت بالكامل مع جميع المميزات المطلوبة 2026")
    print("=" * 50)
    print("🎨 الأزرار ملونة مع دعم Style (primary, success, danger)")
    print("🔄 يتم تشغيل جميع الروابط تلقائياً كل 10 ساعات")
    print("💾 جميع الملفات محفوظة في قاعدة البيانات بشكل دائم")
    print("📥 ميزة مسح رسائل الأدمن والمالك")
    print("🔍 البحث التلقائي عند إرسال اسم الخصم")
    print("📝 ميزة تغيير رسالة الترحيب")
    print("✏️ ميزة تغيير أسماء الأدمن")
    print("👑 قائمة الأدمن مرتبة وملونة")
    print("=" * 50)
    
    try:
        restored, failed = restore_all_links()
        deleted_restored = restore_deleted_links()
        print(f"✅ تم استرجاع {restored} رابط، {deleted_restored} رابط محذوف")
    except:
        pass
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())