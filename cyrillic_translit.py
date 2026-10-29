# cyrillic_translit.py
"""
O'zbek kirill alifbosini rasmiy lotin alifbosiga 100% to'g'ri o'girish (transliteratsiya) moduli.
O'quvchilar ism-familiyalari, sinf va o'qituvchi ismlari uchun moslashtirilgan.
"""

def to_uzbek_latin(text: str) -> str:
    if not text:
        return ""
    
    # Check if text contains any Cyrillic letters
    if not any('\u0400' <= c <= '\u04FF' for c in text):
        return text

    mapping = {
        'А': 'A', 'а': 'a',
        'Б': 'B', 'б': 'b',
        'В': 'V', 'в': 'v',
        'Г': 'G', 'г': 'g',
        'Д': 'D', 'д': 'd',
        'Ж': 'J', 'ж': 'j',
        'З': 'Z', 'з': 'z',
        'И': 'I', 'и': 'i',
        'Й': 'Y', 'й': 'y',
        'К': 'K', 'к': 'k',
        'Л': 'L', 'л': 'l',
        'М': 'M', 'м': 'm',
        'Н': 'N', 'н': 'n',
        'О': 'O', 'о': 'o',
        'П': 'P', 'п': 'p',
        'Р': 'R', 'р': 'r',
        'С': 'S', 'с': 's',
        'Т': 'T', 'т': 't',
        'У': 'U', 'у': 'u',
        'Ф': 'F', 'ф': 'f',
        'Х': 'X', 'х': 'x',
        'Ц': 'Ts', 'ц': 'ts',
        'Ч': 'Ch', 'ч': 'ch',
        'Ш': 'Sh', 'ш': 'sh',
        'Щ': 'Sh', 'щ': 'sh',
        'Ъ': '’', 'ъ': '’',
        'Ь': '', 'ь': '',
        'Э': 'E', 'э': 'e',
        'Ю': 'Yu', 'ю': 'yu',
        'Я': 'Ya', 'я': 'ya',
        'Ё': 'Yo', 'ё': 'yo',
        'Ў': 'O‘', 'ў': 'o‘',
        'Қ': 'Q', 'қ': 'q',
        'Ғ': 'G‘', 'ғ': 'g‘',
        'Ҳ': 'H', 'ҳ': 'h'
    }

    vowels = set('АЕЁИОУЭЮЯЎаеёиоуэюяў')
    res = []
    words = text.split(' ')
    for w in words:
        w_res = []
        for i, char in enumerate(w):
            if char in ('Е', 'е'):
                if i == 0 or (i > 0 and w[i-1] in vowels):
                    w_res.append('Ye' if char == 'Е' else 'ye')
                else:
                    w_res.append('E' if char == 'Е' else 'e')
            else:
                w_res.append(mapping.get(char, char))
        res.append(''.join(w_res))
    return ' '.join(res)
