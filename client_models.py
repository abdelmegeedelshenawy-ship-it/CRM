"""
Client service models for companies, addresses, and contacts.
"""

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime
import sys
import os

# Add shared path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'shared'))

from shared.models.base import BaseModel


class Company(BaseModel):
    """Company/Client model."""
    
    __tablename__ = 'companies'
    __table_args__ = {'schema': 'clients'}
    
    name = Column(String(255), nullable=False, index=True)
    legal_name = Column(String(255))
    industry = Column(String(100))
    company_type = Column(String(50))  # distributor, importer, wholesaler, retailer
    website = Column(String(255))
    phone = Column(String(20))
    email = Column(String(255))
    tax_id = Column(String(100))
    vat_number = Column(String(100))
    registration_number = Column(String(100))
    founded_year = Column(Integer)
    employee_count = Column(Integer)
    annual_revenue = Column(DECIMAL(15, 2))
    currency = Column(String(3), default='USD')
    status = Column(String(50), default='active')  # active, prospect, inactive, blacklisted
    source = Column(String(100))  # website, referral, trade_show, cold_call, etc.
    assigned_to = Column(String(36))  # User UUID from auth service
    notes = Column(Text)
    tags = Column(ARRAY(String))
    custom_fields = Column(Text)  # JSON string for custom fields
    
    # Relationships
    addresses = relationship("CompanyAddress", back_populates="company", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Company {self.name}>'
    
    @property
    def primary_address(self):
        """Get primary address for the company."""
        for address in self.addresses:
            if address.is_primary and address.is_active:
                return address
        return None
    
    @property
    def primary_contact(self):
        """Get primary contact for the company."""
        for contact in self.contacts:
            if contact.is_primary and contact.is_active:
                return contact
        return None
    
    def to_dict(self, include_relationships=True):
        """Convert company to dictionary."""
        data = super().to_dict()
        
        if include_relationships:
            data['addresses'] = [addr.to_dict(include_relationships=False) for addr in self.addresses if addr.is_active]
            data['contacts'] = [contact.to_dict(include_relationships=False) for contact in self.contacts if contact.is_active]
            data['primary_address'] = self.primary_address.to_dict(include_relationships=False) if self.primary_address else None
            data['primary_contact'] = self.primary_contact.to_dict(include_relationships=False) if self.primary_contact else None
        
        # Convert tags array to list
        if self.tags:
            data['tags'] = list(self.tags)
        
        return data


class CompanyAddress(BaseModel):
    """Company address model."""
    
    __tablename__ = 'company_addresses'
    __table_args__ = {'schema': 'clients'}
    
    company_id = Column(String(36), ForeignKey('clients.companies.uuid'), nullable=False)
    address_type = Column(String(50), default='business')  # business, billing, shipping, warehouse
    street_address = Column(Text)
    city = Column(String(100))
    state_province = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100))
    is_primary = Column(Boolean, default=False)
    
    # Relationships
    company = relationship("Company", back_populates="addresses")
    
    def __repr__(self):
        return f'<CompanyAddress {self.company_id}:{self.address_type}>'
    
    @property
    def formatted_address(self):
        """Get formatted address string."""
        parts = []
        if self.street_address:
            parts.append(self.street_address)
        if self.city:
            parts.append(self.city)
        if self.state_province:
            parts.append(self.state_province)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(self.country)
        return ', '.join(parts)
    
    def to_dict(self, include_relationships=True):
        """Convert address to dictionary."""
        data = super().to_dict()
        data['formatted_address'] = self.formatted_address
        
        if include_relationships and self.company:
            data['company_name'] = self.company.name
        
        return data


class Contact(BaseModel):
    """Contact person model."""
    
    __tablename__ = 'contacts'
    __table_args__ = {'schema': 'clients'}
    
    company_id = Column(String(36), ForeignKey('clients.companies.uuid'))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    title = Column(String(100))
    department = Column(String(100))
    email = Column(String(255), index=True)
    phone = Column(String(20))
    mobile = Column(String(20))
    linkedin_url = Column(String(255))
    preferred_language = Column(String(10), default='en')
    preferred_contact_method = Column(String(50), default='email')  # email, phone, mobile, linkedin
    is_primary = Column(Boolean, default=False)
    notes = Column(Text)
    tags = Column(ARRAY(String))
    custom_fields = Column(Text)  # JSON string for custom fields
    
    # Relationships
    company = relationship("Company", back_populates="contacts")
    
    def __repr__(self):
        return f'<Contact {self.full_name}>'
    
    @property
    def full_name(self):
        """Get contact's full name."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def display_name(self):
        """Get display name with title if available."""
        if self.title:
            return f"{self.full_name}, {self.title}"
        return self.full_name
    
    def to_dict(self, include_relationships=True):
        """Convert contact to dictionary."""
        data = super().to_dict()
        data['full_name'] = self.full_name
        data['display_name'] = self.display_name
        
        if include_relationships and self.company:
            data['company_name'] = self.company.name
            data['company_id'] = self.company.uuid
        
        # Convert tags array to list
        if self.tags:
            data['tags'] = list(self.tags)
        
        return data


class CommunicationLog(BaseModel):
    """Communication log for tracking interactions with clients."""
    
    __tablename__ = 'communication_logs'
    __table_args__ = {'schema': 'clients'}
    
    company_id = Column(String(36), ForeignKey('clients.companies.uuid'))
    contact_id = Column(String(36), ForeignKey('clients.contacts.uuid'))
    communication_type = Column(String(50), nullable=False)  # email, phone, meeting, note
    subject = Column(String(255))
    content = Column(Text)
    direction = Column(String(20))  # inbound, outbound
    communication_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(36))  # User who logged the communication
    attachments = Column(ARRAY(String))  # Array of document UUIDs
    follow_up_date = Column(DateTime)
    follow_up_completed = Column(Boolean, default=False)
    
    # Relationships
    company = relationship("Company")
    contact = relationship("Contact")
    
    def __repr__(self):
        return f'<CommunicationLog {self.communication_type}:{self.subject}>'
    
    def to_dict(self):
        """Convert communication log to dictionary."""
        data = super().to_dict()
        
        if self.communication_date:
            data['communication_date'] = self.communication_date.isoformat()
        if self.follow_up_date:
            data['follow_up_date'] = self.follow_up_date.isoformat()
        
        # Convert attachments array to list
        if self.attachments:
            data['attachments'] = list(self.attachments)
        
        return data


class ClientNote(BaseModel):
    """Client notes model for storing important information."""
    
    __tablename__ = 'client_notes'
    __table_args__ = {'schema': 'clients'}
    
    company_id = Column(String(36), ForeignKey('clients.companies.uuid'))
    contact_id = Column(String(36), ForeignKey('clients.contacts.uuid'))
    note_type = Column(String(50), default='general')  # general, important, warning, opportunity
    title = Column(String(255))
    content = Column(Text, nullable=False)
    is_private = Column(Boolean, default=False)  # Private to the user who created it
    priority = Column(String(20), default='normal')  # low, normal, high, urgent
    reminder_date = Column(DateTime)
    reminder_completed = Column(Boolean, default=False)
    
    # Relationships
    company = relationship("Company")
    contact = relationship("Contact")
    
    def __repr__(self):
        return f'<ClientNote {self.title}>'
    
    def to_dict(self):
        """Convert client note to dictionary."""
        data = super().to_dict()
        
        if self.reminder_date:
            data['reminder_date'] = self.reminder_date.isoformat()
        
        return data

