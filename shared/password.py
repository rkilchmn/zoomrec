import bcrypt

def hash_password(plain_password: str) -> str:
    """
    Hashes a password using bcrypt with a generated salt.
    :param plain_password: The plain text password to hash.
    :return: The hashed password as a string.
    """
    # Salting performance (CPU 2025)
    # 12	~40ms
    # 14	~150ms
    # 16	~600ms
    salt = bcrypt.gensalt()  # Generates a new salt using default 12 rounds (good enough for low security web apps)
    hashed_password = bcrypt.hashpw(plain_password.encode(), salt)
    return hashed_password.decode()  # Store as a string

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a password against a given hash.
    :param plain_password: The plain text password to check.
    :param hashed_password: The hashed password to compare against.
    :return: True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())