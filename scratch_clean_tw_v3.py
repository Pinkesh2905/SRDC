import os
import re

patterns = [
    # Backgrounds
    r'\bbg-slate-100\b',
    r'\bbg-white\b',
    r'\bdark:bg-white/5\b',
    r'\bdark:bg-slate-800/50\b',
    r'\bdark:bg-slate-900/50\b',
    
    # Hovers
    r'\bhover:bg-slate-100\b',
    r'\bhover:bg-white\b',
    r'\bhover:bg-white/5\b',
    r'\bhover:bg-white/10\b',
    r'\bhover:bg-slate-50\b',
    
    # Borders
    r'\bborder-slate-200\b',
    r'\bborder-slate-300\b',
    r'\bdark:border-white/5\b',
    r'\bdark:border-white/10\b',
]

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for p in patterns:
        new_content = re.sub(p, '', new_content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

targets = [
    r'c:\Projects\SRDC\orders\templates\orders\order_list.html',
    r'c:\Projects\SRDC\orders\templates\orders\delivery_schedule.html',
    r'c:\Projects\SRDC\salesperson\templates\salesperson\dashboard.html',
    r'c:\Projects\SRDC\customers\templates\customers\customer_list.html',
]

for t in targets:
    if os.path.exists(t):
        if clean_file(t):
            print(f"Cleaned: {t}")
        else:
            print(f"No changes: {t}")
