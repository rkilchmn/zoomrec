import sqlite3
import shortuuid
import os
from enum import Enum
from abc import ABC, abstractmethod
from .msg_telegram import send_telegram_message
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo  # < 3.9
from . import password
from .constants import SFTP_ADMIN_USERNAME, SKIP_SFTP_USER_CREATION
from .sftp_user import create_sftp_user

# IMPORTANT: ordering needs to align with table create
class UserField(Enum):
    KEY = 'key'
    NAME = 'name'
    LOGIN = 'login'
    PASSWORD = 'password'
    TWO_FA_KEY = 'two_fa_key'
    EMAIL = 'email'
    MESSENGER = 'messenger'
    MOBILE_NUMBER = 'mobile_number'
    SFTP_USERNAME = 'sftp_username'
    ROLE = 'role'
    TIMEZONE = 'timezone'
    CREATED_TIMESTAMP = 'created_timestamp'
    LAST_UPDATED_TIMESTAMP = 'last_updated_timestamp'

class UserRole:
    NORMAL = 1
    ADMIN = 2

    @classmethod
    def get_description(cls, role):
        return {
            cls.NORMAL.value: "Normal",
            cls.ADMIN.value: "Admin"
        }.get(role, "Unknown Role")

USER_DEFAULT_VALUES = {
    UserField.ROLE.value: UserRole.NORMAL,
    UserField.EMAIL.value: '',
    UserField.MESSENGER.value: '',
    UserField.MOBILE_NUMBER.value: '',
    UserField.TWO_FA_KEY.value: '',
    UserField.SFTP_USERNAME.value: '',
    UserField.TIMEZONE.value: 'UTC',
}

class MessengerAttribute(Enum):
    TELEGRAM_CHAT_ID = "telegram_chat_id"

INTERNAL_DELIMITER = ',' # don't use : as it is reserved in yaml files

class Users(ABC):
    @abstractmethod
    def create(self, user_data):
        pass

    @abstractmethod
    def get(self, filters=None):
        pass

    @abstractmethod
    def update(self, user):
        pass

    @staticmethod
    def now(user):
        """
        Get current datetime in the user's timezone.
        
        Args:
            user: User dictionary containing TIMEZONE field
            
        Returns:
            datetime: Current datetime in user's timezone
        """
        tz = ZoneInfo(user[UserField.TIMEZONE.value] if user.get(UserField.TIMEZONE.value) else 'UTC')
        return datetime.now(tz)

    @abstractmethod
    def delete(self, user_key):
        pass

    @staticmethod
    def nameStr(user):
        return f"User '{user[UserField.NAME.value]}' with key: '{user[UserField.KEY.value]}'"
    
    def get_messenger_attribute(messenger_attribute: MessengerAttribute, user):
        if UserField.MESSENGER.value in user:
            entries = user[UserField.MESSENGER.value].split(INTERNAL_DELIMITER)
            search_key = f"{messenger_attribute.value}="
            for entry in entries:
                if search_key in entry:
                    return entry.split(search_key)[1]
        return False
    
    @staticmethod
    def set_messenger_attribute(messenger_attribute: MessengerAttribute, value, user):
        if UserField.MESSENGER.value not in user:
            user[UserField.MESSENGER.value] = ''
        entries = user[UserField.MESSENGER.value].split(INTERNAL_DELIMITER)
        search_key = f"{messenger_attribute.value}="
        new_entries = []
        found = False
        for entry in entries:
            if search_key in entry:
                new_entries.append(f"{search_key}{value}")
                found = True
            else:
                new_entries.append(entry)
        if not found:
            new_entries.append(f"{search_key}{value}")
        user[UserField.MESSENGER.value] = INTERNAL_DELIMITER.join(filter(None, new_entries))

    
    @staticmethod
    def clean(user):
        clean_user = {}
        for field in UserField:
            if field.value in user:
                clean_user[field.value] = user[field.value]
        return clean_user
    
    @staticmethod
    def set_missing_defaults(user):
        for fieldname, default_value in USER_DEFAULT_VALUES.items():
            if (fieldname not in user or user[fieldname] is None) and default_value is not None:
                user[fieldname] = default_value
        return user
    
    @staticmethod
    def send_message(user, message):
        for messenger_attribute in MessengerAttribute:
            if messenger_attribute == MessengerAttribute.TELEGRAM_CHAT_ID:
                telegram_chat_id = Users.get_messenger_attribute(messenger_attribute, user)
                if telegram_chat_id:
                    send_telegram_message(telegram_chat_id, message)

    @staticmethod
    def find(search_argument, users):
        matching_indices = []
        for i, user in enumerate(users):
            # Check if search_argument is part of any user field's value, handling both strings and integers
            if any(
                (search_argument.lower() in str(user[field.value]).lower() if isinstance(user[field.value], str) else search_argument == str(user[field.value]))
                for field in UserField
            ):
                matching_indices.append(i)
        
        if not matching_indices:
            raise ValueError(f"No user found for '{search_argument}'")
        
        return matching_indices

    @staticmethod
    def validate(user):
        if not user.get(UserField.NAME.value):
            raise ValueError("Missing required field: name.")
        
        if not user.get(UserField.LOGIN.value):
            raise ValueError("Missing required field: login.")
        else:
            if user.get(UserField.LOGIN.value) == SFTP_ADMIN_USERNAME:
                raise ValueError(f"Invalid login: {SFTP_ADMIN_USERNAME} is reserved.")
        
        if not user.get(UserField.PASSWORD.value):
            raise ValueError("Missing required field: password.")
        
        # Check for at least one of email or messenger detail
        if not user.get(UserField.EMAIL.value) and not user.get(UserField.MESSENGER.value):
            raise ValueError("At least one of the fields 'email' or 'messenger' must be provided.")

        # Validate role if present
        if UserField.ROLE.value in user and user[UserField.ROLE.value] is not None:
            try:
                # Convert role to int if it's a string
                role = int(user[UserField.ROLE.value])
                # Check if role is a valid UserRole value
                valid_roles = [UserRole.NORMAL, UserRole.ADMIN]
                if role not in valid_roles:
                    valid_roles_str = ', '.join(str(r) for r in valid_roles)
                    raise ValueError(f"Invalid role '{role}'. Must be one of: {valid_roles_str}")
                # Update user with integer role
                user[UserField.ROLE.value] = role
            except (ValueError, TypeError) as e:
                raise ValueError(f"Role must be a number. Got: {user[UserField.ROLE.value]}") from e

        return user


class SQLLiteUser(Users):
    def __init__(self, db_path, stateChanged=None):
        self.db_path = db_path
        self.stateChanged = stateChanged  # Initialize the callback
        self._initialize_db()

    def _get_connection(self):
        """Create and return a database connection with foreign key support enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON;')
        return conn

    def _initialize_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # IMPORTANT: order of field needs to align with EventFields order
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS users (
                    {UserField.KEY.value} TEXT PRIMARY KEY,
                    {UserField.NAME.value} TEXT NOT NULL,
                    {UserField.LOGIN.value} TEXT NOT NULL UNIQUE,
                    {UserField.PASSWORD.value} TEXT NOT NULL,
                    {UserField.TWO_FA_KEY.value} TEXT,
                    {UserField.EMAIL.value} TEXT,
                    {UserField.MESSENGER.value} TEXT,
                    {UserField.MOBILE_NUMBER.value} TEXT,
                    {UserField.SFTP_USERNAME.value} TEXT,
                    {UserField.ROLE.value} INTEGER NOT NULL,
                    {UserField.TIMEZONE.value} TEXT DEFAULT 'UTC',
                    {UserField.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    {UserField.LAST_UPDATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def create(self, user):
        user = Users.clean(user)
        user[UserField.PASSWORD.value] = password.hash_password(user[UserField.PASSWORD.value])

        user = Users.set_missing_defaults(user)

        # default sftp username to login
        if user[UserField.SFTP_USERNAME.value] == '':
            user[UserField.SFTP_USERNAME.value] = user[UserField.LOGIN.value]

        user[UserField.KEY.value] = shortuuid.uuid()
        user[UserField.CREATED_TIMESTAMP.value] = Users.now(user).isoformat()
        user[UserField.LAST_UPDATED_TIMESTAMP.value] = user[UserField.CREATED_TIMESTAMP.value]

        # Validate user data
        user = Users.validate(user)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO users (
                    {", ".join(user.keys())}
                ) VALUES ({", ".join("?" for _ in user)})
            ''', list(user.values()))
            conn.commit()

        if os.getenv( SKIP_SFTP_USER_CREATION, "false") == "false":
            if user[UserField.SFTP_USERNAME.value] != '':
                create_sftp_user(user[UserField.SFTP_USERNAME.value])

        # Check for changes and call the callback if necessary
        pre_user = {}
        if self.stateChanged and pre_user != user:
            self.stateChanged(pre_user, user)

        return user

    def get(self, filters=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            parameters = []

            # Check for additional filter queries
            if filters:
                for entry in filters:
                    if len(entry) == 3:  # Ensure the query has three elements
                        attribute, operator, value = entry
                        if attribute and value is not None:
                            conditions.append(f"{attribute} {operator} ?")
                            parameters.append(value)
                    else:
                        raise ValueError(f"Invalid filter format: {filter}")

            # Combine conditions into the SQL query
            sql_query = 'SELECT * FROM users'
            if conditions:
                sql_query += ' WHERE ' + ' AND '.join(conditions)

            cursor.execute(sql_query, parameters)
            rows = cursor.fetchall()
            
            if rows:
                return [{field.value: row[i] for i, field in enumerate(UserField)} for row in rows]
            return []  # Return an empty list if no users are found

    def update(self, user):
        user = Users.clean(user)
        user[UserField.LAST_UPDATED_TIMESTAMP.value] = Users.now(user).isoformat()
        user = Users.validate(user)

        # retrive previous user state before update
        pre_user = self.get(filters=[[UserField.KEY.value, "=", user[UserField.KEY.value]]])
        if len(pre_user) == 0:
            raise ValueError(f"User with key '{user[UserField.KEY.value]}' not found")
        pre_user = pre_user[0]

        # hash password only if password is different and therefore provided in cleartext
        if user[UserField.PASSWORD.value] != pre_user[UserField.PASSWORD.value]:
            user[UserField.PASSWORD.value] = password.hash_password(user[UserField.PASSWORD.value])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join(f"{field} = ?" for field in user.keys())
            cursor.execute(f'''
                UPDATE users SET {set_clause} WHERE {UserField.KEY.value} = ?
            ''', list(user.values()) + [user[UserField.KEY.value]])
            conn.commit()

        if user[UserField.SFTP_USERNAME.value] != pre_user[UserField.SFTP_USERNAME.value] and \
            user[UserField.SFTP_USERNAME.value] != '':
            create_sftp_user(user[UserField.SFTP_USERNAME.value])
            
        # Check for changes and call the callback if necessary
        if self.stateChanged and pre_user != user:
            self.stateChanged(pre_user, user)

        return user


    def delete(self, user_key):
        # retrive previous user state before delete
        pre_user = self.get(filters=[[UserField.KEY.value, "=", user_key]])
        if len(pre_user) == 0:
            raise ValueError(f"User with key '{user_key}' not found")
        pre_user = pre_user[0]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM users WHERE {UserField.KEY.value} = ?', (user_key,))
            conn.commit()

        # Check for changes and call the callback if necessary
        user = {}
        if self.stateChanged and pre_user != user:
            self.stateChanged(pre_user, user)
        
        return True

    