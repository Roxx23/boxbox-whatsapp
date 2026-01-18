# User authentication and management
import os
import json
import bcrypt
from datetime import datetime

class User:
    """User model for authentication"""
    
    def __init__(self, user_id, username, email, password_hash, created_at=None):
        self.id = user_id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at or datetime.now().isoformat()
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def get_id(self):
        """Required by Flask-Login"""
        return str(self.id)
    
    def check_password(self, password):
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash,
            'created_at': self.created_at
        }
    
    @staticmethod
    def from_dict(data):
        """Create user from dictionary"""
        return User(
            user_id=data['id'],
            username=data['username'],
            email=data['email'],
            password_hash=data['password_hash'],
            created_at=data.get('created_at')
        )


class UserManager:
    """Manage users in JSON file"""
    
    def __init__(self, users_file=None):
        # Support persistent storage for users file
        if users_file is None:
            users_file = os.getenv('USERS_FILE_PATH', 'users.json')
        
        # Ensure directory exists
        users_dir = os.path.dirname(users_file)
        if users_dir and not os.path.exists(users_dir):
            os.makedirs(users_dir, exist_ok=True)
        
        self.users_file = users_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create users file if it doesn't exist"""
        if not os.path.exists(self.users_file):
            self._save_users({})
    
    def _load_users(self):
        """Load users from file"""
        try:
            with open(self.users_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _save_users(self, users_dict):
        """Save users to file"""
        with open(self.users_file, 'w') as f:
            json.dump(users_dict, f, indent=2)
    
    def create_user(self, username, email, password):
        """Create a new user"""
        users = self._load_users()
        
        # Check if username or email already exists
        for user_data in users.values():
            if user_data['username'].lower() == username.lower():
                return None, "Username already exists"
            if user_data['email'].lower() == email.lower():
                return None, "Email already exists"
        
        # Generate user ID
        user_id = str(len(users) + 1)
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user
        user = User(user_id, username, email, password_hash)
        
        # Save to file
        users[user_id] = user.to_dict()
        self._save_users(users)
        
        return user, None
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        users = self._load_users()
        user_data = users.get(str(user_id))
        if user_data:
            return User.from_dict(user_data)
        return None
    
    def get_user_by_username(self, username):
        """Get user by username"""
        users = self._load_users()
        for user_data in users.values():
            if user_data['username'].lower() == username.lower():
                return User.from_dict(user_data)
        return None
    
    def get_user_by_email(self, email):
        """Get user by email"""
        users = self._load_users()
        for user_data in users.values():
            if user_data['email'].lower() == email.lower():
                return User.from_dict(user_data)
        return None
    
    def authenticate(self, username, password):
        """Authenticate user with username/email and password"""
        # Try username first
        user = self.get_user_by_username(username)
        if not user:
            # Try email
            user = self.get_user_by_email(username)
        
        if user and user.check_password(password):
            return user
        return None
    
    def get_all_users(self):
        """Get all users (for admin purposes)"""
        users = self._load_users()
        return [User.from_dict(data) for data in users.values()]
    
    def user_count(self):
        """Get total number of users"""
        users = self._load_users()
        return len(users)
