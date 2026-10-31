# criteria_store.py
"""
O'zbekiston umumta'lim maktablari Informatika fani 1-chorak rasmiy BSB mezonlar bazasi.
"""

from typing import Dict, Any, List, Optional

INFORMATIKA_1_CHORAK_BSB: Dict[str, Dict[str, Any]] = {
    "5": {
        "title": "5-sinf Informatika 1-BSB",
        "class_name": "5-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "bsb_number": 1,
        "max_score": 25,
        "criteria": [
            {
                "task_number": 1,
                "skill_text": "Axborot tushunchasi va uning turlari (matnli, tovushli, grafik, raqamli);\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 2,
                "skill_text": "Kompyuterning asosiy qurilmalari va ularning vazifalarini bilish;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 3,
                "skill_text": "Klaviatura va sichqoncha bilan ishlash ko‘nikmalari;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 4,
                "skill_text": "Matn muharririda sodda matn terish va shriftlarni tahrirlash;\n\nJami: 10 ball",
                "max_point": 10
            }
        ]
    },
    "6": {
        "title": "6-sinf Informatika 1-BSB",
        "class_name": "6-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "bsb_number": 1,
        "max_score": 30,
        "criteria": [
            {
                "task_number": 1,
                "skill_text": "Matn qo‘shish, o‘zgartirish va ko‘chirish;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 2,
                "skill_text": "Shrift turi, o‘lchami va rangini o‘zgartirish; Matnni tekislash; Hujjatlarni auditoriya uchun moslash;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 3,
                "skill_text": "Hujjatga tasvir va hoshiya qo‘shish;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 4,
                "skill_text": "Tasvirni import qilish;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 5,
                "skill_text": "Ma’lumotlar validatsiyasi bilan ishlash;\n\nJami: 10 ball",
                "max_point": 10
            }
        ]
    },
    "7": {
        "title": "7-sinf Informatika 1-BSB",
        "class_name": "7-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "bsb_number": 1,
        "max_score": 25,
        "criteria": [
            {
                "task_number": 1,
                "skill_text": "Matn stillarini sozlash va ulardan foydalanish; Wrap text sozlamalarini qo‘llash;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 2,
                "skill_text": "Tasvirni qirqish va o‘lchamini o‘zgartirish; Wrap text sozlamalari;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 3,
                "skill_text": "Jadval o‘rnatish va uni formatlash;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 4,
                "skill_text": "Belgili ro‘yxat (marker) yaratish va tahrirlash;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 5,
                "skill_text": "Matnni ustunlarga bo‘lish; Sahifani formatlash; Print preview ko‘rish;\n\nJami: 5 ball",
                "max_point": 5
            }
        ]
    },
    "8": {
        "title": "8-sinf Informatika 1-BSB",
        "class_name": "8-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "bsb_number": 1,
        "max_score": 25,
        "criteria": [
            {
                "task_number": 1,
                "skill_text": "Sprayt kostyumlari va vaqt bilan ishlash;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 2,
                "skill_text": "Shartli dasturlash asoslari bilan ishlash;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 3,
                "skill_text": "O‘zgaruvchilar va ularni dasturda boshqarish;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 4,
                "skill_text": "To‘qnashuvlar asosidagi ssenariy va animatsiya yaratish;\n\nJami: 5 ball",
                "max_point": 5
            },
            {
                "task_number": 5,
                "skill_text": "Ma’lumotlar validatsiyasi va loyiha sinovi;\n\nJami: 5 ball",
                "max_point": 5
            }
        ]
    },
    "9": {
        "title": "9-sinf Informatika 1-BSB",
        "class_name": "9-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "bsb_number": 1,
        "max_score": 50,
        "criteria": [
            {
                "task_number": 1,
                "skill_text": "Kompyuter qurilmalari va ularning vazifalarini farqlay oladi;\nDasturiy taʼminot vazifalarini biladi;\nKompyuter tizimi asosiy komponentalarini farqlay oladi;\n\nJami: 10 ball",
                "max_point": 10
            },
            {
                "task_number": 2,
                "skill_text": "Kompyuterning kiritish va chiqarish qurilmalarini sanay oladi;\nKiritish va chiqarish qurilmalari vazifalarini biladi;\n\nJami: 10 ball",
                "max_point": 10
            },
            {
                "task_number": 3,
                "skill_text": "Xotira qurilmalarini turlariga koʻra farqini biladi;\nTurli xotira qurilmalarining afzallik va kamchiliklarini ayta oladi;\nXotira hajmiga bogʻliq masalalarni yecha oladi;\n\nJami: 12 ball",
                "max_point": 12
            },
            {
                "task_number": 4,
                "skill_text": "Tarmoqni hosil qiluvchi qurilmalarni biladi;\nTarmoq hosil qiluvchi qurilmalar afzallik va kamchiliklarini ayta oladi;\n\nJami: 8 ball",
                "max_point": 8
            },
            {
                "task_number": 5,
                "skill_text": "Brauzer turlarini biladi;\nBrauzerda ishlay oladi;\nElektron pochta bilan ishlay oladi;\n\nJami: 10 ball",
                "max_point": 10
            }
        ]
    },
    "10": {
        "title": "10-sinf Informatika 1-BSB",
        "class_name": "10-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "bsb_number": 1,
        "max_score": 50,
        "criteria": [
            {
                "task_number": 1,
                "skill_text": "Maʼlumot, axborot va bilimlar bazasi oʻrtasidagi farqlarni tushunadi;\nStatik va dinamik maʼlumotlarni taʼriflay oladi;\nAxborotning sifatini tahlil qila oladi;\n\nJami: 10 ball",
                "max_point": 10
            },
            {
                "task_number": 2,
                "skill_text": "Maʼlumotlarni kodlashning afzallik va kamchiliklarini biladi;\nMaʼlumotlarni kodlashni amalga oshira oladi;\nShifrlash usullarini farqlay oladi;\n\nJami: 8 ball",
                "max_point": 8
            },
            {
                "task_number": 3,
                "skill_text": "Apparat taʼminoti tushunchasini taʼriflay oladi;\nIchki va tashqi qurilmalarni baholay oladi;\nXotira, kiritish va chiqarish qurilmalarini baholay oladi;\n\nJami: 12 ball",
                "max_point": 12
            },
            {
                "task_number": 4,
                "skill_text": "Turli dasturiy taʼminotlarni baholay oladi;\nTizimli va amaliy dasturiy taʼminotni farqlaydi;\nUtilit dasturlarni tasvirlay oladi;\n\nJami: 12 ball",
                "max_point": 12
            },
            {
                "task_number": 5,
                "skill_text": "Elektron xavfsizlik nima uchun zarurligini tushunadi;\nShaxsiy maʼlumotlarni himoyalash va zararli dasturlar xavfini biladi;\n\nJami: 8 ball",
                "max_point": 8
            }
        ]
    },
    "11": {
        "title": "11-sinf Informatika 1-BSB",
        "class_name": "11-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "bsb_number": 1,
        "max_score": 50,
        "criteria": [
            {
                "task_number": 1,
                "skill_text": "Videoklipni yaratish maqsadi va auditoriya talabiga moslab tahrirlay oladi; Audioklipni tahrirlay oladi;\n\nJami: 10 ball",
                "max_point": 10
            },
            {
                "task_number": 2,
                "skill_text": "Video va audiofaylni tahrirlash funksiyalari amalda qanday qoʻllanishini tushunadi;\n\nJami: 10 ball",
                "max_point": 10
            },
            {
                "task_number": 3,
                "skill_text": "Videoklip qismlariga tasvir qo‘sha oladi; Videoklip ovozini o‘zgartira oladi;\n\nJami: 10 ball",
                "max_point": 10
            },
            {
                "task_number": 4,
                "skill_text": "Effektlar va o‘tishlar (transitions) bilan ishlay oladi; Titrlar qo‘sha oladi;\n\nJami: 10 ball",
                "max_point": 10
            },
            {
                "task_number": 5,
                "skill_text": "Reverberatsiya effekti bilan ishlay oladi; Tayyor loyihani eksport qila oladi;\n\nJami: 10 ball",
                "max_point": 10
            }
        ]
    }
}

def get_criteria_for_grade(grade: str) -> Optional[Dict[str, Any]]:
    # Normalizes '9-sinf', '9-G', '9' -> '9'
    digits = "".join([c for c in grade if c.isdigit()])
    return INFORMATIKA_1_CHORAK_BSB.get(digits)

def format_criteria_preview(grade: str) -> str:
    info = get_criteria_for_grade(grade)
    if not info:
        return "Ushbu sinf uchun mezon topilmadi."
    
    text = f"📋 **{info['title']} rasmiy baholash mezonlari ({info['max_score']} ball):**\n\n"
    for idx, c in enumerate(info['criteria'], start=1):
        clean_text = c['skill_text'].replace('\n\nJami:', ' — Jami:').replace('\n', ' ')
        text += f"**{idx}-topshiriq [{c['max_point']} ball]:**\n_{clean_text}_\n\n"
    return text.strip()

# ==================== CHSB MEZONLARI (INFORMATIKA) ====================

INFORMATIKA_1_CHORAK_CHSB: Dict[str, Dict[str, Any]] = {
    "9": {
        "title": "9-sinf Informatika va axborot texnologiyalari",
        "doc_title": "2026-2027-o‘quv yili 9-sinf Informatika 1-CHSB (Original)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "9-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/9_sinf_informatika_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 4, 7-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 2, 3, 5, 6, 8, 9, 10, 11, 12, 14-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 13, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(Q)  3.(Q)  4.(B)  5.(Q)\n6.(Q)  7.(B)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(M) 14.(Q) 15.(M)",
        "keys": "1-C, 2-A, 3-D, 4-C, 5-C, 6-A, 7-C, 8-D, 9-A, 10-B, 11-B, 12-D, 13-C, 14-A, 15-C",
        "keys_formatted": (
            "1-C, 2-A, 3-D, 4-C, 5-C\n"
            "6-A, 7-C, 8-D, 9-A, 10-B\n"
            "11-B, 12-D, 13-C, 14-A, 15-C"
        ),
        "b_questions": [1, 4, 7],
        "q_questions": [2, 3, 5, 6, 8, 9, 10, 11, 12, 14],
        "m_questions": [13, 15],
        "key_dict": {1: 'C', 2: 'A', 3: 'D', 4: 'C', 5: 'C', 6: 'A', 7: 'C', 8: 'D', 9: 'A', 10: 'B', 11: 'B', 12: 'D', 13: 'C', 14: 'A', 15: 'C'}
    },
    "10": {
        "title": "10-sinf Informatika va axborot texnologiyalari",
        "doc_title": "2026-2027-o‘quv yili 10-sinf Informatika 1-CHSB (Original)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "10-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/10_sinf_informatika_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 7, 11-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 2, 3, 4, 5, 6, 8, 9, 12, 13, 14-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 10, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(Q)  3.(Q)  4.(Q)  5.(Q)\n6.(Q)  7.(B)  8.(Q)  9.(Q)  10.(M)\n11.(B) 12.(Q) 13.(Q) 14.(Q) 15.(M)",
        "keys": "1-B, 2-A, 3-A, 4-C, 5-D, 6-B, 7-B, 8-D, 9-C, 10-A, 11-B, 12-B, 13-A, 14-C, 15-B",
        "keys_formatted": (
            "1-B, 2-A, 3-A, 4-C, 5-D\n"
            "6-B, 7-B, 8-D, 9-C, 10-A\n"
            "11-B, 12-B, 13-A, 14-C, 15-B"
        ),
        "b_questions": [1, 7, 11],
        "q_questions": [2, 3, 4, 5, 6, 8, 9, 12, 13, 14],
        "m_questions": [10, 15],
        "key_dict": {1: 'B', 2: 'A', 3: 'A', 4: 'C', 5: 'D', 6: 'B', 7: 'B', 8: 'D', 9: 'C', 10: 'A', 11: 'B', 12: 'B', 13: 'A', 14: 'C', 15: 'B'}
    },
    "11": {
        "title": "11-sinf Informatika va axborot texnologiyalari",
        "doc_title": "2026-2027-o‘quv yili 11-sinf Informatika 1-CHSB (Original)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "11-sinf",
        "subject": "Informatika",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/11_sinf_informatika_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 2, 6-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 3, 4, 5, 7, 8, 9, 10, 11, 12, 13-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 14, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(B)  3.(Q)  4.(Q)  5.(Q)\n6.(B)  7.(Q)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(Q) 14.(M) 15.(M)",
        "keys": "1-B, 2-A, 3-B, 4-A, 5-C, 6-B, 7-A, 8-A, 9-B, 10-C, 11-A, 12-D, 13-B, 14-B, 15-D",
        "keys_formatted": (
            "1-B, 2-A, 3-B, 4-A, 5-C\n"
            "6-B, 7-A, 8-A, 9-B, 10-C\n"
            "11-A, 12-D, 13-B, 14-B, 15-D"
        ),
        "b_questions": [1, 2, 6],
        "q_questions": [3, 4, 5, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'B', 2: 'A', 3: 'B', 4: 'A', 5: 'C', 6: 'B', 7: 'A', 8: 'A', 9: 'B', 10: 'C', 11: 'A', 12: 'D', 13: 'B', 14: 'B', 15: 'D'}
    }
}

INFORMATIKA_1_CHORAK_CHSB_RUS: Dict[str, Dict[str, Any]] = {
    "9": {
        "title": "9-класс Информатика и информационные технологии",
        "doc_title": "2026–2027 учебный год 9-класс Информатика СОЧ-1 (Оригинал)",
        "agency": "Научно-практический центр педагогического мастерства и международной оценки",
        "class_name": "9-класс",
        "subject": "Информатика",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/9_sinf_informatika_chsb1_rus.pdf",
        "distribution_summary": (
            "• **(З) Знание:** 1, 4, 7-вопросы (по 2 балла = 6 баллов)\n"
            "• **(П) Применение:** 2, 3, 5, 6, 8, 9, 10, 11, 12, 14-вопросы (по 2.4 балла = 24 балла)\n"
            "• **(Р) Рассуждение:** 13, 15-вопросы (по 5 баллов = 10 баллов)\n"
            "**Всего: 15 тестов — 40 баллов**"
        ),
        "bqm_compact": "1.(З)  2.(П)  3.(П)  4.(З)  5.(П)\n6.(П)  7.(З)  8.(П)  9.(П)  10.(П)\n11.(П) 12.(П) 13.(Р) 14.(П) 15.(Р)",
        "keys": "1-C, 2-A, 3-D, 4-C, 5-C, 6-A, 7-C, 8-D, 9-A, 10-B, 11-B, 12-D, 13-C, 14-A, 15-C",
        "keys_formatted": (
            "1-C, 2-A, 3-D, 4-C, 5-C\n"
            "6-A, 7-C, 8-D, 9-A, 10-B\n"
            "11-B, 12-D, 13-C, 14-A, 15-C"
        ),
        "b_questions": [1, 4, 7],
        "q_questions": [2, 3, 5, 6, 8, 9, 10, 11, 12, 14],
        "m_questions": [13, 15],
        "key_dict": {1: 'C', 2: 'A', 3: 'D', 4: 'C', 5: 'C', 6: 'A', 7: 'C', 8: 'D', 9: 'A', 10: 'B', 11: 'B', 12: 'D', 13: 'C', 14: 'A', 15: 'C'}
    },
    "10": {
        "title": "10-класс Информатика и информационные технологии",
        "doc_title": "2026–2027 учебный год 10-класс Информатика СОЧ-1 (Оригинал)",
        "agency": "Научно-практический центр педагогического мастерства и международной оценки",
        "class_name": "10-класс",
        "subject": "Информатика",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/10_sinf_informatika_chsb1_rus.pdf",
        "distribution_summary": (
            "• **(З) Знание:** 1, 7, 11-вопросы (по 2 балла = 6 баллов)\n"
            "• **(П) Применение:** 2, 3, 4, 5, 6, 8, 9, 12, 13, 14-вопросы (по 2.4 балла = 24 балла)\n"
            "• **(Р) Рассуждение:** 10, 15-вопросы (по 5 баллов = 10 баллов)\n"
            "**Всего: 15 тестов — 40 баллов**"
        ),
        "bqm_compact": "1.(З)  2.(П)  3.(П)  4.(П)  5.(П)\n6.(П)  7.(З)  8.(П)  9.(П)  10.(Р)\n11.(З) 12.(П) 13.(П) 14.(П) 15.(Р)",
        "keys": "1-B, 2-A, 3-A, 4-C, 5-D, 6-B, 7-B, 8-D, 9-C, 10-A, 11-B, 12-B, 13-A, 14-C, 15-B",
        "keys_formatted": (
            "1-B, 2-A, 3-A, 4-C, 5-D\n"
            "6-B, 7-B, 8-D, 9-C, 10-A\n"
            "11-B, 12-B, 13-A, 14-C, 15-B"
        ),
        "b_questions": [1, 7, 11],
        "q_questions": [2, 3, 4, 5, 6, 8, 9, 12, 13, 14],
        "m_questions": [10, 15],
        "key_dict": {1: 'B', 2: 'A', 3: 'A', 4: 'C', 5: 'D', 6: 'B', 7: 'B', 8: 'D', 9: 'C', 10: 'A', 11: 'B', 12: 'B', 13: 'A', 14: 'C', 15: 'B'}
    },
    "11": {
        "title": "11-класс Информатика и информационные технологии",
        "doc_title": "2026–2027 учебный год 11-класс Информатика СОЧ-1 (Оригинал)",
        "agency": "Научно-практический центр педагогического мастерства и международной оценки",
        "class_name": "11-класс",
        "subject": "Информатика",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/11_sinf_informatika_chsb1_rus.pdf",
        "distribution_summary": (
            "• **(З) Знание:** 1, 2, 6-вопросы (по 2 балла = 6 баллов)\n"
            "• **(П) Применение:** 3, 4, 5, 7, 8, 9, 10, 11, 12, 13-вопросы (по 2.4 балла = 24 балла)\n"
            "• **(Р) Рассуждение:** 14, 15-вопросы (по 5 баллов = 10 баллов)\n"
            "**Всего: 15 тестов — 40 баллов**"
        ),
        "bqm_compact": "1.(З)  2.(З)  3.(П)  4.(П)  5.(П)\n6.(З)  7.(П)  8.(П)  9.(П)  10.(П)\n11.(П) 12.(П) 13.(П) 14.(Р) 15.(Р)",
        "keys": "1-B, 2-A, 3-B, 4-A, 5-C, 6-B, 7-A, 8-A, 9-B, 10-C, 11-A, 12-D, 13-B, 14-B, 15-D",
        "keys_formatted": (
            "1-B, 2-A, 3-B, 4-A, 5-C\n"
            "6-B, 7-A, 8-A, 9-B, 10-C\n"
            "11-A, 12-D, 13-B, 14-B, 15-D"
        ),
        "b_questions": [1, 2, 6],
        "q_questions": [3, 4, 5, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'B', 2: 'A', 3: 'B', 4: 'A', 5: 'C', 6: 'B', 7: 'A', 8: 'A', 9: 'B', 10: 'C', 11: 'A', 12: 'D', 13: 'B', 14: 'B', 15: 'D'}
    }
}

ADABIYOT_1_CHORAK_CHSB: Dict[str, Dict[str, Any]] = {
    "5": {
        "title": "5-sinf Adabiyot",
        "doc_title": "2026-2027-o‘quv yili 5-sinf Adabiyot 1-CHSB (Original)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "5-sinf",
        "subject": "Adabiyot",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/5_sinf_adabiyot_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 2, 3-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 4, 5, 6, 7, 8, 9, 10, 11, 12, 13-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 14, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(B)  3.(B)  4.(Q)  5.(Q)\n6.(Q)  7.(Q)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(Q) 14.(M) 15.(M)",
        "keys": "1-D, 2-B, 3-A, 4-C, 5-D, 6-B, 7-C, 8-D, 9-B, 10-A, 11-A, 12-A, 13-C, 14-B, 15-C",
        "keys_formatted": (
            "1-D, 2-B, 3-A, 4-C, 5-D\n"
            "6-B, 7-C, 8-D, 9-B, 10-A\n"
            "11-A, 12-A, 13-C, 14-B, 15-C"
        ),
        "b_questions": [1, 2, 3],
        "q_questions": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'D', 2: 'B', 3: 'A', 4: 'C', 5: 'D', 6: 'B', 7: 'C', 8: 'D', 9: 'B', 10: 'A', 11: 'A', 12: 'A', 13: 'C', 14: 'B', 15: 'C'}
    },
    "6": {
        "title": "6-sinf Adabiyot",
        "doc_title": "2026-2027-o‘quv yili 6-sinf Adabiyot 1-CHSB (Original)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "6-sinf",
        "subject": "Adabiyot",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/6_sinf_adabiyot_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 2, 3-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 4, 5, 6, 7, 8, 9, 10, 11, 12, 13-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 14, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(B)  3.(B)  4.(Q)  5.(Q)\n6.(Q)  7.(Q)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(Q) 14.(M) 15.(M)",
        "keys": "1-C, 2-B, 3-A, 4-B, 5-B, 6-D, 7-B, 8-C, 9-D, 10-C, 11-B, 12-A, 13-A, 14-B, 15-D",
        "keys_formatted": (
            "1-C, 2-B, 3-A, 4-B, 5-B\n"
            "6-D, 7-B, 8-C, 9-D, 10-C\n"
            "11-B, 12-A, 13-A, 14-B, 15-D"
        ),
        "b_questions": [1, 2, 3],
        "q_questions": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'C', 2: 'B', 3: 'A', 4: 'B', 5: 'B', 6: 'D', 7: 'B', 8: 'C', 9: 'D', 10: 'C', 11: 'B', 12: 'A', 13: 'A', 14: 'B', 15: 'D'}
    },
    "7": {
        "title": "7-sinf Adabiyot",
        "doc_title": "2026-2027-o‘quv yili 7-sinf Adabiyot 1-CHSB (I variant)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "7-sinf",
        "subject": "Adabiyot",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/7_sinf_adabiyot_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 2, 3-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 4, 5, 6, 7, 8, 9, 10, 11, 12, 13-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 14, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(B)  3.(B)  4.(Q)  5.(Q)\n6.(Q)  7.(Q)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(Q) 14.(M) 15.(M)",
        "keys": "1-A, 2-D, 3-A, 4-C, 5-A, 6-B, 7-A, 8-B, 9-D, 10-B, 11-C, 12-D, 13-A, 14-B, 15-C",
        "keys_formatted": (
            "1-A, 2-D, 3-A, 4-C, 5-A\n"
            "6-B, 7-A, 8-B, 9-D, 10-B\n"
            "11-C, 12-D, 13-A, 14-B, 15-C"
        ),
        "b_questions": [1, 2, 3],
        "q_questions": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'A', 2: 'D', 3: 'A', 4: 'C', 5: 'A', 6: 'B', 7: 'A', 8: 'B', 9: 'D', 10: 'B', 11: 'C', 12: 'D', 13: 'A', 14: 'B', 15: 'C'}
    },
    "8": {
        "title": "8-sinf Adabiyot",
        "doc_title": "2026-2027-o‘quv yili 8-sinf Adabiyot 1-CHSB (Original)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "8-sinf",
        "subject": "Adabiyot",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/8_sinf_adabiyot_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 2, 3-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 4, 5, 6, 7, 8, 9, 10, 11, 12, 13-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 14, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(B)  3.(B)  4.(Q)  5.(Q)\n6.(Q)  7.(Q)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(Q) 14.(M) 15.(M)",
        "keys": "1-C, 2-B, 3-B, 4-A, 5-C, 6-D, 7-B, 8-D, 9-B, 10-C, 11-D, 12-D, 13-A, 14-B, 15-C",
        "keys_formatted": (
            "1-C, 2-B, 3-B, 4-A, 5-C\n"
            "6-D, 7-B, 8-D, 9-B, 10-C\n"
            "11-D, 12-D, 13-A, 14-B, 15-C"
        ),
        "b_questions": [1, 2, 3],
        "q_questions": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'C', 2: 'B', 3: 'B', 4: 'A', 5: 'C', 6: 'D', 7: 'B', 8: 'D', 9: 'B', 10: 'C', 11: 'D', 12: 'D', 13: 'A', 14: 'B', 15: 'C'}
    },
    "9": {
        "title": "9-sinf Adabiyot",
        "doc_title": "2026-2027-o‘quv yili 9-sinf Adabiyot 1-CHSB (Original)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "9-sinf",
        "subject": "Adabiyot",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/9_sinf_adabiyot_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 2, 3-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 4, 5, 6, 7, 8, 9, 10, 11, 12, 13-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 14, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(B)  3.(B)  4.(Q)  5.(Q)\n6.(Q)  7.(Q)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(Q) 14.(M) 15.(M)",
        "keys": "1-C, 2-B, 3-B, 4-D, 5-B, 6-B, 7-C, 8-B, 9-D, 10-C, 11-D, 12-C, 13-A, 14-A, 15-D",
        "keys_formatted": (
            "1-C, 2-B, 3-B, 4-D, 5-B\n"
            "6-B, 7-C, 8-B, 9-D, 10-C\n"
            "11-D, 12-C, 13-A, 14-A, 15-D"
        ),
        "b_questions": [1, 2, 3],
        "q_questions": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'C', 2: 'B', 3: 'B', 4: 'D', 5: 'B', 6: 'B', 7: 'C', 8: 'B', 9: 'D', 10: 'C', 11: 'D', 12: 'C', 13: 'A', 14: 'A', 15: 'D'}
    },
    "10": {
        "title": "10-sinf Adabiyot",
        "doc_title": "2026-2027-o‘quv yili 10-sinf Adabiyot 1-CHSB (Original)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "10-sinf",
        "subject": "Adabiyot",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/10_sinf_adabiyot_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 2, 3-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 4, 5, 6, 7, 8, 9, 10, 11, 12, 13-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 14, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(B)  3.(B)  4.(Q)  5.(Q)\n6.(Q)  7.(Q)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(Q) 14.(M) 15.(M)",
        "keys": "1-B, 2-C, 3-B, 4-B, 5-D, 6-D, 7-C, 8-B, 9-D, 10-C, 11-A, 12-D, 13-B, 14-D, 15-A",
        "keys_formatted": (
            "1-B, 2-C, 3-B, 4-B, 5-D\n"
            "6-D, 7-C, 8-B, 9-D, 10-C\n"
            "11-A, 12-D, 13-B, 14-D, 15-A"
        ),
        "b_questions": [1, 2, 3],
        "q_questions": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'B', 2: 'C', 3: 'B', 4: 'B', 5: 'D', 6: 'D', 7: 'C', 8: 'B', 9: 'D', 10: 'C', 11: 'A', 12: 'D', 13: 'B', 14: 'D', 15: 'A'}
    },
    "11": {
        "title": "11-sinf Adabiyot",
        "doc_title": "2026-2027-o‘quv yili 11-sinf Adabiyot 1-CHSB (I variant)",
        "agency": "Pedagogik mahorat va xalqaro baholash ilmiy-amaliy markazi",
        "class_name": "11-sinf",
        "subject": "Adabiyot",
        "quarter": 1,
        "chsb_number": 1,
        "max_score": 40,
        "total_questions": 15,
        "pdf_path": "assets/11_sinf_adabiyot_chsb1_original.pdf",
        "distribution_summary": (
            "• **(B) Bilish:** 1, 2, 3-savollar (har biri 2 balldan = 6 ball)\n"
            "• **(Q) Qo‘llash:** 4, 5, 6, 7, 8, 9, 10, 11, 12, 13-savollar (har biri 2.4 balldan = 24 ball)\n"
            "• **(M) Mulohaza:** 14, 15-savollar (har biri 5 balldan = 10 ball)\n"
            "**Jami: 15 ta test — 40 ball**"
        ),
        "bqm_compact": "1.(B)  2.(B)  3.(B)  4.(Q)  5.(Q)\n6.(Q)  7.(Q)  8.(Q)  9.(Q)  10.(Q)\n11.(Q) 12.(Q) 13.(Q) 14.(M) 15.(M)",
        "keys": "1-C, 2-C, 3-C, 4-A, 5-C, 6-C, 7-D, 8-B, 9-C, 10-A, 11-C, 12-D, 13-B, 14-A, 15-B",
        "keys_formatted": (
            "1-C, 2-C, 3-C, 4-A, 5-C\n"
            "6-C, 7-D, 8-B, 9-C, 10-A\n"
            "11-C, 12-D, 13-B, 14-A, 15-B"
        ),
        "b_questions": [1, 2, 3],
        "q_questions": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
        "m_questions": [14, 15],
        "key_dict": {1: 'C', 2: 'C', 3: 'C', 4: 'A', 5: 'C', 6: 'C', 7: 'D', 8: 'B', 9: 'C', 10: 'A', 11: 'C', 12: 'D', 13: 'B', 14: 'A', 15: 'B'}
    }
}

def get_chsb_for_grade(grade: str, subject: str = "informatika", lang: str = "uz") -> Optional[Dict[str, Any]]:
    digits = "".join([c for c in grade if c.isdigit()])
    subj_norm = (subject or "informatika").lower()
    if "adab" in subj_norm:
        return ADABIYOT_1_CHORAK_CHSB.get(digits)
    if lang == "ru":
        return INFORMATIKA_1_CHORAK_CHSB_RUS.get(digits) or INFORMATIKA_1_CHORAK_CHSB.get(digits)
    return INFORMATIKA_1_CHORAK_CHSB.get(digits)
