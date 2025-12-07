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
        msg = pattern.sub(str(value), msg)
    
    return msg