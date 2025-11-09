import sqlite3
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo  # < 3.9

from .users import UserField

# IMPORTANT: ordering needs to align with table create
class AccessField(Enum):
    RESOURCE = 'resource'
    ACCESS_KEY = 'access_key'
    ACCESS_TYPE = 'access_type'
    EXPIRES_AT = 'expires_at'
    USER_KEY = 'user_key'
    CREATED_TIMESTAMP = 'created_timestamp'
    LAST_UPDATED_TIMESTAMP = 'last_updated_timestamp'

class AccessType:
    HTTP_SERVER_ACCESS = 1

    @classmethod
    def get_description(cls, access_type):
        return {
            cls.HTTP_SERVER_ACCESS: 'HTTP Server Access',
        }.get(access_type, 'Unknown Access Type')


class Access(ABC):
    # Field name used in API requests to specify expiration time in seconds
    EXPIRE_AFTER_SECONDS = 'expire_after_seconds'
    
    @staticmethod
    def nameStr(access):
        """
        Get a formatted string representation of an access record.
        
        Args:
            access: Access record dictionary
            
        Returns:
            str: Formatted string with resource and access key
        """
        return f"Access to '{access[AccessField.RESOURCE.value]}' with key: '{access[AccessField.ACCESS_KEY.value]}'"
    @abstractmethod
    def create(self, record):
        pass

    @abstractmethod
    def get(self, filters=None):
        pass

    @abstractmethod
    def update(self, record):
        pass

    @abstractmethod
    def delete(self, key):
        pass

    @staticmethod
    def clean(record):
        record = dict(record)
        # Convert expires_at to ISO format if it's a datetime object
        if AccessField.EXPIRES_AT.value in record:
            if record[AccessField.EXPIRES_AT.value] is None:
                # Keep as None for NULL in database
                pass
            elif isinstance(record[AccessField.EXPIRES_AT.value], datetime):
                record[AccessField.EXPIRES_AT.value] = record[AccessField.EXPIRES_AT.value].isoformat()
        return record

    @staticmethod
    def now_in_user_tz(user):
        tz = ZoneInfo(user[UserField.TIMEZONE.value] if user.get(UserField.TIMEZONE.value) else 'UTC')
        return datetime.now(tz)

class SQLLiteAccess(Access):
    def __init__(self, db_path):
        self.db_path = db_path
        self._initialize_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON;')
        return conn

    def _initialize_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS access (
                    {AccessField.RESOURCE.value} TEXT NOT NULL,
                    {AccessField.ACCESS_KEY.value} TEXT NOT NULL,
                    {AccessField.ACCESS_TYPE.value} INTEGER NOT NULL,
                    {AccessField.EXPIRES_AT.value} TIMESTAMP NULL,
                    {AccessField.USER_KEY.value} TEXT NOT NULL,
                    {AccessField.CREATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    {AccessField.LAST_UPDATED_TIMESTAMP.value} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY ({AccessField.USER_KEY.value}) REFERENCES users({UserField.KEY.value}) ON DELETE CASCADE,
                    PRIMARY KEY ({AccessField.RESOURCE.value}, {AccessField.ACCESS_KEY.value})
                )
            ''')
            conn.commit()

    def create(self, record):
        record = dict(record)  # copy
        record = Access.clean(record)
        if AccessField.EXPIRES_AT.value not in record:
            raise ValueError('expires_at must be provided (use None for never expires)')

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO access (
                    {", ".join(record.keys())}
                ) VALUES ({", ".join("?" for _ in record)})
            ''', [v if v is not None else None for v in record.values()])
            conn.commit()
        return record

    def get(self, filters=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            parameters = []
            if filters:
                for entry in filters:
                    if len(entry) == 3:
                        attribute, operator, value = entry
                        if attribute and value is not None:
                            conditions.append(f"{attribute} {operator} ?")
                            parameters.append(value)
                    else:
                        raise ValueError(f"Invalid filter format: {filters}")
            sql_query = 'SELECT * FROM access'
            if conditions:
                sql_query += ' WHERE ' + ' AND '.join(conditions)
            cursor.execute(sql_query, parameters)
            rows = cursor.fetchall()
            if rows:
                return [{field.value: row[i] for i, field in enumerate(AccessField)} for row in rows]
            return []

    def update(self, record):
        record = Access.clean(record)
        required_fields = [AccessField.RESOURCE.value, AccessField.ACCESS_KEY.value]
        for field in required_fields:
            if field not in record:
                raise ValueError(f'Missing required field: {field}')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Get fields to update (all fields except the required ones used in WHERE clause)
            update_fields = [field for field in record.keys() if field not in required_fields]
            set_clause = ", ".join(f"{field} = ?" for field in update_fields)
            
            # Prepare parameters: first the SET values, then the WHERE values
            set_params = [record[field] for field in update_fields]
            where_params = [record[AccessField.RESOURCE.value], record[AccessField.ACCESS_KEY.value]]
            
            cursor.execute(f'''
                UPDATE access SET {set_clause} 
                WHERE {AccessField.RESOURCE.value} = ? AND {AccessField.ACCESS_KEY.value} = ?
            ''', set_params + where_params)
            conn.commit()
        return record

    def delete(self, resource, access_key):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'DELETE FROM access WHERE {AccessField.RESOURCE.value} = ? AND {AccessField.ACCESS_KEY.value} = ?',
                (resource, access_key)
            )
            conn.commit()
        return True

    def validate(self, resource, access_key, user_key=None, now_iso=None):
        """
        Validate if the given resource and access_key combination is valid.
        If user_key is provided, also validates that the access belongs to that user.
        
        Args:
            resource: The resource to validate access for
            access_key: The access key to validate
            user_key: Optional user key to validate ownership
            now_iso: Optional timestamp to use for expiration check (for testing)
            
        Returns:
            dict: The access record if valid, None otherwise
        """
        now_iso = now_iso or datetime.now(ZoneInfo('UTC')).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = f'''
                SELECT * FROM access 
                WHERE {AccessField.RESOURCE.value} = ?
                  AND {AccessField.ACCESS_KEY.value} = ?
                  AND ({AccessField.EXPIRES_AT.value} IS NULL OR {AccessField.EXPIRES_AT.value} > ?)
            '''
            params = [resource, access_key, now_iso]
            
            if user_key:
                query += f' AND {AccessField.USER_KEY.value} = ?'
                params.append(user_key)
                
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            if row:
                return {field.value: row[i] for i, field in enumerate(AccessField)}
            return None
