import sqlite3
import json
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo  # >= 3.9
except ImportError:
    from backports.zoneinfo import ZoneInfo  # < 3.9

from .users import UserField, Users


# IMPORTANT: ordering needs to align with table create
class AccessField(Enum):
    RESOURCE = 'resource'
    ACCESS_KEY = 'access_key'
    ACCESS_TYPE = 'access_type'
    EXPIRES_AT = 'expires_at'
    USER_KEY = 'user_key'
    NOTIFY_USER = 'notify_user'
    ADDITIONAL_EMAILS = 'additional_emails'
    DELETE_ON_EXPIRE = 'delete_on_expire'
    CREATED_TIMESTAMP = 'created_timestamp'
    LAST_UPDATED_TIMESTAMP = 'last_updated_timestamp'

ACCESS_DEFAULT_VALUES = {
    AccessField.NOTIFY_USER.value: False,  # Default to not notifying user (becomes 0 in database)
    AccessField.ADDITIONAL_EMAILS.value: None,  # Default to no additional emails
    AccessField.DELETE_ON_EXPIRE.value: False,  # Default to not deleting files on expire
}

class AccessType(Enum):
    HTTP_SERVER_ACCESS = 1

    @classmethod
    def get_description(cls, access_type):
        return {
            cls.HTTP_SERVER_ACCESS.value: 'HTTP Server Access',
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

    @staticmethod
    def validate(access):
        """
        Validate if the access record is valid and not expired.
        
        Args:
            access: The access record dictionary to validate
            
        Returns:
            dict: The access record if valid, None otherwise
            
        Raises:
            ValueError: If required fields are missing from the access record
        """
        if not access:
            return None
            
        # Validate user
        if AccessField.USER_KEY.value in access and access[AccessField.USER_KEY.value] != '':
            pass  # User is valid
        else:
            raise ValueError(f"Missing or empty mandatory attribute {AccessField.USER_KEY.value} or it is empty.")

        # Validate resource
        if AccessField.RESOURCE.value in access and access[AccessField.RESOURCE.value] != '':
            pass  # Resource is valid
        else:
            raise ValueError(f"Missing or empty mandatory attribute {AccessField.RESOURCE.value} or it is empty.")

        # Validate access key
        if AccessField.ACCESS_KEY.value in access and access[AccessField.ACCESS_KEY.value] != '':
            pass  # Access key is valid
        else:
            raise ValueError(f"Missing or empty mandatory attribute {AccessField.ACCESS_KEY.value} or it is empty.")

        # Validate access type
        if AccessField.ACCESS_TYPE.value in access and access[AccessField.ACCESS_TYPE.value] != '':
            pass  # Access type is valid
        else:
            raise ValueError(f"Missing or empty mandatory attribute {AccessField.ACCESS_TYPE.value} or it is empty.")

        # Check expiration in Python
        if AccessField.EXPIRES_AT.value in access:
            expires_at_str = access.get(AccessField.EXPIRES_AT.value)
            if expires_at_str is not None:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                except ValueError:
                    raise ValueError("Invalid expires_at format in access record. Must be in ISO format.")

        # Validate additional_emails
        if AccessField.ADDITIONAL_EMAILS.value in access and access[AccessField.ADDITIONAL_EMAILS.value] is not None:
            additional_emails = access[AccessField.ADDITIONAL_EMAILS.value]
            if not isinstance(additional_emails, list):
                raise ValueError("Invalid additional_emails format. Must be a list of email addresses.")
            
            # Validate each email in the list
            import validators
            for email in additional_emails:
                if not isinstance(email, str) or not validators.email(email):
                    raise ValueError(f"Invalid email address in additional_emails: '{email}'. Must be a valid email address.")

        return access


    @staticmethod
    def set_missing_defaults(access):
        """Set default values for missing fields in access record."""
        for fieldname, default_value in ACCESS_DEFAULT_VALUES.items():
            if (fieldname not in access or access[fieldname] is None) and default_value is not None:
                access[fieldname] = default_value
        return access

    @staticmethod
    def now(access):
        return datetime.now(timezone.utc)
        
    @staticmethod
    def set_expiry(access, expire_after_seconds):
        """
        Handle expiration logic for access requests.
        
        Args:
            access_request: The access dictionary to modify
            expire_after_seconds: Number of seconds from now when access should expire
            
        Returns:
            tuple: (access_request, error_response) where error_response is None if successful
        """
        if expire_after_seconds is not None and expire_after_seconds > 0:
            now = Access.now(access)
            access[AccessField.EXPIRES_AT.value] = (now + timedelta(seconds=expire_after_seconds)).isoformat()
        return access
       
    @abstractmethod
    def create(self, access):
        pass

    @abstractmethod
    def get(self, filters=None):
        pass

    @abstractmethod
    def update(self, access):
        pass

    @abstractmethod
    def delete(self, key):
        pass

    @staticmethod
    def clean(access):
        clean_access = {}
        for field in AccessField:
            if field.value in access:
                clean_access[field.value] = access[field.value]
        return clean_access

class SQLLiteAccess(Access):
    def __init__(self, db_path, stateChanged=None):
        self.db_path = db_path
        self.stateChanged = stateChanged  # Initialize the callback
        self._initialize_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON;')
        return conn

    def _get_schema(self):
        """
        Return the desired schema as a dict of {column_name: (type, constraints)}.
        This is the single source of truth for the table structure.
        """
        return {
            AccessField.RESOURCE.value: ('TEXT', 'NOT NULL'),
            AccessField.ACCESS_KEY.value: ('TEXT', 'NOT NULL'),
            AccessField.ACCESS_TYPE.value: ('INTEGER', 'NOT NULL'),
            AccessField.EXPIRES_AT.value: ('TIMESTAMP', 'NULL'),
            AccessField.USER_KEY.value: ('TEXT', 'NOT NULL'),
            AccessField.NOTIFY_USER.value: ('INTEGER', 'NULL'),
            AccessField.ADDITIONAL_EMAILS.value: ('TEXT', 'NULL'),
            AccessField.DELETE_ON_EXPIRE.value: ('INTEGER', 'NULL'),
            AccessField.CREATED_TIMESTAMP.value: ('TIMESTAMP', 'DEFAULT CURRENT_TIMESTAMP'),
            AccessField.LAST_UPDATED_TIMESTAMP.value: ('TIMESTAMP', 'DEFAULT CURRENT_TIMESTAMP'),
        }

    def _get_constraints(self):
        """
        Return table-specific constraints (foreign keys, primary keys, etc.).
        """
        return [
            f"FOREIGN KEY ({AccessField.USER_KEY.value}) REFERENCES users({UserField.KEY.value}) ON DELETE CASCADE",
            f"PRIMARY KEY ({AccessField.ACCESS_TYPE.value}, {AccessField.RESOURCE.value}, {AccessField.ACCESS_KEY.value})"
        ]

    def _initialize_db(self):
        from shared.db_migration import initialize_table

        with self._get_connection() as conn:
            # Initialize table using generic migration utility
            initialize_table(conn, 'access', self._get_schema(), self._get_constraints())

    def convert_to_internal(self, access):
        """
        Convert data types for specific fields before database insertion.
        
        Args:
            access: The access dictionary to modify
            
        Returns:
            The modified access dictionary
        """
        # Convert notify_user to integer if it's a boolean
        if AccessField.NOTIFY_USER.value in access and access[AccessField.NOTIFY_USER.value] is not None:
            if isinstance(access[AccessField.NOTIFY_USER.value], bool):
                access[AccessField.NOTIFY_USER.value] = 1 if access[AccessField.NOTIFY_USER.value] else 0
        
        # Convert delete_on_expire to integer if it's a boolean
        if AccessField.DELETE_ON_EXPIRE.value in access and access[AccessField.DELETE_ON_EXPIRE.value] is not None:
            if isinstance(access[AccessField.DELETE_ON_EXPIRE.value], bool):
                access[AccessField.DELETE_ON_EXPIRE.value] = 1 if access[AccessField.DELETE_ON_EXPIRE.value] else 0
        
        # Convert additional_emails to JSON string if it's a list
        if AccessField.ADDITIONAL_EMAILS.value in access and access[AccessField.ADDITIONAL_EMAILS.value] is not None:
            if isinstance(access[AccessField.ADDITIONAL_EMAILS.value], list):
                access[AccessField.ADDITIONAL_EMAILS.value] = json.dumps(access[AccessField.ADDITIONAL_EMAILS.value])
        
        return access

    def convert_to_external(self, access):
        """
        Convert data types for specific fields after database retrieval.
        
        Args:
            access: The access dictionary to modify
            
        Returns:
            The modified access dictionary
        """
        # Convert notify_user back to boolean if present
        if AccessField.NOTIFY_USER.value in access and access[AccessField.NOTIFY_USER.value] is not None:
            access[AccessField.NOTIFY_USER.value] = bool(access[AccessField.NOTIFY_USER.value])
        
        # Convert delete_on_expire back to boolean if present
        if AccessField.DELETE_ON_EXPIRE.value in access and access[AccessField.DELETE_ON_EXPIRE.value] is not None:
            access[AccessField.DELETE_ON_EXPIRE.value] = bool(access[AccessField.DELETE_ON_EXPIRE.value])
        
        # Convert additional_emails back from JSON if present
        if AccessField.ADDITIONAL_EMAILS.value in access and access[AccessField.ADDITIONAL_EMAILS.value]:
            try:
                access[AccessField.ADDITIONAL_EMAILS.value] = json.loads(access[AccessField.ADDITIONAL_EMAILS.value])
            except (json.JSONDecodeError, TypeError):
                raise ValueError("Invalid additional_emails format in access record. Must be a JSON string.")

        return access

    def create(self, access):
        access = Access.clean(access)
        access = Access.set_missing_defaults(access)
        Access.validate(access)
        
        # Set timestamps
        access[AccessField.CREATED_TIMESTAMP.value] = Access.now(access).isoformat()
        access[AccessField.LAST_UPDATED_TIMESTAMP.value] = access[AccessField.CREATED_TIMESTAMP.value]  # Set last updated timestamp
        
        # Convert data types
        access_converted = self.convert_to_internal(access)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                INSERT INTO access (
                {", ".join(access_converted.keys())}
            ) VALUES ({", ".join("?" for _ in access_converted)})
            ''', [v if v is not None else None for v in access_converted.values()])
            conn.commit()
        
        # Convert to external format and call callback
        result = self.convert_to_external(access_converted)
        if self.stateChanged:
            self.stateChanged(None, result)
        return result

    def validate_access(self, resource, access_key, access_type):
        access_list = self.get(filters=[[AccessField.RESOURCE.value, '=', resource], [AccessField.ACCESS_KEY.value, '=', access_key], [AccessField.ACCESS_TYPE.value, '=', access_type]])
        if len(access_list) != 1:
            # should only be exactly 1 otherwise somethings wrong
            return None
        else:
            access = access_list[0]
            if access[AccessField.EXPIRES_AT.value] is None:
                # no expiry, always valid
                return access
            else:
                now = Access.now(access)
                expires_at = datetime.fromisoformat(access[AccessField.EXPIRES_AT.value])
                if expires_at > now:
                    # not expired yet
                    return access
                else:
                    # already expired
                    return None

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
                            if attribute not in {f.value for f in AccessField}:
                                raise ValueError(f"Invalid filter field name: '{attribute}'")
                            if operator not in {'=', '!=', '<', '>', '<=', '>=', 'LIKE', 'NOT LIKE', 'IN', 'NOT IN', 'IS', 'IS NOT'}:
                                raise ValueError(f"Invalid filter operator: '{operator}'")
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
                import json
                # Get all field names from AccessField enum
                field_names = [field.value for field in AccessField]
                results = []
                for row in rows:
                    access = {field_names[i]: row[i] for i in range(len(field_names))}
                    # Convert data types for external representation
                    access = self.convert_to_external(access)
                    results.append(access)
                return results
            return []

    def update(self, access):
        access = Access.clean(access)
        access = Access.set_missing_defaults(access)
        Access.validate(access)
        
        access_converted = self.convert_to_internal(access)
        
        # Get old record for callback
        old_records = self.get(filters=[[AccessField.RESOURCE.value, '=', access_converted[AccessField.RESOURCE.value]], 
                                        [AccessField.ACCESS_KEY.value, '=', access_converted[AccessField.ACCESS_KEY.value]], 
                                        [AccessField.ACCESS_TYPE.value, '=', access_converted[AccessField.ACCESS_TYPE.value]]])
        old_record = old_records[0] if old_records else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{key} = ?" for key in access_converted.keys()])
            cursor.execute(f'''
                UPDATE access SET {set_clause} 
                WHERE {AccessField.RESOURCE.value} = ? AND {AccessField.ACCESS_KEY.value} = ? AND {AccessField.ACCESS_TYPE.value} = ?
            ''', list(access_converted.values()) + [access_converted[AccessField.RESOURCE.value], access_converted[AccessField.ACCESS_KEY.value], access_converted[AccessField.ACCESS_TYPE.value]])
            conn.commit()
        
        # Convert to external format and call callback
        result = self.convert_to_external(access_converted)
        if self.stateChanged and old_record:
            self.stateChanged(old_record, result)
        return result

    def delete(self, resource, access_key, access_type):
        if not resource or not access_key or not access_type:
            raise ValueError(f"{AccessField.RESOURCE.value}, {AccessField.ACCESS_KEY.value}, and {AccessField.ACCESS_TYPE.value} are required")

        # Get the access record before deletion for callback
        old_records = self.get(filters=[[AccessField.RESOURCE.value, '=', resource], 
                                       [AccessField.ACCESS_KEY.value, '=', access_key], 
                                       [AccessField.ACCESS_TYPE.value, '=', access_type]])
        if not old_records:
            raise ValueError(f"Access record not found for resource={resource}, access_key={access_key}, access_type={access_type}")
        old_record = old_records[0]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f'DELETE FROM access WHERE {AccessField.RESOURCE.value} = ? AND {AccessField.ACCESS_KEY.value} = ? AND {AccessField.ACCESS_TYPE.value} = ?',
                (resource, access_key, access_type)
            )
            conn.commit()

        # Check if any rows were actually deleted
        if cursor.rowcount == 0:
            raise RuntimeError(f"Failed to delete access record for resource={resource}, access_key={access_key}, access_type={access_type}")

        # Call callback if deletion was successful
        if self.stateChanged and old_record:
            self.stateChanged(old_record, None)

        return True

    
