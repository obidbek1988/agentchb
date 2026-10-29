import os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from typing import Dict, Any

def build_bsb_excel(data: Dict[str, Any], output_path: str) -> str:
    """
    Generates high-quality, print-ready Portrait A4 BSB Report Excel file based on parsed AI data.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Лист1"
    ws.views.sheetView[0].showGridLines = True

    # Page setup: Portrait, A4, fit to 1 page wide
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1

    # Margins in inches
    ws.page_margins.left = 0.25
    ws.page_margins.right = 0.25
    ws.page_margins.top = 0.4
    ws.page_margins.bottom = 0.4

    # Fonts and styles
    font_title = Font(name="Times New Roman", size=11, bold=True)
    font_header = Font(name="Times New Roman", size=8.5, bold=True)
    font_data = Font(name="Times New Roman", size=10)
    font_bold = Font(name="Times New Roman", size=10, bold=True)

    thin_border = Border(
        left=Side(style="thin", color="000000"),
        right=Side(style="thin", color="000000"),
        top=Side(style="thin", color="000000"),
        bottom=Side(style="thin", color="000000")
    )

    school_info = data.get("school_info", {})
    criteria = data.get("criteria", [])
    students = data.get("students", [])

    class_name = school_info.get("class_name", "")
    subject = school_info.get("subject", "Informatika")
    quarter = school_info.get("quarter", 1)
    bsb_number = school_info.get("bsb_number", 1)
    max_score = school_info.get("max_score", 50)
    teacher_name = school_info.get("teacher_name", "Qobilov Obidjon")
    head_teacher = school_info.get("head_teacher", "Mahmudova Dilfuzaxon")

    # 1. Title Block (Row 1 merged A1:I1)
    title_text = (
        "BSB tahlil Bayonnomasi\n"
        f"FARG‘ONA viloyati FARG‘ONA SHAHRI 26-umumta’lim maktabi\n"
        f"{class_name} sinf o‘quvchilarining {quarter}-chorak {subject.lower()} fanidan {bsb_number}-BSB ({max_score}ball)natijalari"
    )

    ws.merge_cells("A1:I1")
    c_a1 = ws["A1"]
    c_a1.value = title_text
    c_a1.font = font_title
    c_a1.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 45

    # 2. Main Headers (Row 2)
    # A: t/r, B: FIO, C..G: criteria, H: Jami ball, I: Foizi 100%
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

    for col in [1, 2, 8, 9]:
        cell = ws.cell(row=2, column=col)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    ws.row_dimensions[2].height = 145

    # 3. Students Data (Starts immediately from Row 3)
    start_row = 3
    for idx, st in enumerate(students, start=1):
        curr_row = start_row + idx - 1
        name = st.get("name", "")
        task_scores = st.get("task_scores", [None]*5)
        tot = st.get("total_score")

        # Col A
        c_a = ws.cell(row=curr_row, column=1, value=idx)
        c_a.alignment = Alignment(horizontal="center", vertical="center")
        c_a.border = thin_border
        c_a.font = font_data

        # Col B
        c_b = ws.cell(row=curr_row, column=2, value=name)
        c_b.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        c_b.border = thin_border
        c_b.font = font_data

        # Cols C to G
        for c_idx, score in enumerate(task_scores[:5], start=3):
            val = score if score is not None else ""
            cell = ws.cell(row=curr_row, column=c_idx, value=val)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
            cell.font = font_data

        # Col H (Total formula)
        c_h = ws.cell(row=curr_row, column=8)
        if tot is not None:
            c_h.value = f"=SUM(C{curr_row}:G{curr_row})"
        else:
            c_h.value = ""
        c_h.alignment = Alignment(horizontal="center", vertical="center")
        c_h.border = thin_border
        c_h.font = font_bold

        # Col I (Percentage formula based on max_score)
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

        ws.row_dimensions[curr_row].height = 19

    end_row = start_row + len(students) - 1

    # 4. Signatures
    sig_row = end_row + 2
    ws.cell(row=sig_row, column=1, value=f"Fan o‘qituvchisi:____________________  {teacher_name}").font = font_bold
    ws.cell(row=sig_row+1, column=1, value=f"Metod birlashma rahbari:_______________ {head_teacher}").font = font_bold

    # Column widths tailored for Portrait A4
    ws.column_dimensions["A"].width = 4.5
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 13
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 13
    ws.column_dimensions["H"].width = 9.5
    ws.column_dimensions["I"].width = 8

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    wb.save(output_path)
    return output_path
