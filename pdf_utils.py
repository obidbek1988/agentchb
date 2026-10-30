# pdf_utils.py
"""
PDF fayllarni o'qish va har bir sahifasini yuqori sifatli rasmga aylantirish yordamchisi.
"""

import os
import logging
from typing import List
import pypdfium2 as pdfium

logger = logging.getLogger(__name__)

def pdf_to_images(pdf_path: str, output_dir: str = "temp") -> List[str]:
    """
    Berilgan PDF faylni o'qib, har bir sahifasini JPEG rasm qilib saqlaydi
    va rasm manzillari ro'yxatini qaytaradi.
    """
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []
    
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        for i, page in enumerate(pdf):
            # 200 DPI yuqori sifatda rasmga aylantirish (scale=2.77)
            image = page.render(scale=2.77).to_pil()
            img_path = os.path.join(output_dir, f"{base_name}_page_{i+1}.jpg")
            image.save(img_path, format="JPEG", quality=90)
            image_paths.append(img_path)
            
        logger.info(f"PDF muvaffaqiyatli {len(image_paths)} ta rasmga aylantirildi: {pdf_path}")
    except Exception as e:
        logger.error(f"PDF convert error ({pdf_path}): {e}", exc_info=True)
        raise e
        
    return image_paths
