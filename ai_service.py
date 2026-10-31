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

    async def parse_journal_data(self, journal_path: str) -> Tuple[str, Dict[str, float]]:
        """
        Universal eMaktab journal parser:
        Handles CSV, TSV, binary .xls (xlrd), real .xlsx (openpyxl), and Gemini Vision fallback for images/PDFs.
        Returns: (detected_class_name, {student_name: avg_grade})
        """
        if not journal_path or not os.path.exists(journal_path):
            return ("9-sinf", {})

        detected_cname = "9-sinf"
        res = {}

        # 1. Try reading as Text / CSV / TSV (eMaktab very often exports CSV with .xls extension)
        try:
            with open(journal_path, "rb") as f:
                raw_bytes = f.read(500000)

            for enc in ["utf-8-sig", "utf-8", "windows-1251", "cp1251", "latin1"]:
                try:
                    text = raw_bytes.decode(enc)
                    if "," in text or ";" in text or "\t" in text:
                        delim = "," if text.count(",") > text.count(";") else (";" if text.count(";") > text.count("\t") else "\t")
                        import csv, io
                        reader = csv.reader(io.StringIO(text), delimiter=delim)
                        for row in reader:
                            if not row:
                                continue
                            row_str = " ".join(row)
                            if "sinf:" in row_str.lower() and detected_cname == "9-sinf":
                                m = re.search(r"sinf:\s*([0-9]+-?[a-zA-Zа-яА-Я]+)", row_str, re.IGNORECASE)
                                if m:
                                    detected_cname = m.group(1).upper().replace("_", "-")

                            if len(row) >= 3:
                                col0 = row[0].strip()
                                col1 = row[1].strip()
                                if re.match(r"^[0-9]+(?:\.[0-9]+)?$", col0) and len(col1.split()) >= 2 and not any(k in col1.lower() for k in ["familiya", "f.i.o", "o'quvchi", "o‘quvchi"]):
                                    grades = []
                                    for val in row[3:]:
                                        v = val.strip().replace(",", ".")
                                        if re.match(r"^[0-9]+(?:\.[0-9]+)?$", v):
                                            num = float(v)
                                            if 1.0 <= num <= 50.0:
                                                grades.append(num)
                                    daily = [g for g in grades if g <= 10.0]
                                    if daily:
                                        avg = round(sum(daily) / len(daily), 1)
                                        res[col1] = avg
                        if len(res) >= 3:
                            return (detected_cname, res)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Text/CSV parse error: {e}")

        # 2. Try xlrd for binary .xls
        try:
            import xlrd
            book = xlrd.open_workbook(journal_path)
            sheet = book.sheet_by_index(0)
            for r in range(sheet.nrows):
                row_vals = [str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)]
                row_str = " ".join(row_vals)
                if "sinf:" in row_str.lower() and detected_cname == "9-sinf":
                    m = re.search(r"sinf:\s*([0-9]+-?[a-zA-Zа-яА-Я]+)", row_str, re.IGNORECASE)
                    if m:
                        detected_cname = m.group(1).upper().replace("_", "-")

                if len(row_vals) >= 3:
                    col0 = row_vals[0]
                    col1 = row_vals[1]
                    if re.match(r"^[0-9]+(?:\.[0-9]+)?$", col0) and len(col1.split()) >= 2 and not any(k in col1.lower() for k in ["familiya", "f.i.o", "o'quvchi", "o‘quvchi"]):
                        grades = []
                        for val in row_vals[3:]:
                            v = str(val).strip().replace(",", ".")
                            if re.match(r"^[0-9]+(?:\.[0-9]+)?$", v):
                                num = float(v)
                                if 1.0 <= num <= 50.0:
                                    grades.append(num)
                        daily = [g for g in grades if g <= 10.0]
                        if daily:
                            avg = round(sum(daily) / len(daily), 1)
                            res[col1] = avg
            if len(res) >= 3:
                return (detected_cname, res)
        except Exception:
            pass

        # 3. Try openpyxl for real .xlsx
        try:
            import openpyxl
            wb = openpyxl.load_workbook(journal_path, data_only=True)
            sheet = wb.active
            for r in range(1, sheet.max_row + 1):
                row_vals = [str(sheet.cell(r, c).value or "").strip() for c in range(1, min(sheet.max_column + 1, 35))]
                row_str = " ".join(row_vals)
                if "sinf:" in row_str.lower() and detected_cname == "9-sinf":
                    m = re.search(r"sinf:\s*([0-9]+-?[a-zA-Zа-яА-Я]+)", row_str, re.IGNORECASE)
                    if m:
                        detected_cname = m.group(1).upper().replace("_", "-")

                if len(row_vals) >= 2:
                    col0 = row_vals[0]
                    col1 = row_vals[1] if len(row_vals) > 1 else ""
                    name_candidate = col1 if len(col1.split()) >= 2 else col0
                    if len(name_candidate.split()) >= 2 and not any(k in name_candidate.lower() for k in ["familiya", "f.i.o", "o'quvchi", "o‘quvchi", "sinf", "tahlil"]):
                        grades = []
                        for c in range(2, min(sheet.max_column + 1, 35)):
                            val = sheet.cell(r, c).value
                            if val is not None:
                                try:
                                    s = str(val).replace(",", ".").strip()
                                    num = float(re.findall(r"^[0-9]+(?:\.[0-9]+)?", s)[0])
                                    if 1.0 <= num <= 50.0:
                                        grades.append(num)
                                except:
                                    pass
                        daily = [g for g in grades if g <= 10.0]
                        if daily:
                            avg = round(sum(daily) / len(daily), 1)
                            res[name_candidate] = avg
            if len(res) >= 3:
                return (detected_cname, res)
        except Exception:
            pass

        # 4. If image or PDF, fallback to Gemini Vision
        prompt = """
Ushbu eMaktab elektron jurnali sahifasidagi sinf nomi (masalan: 9-V yoki 9-A) va barcha o'quvchilarning ism-familiyasi hamda ularning darslardagi baholari o'rtachasini (1-10 ballik tizim bo'yicha) aniqlang.
Quyidagi JSON formatida qaytaring:
{
  "class_name": "9-V",
  "students": [
    {"name": "Erkayev Umidjon", "avg": 8.0},
    {"name": "Ibragimov Azizbek", "avg": 9.0}
  ]
}
Javob FAQAT sof JSON bo'lsin.
"""
        try:
            gem_res = await queue_manager.execute_task(self._send_prompt_to_gemini, prompt, [journal_path])
            if isinstance(gem_res, dict):
                detected_cname = gem_res.get("class_name") or detected_cname
                st_list = gem_res.get("students", [])
                for st in st_list:
                    if st.get("name"):
                        res[st["name"]] = float(st.get("avg", 7.0))
        except Exception as ge:
            logger.error(f"Gemini journal parse error: {ge}")

        return (detected_cname, res)

    async def parse_journal_averages(self, journal_path: str) -> Dict[str, float]:
        _, averages = await self.parse_journal_data(journal_path)
        return averages

    def generate_chsb_report_from_averages(self, journal_averages: Dict[str, float], class_name: str = "9-sinf") -> Dict[str, Any]:
        """
        Darsdagi baholarga qarab 40 ballik CHSB hisobotini o'quvchi ishisiz generatsiya qiladi.
        B: 6 ball (1, 4, 7-savollar)
        Q: 24 ball (2, 3, 5, 6, 8, 9, 10, 11, 12, 14-savollar)
        M: 10 ball (13, 15-savollar)
        """
        import random
        b_q = [1, 4, 7]
        q_q = [2, 3, 5, 6, 8, 9, 10, 11, 12, 14]
        m_q = [13, 15]

        students = []
        for idx, (name, avg_grade) in enumerate(journal_averages.items(), start=1):
            seed = sum(ord(ch) for ch in name) + idx
            rng = random.Random(seed)

            if avg_grade >= 9.0:
                # 5 baho (35 - 40 ball): 0 to 2 wrong
                num_wrong = rng.choice([0, 1, 1, 2])
                wrong_pool = q_q + m_q
                wrong = sorted(rng.sample(wrong_pool, num_wrong)) if num_wrong else []
                baho_num = 5
            elif avg_grade >= 7.0:
                # 4 baho (27 - 34 ball): 2 to 4 wrong
                num_wrong = rng.choice([2, 3, 3, 4])
                wrong_m = rng.choice([0, 1, 1])
                wrong = rng.sample(m_q, min(wrong_m, len(m_q)))
                rem = num_wrong - len(wrong)
                wrong += rng.sample(q_q, rem)
                wrong = sorted(wrong)
                baho_num = 4
            elif avg_grade >= 5.0:
                # 3 baho (13 - 26 ball): 6 to 9 wrong
                num_wrong = rng.choice([6, 7, 8, 9])
                wrong = rng.sample(m_q, 2) + rng.sample(b_q, 1) + rng.sample(q_q, num_wrong - 3)
                wrong = sorted(wrong)
                baho_num = 3
            else:
                # 2 baho (<13 ball): 10 to 12 wrong
                num_wrong = rng.choice([10, 11, 12])
                wrong = sorted(rng.sample(b_q + q_q + m_q, num_wrong))
                baho_num = 2

            b_score = sum(2.0 for q in b_q if q not in wrong)
            q_score = round(sum(2.4 for q in q_q if q not in wrong), 1)
            m_score = sum(5.0 for q in m_q if q not in wrong)
            total = round(b_score + q_score + m_score, 1)
            if total.is_integer():
                total = int(total)

            correct_count = 15 - len(wrong)
            if wrong:
                wrong_str = ', '.join(f'{w}' for w in wrong)
                note = f"Dars bahosi: {avg_grade} ({baho_num} baho). {correct_count} ta to‘g‘ri, {len(wrong)} ta xato ({wrong_str}-testlar)."
            else:
                note = f"Dars bahosi: {avg_grade} ({baho_num} baho). Barcha 15 ta test to‘g‘ri yechilgan (100%)."

            students.append({
                "tr": idx,
                "name": name,
                "total_score": total,
                "task_scores": [b_score, q_score, m_score],
                "note": note
            })

        return {
            "school_info": {
                "class_name": class_name,
                "subject": "Informatika",
                "quarter": 1,
                "chsb_number": 1,
                "max_score": 40,
                "teacher_name": "Qobilov Obidjon",
                "head_teacher": "Mahmudova Dilfuzaxon"
            },
            "students": students
        }

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
    async def evaluate_student_works(self, criteria_img_path: str, work_img_paths: List[str], progress_callback: Optional[Callable] = None, batch_callback: Optional[Callable] = None, keys_input: str = "", is_text_key: bool = False, journal_averages: Optional[Dict[str, float]] = None, is_adjusted: bool = False) -> Dict[str, Any]:
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

            res = await queue_manager.execute_task(self._call_eval_works_vision, criteria_img_path, batch, start_tr=i+1, keys_input=keys_input, is_text_key=is_text_key, journal_averages=journal_averages, is_adjusted=is_adjusted)
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

    def _call_eval_works_vision(self, criteria_img_path: str, work_img_paths: List[str], start_tr: int = 1, keys_input: str = "", is_text_key: bool = False, journal_averages: Optional[Dict[str, float]] = None, is_adjusted: bool = False) -> Dict[str, Any]:
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

        adj_desc = ""
        if is_adjusted and journal_averages:
            avg_lines = [f"• {name}: dars o'rtacha bahosi {score}" for name, score in list(journal_averages.items())[:35]]
            adj_desc = f"""
MUHIM VAZIFA — DARSDAGI O'RTACHA BAHOGA MOSLASHTIRISH:
O'quvchilarning eMaktab jurnali bo'yicha darslardagi o'rtacha baholari:
{chr(10).join(avg_lines)}

50 ballik BSB baholash qoidasi:
1) Jurnaldagi o'rtacha bahosi 9.0–10.0 (5 baho, a'lochi) bo'lsa -> BSB bali 43 dan 50 ballgacha berilsin;
2) Jurnaldagi o'rtacha bahosi 7.0–8.9 (4 baho, yaxshi) bo'lsa -> BSB bali 33 dan 42 ballgacha berilsin (agar o'quvchi 50 ballik yechgan bo'lsa ham, ko'chirish ehtimoli inobatga olinib 33-42 ball oralig'iga moslansin va izohda qaysi topshiriq xato qilingani yozilsin!);
3) Jurnaldagi o'rtacha bahosi 5.0–6.9 (3 baho, qoniqarli) bo'lsa -> BSB bali 15 dan 32 ballgacha berilsin;
4) Jurnaldagi o'rtacha bahosi 0–4.9 (2 baho, qoniqarsiz) bo'lsa -> BSB bali 0 dan 12 ballgacha berilsin.

Har bir o'quvchi uchun 'note' (Izoh) ustuniga:
"Dars o'rtachasi: X.X (Y baho). BSB bali: Z ballga moslashtirildi. 1-3 topshiriq to'liq, 4-topshiriq xato (-Kb) belgilandi."
"""

        prompt = f"""
Siz tajribali o'qituvchisiz.
{crit_desc}
{key_desc}
{adj_desc}
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
    async def evaluate_test_answers(self, keys_input: str, student_test_img_paths: List[str], progress_callback: Optional[Callable] = None, batch_callback: Optional[Callable] = None, is_text_key: bool = False, criteria_input: str = "", is_text_criteria: bool = False, journal_averages: Optional[Dict[str, float]] = None, is_adjusted: bool = False) -> Dict[str, Any]:
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

            res = await queue_manager.execute_task(self._call_eval_tests_vision, keys_input, batch, start_tr=i+1, is_text_key=is_text_key, criteria_input=criteria_input, is_text_criteria=is_text_criteria, journal_averages=journal_averages, is_adjusted=is_adjusted)
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

    def _call_eval_tests_vision(self, keys_input: str, student_test_img_paths: List[str], start_tr: int = 1, is_text_key: bool = False, criteria_input: str = "", is_text_criteria: bool = False, journal_averages: Optional[Dict[str, float]] = None, is_adjusted: bool = False) -> Dict[str, Any]:
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

        adj_desc = ""
        if is_adjusted and journal_averages:
            avg_lines = [f"• {name}: dars o'rtacha bahosi {score}" for name, score in list(journal_averages.items())[:35]]
            adj_desc = f"""
MUHIM VAZIFA — DARSDAGI O'RTACHA BAHOGA MOSLASHTIRISH:
O'quvchilarning eMaktab jurnali bo'yicha darslardagi o'rtacha baholari:
{chr(10).join(avg_lines)}

40 ballik CHSB (15 ta test) baholash qoidasi:
1) Jurnaldagi o'rtacha bahosi 9.0–10.0 (5 baho, a'lochi) bo'lsa -> CHSB bali 35 dan 40 ballgacha berilsin;
2) Jurnaldagi o'rtacha bahosi 7.0–8.9 (4 baho, yaxshi) bo'lsa -> CHSB bali 27 dan 34 ballgacha berilsin (agar 40 ball yechgan bo'lsa ham, ko'chirish ehtimoli inobatga olinib 27-34 ball oralig'iga moslansin va izohda qaysi testlar xato qilib ko'rsatilgani yozilsin!);
3) Jurnaldagi o'rtacha bahosi 5.0–6.9 (3 baho, qoniqarli) bo'lsa -> CHSB bali 13 dan 26 ballgacha berilsin;
4) Jurnaldagi o'rtacha bahosi 0–4.9 (2 baho, qoniqarsiz) bo'lsa -> CHSB bali 0 dan 12 ballgacha berilsin.

Har bir o'quvchi uchun 'note' (Izoh) ustuniga:
"Dars o'rtachasi: X.X (Y baho). CHSB bali: Z ballga moslashtirildi. N ta to'g'ri, M ta xato (falon testlar)."
"""

        prompt = f"""
Siz test javoblarini tekshiruvchi mutaxassissiz.
{crit_desc}
{key_desc}
{adj_desc}
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
