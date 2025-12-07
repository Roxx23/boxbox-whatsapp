def personalize(template: str, row: dict, index: int):
    msg = template

    replacements = {
        "name": row.get("Name", ""),
        "phone": row.get("Phone", ""),
        "index": index,
    }

    # Add all CSV columns automatically
    for key, value in row.items():
        replacements[key] = value

    for key, value in replacements.items():
        msg = msg.replace(f"{{{key}}}", str(value))

    return msg
