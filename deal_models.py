"""
Deal service models for deals, activities, and pipeline management.
"""

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, DECIMAL, Date
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime, date
import sys
import os

# Add shared path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'shared'))

from shared.models.base import BaseModel


class Deal(BaseModel):
    """Deal/Opportunity model."""
    
    __tablename__ = 'deals'
    __table_args__ = {'schema': 'deals'}
    
    title = Column(String(255), nullable=False)
    description = Column(Text)
    company_id = Column(String(36))  # Reference to clients.companies.uuid
    contact_id = Column(String(36))  # Reference to clients.contacts.uuid
    stage = Column(String(50), default='lead')  # lead, qualified, proposal, negotiation, closed_won, closed_lost
    value = Column(DECIMAL(15, 2))
    currency = Column(String(3), default='USD')
    probability = Column(Integer, default=0)  # 0-100
    expected_close_date = Column(Date)
    actual_close_date = Column(Date)
    source = Column(String(100))  # website, referral, trade_show, cold_call, etc.
    assigned_to = Column(String(36))  # User UUID from auth service
    status = Column(String(50), default='open')  # open, won, lost, cancelled
    priority = Column(String(20), default='medium')  # low, medium, high, urgent
    tags = Column(ARRAY(String))
    custom_fields = Column(Text)  # JSON string for custom fields
    
    # Sales cycle tracking
    lead_score = Column(Integer, default=0)  # 0-100
    qualification_notes = Column(Text)
    competitor_info = Column(Text)
    decision_criteria = Column(Text)
    budget_range = Column(String(100))
    decision_timeframe = Column(String(100))
    
    # Relationships
    activities = relationship("DealActivity", back_populates="deal", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Deal {self.title}>'
    
    @property
    def weighted_value(self):
        """Calculate weighted value based on probability."""
        if self.value and self.probability:
            return float(self.value) * (self.probability / 100)
        return 0
    
    @property
    def days_in_stage(self):
        """Calculate days in current stage."""
        # This would require stage change tracking
        return 0
    
    @property
    def is_overdue(self):
        """Check if deal is overdue."""
        if self.expected_close_date and self.status == 'open':
            return date.today() > self.expected_close_date
        return False
    
    def to_dict(self, include_relationships=True):
        """Convert deal to dictionary."""
        data = super().to_dict()
        
        # Convert dates to ISO format
        if self.expected_close_date:
            data['expected_close_date'] = self.expected_close_date.isoformat()
        if self.actual_close_date:
            data['actual_close_date'] = self.actual_close_date.isoformat()
        
        # Add computed fields
        data['weighted_value'] = self.weighted_value
        data['days_in_stage'] = self.days_in_stage
        data['is_overdue'] = self.is_overdue
        
        # Convert tags array to list
        if self.tags:
            data['tags'] = list(self.tags)
        
        if include_relationships:
            data['activities'] = [activity.to_dict(include_relationships=False) 
                                for activity in self.activities if activity.is_active]
        
        return data


class DealActivity(BaseModel):
    """Deal activity model for tracking interactions and progress."""
    
    __tablename__ = 'deal_activities'
    __table_args__ = {'schema': 'deals'}
    
    deal_id = Column(String(36), ForeignKey('deals.deals.uuid'), nullable=False)
    activity_type = Column(String(50), nullable=False)  # call, email, meeting, note, task, demo
    subject = Column(String(255))
    description = Column(Text)
    activity_date = Column(DateTime, default=datetime.utcnow)
    duration_minutes = Column(Integer)
    outcome = Column(String(100))  # positive, negative, neutral, no_response
    next_action = Column(Text)
    next_action_date = Column(DateTime)
    completed = Column(Boolean, default=True)
    
    # Meeting/Call specific fields
    attendees = Column(ARRAY(String))  # Array of contact UUIDs or names
    location = Column(String(255))
    meeting_type = Column(String(50))  # in_person, phone, video, demo
    
    # Task specific fields
    due_date = Column(DateTime)
    priority = Column(String(20), default='medium')  # low, medium, high, urgent
    
    # Relationships
    deal = relationship("Deal", back_populates="activities")
    
    def __repr__(self):
        return f'<DealActivity {self.activity_type}:{self.subject}>'
    
    @property
    def is_overdue(self):
        """Check if activity is overdue."""
        if not self.completed and self.due_date:
            return datetime.utcnow() > self.due_date
        return False
    
    def to_dict(self, include_relationships=True):
        """Convert activity to dictionary."""
        data = super().to_dict()
        
        # Convert dates to ISO format
        if self.activity_date:
            data['activity_date'] = self.activity_date.isoformat()
        if self.next_action_date:
            data['next_action_date'] = self.next_action_date.isoformat()
        if self.due_date:
            data['due_date'] = self.due_date.isoformat()
        
        # Add computed fields
        data['is_overdue'] = self.is_overdue
        
        # Convert attendees array to list
        if self.attendees:
            data['attendees'] = list(self.attendees)
        
        if include_relationships and self.deal:
            data['deal_title'] = self.deal.title
            data['deal_id'] = self.deal.uuid
        
        return data


class DealStage(BaseModel):
    """Deal stage configuration model for pipeline customization."""
    
    __tablename__ = 'deal_stages'
    __table_args__ = {'schema': 'deals'}
    
    name = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    order_index = Column(Integer, nullable=False)
    probability_default = Column(Integer, default=0)  # Default probability for this stage
    color = Column(String(7))  # Hex color code
    is_closed = Column(Boolean, default=False)  # Whether this is a closed stage
    is_won = Column(Boolean, default=False)  # Whether this represents a win
    
    # Stage requirements
    required_fields = Column(ARRAY(String))  # Fields required to move to this stage
    required_activities = Column(ARRAY(String))  # Activity types required
    
    def __repr__(self):
        return f'<DealStage {self.display_name}>'
    
    def to_dict(self):
        """Convert stage to dictionary."""
        data = super().to_dict()
        
        # Convert arrays to lists
        if self.required_fields:
            data['required_fields'] = list(self.required_fields)
        if self.required_activities:
            data['required_activities'] = list(self.required_activities)
        
        return data


class DealProduct(BaseModel):
    """Deal products model for tracking products/services in deals."""
    
    __tablename__ = 'deal_products'
    __table_args__ = {'schema': 'deals'}
    
    deal_id = Column(String(36), ForeignKey('deals.deals.uuid'), nullable=False)
    product_code = Column(String(100))
    product_name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    quantity = Column(DECIMAL(10, 3), default=1)
    unit_price = Column(DECIMAL(10, 2))
    total_price = Column(DECIMAL(15, 2))
    currency = Column(String(3), default='USD')
    unit_of_measure = Column(String(20))
    discount_percent = Column(DECIMAL(5, 2), default=0)
    discount_amount = Column(DECIMAL(10, 2), default=0)
    
    # Product specifications
    specifications = Column(Text)  # JSON string
    delivery_terms = Column(String(100))
    warranty_terms = Column(String(100))
    
    # Relationships
    deal = relationship("Deal")
    
    def __repr__(self):
        return f'<DealProduct {self.product_name}>'
    
    @property
    def net_price(self):
        """Calculate net price after discount."""
        if self.total_price:
            discount = 0
            if self.discount_amount:
                discount = float(self.discount_amount)
            elif self.discount_percent and self.total_price:
                discount = float(self.total_price) * (float(self.discount_percent) / 100)
            return float(self.total_price) - discount
        return 0
    
    def to_dict(self):
        """Convert product to dictionary."""
        data = super().to_dict()
        data['net_price'] = self.net_price
        return data


class DealNote(BaseModel):
    """Deal notes model for storing important information."""
    
    __tablename__ = 'deal_notes'
    __table_args__ = {'schema': 'deals'}
    
    deal_id = Column(String(36), ForeignKey('deals.deals.uuid'), nullable=False)
    note_type = Column(String(50), default='general')  # general, important, warning, opportunity, competitor
    title = Column(String(255))
    content = Column(Text, nullable=False)
    is_private = Column(Boolean, default=False)  # Private to the user who created it
    priority = Column(String(20), default='normal')  # low, normal, high, urgent
    reminder_date = Column(DateTime)
    reminder_completed = Column(Boolean, default=False)
    
    # Relationships
    deal = relationship("Deal")
    
    def __repr__(self):
        return f'<DealNote {self.title}>'
    
    def to_dict(self):
        """Convert note to dictionary."""
        data = super().to_dict()
        
        if self.reminder_date:
            data['reminder_date'] = self.reminder_date.isoformat()
        
        return data


class DealDocument(BaseModel):
    """Deal documents model for linking documents to deals."""
    
    __tablename__ = 'deal_documents'
    __table_args__ = {'schema': 'deals'}
    
    deal_id = Column(String(36), ForeignKey('deals.deals.uuid'), nullable=False)
    document_id = Column(String(36))  # Reference to documents.documents.uuid
    document_type = Column(String(50))  # proposal, contract, presentation, quote, etc.
    title = Column(String(255))
    description = Column(Text)
    version = Column(String(20))
    status = Column(String(50), default='draft')  # draft, sent, signed, approved, rejected
    sent_date = Column(DateTime)
    response_date = Column(DateTime)
    
    # Relationships
    deal = relationship("Deal")
    
    def __repr__(self):
        return f'<DealDocument {self.title}>'
    
    def to_dict(self):
        """Convert document to dictionary."""
        data = super().to_dict()
        
        if self.sent_date:
            data['sent_date'] = self.sent_date.isoformat()
        if self.response_date:
            data['response_date'] = self.response_date.isoformat()
        
        return data

