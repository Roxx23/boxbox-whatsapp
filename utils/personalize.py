import re

def personalize(template: str, row: dict, index: int):
    """
    Replace placeholders in template with row data.
    Supports: {Name}, {name}, {{Name}}, {Phone}, etc.
    """
    if not template:
        return ""
    
    msg = template

    # Build replacements dict with all CSV columns
    replacements = {"index": index}
    
    # Add all CSV columns (case-insensitive)
    for key, value in row.items():
        replacements[key] = str(value) if value is not None else ""

    # Replace {key} format (case-insensitive)
    for key, value in replacements.items():
        # Match {key} with any case
        pattern = re.compile(r'\{' + re.escape(key) + r'\}', re.IGNORECASE)
        # re.sub's replacement argument is itself a pattern string (\1, \g<...>,
        # backslash-escapes) when passed as str -- a customer's own data (e.g. a
        # name/note containing a backslash) would otherwise be interpreted as a
        # regex escape instead of literal text, silently corrupting the message
        # or raising re.error on an invalid escape. A callable replacement is
        # always treated as literal.
        replacement = str(value)
        msg = pattern.sub(lambda m, r=replacement: r, msg)
    
    return msg