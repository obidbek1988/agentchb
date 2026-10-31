import os
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    FSInputFile, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

from config import BOT_TOKEN, ARCHIVE_CHANNEL_ID
from ai_service import ai_service
from queue_manager import queue_manager
from excel_service import build_bsb_excel, build_chsb_excel
from criteria_store import get_criteria_for_grade, format_criteria_preview, get_chsb_for_grade, INFORMATIKA_1_CHORAK_CHSB
from emaktab_parser import parse_emaktab_file
from pdf_utils import pdf_to_images
import db_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# In-memory channel storage if updated dynamically
CURRENT_ARCHIVE_ID = db_service.get_setting("archive_channel_id", "") or ARCHIVE_CHANNEL_ID
ADMIN_ID = 6580113791
ADMIN_USERNAME = "Obidbek1988"
CARD_NUMBER = "5614681211002260"
CARD_HOLDER = "QOBILOV OBIDJON"
PRICE_PER_CLASS = 5000

FEEDBACK_NOTE = (
    "\n\n⚠️ _Eslatma: Tizim hozir test rejimida ishlamoqda. Tayyor bo‘lganda hisobotni bir tekshirib qo‘ying (imloviy xatolik bo‘lishi mumkin)._\n"
    "📩 _Xato va takliflar uchun admin Telegrami:_ @Obidbek1988"
)

def get_main_keyboard(user_id: int = 0, is_admin: bool = False):
    if user_id == ADMIN_ID or is_admin:
        role = "admin"
    elif user_id and db_service.is_vip_user(user_id):
        role = "vip"
    else:
        role = "user"

    if role == "admin":
        kb = [
            [
                KeyboardButton(text="1️⃣ BSB (Ballar orqali)"),
                KeyboardButton(text="2️⃣ CHSB (Ballar orqali)")
            ],
            [
                KeyboardButton(text="3️⃣ BSB (Ishlarni tekshirish)"),
                KeyboardButton(text="4️⃣ CHSB (Testlarni tekshirish)")
            ],
            [
                KeyboardButton(text="5️⃣ BSB (Bahoga moslash)"),
                KeyboardButton(text="6️⃣ CHSB (Bahoga moslash)")
            ],
            [
                KeyboardButton(text="💳 Balans to‘ldirish (Admin)"),
                KeyboardButton(text="👑 VIP Boshqaruvi (Admin)")
            ],
            [
                KeyboardButton(text="📊 Baza va Statistika (Admin)")
            ],
            [
                KeyboardButton(text="💰 Hisobim / To‘lov qilish"),
                KeyboardButton(text="ℹ️ Narxlar va Yordam")
            ]
        ]
    elif role == "vip":
        kb = [
            [
                KeyboardButton(text="1️⃣ BSB (Ballar orqali)"),
                KeyboardButton(text="2️⃣ CHSB (Ballar orqali)")
            ],
            [
                KeyboardButton(text="3️⃣ BSB (Ishlarni tekshirish)"),
                KeyboardButton(text="4️⃣ CHSB (Testlarni tekshirish)")
            ],
            [
                KeyboardButton(text="5️⃣ BSB (Bahoga moslash)"),
                KeyboardButton(text="6️⃣ CHSB (Bahoga moslash)")
            ],
            [
                KeyboardButton(text="💰 Hisobim / To‘lov qilish"),
                KeyboardButton(text="ℹ️ Narxlar va Yordam")
            ]
        ]
    else:
        # Oddiy mijoz (CHSB testlarini tekshirish va Bahoga moslash)
        kb = [
            [
                KeyboardButton(text="🎯 CHSB (Testlarni tekshirish)"),
                KeyboardButton(text="📊 CHSB (Bahoga moslash)")
            ],
            [
                KeyboardButton(text="💰 Hisobim / To‘lov qilish"),
                KeyboardButton(text="ℹ️ Narxlar va Yordam")
            ]
        ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

class BotStates(StatesGroup):
    m1_journal_fixed = State()
    m1_journal = State()
    m1_criteria = State()

    m2_criteria = State()
    m2_keys = State()
    m2_works = State()

    m3_journal = State()
    m3_criteria = State()

    m4_select_grade_or_custom = State()
    m4_criteria = State()
    m4_edit_criteria_input = State()
    m4_keys = State()
    m4_edit_keys_input = State()
    m4_student_tests = State()

    m5_criteria = State()
    m5_keys = State()
    m5_journal = State()
    m5_works = State()

    m6_select_grade_or_custom = State()
    m6_criteria = State()
    m6_edit_criteria_input = State()
    m6_keys = State()
    m6_edit_all_input = State()
    m6_journal = State()

    waiting_for_receipt = State()

    # Admin balans to'ldirish
    admin_topup_select_user = State()
    admin_topup_enter_amount = State()
    admin_vip_add = State()

# ==================== TO'LOV VA BALANS TIZIMI ====================
@dp.message(F.text.contains("Hisobim / To‘lov qilish"))
@dp.message(F.text.contains("Hisobim"))
@dp.message(Command("balance"))
async def show_balance_menu(message: types.Message):
    user = db_service.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    bal = user.get("balance_classes", 0)
    free_used = user.get("free_trial_used", 0)
    is_admin = (message.from_user.id == ADMIN_ID)

    free_status = "❌ Ishlatilgan" if free_used else "🎁 1 ta sinf bepul mavjud!"
    admin_header = "👑 **ADMINSTATUS:** (Siz bot adminisiz — cheksiz huquqqa egasiz)\n\n" if is_admin else ""

    status_text = (
        f"{admin_header}"
        f"👤 **Foydalanuvchi:** {message.from_user.full_name}\n"
        f"🆔 **ID:** `{message.from_user.id}`\n\n"
        f"🎁 **Sinov imkoniyati:** {free_status}\n"
        f"💰 **Mavjud hisobotlar balansi:** **{bal} ta sinf**\n"
        f"💵 **1 ta sinf hisoboti:** 5,000 so‘m\n"
        f"📦 **4 ta sinf (oylik paket):** 15,000 so‘m\n"
        f"📦 **10 ta sinf paketi:** 40,000 so‘m\n"
    )

    msg = (
        f"{status_text}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💳 **To‘lov uchun karta raqami:**\n"
        f"*(Raqam ustiga bosing — avtomatik nusxalanadi)*\n\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 {CARD_HOLDER}\n\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"📲 **Hisobni to‘ldirish tartibi:**\n"
        f"1. Yuqoridagi kartaga to‘lovni bajaring (masalan: 1 ta sinf uchun 5,000 so‘m, 4 ta sinf uchun 15,000 so‘m yoki 10 ta sinf uchun 40,000 so‘m);\n"
        f"2. To‘lov **chekining rasmini (skrinshotini)** pastdagi tugma orqali botga yuboring;\n"
        f"3. Admin 2-5 daqiqa ichida tekshirib tasdiqlaydi va balansingizga sinflar qo‘shiladi!"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 To‘lov chekini yuborish", callback_data="send_receipt_prompt")],
        [InlineKeyboardButton(text="💬 Adminga bog‘lanish", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])
    await message.answer(msg, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text.contains("Narxlar va Yordam"))
async def show_help_pricing(message: types.Message):
    msg = (
        "ℹ️ **BSB & CHSB Bot — Narxlar va Foydalanish:**\n\n"
        "🎁 **Bepul sinov:** Har bir o‘qituvchiga dastlabki **1 ta sinf hisoboti mutlaqo bepul** beriladi (A4 format va mezon taqsimotini sinab ko‘rishingiz uchun).\n\n"
        f"💵 **Xizmat narxi:**\n"
        f"• 1 ta to‘liq sinf BSB yoki CHSB hisoboti — **5,000 so‘m**\n"
        f"• 4 ta sinf (oylik paket) — **15,000 so‘m**\n"
        f"• 10 ta sinf paketi — **40,000 so‘m**\n\n"
        "💳 **To‘lov kartasi:** (ustiga bossangiz nusxalanadi)\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 {CARD_HOLDER}\n\n"
        f"📩 Savol va takliflar uchun admin: @{ADMIN_USERNAME}"
    )
    await message.answer(msg, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")

@dp.callback_query(F.data == "send_receipt_prompt")
async def handle_receipt_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.waiting_for_receipt)
    await callback.message.answer(
        "📸 **To‘lov cheki rasmini (skrinshotini) yuboring:**\n\n"
        "*(Iltimos, chekda sana, summa va karta raqami ko‘ringan bo‘lsin)*",
        reply_markup=get_action_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(BotStates.waiting_for_receipt, F.photo)
async def handle_receipt_photo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "mavjud_emas"
    full_name = message.from_user.full_name
    file_id = message.photo[-1].file_id

    tx_id = db_service.log_transaction(user_id, file_id, amount_classes=1)

    await message.answer(
        "✅ **To‘lov chekingiz adminga yetkazildi!**\n\n"
        "⏳ Admin to‘lovni tasdiqlashi bilan sizga xabar keladi va hisobingiz to‘ldiriladi. "
        "Odatda bu 2–5 daqiqa vaqt oladi.\n\n"
        "Rahmat!",
        reply_markup=get_main_keyboard(message.from_user.id),
        parse_mode="Markdown"
    )
    await state.clear()

    # Send receipt to ADMIN for 1-click approval
    admin_caption = (
        f"🔔 **Yangi to‘lov cheki keldi! (№{tx_id})**\n\n"
        f"👤 **O‘qituvchi:** {full_name}\n"
        f"🔗 **Username:** @{username}\n"
        f"🆔 **User ID:** `{user_id}`\n\n"
        f"Iltimos, hisobingizga pul tushganini tekshirib, quyidagi tugmalardan birini bosing:"
    )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ +1 sinf (5,000 so‘m)", callback_data=f"approve_{tx_id}_{user_id}_1"),
            InlineKeyboardButton(text="✅ +2 sinf (10,000 so‘m)", callback_data=f"approve_{tx_id}_{user_id}_2"),
        ],
        [
            InlineKeyboardButton(text="✅ +4 sinf (15,000 so‘m)", callback_data=f"approve_{tx_id}_{user_id}_4"),
            InlineKeyboardButton(text="✅ +10 sinf (40,000 so‘m)", callback_data=f"approve_{tx_id}_{user_id}_10"),
        ],
        [
            InlineKeyboardButton(text="❌ Rad etish (Soxta chek)", callback_data=f"reject_{tx_id}_{user_id}")
        ]
    ])

    try:
        await bot.send_photo(ADMIN_ID, photo=file_id, caption=admin_caption, reply_markup=admin_kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Adminga chek yuborishda xatolik: {e}")

@dp.callback_query(F.data.startswith("approve_"))
async def handle_admin_approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin tasdiqlay oladi!", show_alert=True)
        return

    parts = callback.data.split("_")
    tx_id = int(parts[1])
    target_user_id = int(parts[2])
    classes_count = int(parts[3])

    db_service.add_classes_balance(target_user_id, classes_count)
    db_service.update_transaction_status(tx_id, "approved")

    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n✅ **TASDIQLANDI:** +{classes_count} ta sinf balansi qo‘shildi!",
        parse_mode="Markdown"
    )
    await callback.answer(f"+{classes_count} sinf muvaffaqiyatli qo‘shildi!", show_alert=True)

    # Notify student / teacher
    try:
        await bot.send_message(
            target_user_id,
            f"🎉 **To‘lovingiz tasdiqlandi!**\n\n"
            f"Hisobingizga **+{classes_count} ta sinf hisoboti** muvaffaqiyatli qo‘shildi.\n"
            f"Endi botdan bemalol BSB va CHSB hisobotlarini tayyorlashingiz mumkin! 🎓",
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchiga tasdiq xabari yetmadi: {e}")

@dp.callback_query(F.data.startswith("reject_"))
async def handle_admin_reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin rad eta oladi!", show_alert=True)
        return

    parts = callback.data.split("_")
    tx_id = int(parts[1])
    target_user_id = int(parts[2])

    db_service.update_transaction_status(tx_id, "rejected")

    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n❌ **RAD ETILDI!** (Chek tasdiqlanmadi)",
        parse_mode="Markdown"
    )
    await callback.answer("Chek rad etildi!", show_alert=True)

    try:
        await bot.send_message(
            target_user_id,
            f"⚠️ **To‘lov chekingiz tasdiqlanmadi.**\n\n"
            f"Iltimos, to‘lov summasi to‘g‘riligini tekshiring yoki admin bilan bog‘laning: @{ADMIN_USERNAME}",
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchiga rad xabari yetmadi: {e}")

async def check_access_and_notify(message: types.Message) -> (bool, str):
    """Foydalanuvchi hisobot qila oladimi yoki to'lov kerakmi?"""
    can_proceed, credit_type = db_service.can_generate_report(message.from_user.id, admin_id=ADMIN_ID)
    if can_proceed:
        return True, credit_type

    # Payment required
    pay_msg = (
        "🔒 **Hisobingizda mablag‘ yetarli emas!**\n\n"
        "🎁 Siz 1 ta bepul sinov imkoniyatidan foydalangansiz.\n"
        f"Keyingi hisobotlarni tayyorlash uchun hisobingizni to‘ldiring:\n\n"
        f"💵 **1 ta sinf hisoboti:** {PRICE_PER_CLASS:,} so‘m\n"
        f"💳 **Karta raqami:** (nusxalash uchun ustiga bosing)\n\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 {CARD_HOLDER}\n\n"
        "To‘lovni amalga oshirib, **'💰 Hisobim / To‘lov qilish'** bo‘limi orqali chekni yuboring — hisobingiz darhol to‘ldiriladi!"
    )
    await message.answer(pay_msg, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
    return False, credit_type

    waiting_for_receipt = State()

def get_action_keyboard(show_finish: bool = False):
    kb = []
    if show_finish:
        kb.append([KeyboardButton(text="✅ Rasmlar tugadi, hisobotni tayyorlang!")])
    kb.append([KeyboardButton(text="❌ Bekor qilish")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_grade_selection_keyboard():
    inline_kb = [
        [
            InlineKeyboardButton(text="⚡ 6-sinf (30b)", callback_data="grade_6"),
            InlineKeyboardButton(text="⚡ 7-sinf (25b)", callback_data="grade_7"),
            InlineKeyboardButton(text="⚡ 8-sinf (25b)", callback_data="grade_8"),
        ],
        [
            InlineKeyboardButton(text="⚡ 9-sinf (50b)", callback_data="grade_9"),
            InlineKeyboardButton(text="⚡ 10-sinf (50b)", callback_data="grade_10"),
            InlineKeyboardButton(text="⚡ 11-sinf (50b)", callback_data="grade_11"),
        ],
        [
            InlineKeyboardButton(text="👁 Mezonlarni ko‘rish", callback_data="view_criteria_menu")
        ],
        [
            InlineKeyboardButton(text="📷 Boshqa fan (Yangi mezon rasmi)", callback_data="custom_criteria")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_criteria_preview_keyboard():
    inline_kb = [
        [
            InlineKeyboardButton(text="6-sinf", callback_data="preview_6"),
            InlineKeyboardButton(text="7-sinf", callback_data="preview_7"),
            InlineKeyboardButton(text="8-sinf", callback_data="preview_8"),
        ],
        [
            InlineKeyboardButton(text="9-sinf", callback_data="preview_9"),
            InlineKeyboardButton(text="10-sinf", callback_data="preview_10"),
            InlineKeyboardButton(text="11-sinf", callback_data="preview_11"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Tanlash menyusiga qaytish", callback_data="back_to_grades")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

# ==================== TO'LOV VA BALANS TIZIMI ====================
@dp.message(F.text.contains("Hisobim / To‘lov qilish"))
@dp.message(F.text.contains("Hisobim"))
@dp.message(Command("balance"))
async def show_balance_menu(message: types.Message):
    user = db_service.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    bal = user.get("balance_classes", 0)
    free_used = user.get("free_trial_used", 0)
    is_admin = (message.from_user.id == ADMIN_ID)

    free_status = "❌ Ishlatilgan" if free_used else "🎁 1 ta sinf bepul mavjud!"
    admin_header = "👑 **ADMINSTATUS:** (Siz bot adminisiz — cheksiz huquqqa egasiz)\n\n" if is_admin else ""

    status_text = (
        f"{admin_header}"
        f"👤 **Foydalanuvchi:** {message.from_user.full_name}\n"
        f"🆔 **ID:** `{message.from_user.id}`\n\n"
        f"🎁 **Sinov imkoniyati:** {free_status}\n"
        f"💰 **Mavjud hisobotlar balansi:** **{bal} ta sinf**\n"
        f"💵 **1 ta sinf hisoboti:** 5,000 so‘m\n"
        f"📦 **4 ta sinf (oylik paket):** 15,000 so‘m\n"
        f"📦 **10 ta sinf paketi:** 40,000 so‘m\n"
    )

    msg = (
        f"{status_text}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💳 **To‘lov uchun karta raqami:**\n"
        f"*(Raqam ustiga bosing — avtomatik nusxalanadi)*\n\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 {CARD_HOLDER}\n\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"📲 **Hisobni to‘ldirish tartibi:**\n"
        f"1. Yuqoridagi kartaga to‘lovni bajaring (masalan: 1 ta sinf uchun 5,000 so‘m, 4 ta sinf uchun 15,000 so‘m yoki 10 ta sinf uchun 40,000 so‘m);\n"
        f"2. To‘lov **chekining rasmini (skrinshotini)** pastdagi tugma orqali botga yuboring;\n"
        f"3. Admin 2-5 daqiqa ichida tekshirib tasdiqlaydi va balansingizga sinflar qo‘shiladi!"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 To‘lov chekini yuborish", callback_data="send_receipt_prompt")],
        [InlineKeyboardButton(text="💬 Adminga bog‘lanish", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])
    await message.answer(msg, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text.contains("Narxlar va Yordam"))
async def show_help_pricing(message: types.Message):
    msg = (
        "ℹ️ **BSB & CHSB Bot — Narxlar va Foydalanish:**\n\n"
        "🎁 **Bepul sinov:** Har bir o‘qituvchiga dastlabki **1 ta sinf hisoboti mutlaqo bepul** beriladi (A4 format va mezon taqsimotini sinab ko‘rishingiz uchun).\n\n"
        f"💵 **Xizmat narxi:**\n"
        f"• 1 ta to‘liq sinf BSB yoki CHSB hisoboti — **5,000 so‘m**\n"
        f"• 4 ta sinf (oylik paket) — **15,000 so‘m**\n"
        f"• 10 ta sinf paketi — **40,000 so‘m**\n\n"
        "💳 **To‘lov kartasi:** (ustiga bossangiz nusxalanadi)\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 {CARD_HOLDER}\n\n"
        f"📩 Savol va takliflar uchun admin: @{ADMIN_USERNAME}"
    )
    await message.answer(msg, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")

@dp.callback_query(F.data == "send_receipt_prompt")
async def handle_receipt_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.waiting_for_receipt)
    await callback.message.answer(
        "📸 **To‘lov cheki rasmini (skrinshotini) yuboring:**\n\n"
        "*(Iltimos, chekda sana, summa va karta raqami ko‘ringan bo‘lsin)*",
        reply_markup=get_action_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(BotStates.waiting_for_receipt, F.photo)
async def handle_receipt_photo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "mavjud_emas"
    full_name = message.from_user.full_name
    file_id = message.photo[-1].file_id

    tx_id = db_service.log_transaction(user_id, file_id, amount_classes=1)

    await message.answer(
        "✅ **To‘lov chekingiz adminga yetkazildi!**\n\n"
        "⏳ Admin to‘lovni tasdiqlashi bilan sizga xabar keladi va hisobingiz to‘ldiriladi. "
        "Odatda bu 2–5 daqiqa vaqt oladi.\n\n"
        "Rahmat!",
        reply_markup=get_main_keyboard(message.from_user.id),
        parse_mode="Markdown"
    )
    await state.clear()

    # Send receipt to ADMIN for 1-click approval
    admin_caption = (
        f"🔔 **Yangi to‘lov cheki keldi! (№{tx_id})**\n\n"
        f"👤 **O‘qituvchi:** {full_name}\n"
        f"🔗 **Username:** @{username}\n"
        f"🆔 **User ID:** `{user_id}`\n\n"
        f"Iltimos, hisobingizga pul tushganini tekshirib, quyidagi tugmalardan birini bosing:"
    )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ +1 sinf (5,000 so‘m)", callback_data=f"approve_{tx_id}_{user_id}_1"),
            InlineKeyboardButton(text="✅ +2 sinf (10,000 so‘m)", callback_data=f"approve_{tx_id}_{user_id}_2"),
        ],
        [
            InlineKeyboardButton(text="✅ +4 sinf (15,000 so‘m)", callback_data=f"approve_{tx_id}_{user_id}_4"),
            InlineKeyboardButton(text="✅ +10 sinf (40,000 so‘m)", callback_data=f"approve_{tx_id}_{user_id}_10"),
        ],
        [
            InlineKeyboardButton(text="❌ Rad etish (Soxta chek)", callback_data=f"reject_{tx_id}_{user_id}")
        ]
    ])

    try:
        await bot.send_photo(ADMIN_ID, photo=file_id, caption=admin_caption, reply_markup=admin_kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Adminga chek yuborishda xatolik: {e}")

@dp.callback_query(F.data.startswith("approve_"))
async def handle_admin_approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin tasdiqlay oladi!", show_alert=True)
        return

    parts = callback.data.split("_")
    tx_id = int(parts[1])
    target_user_id = int(parts[2])
    classes_count = int(parts[3])

    db_service.add_classes_balance(target_user_id, classes_count)
    db_service.update_transaction_status(tx_id, "approved")

    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n✅ **TASDIQLANDI:** +{classes_count} ta sinf balansi qo‘shildi!",
        parse_mode="Markdown"
    )
    await callback.answer(f"+{classes_count} sinf muvaffaqiyatli qo‘shildi!", show_alert=True)

    # Notify student / teacher
    try:
        await bot.send_message(
            target_user_id,
            f"🎉 **To‘lovingiz tasdiqlandi!**\n\n"
            f"Hisobingizga **+{classes_count} ta sinf hisoboti** muvaffaqiyatli qo‘shildi.\n"
            f"Endi botdan bemalol BSB va CHSB hisobotlarini tayyorlashingiz mumkin! 🎓",
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchiga tasdiq xabari yetmadi: {e}")

@dp.callback_query(F.data.startswith("reject_"))
async def handle_admin_reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin rad eta oladi!", show_alert=True)
        return

    parts = callback.data.split("_")
    tx_id = int(parts[1])
    target_user_id = int(parts[2])

    db_service.update_transaction_status(tx_id, "rejected")

    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n❌ **RAD ETILDI!** (Chek tasdiqlanmadi)",
        parse_mode="Markdown"
    )
    await callback.answer("Chek rad etildi!", show_alert=True)

    try:
        await bot.send_message(
            target_user_id,
            f"⚠️ **To‘lov chekingiz tasdiqlanmadi.**\n\n"
            f"Iltimos, to‘lov summasi to‘g‘riligini tekshiring yoki admin bilan bog‘laning: @{ADMIN_USERNAME}",
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchiga rad xabari yetmadi: {e}")

async def check_access_and_notify(message: types.Message) -> (bool, str):
    """Foydalanuvchi hisobot qila oladimi yoki to'lov kerakmi?"""
    can_proceed, credit_type = db_service.can_generate_report(message.from_user.id, admin_id=ADMIN_ID)
    if can_proceed:
        return True, credit_type

    # Payment required
    pay_msg = (
        "🔒 **Hisobingizda mablag‘ yetarli emas!**\n\n"
        "🎁 Siz 1 ta bepul sinov imkoniyatidan foydalangansiz.\n"
        f"Keyingi hisobotlarni tayyorlash uchun hisobingizni to‘ldiring:\n\n"
        f"💵 **1 ta sinf hisoboti:** {PRICE_PER_CLASS:,} so‘m\n"
        f"💳 **Karta raqami:** (nusxalash uchun ustiga bosing)\n\n"
        f"`{CARD_NUMBER}`\n"
        f"👤 {CARD_HOLDER}\n\n"
        "To‘lovni amalga oshirib, **'💰 Hisobim / To‘lov qilish'** bo‘limi orqali chekni yuboring — hisobingiz darhol to‘ldiriladi!"
    )
    await message.answer(pay_msg, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
    return False, credit_type

# Catch channel posts to auto-detect archive channel ID
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    global CURRENT_ARCHIVE_ID
    CURRENT_ARCHIVE_ID = str(message.chat.id)
    db_service.save_setting("archive_channel_id", CURRENT_ARCHIVE_ID)
    logger.info(f"Avtomatik arxiv kanal ID aniqlandi va saqlandi: {CURRENT_ARCHIVE_ID}")

@dp.my_chat_member()
async def handle_my_chat_member(event: types.ChatMemberUpdated):
    global CURRENT_ARCHIVE_ID
    if event.chat.type in ["channel", "supergroup"]:
        CURRENT_ARCHIVE_ID = str(event.chat.id)
        db_service.save_setting("archive_channel_id", CURRENT_ARCHIVE_ID)
        logger.info(f"Bot kanal/guruhga a'zo qilindi va saqlandi: {CURRENT_ARCHIVE_ID}")

@dp.message(F.forward_origin)
async def handle_forward_origin(message: types.Message):
    global CURRENT_ARCHIVE_ID
    origin = message.forward_origin
    if getattr(origin, "type", "") == "channel" and getattr(origin, "chat", None):
        CURRENT_ARCHIVE_ID = str(origin.chat.id)
        db_service.save_setting("archive_channel_id", CURRENT_ARCHIVE_ID)
        logger.info(f"Forward origin orqali kanal ID aniqlandi: {CURRENT_ARCHIVE_ID}")
        await message.answer(
            f"✅ **Kanal muvaffaqiyatli ulandi va saqlandi!**\n\n"
            f"📢 Kanal: **{origin.chat.title or 'Nomsiz'}**\n"
            f"🆔 ID: `{CURRENT_ARCHIVE_ID}`\n\n"
            f"Endi bot yaratgan barcha Excel hisobotlar to‘g‘ridan-to‘g‘ri shu kanalingizga ham avtomatik tashlanadi!",
            parse_mode="Markdown"
        )

@dp.message(F.forward_from_chat)
async def handle_forward(message: types.Message):
    global CURRENT_ARCHIVE_ID
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        CURRENT_ARCHIVE_ID = str(message.forward_from_chat.id)
        db_service.save_setting("archive_channel_id", CURRENT_ARCHIVE_ID)
        logger.info(f"Forward orqali kanal ID aniqlandi: {CURRENT_ARCHIVE_ID}")
        await message.answer(
            f"✅ **Kanal muvaffaqiyatli ulandi va saqlandi!**\n\n"
            f"📢 Kanal: **{message.forward_from_chat.title or 'Nomsiz'}**\n"
            f"🆔 ID: `{CURRENT_ARCHIVE_ID}`\n\n"
            f"Endi bot yaratgan barcha Excel hisobotlar to‘g‘ridan-to‘g‘ri shu kanalingizga ham avtomatik tashlanadi!",
            parse_mode="Markdown"
        )

@dp.message(Command("setchannel"))
@dp.message(Command("kanal"))
async def cmd_set_channel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) > 1:
        cid = parts[1].strip()
        global CURRENT_ARCHIVE_ID
        CURRENT_ARCHIVE_ID = cid
        db_service.save_setting("archive_channel_id", cid)
        await message.answer(f"✅ **Kanal ID saqlandi:** `{cid}`\n\nEndi barcha hisobotlar shu kanalga yuboriladi.", parse_mode="Markdown")
    else:
        curr = CURRENT_ARCHIVE_ID or db_service.get_setting("archive_channel_id", "") or "Ulanmagan"
        await message.answer(
            f"📢 **Hozirgi arxiv kanal ID:** `{curr}`\n\n"
            f"O‘zgartirish uchun: `/setchannel -100xxxxxxxxxx` deb yozing.",
            parse_mode="Markdown"
        )

@dp.message(Command("start", ignore_case=True))
@dp.message(CommandStart())
@dp.message(F.text.lower().in_(["/start", "start", "❌ bekor qilish", "bekor qilish"]))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    is_admin = (uid == ADMIN_ID)
    is_vip = db_service.is_vip_user(uid)

    if is_admin or is_vip:
        welcome_text = (
            "Assalomu alaykum! 🎓 **BSB va CHSB Hisobot Agentiga** xush kelibsiz.\n\n"
            "Quyidagi imkoniyatlardan birini tanlang:\n\n"
            "⬅️ **BSB bo‘limi (Chap tomonda):**\n"
            "1️⃣ **BSB (Ballar orqali):** eMaktab jurnali va mezon rasmidan hisobot qilish.\n"
            "3️⃣ **BSB (Ishlarni tekshirish):** O‘quvchilar yozma ishlarini AI orqali tekshirish.\n"
            "5️⃣ **BSB (Bahoga moslash):** Darsdagi o‘rtacha bahosiga moslab BSB ball qo‘yish.\n\n"
            "➡️ **CHSB bo‘limi (O‘ng tomonda):**\n"
            "2️⃣ **CHSB (Ballar orqali):** eMaktab CHSB jurnali bo‘yicha hisobot qilish.\n"
            "4️⃣ **CHSB (Testlarni tekshirish):** Test to‘g‘ri kaliti va varaqalarini tekshirish.\n"
            "6️⃣ **CHSB (Bahoga moslash):** Darsdagi o‘rtacha bahosiga moslab CHSB ball qo‘yish."
        )
    else:
        welcome_text = (
            "Assalomu alaykum! 🎓 **CHSB Hisobot va Test Tahlili Agentiga** xush kelibsiz.\n\n"
            "Quyidagi qulay imkoniyatlardan birini tanlang:\n\n"
            "🎯 **CHSB (Testlarni tekshirish):** Test to‘g‘ri kaliti va o‘quvchilar javob varaqalarini rasmga olib tekshirish;\n"
            "📊 **CHSB (Bahoga moslash):** O‘quvchi ishlarisiz — faqat eMaktab jurnali orqali darsdagi baholarga moslab tezkor hisobot chiqarish."
        )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(user_id=uid, is_admin=is_admin), parse_mode="Markdown")

async def send_to_archive(doc_path: str, caption: str):
    global CURRENT_ARCHIVE_ID
    if not CURRENT_ARCHIVE_ID:
        CURRENT_ARCHIVE_ID = db_service.get_setting("archive_channel_id", "") or ARCHIVE_CHANNEL_ID
    if CURRENT_ARCHIVE_ID:
        try:
            doc = FSInputFile(doc_path)
            await bot.send_document(CURRENT_ARCHIVE_ID, doc, caption=caption)
            return
        except Exception as e:
            logger.warning(f"Arxiv kanalga jo'natilmadi ({CURRENT_ARCHIVE_ID}): {e}")
    # Backup failsafe to Admin ID
    try:
        doc_adm = FSInputFile(doc_path)
        await bot.send_document(ADMIN_ID, doc_adm, caption=f"📁 **Arxiv nusxasi (Admin):**\n{caption}")
    except Exception as e2:
        logger.warning(f"Adminga arxiv nusxa jo'natilmadi: {e2}")

# ==================== 1-REJIM: BSB BALLAR ORQALI ====================
@dp.message(F.text.contains("1️⃣ BSB (Ballar orqali)"))
@dp.message(F.text.contains("BSB (Ballar orqali)"))
async def mode1_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid != ADMIN_ID and not db_service.is_vip_user(uid):
        await message.answer(
            "🔒 **BSB xizmatlari faqat ruxsat berilgan foydalanuvchilar uchun!**\n\n"
            "Ushbu bo‘limdan foydalanish uchun adminga murojaat qiling: @Obidbek1988",
            reply_markup=get_main_keyboard(uid)
        )
        return
    can_proceed, credit_type = await check_access_and_notify(message)
    if not can_proceed:
        return

    await state.clear()
    await state.update_data(credit_type=credit_type)
    msg = (
        "📝 **1-REJIM: BSB (Ballar orqali hisobot)**\n\n"
        "O‘zbek sinflar Informatika 1-BSB rasmiy mezonlari **bazada tayyor saqlangan!**\n\n"
        "💡 Sinfni tanlasangiz, mezon rasmini qayta-qayta yuklash shart emas — **faqat elektron jurnal skrinshotini yoki Excel faylini** yuborsangiz kifoya!\n\n"
        "Quyidagilardan birini tanlang yoki mezonni ko‘ring:"
    )
    await message.answer(msg, reply_markup=get_grade_selection_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("grade_"))
async def handle_grade_selection(callback: CallbackQuery, state: FSMContext):
    grade = callback.data.split("_")[1]
    crit_info = get_criteria_for_grade(grade)
    await state.update_data(fixed_criteria=crit_info, selected_grade=grade)
    await state.set_state(BotStates.m1_journal_fixed)
    await callback.message.answer(
        f"✅ **{grade}-sinf Informatika 1-BSB ({crit_info['max_score']} ball)** tanlandi!\n\n"
        f"💡 **Eng yaxshi va xatosiz usul:** eMaktabdan yuklangan **Excel (.xlsx yoki .xls) faylini** yuboring!\n"
        f"• Excel fayl yuborilsa (hatto kirillcha bo‘lsa ham), **lotin alifbosida 0% imloviy xatosiz va 1 soniyada** mukammal tayyor bo‘ladi!\n\n"
        f"📸 Agar Excel fayl bo‘lmasa, jurnalning **tiniq skrinshotini** yuboring (skrinshot xira bo‘lsa, ismlarda imloviy xatolik bo‘lishi mumkin).\n\n"
        f"*(Mezon rasmi shart emas, bazadan avtomat olinadi!)*",
        reply_markup=get_action_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "view_criteria_menu")
@dp.callback_query(F.data == "back_to_grades")
async def handle_criteria_menu(callback: CallbackQuery):
    if callback.data == "back_to_grades":
        await callback.message.edit_text(
            "📝 **1-REJIM: BSB (Ballar orqali hisobot)**\n\nQaysi sinf hisobotini tayyorlaymiz?",
            reply_markup=get_grade_selection_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            "👁 **Qaysi sinfning 1-BSB baholash mezonini ko‘rmoqchisiz?**",
            reply_markup=get_criteria_preview_keyboard(),
            parse_mode="Markdown"
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("preview_"))
async def handle_preview_grade(callback: CallbackQuery):
    grade = callback.data.split("_")[1]
    preview_text = format_criteria_preview(grade)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Shu {grade}-sinf bilan hisobot tuzish", callback_data=f"grade_{grade}")],
        [InlineKeyboardButton(text="⬅️ Boshqa sinflar mezonini ko‘rish", callback_data="view_criteria_menu")]
    ])
    await callback.message.edit_text(preview_text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "custom_criteria")
async def handle_custom_criteria(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.m1_journal)
    await callback.message.answer(
        "📷 **Boshqa fan / Yangi mezon bilan hisobot tuzish**\n\n"
        "1-qadam: eMaktab elektron jurnali **Excel (.xlsx/.xls) faylini** yoki **tiniq skrinshotini** yuboring:\n"
        "*(Excel fayl bo‘lsa 100% xatosiz va tez tayyor bo‘ladi!)*",
        reply_markup=get_action_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

# ==================== 1-REJIM: TAYYOR MEZON BILAN ISHLASH ====================
@dp.message(BotStates.m1_journal_fixed, F.document)
async def mode1_fixed_document(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    
    # PDF fayl bo'lsa
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m1_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            status_pdf = await message.answer("📄 PDF qabul qilindi, sahifalari o‘qilmoqda...")
            images = pdf_to_images(pdf_path)
            data = await state.get_data()
            j_list = data.get("journal_paths", [])
            j_list.extend(images)
            await state.update_data(journal_paths=j_list)
            await status_pdf.delete()
            await message.answer(
                f"📥 **PDF dan {len(images)} ta sahifa muvaffaqiyatli olindi!**\n\n"
                f"• Yana rasm/PDF bo‘lsa yuboring;\n"
                f"• Tugagan bo‘lsa, **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
                reply_markup=get_action_keyboard(show_finish=True)
            )
        except Exception as e:
            logger.error(f"PDF convert error: {e}")
            await message.answer("❌ PDF faylni o‘qishda xatolik yuz berdi. Iltimos, rasm yoki Excel yuboring.")
        return

    if not (fname.endswith(".xlsx") or fname.endswith(".xls")):
        await message.answer("Iltimos, eMaktab elektron jurnalini Excel (.xlsx, .xls) yoki PDF formatda yuboring.")
        return

    data = await state.get_data()
    crit_info = data.get("fixed_criteria")
    grade = data.get("selected_grade", "")

    status_msg = await message.answer(f"⏳ {grade}-sinf elektron jurnali ({fname}) to‘g‘ridan-to‘g‘ri o‘qilmoqda...")
    os.makedirs("temp", exist_ok=True)
    ext = ".xls" if fname.endswith(".xls") else ".xlsx"
    fpath = f"temp/m1_doc_{message.from_user.id}_{message.message_id}{ext}"
    await bot.download(message.document, destination=fpath)

    try:
        parsed = parse_emaktab_file(fpath, criteria=crit_info["criteria"], target_mode="BSB")
        cname = parsed.get("school_info", {}).get("class_name") or f"{grade}-sinf"
        out_excel = f"temp/{message.from_user.id}_{cname}_bsb.xlsx"
        build_bsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_1-BSB_hisobot.xlsx")
        cap = (
            f"🎉 **{cname} sinf 1-BSB hisoboti tayyor!**\n"
            f"• Manba: eMaktab elektron jurnali ({ext})\n"
            f"• O‘quvchilar soni: {len(parsed['students'])} nafar\n"
            f"• A4 Portret format\n"
            f"• Ballar rasmiy mezon bo‘yicha taqsimlangan"
            f"{FEEDBACK_NOTE}"
        )
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Yangi BSB ({grade}-sinf Excel): {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
    except Exception as e:
        logger.error(f"Excel Direct Parse Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Faylni o‘qishda xatolik: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")
    finally:
        await state.clear()

@dp.message(BotStates.m1_journal_fixed, F.photo)
async def mode1_fixed_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    jpath = f"temp/m1_j_fixed_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=jpath)

    data = await state.get_data()
    j_list = data.get("journal_paths", [])
    j_list.append(jpath)
    await state.update_data(journal_paths=j_list)

    count = len(j_list)
    await message.answer(
        f"📥 **{count}-jurnal rasmi qabul qilindi.**\n\n"
        f"• Agar jurnal davomi bo‘lsa, keyingi rasmni yuboring.\n"
        f"• Rasmlar tugagan bo‘lsa, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
        reply_markup=get_action_keyboard(show_finish=True)
    )

@dp.message(BotStates.m1_journal_fixed, F.text == "✅ Rasmlar tugadi, hisobotni tayyorlang!")
async def mode1_fixed_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    j_list = data.get("journal_paths", [])
    crit_info = data.get("fixed_criteria")
    grade = data.get("selected_grade", "")

    if not j_list:
        await message.answer("Iltimos, avval elektron jurnal rasmini yuboring.")
        return

    pos, eta = queue_manager.get_queue_info()
    queue_msg = f"⏳ Navbatdagi o‘rningiz: №{pos} (kutilmoqda: ~{eta}s)..." if pos > 1 else f"⏳ {grade}-sinf BSB hisoboti tayyorlanmoqda ({len(j_list)} ta rasm birlashtirilmoqda)..."
    status_msg = await message.answer(queue_msg)

    try:
        parsed = await ai_service.parse_bsb_with_fixed_criteria(j_list, crit_info)
        cname = parsed.get("school_info", {}).get("class_name", f"{grade}-sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_bsb.xlsx"
        build_bsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_1-BSB_hisobot.xlsx")
        cap = (
            f"🎉 **{cname} sinf 1-BSB hisoboti tayyor!**\n"
            f"• Manba: {len(j_list)} ta skrinshot birlashtirildi\n"
            f"• A4 Portret format\n"
            f"• Ballar rasmiy mezon bo‘yicha taqsimlangan"
            f"{FEEDBACK_NOTE}"
        )
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Yangi BSB ({grade}-sinf): {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
    except Exception as e:
        logger.error(f"Fixed Criteria BSB Error: {e}", exc_info=True)
        err_msg = (
            f"⚠️ **Rasm xira bo‘lgani yoki tahlil qilishda qiyinchilik bo‘lgani sababli xatolik yuz berdi!**\n\n"
            f"💡 **Tavsiya:** eMaktabdan elektron jurnalni **Excel (.xlsx yoki .xls)** formatida yuklab olib botga yuboring — unda kirillcha bo‘lsa ham 100% xatosiz va darhol tayyor bo‘ladi!\n\n"
            f"📸 Yoki jurnalning tiniqroq skrinshotini qaytadan yuborib ko‘ring.\n\n"
            f"📩 Xato va takliflar uchun admin: @{ADMIN_USERNAME}"
        )
        await status_msg.edit_text(err_msg, parse_mode="Markdown")
    finally:
        await state.clear()

# ==================== 1-REJIM: BOSHQACHA/YANGI MEZON BILAN ISHLASH ====================
@dp.message(BotStates.m1_journal, F.document)
async def mode1_journal_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m1_custom_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            status_pdf = await message.answer("📄 PDF qabul qilindi, sahifalari o‘qilmoqda...")
            images = pdf_to_images(pdf_path)
            data = await state.get_data()
            j_list = data.get("journal_paths", [])
            j_list.extend(images)
            await state.update_data(journal_paths=j_list)
            await status_pdf.delete()
            await message.answer(
                f"📥 **PDF dan {len(images)} ta sahifa muvaffaqiyatli olindi!**\n\n"
                f"• Yana jurnal rasmi/PDF bo‘lsa yuboring;\n"
                f"• Jurnal tugagan bo‘lsa, pastdagi **'✅ Jurnal tugadi, mezonga o‘tish'** tugmasini bosing:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="✅ Jurnal tugadi, mezonga o‘tish")], [KeyboardButton(text="❌ Bekor qilish")]],
                    resize_keyboard=True
                )
            )
        except Exception as e:
            logger.error(f"Mode 1 Custom PDF error: {e}")
            await message.answer("❌ PDF faylni o‘qishda xatolik yuz berdi. Iltimos, rasm yoki Excel yuboring.")
    elif fname.endswith(".xlsx") or fname.endswith(".xls"):
        # Excel direct in custom mode
        os.makedirs("temp", exist_ok=True)
        ext = ".xls" if fname.endswith(".xls") else ".xlsx"
        fpath = f"temp/m1_custom_doc_{message.from_user.id}_{message.message_id}{ext}"
        await bot.download(message.document, destination=fpath)
        await state.update_data(excel_journal_path=fpath)
        await state.set_state(BotStates.m1_criteria)
        await message.answer(
            f"✅ **eMaktab elektron jurnali ({fname}) qabul qilindi!**\n\n"
            "2-qadam: Endi ushbu fan BSB ning **Baholash mezoni rasmini yoki PDF faylini** yuboring:",
            reply_markup=get_action_keyboard(show_finish=True)
        )
    else:
        await message.answer("Iltimos, elektron jurnalni Excel (.xlsx/.xls), PDF yoki rasm ko‘rinishida yuboring.")

@dp.message(BotStates.m1_journal, F.photo)
async def mode1_journal(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    fpath = f"temp/m1_j_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=fpath)

    data = await state.get_data()
    j_list = data.get("journal_paths", [])
    j_list.append(fpath)
    await state.update_data(journal_paths=j_list)

    await message.answer(
        f"📥 **{len(j_list)}-jurnal rasmi qabul qilindi.**\n\n"
        f"• Agar jurnal davomi bo‘lsa, keyingi sahifa rasmini yuboring.\n"
        f"• Jurnal rasmlari tugagan bo‘lsa, pastdagi **'✅ Jurnal tugadi, mezonga o‘tish'** tugmasini bosing:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✅ Jurnal tugadi, mezonga o‘tish")], [KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True
        )
    )

@dp.message(BotStates.m1_journal, F.text == "✅ Jurnal tugadi, mezonga o‘tish")
async def mode1_journal_done(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("journal_paths"):
        await message.answer("Iltimos, avval jurnal rasmini yuboring.")
        return
    await state.set_state(BotStates.m1_criteria)
    await message.answer(
        "✅ Jurnal rasmlari qabul qilindi!\n\n"
        "2-qadam: Endi ushbu BSB ning **Baholash mezoni rasmlarini** yuboring (1 yoki 2 sahifa bo‘lsa ham ketma-ket yuboring):",
        reply_markup=get_action_keyboard(show_finish=True)
    )

@dp.message(BotStates.m1_criteria, F.document)
async def mode1_criteria_document(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m1_c_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            status_pdf = await message.answer("📄 Mezon PDF qabul qilindi, sahifalari o‘qilmoqda...")
            images = pdf_to_images(pdf_path)
            data = await state.get_data()
            c_list = data.get("criteria_paths", [])
            c_list.extend(images)
            await state.update_data(criteria_paths=c_list)
            await status_pdf.delete()
            await message.answer(
                f"📥 **Mezon PDF dan {len(images)} ta sahifa muvaffaqiyatli olindi!**\n\n"
                f"• Yana rasm/PDF bo‘lsa yuboring;\n"
                f"• Tugagan bo‘lsa, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
                reply_markup=get_action_keyboard(show_finish=True)
            )
        except Exception as e:
            logger.error(f"Mode 1 Criteria PDF error: {e}")
            await message.answer("❌ PDF mezonni o‘qishda xatolik yuz berdi. Iltimos, rasm ko‘rinishida yuboring.")
    else:
        await message.answer("Iltimos, baholash mezonini rasm yoki PDF formatida yuboring.")

@dp.message(BotStates.m1_criteria, F.photo)
async def mode1_criteria_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    cpath = f"temp/m1_c_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=cpath)

    data = await state.get_data()
    c_list = data.get("criteria_paths", [])
    c_list.append(cpath)
    await state.update_data(criteria_paths=c_list)

    await message.answer(
        f"📥 **{len(c_list)}-mezon rasmi qabul qilindi.**\n\n"
        f"• Yana mezon rasmi bo‘lsa, yuboring.\n"
        f"• Rasmlar tugagan bo‘lsa, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
        reply_markup=get_action_keyboard(show_finish=True)
    )

@dp.message(BotStates.m1_criteria, F.text == "✅ Rasmlar tugadi, hisobotni tayyorlang!")
async def mode1_criteria_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    j_list = data.get("journal_paths", [])
    c_list = data.get("criteria_paths", [])

    if not c_list:
        await message.answer("Iltimos, avval baholash mezoni rasmini yuboring.")
        return

    pos, eta = queue_manager.get_queue_info()
    queue_msg = f"⏳ Navbatdagi o‘rningiz: №{pos} (kutilmoqda: ~{eta}s)..." if pos > 1 else f"⏳ BSB tahlil qilinmoqda ({len(j_list)} ta jurnal, {len(c_list)} ta mezon rasmi birlashtirilmoqda)..."
    status_msg = await message.answer(queue_msg)

    try:
        parsed = await ai_service.parse_bsb_data(j_list, c_list)
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_bsb.xlsx"
        build_bsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_1-BSB_hisobot.xlsx")
        cap = (
            f"🎉 **{cname} sinf 1-BSB hisoboti tayyor!**\n"
            f"• {len(j_list)} ta jurnal + {len(c_list)} ta mezon sahifalari birlashtirildi\n"
            f"• A4 Portret format\n"
            f"• Ballar mezonlar bo‘yicha taqsimlangan"
            f"{FEEDBACK_NOTE}"
        )
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Yangi BSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
    except Exception as e:
        logger.error(f"Mode 1 Error: {e}", exc_info=True)
        err_msg = (
            f"⚠️ **Rasm xira bo‘lgani yoki tahlil qilishda qiyinchilik bo‘lgani sababli xatolik yuz berdi!**\n\n"
            f"💡 **Tavsiya:** eMaktabdan elektron jurnalni **Excel (.xlsx yoki .xls)** formatida yuklab olib botga yuboring — unda kirillcha bo‘lsa ham 100% xatosiz va tez tayyor bo‘ladi!\n\n"
            f"📸 Yoki jurnal va mezonning tiniqroq skrinshotlarini qaytadan yuborib ko‘ring.\n\n"
            f"📩 Xato va takliflar uchun admin: @{ADMIN_USERNAME}"
        )
        await status_msg.edit_text(err_msg, parse_mode="Markdown")
    finally:
        await state.clear()

# ==================== 2-REJIM: BSB ISHLARNI TEKSHIRISH ====================
@dp.message(F.text.contains("3️⃣ BSB (Ishlarni tekshirish)"))
@dp.message(F.text.contains("2️⃣ BSB (Ishlarni tekshirish)"))
@dp.message(F.text.contains("BSB (Ishlarni tekshirish)"))
async def mode2_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid != ADMIN_ID and not db_service.is_vip_user(uid):
        await message.answer(
            "🔒 **BSB xizmatlari faqat ruxsat berilgan foydalanuvchilar uchun!**\n\n"
            "Ushbu bo‘limdan foydalanish uchun adminga murojaat qiling: @Obidbek1988",
            reply_markup=get_main_keyboard(uid)
        )
        return
    can_proceed, credit_type = await check_access_and_notify(message)
    if not can_proceed:
        return

    await state.clear()
    await state.update_data(credit_type=credit_type, works_paths=[])
    await state.set_state(BotStates.m2_criteria)

    msg_text = (
        "✍️ **2-REJIM: BSB o‘quvchilar yozma ishini tekshirish**\n\n"
        "📍 **1-QADAM (3 tadan): BSB Baholash mezonini yuboring**\n"
        "*(Rasm yoki PDF formatida)*\n\n"
        "📋 **MEZON UCHUN NAMUNA (Qanday bo‘lishi kerak?):**\n"
        "Mezonda BSB topshiriqlari va har biriga qo‘yiladigan ballar ko‘rsatiladi:\n"
        "• 1-topshiriq (Nazariy/qisqa savol): **5 ball**\n"
        "• 2-topshiriq (Amaliy mashq): **10 ball**\n"
        "• 3-topshiriq (Masala yechish): **10 ball**\n"
        "• 4-topshiriq (Loyiha / ijodiy ish): **15 ball**\n"
        "*(Jami: 25, 40 yoki 50 ball)*\n\n"
        "📸 _Iltimos, BSB baholash mezoni jadvali fotosuratini yoki PDF faylini yuboring:_"
    )
    await message.answer(msg_text, reply_markup=get_action_keyboard(), parse_mode="Markdown")

@dp.message(BotStates.m2_criteria, F.document)
async def mode2_criteria_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m2_c_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            status_pdf = await message.answer("📄 Mezon PDF qabul qilindi, o‘qilmoqda...")
            images = pdf_to_images(pdf_path)
            cpath = images[0] if images else pdf_path
            await state.update_data(criteria_path=cpath)
            await status_pdf.delete()
            await state.set_state(BotStates.m2_keys)
            await ask_m2_keys(message)
        except Exception as e:
            logger.error(f"Mode 2 Criteria PDF error: {e}")
            await message.answer("❌ PDF faylni ochishda xatolik yuz berdi. Rasm ko‘rinishida yuboring.")
    else:
        await message.answer("Iltimos, mezonni rasm yoki PDF formatida yuboring.")

@dp.message(BotStates.m2_criteria, F.photo)
async def mode2_criteria(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    cpath = f"temp/m2_c_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=cpath)
    await state.update_data(criteria_path=cpath)

    await state.set_state(BotStates.m2_keys)
    await ask_m2_keys(message)

async def ask_m2_keys(message: types.Message):
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Kalit mezonda bor (Keyingi qadam)", callback_data="m2_skip_keys")]
    ])
    msg_text = (
        "✅ **BSB baholash mezoni qabul qilindi!**\n\n"
        "📍 **2-QADAM (3 tadan): To‘g‘ri javoblar KALITINI yuboring**\n"
        "*(Matn, rasm yoki PDF ko‘rinishida)*\n\n"
        "🔑 **KALIT UCHUN NAMUNA (Qanday yuborish kerak?):**\n"
        "1️⃣ **Matn ko‘rinishida** botga yozib yuborishingiz mumkin:\n"
        "• 1-topshiriq javobi: Axborot — bu atrof-muhit haqidagi maʼlumotlar to‘plami...\n"
        "• 2-topshiriq javobi: Algoritm chiziqli, tarmoqlanuvchi va takrorlanuvchi bo‘ladi.\n"
        "• 3-topshiriq javobi: Natija: X = 120, Y = 45...\n\n"
        "2️⃣ **Yoki to‘g‘ri javoblar/yechimlar yozilgan varaq fotosuratini** yuboring!\n\n"
        "💡 _Agar to‘g‘ri javoblar kaliti mezon varag‘ining o‘zida bo‘lsa, pastdagi **'⚡ Kalit mezonda bor'** tugmasini bosing:_"
    )
    await message.answer(msg_text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "m2_skip_keys")
async def cb_m2_skip_keys(callback: CallbackQuery, state: FSMContext):
    await state.update_data(keys_path="", keys_text="Mezonda ko'rsatilgan")
    await callback.answer("Keyingi qadamga o'tildi")
    await state.set_state(BotStates.m2_works)
    await ask_m2_works(callback.message)

@dp.message(BotStates.m2_keys, F.text)
async def mode2_keys_text(message: types.Message, state: FSMContext):
    if message.text.lower() in ["❌ bekor qilish", "bekor qilish", "/start"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    await state.update_data(keys_text=message.text.strip(), keys_path="")
    await state.set_state(BotStates.m2_works)
    await ask_m2_works(message)

@dp.message(BotStates.m2_keys, F.document)
async def mode2_keys_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m2_k_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            images = pdf_to_images(pdf_path)
            kpath = images[0] if images else pdf_path
            await state.update_data(keys_path=kpath, keys_text="")
            await state.set_state(BotStates.m2_works)
            await ask_m2_works(message)
        except Exception as e:
            logger.error(f"Mode 2 Keys PDF error: {e}")
            await message.answer("❌ PDF kalitni ochishda xatolik yuz berdi. Rasm yuboring.")
    else:
        await message.answer("Iltimos, kalitni rasm yoki matn ko‘rinishida yuboring.")

@dp.message(BotStates.m2_keys, F.photo)
async def mode2_keys_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    kpath = f"temp/m2_k_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=kpath)
    await state.update_data(keys_path=kpath, keys_text="")

    await state.set_state(BotStates.m2_works)
    await ask_m2_works(message)

async def ask_m2_works(message: types.Message):
    msg_text = (
        "✅ **To‘g‘ri javoblar kaliti qabul qilindi!**\n\n"
        "📍 **3-QADAM (3 tadan): O‘quvchilarning daftardagi/qog‘ozdagi yozma ishlari rasmlarini yuboring**\n"
        "*(Barcha o‘quvchilar rasmlarini birin-ketin yoki bitta umumiy PDF faylda yuborishingiz mumkin)*\n\n"
        "📝 **O‘QUVCHI ISHI UCHUN NAMUNA (Qanday bo‘lishi kerak?):**\n"
        "• O‘quvchining daftari yoki toza oq qog‘ozga yozgan BSB topshiriqlari yechimlari;\n"
        "• Varaqning yuqorisida **o‘quvchining ismi va familiyasi** (masalan: _Rahimova Madina 8-B_) aniq ko‘rinishi shart;\n"
        "• Har bir topshiriq raqami va yozuvi tushunarli yoritilgan bo‘lsin.\n\n"
        "📸 _O‘quvchilar daftarlari rasmlarini birin-ketin yuboravering. Barchasini yuborib bo‘lgach, pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing:_"
    )
    await message.answer(msg_text, reply_markup=get_action_keyboard(show_finish=True), parse_mode="Markdown")

@dp.message(BotStates.m2_works, F.document)
async def mode2_works_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m2_w_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            images = pdf_to_images(pdf_path)
            data = await state.get_data()
            wlist = data.get("works_paths", [])
            wlist.extend(images)
            await state.update_data(works_paths=wlist)
            ikb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🚀 Hisobotni tayyorlash ({len(wlist)} ta ish)", callback_data="m2_finish_now")]
            ])
            await message.answer(
                f"📥 PDF dan {len(images)} ta sahifa qo‘shildi (Jami ishlar: {len(wlist)} ta).\n\n"
                f"• Yana ishlar bo‘lsa, yuboravering;\n"
                f"• Tayyor bo‘lsa, pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing!",
                reply_markup=ikb,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Mode 2 Works PDF error: {e}")
            await message.answer("❌ PDF faylni ochishda xatolik yuz berdi.")
    else:
        await message.answer("Iltimos, o‘quvchi ishlarini rasm yoki PDF ko‘rinishida yuboring.")

@dp.message(BotStates.m2_works, F.photo)
async def mode2_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    wpath = f"temp/m2_w_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=wpath)

    data = await state.get_data()
    wlist = data.get("works_paths", [])
    wlist.append(wpath)
    await state.update_data(works_paths=wlist)

    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚀 Hisobotni tayyorlash ({len(wlist)} ta ish)", callback_data="m2_finish_now")],
        [InlineKeyboardButton(text="⚡ Faqat shu 1 ta rasmni tekshirish", callback_data="m2_single_image_process")]
    ])
    await message.answer(
        f"📥 **{len(wlist)}-o‘quvchi ishi qabul qilindi.**\n\n"
        f"• Yana ishlar bo‘lsa, rasmlarini yuboravering;\n"
        f"• BSB hisobotini chiqarish uchun pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing!",
        reply_markup=ikb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "m2_single_image_process")
async def cb_m2_single(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    wlist = data.get("works_paths", [])
    if not wlist:
        cpath = data.get("criteria_path", "")
        if cpath:
            await state.update_data(works_paths=[cpath])
    await callback.answer("⏳ BSB tekshirish boshlanmoqda...")
    await mode2_finish(callback.message, state, user_id=callback.from_user.id, username=callback.from_user.username)

@dp.callback_query(F.data == "m2_finish_now")
async def cb_m2_finish(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏳ BSB hisoboti tayyorlanmoqda...")
    await mode2_finish(callback.message, state, user_id=callback.from_user.id, username=callback.from_user.username)

@dp.message(BotStates.m2_works, F.text.lower().in_(["tayyor", "tayyorla", "tayyorlang", "boshla", "boshlang", "tekshir", "tekshiring", "bo'ldi", "boldi", "hisobot", "qil", "ha", "ok", "1"]))
@dp.message(BotStates.m2_works, F.text == "✅ Rasmlar tugadi, hisobotni tayyorlang!")
async def mode2_finish(message: types.Message, state: FSMContext, user_id: int = None, username: str = None):
    actual_user_id = user_id or (message.from_user.id if message.from_user else 0)
    actual_username = username or (message.from_user.username if message.from_user and message.from_user.username else str(actual_user_id))

    data = await state.get_data()
    cpath = data.get("criteria_path", "")
    kpath = data.get("keys_path", "")
    ktext = data.get("keys_text", "")
    wlist = data.get("works_paths", [])

    if not wlist:
        await message.answer("Iltimos, avval kamida bitta o‘quvchi ishi rasmini yuboring.")
        return

    is_text_key = bool(ktext)
    keys_input = ktext if is_text_key else kpath

    status_msg = await message.answer(f"⏳ Navbatga olindi. {len(wlist)} nafar o‘quvchining daftardagi ishlari 4 tadan bo‘lib tekshirilmoqda...")

    async def update_progress(text):
        try:
            await status_msg.edit_text(text)
        except:
            pass

    async def send_batch_works_results(batch_students, current_count, total_count):
        if not batch_students:
            return
        lines = [f"📋 **Tekshirildi ({current_count}/{total_count}-o‘quvchilar):**"]
        for st in batch_students:
            tr = st.get("tr", "")
            name = st.get("name", "O‘quvchi")
            score = st.get("total_score", 0)
            note = st.get("note", "Tekshirildi")
            lines.append(f"{tr}. 👤 **{name}** — **{score} ball**\n   📝 _Tahlil: {note}_")
        txt = "\n\n".join(lines)
        try:
            await message.answer(txt, parse_mode="Markdown")
        except Exception:
            await message.answer(txt)

    try:
        parsed = await ai_service.evaluate_student_works(
            cpath, wlist,
            progress_callback=update_progress,
            batch_callback=send_batch_works_results,
            keys_input=keys_input,
            is_text_key=is_text_key
        )
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{actual_user_id}_{cname}_bsb_evaluated.xlsx"
        build_bsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_BSB_tekshirilgan_hisobot.xlsx")
        cap = f"🎉 **{cname} sinf o‘quvchilarining yozma ishlari to‘liq tekshirildi va BSB hisoboti tuzildi!**{FEEDBACK_NOTE}"
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(actual_user_id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Tekshirilgan BSB: {cname} | @{actual_username}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(actual_user_id, credit_type, admin_id=ADMIN_ID)
        db_service.clear_session_files(actual_user_id, "m4")
        await state.clear()
    except Exception as e:
        logger.error(f"Mode 2 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")

# ==================== 3-REJIM: CHSB BALLAR ORQALI ====================
@dp.message(F.text.contains("2️⃣ CHSB (Ballar orqali)"))
@dp.message(F.text.contains("3️⃣ CHSB (Ballar orqali)"))
@dp.message(F.text.contains("CHSB (Ballar orqali)"))
async def mode3_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid != ADMIN_ID and not db_service.is_vip_user(uid):
        await message.answer(
            "ℹ️ Sizga **🎯 CHSB (Testlarni tekshirish)** xizmati biriktirilgan.\n\nBoshqa bo‘limlarni ochish uchun adminga murojaat qiling: @Obidbek1988",
            reply_markup=get_main_keyboard(uid)
        )
        return
    can_proceed, credit_type = await check_access_and_notify(message)
    if not can_proceed:
        return

    await state.clear()
    await state.update_data(credit_type=credit_type)
    await state.set_state(BotStates.m3_journal)
    await message.answer(
        "📊 **3-REJIM: CHSB (Ballar orqali hisobot)**\n\n"
        "1-qadam: eMaktab elektron jurnali **Excel (.xlsx/.xls) faylini**, **PDF faylini** yoki **skrinshotini** (CHSB 40 ballik ustuni bilan) yuboring:\n"
        "*(Excel fayl bo‘lsa 100% xatosiz va darhol tayyor bo‘ladi!)*",
        reply_markup=get_action_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(BotStates.m3_journal, F.document)
async def mode3_journal_document(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    
    # If PDF
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m3_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            status_pdf = await message.answer("📄 CHSB jurnali PDF qabul qilindi, sahifalari o‘qilmoqda...")
            images = pdf_to_images(pdf_path)
            jpath = images[0] if images else pdf_path
            await state.update_data(journal_path=jpath)
            await status_pdf.delete()
            await state.set_state(BotStates.m3_criteria)
            await message.answer(
                "✅ Jurnal PDF qabul qilindi!\n\n"
                "2-qadam: Ushbu CHSB ning **Baholash mezoni skrinshotini yoki PDF faylini** yuboring:",
                reply_markup=get_action_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Mode 3 PDF error: {e}")
            await message.answer("❌ PDF faylni o‘qishda xatolik yuz berdi. Iltimos, rasm yoki Excel yuboring.")
        return

    if not (fname.endswith(".xlsx") or fname.endswith(".xls")):
        await message.answer("Iltimos, eMaktab elektron jurnalini Excel (.xlsx, .xls) yoki PDF formatda yuboring.")
        return

    status_msg = await message.answer(f"⏳ CHSB elektron jurnali ({fname}) to‘g‘ridan-to‘g‘ri o‘qilmoqda...")
    os.makedirs("temp", exist_ok=True)
    ext = ".xls" if fname.endswith(".xls") else ".xlsx"
    fpath = f"temp/m3_doc_{message.from_user.id}_{message.message_id}{ext}"
    await bot.download(message.document, destination=fpath)

    try:
        from emaktab_parser import distribute_chsb_40
        parsed = parse_emaktab_file(fpath, target_mode="CHSB")
        # Update students task_scores with CHSB B, Q, M (6, 24, 10)
        for st in parsed.get("students", []):
            st["task_scores"] = distribute_chsb_40(st.get("total_score"))

        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_chsb.xlsx"
        build_chsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_CHSB_hisobot.xlsx")
        cap = (
            f"🎉 **{cname} sinf CHSB hisoboti tayyor!**\n"
            f"• Manba: eMaktab elektron jurnali ({fname})\n"
            f"• A4 Portret format\n"
            f"• (B) Bilish (6 ball), (Q) Qo‘llash (24 ball), (M) Mulohaza (10 ball) taqsimlandi."
            f"{FEEDBACK_NOTE}"
        )
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Yangi CHSB (Excel): {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
        credit_type = (await state.get_data()).get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
    except Exception as e:
        logger.error(f"Mode 3 Excel Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")
    finally:
        await state.clear()

@dp.message(BotStates.m3_journal, F.photo)
async def mode3_journal(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    fpath = f"temp/m3_j_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=fpath)
    await state.update_data(journal_path=fpath)

    await state.set_state(BotStates.m3_criteria)
    await message.answer(
        "✅ Jurnal qabul qilindi!\n\n"
        "2-qadam: Ushbu CHSB ning **Baholash mezoni skrinshotini yoki PDF faylini** yuboring:",
        reply_markup=get_action_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(BotStates.m3_criteria, F.document)
async def mode3_criteria_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m3_c_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            images = pdf_to_images(pdf_path)
            cpath = images[0] if images else pdf_path
            
            pos, eta = queue_manager.get_queue_info()
            queue_msg = f"⏳ Navbatdagi o‘rningiz: №{pos} (kutilmoqda: ~{eta}s)..." if pos > 1 else "⏳ CHSB (B, Q, M) tahlil qilinmoqda..."
            status_msg = await message.answer(queue_msg)

            data = await state.get_data()
            jpath = data.get("journal_path")

            parsed = await ai_service.parse_chsb_data(jpath, cpath)
            cname = parsed.get("school_info", {}).get("class_name", "sinf")
            out_excel = f"temp/{message.from_user.id}_{cname}_chsb.xlsx"
            build_chsb_excel(parsed, out_excel)

            doc = FSInputFile(out_excel, filename=f"{cname}_CHSB_hisobot.xlsx")
            cap = (
                f"🎉 **{cname} sinf CHSB hisoboti tayyor!**\n"
                f"• (B) Bilish (6 ball), (Q) Qo‘llash (24 ball), (M) Mulohaza (10 ball) taqsimlangan."
                f"{FEEDBACK_NOTE}"
            )
            await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
            await send_to_archive(out_excel, f"📁 Yangi CHSB: {cname} | @{message.from_user.username or message.from_user.id}")
            await status_msg.delete()
            credit_type = data.get("credit_type", "paid")
            db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
        except Exception as e:
            logger.error(f"Mode 3 Criteria PDF error: {e}", exc_info=True)
            await message.answer(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")
        finally:
            await state.clear()
    else:
        await message.answer("Iltimos, mezonni rasm yoki PDF formatida yuboring.")

@dp.message(BotStates.m3_criteria, F.photo)
async def mode3_criteria(message: types.Message, state: FSMContext):
    pos, eta = queue_manager.get_queue_info()
    queue_msg = f"⏳ Navbatdagi o‘rningiz: №{pos} (kutilmoqda: ~{eta}s)..." if pos > 1 else "⏳ CHSB (B, Q, M) tahlil qilinmoqda..."
    status_msg = await message.answer(queue_msg)

    os.makedirs("temp", exist_ok=True)
    cpath = f"temp/m3_c_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=cpath)

    data = await state.get_data()
    jpath = data.get("journal_path")

    try:
        parsed = await ai_service.parse_chsb_data(jpath, cpath)
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_chsb.xlsx"
        build_chsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_CHSB_hisobot.xlsx")
        cap = (
            f"🎉 **{cname} sinf CHSB hisoboti tayyor!**\n"
            f"• (B) Bilish (6 ball), (Q) Qo‘llash (24 ball), (M) Mulohaza (10 ball) taqsimlangan."
            f"{FEEDBACK_NOTE}"
        )
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Yangi CHSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
    except Exception as e:
        logger.error(f"Mode 3 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")
    finally:
        await state.clear()

# ==================== 4-REJIM: CHSB TESTLARNI TEKSHIRISH ====================

@dp.message(F.text.contains("4️⃣ CHSB (Testlarni tekshirish)"))
@dp.message(F.text.contains("CHSB (Testlarni tekshirish)"))
@dp.message(F.text.contains("Testlarni tekshirish"))
async def mode4_start(message: types.Message, state: FSMContext):
    can_proceed, credit_type = await check_access_and_notify(message)
    if not can_proceed:
        return

    await state.clear()
    await state.update_data(credit_type=credit_type, test_paths=[])
    await state.set_state(BotStates.m4_select_grade_or_custom)

    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 9-sinf (O‘zbek)", callback_data="chsb_pick_9"),
            InlineKeyboardButton(text="🇷🇺 9-класс (Русский)", callback_data="chsb_pick_9_ru")
        ],
        [
            InlineKeyboardButton(text="🇺🇿 10-sinf (O‘zbek)", callback_data="chsb_pick_10"),
            InlineKeyboardButton(text="🇷🇺 10-класс (Русский)", callback_data="chsb_pick_10_ru")
        ],
        [
            InlineKeyboardButton(text="🇺🇿 11-sinf (O‘zbek)", callback_data="chsb_pick_11"),
            InlineKeyboardButton(text="🇷🇺 11-класс (Русский)", callback_data="chsb_pick_11_ru")
        ],
        [InlineKeyboardButton(text="🔄 Boshqa sinf / O‘z mezoningizni yuklash", callback_data="chsb_pick_custom")]
    ])
    msg_text = (
        "🎯 **CHSB TEST TAHLILI VA HISOBOTI (1-CHORAK)**\n\n"
        "Fan: **Informatika va axborot texnologiyalari (O‘zbek sinf)**\n\n"
        "🏛 Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazining **9, 10 va 11-sinf original test variantlari va mezonlari** tizimda tayyor mavjud!\n\n"
        "📢 _Boshqa fanlar (Tarix, Ona tili, Ingliz tili, Matematika, Biologiya...) uchun ham test va mezonlarni agentga qo‘shib beramiz! Murojaat: @Obidbek1988_\n\n"
        "Quyidagilardan birini tanlang:"
    )
    await message.answer(msg_text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data.in_(["chsb_pick_9", "chsb_pick_10", "chsb_pick_11", "chsb_pick_9_ru", "chsb_pick_10_ru", "chsb_pick_11_ru"]))
async def cb_chsb_pick(callback: CallbackQuery, state: FSMContext):
    data_str = callback.data.replace("chsb_pick_", "")
    is_ru = "_ru" in data_str
    grade_code = data_str.replace("_ru", "")
    lang = "ru" if is_ru else "uz"
    chsb_info = get_chsb_for_grade(grade_code, lang=lang)
    if not chsb_info:
        await callback.answer("Ma'lumot topilmadi.")
        return

    crit_summary = (
        f"📋 **MEZON VA BALLAR TAQSIMOTI ({chsb_info['max_score']} ball):**\n"
        f"{chsb_info['distribution_summary']}\n\n"
        f"🔢 **1 dan 15 gacha savollar bo‘yicha taqsimot:**\n"
        f"`{chsb_info['bqm_compact']}`"
    )
    await state.update_data(
        grade=grade_code,
        lang=lang,
        criteria_text=crit_summary,
        criteria_path="",
        keys_text=chsb_info["keys"],
        keys_path="",
        pdf_path=chsb_info.get("pdf_path", "")
    )

    card_text = (
        f"📚 **{chsb_info['title']} (O‘zbek sinf)**\n"
        f"🏛 _{chsb_info['agency']}_\n"
        f"📋 **1-CHORAK 1-CHSB (ORIGINAL TEST VARIANTI)**\n"
        f"Jami: **{chsb_info['total_questions']} ta test — {chsb_info['max_score']} ball**\n\n"
        f"{crit_summary}\n\n"
        f"Pastdagi tugmalar orqali test varaqasini ko‘rishingiz yoki mezonni tasdiqlashingiz mumkin:"
    )

    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Original test PDF faylini ko‘rish", callback_data="m4_show_test_pdf")],
        [InlineKeyboardButton(text="✅ Shu original mezonni tasdiqlash", callback_data="m4_confirm_criteria")],
        [InlineKeyboardButton(text="✏️ Mezon (B-Q-M) ni tahrirlash", callback_data="m4_edit_criteria")],
        [InlineKeyboardButton(text="🔄 Boshqa mezon yuklash", callback_data="chsb_pick_custom")]
    ])
    await callback.answer()
    await callback.message.edit_text(card_text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "m4_show_test_pdf")
async def cb_m4_show_test_pdf(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    grade = data.get("grade", "9")
    pdf_path = data.get("pdf_path", "") or f"assets/{grade}_sinf_informatika_chsb1_original.pdf"
    if os.path.exists(pdf_path):
        doc = FSInputFile(pdf_path, filename=f"{grade}_sinf_Informatika_1_CHSB_Original_Test.pdf")
        await callback.message.answer_document(
            doc,
            caption=f"📄 **{grade}-sinf Informatika 1-CHSB Original test varianti (Markaz testi, 15 ta savol)**\n\nUshbu test varianti asosida baholash mezoni va to‘g‘ri javoblar kaliti tuzilgan.",
            parse_mode="Markdown"
        )
        await callback.answer("PDF yuborildi.")
    else:
        await callback.answer("Fayl topilmadi.", show_alert=True)

@dp.callback_query(F.data == "m4_edit_criteria")
async def cb_m4_edit_criteria(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.m4_edit_criteria_input)
    await callback.answer()
    msg = (
        "✏️ **CHSB BAHOLASH MEZONINI TAHRIRLASH:**\n\n"
        "1 dan 15 gacha qaysi savollar (B) Bilish, (Q) Qo‘llash yoki (M) Mulohaza ekanligini yozib yuboring.\n\n"
        "Masalan:\n"
        "`1-B, 2-Q, 3-Q, 4-B, 5-Q, 6-Q, 7-B, 8-Q, 9-Q, 10-Q, 11-Q, 12-Q, 13-M, 14-Q, 15-M`\n\n"
        "*(Bekor qilish uchun: '❌ Bekor qilish')*"
    )
    await callback.message.answer(msg, parse_mode="Markdown")

@dp.message(BotStates.m4_edit_criteria_input, F.text)
async def mode4_edit_criteria_handler(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.lower() in ["❌ bekor qilish", "bekor qilish", "/cancel", "cancel"]:
        await state.set_state(BotStates.m4_select_grade_or_custom)
        await message.answer("Tahrirlash bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    updated_crit = f"Foydalanuvchi tomonidan kiritilgan CHSB mezoni:\n{text}\n(Jami 15 ta test = 40 ball)"
    await state.update_data(criteria_text=updated_crit, criteria_path="")

    msg = (
        f"✅ **Yangi mezon saqlandi:**\n\n"
        f"`{text}`\n\n"
        f"Mezonni tasdiqlab, keyingi bosqichga o‘tasizmi?"
    )
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Shu mezonni tasdiqlash", callback_data="m4_confirm_criteria")],
        [InlineKeyboardButton(text="✏️ Qayta tahrirlash", callback_data="m4_edit_criteria")]
    ])
    await message.answer(msg, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "chsb_pick_custom")
async def cb_chsb_pick_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.m4_criteria)
    await callback.answer()
    msg = (
        "📋 **O‘Z MEZONINGIZNI YUKLASH (Boshqa sinf yoki fan uchun):**\n\n"
        "Iltimos, CHSB baholash mezonini yoki namunaviy test varaqasini yuboring:\n"
        "*(Rasm, PDF yoki matn ko‘rinishida)*\n\n"
        "💡 _AI mezonni o‘qib, 1 dan 15 gacha (B), (Q), (M) taqsimotini aniqlab beradi va uni tahrirlashingiz mumkin bo‘ladi._"
    )
    await callback.message.answer(msg, reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    ), parse_mode="Markdown")

@dp.message(BotStates.m4_criteria, F.photo)
async def mode4_custom_criteria_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    cpath = f"temp/m4_c_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=cpath)

    status_msg = await message.answer("⏳ Mezon fotosurati tahlil qilinmoqda...")
    try:
        prompt = (
            "Ushbu CHSB mezon rasmini tahlil qiling. 1 dan 15 gacha bo'lgan test savollarining qaysi biri "
            "(B) Bilish, qaysi biri (Q) Qo'llash va qaysi biri (M) Mulohaza ekanligini aniqlang. "
            "Qisqa matn ko'rinishida quyidagicha qaytaring: "
            "1-B, 2-Q, 3-Q, 4-B... va ballar taqsimotini ko'rsating. Boshqa ortiqcha gap yozmang."
        )
        parsed_crit = ai_service._send_prompt_to_gemini(prompt, [cpath])
        crit_str = str(parsed_crit).strip()
    except Exception as e:
        logger.error(f"Custom criteria AI error: {e}")
        crit_str = "1-B, 2-Q, 3-Q, 4-B, 5-Q, 6-Q, 7-B, 8-Q, 9-Q, 10-Q, 11-Q, 12-Q, 13-M, 14-Q, 15-M (40 ball)"

    await status_msg.delete()
    await state.update_data(criteria_path=cpath, criteria_text=crit_str)

    msg = (
        f"📋 **ANIQLANGAN BAHOLASH MEZONI:**\n\n"
        f"{crit_str}\n\n"
        f"Mezon to‘g‘rimi? Tasdiqlaysizmi yoki tahrirlaysizmi?"
    )
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Mezonni tasdiqlash", callback_data="m4_confirm_criteria")],
        [InlineKeyboardButton(text="✏️ Mezonni tahrirlash", callback_data="m4_edit_criteria")]
    ])
    await message.answer(msg, reply_markup=ikb, parse_mode="Markdown")

@dp.message(BotStates.m4_criteria, F.document)
async def mode4_custom_criteria_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m4_c_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        images = pdf_to_images(pdf_path)
        cpath = images[0] if images else pdf_path

        status_msg = await message.answer("⏳ PDF mezon tahlil qilinmoqda...")
        try:
            prompt = (
                "Ushbu CHSB mezon faylini tahlil qiling. 1 dan 15 gacha bo'lgan test savollarining qaysi biri "
                "(B) Bilish, qaysi biri (Q) Qo'llash va qaysi biri (M) Mulohaza ekanligini aniqlang. "
                "Qisqa matn ko'rinishida: 1-B, 2-Q, 3-Q... shaklida qaytaring."
            )
            parsed_crit = ai_service._send_prompt_to_gemini(prompt, [cpath])
            crit_str = str(parsed_crit).strip()
        except Exception:
            crit_str = "1-B, 2-Q, 3-Q, 4-B, 5-Q, 6-Q, 7-B, 8-Q, 9-Q, 10-Q, 11-Q, 12-Q, 13-M, 14-Q, 15-M (40 ball)"

        await status_msg.delete()
        await state.update_data(criteria_path=cpath, criteria_text=crit_str)

        msg = (
            f"📋 **PDF DAN ANIQLANGAN MEZON:**\n\n"
            f"{crit_str}\n\n"
            f"Mezon to‘g‘rimi? Tasdiqlaysizmi yoki tahrirlaysizmi?"
        )
        ikb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Mezonni tasdiqlash", callback_data="m4_confirm_criteria")],
            [InlineKeyboardButton(text="✏️ Mezonni tahrirlash", callback_data="m4_edit_criteria")]
        ])
        await message.answer(msg, reply_markup=ikb, parse_mode="Markdown")
    else:
        await message.answer("Iltimos, mezonni rasm yoki PDF formatida yuboring.")

@dp.message(BotStates.m4_criteria, F.text)
async def mode4_custom_criteria_text(message: types.Message, state: FSMContext):
    if message.text.lower() in ["❌ bekor qilish", "bekor qilish", "/cancel", "cancel"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    crit_str = message.text.strip()
    await state.update_data(criteria_text=crit_str, criteria_path="")
    msg = (
        f"📋 **QABUL QILINGAN MEZON:**\n\n"
        f"`{crit_str}`\n\n"
        f"Mezon to‘g‘rimi? Tasdiqlaysizmi yoki tahrirlaysizmi?"
    )
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Mezonni tasdiqlash", callback_data="m4_confirm_criteria")],
        [InlineKeyboardButton(text="✏️ Mezonni tahrirlash", callback_data="m4_edit_criteria")]
    ])
    await message.answer(msg, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "m4_confirm_criteria")
async def cb_m4_confirm_criteria(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    keys_text = data.get("keys_text", "")
    if not keys_text:
        keys_text = "1-C, 2-A, 3-D, 4-C, 5-C, 6-A, 7-C, 8-D, 9-A, 10-B, 11-B, 12-D, 13-C, 14-A, 15-C"
        await state.update_data(keys_text=keys_text)

    await callback.answer("Mezon tasdiqlandi!")
    await show_m4_keys_card(callback.message, keys_text)

async def show_m4_keys_card(message: types.Message, keys_str: str):
    msg_text = (
        "✅ **CHSB Baholash mezoni tasdiqlandi!**\n\n"
        "📍 **2-QADAM (3 tadan): Testning to‘g‘ri javoblar KALITI**\n\n"
        "🔑 **Hozirgi to‘g‘ri javoblar kaliti:**\n"
        f"`{keys_str}`\n\n"
        "Shu kalitni tasdiqlaysizmi yoki o‘zgartirmoqchimisiz?"
    )
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Shu to‘g‘ri kalitni tasdiqlash", callback_data="m4_confirm_key")],
        [InlineKeyboardButton(text="✏️ Kalitni o‘zgartirish / tahrirlash", callback_data="m4_edit_key")],
        [InlineKeyboardButton(text="🔑 Boshqa kalit kiritish (Matn/Rasm)", callback_data="m4_custom_key")]
    ])
    try:
        await message.edit_text(msg_text, reply_markup=ikb, parse_mode="Markdown")
    except Exception:
        await message.answer(msg_text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data.in_(["m4_edit_key", "m4_custom_key"]))
async def cb_m4_edit_key(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.m4_edit_keys_input)
    await callback.answer()
    msg = (
        "✏️ **TO‘G‘RI JAVOBLAR KALITINI KIRITING:**\n\n"
        "Kalitni matn ko‘rinishida yozing yoki fotosuratini yuboring:\n\n"
        "Masalan (matn ko‘rinishida):\n"
        "`1-C, 2-A, 3-D, 4-C, 5-C, 6-A, 7-C, 8-D, 9-A, 10-B, 11-B, 12-D, 13-C, 14-A, 15-C`\n\n"
        "*(Bekor qilish uchun: '❌ Bekor qilish')*"
    )
    await callback.message.answer(msg, parse_mode="Markdown")

@dp.message(BotStates.m4_edit_keys_input, F.text)
async def mode4_edit_keys_text(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.lower() in ["❌ bekor qilish", "bekor qilish", "/cancel", "cancel"]:
        data = await state.get_data()
        await show_m4_keys_card(message, data.get("keys_text", ""))
        return

    await state.update_data(keys_text=text, keys_path="")
    await show_m4_keys_card(message, text)

@dp.message(BotStates.m4_edit_keys_input, F.photo)
async def mode4_edit_keys_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    kpath = f"temp/m4_k_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=kpath)
    await state.update_data(keys_path=kpath, keys_text="")

    msg = (
        "📸 **Kalit fotosurati qabul qilindi!**\n\n"
        "Shu kalit tasviri bo‘yicha tekshirishni tasdiqlaysizmi?"
    )
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Shu rasm kalitni tasdiqlash", callback_data="m4_confirm_key")],
        [InlineKeyboardButton(text="✏️ Qayta kiritish", callback_data="m4_edit_key")]
    ])
    await message.answer(msg, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "m4_confirm_key")
async def cb_m4_confirm_key(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.m4_student_tests)
    await callback.answer("Kalit tasdiqlandi!")
    await ask_m4_student_tests(callback.message)

async def ask_m4_student_tests(message: types.Message):
    guide_path = "assets/test_namuna_guide.jpg"
    msg_text = (
        "✅ **To‘g‘ri javoblar kaliti tasdiqlandi!**\n\n"
        "📸 **3-QADAM (3 tadan): O‘quvchilarning test javoblari varaqalari rasmlarini yuboring**\n"
        "*(Barcha o‘quvchilar rasmlarini birin-ketin yoki bitta umumiy PDF faylda yuborishingiz mumkin)*\n\n"
        "📋 **RASMGA OLISH VA YUBORISH NAMUNASI (Suratga qarang):**\n"
        "• **1-rasm (Oldi tomoni):** O‘quvchi F.I.O.si (masalan: *Erkayev Umidjon 9-B*) va savollar;\n"
        "• **2-rasm (Orqa tomoni):** 1 dan 15 gacha to‘ldirilgan Javoblar jadvali (kalit matrisi);\n"
        "• AI ikkala rasmni bitta o‘quvchining ishi deb avtomatik birlashtirib tekshiradi!\n\n"
        "🚀 _O‘quvchilar test varaqalarini birin-ketin yuboravering. Barchasini yuborib bo‘lgach, pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing:_"
    )
    if os.path.exists(guide_path):
        photo = FSInputFile(guide_path)
        await message.answer_photo(photo, caption=msg_text, reply_markup=get_action_keyboard(show_finish=True), parse_mode="Markdown")
    else:
        await message.answer(msg_text, reply_markup=get_action_keyboard(show_finish=True), parse_mode="Markdown")

@dp.message(BotStates.m4_student_tests, F.document)
async def mode4_student_tests_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m4_t_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            images = pdf_to_images(pdf_path)
            data = await state.get_data()
            tlist = data.get("test_paths", [])
            tlist.extend(images)
            await state.update_data(test_paths=tlist)
            ikb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🚀 Hisobotni tayyorlash ({len(tlist)} ta o‘quvchi)", callback_data="m4_finish_now")]
            ])
            await message.answer(
                f"📥 PDF dan {len(images)} ta sahifa qo‘shildi (Jami testlar: {len(tlist)} ta).\n\n"
                f"• Yana testlar bo‘lsa, yuboravering;\n"
                f"• Hisobotni chiqarish uchun pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing!",
                reply_markup=ikb,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Mode 4 Test PDF error: {e}")
            await message.answer("❌ PDF faylni ochishda xatolik yuz berdi.")
    else:
        await message.answer("Iltimos, o‘quvchilar test varaqalarini rasm yoki PDF formatida yuboring.")

@dp.message(BotStates.m4_student_tests, F.photo)
async def mode4_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    tpath = f"temp/m4_t_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=tpath)

    db_service.save_session_file(message.from_user.id, "m4", tpath)
    tlist = db_service.get_session_files(message.from_user.id, "m4")
    await state.update_data(test_paths=tlist)

    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚀 Hisobotni tayyorlash ({len(tlist)} ta o‘quvchi)", callback_data="m4_finish_now")],
        [InlineKeyboardButton(text="⚡ Faqat shu 1 ta rasmni tekshirish", callback_data="m4_single_image_process")]
    ])
    await message.answer(
        f"📥 **{len(tlist)}-o‘quvchi test varaqasi qabul qilindi!**\n\n"
        f"• Yana o‘quvchilar bo‘lsa, rasmlarini yuboravering;\n"
        f"• Hisobotni chiqarish uchun pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing!",
        reply_markup=ikb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "m4_single_image_process")
async def cb_m4_single(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tlist = data.get("test_paths", [])
    if not tlist:
        kpath = data.get("keys_path", "")
        if kpath:
            await state.update_data(test_paths=[kpath])
    await callback.answer("⏳ Tekshirish boshlanmoqda...")
    await mode4_finish(callback.message, state, user_id=callback.from_user.id, username=callback.from_user.username)

@dp.callback_query(F.data == "m4_finish_now")
async def cb_m4_finish(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏳ Hisobot tayyorlanmoqda...")
    await mode4_finish(callback.message, state, user_id=callback.from_user.id, username=callback.from_user.username)

@dp.message(BotStates.m4_student_tests, F.text.lower().in_(["tayyor", "tayyorla", "tayyorlang", "boshla", "boshlang", "tekshir", "tekshiring", "bo'ldi", "boldi", "hisobot", "qil", "ha", "ok", "1"]))
@dp.message(BotStates.m4_student_tests, F.text == "✅ Rasmlar tugadi, hisobotni tayyorlang!")
async def mode4_finish(message: types.Message, state: FSMContext, user_id: int = None, username: str = None):
    actual_user_id = user_id or (message.from_user.id if message.from_user else 0)
    actual_username = username or (message.from_user.username if message.from_user and message.from_user.username else str(actual_user_id))

    data = await state.get_data()
    cpath = data.get("criteria_path", "")
    ctext = data.get("criteria_text", "")
    kpath = data.get("keys_path", "")
    ktext = data.get("keys_text", "")
    tlist = data.get("test_paths") or db_service.get_session_files(actual_user_id, "m4")

    if not tlist:
        await message.answer("Iltimos, avval kamida bitta o‘quvchi test javobi rasmini yuboring.")
        return

    is_text_key = bool(ktext)
    keys_input = ktext if is_text_key else kpath

    is_text_crit = bool(ctext)
    crit_input = ctext if is_text_crit else cpath

    status_msg = await message.answer(f"⏳ **Tekshirish boshlandi!**\n\nAI {len(tlist)} nafar o‘quvchining test varaqasini o‘qib, to‘g‘ri javoblar kaliti va mezoni bilan solishtirmoqda (taxminan 15–25 soniya)...")

    async def update_progress(text):
        try:
            await status_msg.edit_text(text)
        except:
            pass

    async def send_batch_test_results(batch_students, current_count, total_count):
        if not batch_students:
            return
        lines = [f"📋 **Tekshirildi ({current_count}/{total_count}-o‘quvchilar testlari):**"]
        for st in batch_students:
            tr = st.get("tr", "")
            name = st.get("name", "O‘quvchi")
            score = st.get("total_score", 0)
            note = st.get("note", "Tekshirildi")
            lines.append(f"{tr}. 👤 **{name}** — **{score}/40 ball**\n   📝 _Tahlil: {note}_")
        txt = "\n\n".join(lines)
        try:
            await message.answer(txt, parse_mode="Markdown")
        except Exception:
            await message.answer(txt)

    try:
        parsed = await ai_service.evaluate_test_answers(
            keys_input, tlist,
            progress_callback=update_progress,
            batch_callback=send_batch_test_results,
            is_text_key=is_text_key,
            criteria_input=crit_input,
            is_text_criteria=is_text_crit
        )
        chosen_grade = data.get("grade", "")
        detected_class = str(parsed.get("school_info", {}).get("class_name", "")).strip()
        if chosen_grade in ["9", "10", "11"]:
            if chosen_grade in detected_class:
                cname = detected_class
            elif any(ch.isalpha() for ch in detected_class):
                letter = "".join([c for c in detected_class if c.isalpha()]).upper()
                cname = f"{chosen_grade}-{letter}"
            else:
                cname = f"{chosen_grade}-B"
        else:
            cname = detected_class or (f"{chosen_grade}-sinf" if chosen_grade else "9-sinf")

        lang = data.get("lang", "uz")
        if "school_info" not in parsed:
            parsed["school_info"] = {}
        parsed["school_info"]["lang"] = lang
        if lang == "ru":
            parsed["school_info"]["subject"] = "Информатика"
            parsed["school_info"]["teacher_name"] = "Кабилов Обиджон"
            parsed["school_info"]["head_teacher"] = "Махмудова Дильфузахон"
        out_excel = f"temp/{actual_user_id}_{cname}_chsb_test_hisoboti.xlsx"
        build_chsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_CHSB_test_hisoboti.xlsx")
        cap = f"🎉 **{cname} sinf CHSB testlari muvaffaqiyatli tekshirildi va test hisoboti tayyorlandi!**\n• Har bir o‘quvchining to‘g‘ri/noto‘g‘ri javoblari va yakuniy bali hisobotda aks etgan.{FEEDBACK_NOTE}"
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(actual_user_id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Tekshirilgan Test CHSB: {cname} | @{actual_username}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(actual_user_id, credit_type, admin_id=ADMIN_ID)
        await state.clear()
    except Exception as e:
        logger.error(f"Mode 4 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")

# ==================== 5-REJIM: BSB BAHOGA MOSLASH ====================
@dp.message(F.text.contains("5️⃣ BSB (Bahoga moslash)"))
@dp.message(F.text.contains("BSB (Bahoga moslash)"))
async def mode5_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid != ADMIN_ID and not db_service.is_vip_user(uid):
        await message.answer(
            "🔒 **BSB xizmatlari faqat ruxsat berilgan foydalanuvchilar uchun!**\n\n"
            "Ushbu bo‘limdan foydalanish uchun adminga murojaat qiling: @Obidbek1988",
            reply_markup=get_main_keyboard(uid)
        )
        return
    can_proceed, credit_type = await check_access_and_notify(message)
    if not can_proceed:
        return

    await state.clear()
    await state.update_data(credit_type=credit_type, works_paths=[], journal_averages={})
    await state.set_state(BotStates.m5_criteria)

    msg_text = (
        "✍️ **5-REJIM: BSB (Darsdagi o‘rtacha bahoga moslash)**\n\n"
        "📍 **1-QADAM (4 tadan): BSB Baholash mezonini yuboring**\n"
        "*(Rasm yoki PDF formatida)*\n\n"
        "📋 **MEZON UCHUN NAMUNA (Qanday bo‘lishi kerak?):**\n"
        "Mezonda BSB topshiriqlari va har biriga qo‘yiladigan ballar ko‘rsatiladi:\n"
        "• 1-topshiriq (Nazariy savol): **5 ball**\n"
        "• 2-topshiriq (Amaliy mashq): **10 ball**\n"
        "• 3-topshiriq (Masala yechish): **10 ball**\n"
        "• 4-topshiriq (Loyiha ishi): **25 ball**\n"
        "*(Jami: 50 ball)*\n\n"
        "📸 _Iltimos, BSB baholash mezoni jadvali fotosuratini yoki PDF faylini yuboring:_"
    )
    await message.answer(msg_text, reply_markup=get_action_keyboard(), parse_mode="Markdown")

@dp.message(BotStates.m5_criteria, F.document)
async def mode5_criteria_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m5_c_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            status_pdf = await message.answer("📄 Mezon PDF qabul qilindi, o‘qilmoqda...")
            images = pdf_to_images(pdf_path)
            cpath = images[0] if images else pdf_path
            await state.update_data(criteria_path=cpath)
            await status_pdf.delete()
            await state.set_state(BotStates.m5_keys)
            await ask_m5_keys(message)
        except Exception as e:
            logger.error(f"Mode 5 Criteria PDF error: {e}")
            await message.answer("❌ PDF faylni ochishda xatolik yuz berdi. Rasm ko‘rinishida yuboring.")
    else:
        await message.answer("Iltimos, mezonni rasm yoki PDF formatida yuboring.")

@dp.message(BotStates.m5_criteria, F.photo)
async def mode5_criteria_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    cpath = f"temp/m5_c_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=cpath)
    await state.update_data(criteria_path=cpath)

    await state.set_state(BotStates.m5_keys)
    await ask_m5_keys(message)

async def ask_m5_keys(message: types.Message):
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Kalit mezonda bor (Keyingi qadam)", callback_data="m5_skip_keys")]
    ])
    msg_text = (
        "✅ **BSB baholash mezoni qabul qilindi!**\n\n"
        "📍 **2-QADAM (4 tadan): To‘g‘ri javoblar KALITINI yuboring**\n"
        "*(Matn, rasm yoki PDF ko‘rinishida)*\n\n"
        "🔑 **KALIT UCHUN NAMUNA:**\n"
        "1️⃣ **Matn ko‘rinishida:**\n"
        "• 1-topshiriq javobi: Axborot — bu borliq haqidagi maʼlumotlar...\n"
        "• 2-topshiriq javobi: Algoritm chiziqli, tarmoqlanuvchi va takrorlanuvchi...\n"
        "2️⃣ **Yoki to‘g‘ri yechimlar yozilgan varaq fotosuratini** yuboring!\n\n"
        "💡 _Agar to‘g‘ri javoblar mezon varag‘ining o‘zida bo‘lsa, pastdagi **'⚡ Kalit mezonda bor'** tugmasini bosing:_"
    )
    await message.answer(msg_text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "m5_skip_keys")
async def cb_m5_skip_keys(callback: CallbackQuery, state: FSMContext):
    await state.update_data(keys_path="", keys_text="Mezonda ko'rsatilgan")
    await callback.answer("Keyingi qadamga o'tildi")
    await state.set_state(BotStates.m5_journal)
    await ask_m5_journal(callback.message)

@dp.message(BotStates.m5_keys, F.text)
async def mode5_keys_text(message: types.Message, state: FSMContext):
    if message.text.lower() in ["❌ bekor qilish", "bekor qilish", "/start"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return
    await state.update_data(keys_text=message.text.strip(), keys_path="")
    await state.set_state(BotStates.m5_journal)
    await ask_m5_journal(message)

@dp.message(BotStates.m5_keys, F.document)
async def mode5_keys_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m5_k_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            images = pdf_to_images(pdf_path)
            kpath = images[0] if images else pdf_path
            await state.update_data(keys_path=kpath, keys_text="")
            await state.set_state(BotStates.m5_journal)
            await ask_m5_journal(message)
        except Exception as e:
            logger.error(f"Mode 5 Keys PDF error: {e}")
            await message.answer("❌ PDF kalitni ochishda xatolik yuz berdi. Rasm yuboring.")
    else:
        await message.answer("Iltimos, kalitni rasm yoki matn ko‘rinishida yuboring.")

@dp.message(BotStates.m5_keys, F.photo)
async def mode5_keys_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    kpath = f"temp/m5_k_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=kpath)
    await state.update_data(keys_path=kpath, keys_text="")

    await state.set_state(BotStates.m5_journal)
    await ask_m5_journal(message)

async def ask_m5_journal(message: types.Message):
    msg_text = (
        "✅ **To‘g‘ri javoblar kaliti qabul qilindi!**\n\n"
        "📍 **3-QADAM (4 tadan): eMaktab elektron jurnali faylini yoki rasmini yuboring**\n"
        "*(Excel .xlsx, skrinshot fotosurati yoki PDF formatida)*\n\n"
        "📊 **JURNAL UCHUN NAMUNA (Qanday moslashtiriladi?):**\n"
        "• Bot har bir o‘quvchining darsdagi baholari o‘rtachasini (1-10 ballik) hisoblaydi;\n"
        "• 50 ballik BSB bahosi shunga qatʼiy moslanadi:\n"
        "  - **9–10 baho (A'lo):** ➔ **43 dan 50 ballgacha**\n"
        "  - **7–8 baho (Yaxshi):** ➔ **33 dan 42 ballgacha** (50 yozgan bo‘lsa ham shubhali ko‘chirish deb 33-42 ga tushiriladi)\n"
        "  - **5–6 baho (Qoniqarli):** ➔ **15 dan 32 ballgacha**\n"
        "  - **1–4 baho (Qoniqarsiz):** ➔ **0 dan 12 ballgacha**\n\n"
        "📸 _Iltimos, eMaktab jurnali Excel faylini yoki fotosuratini yuboring:_"
    )
    await message.answer(msg_text, reply_markup=get_action_keyboard(), parse_mode="Markdown")

@dp.message(BotStates.m5_journal, F.document)
async def mode5_journal_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    os.makedirs("temp", exist_ok=True)
    ext = ".xlsx" if fname.endswith(".xlsx") else (".xls" if fname.endswith(".xls") else ".pdf")
    jpath = f"temp/m5_j_{message.from_user.id}_{message.message_id}{ext}"
    await bot.download(message.document, destination=jpath)

    status_j = await message.answer("⏳ Jurnal o‘qilmoqda va o‘quvchilar o‘rtacha baholari hisoblanmoqda...")
    try:
        averages = await ai_service.parse_journal_averages(jpath)
        await state.update_data(journal_path=jpath, journal_averages=averages)
        await status_j.delete()
        await state.set_state(BotStates.m5_works)
        await message.answer(f"✅ Jurnaldan {len(averages)} nafar o‘quvchining dars o‘rtacha baholari aniqlandi!")
        await ask_m5_works(message)
    except Exception as e:
        logger.error(f"Mode 5 Journal parse error: {e}")
        await status_j.edit_text("❌ Jurnalni o‘qishda xatolik yuz berdi. Iltimos, Excel yoki aniq rasm yuboring.")

@dp.message(BotStates.m5_journal, F.photo)
async def mode5_journal_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    jpath = f"temp/m5_j_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=jpath)

    status_j = await message.answer("⏳ Jurnal skrinshoti o‘qilmoqda...")
    try:
        averages = await ai_service.parse_journal_averages(jpath)
        await state.update_data(journal_path=jpath, journal_averages=averages)
        await status_j.delete()
        await state.set_state(BotStates.m5_works)
        await message.answer(f"✅ Jurnaldan {len(averages)} nafar o‘quvchining dars o‘rtacha baholari aniqlandi!")
        await ask_m5_works(message)
    except Exception as e:
        logger.error(f"Mode 5 Journal photo error: {e}")
        await status_j.edit_text("❌ Jurnal rasmini o‘qishda xatolik yuz berdi. Excel formatda yuborish tavsiya etiladi.")

async def ask_m5_works(message: types.Message):
    msg_text = (
        "📍 **4-QADAM (4 tadan): O‘quvchilarning daftardagi yozma ishlari rasmlarini yuboring**\n"
        "*(Barcha o‘quvchilar rasmlarini birin-ketin yoki bitta umumiy PDF faylda yuborishingiz mumkin)*\n\n"
        "📝 **O‘QUVCHI ISHI UCHUN NAMUNA:**\n"
        "• O‘quvchi daftari yoki toza oq qog‘ozga yozgan BSB yozma ishi;\n"
        "• Varaq yuqorisida **o‘quvchining ismi va familiyasi** aniq ko‘rinsin.\n\n"
        "📸 _Daftarlar rasmlarini birin-ketin yuboravering. Barchasini yuborib bo‘lgach, pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing:_"
    )
    await message.answer(msg_text, reply_markup=get_action_keyboard(show_finish=True), parse_mode="Markdown")

@dp.message(BotStates.m5_works, F.document)
async def mode5_works_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m5_w_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            images = pdf_to_images(pdf_path)
            data = await state.get_data()
            wlist = data.get("works_paths", [])
            wlist.extend(images)
            await state.update_data(works_paths=wlist)
            ikb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🚀 Hisobotni tayyorlash ({len(wlist)} ta ish)", callback_data="m5_finish_now")]
            ])
            await message.answer(
                f"📥 PDF dan {len(images)} ta sahifa qo‘shildi (Jami ishlar: {len(wlist)} ta).\n\n"
                f"• Yana ishlar bo‘lsa, yuboravering;\n"
                f"• Tayyor bo‘lsa, pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing!",
                reply_markup=ikb,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Mode 5 Works PDF error: {e}")
            await message.answer("❌ PDF faylni ochishda xatolik yuz berdi.")
    else:
        await message.answer("Iltimos, o‘quvchi ishlarini rasm yoki PDF ko‘rinishida yuboring.")

@dp.message(BotStates.m5_works, F.photo)
async def mode5_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    wpath = f"temp/m5_w_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=wpath)

    data = await state.get_data()
    wlist = data.get("works_paths", [])
    wlist.append(wpath)
    await state.update_data(works_paths=wlist)

    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚀 Hisobotni tayyorlash ({len(wlist)} ta ish)", callback_data="m5_finish_now")],
        [InlineKeyboardButton(text="⚡ Faqat shu 1 ta rasmni tekshirish", callback_data="m5_single_image_process")]
    ])
    await message.answer(
        f"📥 **{len(wlist)}-o‘quvchi ishi qabul qilindi.**\n\n"
        f"• Yana ishlar bo‘lsa, rasmlarini yuboravering;\n"
        f"• BSB hisobotini chiqarish uchun pastdagi **'🚀 Hisobotni tayyorlash'** tugmasini bosing!",
        reply_markup=ikb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "m5_single_image_process")
async def cb_m5_single(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    wlist = data.get("works_paths", [])
    if not wlist:
        cpath = data.get("criteria_path", "")
        if cpath:
            await state.update_data(works_paths=[cpath])
    await callback.answer("⏳ BSB bahoga moslab tekshirish boshlanmoqda...")
    await mode5_finish(callback.message, state, user_id=callback.from_user.id, username=callback.from_user.username)

@dp.callback_query(F.data == "m5_finish_now")
async def cb_m5_finish(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏳ BSB hisoboti tayyorlanmoqda...")
    await mode5_finish(callback.message, state, user_id=callback.from_user.id, username=callback.from_user.username)

@dp.message(BotStates.m5_works, F.text.lower().in_(["tayyor", "tayyorla", "tayyorlang", "boshla", "boshlang", "tekshir", "tekshiring", "bo'ldi", "boldi", "hisobot", "qil", "ha", "ok", "1"]))
@dp.message(BotStates.m5_works, F.text == "✅ Rasmlar tugadi, hisobotni tayyorlang!")
async def mode5_finish(message: types.Message, state: FSMContext, user_id: int = None, username: str = None):
    actual_user_id = user_id or (message.from_user.id if message.from_user else 0)
    actual_username = username or (message.from_user.username if message.from_user and message.from_user.username else str(actual_user_id))

    data = await state.get_data()
    cpath = data.get("criteria_path", "")
    kpath = data.get("keys_path", "")
    ktext = data.get("keys_text", "")
    wlist = data.get("works_paths", [])
    averages = data.get("journal_averages", {})

    if not wlist:
        await message.answer("Iltimos, avval kamida bitta o‘quvchi ishi rasmini yuboring.")
        return

    is_text_key = bool(ktext)
    keys_input = ktext if is_text_key else kpath

    status_msg = await message.answer(f"⏳ **Tekshirish boshlandi!**\n\n{len(wlist)} nafar o‘quvchining daftardagi ishlari dars o‘rtacha baholariga moslanib tekshirilmoqda...")

    async def update_progress(text):
        try:
            await status_msg.edit_text(text)
        except:
            pass

    async def send_batch_works_results(batch_students, current_count, total_count):
        if not batch_students:
            return
        lines = [f"📋 **Tekshirildi ({current_count}/{total_count}-o‘quvchilar):**"]
        for st in batch_students:
            tr = st.get("tr", "")
            name = st.get("name", "O‘quvchi")
            score = st.get("total_score", 0)
            note = st.get("note", "Tekshirildi")
            lines.append(f"{tr}. 👤 **{name}** — **{score} ball**\n   📝 _Tahlil: {note}_")
        txt = "\n\n".join(lines)
        try:
            await message.answer(txt, parse_mode="Markdown")
        except Exception:
            await message.answer(txt)

    try:
        parsed = await ai_service.evaluate_student_works(
            cpath, wlist,
            progress_callback=update_progress,
            batch_callback=send_batch_works_results,
            keys_input=keys_input,
            is_text_key=is_text_key,
            journal_averages=averages,
            is_adjusted=True
        )
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{actual_user_id}_{cname}_bsb_bahoga_moslangan.xlsx"
        build_bsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_BSB_bahoga_moslangan_hisobot.xlsx")
        cap = (
            f"🎉 **{cname} sinf BSB ishlari darsdagi baholarga to‘liq moslashtirildi va hisobot tayyorlandi!**\n"
            f"• 9–10 baho ➔ 43–50 ball\n"
            f"• 7–8 baho ➔ 33–42 ball\n"
            f"• 5–6 baho ➔ 15–32 ball\n"
            f"• Har bir o‘quvchi bo‘yicha batafsil tahlil hisobot oxirgi ustunida yozildi."
            f"{FEEDBACK_NOTE}"
        )
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(actual_user_id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Bahoga moslangan BSB: {cname} | @{actual_username}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(actual_user_id, credit_type, admin_id=ADMIN_ID)
        await state.clear()
    except Exception as e:
        logger.error(f"Mode 5 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")


# ==================== 6-REJIM: CHSB BAHOGA MOSLASH (JURNALDAN O'QUVCHI ISHISIZ) ====================

@dp.message(F.text.contains("6️⃣ CHSB (Bahoga moslash)"))
@dp.message(F.text.contains("CHSB (Bahoga moslash)"))
async def mode6_start(message: types.Message, state: FSMContext):
    can_proceed, credit_type = await check_access_and_notify(message)
    if not can_proceed:
        return

    await state.clear()
    await state.update_data(credit_type=credit_type, journal_averages={})
    await state.set_state(BotStates.m6_select_grade_or_custom)

    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 9-sinf (O‘zbek)", callback_data="chsb_adj_pick_9"),
            InlineKeyboardButton(text="🇷🇺 9-класс (Русский)", callback_data="chsb_adj_pick_9_ru")
        ],
        [
            InlineKeyboardButton(text="🇺🇿 10-sinf (O‘zbek)", callback_data="chsb_adj_pick_10"),
            InlineKeyboardButton(text="🇷🇺 10-класс (Русский)", callback_data="chsb_adj_pick_10_ru")
        ],
        [
            InlineKeyboardButton(text="🇺🇿 11-sinf (O‘zbek)", callback_data="chsb_adj_pick_11"),
            InlineKeyboardButton(text="🇷🇺 11-класс (Русский)", callback_data="chsb_adj_pick_11_ru")
        ],
        [InlineKeyboardButton(text="🔄 Boshqa sinf / O‘z mezoningizni kiritish", callback_data="chsb_adj_pick_custom")]
    ])
    msg_text = (
        "📊 **CHSB HISOBOTINI DARSDAGI BAHOGA MOSLASH (1-CHORAK)**\n\n"
        "Fan: **Informatika va axborot texnologiyalari (O‘zbek sinf)**\n\n"
        "💡 **Ushbu rejimda o‘quvchilar test varaqalarini yuklash SHART EMAS!**\n"
        "Faqat eMaktab jurnali (Excel, PDF yoki skrinshot) yuklasangiz kifoya — tizim darsdagi baholarga qarab har bir o‘quvchiga mos CHSB ballini (B-Q-M bo‘yicha) va qaysi savollardan adashganini hisobotga chiqarib beradi.\n\n"
        "🏛 **9, 10 va 11-sinf original test mezonlari** tizimda tayyor mavjud!\n\n"
        "📢 _Boshqa fanlar (Tarix, Ona tili, Ingliz tili, Matematika, Biologiya...) uchun ham maxsus mezonlarni agentga qo‘shib beramiz: @Obidbek1988_\n\n"
        "Quyidagilardan birini tanlang:"
    )
    await message.answer(msg_text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data.in_(["chsb_adj_pick_9", "chsb_adj_pick_10", "chsb_adj_pick_11", "chsb_adj_pick_9_ru", "chsb_adj_pick_10_ru", "chsb_adj_pick_11_ru"]))
async def cb_chsb_adj_pick(callback: CallbackQuery, state: FSMContext):
    data_str = callback.data.replace("chsb_adj_pick_", "")
    is_ru = "_ru" in data_str
    grade_code = data_str.replace("_ru", "")
    lang = "ru" if is_ru else "uz"
    chsb_info = get_chsb_for_grade(grade_code, lang=lang)
    if not chsb_info:
        await callback.answer("Ma'lumot topilmadi.")
        return

    crit_summary = (
        f"📋 **MEZON VA BALLAR TAQSIMOTI ({chsb_info['max_score']} ball):**\n"
        f"{chsb_info['distribution_summary']}\n\n"
        f"🔢 **1 dan 15 gacha savollar bo‘yicha taqsimot:**\n"
        f"`{chsb_info['bqm_compact']}`\n\n"
        f"🔑 **TO‘G‘RI JAVOBLAR KALITI:**\n"
        f"`{chsb_info['keys']}`"
    )
    await state.update_data(
        grade=grade_code,
        lang=lang,
        criteria_text=crit_summary,
        criteria_path="",
        keys_text=chsb_info["keys"],
        pdf_path=chsb_info.get("pdf_path", "")
    )

    card_text = (
        f"📚 **{chsb_info['title']} (O‘zbek sinf)**\n"
        f"🏛 _{chsb_info['agency']}_\n"
        f"📋 **1-CHORAK 1-CHSB MEZONI VA KALITI**\n"
        f"Jami: **{chsb_info['total_questions']} ta test — {chsb_info['max_score']} ball**\n\n"
        f"{crit_summary}\n\n"
        f"Tasdiqlaysizmi yoki o‘zgartirmoqchimisiz?"
    )

    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Original test PDF faylini ko‘rish", callback_data="m6_show_test_pdf")],
        [InlineKeyboardButton(text="✅ Shu mezon va kalitni tasdiqlash", callback_data="m6_confirm_all")],
        [InlineKeyboardButton(text="✏️ Mezon yoki kalitni tahrirlash", callback_data="m6_edit_all")],
        [InlineKeyboardButton(text="🔄 Boshqa mezon yuklash", callback_data="chsb_adj_pick_custom")]
    ])
    await callback.answer()
    await callback.message.edit_text(card_text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "m6_show_test_pdf")
async def cb_m6_show_test_pdf(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    grade = data.get("grade", "9")
    pdf_path = data.get("pdf_path", "") or f"assets/{grade}_sinf_informatika_chsb1_original.pdf"
    if os.path.exists(pdf_path):
        doc = FSInputFile(pdf_path, filename=f"{grade}_sinf_Informatika_1_CHSB_Original_Test.pdf")
        await callback.message.answer_document(
            doc,
            caption=f"📄 **{grade}-sinf Informatika 1-CHSB Original test varianti (Markaz testi, 15 ta savol)**",
            parse_mode="Markdown"
        )
        await callback.answer("PDF yuborildi.")
    else:
        await callback.answer("Fayl topilmadi.", show_alert=True)

@dp.callback_query(F.data == "m6_edit_all")
async def cb_m6_edit_all(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.m6_edit_all_input)
    await callback.answer()
    msg = (
        "✏️ **MEZON YOKI KALITNI TAHRIRLASH:**\n\n"
        "O‘zingiz istagan kalitni (yoki mezonni) yozib yuboring:\n"
        "Masalan:\n"
        "`1-A, 2-B, 3-C, 4-D, 5-A, 6-B, 7-C, 8-D, 9-A, 10-B, 11-C, 12-D, 13-A, 14-B, 15-C`\n\n"
        "*(Bekor qilish uchun: '❌ Bekor qilish')*"
    )
    await callback.message.answer(msg, parse_mode="Markdown")

@dp.message(BotStates.m6_edit_all_input, F.text)
async def mode6_edit_all_handler(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.lower() in ["❌ bekor qilish", "bekor qilish", "/cancel", "cancel"]:
        await state.set_state(BotStates.m6_select_grade_or_custom)
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    await state.update_data(keys_text=text)
    msg = (
        f"✅ **O‘zgartirishlar saqlandi:**\n\n"
        f"🔑 Kalit:\n`{text}`\n\n"
        f"Tasdiqlab, jurnallarni yuklash bosqichiga o‘tasizmi?"
    )
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash va davom etish", callback_data="m6_confirm_all")],
        [InlineKeyboardButton(text="✏️ Qayta tahrirlash", callback_data="m6_edit_all")]
    ])
    await message.answer(msg, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "chsb_adj_pick_custom")
async def cb_chsb_adj_pick_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.m6_criteria)
    await callback.answer()
    msg = (
        "📋 **O‘Z MEZONINGIZ VA KALITINGIZNI KIRITISH:**\n\n"
        "Boshqa fan yoki sinf uchun mezon va kalitni matn, rasm yoki PDF ko‘rinishida yuboring:\n"
        "*(Bekor qilish uchun: '❌ Bekor qilish')*"
    )
    await callback.message.answer(msg, reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    ), parse_mode="Markdown")

@dp.message(BotStates.m6_criteria, F.text)
async def mode6_custom_criteria_text(message: types.Message, state: FSMContext):
    if message.text.lower() in ["❌ bekor qilish", "bekor qilish", "/cancel", "cancel"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    crit_text = message.text.strip()
    await state.update_data(criteria_text=crit_text, keys_text="1-A, 2-B, 3-C, 4-D, 5-A, 6-B, 7-C, 8-D, 9-A, 10-B, 11-C, 12-D, 13-A, 14-B, 15-C")
    await ask_m6_journal(message, state)

@dp.callback_query(F.data == "m6_confirm_all")
async def cb_m6_confirm_all(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Mezon va kalit tasdiqlandi!")
    await ask_m6_journal(callback.message, state)

async def ask_m6_journal(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.m6_journal)
    msg = (
        "✅ **CHSB Mezoni va Kaliti tasdiqlandi!**\n\n"
        "📍 **KEYINGI QADAM: Endi eMaktab jurnalini yuboring**\n"
        "*(Excel .xlsx / .xls, PDF yoki jurnal skrinshotini yuborishingiz mumkin)*\n\n"
        "💡 **Afzalligi:** eMaktabdan Excel fayl yuklasangiz 1 soniyada 100% aniq o‘qiladi!\n\n"
        "⚡ Jurnal yuklanishi bilan, tizim o‘quvchilarning dars baholariga moslab 40 ballik CHSB ballarini taqsimlaydi va qaysi savollardan adashganini hisobotning izoh ustuniga avtomatik yozib beradi."
    )
    ikb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )
    try:
        await message.edit_text(msg, parse_mode="Markdown")
        await message.answer("Jurnal faylini yuboring 👇", reply_markup=ikb)
    except Exception:
        await message.answer(msg, reply_markup=ikb, parse_mode="Markdown")

@dp.message(BotStates.m6_journal, F.document)
async def mode6_journal_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    os.makedirs("temp", exist_ok=True)
    jpath = f"temp/m6_j_{message.from_user.id}_{message.message_id}_{message.document.file_name}"
    await bot.download(message.document, destination=jpath)

    status_msg = await message.answer("⏳ **Jurnal o‘qilmoqda va dars baholariga mos CHSB hisoboti tayyorlanmoqda...**")
    try:
        # 1. Parse averages & class name using universal parser
        detected_cname, averages = await ai_service.parse_journal_data(jpath)
        if not averages:
            await status_msg.edit_text("❌ Jurnaldan o‘quvchilar va ularning baholarini o‘qib bo‘lmadi. Iltimos, eMaktab jurnali faylini to‘g‘ri formatda yuboring.")
            return

        import re
        cname_match = re.search(r"(\d+[-_]?[a-zA-Zа-яА-Я]*)", message.document.file_name or "")
        if detected_cname == "9-sinf" and cname_match:
            detected_cname = cname_match.group(1).upper().replace("_", "-") 

        # 3. Generate instant report from averages
        data = await state.get_data()
        lang = data.get("lang", "uz")
        report_data = ai_service.generate_chsb_report_from_averages(averages, class_name=detected_cname, lang=lang)

        out_excel = f"temp/{message.from_user.id}_{detected_cname}_chsb_bahoga_moslangan.xlsx"
        build_chsb_excel(report_data, out_excel)

        doc = FSInputFile(out_excel, filename=f"{detected_cname}_CHSB_bahoga_moslangan_hisobot.xlsx")
        cap = (
            f"🎉 **{detected_cname} sinf o‘quvchilari darsdagi baholariga to‘liq moslashtirildi va CHSB test hisoboti tayyorlandi!**\n\n"
            f"• 👥 **Jami o‘quvchilar:** {len(averages)} nafar\n"
            f"• 9–10 baho ➔ 35–40 ball (A'lo)\n"
            f"• 7–8 baho ➔ 27–34 ball (Yaxshi)\n"
            f"• 5–6 baho ➔ 13–26 ball (Qoniqarli)\n"
            f"• Har bir o‘quvchi qoshida qaysi savollardan adashgani va to‘g‘ri bajargani hisobotda aniq yozilgan."
            f"{FEEDBACK_NOTE}"
        )
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Bahoga moslangan CHSB: {detected_cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()

        data = await state.get_data()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
        await state.clear()
    except Exception as e:
        logger.error(f"Mode 6 Doc Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")

@dp.message(BotStates.m6_journal, F.photo)
async def mode6_journal_photo(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    jpath = f"temp/m6_j_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=jpath)

    status_msg = await message.answer("⏳ **Jurnal fotosurati tahlil qilinmoqda va CHSB hisoboti tayyorlanmoqda...**")
    try:
        detected_cname, averages = await ai_service.parse_journal_data(jpath)
        if not averages:
            await status_msg.edit_text("❌ Jurnal fotosuratidan baholarni aniqlab bo‘lmadi. eMaktabdan Excel formatida yuklash tavsiya etiladi.")
            return

        data = await state.get_data()
        lang = data.get("lang", "uz")
        report_data = ai_service.generate_chsb_report_from_averages(averages, class_name=detected_cname, lang=lang)
        cname = detected_cname

        out_excel = f"temp/{message.from_user.id}_{cname}_chsb_bahoga_moslangan.xlsx"
        build_chsb_excel(report_data, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_CHSB_bahoga_moslangan_hisobot.xlsx")
        cap = (
            f"🎉 **{cname} o‘quvchilari darsdagi baholariga to‘liq moslashtirildi va CHSB hisoboti tayyorlandi!**\n\n"
            f"• 👥 **Jami o‘quvchilar:** {len(averages)} nafar\n"
            f"• 9–10 baho ➔ 35–40 ball\n"
            f"• 7–8 baho ➔ 27–34 ball\n"
            f"• 5–6 baho ➔ 13–26 ball\n"
            f"• Har bir o‘quvchi qoshida to‘g‘ri/xatolar hisobotda ko‘rsatilgan."
            f"{FEEDBACK_NOTE}"
        )
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(message.from_user.id), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Bahoga moslangan CHSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()

        data = await state.get_data()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
        await state.clear()
    except Exception as e:
        logger.error(f"Mode 6 Photo Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")


# ==================== ADMIN UCHUN MAXSUS BUYRUQLAR ====================
@dp.message(Command("admin"))
@dp.message(Command("baza"))
@dp.message(F.text.contains("Baza va Statistika"))
@dp.message(F.text.lower().in_(["/admin", "/baza", "baza"]))
async def admin_dashboard_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    import sqlite3
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users;")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE free_trial_used = 1;")
    used_trials = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(total_generated) FROM users;")
    total_gen = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM transactions WHERE status = 'approved';")
    approved_tx = cursor.fetchone()[0]

    conn.close()

    vips = db_service.get_vip_users()
    vip_count = len(vips)

    admin_msg = (
        f"📊 **BOTNING BAZA VA MOLIYA STATISTIKASI:**\n\n"
        f"👥 **Jami o‘qituvchilar:** {total_users} nafar\n"
        f"🌟 **VIP mijozlar:** {vip_count} nafar (/viplist)\n"
        f"🎁 **Sinovdan foydalanganlar:** {used_trials} nafar\n"
        f"📑 **Jami yaratilgan hisobotlar:** {total_gen} ta\n"
        f"💰 **Tasdiqlangan to‘lovlar:** {approved_tx} ta\n"
        f"💵 **Tushum (taxminan):** {approved_tx * 5000:,} so‘m\n\n"
        f"💡 **Admin boshqaruvi:**\n"
        f"• Balans to‘ldirish: Menyudagi **'💳 Balans to‘ldirish (Admin)'**\n"
        f"• VIP qo‘shish: `/addvip <user_id>`\n"
        f"• VIP o‘chirish: `/delvip <user_id>`\n"
        f"• VIP ro‘yxati: `/viplist`\n\n"
        f"Pastdagi tugma orqali butun bazani Excel qilib yuklab olishingiz mumkin:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Baza (Excel)ni yuklab olish", callback_data="export_db_excel")]
    ])
    await message.answer(admin_msg, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "export_db_excel")
async def export_db_to_excel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return

    await callback.answer("⏳ Excel tayyorlanmoqda...", show_alert=False)

    try:
        import sqlite3, openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        try:
            db_service.restore_from_github()
        except Exception:
            pass

        os.makedirs("temp", exist_ok=True)
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()

        wb = openpyxl.Workbook()
        ws_u = wb.active
        ws_u.title = "Foydalanuvchilar"

        headers_u = [
            "Telegram ID", "Username", "F.I.O (Ism-Familiya)", 
            "Bepul sinov", "Mavjud balans (sinf)", "Jami hisobotlar", "Ro‘yxatdan o‘tgan sana"
        ]
        ws_u.append(headers_u)

        cursor.execute("SELECT user_id, username, full_name, free_trial_used, balance_classes, total_generated, created_at FROM users ORDER BY created_at DESC;")
        for row in cursor.fetchall():
            uid, uname, fname, trial, bal, total_gen, cdate = row
            trial_text = "Ishlatilgan (0)" if trial else "Mavjud (1 ta)"
            ws_u.append([
                str(uid),
                f"@{uname}" if uname and not str(uname).startswith("@") else (uname or ""),
                fname or "",
                trial_text,
                f"{bal} ta sinf",
                total_gen,
                str(cdate)
            ])

        ws_t = wb.create_sheet(title="To‘lovlar Tarixi")
        headers_t = ["Tranzaksiya ID", "User ID", "Tasdiqlangan sinflar", "Holat", "Sana"]
        ws_t.append(headers_t)
        cursor.execute("SELECT id, user_id, amount_classes, status, created_at FROM transactions ORDER BY created_at DESC;")
        for row in cursor.fetchall():
            tid, uid, amt, status, cdate = row
            status_map = {"approved": "Tasdiqlangan", "rejected": "Rad etilgan", "pending": "Kutilmoqda"}
            ws_t.append([
                f"№{tid}",
                str(uid),
                f"+{amt} sinf",
                status_map.get(status, status),
                str(cdate)
            ])

        conn.close()

        # Rasmiy, toza va professional dizayn (rang-barang emas, jiddiy va o'qishga oson)
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
        white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin", color="D3D3D3"),
            right=Side(style="thin", color="D3D3D3"),
            top=Side(style="thin", color="D3D3D3"),
            bottom=Side(style="thin", color="D3D3D3")
        )

        for ws in [ws_u, ws_t]:
            ws.views.sheetView[0].showGridLines = True
            ws.row_dimensions[1].height = 28
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            for row_idx in range(2, ws.max_row + 1):
                ws.row_dimensions[row_idx].height = 22
                row_fill = zebra_fill if row_idx % 2 == 0 else white_fill
                for col_idx in range(1, ws.max_column + 1):
                    cell = ws.cell(row=row_idx, column=col_idx)
                    cell.border = thin_border
                    cell.fill = row_fill
                    if col_idx in [1, 4, 5, 6, 7]:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")

            for col in ws.columns:
                max_len = 0
                for cell in col:
                    val_str = str(cell.value or "")
                    if len(val_str) > max_len:
                        max_len = len(val_str)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 5, 16)

        export_path = "temp/Bot_Baza_Hisoboti.xlsx"
        wb.save(export_path)

        doc = FSInputFile(export_path, filename="Bot_Foydalanuvchilar_va_To‘lovlar_Bazasi.xlsx")
        await callback.message.answer_document(doc, caption="📊 **Barcha hisob-kitoblar va o‘qituvchilar bazasi (Excel shaklida):**", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Export Excel Error: {e}", exc_info=True)
        await callback.message.answer(f"❌ Xatolik yuz berdi: {str(e)}")

@dp.message(Command("addbalance"))
async def cmd_add_balance(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) >= 3:
        try:
            target_uid = int(parts[1])
            count = int(parts[2])
            db_service.add_classes_balance(target_uid, count)
            user = db_service.get_or_create_user(target_uid)
            await message.answer(f"✅ User `{target_uid}` hisobiga **+{count} sinf** qo‘shildi!\nYangi balansi: **{user.get('balance_classes', 0)} ta sinf**", parse_mode="Markdown")
        except Exception as err:
            await message.answer(f"Xatolik: {err}")
    else:
        await message.answer("ℹ️ Qo‘llash: `/addbalance <user_id> <sinflar_soni>`\nMasalan: `/addbalance 6580113791 10`", parse_mode="Markdown")

@dp.message(Command("setbalance"))
async def cmd_set_balance(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) >= 3:
        try:
            target_uid = int(parts[1])
            count = int(parts[2])
            import sqlite3
            conn = sqlite3.connect("bot_database.db")
            c = conn.cursor()
            c.execute("UPDATE users SET balance_classes = ? WHERE user_id = ?", (count, target_uid))
            conn.commit()
            conn.close()
            db_service.trigger_cloud_sync()
            await message.answer(f"✅ User `{target_uid}` balansi **{count} ta sinf** qilib belgilandi!", parse_mode="Markdown")
        except Exception as err:
            await message.answer(f"Xatolik: {err}")
    else:
        await message.answer("ℹ️ Qo‘llash: `/setbalance <user_id> <sinflar_soni>`\nMasalan: `/setbalance 6580113791 10`", parse_mode="Markdown")

@dp.message(Command("reloadbaza"))
async def cmd_reload_baza(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    db_service.restore_from_github()
    user = db_service.get_or_create_user(ADMIN_ID)
    await message.answer(f"✅ Baza GitHub Cloud'dan yangilandi!\nSizning balansingiz: **{user.get('balance_classes', 0)} ta sinf**", parse_mode="Markdown")



# ==================== ADMIN: VIP BOSHQARUVI (TUGMA VA INTERAKTIV MENYU) ====================

async def build_vip_management_message():
    vips = db_service.get_vip_users()
    if not vips:
        text = (
            "👑 **VIP MIJOZLAR BOSHQARUVI (Admin)**\n\n"
            "Hozircha maxsus VIP mijozlar ro‘yxati bo‘sh.\n\n"
            "💡 _VIP qilingan foydalanuvchilarga barcha 6 ta BSB va CHSB imkoniyatlari to‘liq ochiladi._\n\n"
            "Yangi VIP qo‘shish uchun pastdagi tugmani bosing:"
        )
        ikb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Yangi VIP mijoz qo‘shish", callback_data="vip_add_start")],
            [InlineKeyboardButton(text="❌ Yopish", callback_data="vip_close")]
        ])
        return text, ikb

    lines = [f"👑 **VIP MIJOZLAR BOSHQARUVI (Admin)**\n\nJami VIP mijozlar: **{len(vips)} nafar**\n"]
    kb_rows = [
        [InlineKeyboardButton(text="➕ Yangi VIP mijoz qo‘shish", callback_data="vip_add_start")]
    ]
    for idx, uid in enumerate(vips, 1):
        u = db_service.get_or_create_user(uid)
        uname = f"@{u['username']}" if u.get("username") else "usernamesiz"
        fname = u.get("full_name") or "Ismsiz"
        bal = u.get("balance_classes", 0)
        lines.append(f"{idx}. 👤 **{fname}** ({uname})\n   🆔 `{uid}` | 💰 Balans: {bal} sinf")
        kb_rows.append([
            InlineKeyboardButton(text=f"❌ {fname[:14]} ({uid}) ni chiqarish", callback_data=f"vip_remove_{uid}")
        ])

    lines.append("\n💡 _Biror foydalanuvchini VIPdan chiqarish uchun uning yonidagi '❌ ... ni chiqarish' tugmasini bosing._")
    kb_rows.append([
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="vip_refresh"),
        InlineKeyboardButton(text="❌ Yopish", callback_data="vip_close")
    ])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb_rows)

@dp.message(F.text.contains("VIP Boshqaruvi (Admin)"))
@dp.message(Command("vipmenu"))
async def admin_vip_menu_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text, ikb = await build_vip_management_message()
    await message.answer(text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data == "vip_refresh")
async def cb_vip_refresh(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    text, ikb = await build_vip_management_message()
    try:
        await callback.message.edit_text(text, reply_markup=ikb, parse_mode="Markdown")
        await callback.answer("Ro‘yxat yangilandi.")
    except Exception:
        await callback.answer("O‘zgarish yo‘q.")

@dp.callback_query(F.data == "vip_close")
async def cb_vip_close(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@dp.callback_query(F.data == "vip_add_start")
async def cb_vip_add_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    await state.set_state(BotStates.admin_vip_add)
    await callback.answer()
    await callback.message.answer(
        "👑 **YANGI VIP MIJOZ QO‘SHISH:**\n\n"
        "Mijozning **Telegram ID** raqamini, **@username** ini yoki ism-familiyasini yozib yuboring:\n\n"
        "*(Bekor qilish uchun: '❌ Bekor qilish')*",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True
        ),
        parse_mode="Markdown"
    )

@dp.message(BotStates.admin_vip_add)
async def admin_vip_add_input(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    query = (message.text or "").strip()
    if query.lower() in ["/cancel", "cancel", "❌ bekor qilish", "bekor qilish"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    users = db_service.find_users(query, limit=5)
    if not users and query.isdigit():
        uid = int(query)
        u = db_service.get_or_create_user(uid)
        users = [u]

    if not users:
        await message.answer(
            f"❌ Bazada **'{query}'** bo‘yicha foydalanuvchi topilmadi.\n"
            f"Iltimos, Telegram ID raqamini aniqroq kiriting (masalan: `6580113791`):",
            parse_mode="Markdown"
        )
        return

    if len(users) == 1:
        u = users[0]
        uid = u["user_id"]
        db_service.add_vip_user(uid)
        await state.clear()
        name = u.get("full_name") or u.get("username") or str(uid)
        await message.answer(
            f"✅ **{name}** (`{uid}`) muvaffaqiyatli VIP ro‘yxatiga qo‘shildi!\n"
            f"Unga barcha 6 ta BSB va CHSB menyulari to‘liq ochildi.",
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )
        try:
            await bot.send_message(
                uid,
                "🎉 **Tabriklaymiz! Sizga admin tomonidan to‘liq imkoniyatlar (VIP) ochildi!**\n\n"
                "Endi siz BSB va CHSB bo‘yicha barcha 6 ta rejimdan bemalol foydalanishingiz mumkin:\n"
                "⬅️ BSB (Chap): 1️⃣ BSB (Ballar), 3️⃣ BSB (Ishlar), 5️⃣ BSB (Bahoga moslash)\n"
                "➡️ CHSB (O‘ng): 2️⃣ CHSB (Ballar), 4️⃣ CHSB (Testlar), 6️⃣ CHSB (Bahoga moslash)\n\n"
                "Pastdagi menyu yangilandi! 👇",
                reply_markup=get_main_keyboard(uid)
            )
        except Exception:
            pass

        text, ikb = await build_vip_management_message()
        await message.answer(text, reply_markup=ikb, parse_mode="Markdown")
    else:
        ikb_rows = []
        for u in users:
            uid = u["user_id"]
            uname = f"@{u['username']}" if u.get("username") else "ID"
            name = u.get("full_name") or uname
            ikb_rows.append([InlineKeyboardButton(text=f"👤 {name[:16]} ({uname})", callback_data=f"vip_pickadd_{uid}")])
        ikb_rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="vip_close")])
        await message.answer(
            f"🔍 Bir nechta foydalanuvchi topildi ({len(users)} ta). Birini tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=ikb_rows)
        )

@dp.callback_query(F.data.startswith("vip_pickadd_"))
async def cb_vip_pickadd(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    uid = int(callback.data.split("_")[2])
    db_service.add_vip_user(uid)
    await state.clear()
    u = db_service.get_or_create_user(uid)
    name = u.get("full_name") or u.get("username") or str(uid)

    await callback.answer("✅ VIP qo‘shildi!", show_alert=True)
    try:
        await bot.send_message(
            uid,
            "🎉 **Tabriklaymiz! Sizga botda to‘liq imkoniyatlar (VIP) ochildi!**\n\nMenyuingiz yangilandi! 👇",
            reply_markup=get_main_keyboard(uid)
        )
    except Exception:
        pass

    text, ikb = await build_vip_management_message()
    await callback.message.edit_text(text, reply_markup=ikb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("vip_remove_"))
async def cb_vip_remove(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    uid = int(callback.data.split("_")[2])
    db_service.remove_vip_user(uid)
    await callback.answer("❌ Foydalanuvchi VIP ro‘yxatidan chiqarildi!", show_alert=True)

    try:
        await bot.send_message(
            uid,
            "ℹ️ **Hisobingiz odatiy mijoz rejimiga o‘tkazildi.**\nSizga CHSB test hisobotlari xizmati mavjud.",
            reply_markup=get_main_keyboard(uid)
        )
    except Exception:
        pass

    text, ikb = await build_vip_management_message()
    try:
        await callback.message.edit_text(text, reply_markup=ikb, parse_mode="Markdown")
    except Exception:
        pass

# ==================== ADMIN: VIP BOSHQARUVI ====================

@dp.message(Command("addvip"))
@dp.message(Command("vip"))
async def cmd_add_vip(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    target_uid = None
    if len(parts) >= 2:
        try:
            target_uid = int(parts[1])
        except ValueError:
            await message.answer("❌ Noto‘g‘ri format! Foydalanuvchi ID raqamini kiriting.\nMasalan: `/addvip 123456789`", parse_mode="Markdown")
            return
    elif message.reply_to_message and message.reply_to_message.from_user:
        target_uid = message.reply_to_message.from_user.id

    if not target_uid:
        await message.answer("ℹ️ Qo‘llash:\n`/addvip <user_id>` yoki xabarga reply qilib `/addvip`\nMasalan: `/addvip 123456789`", parse_mode="Markdown")
        return

    success = db_service.add_vip_user(target_uid)
    if success:
        target_user = db_service.get_or_create_user(target_uid)
        name_str = target_user.get("full_name") or target_user.get("username") or str(target_uid)
        await message.answer(
            f"✅ **Foydalanuvchi VIP ro‘yxatiga muvaffaqiyatli qo‘shildi!**\n\n"
            f"👤 Foydalanuvchi: **{name_str}** (`{target_uid}`)\n"
            f"🔓 Unga barcha BSB va CHSB knopkalari (1, 2, 3, 4, 5, 6) ko‘rinadi.",
            parse_mode="Markdown"
        )
        try:
            await bot.send_message(
                target_uid,
                "🎉 **Tabriklaymiz! Sizga admin tomonidan to‘liq imkoniyatlar (VIP) ochildi!**\n\n"
                "Endi siz BSB va CHSB bo‘yicha barcha 6 ta rejimdan bemalol foydalanishingiz mumkin!\n"
                "⬅️ BSB (Chap): 1️⃣ BSB (Ballar), 3️⃣ BSB (Ishlar), 5️⃣ BSB (Bahoga moslash)\n"
                "➡️ CHSB (O‘ng): 2️⃣ CHSB (Ballar), 4️⃣ CHSB (Testlar), 6️⃣ CHSB (Bahoga moslash)\n\n"
                "Pastdagi menyu yangilandi! 👇",
                reply_markup=get_main_keyboard(target_uid)
            )
        except Exception as e:
            logger.info(f"Userga VIP xabari jo'natilmadi ({target_uid}): {e}")
    else:
        await message.answer("❌ VIP qo‘shishda xatolik yuz berdi.")

@dp.message(Command("delvip"))
@dp.message(Command("unvip"))
async def cmd_del_vip(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    target_uid = None
    if len(parts) >= 2:
        try:
            target_uid = int(parts[1])
        except ValueError:
            await message.answer("❌ Noto‘g‘ri format! Foydalanuvchi ID raqamini kiriting.\nMasalan: `/delvip 123456789`", parse_mode="Markdown")
            return
    elif message.reply_to_message and message.reply_to_message.from_user:
        target_uid = message.reply_to_message.from_user.id

    if not target_uid:
        await message.answer("ℹ️ Qo‘llash:\n`/delvip <user_id>` yoki xabarga reply qilib `/delvip`\nMasalan: `/delvip 123456789`", parse_mode="Markdown")
        return

    success = db_service.remove_vip_user(target_uid)
    if success:
        await message.answer(
            f"❌ **Foydalanuvchi `{target_uid}` VIP ro‘yxatidan chiqarildi.**\n"
            f"Unga endi faqat CHSB imkoniyatlari ko‘rinadi.",
            parse_mode="Markdown"
        )
        try:
            await bot.send_message(
                target_uid,
                "ℹ️ **Hisobingiz odatiy mijoz rejimiga o‘tkazildi.**\n"
                "Sizga CHSB hisobotlari bo‘yicha xizmatlar mavjud.",
                reply_markup=get_main_keyboard(target_uid)
            )
        except Exception:
            pass
    else:
        await message.answer("❌ VIP ro‘yxatidan o‘chirishda xatolik yuz berdi.")

@dp.message(Command("viplist"))
@dp.message(Command("viplar"))
async def cmd_vip_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    vips = db_service.get_vip_users()
    if not vips:
        await message.answer("ℹ️ Hozircha maxsus VIP mijozlar ro‘yxati bo‘sh.\n\nQo‘shish uchun: `/addvip <user_id>`", parse_mode="Markdown")
        return

    msg = f"🌟 **MAXSUS VIP MIJOZLAR RO‘YXATI ({len(vips)} nafar):**\n\n"
    for idx, uid in enumerate(vips, 1):
        user = db_service.get_or_create_user(uid)
        uname = f"@{user.get('username')}" if user.get("username") else "usernamesiz"
        fname = user.get("full_name") or "Noma'lum"
        bal = user.get("balance_classes", 0)
        msg += f"{idx}. **{fname}** ({uname})\n   🆔 `{uid}` | 💰 Balans: {bal} sinf\n   O‘chirish: `/delvip {uid}`\n\n"

    await message.answer(msg, parse_mode="Markdown")

# ==================== ADMIN: BALANS TO'LDIRISH TIZIMI ====================

async def show_user_topup_card(message: types.Message, u: dict):
    uid = u["user_id"]
    uname = f"@{u['username']}" if u.get("username") else "mavjud emas"
    name = u.get("full_name") or "Noma'lum"
    bal = u.get("balance_classes", 0)
    is_vip = db_service.is_vip_user(uid)
    vip_str = "🌟 VIP Mijoz (BSB va CHSB ochiq)" if is_vip else "👤 Odatiy mijoz (Faqat CHSB)"

    msg = (
        f"👤 **MIJOZ MA'LUMOTLARI:**\n\n"
        f"▫️ **Ism-Familiya:** {name}\n"
        f"▫️ **Telegram ID:** `{uid}`\n"
        f"▫️ **Username:** {uname}\n"
        f"▫️ **Mavjud balans:** **{bal} ta sinf**\n"
        f"▫️ **Status:** {vip_str}\n\n"
        f"➕ **Ushbu mijozga necha sinf qo‘shmoqchisiz?**\n"
        f"Pastdagi tezkor tugmalardan tanlang yoki ixtiyoriy raqam yozib yuboring (masalan: `15`):"
    )

    vip_btn_text = "🚫 VIPdan chiqarish" if is_vip else "🌟 VIP status berish"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="+1 sinf", callback_data=f"topupamt_{uid}_1"),
            InlineKeyboardButton(text="+2 sinf", callback_data=f"topupamt_{uid}_2"),
            InlineKeyboardButton(text="+5 sinf", callback_data=f"topupamt_{uid}_5")
        ],
        [
            InlineKeyboardButton(text="+10 sinf", callback_data=f"topupamt_{uid}_10"),
            InlineKeyboardButton(text="+20 sinf", callback_data=f"topupamt_{uid}_20"),
            InlineKeyboardButton(text="+50 sinf", callback_data=f"topupamt_{uid}_50")
        ],
        [
            InlineKeyboardButton(text=vip_btn_text, callback_data=f"togglevip_{uid}")
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="topup_cancel")
        ]
    ])
    await message.answer(msg, reply_markup=kb, parse_mode="Markdown")

async def ask_topup_confirmation(message: types.Message, uid: int, amount: int, state: FSMContext):
    u = db_service.get_or_create_user(uid)
    uname = f"@{u['username']}" if u.get("username") else "mavjud emas"
    name = u.get("full_name") or uname
    current_bal = u.get("balance_classes", 0)
    new_bal = current_bal + amount

    confirm_msg = (
        f"⚠️ **HISOB TO‘LDIRISHNI TASDIQLAYSIZMI?**\n\n"
        f"👤 **Mijoz:** {name} (`{uid}`)\n"
        f"➕ **Qo‘shilayotgan:** **+{amount} ta sinf**\n"
        f"💰 **Hozirgi balans:** {current_bal} ta sinf\n"
        f"📈 **Yangi balans:** **{new_bal} ta sinf** bo‘ladi.\n\n"
        f"✅ Tasdiqlasangiz, mijoz hisobiga sinflar darhol qo‘shiladi va unga shaxsiy xabar boradi."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data=f"confirmtopup_{uid}_{amount}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="topup_cancel")
        ]
    ])
    await message.answer(confirm_msg, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text.contains("Balans to‘ldirish (Admin)"))
@dp.message(Command("topup"))
@dp.message(Command("payuser"))
async def admin_topup_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(BotStates.admin_topup_select_user)
    
    ikb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 O‘z hisobimga sinf qo‘shish (Admin)", callback_data="adm_topup_self")]
    ])
    await message.answer(
        "💳 **HISOB TO‘LDIRISH (ADMIN BO‘LIMI)**\n\n"
        "Qaysi foydalanuvchining hisobiga sinf qo‘shmoqchisiz?\n"
        "Foydalanuvchining **Telegram ID** raqamini, **@username** ini yoki ismini yozing.\n\n"
        "💡 *O‘zingizning balansingizga sinf qo‘shish uchun pastdagi tugmani bosing:*",
        reply_markup=ikb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "adm_topup_self")
async def cb_adm_topup_self(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    u = db_service.get_or_create_user(ADMIN_ID, callback.from_user.username, callback.from_user.full_name)
    await state.update_data(target_uid=ADMIN_ID)
    await state.set_state(BotStates.admin_topup_enter_amount)
    await show_user_topup_card(callback.message, u)
    await callback.answer()

@dp.message(BotStates.admin_topup_select_user)
async def admin_topup_find_user(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    query = (message.text or "").strip()
    if query.lower() in ["/cancel", "cancel", "❌ bekor qilish", "bekor qilish"]:
        await state.clear()
        await message.answer("Hisob to‘ldirish bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    users = db_service.find_users(query, limit=6)

    # Agar ID son bo'lib bazada hali bo'lmasa, yaratib olish
    if not users and query.isdigit():
        uid = int(query)
        user = db_service.get_or_create_user(uid)
        users = [user]

    if not users:
        await message.answer(
            f"❌ Bazada **'{query}'** bo‘yicha hech qanday mijoz topilmadi.\n\n"
            f"Iltimos, Telegram ID raqamini (masalan: `6580113791`) yoki aniq @username ini yozing:\n"
            f"*(Bekor qilish uchun: '❌ Bekor qilish')*",
            parse_mode="Markdown"
        )
        return

    if len(users) == 1:
        u = users[0]
        await state.update_data(target_uid=u["user_id"])
        await state.set_state(BotStates.admin_topup_enter_amount)
        await show_user_topup_card(message, u)
    else:
        inline_kb = []
        for u in users:
            uid = u["user_id"]
            uname = f"@{u['username']}" if u.get("username") else "ID"
            name = u.get("full_name") or uname
            bal = u.get("balance_classes", 0)
            btn_text = f"👤 {name[:16]} ({uname}) - Balans: {bal}"
            inline_kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"seluser_{uid}")])
        inline_kb.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="topup_cancel")])

        await message.answer(
            f"🔍 Bir nechta mijoz topildi ({len(users)} ta). Birini tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb)
        )

@dp.message(BotStates.admin_topup_enter_amount)
async def admin_topup_amount_typed(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = (message.text or "").strip()
    if text.lower() in ["/cancel", "cancel", "❌ bekor qilish", "bekor qilish"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Iltimos, musbat son kiriting (masalan: `5` yoki `10`):", parse_mode="Markdown")
        return

    amount = int(text)
    data = await state.get_data()
    uid = data.get("target_uid")
    if not uid:
        await state.clear()
        await message.answer("Foydalanuvchi aniqlanmadi, qaytadan boshlang.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    await ask_topup_confirmation(message, uid, amount, state)

@dp.callback_query(F.data.startswith("seluser_"))
async def callback_select_user(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    uid = int(callback.data.split("_")[1])
    u = db_service.get_or_create_user(uid)
    await state.update_data(target_uid=uid)
    await state.set_state(BotStates.admin_topup_enter_amount)
    await callback.answer()
    await show_user_topup_card(callback.message, u)

@dp.callback_query(F.data.startswith("topupamt_"))
async def callback_topup_amount(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    parts = callback.data.split("_")
    uid = int(parts[1])
    amount = int(parts[2])
    await callback.answer()
    await ask_topup_confirmation(callback.message, uid, amount, state)

@dp.callback_query(F.data.startswith("togglevip_"))
async def callback_toggle_vip(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    uid = int(callback.data.split("_")[1])
    is_vip = db_service.is_vip_user(uid)
    if is_vip:
        db_service.remove_vip_user(uid)
        await callback.answer("Foydalanuvchi VIP ro'yxatidan chiqarildi!", show_alert=True)
    else:
        db_service.add_vip_user(uid)
        await callback.answer("Foydalanuvchi VIP ro'yxatiga qo'shildi!", show_alert=True)
        try:
            await bot.send_message(
                uid,
                "🎉 **Tabriklaymiz! Sizga admin tomonidan to‘liq imkoniyatlar (VIP) ochildi!**\n\n"
                "Endi BSB va CHSB bo‘yicha barcha rejimlardan bemalol foydalanishingiz mumkin! Menyuingiz yangilandi 👇",
                reply_markup=get_main_keyboard(uid)
            )
        except Exception:
            pass

    u = db_service.get_or_create_user(uid)
    await show_user_topup_card(callback.message, u)

@dp.callback_query(F.data == "topup_cancel")
async def callback_topup_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Bekor qilindi.")
    await callback.message.answer("❌ Hisob to‘ldirish bekor qilindi.", reply_markup=get_main_keyboard(callback.from_user.id))

@dp.callback_query(F.data.startswith("confirmtopup_"))
async def callback_confirm_topup(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Faqat admin uchun!", show_alert=True)
        return
    parts = callback.data.split("_")
    uid = int(parts[1])
    amount = int(parts[2])

    await state.clear()
    db_service.add_classes_balance(uid, amount)
    u = db_service.get_or_create_user(uid)
    new_bal = u.get("balance_classes", 0)
    name = u.get("full_name") or u.get("username") or str(uid)

    await callback.answer("✅ Muvaffaqiyatli to‘ldirildi!", show_alert=True)
    await callback.message.edit_text(
        f"✅ **HISOB TO‘LDIRILDI!**\n\n"
        f"👤 Mijoz: **{name}** (`{uid}`)\n"
        f"➕ Qo‘shildi: **+{amount} ta sinf**\n"
        f"💰 Yangi balans: **{new_bal} ta sinf**\n\n"
        f"Mijozga avtomatik bildirishnoma yuborildi.",
        parse_mode="Markdown"
    )
    await callback.message.answer("Asosiy menyu:", reply_markup=get_main_keyboard(callback.from_user.id))

    # Mijozga bildirishnoma
    try:
        user_kb = get_main_keyboard(uid)
        await bot.send_message(
            uid,
            f"🎉 **Hisobingiz to‘ldirildi!**\n\n"
            f"Admin tomonidan sizning hisobingizga **+{amount} ta sinf** qo‘shildi!\n"
            f"💰 Sizning jami balansingiz: **{new_bal} ta sinf**.\n\n"
            f"Marhamat, xizmatlardan foydalanishingiz mumkin! 👇",
            reply_markup=user_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.info(f"Userga to'lov xabari yuborilmadi ({uid}): {e}")

@dp.message(F.text == "✅ Rasmlar tugadi, hisobotni tayyorlang!")
async def fallback_finish_btn(message: types.Message, state: FSMContext):
    cur_state = await state.get_state()
    if not cur_state:
        await message.answer(
            "ℹ️ Sessiya muddati yakunlangan yoki bot yangilangan.\nIltimos, qaytadan boshlash uchun **/start** buyrug‘ini yuboring.",
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )

@dp.message(F.photo)
async def fallback_photo(message: types.Message, state: FSMContext):
    cur_state = await state.get_state()
    if not cur_state:
        await message.answer(
            "ℹ️ Iltimos, avval pastdagi menyudan kerakli bo‘limni tanlang (masalan: **4️⃣ CHSB (Testlarni tekshirish)** yoki **3️⃣ BSB (Ishlarni tekshirish)**), so‘ngra rasmlarni yuboring.",
            reply_markup=get_main_keyboard(message.from_user.id),
            parse_mode="Markdown"
        )

async def handle_ping(request):
    return web.Response(text="BSB & CHSB Hisobot Agent Telegram Bot is running 24/7!")

async def main():
    if not BOT_TOKEN:
        print("DIQQAT: .env faylida BOT_TOKEN ko'rsatilmagan!")
        return

    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health server port {port} da ishga tushdi.")

    logger.info("BSB va CHSB Hisobot Boti ishga tushmoqda...")
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message", "edited_message", "channel_post",
            "edited_channel_post", "callback_query",
            "my_chat_member", "chat_member"
        ]
    )

if __name__ == "__main__":
    asyncio.run(main())