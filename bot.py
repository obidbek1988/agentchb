import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from config import BOT_TOKEN, ARCHIVE_CHANNEL_ID
from ai_service import ai_service
from excel_service import build_bsb_excel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class ReportStates(StatesGroup):
    waiting_for_journal = State()
    waiting_for_criteria = State()

@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "Assalomu alaykum! 🎓 **BSB Hisobot Agentiga** xush kelibsiz.\n\n"
        "Men sizga BSB tahlil hisobotini soniyalar ichida tayyor, formulalari bilan "
        "A4 Portret formatidagi **Excel (.xlsx)** fayl qilib beraman.\n\n"
        "Boshlash uchun: **eMaktab elektron jurnali skrinshotini** (o‘quvchilar va ularning ballari ko‘ringan) yuboring:"
    )
    await message.answer(welcome_text, parse_mode="Markdown")
    await state.set_state(ReportStates.waiting_for_journal)

@dp.message(Command("cancel"))
async def cancel_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Jarayon bekor qilindi. Boshlash uchun /start buyrug‘ini bosing.")

@dp.message(ReportStates.waiting_for_journal, F.photo)
async def handle_journal_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    
    file_path = os.path.join(temp_dir, f"journal_{message.from_user.id}_{message.message_id}.jpg")
    await bot.download(photo, destination=file_path)
    
    await state.update_data(journal_path=file_path)
    await message.answer(
        "✅ Jurnal skrinshoti qabul qilindi!\n\n"
        "Endi ushbu BSB ning **Baholash mezonlari skrinshotini** (yoki PDF sahifasi rasmini) yuboring:"
    )
    await state.set_state(ReportStates.waiting_for_criteria)

@dp.message(ReportStates.waiting_for_criteria, F.photo)
async def handle_criteria_photo(message: types.Message, state: FSMContext):
    status_msg = await message.answer("⏳ Rasm qabul qilindi. AI ko‘zi bilan tahlil qilinmoqda, kuting...")
    
    photo = message.photo[-1]
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    
    criteria_path = os.path.join(temp_dir, f"criteria_{message.from_user.id}_{message.message_id}.jpg")
    await bot.download(photo, destination=criteria_path)
    
    data = await state.get_data()
    journal_path = data.get("journal_path")
    
    try:
        await status_msg.edit_text("⏳ Navbatda: Mezonlar va ballar taqsimlanmoqda...")
        
        # Parse data using Gemini Vision
        parsed_data = await ai_service.parse_bsb_data(journal_path, criteria_path)
        
        await status_msg.edit_text("⏳ A4 Portret shaklda Excel (.xlsx) hisoboti tuzilmoqda...")
        
        class_name = parsed_data.get("school_info", {}).get("class_name", "sinf")
        output_filename = f"{class_name}_bsb_hisobot.xlsx".replace(" ", "_")
        excel_path = os.path.join(temp_dir, f"{message.from_user.id}_{output_filename}")
        
        build_bsb_excel(parsed_data, excel_path)
        
        # Send document to user
        doc = FSInputFile(excel_path, filename=output_filename)
        caption = (
            f"🎉 **{class_name} sinf BSB hisoboti tayyor!**\n\n"
            f"• A4 Portret (chop etishga tayyor)\n"
            f"• Formulalar (SUM, Foiz) to‘liq hisoblangan\n"
            f"• Imzolar joylashtirilgan\n\n"
            f"Yana boshqa hisobot qilish uchun /start bosing."
        )
        await message.answer_document(doc, caption=caption, parse_mode="Markdown")
        await status_msg.delete()
        
        # Optional: Send copy to Archive Channel
        if ARCHIVE_CHANNEL_ID:
            try:
                arch_caption = f"📁 Yangi hisobot: {class_name} | User: @{message.from_user.username or message.from_user.id}"
                await bot.send_document(ARCHIVE_CHANNEL_ID, doc, caption=arch_caption)
            except Exception as e:
                logger.warning(f"Arxiv kanalga jo'natib bo'lmadi: {e}")
                
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}\nIltimos, rasmlarni aniqroq qilib qaytadan yuboring (/start).")
    finally:
        await state.clear()
        # Clean up temp files
        for p in [journal_path, criteria_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

async def main():
    if not BOT_TOKEN:
        print("DIQQAT: .env faylida BOT_TOKEN ko'rsatilmagan!")
        return
    logger.info("BSB Hisobot Telegram Boti ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
