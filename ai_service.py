import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from PIL import Image

from config import GEMINI_KEYS
from queue_manager import queue_manager

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.keys = GEMINI_KEYS
        self.current_key_idx = 0

    def _get_next_key(self) -> str:
        if not self.keys:
            raise ValueError("GEMINI_API_KEYS sozlanmagan! .env faylga Gemini kalitini qo'shing.")
        key = self.keys[self.current_key_idx % len(self.keys)]
        self.current_key_idx += 1
        return key

    async def parse_bsb_data(self, journal_img_path: str, criteria_img_path: str) -> Dict[str, Any]:
        """
        Parses journal image and criteria image using Gemini Vision with rate-limit queue.
        Returns structured data for Excel generator.
        """
        return await queue_manager.execute_with_rate_limit(
            self._call_gemini_vision, journal_img_path, criteria_img_path
        )

    def _call_gemini_vision(self, journal_img_path: str, criteria_img_path: str) -> Dict[str, Any]:
        retries = 3
        last_error = None

        for attempt in range(retries):
            key = self._get_next_key()
            genai.configure(api_key=key)
            
            # Using Gemini 3.8 Flash model for fast multimodal vision
            model = genai.GenerativeModel("gemini-3.8-flash")

            prompt = """
Siz umumta'lim maktablarining BSB (Baholash sinov topshiriqlari) hisobotlarini shakllantiruvchi yordamchisiz.
Sizga 2 ta rasm berilmoqda:
1-rasm: eMaktab (Kundalik) elektron jurnali skrinshoti (o'quvchilar ro'yxati va ularning BSB ballari ko'rsatilgan).
2-rasm: Rasmiy Baholash mezoni jadvali (har bir topshiriq uchun baholanadigan ko'nikmalar matni va ajratilgan ballar).

Iltimos, ushbu ikki rasmni juda sinchiklab tahlil qiling va quyidagi JSON formatida aniq ma'lumot qaytaring:

{
  "school_info": {
    "title": "BSB tahlil Bayonnomasi\\nFARG‘ONA viloyati FARG‘ONA SHAHRI 26-umumta’lim maktabi",
    "class_name": "10-B",
    "subject": "Informatika",
    "quarter": 1,
    "bsb_number": 1,
    "max_score": 50,
    "teacher_name": "Qobilov Obidjon",
    "head_teacher": "Mahmudova Dilfuzaxon"
  },
  "criteria": [
    {
      "task_number": 1,
      "skill_text": "Maʼlumot, axborot va bilimlar bazasi oʻrtasidagi farqlarni tushunadi; Statik va dinamik maʼlumotlarni taʼriflay oladi; Axborotning sifatini tahlil qila oladi;\\n\\nJami: 10 ball",
      "max_point": 10
    }
  ],
  "students": [
    {
      "tr": 1,
      "name": "Abdullayeva Muslimaxon",
      "total_score": null,
      "task_scores": [null, null, null, null, null]
    },
    {
      "tr": 2,
      "name": "Abdumannonova Lazizabonu",
      "total_score": 44,
      "task_scores": [10, 8, 9, 9, 8]
    }
  ]
}

MUHIM QOIDALAR:
1. "criteria" ro'yxatida har bir topshiriqning mezoni Katta harf bilan boshlansin, oxiriga "\\n\\nJami: X ball" deb aniq balli yozilsin. Ortiqcha "1-topshiriq" deb boshlanmasin, to'g'ridan-to'g'ri ko'nikma matni yozilsin.
2. "students" ro'yxatida o'quvchining jurnaldagi umumiy BSB balli ("total_score") ma'lum bo'lsa, uni mezonlarning "max_point" lariga to'liq mos keladigan qilib "task_scores" 5 ta topshiriqqa mantiqiy taqsimlang (yig'indisi aynan "total_score" bo'lsin).
3. Agar o'quvchiga ball qo'yilmagan bo'lsa (qatnashmagan bo'lsa), "total_score": null va "task_scores": [null, null, null, null, null] bo'lsin.
4. Javobingiz FAQAT sof JSON bo'lsin, hech qanday markdown kod bloklarisiz (faqat { ... }).
"""

            try:
                img_journal = Image.open(journal_img_path)
                img_criteria = Image.open(criteria_img_path)
                
                response = model.generate_content([prompt, img_journal, img_criteria])
                txt = response.text.strip()
                if txt.startswith("```json"):
                    txt = txt[7:]
                if txt.startswith("```"):
                    txt = txt[3:]
                if txt.endswith("```"):
                    txt = txt[:-3]
                
                data = json.loads(txt.strip())
                return data
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed with key ...{key[-4:]}: {e}")
                last_error = e
                # Wait briefly before retry
                import time
                time.sleep(2.5)

        raise RuntimeError(f"Gemini so'rovi bajarilmadi. Oxirgi xato: {last_error}")

ai_service = AIService()
