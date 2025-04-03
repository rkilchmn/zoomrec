
def convert_to_safe_filename(filename):
    invalid_chars = '\\/:*?"\'<>|'
    safe_filename = ''.join(char for char in filename if char not in invalid_chars)
    safe_filename = safe_filename.strip()
    safe_filename = safe_filename.replace(' ', '_')
    if not safe_filename:
        safe_filename = '_'
    safe_filename = safe_filename[:255]
    return safe_filename

def create_unique_filename(directory_path, basename, extension):
    """
    Creates a unique filename by combining directory path, basename, and extension.
    If the file already exists, adds numerical suffixes (_1, _2, etc.) until a unique name is found.
    
    Args:
        directory_path (str): The directory path where the file will be saved
        basename (str): The base name of the file (without extension)
        extension (str): The file extension (with or without the dot)
    
    Returns:
        str: A unique full path filename
    """
    import os
    
    # Ensure extension starts with a dot
    if extension and not extension.startswith('.'):
        extension = '.' + extension
    
    # Create the initial filename
    filename = os.path.join(directory_path, f"{basename}{extension}")
    
    # If the file doesn't exist, return the filename
    if not os.path.exists(filename):
        return filename
    
    # If the file exists, add numerical suffix
    counter = 1
    while True:
        new_filename = os.path.join(directory_path, f"{basename}_{counter}{extension}")
        if not os.path.exists(new_filename):
            return new_filename
        counter += 1