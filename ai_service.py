import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
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

    # 1-TUGMA: BSB ballar bo'yicha
    async def parse_bsb_data(self, journal_img_path: str, criteria_img_path: str) -> Dict[str, Any]:
        return await queue_manager.execute_task(
            self._call_bsb_vision, journal_img_path, criteria_img_path
        )

    def _call_bsb_vision(self, journal_img_path: str, criteria_img_path: str) -> Dict[str, Any]:
        prompt = """
Siz umumta'lim maktablarining BSB hisobotlarini shakllantiruvchi yordamchisiz.
1-rasm: eMaktab elektron jurnali skrinshoti (o'quvchilar va ularning BSB ballari).
2-rasm: Rasmiy Baholash mezoni jadvali (ko'nikmalar matni va ajratilgan ballar).

Quyidagi JSON formatida qaytaring:
{
  "school_info": {
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
      "skill_text": "Maʼlumot, axborot va bilimlar bazasi oʻrtasidagi farqlarni tushunadi;\\n\\nJami: 10 ball",
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
MUHIM:
1. Mezonlar har doim Bosh harf bilan boshlansin, oxiriga '\\n\\nJami: X ball' yozilsin.
2. Jurnaldagi 'total_score' mezonlarning 'max_point' lariga mos keladigan qilib 'task_scores' ga taqsimlansin (yig'indisi total_score ga teng bo'lsin).
3. Javob FAQAT sof JSON bo'lsin.
"""
        return self._send_prompt_to_gemini(prompt, [journal_img_path, criteria_img_path])

    # 2-TUGMA: BSB o'quvchilar ishini tekshirish (BATCH PROCESSOR: 5 tadan bo'lib tekshiradi!)
    async def evaluate_student_works(self, criteria_img_path: str, work_img_paths: List[str], progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        batch_size = 5
        all_students = []
        final_info = {}
        criteria_list = []

        total_works = len(work_img_paths)
        for i in range(0, total_works, batch_size):
            batch = work_img_paths[i:i + batch_size]
            current_count = min(i + batch_size, total_works)
            if progress_callback:
                percent = int((current_count / total_works) * 100)
                await progress_callback(f"⏳ Tekshirilmoqda: {current_count} / {total_works} ta o‘quvchi ({percent}%)...")

            res = await queue_manager.execute_task(self._call_eval_works_vision, criteria_img_path, batch, start_tr=i+1)
            if not final_info and "school_info" in res:
                final_info = res["school_info"]
            if not criteria_list and "criteria" in res:
                criteria_list = res["criteria"]

            all_students.extend(res.get("students", []))
            # Safe interval between batches
            await asyncio.sleep(1.0)

        return {
            "school_info": final_info,
            "criteria": criteria_list,
            "students": all_students
        }

    def _call_eval_works_vision(self, criteria_img_path: str, work_img_paths: List[str], start_tr: int = 1) -> Dict[str, Any]:
        prompt = f"""
Siz tajribali o'qituvchisiz.
1-rasm: BSB Baholash mezonlari (savollar, topshiriqlar va baholash mezonlari).
Keyingi rasmlar: O'quvchilarning daftardagi yoki qog'ozdagi yozma ishlari.

Har bir o'quvchining ishini mezonga qarab tekshiring:
- O'quvchining ism-familiyasini aniqlang;
- Har bir topshiriq uchun to'g'riligiga qarab ball bering;
- Jami to'plagan ballini hisoblang.
- Tartib raqamini (tr) {start_tr} dan boshlab bering.

Quyidagi JSON formatida qaytaring:
{{
  "school_info": {{
    "class_name": "10-B",
    "subject": "Informatika",
    "quarter": 1,
    "bsb_number": 1,
    "max_score": 50,
    "teacher_name": "Qobilov Obidjon",
    "head_teacher": "Mahmudova Dilfuzaxon"
  }},
  "criteria": [
    {{
      "task_number": 1,
      "skill_text": "Maʼlumot, axborot va bilimlar bazasi oʻrtasidagi farqlarni tushunadi;\\n\\nJami: 10 ball",
      "max_point": 10
    }}
  ],
  "students": [
    {{
      "tr": {start_tr},
      "name": "O'quvchi F.I.O",
      "total_score": 42,
      "task_scores": [10, 8, 9, 8, 7]
    }}
  ]
}}
Javob FAQAT sof JSON bo'lsin.
"""
        all_imgs = [criteria_img_path] + work_img_paths
        return self._send_prompt_to_gemini(prompt, all_imgs)

    # 3-TUGMA: CHSB ballar bo'yicha (B, Q, M mezonlari)
    async def parse_chsb_data(self, journal_img_path: str, criteria_img_path: str) -> Dict[str, Any]:
        return await queue_manager.execute_task(
            self._call_chsb_vision, journal_img_path, criteria_img_path
        )

    def _call_chsb_vision(self, journal_img_path: str, criteria_img_path: str) -> Dict[str, Any]:
        prompt = """
Siz CHSB hisobotini shakllantiruvchi yordamchisiz.
1-rasm: eMaktab elektron jurnali (CHSB 40 ballik ko'rsatilgan).
2-rasm: CHSB Baholash mezonlari.

CHSB odatda 3 ta mezondan iborat:
(B) - Bilish (6 ball)
(Q) - Qo'llash (24 ball)
(M) - Mulohaza (10 ball)
Jami: 40 ball.

O'quvchilarning 40 ballik jurnaldagi ballini ushbu 3 ta mezon [B, Q, M] ga to'g'ri taqsimlang.
Quyidagi JSON formatida qaytaring:
{
  "school_info": {
    "class_name": "6-G",
    "subject": "Informatika",
    "quarter": 2,
    "chsb_number": 2,
    "max_score": 40,
    "teacher_name": "Qobilov Obidjon",
    "head_teacher": "Mahmudova Dilfuzaxon"
  },
  "students": [
    {
      "tr": 1,
      "name": "Abduxalilova Ruxshona",
      "total_score": 36,
      "task_scores": [4, 22, 10]
    }
  ]
}
Javob FAQAT sof JSON bo'lsin.
"""
        return self._send_prompt_to_gemini(prompt, [journal_img_path, criteria_img_path])

    # 4-TUGMA: CHSB Testlarni tekshirish (BATCH PROCESSOR: 5 tadan bo'lib tekshiradi!)
    async def evaluate_test_answers(self, keys_img_path: str, student_test_img_paths: List[str], progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        batch_size = 5
        all_students = []
        final_info = {}

        total_tests = len(student_test_img_paths)
        for i in range(0, total_tests, batch_size):
            batch = student_test_img_paths[i:i + batch_size]
            current_count = min(i + batch_size, total_tests)
            if progress_callback:
                percent = int((current_count / total_tests) * 100)
                await progress_callback(f"⏳ Testlar tekshirilmoqda: {current_count} / {total_tests} ta o‘quvchi ({percent}%)...")

            res = await queue_manager.execute_task(self._call_eval_tests_vision, keys_img_path, batch, start_tr=i+1)
            if not final_info and "school_info" in res:
                final_info = res["school_info"]

            all_students.extend(res.get("students", []))
            await asyncio.sleep(1.0)

        return {
            "school_info": final_info,
            "students": all_students
        }

    def _call_eval_tests_vision(self, keys_img_path: str, student_test_img_paths: List[str], start_tr: int = 1) -> Dict[str, Any]:
        prompt = f"""
Siz test javoblarini tekshiruvchi mutaxassissiz.
1-rasm: CHSB test savollarining to'g'ri javoblari kaliti (masalan: 1-A, 2-D, 3-C...) va mezonlari.
Keyingi rasmlar: O'quvchilarning belgilagan test javoblari varaqalari (A, B, C, D).

Vazifangiz:
Har bir o'quvchining belgilagan javoblarini to'g'ri kalit bilan solishtirib tekshiring:
- O'quvchi F.I.O;
- To'g'ri topilgan testlar ballarini hisoblang: (B) Bilish, (Q) Qo'llash, (M) Mulohaza mezonlari bo'yicha ajrating;
- Jami to'plagan ballini hisoblang (maksimal 40 ball);
- Tartib raqami (tr) {start_tr} dan boshlansin.

Quyidagi JSON formatida qaytaring:
{{
  "school_info": {{
    "class_name": "6-G",
    "subject": "Informatika",
    "quarter": 2,
    "chsb_number": 2,
    "max_score": 40,
    "teacher_name": "Qobilov Obidjon",
    "head_teacher": "Mahmudova Dilfuzaxon"
  }},
  "students": [
    {{
      "tr": {start_tr},
      "name": "O'quvchi F.I.O",
      "total_score": 34,
      "task_scores": [6, 20, 8]
    }}
  ]
}}
Javob FAQAT sof JSON bo'lsin.
"""
        all_imgs = [keys_img_path] + student_test_img_paths
        return self._send_prompt_to_gemini(prompt, all_imgs)

    def _send_prompt_to_gemini(self, prompt: str, img_paths: List[str]) -> Dict[str, Any]:
        retries = 3
        last_error = None

        for attempt in range(retries):
            key = self._get_next_key()
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-3.8-flash")

            loaded_imgs = [Image.open(p) for p in img_paths]
            content = [prompt] + loaded_imgs

            try:
                response = model.generate_content(content)
                txt = response.text.strip()
                if txt.startswith("```json"):
                    txt = txt[7:]
                if txt.startswith("```"):
                    txt = txt[3:]
                if txt.endswith("```"):
                    txt = txt[:-3]

                return json.loads(txt.strip())
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed with key ...{key[-4:]}: {e}")
                last_error = e
                import time
                time.sleep(3.5)

        raise RuntimeError(f"Gemini so'rovi bajarilmadi: {last_error}")

ai_service = AIService()
