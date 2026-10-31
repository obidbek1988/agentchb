from cyrillic_translit import to_uzbek_latin
import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from typing import Dict, Any, List

thin_border = Border(
    left=Side(style="thin", color="000000"),
    right=Side(style="thin", color="000000"),
    top=Side(style="thin", color="000000"),
    bottom=Side(style="thin", color="000000")
)

font_title = Font(name="Times New Roman", size=11, bold=True)
font_header = Font(name="Times New Roman", size=8.5, bold=True)
font_data = Font(name="Times New Roman", size=10)
font_bold = Font(name="Times New Roman", size=10, bold=True)

def build_bsb_excel(data: Dict[str, Any], output_path: str) -> str:
    """BSB standard 50/25 ball report (A4 Portrait, exact official template)"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Лист1"
    ws.views.sheetView[0].showGridLines = True

    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1

    ws.page_margins.left = 0.25
    ws.page_margins.right = 0.25
    ws.page_margins.top = 0.4
    ws.page_margins.bottom = 0.4

    school_info = data.get("school_info", {})
    criteria = data.get("criteria", [])
    students = data.get("students", [])

    class_name = to_uzbek_latin(school_info.get("class_name", ""))
    subject = school_info.get("subject", "Informatika")
    quarter = school_info.get("quarter", 1)
    bsb_number = school_info.get("bsb_number", 1)
    max_score = school_info.get("max_score", 50)
    teacher_name = to_uzbek_latin(school_info.get("teacher_name", "Qobilov Obidjon"))
    head_teacher = to_uzbek_latin(school_info.get("head_teacher", "Mahmudova Dilfuzaxon"))

    title_text = (
        "BSB tahlil Bayonnomasi\n"
        f"FARG‘ONA viloyati FARG‘ONA SHAHRI 26-umumta’lim maktabi\n"
        f"{class_name} sinf o‘quvchilarining {quarter}-chorak {subject.lower()} fanidan {bsb_number}-BSB ({max_score}ball)natijalari"
    )

    ws.merge_cells("A1:J1")
    c_a1 = ws["A1"]
    c_a1.value = title_text
    c_a1.font = font_title
    c_a1.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 45

    ws.cell(row=2, column=1, value="t/r").font = font_header
    ws.cell(row=2, column=2, value="O‘quvchilarning ism-sharifi").font = font_header

    for idx, crit in enumerate(criteria[:5], start=3):
        txt = crit.get("skill_text", f"{idx-2}-topshiriq")
        c = ws.cell(row=2, column=idx, value=txt)
        c.font = font_header
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin_border

    ws.cell(row=2, column=8, value=f"Jami ball\n{max_score}").font = font_header
    ws.cell(row=2, column=9, value="Foizi\n100%").font = font_header
    ws.cell(row=2, column=10, value="Tahlil / Qisqa izoh\n(Xatolar va to‘g‘rilar)").font = font_header

    for col in [1, 2, 8, 9, 10]:
        cell = ws.cell(row=2, column=col)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    ws.row_dimensions[2].height = 145

    start_row = 3
    for idx, st in enumerate(students, start=1):
        curr_row = start_row + idx - 1
        name = to_uzbek_latin(st.get("name", ""))
        tot = st.get("total_score")
        task_scores = st.get("task_scores")

        # If task_scores is missing, empty or all None, auto-distribute total_score across criteria!
        if tot is not None and tot > 0:
            if not task_scores or all(s is None for s in task_scores) or sum(s or 0 for s in task_scores) != tot:
                from emaktab_parser import distribute_score_to_tasks
                task_scores = distribute_score_to_tasks(tot, criteria)
        else:
            task_scores = [None] * len(criteria)

        c_a = ws.cell(row=curr_row, column=1, value=idx)
        c_a.alignment = Alignment(horizontal="center", vertical="center")
        c_a.border = thin_border
        c_a.font = font_data

        c_b = ws.cell(row=curr_row, column=2, value=name)
        c_b.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        c_b.border = thin_border
        c_b.font = font_data

        for c_idx, score in enumerate(task_scores[:5], start=3):
            val = score if score is not None else ""
            cell = ws.cell(row=curr_row, column=c_idx, value=val)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
            cell.font = font_data

        c_h = ws.cell(row=curr_row, column=8)
        if tot is not None:
            c_h.value = f"=SUM(C{curr_row}:G{curr_row})"
        else:
            c_h.value = ""
        c_h.alignment = Alignment(horizontal="center", vertical="center")
        c_h.border = thin_border
        c_h.font = font_bold

        c_i = ws.cell(row=curr_row, column=9)
        if tot is not None:
            if max_score == 50:
                c_i.value = f"=IF(H{curr_row}=\"\",\"\",H{curr_row}*2)"
            elif max_score == 25:
                c_i.value = f"=IF(H{curr_row}=\"\",\"\",H{curr_row}*4)"
            else:
                c_i.value = f"=IF(H{curr_row}=\"\",\"\",ROUND(H{curr_row}/{max_score}*100,0))"
        else:
            c_i.value = ""
        c_i.alignment = Alignment(horizontal="center", vertical="center")
        c_i.border = thin_border
        c_i.font = font_data

        c_j = ws.cell(row=curr_row, column=10, value=st.get("note", ""))
        c_j.alignment = Alignment(horizontal="left", vertical="center")
        c_j.border = thin_border
        c_j.font = font_data

        ws.row_dimensions[curr_row].height = 19

    end_row = start_row + len(students) - 1
    sig_row = end_row + 2
    ws.cell(row=sig_row, column=1, value=f"Fan o‘qituvchisi:____________________  {teacher_name}").font = font_bold
    ws.cell(row=sig_row+1, column=1, value=f"Metod birlashma rahbari:_______________ {head_teacher}").font = font_bold

    # Printerdan chiqarganda FOIZ ustunigacha (A dan I gacha) chiqsin
    ws.print_area = f"A1:I{sig_row+1}"

    ws.column_dimensions["A"].width = 4.5
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 13
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 13
    ws.column_dimensions["H"].width = 9.5
    ws.column_dimensions["I"].width = 8
    ws.column_dimensions["J"].width = 26

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path

def build_chsb_excel(data: Dict[str, Any], output_path: str) -> str:
    """CHSB 40 ball report: (B) Bilish, (Q) Qo'llash, (M) Mulohaza based template"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Лист1"
    ws.views.sheetView[0].showGridLines = True

    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1

    ws.page_margins.left = 0.3
    ws.page_margins.right = 0.3
    ws.page_margins.top = 0.4
    ws.page_margins.bottom = 0.4

    school_info = data.get("school_info", {})
    students = data.get("students", [])

    class_name = to_uzbek_latin(school_info.get("class_name", ""))
    subject = school_info.get("subject", "Informatika")
    quarter = school_info.get("quarter", 1)
    chsb_number = school_info.get("chsb_number", 1)
    max_score = school_info.get("max_score", 40)
    teacher_name = to_uzbek_latin(school_info.get("teacher_name", "Qobilov Obidjon"))
    head_teacher = to_uzbek_latin(school_info.get("head_teacher", "Mahmudova Dilfuzaxon"))

    title_text = (
        "CHSB test tahlil Bayonnomasi\n"
        f"FARG‘ONA viloyati FARG‘ONA SHAHRI 26-umumta’lim maktabi\n"
        f"{class_name} sinf o‘quvchilarining {quarter}-chorak {subject.lower()} fanidan {chsb_number}-CHSB ({max_score} ball) test natijalari"
    )

    ws.merge_cells("A1:G1")
    c_a1 = ws["A1"]
    c_a1.value = title_text
    c_a1.font = font_title
    c_a1.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 45

    # Headers Row 2
    chsb_headers = [
        ("A2", "t/r"),
        ("B2", "O‘quvchilarning ism-sharifi"),
        ("C2", "(B) – Bilish,\nhar bir to‘g‘ri javob uchun – 2 balldan,\njami 6 ball;"),
        ("D2", "(Q) – Qo‘llash,\nhar bir to‘g‘ri javob uchun – 2,4 balldan,\njami 24 ball;"),
        ("E2", "(M) – Mulohaza,\nhar bir to‘g‘ri javob uchun – 5 balldan,\njami 10 ball;"),
        ("F2", f"Jami ball\n{max_score}"),
        ("G2", "Foizi\n100%"),
        ("H2", "Tahlil / Qisqa izoh\n(Xatolar va to‘g‘rilar)"),
        ("I2", "O‘quvchi belgilagan kalitlar\n(1–15 test javoblari)")
    ]

    for coord, txt in chsb_headers:
        cell = ws[coord]
        cell.value = txt
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    ws.row_dimensions[2].height = 95

    start_row = 3
    for idx, st in enumerate(students, start=1):
        curr_row = start_row + idx - 1
        name = to_uzbek_latin(st.get("name", ""))
        # Expecting task_scores: [B, Q, M]
        bqm = st.get("task_scores", [None, None, None])
        tot = st.get("total_score")

        c_a = ws.cell(row=curr_row, column=1, value=idx)
        c_a.alignment = Alignment(horizontal="center", vertical="center")
        c_a.border = thin_border
        c_a.font = font_data

        c_b = ws.cell(row=curr_row, column=2, value=name)
        c_b.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        c_b.border = thin_border
        c_b.font = font_data

        for c_idx, score in enumerate(bqm[:3], start=3):
            val = score if score is not None else ""
            cell = ws.cell(row=curr_row, column=c_idx, value=val)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
            cell.font = font_data

        c_f = ws.cell(row=curr_row, column=6)
        if tot is not None:
            c_f.value = f"=SUM(C{curr_row}:E{curr_row})"
        else:
            c_f.value = ""
        c_f.alignment = Alignment(horizontal="center", vertical="center")
        c_f.border = thin_border
        c_f.font = font_bold

        c_g = ws.cell(row=curr_row, column=7)
        if tot is not None:
            c_g.value = f"=IF(F{curr_row}=\"\",\"\",ROUND(F{curr_row}/{max_score}*100,0))"
        else:
            c_g.value = ""
        c_g.alignment = Alignment(horizontal="center", vertical="center")
        c_g.border = thin_border
        c_g.font = font_data

        c_h = ws.cell(row=curr_row, column=8, value=st.get("note", ""))
        c_h.alignment = Alignment(horizontal="left", vertical="center")
        c_h.border = thin_border
        c_h.font = font_data

        keys_val = st.get("keys_str") or st.get("student_keys", "")
        c_i = ws.cell(row=curr_row, column=9, value=keys_val)
        c_i.alignment = Alignment(horizontal="left", vertical="center")
        c_i.border = thin_border
        c_i.font = font_data

        ws.row_dimensions[curr_row].height = 19

    end_row = start_row + len(students) - 1
    sig_row = end_row + 2
    ws.cell(row=sig_row, column=1, value=f"Fan o‘qituvchisi:____________________  {teacher_name}").font = font_bold
    ws.cell(row=sig_row+1, column=1, value=f"Metod birlashma rahbari:_______________ {head_teacher}").font = font_bold

    # Printerdan chiqarganda FOIZ ustunigacha (A dan G gacha) chiqsin
    ws.print_area = f"A1:G{sig_row+1}"

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 17
    ws.column_dimensions["D"].width = 19
    ws.column_dimensions["E"].width = 17
    ws.column_dimensions["F"].width = 10
    ws.column_dimensions["G"].width = 8
    ws.column_dimensions["H"].width = 32
    ws.column_dimensions["I"].width = 48

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path
