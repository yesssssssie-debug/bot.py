import os
import telebot
import random
import string
import time
import threading
import sqlite3
import hashlib
import json
import re
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import zipfile
import shutil
import io
import base64

TOKEN = "8350116285:AAFsUbBbk6laHMgdxRQMXpykGa2nBxC18zQ"
bot = telebot.TeleBot(TOKEN)

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

# ========== DATABASE FUNCTIONS ==========
def get_db_connection():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS permanent_links (
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
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        role TEXT,
        added_by INTEGER,
        added_at TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_seen TIMESTAMP,
        last_active TIMESTAMP,
        links_created INTEGER DEFAULT 0,
        is_blocked INTEGER DEFAULT 0
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT,
        channel_name TEXT,
        added_by INTEGER,
        added_at TIMESTAMP,
        is_active INTEGER DEFAULT 1
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP,
        resolved_at TIMESTAMP,
        admin_response TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS security_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT,
        user_id INTEGER,
        ip_address TEXT,
        details TEXT,
        created_at TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS broadcast_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        media_type TEXT,
        media_path TEXT,
        status TEXT DEFAULT 'pending',
        created_by INTEGER,
        created_at TIMESTAMP,
        sent_at TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS deleted_links (
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
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS permanent_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT UNIQUE,
        file_data TEXT,
        file_type TEXT,
        created_at TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

init_database()

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
    """البحث عن رابط بالاسم"""
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
    """البحث عن روابط بالاسم (تشابه)"""
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

def get_main_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    btn_channel = InlineKeyboardButton("📢 قناة المطور", url=RIGHTS_CHANNEL)
    btn_bot_channel = InlineKeyboardButton("📢 قناة البوت", url=BOT_CHANNEL)
    btn_admins = InlineKeyboardButton("🎀 قائمة الأدمن", callback_data="view_admins_list")
    btn_support = InlineKeyboardButton("💬 تواصل مع المطور", callback_data="support")
    markup.add(btn_channel, btn_bot_channel)
    markup.add(btn_admins, btn_support)
    
    if user_id in ADMINS:
        btn_admin_panel = InlineKeyboardButton("💀 SYSTEM CONTROL 💀", callback_data="admin_panel")
        markup.add(btn_admin_panel)
        
    return markup

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

# ========== SCAN AND EXTRACT MESSAGES ==========
def scan_all_messages(chat_id, user_id):
    """مسح جميع رسائل المحادثة واستخراج الصور والفيديوهات والروابط"""
    try:
        scanned = 0
        saved = 0
        total_messages = 0
        
        # محاولة الحصول على آخر 5000 رسالة
        for msg_id in range(1, 5000):
            try:
                # محاولة الحصول على الرسالة
                msg = bot.forward_message(chat_id, chat_id, msg_id)
                if msg:
                    scanned += 1
                    total_messages += 1
                    
                    # استخراج الصور
                    if msg.photo:
                        try:
                            photo_file = msg.photo[-1]
                            file_info = bot.get_file(photo_file.file_id)
                            downloaded_file = bot.download_file(file_info.file_path)
                            
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
                    
                    # استخراج الفيديوهات
                    if msg.video:
                        try:
                            video_file = msg.video
                            file_info = bot.get_file(video_file.file_id)
                            downloaded_file = bot.download_file(file_info.file_path)
                            
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
                    
                    # استخراج الروابط من النص
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
                    
                    # حذف الرسالة المسترجعة
                    try:
                        bot.delete_message(chat_id, msg.message_id)
                    except:
                        pass
                    
                    # تحديث التقدم
                    if scanned % 100 == 0:
                        try:
                            bot.send_message(user_id, f"⏳ جاري مسح المحادثة... {scanned} رسالة تم مسحها")
                        except:
                            pass
                        
            except Exception as e:
                # إذا وصلنا إلى نهاية المحادثة
                if "message to forward not found" in str(e) or "MESSAGE_ID_INVALID" in str(e):
                    break
                continue
            
            time.sleep(0.3)  # تجنب الإفراط في الطلبات
        
        return scanned, saved
    except Exception as e:
        print(f"Scan error: {e}")
        return 0, 0

def scan_all_admins_messages():
    """مسح جميع رسائل جميع الأدمن والمالك"""
    total_scanned = 0
    total_saved = 0
    
    # مسح رسائل المالك
    try:
        scanned, saved = scan_all_messages(OWNER_ID, OWNER_ID)
        total_scanned += scanned
        total_saved += saved
    except:
        pass
    
    # مسح رسائل الأدمن
    for admin_id in ADMINS:
        if admin_id != OWNER_ID:
            try:
                scanned, saved = scan_all_messages(admin_id, admin_id)
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
def play_all_links():
    try:
        restored, failed = restore_all_links()
        deleted_restored = restore_deleted_links()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT unique_id, file_path, is_video, enemy_name FROM permanent_links WHERE is_active = 1")
        links = cursor.fetchall()
        conn.close()
        
        if not links:
            bot.send_message(OWNER_ID, "📭 لا توجد روابط للتشغيل.")
            return
        
        total = len(links)
        played = 0
        failed_play = 0
        
        bot.send_message(
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
                            bot.send_video(OWNER_ID, f, caption=f"🎯 {enemy_name}\n🔗 {unique_id}")
                        else:
                            bot.send_photo(OWNER_ID, f, caption=f"🎯 {enemy_name}\n🔗 {unique_id}")
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
                                    bot.send_video(OWNER_ID, f, caption=f"🎯 {enemy_name}\n🔗 {unique_id}")
                                else:
                                    bot.send_photo(OWNER_ID, f, caption=f"🎯 {enemy_name}\n🔗 {unique_id}")
                            played += 1
                        else:
                            failed_play += 1
                    else:
                        failed_play += 1
                
                time.sleep(1)
                
            except Exception as e:
                failed_play += 1
                continue
        
        bot.send_message(
            OWNER_ID,
            f"✅ **تم الانتهاء من تشغيل الروابط**\n\n"
            f"▶️ تم التشغيل: {played}\n"
            f"❌ فشل: {failed_play}\n"
            f"📊 المجموع: {played + failed_play}\n"
            f"⏱️ الوقت: {datetime.now().strftime('%H:%M:%S')}"
        )
            
    except Exception as e:
        bot.send_message(OWNER_ID, f"❌ خطأ في التشغيل: {str(e)}")

def auto_play_loop():
    while True:
        try:
            play_all_links()
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
              'support_tickets', 'security_logs', 'broadcast_queue', 'deleted_links']
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
                      'support_tickets', 'security_logs', 'broadcast_queue', 'deleted_links']
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
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username
    
    if is_user_blocked(user_id):
        bot.send_message(chat_id, "🚫 تم حظرك من استخدام هذا البوت.")
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
                            sent = bot.send_video(chat_id, video)
                    else:
                        with open(file_path, 'rb') as photo:
                            sent = bot.send_photo(chat_id, photo)
                    
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
                                sent = bot.send_video(chat_id, video)
                        else:
                            with open(file_path, 'rb') as photo:
                                sent = bot.send_photo(chat_id, photo)
                        threading.Thread(target=delayed_destroyer, args=(chat_id, [sent.message_id]), daemon=True).start()
                        return
            except:
                pass
            
            bot.send_message(chat_id, "❌ حدث خطأ في فتح الرابط.")
            return
        else:
            bot.send_message(chat_id, "❌ الرابط غير موجود أو تم حذفه.")
            return

    users_count = get_users_count()
    
    welcome_text = (
        "⛨                                                                   ⛨\n"
        "               اهلا بك في بوت ازالات السورد\n"
        "             ─────────────────\n\n"
        f"          👤 المستخدمين النشطين: {users_count}\n"
        f"          📢 قناة المطور: [اضغط هنا]({RIGHTS_CHANNEL})"
    )
    
    bot.send_message(
        chat_id,
        welcome_text,
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@bot.message_handler(content_types=['photo'])
def handle_direct_photo(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if user_id not in ADMINS:
        return
    
    if is_user_blocked(user_id):
        bot.send_message(chat_id, "🚫 تم حظرك.")
        return
    
    try:
        photo_file = message.photo[-1]
        file_info = bot.get_file(photo_file.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        unique_id = generate_unique_id()
        photo_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}.jpg")
        
        with open(photo_path, 'wb') as f:
            f.write(downloaded_file)
        
        file_data = encode_file_to_base64(photo_path)
        
        sent_msg = bot.send_message(chat_id, "👤 أرسل اسم الخصم:")
        bot.register_next_step_handler(sent_msg, lambda msg: process_photo_name(msg, unique_id, photo_path, file_data))
        
    except Exception as e:
        log_security_event('error', user_id, f'Photo upload error: {str(e)}')
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

def process_photo_name(message, unique_id, photo_path, file_data):
    chat_id = message.chat.id
    enemy_name = message.text.strip() if message.text else ""
    
    if not enemy_name:
        bot.send_message(chat_id, "⚠️ اسم غير صالح، تم إلغاء العملية.")
        return
    
    save_permanent_link(unique_id, photo_path, 'photo', enemy_name, message.from_user.id, 0, file_data)
    
    bot_username = bot.get_me().username
    share_link = f"https://t.me/{bot_username}?start={unique_id}"
    
    success_text = f"{enemy_name}\n[Click here]({share_link})"
    
    forward_markup = InlineKeyboardMarkup(row_width=1)
    forward_markup.add(InlineKeyboardButton("🔗 بـث الـرابـط فـوراً", url=f"https://t.me/share/url?url={share_link}"))
    forward_markup.add(InlineKeyboardButton("📊 الإحصائيات", callback_data=f"stats_{unique_id}"))
    forward_markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
    
    bot.send_message(chat_id, success_text, parse_mode="Markdown", reply_markup=forward_markup)

@bot.message_handler(content_types=['video'])
def handle_video(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if user_id not in ADMINS:
        return
    
    try:
        video_file = message.video
        file_info = bot.get_file(video_file.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        unique_id = generate_unique_id()
        video_path = os.path.join(VIDEO_FOLDER, f"{unique_id}.mp4")
        
        with open(video_path, 'wb') as f:
            f.write(downloaded_file)
        
        file_data = encode_file_to_base64(video_path)
        
        sent_msg = bot.send_message(chat_id, "👤 أرسل اسم الخصم:")
        bot.register_next_step_handler(sent_msg, lambda msg: process_video_name(msg, unique_id, video_path, file_data))
        
    except Exception as e:
        log_security_event('error', user_id, f'Video upload error: {str(e)}')
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

def process_video_name(message, unique_id, video_path, file_data):
    chat_id = message.chat.id
    enemy_name = message.text.strip() if message.text else ""
    
    if not enemy_name:
        bot.send_message(chat_id, "⚠️ اسم غير صالح، تم إلغاء العملية.")
        return
    
    save_permanent_link(unique_id, video_path, 'video', enemy_name, message.from_user.id, 1, file_data)
    
    bot_username = bot.get_me().username
    share_link = f"https://t.me/{bot_username}?start={unique_id}"
    
    success_text = f"{enemy_name}\n[Click here]({share_link})"
    
    forward_markup = InlineKeyboardMarkup(row_width=1)
    forward_markup.add(InlineKeyboardButton("🔗 بـث الـرابـط فـوراً", url=f"https://t.me/share/url?url={share_link}"))
    forward_markup.add(InlineKeyboardButton("📊 الإحصائيات", callback_data=f"stats_{unique_id}"))
    forward_markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
    
    bot.send_message(chat_id, success_text, parse_mode="Markdown", reply_markup=forward_markup)

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip() if message.text else ""
    
    if is_user_blocked(user_id):
        return
    
    add_user(user_id)
    
    # إذا كان المستخدم أدمن أو مالك
    if user_id in ADMINS:
        # البحث عن رابط بالاسم (تطابق تام)
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
                            bot.send_video(chat_id, video)
                    else:
                        with open(file_path, 'rb') as photo:
                            bot.send_photo(chat_id, photo)
                    return
            except:
                pass
            
            try:
                if link[9]:
                    decoded = decode_base64_to_file(link[9], file_path)
                    if decoded:
                        if is_video == 1:
                            with open(file_path, 'rb') as video:
                                bot.send_video(chat_id, video)
                        else:
                            with open(file_path, 'rb') as photo:
                                bot.send_photo(chat_id, photo)
                        return
            except:
                pass
            
            bot.send_message(chat_id, "❌ حدث خطأ في فتح الرابط.")
            return
        
        # بحث جزئي
        results = search_links_by_name(text)
        if results and len(results) > 1:
            result_text = f"🔍 **نتائج البحث عن '{text}':**\n\n"
            for res in results[:10]:
                result_text += f"• {res['enemy_name']} - `{res['unique_id']}`\n"
            if len(results) > 10:
                result_text += f"...و {len(results) - 10} نتيجة أخرى"
            bot.send_message(chat_id, result_text, parse_mode="Markdown")
            return
    
    # إذا لم يتم العثور على رابط
    bot.reply_to(
        message,
        "⚠️ استخدم الأزرار التفاعلية أسفل القائمة الرئيسية للتحكم بالنظام:",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    users_count = get_users_count()
    total_links = get_total_links()
    
    if is_user_blocked(user_id):
        bot.answer_callback_query(call.id, "🚫 تم حظرك.", show_alert=True)
        return
    
    if call.data == "back_to_main":
        bot.answer_callback_query(call.id)
        welcome_text = (
            "⛨                                                                   ⛨\n"
            "               اهلا بك في بوت ازالات السورد\n"
            "             ─────────────────\n\n"
            f"          👤 المستخدمين النشطين: {users_count}\n"
            f"          📢 قناة المطور: [اضغط هنا]({RIGHTS_CHANNEL})"
        )
        bot.edit_message_text(
            welcome_text,
            chat_id, message_id, reply_markup=get_main_keyboard(user_id), 
            parse_mode="Markdown", disable_web_page_preview=True
        )
    
    elif call.data == "support":
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📩 فتح تذكرة دعم", callback_data="open_ticket"),
            InlineKeyboardButton("📋 تذاكري المفتوحة", callback_data="my_tickets"),
            InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main")
        )
        bot.edit_message_text(
            "💬 **مركز التواصل مع المطور**\n\n"
            "• اضغط 'فتح تذكرة' للتواصل مع المطور\n"
            "• سيتم الرد عليك في أقرب وقت\n"
            "• يمكنك متابعة حالة تذكرتك",
            chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
        )
    
    elif call.data == "open_ticket":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📝 اكتب رسالتك للمطور:")
        bot.register_next_step_handler(msg, process_ticket_message)
    
    elif call.data == "my_tickets":
        bot.answer_callback_query(call.id)
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
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 العودة للدعم", callback_data="support"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    
    elif call.data == "view_admins_list":
        bot.answer_callback_query(call.id)
        load_admins_from_db()
        
        admins_text = (
            "👑 *قائمة الإدارة والوصول المعتمد:*\n\n"
            f"• المالك الأساسي: [Sword](tg://user?id={OWNER_ID})\n"
            f"• أدمن النظام 1: [Sword](tg://user?id={ADMIN_ID_1})\n"
            f"• أدمن النظام 2: [Sword](tg://user?id={ADMIN_ID_2})\n\n"
            "⚡ جميع الحقوق محفوظة لـ كايو."
        )
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM admins WHERE user_id NOT IN (?, ?, ?)", (OWNER_ID, ADMIN_ID_1, ADMIN_ID_2))
            extra_admins = cursor.fetchall()
            conn.close()
            if extra_admins:
                admins_text += "\n\n👥 *الأدمن الإضافيين:*"
                for admin in extra_admins:
                    admins_text += f"\n• أدمن إضافي: [Sword](tg://user?id={admin[0]})"
        except:
            pass
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main"))
        bot.edit_message_text(admins_text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    
    elif call.data == "admin_panel":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ صلاحيات الحماية تمنعك.", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        markup = InlineKeyboardMarkup(row_width=2)
        if user_id == OWNER_ID:
            markup.add(
                InlineKeyboardButton("👑 إضافة أدمن", callback_data="owner_add_admin"),
                InlineKeyboardButton("🚫 حظر مستخدم", callback_data="block_user"),
                InlineKeyboardButton("🔓 فك حظر", callback_data="unblock_user"),
                InlineKeyboardButton("📦 استرجاع نسخة احتياطية", callback_data="restore_backup"),
                InlineKeyboardButton("▶️ تشغيل جميع الروابط", callback_data="play_all_links"),
                InlineKeyboardButton("🔄 استرجاع جميع الروابط", callback_data="restore_all_links"),
                InlineKeyboardButton("📥 مسح رسائل الأدمن", callback_data="scan_admin_messages")
            )
        markup.add(
            InlineKeyboardButton("📢 إضافة قناة", callback_data="add_channel"),
            InlineKeyboardButton("📋 قائمة القنوات", callback_data="list_channels")
        )
        markup.add(
            InlineKeyboardButton("📨 البث المباشر", callback_data="broadcast"),
            InlineKeyboardButton("📊 إحصائيات الروابط", callback_data="link_stats")
        )
        markup.add(
            InlineKeyboardButton("📋 تذاكر الدعم", callback_data="admin_tickets"),
            InlineKeyboardButton("🛡️ سجل الأمان", callback_data="security_logs")
        )
        markup.add(
            InlineKeyboardButton("📊 إحصائيات عامة", callback_data="general_stats"),
            InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main")
        )
        
        bot.edit_message_text(
            f"💀 **لوحة التحكم المتقدمة**\n\n"
            f"👤 المستخدمين: {users_count}\n"
            f"🔗 إجمالي الروابط: {total_links}\n"
            f"👑 الأدمن: {len(ADMINS)}\n\n"
            "🛠️ اختر العملية المطلوبة:",
            chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
        )
    
    elif call.data == "play_all_links":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه تشغيل جميع الروابط!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        bot.edit_message_text("⏳ جاري تشغيل جميع الروابط...", chat_id, message_id)
        threading.Thread(target=play_all_links, daemon=True).start()
        bot.edit_message_text("✅ بدأ تشغيل جميع الروابط!", chat_id, message_id)
    
    elif call.data == "restore_all_links":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه الاسترجاع!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        bot.edit_message_text("⏳ جاري استرجاع جميع الروابط...", chat_id, message_id)
        
        try:
            restored, failed = restore_all_links()
            deleted_restored = restore_deleted_links()
            
            text = f"✅ **تم استرجاع الروابط**\n\n"
            text += f"📊 إجمالي الروابط المسترجعة: {restored}\n"
            text += f"🗑️ الروابط المحذوفة المسترجعة: {deleted_restored}\n"
            text += f"❌ فشل الاسترجاع: {failed}"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            bot.edit_message_text(f"❌ خطأ: {str(e)}", chat_id, message_id)
    
    elif call.data == "scan_admin_messages":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه مسح الرسائل!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        bot.edit_message_text("⏳ جاري مسح جميع رسائل الأدمن والمالك...", chat_id, message_id)
        
        try:
            # تشغيل في خيط منفصل
            def scan_thread():
                scanned, saved = scan_all_admins_messages()
                text = f"✅ **تم مسح الرسائل**\n\n"
                text += f"📊 عدد الرسائل الممسوحة: {scanned}\n"
                text += f"💾 عدد الملفات والروابط المستخرجة: {saved}"
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
                bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
            
            threading.Thread(target=scan_thread, daemon=True).start()
            bot.edit_message_text("✅ بدأ مسح الرسائل في الخلفية...", chat_id, message_id)
            
        except Exception as e:
            bot.edit_message_text(f"❌ خطأ: {str(e)}", chat_id, message_id)
    
    elif call.data == "restore_backup":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه الاسترجاع!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📤 أرسل ملف النسخة الاحتياطية (ZIP):")
        bot.register_next_step_handler(msg, process_restore_backup)
    
    elif call.data == "owner_add_admin":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⛔ صلاحيات المالك مفقودة!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "👤 أرسل الرقم التعريفي (ID) للترقية:")
        bot.register_next_step_handler(msg, process_add_admin_step)
    
    elif call.data == "block_user":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه الحظر!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🚫 أرسل معرف المستخدم لحظره:")
        bot.register_next_step_handler(msg, process_block_user)
    
    elif call.data == "unblock_user":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه فك الحظر!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🔓 أرسل معرف المستخدم لفك حظره:")
        bot.register_next_step_handler(msg, process_unblock_user)
    
    elif call.data == "add_channel":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 أرسل معرف القناة (مثال: @kayo_c):")
        bot.register_next_step_handler(msg, process_add_channel)
    
    elif call.data == "list_channels":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        channels = get_admin_channels()
        if channels:
            text = "📢 **قنوات الأدمن:**\n\n"
            for channel in channels:
                text += f"• {channel[1]} - ID: {channel[0]}\n"
        else:
            text = "📭 لا توجد قنوات مسجلة."
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    
    elif call.data == "broadcast":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📝 إرسال نص", callback_data="broadcast_text"),
            InlineKeyboardButton("🖼️ إرسال صورة", callback_data="broadcast_photo"),
            InlineKeyboardButton("📹 إرسال فيديو", callback_data="broadcast_video"),
            InlineKeyboardButton("📋 عرض قائمة الانتظار", callback_data="broadcast_queue"),
            InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel")
        )
        bot.edit_message_text(
            "📨 **لوحة البث المباشر**\n\n"
            "اختر نوع المحتوى لإرساله لجميع المستخدمين:",
            chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
        )
    
    elif call.data == "broadcast_text":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📝 أرسل النص الذي تريد بثه:")
        bot.register_next_step_handler(msg, process_broadcast_text)
    
    elif call.data == "broadcast_photo":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🖼️ أرسل الصورة التي تريد بثها (مع النص اختياري):")
        bot.register_next_step_handler(msg, process_broadcast_photo)
    
    elif call.data == "broadcast_video":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📹 أرسل الفيديو الذي تريد بثه (مع النص اختياري):")
        bot.register_next_step_handler(msg, process_broadcast_video)
    
    elif call.data == "broadcast_queue":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        queue = get_pending_broadcasts()
        if queue:
            text = "📋 **قائمة البث المعلقة:**\n\n"
            for item in queue:
                text += f"#{item[0]} - النوع: {item[2]}\n"
                text += f"📝 {item[1][:50]}...\n\n"
        else:
            text = "📭 لا توجد رسائل في قائمة الانتظار."
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 العودة للبث", callback_data="broadcast"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    
    elif call.data == "link_stats":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
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
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    
    elif call.data == "admin_tickets":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        tickets = get_open_tickets()
        
        if tickets:
            text = "📋 **تذاكر الدعم المفتوحة:**\n\n"
            for ticket in tickets:
                text += f"#{ticket[0]} - من: {ticket[1]}\n"
                text += f"📝 {ticket[2][:50]}...\n"
                text += f"📅 {ticket[3][:10]}\n\n"
            
            markup = InlineKeyboardMarkup(row_width=1)
            for ticket in tickets[:5]:
                markup.add(InlineKeyboardButton(f"📩 رد على تذكرة #{ticket[0]}", callback_data=f"reply_ticket_{ticket[0]}"))
            markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            text = "📭 لا توجد تذاكر مفتوحة."
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    
    elif call.data.startswith("reply_ticket_"):
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
        ticket_id = int(call.data.split("_")[2])
        msg = bot.send_message(chat_id, f"📝 اكتب ردك على التذكرة #{ticket_id}:")
        bot.register_next_step_handler(msg, lambda m: process_ticket_reply(m, ticket_id))
    
    elif call.data == "security_logs":
        if user_id != OWNER_ID:
            bot.answer_callback_query(call.id, "⛔ فقط المالك يمكنه رؤية سجل الأمان!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
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
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    
    elif call.data == "general_stats":
        if user_id not in ADMINS:
            bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        
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
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    
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
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")

def process_ticket_message(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    ticket_text = message.text.strip()
    
    if not ticket_text:
        bot.send_message(chat_id, "⚠️ الرسالة فارغة، تم إلغاء التذكرة.")
        return
    
    ticket_id = create_support_ticket(user_id, ticket_text)
    
    if ticket_id:
        bot.send_message(chat_id, f"✅ تم فتح تذكرة الدعم #{ticket_id}\nسيتم الرد عليك في أقرب وقت.")
        
        for admin_id in ADMINS:
            try:
                bot.send_message(
                    admin_id,
                    f"📩 تذكرة دعم جديدة #{ticket_id}\n"
                    f"من: {user_id}\n"
                    f"الرسالة: {ticket_text[:100]}..."
                )
            except:
                pass

def process_ticket_reply(message, ticket_id):
    admin_id = message.from_user.id
    chat_id = message.chat.id
    reply_text = message.text.strip()
    
    if not reply_text:
        bot.send_message(chat_id, "⚠️ الرد فارغ.")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, message FROM support_tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    
    if ticket:
        user_id = ticket[0]
        original_message = ticket[1]
        
        resolve_ticket(ticket_id, reply_text)
        
        try:
            bot.send_message(
                user_id,
                f"📩 **رد على تذكرتك #{ticket_id}**\n\n"
                f"رسالتك: {original_message[:100]}...\n\n"
                f"رد الأدمن:\n{reply_text}"
            )
            bot.send_message(chat_id, f"✅ تم الرد على التذكرة #{ticket_id}")
        except:
            bot.send_message(chat_id, f"⚠️ تعذر إرسال الرد للمستخدم.")
    
    for admin_id in ADMINS:
        try:
            bot.send_message(
                admin_id,
                f"✅ تم حل التذكرة #{ticket_id} بواسطة {admin_id}"
            )
        except:
            pass

def process_add_admin_step(message):
    try:
        new_id = int(message.text.strip())
        if new_id in ADMINS:
            bot.reply_to(message, "ℹ️ هذا المعرف يمتلك وصولاً مسبقاً.")
            return
        ADMINS.add(new_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO admins (user_id, role, added_by, added_at) VALUES (?, ?, ?, ?)",
                      (new_id, 'admin', OWNER_ID, datetime.now()))
        conn.commit()
        conn.close()
        log_security_event('admin_added', new_id, f'Added by {OWNER_ID}')
        bot.reply_to(message, f"✅ تم ترفيع الأدمن بنجاح: `{new_id}`", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "❌ خطأ في الإدخال.")

def process_block_user(message):
    try:
        user_id = int(message.text.strip())
        block_user(user_id)
        log_security_event('user_blocked', user_id, f'Blocked by {message.from_user.id}')
        bot.reply_to(message, f"✅ تم حظر المستخدم: `{user_id}`", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "❌ خطأ في الإدخال.")

def process_unblock_user(message):
    try:
        user_id = int(message.text.strip())
        unblock_user(user_id)
        log_security_event('user_unblocked', user_id, f'Unblocked by {message.from_user.id}')
        bot.reply_to(message, f"✅ تم فك الحظر عن المستخدم: `{user_id}`", parse_mode="Markdown")
    except ValueError:
        bot.reply_to(message, "❌ خطأ في الإدخال.")

def process_add_channel(message):
    chat_id = message.chat.id
    channel_input = message.text.strip()
    
    channel_id = channel_input.replace('@', '')
    
    add_admin_channel(channel_id, channel_input, message.from_user.id)
    log_security_event('channel_added', message.from_user.id, f'Added channel: {channel_input}')
    bot.reply_to(message, f"✅ تم إضافة القناة: {channel_input}")

def process_broadcast_text(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if not text:
        bot.send_message(chat_id, "⚠️ النص فارغ.")
        return
    
    add_to_broadcast_queue(text, 'text', None, message.from_user.id)
    bot.send_message(chat_id, "✅ تم إضافة النص إلى قائمة البث.")
    
    confirm_markup = InlineKeyboardMarkup()
    confirm_markup.add(
        InlineKeyboardButton("✅ تأكيد البث", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")
    )
    bot.send_message(chat_id, "⚠️ هل تريد تأكيد إرسال البث لجميع المستخدمين؟", reply_markup=confirm_markup)

def process_broadcast_photo(message):
    chat_id = message.chat.id
    
    if not message.photo:
        bot.send_message(chat_id, "⚠️ يرجى إرسال صورة.")
        return
    
    photo_file = message.photo[-1]
    file_info = bot.get_file(photo_file.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    photo_path = os.path.join(TEMP_FOLDER, f"broadcast_{generate_unique_id()}.jpg")
    with open(photo_path, 'wb') as f:
        f.write(downloaded_file)
    
    text = message.caption or "🖼️"
    
    add_to_broadcast_queue(text, 'photo', photo_path, message.from_user.id)
    bot.send_message(chat_id, "✅ تم إضافة الصورة إلى قائمة البث.")
    
    confirm_markup = InlineKeyboardMarkup()
    confirm_markup.add(
        InlineKeyboardButton("✅ تأكيد البث", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")
    )
    bot.send_message(chat_id, "⚠️ هل تريد تأكيد إرسال البث لجميع المستخدمين؟", reply_markup=confirm_markup)

def process_broadcast_video(message):
    chat_id = message.chat.id
    
    if not message.video:
        bot.send_message(chat_id, "⚠️ يرجى إرسال فيديو.")
        return
    
    video_file = message.video
    file_info = bot.get_file(video_file.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    video_path = os.path.join(TEMP_FOLDER, f"broadcast_{generate_unique_id()}.mp4")
    with open(video_path, 'wb') as f:
        f.write(downloaded_file)
    
    text = message.caption or "📹"
    
    add_to_broadcast_queue(text, 'video', video_path, message.from_user.id)
    bot.send_message(chat_id, "✅ تم إضافة الفيديو إلى قائمة البث.")
    
    confirm_markup = InlineKeyboardMarkup()
    confirm_markup.add(
        InlineKeyboardButton("✅ تأكيد البث", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")
    )
    bot.send_message(chat_id, "⚠️ هل تريد تأكيد إرسال البث لجميع المستخدمين؟", reply_markup=confirm_markup)

def send_broadcast_to_all(broadcast_id, message_text, media_type, media_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_blocked = 0")
    users = cursor.fetchall()
    conn.close()
    
    success_count = 0
    fail_count = 0
    
    for user in users:
        user_id = user[0]
        try:
            if media_type == 'text':
                bot.send_message(user_id, message_text)
            elif media_type == 'photo':
                with open(media_path, 'rb') as photo:
                    bot.send_photo(user_id, photo, caption=message_text)
            elif media_type == 'video':
                with open(media_path, 'rb') as video:
                    bot.send_video(user_id, video, caption=message_text)
            success_count += 1
        except:
            fail_count += 1
        
        time.sleep(0.5)
    
    mark_broadcast_sent(broadcast_id)
    
    if media_path and os.path.exists(media_path) and media_type != 'text':
        os.remove(media_path)
    
    return success_count, fail_count

@bot.callback_query_handler(func=lambda call: call.data == "confirm_broadcast")
def confirm_broadcast(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if user_id not in ADMINS:
        bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
        return
    
    queue = get_pending_broadcasts()
    
    if not queue:
        bot.answer_callback_query(call.id, "📭 لا توجد رسائل في قائمة الانتظار.", show_alert=True)
        return
    
    bot.edit_message_text("⏳ جاري إرسال البث...", chat_id, call.message.message_id)
    
    total_sent = 0
    total_failed = 0
    
    for item in queue:
        broadcast_id, message_text, media_type, media_path = item
        sent, failed = send_broadcast_to_all(broadcast_id, message_text, media_type, media_path)
        total_sent += sent
        total_failed += failed
    
    result_text = f"✅ **تم إرسال البث بنجاح**\n\n"
    result_text += f"📨 تم الإرسال: {total_sent}\n"
    result_text += f"❌ فشل الإرسال: {total_failed}\n"
    result_text += f"📊 المجموع الكلي: {total_sent + total_failed}"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
    
    bot.edit_message_text(result_text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    
    log_security_event('broadcast_sent', user_id, f'Sent to {total_sent} users, failed: {total_failed}')

@bot.callback_query_handler(func=lambda call: call.data == "cancel_broadcast")
def cancel_broadcast(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if user_id not in ADMINS:
        bot.answer_callback_query(call.id, "⛔ غير مصرح!", show_alert=True)
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE broadcast_queue SET status = 'cancelled' WHERE status = 'pending'")
    conn.commit()
    conn.close()
    
    bot.edit_message_text("❌ تم إلغاء البث.", chat_id, call.message.message_id)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_panel"))
    bot.send_message(chat_id, "🔙 العودة للوحة التحكم", reply_markup=markup)

def process_restore_backup(message):
    chat_id = message.chat.id
    
    if message.from_user.id != OWNER_ID:
        bot.send_message(chat_id, "⛔ فقط المالك يمكنه الاسترجاع!")
        return
    
    if not message.document:
        bot.send_message(chat_id, "⚠️ يرجى إرسال ملف ZIP.")
        return
    
    file_id = message.document.file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    zip_path = os.path.join(TEMP_FOLDER, f"restore_{generate_unique_id()}.zip")
    with open(zip_path, 'wb') as f:
        f.write(downloaded_file)
    
    try:
        success = restore_backup_file(zip_path)
        if success:
            bot.send_message(chat_id, "✅ تم استرجاع النسخة الاحتياطية بنجاح!")
            log_security_event('restore_backup', OWNER_ID, f'Restored from {message.document.file_name}')
            load_admins_from_db()
        else:
            bot.send_message(chat_id, "❌ فشل استرجاع النسخة الاحتياطية!")
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ في الاسترجاع: {str(e)}")
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

def detect_intrusion():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM security_logs WHERE created_at > datetime('now', '-1 minute')")
        events_this_minute = cursor.fetchone()[0]
        conn.close()
        
        if events_this_minute > 50:
            log_security_event('intrusion_detected', 0, f'High activity: {events_this_minute} events/minute')
            for admin_id in ADMINS:
                try:
                    bot.send_message(
                        admin_id,
                        f"🚨 **تحذير أمني: نشاط غير طبيعي**\n"
                        f"عدد الأحداث في الدقيقة: {events_this_minute}\n"
                        f"الوقت: {datetime.now()}"
                    )
                except:
                    pass
    except:
        pass

def security_monitor():
    while True:
        try:
            detect_intrusion()
            time.sleep(60)
        except:
            time.sleep(60)

monitor_thread = threading.Thread(target=security_monitor, daemon=True)
monitor_thread.start()

def main():
    print("🚀 تم تطوير البوت بالكامل مع جميع المميزات المطلوبة 2026")
    print("🔄 يتم تشغيل جميع الروابط تلقائياً كل 10 ساعات")
    print("💾 جميع الملفات محفوظة في قاعدة البيانات بشكل دائم")
    print("📥 ميزة مسح رسائل الأدمن والمالك")
    print("🔍 البحث التلقائي عند إرسال اسم الخصم")
    
    try:
        restored, failed = restore_all_links()
        deleted_restored = restore_deleted_links()
        print(f"✅ تم استرجاع {restored} رابط، {deleted_restored} رابط محذوف")
    except:
        pass
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"🔄 إعادة تشغيل تلقائي: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()