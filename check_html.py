"""
Check templates/index.html for common syntax errors
"""

import re

print("Checking templates/index.html...")
print("="*60)

errors = []
warnings = []

try:
    with open("templates/index.html", "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")
    
    print(f"✅ File loaded: {len(lines)} lines")
    
    # Check for common JavaScript errors
    print("\n1. Checking JavaScript syntax...")
    
    # Count braces
    open_braces = content.count("{")
    close_braces = content.count("}")
    if open_braces != close_braces:
        errors.append(f"Brace mismatch: {open_braces} open, {close_braces} close")
    else:
        print(f"   ✅ Braces balanced: {open_braces} pairs")
    
    # Count parentheses in <script> sections
    script_start = content.find("<script>")
    script_end = content.rfind("</script>")
    if script_start > 0 and script_end > script_start:
        script_content = content[script_start:script_end]
        open_parens = script_content.count("(")
        close_parens = script_content.count(")")
        if open_parens != close_parens:
            warnings.append(f"Parentheses mismatch in script: {open_parens} open, {close_parens} close")
        else:
            print(f"   ✅ Parentheses balanced: {open_parens} pairs")
    
    # Check for common typos
    print("\n2. Checking for common issues...")
    
    if "});});}" in content:
        errors.append("Found triple closing: '});});}'")
    elif "});})" in content:
        errors.append("Found double closing: '});}'")
    else:
        print("   ✅ No duplicate closing braces found")
    
    # Check for unclosed HTML tags
    print("\n3. Checking HTML tags...")
    div_open = content.count("<div")
    div_close = content.count("</div>")
    if abs(div_open - div_close) > 2:  # Allow small difference for self-closing
        warnings.append(f"Div tag mismatch: {div_open} open, {div_close} close")
    else:
        print(f"   ✅ Div tags roughly balanced: {div_open} open, {div_close} close")
    
    # Check for Jinja2 syntax
    print("\n4. Checking Jinja2 template tags...")
    for_count = len(re.findall(r'{%\s*for\s+', content))
    endfor_count = len(re.findall(r'{%\s*endfor\s*%}', content))
    if for_count != endfor_count:
        errors.append(f"For loop mismatch: {for_count} {% for %}, {endfor_count} {% endfor %}")
    else:
        print(f"   ✅ For loops balanced: {for_count} loops")
    
    if_count = len(re.findall(r'{%\s*if\s+', content))
    endif_count = len(re.findall(r'{%\s*endif\s*%}', content))
    if if_count != endif_count:
        errors.append(f"If statement mismatch: {if_count} {% if %}, {endif_count} {% endif %}")
    else:
        print(f"   ✅ If statements balanced: {if_count} conditions")
    
    # Look for specific problematic patterns
    print("\n5. Checking for problem patterns...")
    problem_patterns = [
        (r'addEventListener\(["\']change["\']\s*,', "Event listeners"),
        (r'fetch\(["\']/', "API fetch calls"),
        (r'getElementById\(["\']', "DOM element access"),
    ]
    
    for pattern, name in problem_patterns:
        matches = len(re.findall(pattern, content))
        if matches > 0:
            print(f"   ✅ {name}: {matches} found")
    
    # Check line 1050-1055 specifically (where we made changes)
    print("\n6. Checking recent changes (lines 1050-1055)...")
    if len(lines) >= 1055:
        for i in range(1049, 1055):
            line = lines[i].strip()
            if line:
                print(f"   Line {i+1}: {line[:60]}...")
    
    print("\n" + "="*60)
    
    if errors:
        print(f"❌ ERRORS FOUND ({len(errors)}):")
        for i, err in enumerate(errors, 1):
            print(f"   {i}. {err}")
    else:
        print("✅ No critical errors found!")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for i, warn in enumerate(warnings, 1):
            print(f"   {i}. {warn}")
    
    if not errors and not warnings:
        print("\n🎉 File looks good!")
    
except FileNotFoundError:
    print("❌ templates/index.html not found!")
except Exception as e:
    print(f"❌ Error checking file: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Check complete!")
