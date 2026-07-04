import re


def normalize_phone(phone):
    if not phone:
        return ''
    phone = phone.strip()
    has_plus = phone.startswith('+')
    digits = re.sub(r'\D+', '', phone)
    if has_plus:
        return f"+{digits}"
    return digits
