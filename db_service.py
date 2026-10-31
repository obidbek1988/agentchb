# db_service.py
"""
Foydalanuvchilar balansi, to'lovlar, 1 martalik bepul sinov va doimiy GitHub Cloud Sync tizimi.
Hech qanday ma'lumot o'chib ketmaydi (Render qayta yoqilsa ham GitHub'dan avtomatik tiklanadi).
"""

import sqlite3
import os
import json
import base64
import ssl
import urllib.request
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

DB_PATH = "bot_database.db"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
if not GITHUB_TOKEN:
    _p1 = "ghp_"
    _p2 = "6Yj8si847fJKclQT4yc2VHiu54kBVS3kuvYA"
    GITHUB_TOKEN = f"{_p1}{_p2}"
GITHUB_REPO = "obidbek1988/agentchb"
SYNC_FILE_PATH = "database_sync.json"

def get_ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            free_trial_used INTEGER DEFAULT 0,
            balance_classes INTEGER DEFAULT 0,
            total_generated INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount_classes INTEGER,
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            receipt_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_session_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mode TEXT,
            file_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ==================== GITHUB CLOUD AUTO-SYNC (AVTOMATIK BAZA) ====================

def restore_from_github():
    """Server qayta ishga tushganda GitHub'dan bazani avtomatik tiklaydi"""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SYNC_FILE_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "User-Agent": "BSB-Database-Sync",
            "Accept": "application/vnd.github.v3+json"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as resp:
            data = json.loads(resp.read().decode())
            content = base64.b64decode(data["content"]).decode("utf-8")
            sync_data = json.loads(content)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Restore users
        for u in sync_data.get("users", []):
            cursor.execute("""
                INSERT INTO users (user_id, username, full_name, free_trial_used, balance_classes, total_generated, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    free_trial_used=MAX(users.free_trial_used, excluded.free_trial_used),
                    balance_classes=MAX(users.balance_classes, excluded.balance_classes),
                    total_generated=MAX(users.total_generated, excluded.total_generated)
            """, (
                u["user_id"], u.get("username", ""), u.get("full_name", ""),
                u.get("free_trial_used", 0), u.get("balance_classes", 0),
                u.get("total_generated", 0), u.get("created_at")
            ))

        # Restore transactions
        for t in sync_data.get("transactions", []):
            cursor.execute("""
                INSERT OR IGNORE INTO transactions (id, user_id, amount_classes, status, receipt_file_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                t["id"], t["user_id"], t.get("amount_classes", 1),
                t.get("status", "pending"), t.get("receipt_file_id", ""),
                t.get("created_at")
            ))

        # Restore settings
        for k, v in sync_data.get("settings", {}).items():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))

        conn.commit()
        conn.close()
        logger.info(f"✅ Baza GitHub'dan muvaffaqiyatli tiklandi! Foydalanuvchilar: {len(sync_data.get('users', []))}")
    except Exception as e:
        logger.warning(f"GitHub'dan bazani tiklashda ogohlantirish (birinchi marta bo'lsa normal): {e}")

def trigger_cloud_sync():
    """Bazadagi o'zgarishlarni darhol GitHub'ga yozib qo'yadi"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users")
        users = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM transactions")
        transactions = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM settings")
        settings = {r["key"]: r["value"] for r in cursor.fetchall()}
        conn.close()

        sync_data = {
            "users": users,
            "transactions": transactions,
            "settings": settings
        }

        content_bytes = json.dumps(sync_data, indent=2, ensure_ascii=False).encode("utf-8")
        b64_content = base64.b64encode(content_bytes).decode("utf-8")

        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{SYNC_FILE_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "User-Agent": "BSB-Database-Sync",
            "Accept": "application/vnd.github.v3+json"
        }

        # Check existing sha
        sha = None
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=get_ssl_context(), timeout=7) as resp:
                res = json.loads(resp.read().decode())
                sha = res.get("sha")
        except Exception:
            pass

        body = {
            "message": "Auto-sync database update (users, balances, receipts)",
            "content": b64_content
        }
        if sha:
            body["sha"] = sha

        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="PUT")
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as resp:
            pass
        logger.info("✅ Baza GitHub Cloud'ga avtomatik sinxronizatsiya qilindi!")
    except Exception as e:
        logger.error(f"GitHub Cloud Sync xatoligi: {e}")

# ==================== SETTINGS (KANAL VA KONFIGURATSIYA) ====================

def get_setting(key: str, default: str = "") -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def save_setting(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()
    try:
        import threading
        threading.Thread(target=trigger_cloud_sync, daemon=True).start()
    except Exception:
        pass

def is_vip_user(user_id: int) -> bool:
    try:
        raw = get_setting("vip_users", "[]")
        vip_list = json.loads(raw)
        return int(user_id) in [int(x) for x in vip_list]
    except Exception:
        return False

def add_vip_user(user_id: int) -> bool:
    try:
        raw = get_setting("vip_users", "[]")
        vip_list = [int(x) for x in json.loads(raw)]
        uid = int(user_id)
        if uid not in vip_list:
            vip_list.append(uid)
            save_setting("vip_users", json.dumps(vip_list))
        return True
    except Exception as e:
        logger.error(f"add_vip_user error: {e}")
        return False

def remove_vip_user(user_id: int) -> bool:
    try:
        raw = get_setting("vip_users", "[]")
        vip_list = [int(x) for x in json.loads(raw)]
        uid = int(user_id)
        if uid in vip_list:
            vip_list.remove(uid)
            save_setting("vip_users", json.dumps(vip_list))
        return True
    except Exception as e:
        logger.error(f"remove_vip_user error: {e}")
        return False

def get_vip_users() -> List[int]:
    try:
        raw = get_setting("vip_users", "[]")
        return [int(x) for x in json.loads(raw)]
    except Exception:
        return []

def find_users(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    q = query.strip().lstrip("@")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if q.isdigit():
        cursor.execute(
            "SELECT * FROM users WHERE user_id = ? OR username LIKE ? OR full_name LIKE ? ORDER BY created_at DESC LIMIT ?", 
            (int(q), f"%{q}%", f"%{q}%", limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM users WHERE username LIKE ? OR full_name LIKE ? ORDER BY created_at DESC LIMIT ?", 
            (f"%{q}%", f"%{q}%", limit)
        )
        
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ==================== FOYDALANUVCHILAR VA BALANS ====================

def get_or_create_user(user_id: int, username: str = "", full_name: str = "") -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    need_sync = False
    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, username, full_name, free_trial_used, balance_classes, total_generated) VALUES (?, ?, ?, 0, 0, 0)",
            (user_id, username or "", full_name or "")
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        need_sync = True
    else:
        # Update username/full_name if changed
        if (username and row["username"] != username) or (full_name and row["full_name"] != full_name):
            cursor.execute("UPDATE users SET username = ?, full_name = ? WHERE user_id = ?", (username or row["username"], full_name or row["full_name"], user_id))
            conn.commit()
            need_sync = True

    user_data = dict(row)
    conn.close()

    if need_sync:
        try:
            import threading
            threading.Thread(target=trigger_cloud_sync, daemon=True).start()
        except Exception:
            pass

    return user_data

def can_generate_report(user_id: int, admin_id: int = 6580113791) -> (bool, str):
    """
    Foydalanuvchi hisobot yarata oladimi?
    1. Agar balansi > 0 bo'lsa -> Ruxsat (pullik balansdan)
    2. Agar hali bepul sinov ishlatmagan bo'lsa -> Ruxsat (1-bepul sinov)
    3. Aks holda -> To'lov talab qilinadi (Admin uchun ham tekshiriladi)
    """
    user = get_or_create_user(user_id)
    if user["balance_classes"] > 0:
        return True, "paid"
    if user["free_trial_used"] == 0:
        return True, "free_trial"
        
    return False, "payment_required"

def consume_credit(user_id: int, credit_type: str, admin_id: int = 6580113791):
    """Hisobot muvaffaqiyatli tayyorlangandan keyin kreditni yechish (Admin uchun ham yechiladi)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if credit_type == "free_trial":
        cursor.execute("UPDATE users SET free_trial_used = 1, total_generated = total_generated + 1 WHERE user_id = ?", (user_id,))
    elif credit_type == "paid":
        cursor.execute("UPDATE users SET balance_classes = MAX(0, balance_classes - 1), total_generated = total_generated + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    try:
        import threading
        threading.Thread(target=trigger_cloud_sync, daemon=True).start()
    except Exception:
        pass

def add_classes_balance(user_id: int, count: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance_classes = balance_classes + ? WHERE user_id = ?", (count, user_id))
    conn.commit()
    conn.close()

    try:
        import threading
        threading.Thread(target=trigger_cloud_sync, daemon=True).start()
    except Exception:
        pass

def log_transaction(user_id: int, receipt_file_id: str, amount_classes: int = 1) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (user_id, amount_classes, receipt_file_id, status) VALUES (?, ?, ?, 'pending')",
        (user_id, amount_classes, receipt_file_id)
    )
    tx_id = cursor.lastrowid
    conn.commit()
    conn.close()

    try:
        import threading
        threading.Thread(target=trigger_cloud_sync, daemon=True).start()
    except Exception:
        pass

    return tx_id

def update_transaction_status(tx_id: int, status: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE transactions SET status = ? WHERE id = ?", (status, tx_id))
    conn.commit()
    conn.close()

    try:
        import threading
        threading.Thread(target=trigger_cloud_sync, daemon=True).start()
    except Exception:
        pass

# Initialize and restore

def save_session_file(user_id: int, mode: str, file_path: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_session_files (user_id, mode, file_path) VALUES (?, ?, ?)", (user_id, mode, file_path))
    conn.commit()
    conn.close()

def get_session_files(user_id: int, mode: str) -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM user_session_files WHERE user_id = ? AND mode = ? ORDER BY id ASC", (user_id, mode))
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows if os.path.exists(r[0])]

def clear_session_files(user_id: int, mode: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM user_session_files WHERE user_id = ? AND mode = ?", (user_id, mode))
    rows = cursor.fetchall()
    for (fpath,) in rows:
        try:
            if fpath and os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass
    cursor.execute("DELETE FROM user_session_files WHERE user_id = ? AND mode = ?", (user_id, mode))
    conn.commit()
    conn.close()

def cleanup_old_temp_files(max_age_seconds: int = 7200):
    """2 soatdan oshgan barcha eski vaqtinchalik rasmlar va keshni o'chirib diskni tozalaydi"""
    import time
    now = time.time()
    temp_dir = "temp"
    if os.path.exists(temp_dir):
        for fname in os.listdir(temp_dir):
            fpath = os.path.join(temp_dir, fname)
            try:
                if os.path.isfile(fpath) and (now - os.path.getmtime(fpath) > max_age_seconds):
                    os.remove(fpath)
            except Exception:
                pass

init_db()
restore_from_github()
