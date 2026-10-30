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
from criteria_store import get_criteria_for_grade, format_criteria_preview
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

def get_main_keyboard(is_admin: bool = False):
    kb = [
        [
            KeyboardButton(text="1️⃣ BSB (Ballar orqali)"),
            KeyboardButton(text="2️⃣ BSB (Ishlarni tekshirish)")
        ],
        [
            KeyboardButton(text="3️⃣ CHSB (Ballar orqali)"),
            KeyboardButton(text="4️⃣ CHSB (Testlarni tekshirish)")
        ],
        [
            KeyboardButton(text="💰 Hisobim / To‘lov qilish"),
            KeyboardButton(text="ℹ️ Narxlar va Yordam")
        ]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="📊 Baza va Statistika (Admin)")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

class BotStates(StatesGroup):
    m1_journal_fixed = State()
    m1_journal = State()
    m1_criteria = State()

    m2_criteria = State()
    m2_works = State()

    m3_journal = State()
    m3_criteria = State()

    m4_keys = State()
    m4_student_tests = State()

    waiting_for_receipt = State()

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
    await message.answer(msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")

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
        reply_markup=get_main_keyboard(),
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
            reply_markup=get_main_keyboard(),
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
            reply_markup=get_main_keyboard(),
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
    await message.answer(pay_msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")
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
    await message.answer(msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")

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
        reply_markup=get_main_keyboard(),
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
            reply_markup=get_main_keyboard(),
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
            reply_markup=get_main_keyboard(),
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
    await message.answer(pay_msg, reply_markup=get_main_keyboard(), parse_mode="Markdown")
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
    welcome_text = (
        "Assalomu alaykum! 🎓 **BSB va CHSB Hisobot Agentiga** xush kelibsiz.\n\n"
        "Quyidagi 4 ta imkoniyatdan birini tanlang:\n\n"
        "1️⃣ **BSB (Ballar orqali):** eMaktab jurnali va mezon rasmidan tayyor hisobot qilish.\n"
        "2️⃣ **BSB (Ishlarni tekshirish):** O‘quvchilar yozma ishlarini AI orqali tekshirib, ball qo‘yish va hisobot qilish.\n"
        "3️⃣ **CHSB (Ballar orqali):** eMaktab CHSB jurnali va mezoni bo‘yicha (B-Q-M) hisobot qilish.\n"
        "4️⃣ **CHSB (Testlarni tekshirish):** Test to‘g‘ri kaliti va o‘quvchi javoblari varaqasini tekshirib hisobot qilish."
    )
    is_admin = (message.from_user.id == ADMIN_ID)
    await message.answer(welcome_text, reply_markup=get_main_keyboard(is_admin=is_admin), parse_mode="Markdown")

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
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
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
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
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
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
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
@dp.message(F.text.contains("2️⃣ BSB (Ishlarni tekshirish)"))
@dp.message(F.text.contains("BSB (Ishlarni tekshirish)"))
async def mode2_start(message: types.Message, state: FSMContext):
    can_proceed, credit_type = await check_access_and_notify(message)
    if not can_proceed:
        return

    await state.clear()
    await state.update_data(credit_type=credit_type)
    await state.set_state(BotStates.m2_criteria)
    await message.answer(
        "✍️ **2-REJIM: BSB o‘quvchilar ishini tekshirish**\n\n"
        "1-qadam: BSB **savollari va baholash mezonlari rasmini yoki PDF faylini** yuboring:",
        reply_markup=get_action_keyboard(),
        parse_mode="Markdown"
    )

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
            await state.update_data(criteria_path=cpath, works_paths=[])
            await status_pdf.delete()
            await state.set_state(BotStates.m2_works)
            await message.answer(
                "✅ Mezon PDF qabul qilindi!\n\n"
                "2-qadam: Endi **o‘quvchilarning daftardagi/qog‘ozdagi ishlarining rasmlarini yoki PDF fayllarini** yuboring (ketma-ket yuboravering).\n\n"
                "Barchasini yuborib bo‘lgach, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
                reply_markup=get_action_keyboard(show_finish=True),
                parse_mode="Markdown"
            )
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
    await state.update_data(criteria_path=cpath, works_paths=[])

    await state.set_state(BotStates.m2_works)
    await message.answer(
        "✅ Mezon qabul qilindi!\n\n"
        "2-qadam: Endi **o‘quvchilarning daftardagi/qog‘ozdagi ishlarining rasmlarini yoki PDF fayllarini** yuboring (30 ta bo‘lsa ham ketma-ket yuboravering).\n\n"
        "Barcha rasmlarni yuborib bo‘lgach, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
        reply_markup=get_action_keyboard(show_finish=True),
        parse_mode="Markdown"
    )

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
            await message.answer(
                f"📥 PDF dan {len(images)} ta sahifa qo‘shildi (Jami ishlar: {len(wlist)} ta). Yana yuboring yoki 'Tayyorlang' tugmasini bosing.",
                reply_markup=get_action_keyboard(show_finish=True)
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

    await message.answer(f"📥 {len(wlist)}-o‘quvchi ishi qabul qilindi. Yana yuboring yoki 'Tayyorlang' tugmasini bosing.", reply_markup=get_action_keyboard(show_finish=True))

@dp.message(BotStates.m2_works, F.text == "✅ Rasmlar tugadi, hisobotni tayyorlang!")
async def mode2_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cpath = data.get("criteria_path")
    wlist = data.get("works_paths", [])

    if not wlist:
        await message.answer("Iltimos, avval kamida bitta o‘quvchi ishi rasmini yuboring.")
        return

    status_msg = await message.answer(f"⏳ Navbatga olindi. {len(wlist)} nafar o‘quvchining ishi 5 tadan bo‘lib xavfsiz tekshirilmoqda...")

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
            batch_callback=send_batch_works_results
        )
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_bsb_evaluated.xlsx"
        build_bsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_BSB_tekshirilgan_hisobot.xlsx")
        cap = f"🎉 **{cname} sinf o‘quvchilarining yozma ishlari to‘liq tekshirildi va BSB hisoboti tuzildi!**{FEEDBACK_NOTE}"
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Tekshirilgan BSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
    except Exception as e:
        logger.error(f"Mode 2 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")
    finally:
        await state.clear()

# ==================== 3-REJIM: CHSB BALLAR ORQALI ====================
@dp.message(F.text.contains("3️⃣ CHSB (Ballar orqali)"))
@dp.message(F.text.contains("CHSB (Ballar orqali)"))
async def mode3_start(message: types.Message, state: FSMContext):
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
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
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
            await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
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
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
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
async def mode4_start(message: types.Message, state: FSMContext):
    can_proceed, credit_type = await check_access_and_notify(message)
    if not can_proceed:
        return

    await state.clear()
    await state.update_data(credit_type=credit_type)
    await state.set_state(BotStates.m4_keys)
    await message.answer(
        "🎯 **4-REJIM: CHSB Testlarni tekshirish va hisobot tuzish**\n\n"
        "1-qadam: Testning **to‘g‘ri javoblar kaliti va mezoni rasmini yoki PDF faylini** yuboring:",
        reply_markup=get_action_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(BotStates.m4_keys, F.document)
async def mode4_keys_doc(message: types.Message, state: FSMContext):
    fname = (message.document.file_name or "").lower()
    if fname.endswith(".pdf"):
        os.makedirs("temp", exist_ok=True)
        pdf_path = f"temp/m4_k_pdf_{message.from_user.id}_{message.message_id}.pdf"
        await bot.download(message.document, destination=pdf_path)
        try:
            status_pdf = await message.answer("📄 Kalit/Mezon PDF qabul qilindi, o‘qilmoqda...")
            images = pdf_to_images(pdf_path)
            kpath = images[0] if images else pdf_path
            await state.update_data(keys_path=kpath, test_paths=[])
            await status_pdf.delete()
            await state.set_state(BotStates.m4_student_tests)
            await message.answer(
                "✅ Test kaliti PDF qabul qilindi!\n\n"
                "2-qadam: Endi **o‘quvchilarning test javoblari varaqalari rasmlarini yoki PDF fayllarini** yuboring (ketma-ket yuboravering).\n\n"
                "Barchasini yuborib bo‘lgach, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
                reply_markup=get_action_keyboard(show_finish=True),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Mode 4 Keys PDF error: {e}")
            await message.answer("❌ PDF faylni ochishda xatolik yuz berdi. Rasm ko‘rinishida yuboring.")
    else:
        await message.answer("Iltimos, test kalitini rasm yoki PDF formatida yuboring.")

@dp.message(BotStates.m4_keys, F.photo)
async def mode4_keys(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    kpath = f"temp/m4_k_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=kpath)
    await state.update_data(keys_path=kpath, test_paths=[])

    await state.set_state(BotStates.m4_student_tests)
    await message.answer(
        "✅ Test kaliti qabul qilindi!\n\n"
        "2-qadam: Endi **o‘quvchilarning test javoblari varaqalari rasmlarini yoki PDF fayllarini** yuboring (30 ta bo‘lsa ham ketma-ket yuboravering).\n\n"
        "Barchasini yuborib bo‘lgach, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
        reply_markup=get_action_keyboard(show_finish=True),
        parse_mode="Markdown"
    )

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
            await message.answer(
                f"📥 PDF dan {len(images)} ta sahifa qo‘shildi (Jami testlar: {len(tlist)} ta). Yana yuboring yoki 'Tayyorlang' tugmasini bosing.",
                reply_markup=get_action_keyboard(show_finish=True)
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

    data = await state.get_data()
    tlist = data.get("test_paths", [])
    tlist.append(tpath)
    await state.update_data(test_paths=tlist)

    await message.answer(f"📥 {len(tlist)}-o‘quvchi test varaqasi qabul qilindi. Yana yuboring yoki 'Tayyorlang' tugmasini bosing.", reply_markup=get_action_keyboard(show_finish=True))

@dp.message(BotStates.m4_student_tests, F.text == "✅ Rasmlar tugadi, hisobotni tayyorlang!")
async def mode4_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    kpath = data.get("keys_path")
    tlist = data.get("test_paths", [])

    if not tlist:
        await message.answer("Iltimos, avval kamida bitta o‘quvchi test javobi rasmini yuboring.")
        return

    status_msg = await message.answer(f"⏳ Navbatga olindi. {len(tlist)} nafar o‘quvchining testlari 5 tadan bo‘lib xavfsiz tekshirilmoqda...")

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
            kpath, tlist,
            progress_callback=update_progress,
            batch_callback=send_batch_test_results
        )
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_chsb_test_report.xlsx"
        build_chsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_CHSB_test_tekshirilgan.xlsx")
        cap = f"🎉 **{cname} sinf testlari to‘liq tekshirildi va CHSB hisoboti tayyorlandi!**{FEEDBACK_NOTE}"
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Tekshirilgan Test CHSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
        credit_type = data.get("credit_type", "paid")
        db_service.consume_credit(message.from_user.id, credit_type, admin_id=ADMIN_ID)
    except Exception as e:
        logger.error(f"Mode 4 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nSavollar uchun admin: @{ADMIN_USERNAME}")
    finally:
        await state.clear()

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

    admin_msg = (
        f"📊 **BOTNING BAZA VA MOLIYA STATISTIKASI:**\n\n"
        f"👥 **Jami o‘qituvchilar:** {total_users} nafar\n"
        f"🎁 **Sinovdan foydalanganlar:** {used_trials} nafar\n"
        f"📑 **Jami yaratilgan hisobotlar:** {total_gen} ta\n"
        f"💰 **Tasdiqlangan to‘lovlar:** {approved_tx} ta\n"
        f"💵 **Tushum (taxminan):** {approved_tx * 5000:,} so‘m\n\n"
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
