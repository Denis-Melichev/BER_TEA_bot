import re


def extract_price(price_str: str) -> float:
    """
    Извлекает числовое значение цены из строки вроде "1 500 ₽" → 1500.0
    """
    if not price_str:
        return 0.0
    cleaned = re.sub(r'[^\d.,]', '', price_str)
    if not cleaned:
        return 0.0
    if ',' in cleaned and '.' in cleaned:
        cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        cleaned = cleaned.replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
