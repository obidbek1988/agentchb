import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton

from config import BOT_TOKEN, ARCHIVE_CHANNEL_ID
from ai_service import ai_service
from queue_manager import queue_manager
from excel_service import build_bsb_excel, build_chsb_excel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# In-memory channel storage if updated dynamically
CURRENT_ARCHIVE_ID = ARCHIVE_CHANNEL_ID

def get_main_keyboard():
    kb = [
        [
            KeyboardButton(text="1️⃣ BSB (Ballar orqali)"),
            KeyboardButton(text="2️⃣ BSB (Ishlarni tekshirish)")
        ],
        [
            KeyboardButton(text="3️⃣ CHSB (Ballar orqali)"),
            KeyboardButton(text="4️⃣ CHSB (Testlarni tekshirish)")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_action_keyboard(show_finish: bool = False):
    kb = []
    if show_finish:
        kb.append([KeyboardButton(text="✅ Rasmlar tugadi, hisobotni tayyorlang!")])
    kb.append([KeyboardButton(text="❌ Bekor qilish")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

class BotStates(StatesGroup):
    m1_journal = State()
    m1_criteria = State()

    m2_criteria = State()
    m2_works = State()

    m3_journal = State()
    m3_criteria = State()

    m4_keys = State()
    m4_student_tests = State()

# Catch channel posts to auto-detect archive channel ID
@dp.channel_post()
async def handle_channel_post(message: types.Message):
    global CURRENT_ARCHIVE_ID
    CURRENT_ARCHIVE_ID = str(message.chat.id)
    logger.info(f"Avtomatik arxiv kanal ID aniqlandi: {CURRENT_ARCHIVE_ID}")

@dp.message(CommandStart())
@dp.message(F.text == "❌ Bekor qilish")
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
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

async def send_to_archive(doc_path: str, caption: str):
    global CURRENT_ARCHIVE_ID
    if CURRENT_ARCHIVE_ID:
        try:
            doc = FSInputFile(doc_path)
            await bot.send_document(CURRENT_ARCHIVE_ID, doc, caption=caption)
        except Exception as e:
            logger.warning(f"Arxiv kanalga jo'natilmadi: {e}")

# ==================== 1-REJIM: BSB BALLAR ORQALI ====================
@dp.message(F.text == "1️⃣ BSB (Ballar orqali)")
async def mode1_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.m1_journal)
    await message.answer(
        "📝 **1-REJIM: BSB (Ballar orqali hisobot)**\n\n"
        "1-qadam: **eMaktab elektron jurnali skrinshotini** (o‘quvchilar va ularning BSB ballari) yuboring:",
        reply_markup=get_action_keyboard()
    )

@dp.message(BotStates.m1_journal, F.photo)
async def mode1_journal(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    fpath = f"temp/m1_j_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=fpath)
    await state.update_data(journal_path=fpath)

    await state.set_state(BotStates.m1_criteria)
    await message.answer(
        "✅ Jurnal rasmi qabul qilindi!\n\n"
        "2-qadam: Ushbu BSB ning **Baholash mezoni skrinshotini** yuboring:",
        reply_markup=get_action_keyboard()
    )

@dp.message(BotStates.m1_criteria, F.photo)
async def mode1_criteria(message: types.Message, state: FSMContext):
    pos, eta = queue_manager.get_queue_info()
    queue_msg = f"⏳ Navbatdagi o‘rningiz: №{pos} (kutilmoqda: ~{eta}s)..." if pos > 1 else "⏳ BSB tahlil qilinmoqda..."
    status_msg = await message.answer(queue_msg)

    os.makedirs("temp", exist_ok=True)
    cpath = f"temp/m1_c_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=cpath)

    data = await state.get_data()
    jpath = data.get("journal_path")

    try:
        parsed = await ai_service.parse_bsb_data(jpath, cpath)
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_bsb.xlsx"
        build_bsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_1-BSB_hisobot.xlsx")
        cap = f"🎉 **{cname} sinf 1-BSB hisoboti tayyor!**\n• A4 Portret format\n• Ballar mezonlar bo‘yicha taqsimlangan"
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Yangi BSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Mode 1 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nIltimos, qaytadan urinib ko'ring.")
    finally:
        await state.clear()

# ==================== 2-REJIM: BSB ISHLARNI TEKSHIRISH ====================
@dp.message(F.text == "2️⃣ BSB (Ishlarni tekshirish)")
async def mode2_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.m2_criteria)
    await message.answer(
        "✍️ **2-REJIM: BSB o‘quvchilar ishini tekshirish**\n\n"
        "1-qadam: BSB **savollari va baholash mezonlari rasmini** yuboring:",
        reply_markup=get_action_keyboard()
    )

@dp.message(BotStates.m2_criteria, F.photo)
async def mode2_criteria(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    cpath = f"temp/m2_c_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=cpath)
    await state.update_data(criteria_path=cpath, works_paths=[])

    await state.set_state(BotStates.m2_works)
    await message.answer(
        "✅ Mezon qabul qilindi!\n\n"
        "2-qadam: Endi **o‘quvchilarning daftardagi/qog‘ozdagi ishlarining rasmlarini** yuboring (30 ta bo‘lsa ham ketma-ket yuboravering).\n\n"
        "Barcha rasmlarni yuborib bo‘lgach, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
        reply_markup=get_action_keyboard(show_finish=True)
    )

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

    try:
        parsed = await ai_service.evaluate_student_works(cpath, wlist, progress_callback=update_progress)
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_bsb_evaluated.xlsx"
        build_bsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_BSB_tekshirilgan_hisobot.xlsx")
        cap = f"🎉 **{cname} sinf o‘quvchilarining yozma ishlari to‘liq tekshirildi va BSB hisoboti tuzildi!**"
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Tekshirilgan BSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Mode 2 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
    finally:
        await state.clear()

# ==================== 3-REJIM: CHSB BALLAR ORQALI ====================
@dp.message(F.text == "3️⃣ CHSB (Ballar orqali)")
async def mode3_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.m3_journal)
    await message.answer(
        "📊 **3-REJIM: CHSB (Ballar orqali hisobot)**\n\n"
        "1-qadam: **eMaktab jurnali skrinshotini** (CHSB 40 ballik ustuni bilan) yuboring:",
        reply_markup=get_action_keyboard()
    )

@dp.message(BotStates.m3_journal, F.photo)
async def mode3_journal(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    fpath = f"temp/m3_j_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=fpath)
    await state.update_data(journal_path=fpath)

    await state.set_state(BotStates.m3_criteria)
    await message.answer(
        "✅ Jurnal qabul qilindi!\n\n"
        "2-qadam: Ushbu CHSB ning **Baholash mezoni skrinshotini** yuboring:",
        reply_markup=get_action_keyboard()
    )

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
        cap = f"🎉 **{cname} sinf CHSB hisoboti tayyor!**\n• (B) Bilish (6 ball), (Q) Qo‘llash (24 ball), (M) Mulohaza (10 ball) taqsimlangan."
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Yangi CHSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Mode 3 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
    finally:
        await state.clear()

# ==================== 4-REJIM: CHSB TESTLARNI TEKSHIRISH ====================
@dp.message(F.text == "4️⃣ CHSB (Testlarni tekshirish)")
async def mode4_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(BotStates.m4_keys)
    await message.answer(
        "🎯 **4-REJIM: CHSB Testlarni tekshirish va hisobot tuzish**\n\n"
        "1-qadam: Testning **to‘g‘ri javoblar kaliti va mezoni rasmini** yuboring:",
        reply_markup=get_action_keyboard()
    )

@dp.message(BotStates.m4_keys, F.photo)
async def mode4_keys(message: types.Message, state: FSMContext):
    os.makedirs("temp", exist_ok=True)
    kpath = f"temp/m4_k_{message.from_user.id}_{message.message_id}.jpg"
    await bot.download(message.photo[-1], destination=kpath)
    await state.update_data(keys_path=kpath, test_paths=[])

    await state.set_state(BotStates.m4_student_tests)
    await message.answer(
        "✅ Test kaliti qabul qilindi!\n\n"
        "2-qadam: Endi **o‘quvchilarning test javoblari varaqalari rasmlarini** yuboring (30 ta bo‘lsa ham ketma-ket yuboravering).\n\n"
        "Barchasini yuborib bo‘lgach, pastdagi **'✅ Rasmlar tugadi, hisobotni tayyorlang!'** tugmasini bosing:",
        reply_markup=get_action_keyboard(show_finish=True)
    )

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

    try:
        parsed = await ai_service.evaluate_test_answers(kpath, tlist, progress_callback=update_progress)
        cname = parsed.get("school_info", {}).get("class_name", "sinf")
        out_excel = f"temp/{message.from_user.id}_{cname}_chsb_test_report.xlsx"
        build_chsb_excel(parsed, out_excel)

        doc = FSInputFile(out_excel, filename=f"{cname}_CHSB_test_tekshirilgan.xlsx")
        cap = f"🎉 **{cname} sinf testlari to‘liq tekshirildi va CHSB hisoboti tayyorlandi!**"
        await message.answer_document(doc, caption=cap, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        await send_to_archive(out_excel, f"📁 Tekshirilgan Test CHSB: {cname} | @{message.from_user.username or message.from_user.id}")
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Mode 4 Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
    finally:
        await state.clear()

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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
