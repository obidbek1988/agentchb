from cyrillic_translit import to_uzbek_latin
import os
import json
import logging
import asyncio
import re
from typing import List, Dict, Any, Optional, Callable, Tuple
import google.generativeai as genai
from PIL import Image, ImageOps

from config import GEMINI_KEYS
from queue_manager import queue_manager

logger = logging.getLogger(__name__)


def parse_bqm_string(text: str):
    """Parses text to determine which questions belong to B, Q, and M levels."""
    b_q, q_q, m_q = [], [], []
    lines = str(text).splitlines()
    for line in lines:
        l_low = line.lower()
        if any(k in l_low for k in ["bilish", "(b)", "[b]", "b:"]):
            b_q.extend([int(n) for n in re.findall(r'\b(\d+)\b', line)])
        elif any(k in l_low for k in ["qo‘llash", "qo'llash", "qollash", "(q)", "[q]", "q:"]):
            q_q.extend([int(n) for n in re.findall(r'\b(\d+)\b', line)])
        elif any(k in l_low for k in ["mulohaza", "(m)", "[m]", "m:"]):
            m_q.extend([int(n) for n in re.findall(r'\b(\d+)\b', line)])

    if not (b_q or q_q or m_q):
        for m in re.finditer(r'(\d+)\s*(?:[-.:)]|\.)?\s*\[?([BQMбқмBqmБҚМ])\]?', str(text), re.IGNORECASE):
            num = int(m.group(1))
            lvl = m.group(2).upper()
            if lvl in ['B', 'Б']:
                b_q.append(num)
            elif lvl in ['Q', 'Қ']:
                q_q.append(num)
            elif lvl in ['M', 'М']:
                m_q.append(num)

    b_q = [n for n in sorted(list(set(b_q))) if 1 <= n <= 15]
    q_q = [n for n in sorted(list(set(q_q))) if 1 <= n <= 15]
    m_q = [n for n in sorted(list(set(m_q))) if 1 <= n <= 15]
    return b_q, q_q, m_q

def parse_keys_string(keys_str: Any) -> Dict[int, str]:
    res = {}
    if not keys_str:
        return res
    cyr_map = {'А': 'A', 'В': 'B', 'С': 'C', 'Д': 'D', 'а': 'A', 'в': 'B', 'с': 'C', 'д': 'D'}
    s = str(keys_str)
    # Match patterns like: "1. [B] A", "1-A", "1: A", "1.[B]A", "1 A"
    pat = re.compile(r'(\d+)\s*(?:[-.:)]|\.)?\s*(?:\[?[BQMбқмBqmБҚМ]\]?\s*[-.:)]?\s*)?([A-Da-dА-Да-д])\b', re.IGNORECASE)
    for m in pat.finditer(s):
        q_num = int(m.group(1))
        ans = cyr_map.get(m.group(2).upper(), m.group(2).upper())
        res[q_num] = ans

    # If regex missed and input is just 15 space/comma separated letters like "A B C D..."
    if len(res) < 10:
        clean_tokens = [cyr_map.get(t.upper(), t.upper()) for t in re.findall(r'\b([A-Da-dА-Да-д])\b', s)]
        if len(clean_tokens) >= 15:
            res = {i + 1: clean_tokens[i] for i in range(15)}

    return res

def get_chsb_scoring_config(grade: str = "9", subject: str = "Informatika", lang: str = "uz", custom_keys: str = "", custom_criteria: str = "") -> Dict[str, Any]:
    from criteria_store import get_chsb_for_grade
    cfg = get_chsb_for_grade(grade, subject=subject, lang=lang) or {}

    key_dict = dict(cfg.get("key_dict", {}))
    if custom_keys and isinstance(custom_keys, str):
        parsed = parse_keys_string(custom_keys)
        if parsed:
            key_dict.update(parsed)

    if not key_dict:
        key_dict = {1: 'C', 2: 'A', 3: 'D', 4: 'C', 5: 'C', 6: 'A', 7: 'C', 8: 'D', 9: 'A', 10: 'B', 11: 'B', 12: 'D', 13: 'C', 14: 'A', 15: 'C'}

    b_q = list(cfg.get("b_questions", []))
    q_q = list(cfg.get("q_questions", []))
    m_q = list(cfg.get("m_questions", []))

    # Check custom_criteria or custom_keys for custom BQM levels
    if custom_criteria and isinstance(custom_criteria, str):
        cb_q, cq_q, cm_q = parse_bqm_string(custom_criteria)
        if cb_q or cq_q or cm_q:
            b_q = cb_q or b_q
            q_q = cq_q or q_q
            m_q = cm_q or m_q
    elif custom_keys and isinstance(custom_keys, str):
        cb_q, cq_q, cm_q = parse_bqm_string(custom_keys)
        if cb_q or cq_q or cm_q:
            b_q = cb_q or b_q
            q_q = cq_q or q_q
            m_q = cm_q or m_q

    if not b_q or not q_q or not m_q:
        b_q = [1, 4, 7]
        q_q = [2, 3, 5, 6, 8, 9, 10, 11, 12, 14]
        m_q = [13, 15]

    return {
        "key_dict": key_dict,
        "b_questions": b_q,
        "q_questions": q_q,
        "m_questions": m_q,
        "total_questions": cfg.get("total_questions", 15),
        "max_score": cfg.get("max_score", 40)
    }

def score_student_answers(raw_answers: Any, scoring_config: Dict[str, Any]) -> Dict[str, Any]:
    key_dict = scoring_config["key_dict"]
    b_q = scoring_config["b_questions"]
    q_q = scoring_config["q_questions"]
    m_q = scoring_config["m_questions"]
    total_q = scoring_config.get("total_questions", 15)

    ans_dict = {}
    if isinstance(raw_answers, dict):
        cyr_map = {'А': 'A', 'В': 'B', 'С': 'C', 'Д': 'D', 'а': 'A', 'в': 'B', 'с': 'C', 'д': 'D'}
        for k, v in raw_answers.items():
            try:
                ch = str(v).strip().upper()
                ch = cyr_map.get(ch, ch)
                ans_dict[int(k)] = ch
            except:
                pass
    elif isinstance(raw_answers, (str, list)):
        ans_dict = parse_keys_string(raw_answers)

    b_score = 0.0
    q_score = 0.0
    m_score = 0.0
    correct_count = 0
    wrong_q_list = []
    display_parts = []

    for q in range(1, total_q + 1):
        c_ans = key_dict.get(q, "").upper()
        s_ans = ans_dict.get(q, "").upper()

        is_correct = bool(s_ans and c_ans and s_ans == c_ans)
        if is_correct:
            correct_count += 1
            if q in b_q:
                b_score += 2.0
            elif q in q_q:
                q_score += 2.4
            elif q in m_q:
                m_score += 5.0
            else:
                q_score += 2.4
            display_parts.append(f"{q}-{s_ans}")
        else:
            wrong_q_list.append(q)
            shown_ans = s_ans if s_ans else "?"
            display_parts.append(f"{q}-{shown_ans} ❌")

    b_score = round(b_score, 1)
    q_score = round(q_score, 1)
    m_score = round(m_score, 1)
    tot = round(b_score + q_score + m_score, 1)

    tot_val = int(tot) if tot.is_integer() else tot
    b_val = int(b_score) if b_score.is_integer() else b_score
    q_val = int(q_score) if q_score.is_integer() else q_score
    m_val = int(m_score) if m_score.is_integer() else m_score

    wrong_count = len(wrong_q_list)
    if wrong_count == 0:
        note = f"{correct_count} ta to‘g‘ri (100% a‘lo natija)"
    elif wrong_count == 1:
        note = f"{correct_count} ta to‘g‘ri, 1 ta xato ({wrong_q_list[0]}-test)"
    else:
        wr_str = ", ".join(str(x) for x in wrong_q_list)
        note = f"{correct_count} ta to‘g‘ri, {wrong_count} ta xato ({wr_str}-testlar)"

    return {
        "total_score": tot_val,
        "task_scores": [b_val, q_val, m_val],
        "note": note,
        "keys_str": ", ".join(display_parts),
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "wrong_questions": wrong_q_list
    }

class AIService:
    def __init__(self):
        self.keys = GEMINI_KEYS
        self.current_key_idx = 0

    def _get_next_key(self) -> str:
        if not self.keys:
            raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
            self.keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not self.keys:
            raise ValueError("GEMINI_API_KEYS sozlanmagan! .env faylga Gemini API kalitini kiriting.")
        key = self.keys[self.current_key_idx % len(self.keys)]
        self.current_key_idx += 1
        return key

    def _optimize_image(self, path: str) -> Optional[Image.Image]:
        if not path or not os.path.exists(path):
            return None
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img) or img
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            max_dim = 1280
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            logger.warning(f"Error optimizing image {path}: {e}")
            return Image.open(path)

    async def parse_journal_data(self, journal_path: str) -> Tuple[str, Dict[str, float]]:
        """
        Universal eMaktab journal parser:
        Fast magic-byte detection for binary .xls (xlrd), zip .xlsx (openpyxl), text/CSV, and Gemini Vision fallback for images/PDFs.
        Returns: (detected_class_name, {student_name: avg_grade})
        """
        if not journal_path or not os.path.exists(journal_path):
            return ("9-sinf", {})

        detected_cname = "9-sinf"
        res = {}

        # Read first 8 bytes for magic format detection
        try:
            with open(journal_path, "rb") as f:
                magic = f.read(8)
        except Exception:
            magic = b""

        # A. Binary .xls (BIFF8 / OLE2) -> xlrd
        if magic.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") or journal_path.lower().endswith(".xls"):
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
                            detected_cname = to_uzbek_latin(m.group(1).upper().replace("_", "-"))

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
                                res[to_uzbek_latin(col1)] = avg
                if len(res) >= 3:
                    return (detected_cname, res)
            except Exception as e_xlrd:
                logger.warning(f"xlrd parse error: {e_xlrd}")

        # B. Real .xlsx (ZIP PK) -> openpyxl
        if magic.startswith(b"PK\x03\x04") or journal_path.lower().endswith(".xlsx"):
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
                            detected_cname = to_uzbek_latin(m.group(1).upper().replace("_", "-"))

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
                                res[to_uzbek_latin(name_candidate)] = avg
                if len(res) >= 3:
                    return (detected_cname, res)
            except Exception as e_openpyxl:
                logger.warning(f"openpyxl parse error: {e_openpyxl}")

        # C. Text / CSV / TSV
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
                                    detected_cname = to_uzbek_latin(m.group(1).upper().replace("_", "-"))

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
                                        res[to_uzbek_latin(col1)] = avg
                        if len(res) >= 3:
                            return (detected_cname, res)
                except Exception:
                    pass
        except Exception as e_text:
            logger.warning(f"Text/CSV parse error: {e_text}")

        # D. Image or PDF -> Gemini Vision
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

    def generate_chsb_report_from_averages(self, journal_averages: Dict[str, float], class_name: str = "9-sinf", subject: str = "Informatika", lang: str = "uz", custom_keys: str = "", custom_criteria: str = "") -> Dict[str, Any]:
        """
        Darsdagi baholarga qarab 40 ballik CHSB hisobotini o'quvchi ishisiz generatsiya qiladi.
        O'zbek va Rus sinflari uchun to'liq moslangan.
        """
        import random
        from criteria_store import get_chsb_for_grade
        from cyrillic_translit import to_uzbek_latin

        if "рус" in class_name.lower() or "rus" in class_name.lower():
            lang = "ru"

        subject_name = school_info_subject if "school_info_subject" in locals() else "Informatika"
        chsb_cfg = get_chsb_for_grade(class_name, subject=subject, lang=lang) or get_chsb_for_grade("9", subject=subject, lang=lang)
        b_q = chsb_cfg.get("b_questions", [1, 4, 7])
        q_q = chsb_cfg.get("q_questions", [2, 3, 5, 6, 8, 9, 10, 11, 12, 14])
        m_q = chsb_cfg.get("m_questions", [13, 15])
        official_keys = chsb_cfg.get("key_dict", {
            1: 'C', 2: 'A', 3: 'D', 4: 'C', 5: 'C',
            6: 'A', 7: 'C', 8: 'D', 9: 'A', 10: 'B',
            11: 'B', 12: 'D', 13: 'C', 14: 'A', 15: 'C'
        })
        if custom_keys and isinstance(custom_keys, str):
            p_keys = parse_keys_string(custom_keys)
            if p_keys:
                official_keys.update(p_keys)
        if custom_criteria and isinstance(custom_criteria, str):
            cb_q, cq_q, cm_q = parse_bqm_string(custom_criteria)
            if cb_q or cq_q or cm_q:
                b_q = cb_q or b_q
                q_q = cq_q or q_q
                m_q = cm_q or m_q

        students = []
        for idx, (name, avg_grade) in enumerate(journal_averages.items(), start=1):
            seed = sum(ord(ch) for ch in name) + idx
            rng = random.Random(seed)

            if avg_grade >= 9.0:
                num_wrong = rng.choice([1, 1, 2])
                wrong_pool = q_q + m_q
                wrong = sorted(rng.sample(wrong_pool, num_wrong))
                baho_num = 5
            elif avg_grade >= 7.0:
                num_wrong = rng.choice([2, 3, 3, 4])
                wrong_m = rng.choice([0, 1, 1])
                wrong = rng.sample(m_q, min(wrong_m, len(m_q)))
                rem = num_wrong - len(wrong)
                wrong += rng.sample(q_q, rem)
                wrong = sorted(wrong)
                baho_num = 4
            elif avg_grade >= 5.0:
                num_wrong = rng.choice([6, 7, 8, 9])
                wrong = rng.sample(m_q, min(2, len(m_q))) + rng.sample(b_q, 1) + rng.sample(q_q, max(1, num_wrong - 3))
                wrong = sorted(list(set(wrong)))
                baho_num = 3
            else:
                num_wrong = rng.choice([10, 11, 12])
                all_pool = b_q + q_q + m_q
                wrong = sorted(rng.sample(all_pool, min(num_wrong, len(all_pool))))
                baho_num = 2

            b_score = sum(2.0 for q in b_q if q not in wrong)
            q_score = round(sum(2.4 for q in q_q if q not in wrong), 1)
            m_score = sum(5.0 for q in m_q if q not in wrong)
            total = round(b_score + q_score + m_score, 1)

            if total >= 40.0:
                forced = rng.choice(q_q)
                if forced not in wrong:
                    wrong.append(forced)
                    wrong.sort()
                b_score = sum(2.0 for q in b_q if q not in wrong)
                q_score = round(sum(2.4 for q in q_q if q not in wrong), 1)
                m_score = sum(5.0 for q in m_q if q not in wrong)
                total = round(b_score + q_score + m_score, 1)

            if total.is_integer():
                total = int(total)

            correct_count = 15 - len(wrong)
            if lang == "ru":
                if wrong:
                    wrong_str = ', '.join(f'{w}' for w in wrong)
                    note = f"Оценка за урок: {avg_grade} (оценка {baho_num}). {correct_count} верно, {len(wrong)} ошибок ({wrong_str}-тесты)."
                else:
                    note = f"Оценка за урок: {avg_grade} (оценка {baho_num}). Все 15 тестов решены верно (100%)."
                final_name = name
            else:
                if bool(custom_keys):
                    if wrong:
                        wrong_parts = [f"{w}-{official_keys.get(w, 'A')} xato" for w in wrong]
                        note = f"Dars bahosi: {avg_grade} ({baho_num} baho). {correct_count} ta to‘g‘ri, {len(wrong)} ta xato ({', '.join(wrong_parts)})."
                    else:
                        note = f"Dars bahosi: {avg_grade} ({baho_num} baho). Barcha 15 ta test to‘g‘ri yechilgan (100%)."
                else:
                    if wrong:
                        wrong_str = ', '.join(f'{w}' for w in wrong)
                        note = f"Dars bahosi: {avg_grade} ({baho_num} baho). {correct_count} ta to‘g‘ri, {len(wrong)} ta xato ({wrong_str}-testlar)."
                    else:
                        note = f"Dars bahosi: {avg_grade} ({baho_num} baho). Barcha 15 ta test to‘g‘ri yechilgan (100%)."
                final_name = to_uzbek_latin(name)
                note = to_uzbek_latin(note)

            student_keys = []
            for q_num in range(1, 16):
                corr = official_keys.get(q_num, "A")
                if q_num in wrong:
                    wrong_choices = [c for c in ["A", "B", "C", "D"] if c != corr]
                    picked = rng.choice(wrong_choices)
                    student_keys.append(f"{q_num}-{picked} ❌")
                else:
                    student_keys.append(f"{q_num}-{corr}")
            keys_str = ", ".join(student_keys)

            students.append({
                "tr": idx,
                "name": final_name,
                "total_score": total,
                "task_scores": [b_score, q_score, m_score],
                "note": note,
                "keys_str": keys_str
            })

        return {
            "school_info": {
                "class_name": class_name if lang == "ru" else to_uzbek_latin(class_name),
                "subject": ("Информатика" if lang == "ru" else "Informatika") if "adab" not in subject.lower() else "Adabiyot",
                "quarter": 1,
                "chsb_number": 1,
                "max_score": 40,
                "lang": lang,
                "teacher_name": "Кабилов Обиджон" if lang == "ru" else "Qobilov Obidjon",
                "head_teacher": "Махмудова Дильфузахон" if lang == "ru" else "Mahmudova Dilfuzaxon"
            },
            "students": students
        }

    def generate_bsb_report_from_averages(self, journal_averages: Dict[str, float], class_name: str = "9-sinf", subject: str = "Informatika", criteria: Optional[List[Dict[str, Any]]] = None, max_score: Optional[int] = None) -> Dict[str, Any]:
        """
        Darsdagi baholarga qarab BSB hisobotini o'quvchi yozma ishisiz (100% qog'ozsiz) tezkor generatsiya qiladi.
        Mezon topshiriqlari va ballari avtomatik to'g'ri taqsimlanadi va hisobot izohi to'ldiriladi.
        """
        import random
        from cyrillic_translit import to_uzbek_latin
        from emaktab_parser import distribute_score_to_tasks
        from excel_service import generate_bsb_student_note

        if not criteria:
            from criteria_store import get_criteria_for_grade
            c_info = get_criteria_for_grade(class_name) or get_criteria_for_grade("9")
            criteria = c_info.get("criteria", [])
            if not max_score:
                max_score = c_info.get("max_score", 50)

        if not max_score:
            max_score = sum(c.get("max_point", 10) for c in criteria)
            if max_score <= 0:
                max_score = 50

        students = []
        for idx, (name, avg_grade) in enumerate(journal_averages.items(), start=1):
            seed = sum(ord(ch) for ch in name) + idx
            rng = random.Random(seed)

            # O'rtacha baho (1-10 yoki 1-5) ni BSB balliga moslash:
            if avg_grade >= 9.0:
                pct = rng.uniform(0.86, 0.98)
            elif avg_grade >= 7.0:
                pct = rng.uniform(0.70, 0.84)
            elif avg_grade >= 5.0:
                pct = rng.uniform(0.42, 0.65)
            elif avg_grade >= 2.0:
                pct = rng.uniform(0.18, 0.38)
            else:
                pct = rng.uniform(0.10, 0.25)

            tot_score = int(round(pct * max_score))
            tot_score = max(min(tot_score, max_score), 1)

            task_scores = distribute_score_to_tasks(tot_score, criteria)
            note = generate_bsb_student_note(tot_score, max_score, task_scores, criteria)
            percent = int(round((tot_score / max_score) * 100))
            grade_num = 5 if percent >= 85 else (4 if percent >= 70 else (3 if percent >= 50 else 2))

            final_name = to_uzbek_latin(name)
            students.append({
                "tr": idx,
                "name": final_name,
                "total_score": tot_score,
                "task_scores": task_scores,
                "percent": percent,
                "grade": grade_num,
                "note": to_uzbek_latin(note)
            })

        return {
            "school_info": {
                "class_name": to_uzbek_latin(class_name),
                "subject": subject,
                "quarter": 1,
                "bsb_number": 1,
                "max_score": max_score,
                "teacher_name": "Qobilov Obidjon",
                "head_teacher": "Mahmudova Dilfuzaxon"
            },
            "criteria": criteria,
            "students": students
        }

    # 2-TUGMA: BSB o'quvchilar ishini tekshirish (BATCH PROCESSOR: 5 tadan bo'lib tekshiradi!)
    async def evaluate_student_works(self, criteria_img_path: str, work_img_paths: List[str], progress_callback: Optional[Callable] = None, batch_callback: Optional[Callable] = None, keys_input: str = "", is_text_key: bool = False, journal_averages: Optional[Dict[str, float]] = None, is_adjusted: bool = False, custom_criteria: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        batch_size = 4
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
        if custom_criteria:
            criteria_list = custom_criteria
            if not final_info:
                final_info = {}
            final_info["max_score"] = sum(c.get("max_point", 10) for c in custom_criteria)

            new_students = res.get("students", [])
            for s_idx, st in enumerate(new_students):
                st["tr"] = len(all_students) + s_idx + 1
                ts = st.get("task_scores")
                if ts and isinstance(ts, list) and any(x is not None for x in ts):
                    try:
                        computed_sum = sum(float(x) for x in ts if x is not None)
                        tot = round(computed_sum, 1)
                        st["total_score"] = int(tot) if tot.is_integer() else tot
                    except Exception:
                        pass
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
        elif criteria_img_path:
            crit_desc = f"BSB Baholash mezoni va topshiriqlar bo'yicha maksimal ballar (QAT'IY AMAL QILINSIN):\n{criteria_img_path}"
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

YOZMA ISHLARNI TEKSHIRISH VA BIRLASHTIRISH QOIDALARI:
1. KO'P VARAQLI ISHLARNI BIRLASHTIRISH (1-8 VARAQ):
   O'quvchi yozma ishni 1 ta, 2 ta, 4 ta yoki 8 tagacha varaqda yozgan bo'lishi mumkin.
   O'quvchi F.I.O faqat 1-sahifada bo'ladi. Keyingi sahifalarda yangi ism bo'lmasa, ularni yangi o'quvchi deb ochmang — oldingi o'quvchining davomi deb bitta o'quvchiga jamlang!
2. HAQIQATGA MOSLIK:
   O'rtacha bahoga moslashda 50 dan 50 (100%) ball chiqarmang, 44-48 ball oralig'iga moslansin.

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
    "class_name": "9-B",
    "subject": "Informatika",
    "quarter": 1,
    "chsb_number": 1,
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

    # 4-TUGMA: CHSB Testlarni tekshirish (BATCH PROCESSOR: Python 100% matematik aniq hisoblaydi!)
    async def evaluate_test_answers(self, keys_input: str, student_test_img_paths: List[str], progress_callback: Optional[Callable] = None, batch_callback: Optional[Callable] = None, is_text_key: bool = False, criteria_input: str = "", is_text_criteria: bool = False, journal_averages: Optional[Dict[str, float]] = None, is_adjusted: bool = False, grade: str = "9", subject: str = "Informatika", lang: str = "uz") -> Dict[str, Any]:
        scoring_cfg = get_chsb_scoring_config(
            grade=grade,
            subject=subject,
            lang=lang,
            custom_keys=keys_input if is_text_key else "",
            custom_criteria=criteria_input if is_text_criteria else ""
        )

        batch_size = 4
        all_students = []
        final_info = {}

        total_tests = len(student_test_img_paths)
        for i in range(0, total_tests, batch_size):
            batch = student_test_img_paths[i:i + batch_size]
            current_count = min(i + batch_size, total_tests)
            if progress_callback:
                percent = int((current_count / total_tests) * 100)
                await progress_callback(f"⏳ Testlar tekshirilmoqda: {current_count} / {total_tests} ta o‘quvchi ({percent}%)...")

            res = await queue_manager.execute_task(
                self._call_eval_tests_vision,
                keys_input,
                batch,
                start_tr=i+1,
                is_text_key=is_text_key,
                criteria_input=criteria_input,
                is_text_criteria=is_text_criteria,
                journal_averages=journal_averages,
                is_adjusted=is_adjusted
            )
            if not final_info and "school_info" in res:
                final_info = res["school_info"]

            raw_students = res.get("students", [])
            processed_students = []
            for s_idx, st in enumerate(raw_students):
                raw_answers = st.get("answers") or st.get("keys_str") or st.get("student_keys") or {}
                scored = score_student_answers(raw_answers, scoring_cfg)
                
                st.update(scored)
                st["tr"] = len(all_students) + s_idx + 1
                name = str(st.get("name", "")).strip()
                if not name or name.lower() in ["o'quvchi", "o‘quvchi", "noma'lum", "f.i.o"]:
                    st["name"] = f"O‘quvchi {st['tr']}"
                processed_students.append(st)

            all_students.extend(processed_students)
            if batch_callback and processed_students:
                try:
                    await batch_callback(processed_students, current_count, total_tests)
                except Exception as be:
                    logger.warning(f"Batch test callback error: {be}")

            await asyncio.sleep(0.5)

        return {
            "school_info": final_info,
            "students": all_students
        }

    def _call_eval_tests_vision(self, keys_input: str, student_test_img_paths: List[str], start_tr: int = 1, is_text_key: bool = False, criteria_input: str = "", is_text_criteria: bool = False, journal_averages: Optional[Dict[str, float]] = None, is_adjusted: bool = False) -> Dict[str, Any]:
        all_imgs = []
        all_imgs.extend(student_test_img_paths)

        prompt = f"""
Siz test javoblarini o'quvchi mutaxassissiz.
Rasmlar: O'quvchilarning belgilagan test javoblari varaqalari rasmlari.

DIQQAT — ASOSIY VAZIFALAR:
1. O'QUVCHINING ISM-FAMILIYASI (F.I.O):
   Har bir test varaqasidagi "O'quvchining familiyasi, ismi" yoki "F.I.O" yozilgan joydan o'quvchining haqiqiy Ism va Familiyasini juda aniq o'qing (masalan: Абдувоҳидова Мубина, Абдулахаев Шердорбек, Болтабоев Фирдавс...).
   - Qo'lyozma harflarni sinchiklab tahlil qilib to'liq ism-familiyani yozing.
   - Hech qachon "O'quvchi 1", "O'quvchi 2" yoki "O'quvchi (2-varaq)" deb YOZMANG! Har bir varaqada yozilgan ismni aniqlang.

2. O'QUVCHI BELGILAGAN TEST JAVOBLARI (1 dan 15 gacha):
   Har bir savol uchun o'quvchi qaysi variantni (A, B, C, D) belgilaganini aniqlang:
   - Agar test varaqasida "Javoblar jadvali" (kalit matrisi: 1-A, 2-B...) to'ldirilgan bo'lsa — birinchi navbatda o'sha jadvaldagi javob harflarini oling!
   - Agar javoblar jadvali bo'lmasa, test savollarining o'zida doiraga olingan yoki belgilangan variantlarni oling.
   - O'quvchi qog'ozga qaysi harfni belgilagan bo'lsa, AYNAN O'SHANI xolis va haqqoniy yozing. Hech qanday soxta xato to'qimang! Agar barcha 15 ta test to'g'ri belgilangan bo'lsa, barchasini to'g'ri yozing (hech qanday sun'iy ball cheklovi yo'q, halol baholanadi).
   - Agar biror savol belgilanmagan bo'lsa, bo'sh qoldiring ("").

3. VARAQLAR:
   Har bir alohida test varaqasi 1 nafar o'quvchiga tegishli.

Quyidagi JSON formatida qaytaring:
{{
  "school_info": {{
    "class_name": "9-G",
    "subject": "Informatika"
  }},
  "students": [
    {{
      "tr": {start_tr},
      "name": "Абдувоҳидова Мубина",
      "answers": {{
        "1": "C", "2": "A", "3": "D", "4": "C", "5": "C",
        "6": "A", "7": "C", "8": "D", "9": "A", "10": "C",
        "11": "B", "12": "D", "13": "C", "14": "A", "15": "C"
      }}
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
        retries = 6  # 6 tagacha xavfsiz urinish
        last_error = None
        models_pool = ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]

        loaded_imgs = [self._optimize_image(p) for p in img_paths if p and os.path.exists(p)]
        loaded_imgs = [im for im in loaded_imgs if im is not None]
        content = [prompt] + loaded_imgs

        for attempt in range(retries):
            key = self._get_next_key()
            model_name = models_pool[attempt % len(models_pool)]
            genai.configure(api_key=key, transport="rest")
            model = genai.GenerativeModel(model_name)

            try:
                response = model.generate_content(content, request_options={"timeout": 45})
                txt = response.text.strip()
                return self._extract_json(txt)
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Attempt {attempt+1}/{retries} with {model_name} (key ...{key[-4:]}) failed: {e}")
                last_error = e
                import time
                # Agar 429 bo'lsa darhol keyingi kalitga o'tish uchun kutish
                if any(w in err_str.lower() for w in ["429", "quota", "exhausted", "rate"]):
                    logger.info("429 Rate limit aniqlandi, keyingi kalitga avtomatik o'tilmoqda...")
                    time.sleep(2.5)
                else:
                    time.sleep(1.0)

        raise RuntimeError(f"Gemini so'rovi bajarilmadi: {last_error}")

ai_service = AIService()
