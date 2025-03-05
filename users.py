import sqlite3
import shortuuid
from enum import Enum
from abc import ABC, abstractmethod
from msg_telegram import send_telegram_message
import constants
from datetime import datetime

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
    CREATED_TIMESTAMP = 'created_timestamp'
    LAST_UPDATED_TIMESTAMP = 'last_updated_timestamp'

class UserRole:
    NORMAL = 1
    ADMIN = 2

USER_DEFAULT_VALUES = {
    UserField.ROLE.value: UserRole.NORMAL,
    UserField.EMAIL.value: '',
    UserField.MESSENGER.value: '',
    UserField.MOBILE_NUMBER.value: '',
    UserField.TWO_FA_KEY.value: '',
    UserField.SFTP_USERNAME.value: '',
}

class MessengerAttribute(Enum):
    TELEGRAM_CHAT_ID = "telegram_chat_id"

INTERNAL_DELIMITER = ',' # don't use : as it is reserved in yaml files

class Users(ABC):
    @abstractmethod
    def create(self, user_data):
        pass

    @abstractmethod
    def get(self, user_key=None, filters=None):
        pass

    @abstractmethod
    def update(self, user_key, updates):
        pass

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
            if fieldname not in user and default_value is not None:
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
        
        if not user.get(UserField.PASSWORD.value):
            raise ValueError("Missing required field: password.")
        
        # Check for at least one of email or messenger detail
        if not user.get(UserField.EMAIL.value) and not user.get(UserField.MESSENGER.value):
            raise ValueError("At least one of the fields 'email' or 'messenger' must be provided.")

        return user


class SQLLiteUser(Users):
    def __init__(self, db_path, stateChanged=None):
        self.db_path = db_path
        self.stateChanged = stateChanged  # Initialize the callback
        self._initialize_db()

    def _initialize_db(self):
        with sqlite3.connect(self.db_path) as conn:
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
                    {UserField.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    {UserField.LAST_UPDATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def create(self, user):
        user = Users.clean(user)
        user = Users.set_missing_defaults(user)
        user[UserField.KEY.value] = shortuuid.uuid()
        user[UserField.CREATED_TIMESTAMP.value] = datetime.now()
        user[UserField.LAST_UPDATED_TIMESTAMP.value] = user[UserField.CREATED_TIMESTAMP.value]

        # Validate user data
        user = Users.validate(user)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO users (
                    {", ".join(user.keys())}
                ) VALUES ({", ".join("?" for _ in user)})
            ''', list(user.values()))
            conn.commit()

        # Check for changes and call the callback if necessary
        old_user = {}
        if self.stateChanged and old_user != user:
            self.stateChanged(old_user, user)

        return user

    def get(self, user_key=None, filters=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            conditions = []
            parameters = []

            # Check for user_key
            if user_key:
                conditions.append(f"{UserField.KEY.value} = ?")
                parameters.append(user_key)

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
        user[UserField.LAST_UPDATED_TIMESTAMP.value] = datetime.now()
        user = Users.validate(user)
        old_user = self.get(user[UserField.KEY.value])
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            set_clause = ", ".join(f"{field} = ?" for field in user.keys())
            cursor.execute(f'''
                UPDATE users SET {set_clause} WHERE {UserField.KEY.value} = ?
            ''', list(user.values()) + [user[UserField.KEY.value]])
            conn.commit()
        
        # Check for changes and call the callback if necessary
        if self.stateChanged and old_user != user:
            self.stateChanged(old_user, user)

        return user


    def delete(self, user_key):
        old_user = self.get(user_key)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'DELETE FROM users WHERE {UserField.KEY.value} = ?', (user_key,))
            conn.commit()

        # Check for changes and call the callback if necessary
        user = {}
        if self.stateChanged and old_user != user:
            self.stateChanged(old_user, user)
        
        return True

    