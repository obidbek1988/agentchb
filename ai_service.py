import os
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
    def _optimize_image(self, path: str) -> Optional[Image.Image]:
        if not path or not os.path.exists(path):
            return None
        try:
            img = Image.open(path)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            max_dim = 1600
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            logger.warning(f"Error optimizing image {path}: {e}")
            return Image.open(path)

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
    async def parse_bsb_data(self, journal_img_paths: Any, criteria_img_paths: Any) -> Dict[str, Any]:
        return await queue_manager.execute_task(
            self._call_bsb_vision, journal_img_paths, criteria_img_paths
        )

    async def parse_bsb_with_fixed_criteria(self, journal_img_paths: Any, fixed_criteria_info: Dict[str, Any]) -> Dict[str, Any]:
        return await queue_manager.execute_task(
            self._call_bsb_fixed_vision, journal_img_paths, fixed_criteria_info
        )

    def _call_bsb_fixed_vision(self, journal_img_paths: Any, fixed_criteria_info: Dict[str, Any]) -> Dict[str, Any]:
        criteria_list = fixed_criteria_info["criteria"]
        max_score = fixed_criteria_info["max_score"]
        crit_desc = "\n".join([f"Topshiriq {c['task_number']} (maks: {c['max_point']} ball): {c['skill_text']}" for c in criteria_list])

        j_list = journal_img_paths if isinstance(journal_img_paths, list) else [journal_img_paths]

        prompt = f"""
Siz umumta'lim maktablarining BSB hisobotlarini shakllantiruvchi yordamchisiz.
Yuborilgan {len(j_list)} ta rasm: eMaktab elektron jurnali skrinshotlari (o'quvchilar va ularning BSB ballari).
Agar sinfda o'quvchilar ko'p bo'lib 2 ta yoki undan ortiq rasm bo'lsa, ularni ketma-ket birlashtirib, tartib raqami (tr) bo'yicha bitta umumiy ro'yxat qiling!

Rasmiy Baholash mezonlari:
{crit_desc}
Maksimal umumiy ball: {max_score}

JUDA MUHIM QOIDALAR (BSB USTUNIDAN BALLARNI OLISH):
1. Chap ustun: O'quvchilarning To'liq ism-familiyasi.
2. O'rtadagi kundalik dars baholari (Dj ustunlari: 10, 9, 8...) va davomat (K, S) - BULAR BSB BALI EMAS!
3. DIQQAT BSB USTUNI: Jurnaldagi sanalar orasida yoki o'ngrog'ida 'BSB', '1-BSB' yoki 'BSB-1 [50 ball]' deb belgilangan alohida ustun bor (masalan: '17.10 BSB-1' yashil rangli katakchalar bilan).
Aynan shu ustundagi ballarni oling (masalan: 44, 35, 44, 43, 38, 44...)!
4. AGAR BITTA BSB USTUNI BO'SH BO'LSA, ALBATTA NARIGI BSB USTUNIGA QARANG! (Chunki 1-guruh va 2-guruh alohida ustunda bo'lishi mumkin, yoki sanasi boshqa bo'lishi mumkin). O'quvchining bali qaysi BSB ustunida bo'lsa, o'sha ustundagi ballni oling!
5. Har bir o'quvchi to'g'risidagi o'sha 'BSB' ustunidagi ballni 'total_score' ga aniq yozing.
6. Agar o'quvchida BSB bali bo'lsa (masalan 44, 35, 43...) -> total_score ga aynan o'sha sonni yozing! Faqat ikkala BSB ustunida ham ball bo'lmasa, total_score: null bo'ladi.

Quyidagi JSON formatida qaytaring:
{{
  "school_info": {{
    "class_name": "{fixed_criteria_info.get('class_name', '')}",
    "subject": "{fixed_criteria_info.get('subject', 'Informatika')}",
    "quarter": {fixed_criteria_info.get('quarter', 1)},
    "bsb_number": {fixed_criteria_info.get('bsb_number', 1)},
    "max_score": {max_score},
    "teacher_name": "Qobilov Obidjon",
    "head_teacher": "Mahmudova Dilfuzaxon"
  }},
  "students": [
    {{
      "tr": 1,
      "name": "O'quvchi F.I.O",
      "total_score": 44,
      "task_scores": [9, 9, 10, 7, 9]
    }}
  ]
}}
Javob FAQAT sof JSON bo'lsin.
"""
        res = self._send_prompt_to_gemini(prompt, j_list)
        res["criteria"] = criteria_list
        if "school_info" in res:
            res["school_info"]["max_score"] = max_score
            res["school_info"]["subject"] = fixed_criteria_info.get("subject", "Informatika")

        # Guarantee task_scores are accurately allocated in Python
        from emaktab_parser import distribute_score_to_tasks, clean_score
        for st in res.get("students", []):
            raw_tot = st.get("total_score")
            tot = clean_score(raw_tot)
            st["total_score"] = tot
            st["task_scores"] = distribute_score_to_tasks(tot, criteria_list)

        return res

    def _call_bsb_vision(self, journal_img_paths: Any, criteria_img_paths: Any) -> Dict[str, Any]:
        j_list = journal_img_paths if isinstance(journal_img_paths, list) else [journal_img_paths]
        c_list = criteria_img_paths if isinstance(criteria_img_paths, list) else [criteria_img_paths]

        prompt = f"""
Siz umumta'lim maktablarining BSB hisobotlarini shakllantiruvchi yordamchisiz.
Dastlabki {len(j_list)} ta rasm: eMaktab elektron jurnali skrinshotlari (barcha o'quvchilar va ularning BSB ballari).
Keyingi {len(c_list)} ta rasm: Rasmiy Baholash mezoni jadvali (ko'nikmalar matni va ajratilgan ballar, bir nechta sahifa bo'lishi mumkin).

JUDA MUHIM QOIDALAR (BSB USTUNIDAN BALLARNI OLISH):
1. Mezon rasmlaridagi barcha mezonlarni to'liq aniqlang (har doim Bosh harf bilan boshlansin, oxiriga '\\n\\nJami: X ball' yozilsin).
2. Jurnalda dars baholarini (Dj) EMAS, aynan 'BSB' / 'BSB-1' deb belgilangan ustundagi ballarni (masalan: 44, 35, 43, 38...) har bir o'quvchining 'total_score' siga oling!
3. AGAR BITTA BSB USTUNI BO'SH BO'LSA, ALBATTA NARIGI BSB USTUNIGA QARANG! O'quvchining bali qaysi BSB ustunida yozilgan bo'lsa, o'sha ustundagi ballni oling!
4. Agar o'quvchida BSB bali bo'lsa, 'total_score' ga aynan o'sha sonni yozing. Faqat ikkala BSB ustunida ham ball bo'lmasa, total_score: null bo'ladi.

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
      "tr": 1,
      "name": "Abdullayeva Muslimaxon",
      "total_score": null,
      "task_scores": [null, null, null, null, null]
    }},
    {{
      "tr": 2,
      "name": "Abdumannonova Lazizabonu",
      "total_score": 44,
      "task_scores": [10, 8, 9, 9, 8]
    }}
  ]
}}
Javob FAQAT sof JSON bo'lsin.
"""
        all_imgs = j_list + c_list
        res = self._send_prompt_to_gemini(prompt, all_imgs)

        # Guarantee task_scores are accurately allocated in Python
        from emaktab_parser import distribute_score_to_tasks, clean_score
        c_list_parsed = res.get("criteria", [])
        for st in res.get("students", []):
            raw_tot = st.get("total_score")
            tot = clean_score(raw_tot)
            st["total_score"] = tot
            if c_list_parsed:
                st["task_scores"] = distribute_score_to_tasks(tot, c_list_parsed)

        return res

    # 2-TUGMA: BSB o'quvchilar ishini tekshirish (BATCH PROCESSOR: 5 tadan bo'lib tekshiradi!)
    async def evaluate_student_works(self, criteria_img_path: str, work_img_paths: List[str], progress_callback: Optional[Callable] = None, batch_callback: Optional[Callable] = None, keys_input: str = "", is_text_key: bool = False) -> Dict[str, Any]:
        batch_size = 8
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

            res = await queue_manager.execute_task(self._call_eval_works_vision, criteria_img_path, batch, start_tr=i+1, keys_input=keys_input, is_text_key=is_text_key)
            if not final_info and "school_info" in res:
                final_info = res["school_info"]
            if not criteria_list and "criteria" in res:
                criteria_list = res["criteria"]

            new_students = res.get("students", [])
            all_students.extend(new_students)
            if batch_callback and new_students:
                try:
                    await batch_callback(new_students, current_count, total_works)
                except Exception as be:
                    logger.warning(f"Batch callback error: {be}")

            # Safe interval between batches
            await asyncio.sleep(0.5)

        return {
            "school_info": final_info,
            "criteria": criteria_list,
            "students": all_students
        }

    def _call_eval_works_vision(self, criteria_img_path: str, work_img_paths: List[str], start_tr: int = 1, keys_input: str = "", is_text_key: bool = False) -> Dict[str, Any]:
        all_imgs = []
        if criteria_img_path and os.path.exists(criteria_img_path):
            all_imgs.append(criteria_img_path)
            crit_desc = "1-rasm: BSB Baholash mezonlari (savollar va har bir topshiriq uchun maksimal ballar)."
        else:
            crit_desc = "BSB Baholash mezoni topshiriqlar bo'yicha mezon asosida."

        if keys_input:
            if is_text_key:
                key_desc = f"To'g'ri javoblar / yechimlar kaliti:\n{keys_input}"
            elif os.path.exists(keys_input):
                all_imgs.append(keys_input)
                key_desc = f"{len(all_imgs)}-rasm: To'g'ri javoblar va yechimlar kaliti."
            else:
                key_desc = f"To'g'ri javoblar / yechimlar: {keys_input}"
        else:
            key_desc = "To'g'ri javoblar mezon bilan birga keltirilgan."

        all_imgs.extend(work_img_paths)

        prompt = f"""
Siz tajribali o'qituvchisiz.
{crit_desc}
{key_desc}
Keyingi rasmlar: O'quvchilarning daftardagi yoki qog'ozdagi yozma ishlari.

Har bir o'quvchining ishini mezonga va to'g'ri javoblar kalitiga qarab tekshiring:
- O'quvchining ism-familiyasini aniqlang;
- Har bir topshiriq uchun to'g'riligiga qarab ball bering;
- Jami to'plagan ballini hisoblang;
- Har bir o'quvchi uchun QISQA TAHLIL (note) yozing: qaysi topshiriq to'g'ri, qaysi birida xato qilgani (masalan: "1-3 topshiriq to'liq, 4-topshiriqda xatolik (-2b)");
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
      "task_scores": [10, 8, 9, 8, 7],
      "note": "1-3 to'liq, 4-topshiriqda xatolik (-2b)"
    }}
  ]
}}
Javob FAQAT sof JSON bo'lsin.
"""
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

    # 4-TUGMA: CHSB Testlarni tekshirish (BATCH PROCESSOR: 4 tadan bo'lib xavfsiz tekshiradi!)
    async def evaluate_test_answers(self, keys_input: str, student_test_img_paths: List[str], progress_callback: Optional[Callable] = None, batch_callback: Optional[Callable] = None, is_text_key: bool = False, criteria_input: str = "", is_text_criteria: bool = False) -> Dict[str, Any]:
        batch_size = 10
        all_students = []
        final_info = {}

        total_tests = len(student_test_img_paths)
        for i in range(0, total_tests, batch_size):
            batch = student_test_img_paths[i:i + batch_size]
            current_count = min(i + batch_size, total_tests)
            if progress_callback:
                percent = int((current_count / total_tests) * 100)
                await progress_callback(f"⏳ Testlar tekshirilmoqda: {current_count} / {total_tests} ta o‘quvchi ({percent}%)...")

            res = await queue_manager.execute_task(self._call_eval_tests_vision, keys_input, batch, start_tr=i+1, is_text_key=is_text_key, criteria_input=criteria_input, is_text_criteria=is_text_criteria)
            if not final_info and "school_info" in res:
                final_info = res["school_info"]

            new_students = res.get("students", [])
            all_students.extend(new_students)
            if batch_callback and new_students:
                try:
                    await batch_callback(new_students, current_count, total_tests)
                except Exception as be:
                    logger.warning(f"Batch test callback error: {be}")

            await asyncio.sleep(0.5)

        return {
            "school_info": final_info,
            "students": all_students
        }

    def _call_eval_tests_vision(self, keys_input: str, student_test_img_paths: List[str], start_tr: int = 1, is_text_key: bool = False, criteria_input: str = "", is_text_criteria: bool = False) -> Dict[str, Any]:
        all_imgs = []

        # 1. Criteria description
        if criteria_input:
            if is_text_criteria:
                crit_desc = f"Baholash mezoni:\n{criteria_input}"
            elif os.path.exists(criteria_input):
                all_imgs.append(criteria_input)
                crit_desc = f"{len(all_imgs)}-rasm: CHSB Baholash mezoni jadvali."
            else:
                crit_desc = f"Baholash mezoni: {criteria_input}"
        else:
            crit_desc = "Standart CHSB mezoni (jami 15 ta test): (B) Bilish 1-5 savollar (6 ball), (Q) Qo'llash 6-12 savollar (24 ball), (M) Mulohaza 13-15 savollar (10 ball). Jami: 40 ball."

        # 2. Key description
        if is_text_key:
            key_desc = f"To'g'ri javoblar kaliti:\n{keys_input}"
        elif keys_input and os.path.exists(keys_input):
            all_imgs.append(keys_input)
            key_desc = f"{len(all_imgs)}-rasm: CHSB test savollarining to'g'ri javoblari kaliti (masalan: 1-A, 2-D, 3-C...)."
        else:
            key_desc = f"To'g'ri javoblar kaliti: {keys_input}"

        all_imgs.extend(student_test_img_paths)

        prompt = f"""
Siz test javoblarini tekshiruvchi mutaxassissiz.
{crit_desc}
{key_desc}
Keyingi rasmlar: O'quvchilarning belgilagan test javoblari varaqalari rasmlari.

Vazifangiz:
Har bir o'quvchining belgilagan javoblarini to'g'ri kalit va baholash mezoni bilan solishtirib tekshiring:
- O'quvchi F.I.O;
- To'g'ri topilgan testlar ballarini hisoblang: (B) Bilish, (Q) Qo'llash, (M) Mulohaza mezonlari bo'yicha ajrating;
- Jami to'plagan ballini hisoblang (maksimal 40 ball);
- Har bir o'quvchi uchun QISQA TAHLIL (note) yozing: nechta to'g'ri, nechta xato va qaysi savollarda adashgani (masalan: "12 to'g'ri, 3 xato (4, 9, 14-testlar)");
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
      "task_scores": [6, 20, 8],
      "note": "12 to'g'ri, 3 xato (4, 9, 14-testlar)"
    }}
  ]
}}
Javob FAQAT sof JSON bo'lsin.
"""
        return self._send_prompt_to_gemini(prompt, all_imgs)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            s = text.find("{")
            e = text.rfind("}")
            if s != -1 and e != -1:
                return json.loads(text[s:e+1])
            raise

    def _send_prompt_to_gemini(self, prompt: str, img_paths: List[str]) -> Dict[str, Any]:
        retries = 3
        last_error = None

        for attempt in range(retries):
            key = self._get_next_key()
            genai.configure(api_key=key, transport="rest")
            model = genai.GenerativeModel("gemini-3.5-flash")

            loaded_imgs = [self._optimize_image(p) for p in img_paths if p and os.path.exists(p)]
            loaded_imgs = [im for im in loaded_imgs if im is not None]
            content = [prompt] + loaded_imgs

            try:
                response = model.generate_content(content)
                txt = response.text.strip()
                return self._extract_json(txt)
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed with key ...{key[-4:]}: {e}")
                last_error = e
                import time
                time.sleep(2.0)

        raise RuntimeError(f"Gemini so'rovi bajarilmadi: {last_error}")

ai_service = AIService()
