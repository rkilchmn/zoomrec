
def convert_to_safe_filename(filename):
    invalid_chars = '\\/:*?"\'<>|'
    safe_filename = ''.join(char for char in filename if char not in invalid_chars)
    safe_filename = safe_filename.strip()
    safe_filename = safe_filename.replace(' ', '_')
    if not safe_filename:
        safe_filename = '_'
    safe_filename = safe_filename[:255]
    return safe_filename