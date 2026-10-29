# criteria_store.py
"""
O'zbekiston umumta'lim maktablari Informatika fani 1-chorak rasmiy BSB mezonlar bazasi.
"""

from typing import Dict, Any, List, Optional

INFORMATIKA_1_CHORAK_BSB: Dict[str, Dict[str, Any]] = {
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
