"""
Authentication and authorization utilities for CRM platform.
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps
from flask import request, jsonify, current_app
import redis
import json


class AuthManager:
    """Handles JWT token generation, validation, and user authentication."""
    
    def __init__(self, secret_key: str, redis_client: Optional[redis.Redis] = None):
        self.secret_key = secret_key
        self.redis_client = redis_client
        self.algorithm = 'HS256'
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    def create_access_token(self, user_data: Dict[str, Any]) -> str:
        """Create a JWT access token."""
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        payload = {
            'user_id': user_data['id'],
            'email': user_data['email'],
            'tenant_id': user_data['tenant_id'],
            'roles': user_data.get('roles', []),
            'exp': expire,
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_data: Dict[str, Any]) -> str:
        """Create a JWT refresh token."""
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        payload = {
            'user_id': user_data['id'],
            'exp': expire,
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Store refresh token in Redis if available
        if self.redis_client:
            self.redis_client.setex(
                f"refresh_token:{user_data['id']}", 
                timedelta(days=self.refresh_token_expire_days),
                token
            )
        
        return token
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def revoke_refresh_token(self, user_id: str):
        """Revoke a refresh token by removing it from Redis."""
        if self.redis_client:
            self.redis_client.delete(f"refresh_token:{user_id}")
    
    def is_refresh_token_valid(self, user_id: str, token: str) -> bool:
        """Check if refresh token is valid and not revoked."""
        if not self.redis_client:
            return True  # If no Redis, assume valid (not recommended for production)
        
        stored_token = self.redis_client.get(f"refresh_token:{user_id}")
        return stored_token and stored_token.decode('utf-8') == token


def require_auth(f):
    """Decorator to require authentication for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid authorization header format'}), 401
        
        if not token:
            return jsonify({'error': 'Authentication token is missing'}), 401
        
        try:
            auth_manager = current_app.auth_manager
            payload = auth_manager.verify_token(token)
            
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            if payload.get('type') != 'access':
                return jsonify({'error': 'Invalid token type'}), 401
            
            # Add user info to request context
            request.current_user = payload
            
        except Exception as e:
            return jsonify({'error': 'Token verification failed'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_roles(*required_roles):
    """Decorator to require specific roles for API endpoints."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401
            
            user_roles = request.current_user.get('roles', [])
            
            if not any(role in user_roles for role in required_roles):
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_tenant_access(f):
    """Decorator to ensure user can only access their tenant's data."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({'error': 'Authentication required'}), 401
        
        # Add tenant_id to kwargs for use in the endpoint
        kwargs['tenant_id'] = request.current_user['tenant_id']
        
        return f(*args, **kwargs)
    
    return decorated_function


class RoleManager:
    """Manages user roles and permissions."""
    
    ROLES = {
        'admin': {
            'description': 'System administrator',
            'permissions': ['*']  # All permissions
        },
        'manager': {
            'description': 'Sales/Export manager',
            'permissions': [
                'clients.read', 'clients.write', 'clients.delete',
                'deals.read', 'deals.write', 'deals.delete',
                'orders.read', 'orders.write', 'orders.delete',
                'documents.read', 'documents.write',
                'analytics.read', 'reports.read'
            ]
        },
        'sales': {
            'description': 'Sales representative',
            'permissions': [
                'clients.read', 'clients.write',
                'deals.read', 'deals.write',
                'orders.read', 'orders.write',
                'documents.read', 'documents.write'
            ]
        },
        'logistics': {
            'description': 'Logistics coordinator',
            'permissions': [
                'clients.read',
                'orders.read', 'orders.write',
                'documents.read', 'documents.write'
            ]
        },
        'finance': {
            'description': 'Finance team member',
            'permissions': [
                'clients.read',
                'deals.read',
                'orders.read',
                'analytics.read', 'reports.read'
            ]
        },
        'support': {
            'description': 'Customer support',
            'permissions': [
                'clients.read', 'clients.write',
                'documents.read'
            ]
        }
    }
    
    @classmethod
    def has_permission(cls, user_roles: list, required_permission: str) -> bool:
        """Check if user has required permission."""
        for role in user_roles:
            if role in cls.ROLES:
                permissions = cls.ROLES[role]['permissions']
                if '*' in permissions or required_permission in permissions:
                    return True
        return False
    
    @classmethod
    def get_role_permissions(cls, role: str) -> list:
        """Get permissions for a specific role."""
        return cls.ROLES.get(role, {}).get('permissions', [])

