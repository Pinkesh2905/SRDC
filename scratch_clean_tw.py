import os
import re

files_to_clean = [
    r'C:\Projects\SRDC\salesperson\templates\salesperson\dashboard.html',
    r'C:\Projects\SRDC\salesperson\templates\salesperson\detail.html',
    r'C:\Projects\SRDC\customers\templates\customers\customer_detail.html',
    r'C:\Projects\SRDC\customers\templates\customers\customer_list.html',
    r'C:\Projects\SRDC\core\templates\core\dashboard.html',
    r'C:\Projects\SRDC\orders\templates\orders\delivery_schedule.html',
    r'C:\Projects\SRDC\orders\templates\orders\order_detail.html',
    r'C:\Projects\SRDC\orders\templates\orders\order_form.html',
    r'C:\Projects\SRDC\orders\templates\orders\order_list.html',
]

# Remove specific Tailwind background classes that conflict with our CSS variables
# and fix the hover syntax
patterns = [
    (r'bg-slate-100 dark:bg-white/5', ''),
    (r'bg-slate-200 dark:bg-white/10', ''),
    (r'hover:bg-slate-100 dark:bg-white/5', ''),
    (r'hover:bg-slate-100', ''),
    (r'border-slate-300 dark:border-white/10', ''),
    (r'border-slate-200 dark:border-white/5', ''),
]

for filepath in files_to_clean:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    for old, new in patterns:
        content = content.replace(old, new)
    
    # Also fix some specific combined classes
    content = content.replace('class=" "', 'class=""')
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Cleaned: {filepath}")
