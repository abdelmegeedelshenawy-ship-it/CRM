"""
Authentication service models.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import sys
import os

# Add shared path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'shared'))

from shared.models.base import BaseModel


class User(BaseModel):
    """User model for authentication."""
    
    __tablename__ = 'users'
    __table_args__ = {'schema': 'auth'}
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    language = Column(String(10), default='en')
    timezone = Column(String(50), default='UTC')
    last_login = Column(DateTime)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    
    # Relationships
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    @property
    def full_name(self):
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.email
    
    def get_roles(self):
        """Get list of user roles."""
        return [role.role for role in self.roles if role.is_active]
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return role_name in self.get_roles()
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary."""
        data = super().to_dict()
        
        # Remove sensitive information unless explicitly requested
        if not include_sensitive:
            data.pop('password_hash', None)
        
        # Add computed fields
        data['full_name'] = self.full_name
        data['roles'] = self.get_roles()
        
        return data


class UserRole(BaseModel):
    """User role assignment model."""
    
    __tablename__ = 'user_roles'
    __table_args__ = {'schema': 'auth'}
    
    user_id = Column(String(36), ForeignKey('auth.users.uuid'), nullable=False)
    role = Column(String(50), nullable=False)
    granted_by = Column(String(36), ForeignKey('auth.users.uuid'))
    granted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="roles", foreign_keys=[user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by])
    
    def __repr__(self):
        return f'<UserRole {self.user_id}:{self.role}>'
    
    def to_dict(self):
        """Convert user role to dictionary."""
        data = super().to_dict()
        data['granted_at'] = self.granted_at.isoformat() if self.granted_at else None
        return data


class RefreshToken(BaseModel):
    """Refresh token model for token management."""
    
    __tablename__ = 'refresh_tokens'
    __table_args__ = {'schema': 'auth'}
    
    user_id = Column(String(36), ForeignKey('auth.users.uuid'), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime)
    device_info = Column(String(500))  # User agent, IP, etc.
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f'<RefreshToken {self.user_id}>'
    
    def is_valid(self):
        """Check if refresh token is valid."""
        return (
            self.is_active and 
            not self.revoked and 
            self.expires_at > datetime.utcnow()
        )
    
    def revoke(self):
        """Revoke the refresh token."""
        self.revoked = True
        self.revoked_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class LoginAttempt(BaseModel):
    """Login attempt tracking for security."""
    
    __tablename__ = 'login_attempts'
    __table_args__ = {'schema': 'auth'}
    
    email = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500))
    success = Column(Boolean, default=False)
    failure_reason = Column(String(100))
    attempted_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<LoginAttempt {self.email}:{self.success}>'
    
    @classmethod
    def get_recent_failures(cls, session, email: str, minutes: int = 15):
        """Get recent failed login attempts for an email."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        return session.query(cls).filter(
            cls.email == email,
            cls.success == False,
            cls.attempted_at > cutoff_time
        ).count()


class PasswordReset(BaseModel):
    """Password reset token model."""
    
    __tablename__ = 'password_resets'
    __table_args__ = {'schema': 'auth'}
    
    user_id = Column(String(36), ForeignKey('auth.users.uuid'), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    used_at = Column(DateTime)
    ip_address = Column(String(45))
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f'<PasswordReset {self.user_id}>'
    
    def is_valid(self):
        """Check if password reset token is valid."""
        return (
            self.is_active and 
            not self.used and 
            self.expires_at > datetime.utcnow()
        )
    
    def mark_used(self):
        """Mark the password reset token as used."""
        self.used = True
        self.used_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class EmailVerification(BaseModel):
    """Email verification token model."""
    
    __tablename__ = 'email_verifications'
    __table_args__ = {'schema': 'auth'}
    
    user_id = Column(String(36), ForeignKey('auth.users.uuid'), nullable=False)
    email = Column(String(255), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime)
    
    # Relationships
    user = relationship("User")
    
    def __repr__(self):
        return f'<EmailVerification {self.email}>'
    
    def is_valid(self):
        """Check if email verification token is valid."""
        return (
            self.is_active and 
            not self.verified and 
            self.expires_at > datetime.utcnow()
        )
    
    def mark_verified(self):
        """Mark the email as verified."""
        self.verified = True
        self.verified_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

