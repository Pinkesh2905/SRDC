import re


def normalize_phone(phone):
    digits = re.sub(r'\D+', '', phone or '')
    if len(digits) > 10 and digits.startswith('91'):
        digits = digits[-10:]
    return digits
