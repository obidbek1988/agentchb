# db_service.py
"""
Foydalanuvchilar balansi, to'lovlar va 1 martalik bepul sinov tizimi uchun SQLite ma'lumotlar bazasi.
"""

import sqlite3
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = "bot_database.db"

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
    conn.commit()
    conn.close()

def get_or_create_user(user_id: int, username: str = "", full_name: str = "") -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, username, full_name, free_trial_used, balance_classes, total_generated) VALUES (?, ?, ?, 0, 0, 0)",
            (user_id, username or "", full_name or "")
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    else:
        # Update username if changed
        if username and row["username"] != username:
            cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            conn.commit()

    user_data = dict(row)
    conn.close()
    return user_data

def can_generate_report(user_id: int, admin_id: int = 6580113791) -> (bool, str):
    """
    Foydalanuvchi hisobot yarata oladimi?
    1. Agar Admin bo'lsa -> Cheksiz ruxsat
    2. Agar balansi > 0 bo'lsa -> Ruxsat (pullik balansdan)
    3. Agar hali bepul sinov ishlatmagan bo'lsa -> Ruxsat (1-bepul sinov)
    4. Aks holda -> To'lov talab qilinadi
    """
    if user_id == admin_id:
        return True, "admin"
        
    user = get_or_create_user(user_id)
    if user["balance_classes"] > 0:
        return True, "paid"
    if user["free_trial_used"] == 0:
        return True, "free_trial"
        
    return False, "payment_required"

def consume_credit(user_id: int, credit_type: str, admin_id: int = 6580113791):
    """Hisobot muvaffaqiyatli tayyorlangandan keyin kreditni yechish"""
    if user_id == admin_id:
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if credit_type == "free_trial":
        cursor.execute("UPDATE users SET free_trial_used = 1, total_generated = total_generated + 1 WHERE user_id = ?", (user_id,))
    elif credit_type == "paid":
        cursor.execute("UPDATE users SET balance_classes = MAX(0, balance_classes - 1), total_generated = total_generated + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_classes_balance(user_id: int, count: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance_classes = balance_classes + ? WHERE user_id = ?", (count, user_id))
    conn.commit()
    conn.close()

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
    return tx_id

def update_transaction_status(tx_id: int, status: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE transactions SET status = ? WHERE id = ?", (status, tx_id))
    conn.commit()
    conn.close()

# Auto init
init_db()
