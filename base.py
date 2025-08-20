"""
Base models and database utilities for CRM platform microservices.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, DateTime, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import uuid

Base = declarative_base()


class BaseModel(Base):
    """Base model class with common fields for all entities."""
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100))
    updated_by = Column(String(100))
    is_active = Column(Boolean, default=True)
    tenant_id = Column(String(36), nullable=False)  # For multi-tenancy
    
    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: dict):
        """Update model instance from dictionary."""
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'uuid', 'created_at']:
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()


class TenantModel(BaseModel):
    """Base model for tenant-specific entities."""
    
    __abstract__ = True
    
    @classmethod
    def get_by_tenant(cls, session, tenant_id: str, **filters):
        """Get entities filtered by tenant."""
        query = session.query(cls).filter(cls.tenant_id == tenant_id)
        for key, value in filters.items():
            if hasattr(cls, key):
                query = query.filter(getattr(cls, key) == value)
        return query.all()
    
    @classmethod
    def get_one_by_tenant(cls, session, tenant_id: str, **filters):
        """Get single entity filtered by tenant."""
        query = session.query(cls).filter(cls.tenant_id == tenant_id)
        for key, value in filters.items():
            if hasattr(cls, key):
                query = query.filter(getattr(cls, key) == value)
        return query.first()


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get database session."""
        session = self.SessionLocal()
        try:
            return session
        except Exception:
            session.close()
            raise
    
    def close_session(self, session):
        """Close database session."""
        session.close()


# Audit trail model for compliance
class AuditLog(BaseModel):
    """Audit log for tracking all changes."""
    
    __tablename__ = 'audit_logs'
    
    entity_type = Column(String(100), nullable=False)  # e.g., 'client', 'deal'
    entity_id = Column(String(36), nullable=False)
    action = Column(String(50), nullable=False)  # CREATE, UPDATE, DELETE
    old_values = Column(String)  # JSON string of old values
    new_values = Column(String)  # JSON string of new values
    user_id = Column(String(36))
    ip_address = Column(String(45))
    user_agent = Column(String(500))

