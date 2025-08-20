"""
Order service models for orders, items, and shipment management.
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


class Order(BaseModel):
    """Order model for managing customer orders."""
    
    __tablename__ = 'orders'
    __table_args__ = {'schema': 'orders'}
    
    order_number = Column(String(100), nullable=False, unique=True, index=True)
    deal_id = Column(String(36))  # Reference to deals.deals.uuid
    company_id = Column(String(36))  # Reference to clients.companies.uuid
    contact_id = Column(String(36))  # Reference to clients.contacts.uuid
    
    # Order details
    order_date = Column(Date, default=date.today)
    requested_delivery_date = Column(Date)
    confirmed_delivery_date = Column(Date)
    actual_delivery_date = Column(Date)
    
    # Status and workflow
    status = Column(String(50), default='pending')  # pending, confirmed, processing, shipped, delivered, cancelled
    payment_status = Column(String(50), default='pending')  # pending, partial, paid, overdue, cancelled
    fulfillment_status = Column(String(50), default='pending')  # pending, processing, shipped, delivered, cancelled
    
    # Financial information
    subtotal = Column(DECIMAL(15, 2), default=0)
    tax_amount = Column(DECIMAL(15, 2), default=0)
    shipping_amount = Column(DECIMAL(15, 2), default=0)
    discount_amount = Column(DECIMAL(15, 2), default=0)
    total_amount = Column(DECIMAL(15, 2), default=0)
    currency = Column(String(3), default='USD')
    
    # Payment terms
    payment_terms = Column(String(100))  # net_30, net_60, cod, prepaid, etc.
    payment_due_date = Column(Date)
    
    # Shipping information
    shipping_method = Column(String(100))  # air, sea, land, express, standard
    shipping_address = Column(Text)
    billing_address = Column(Text)
    tracking_number = Column(String(100))
    carrier = Column(String(100))
    
    # Export/Import information
    incoterms = Column(String(20))  # FOB, CIF, EXW, DDP, etc.
    port_of_loading = Column(String(100))
    port_of_discharge = Column(String(100))
    country_of_origin = Column(String(100))
    destination_country = Column(String(100))
    
    # Documentation
    commercial_invoice_number = Column(String(100))
    packing_list_number = Column(String(100))
    bill_of_lading_number = Column(String(100))
    certificate_of_origin_number = Column(String(100))
    
    # Internal tracking
    assigned_to = Column(String(36))  # User UUID from auth service
    priority = Column(String(20), default='medium')  # low, medium, high, urgent
    notes = Column(Text)
    internal_notes = Column(Text)  # Private notes for internal use
    tags = Column(ARRAY(String))
    custom_fields = Column(Text)  # JSON string for custom fields
    
    # Relationships
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    shipments = relationship("OrderShipment", back_populates="order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Order {self.order_number}>'
    
    @property
    def is_overdue(self):
        """Check if order is overdue for delivery."""
        if self.confirmed_delivery_date and self.status not in ['delivered', 'cancelled']:
            return date.today() > self.confirmed_delivery_date
        return False
    
    @property
    def payment_overdue(self):
        """Check if payment is overdue."""
        if self.payment_due_date and self.payment_status not in ['paid', 'cancelled']:
            return date.today() > self.payment_due_date
        return False
    
    @property
    def total_quantity(self):
        """Calculate total quantity of all items."""
        return sum(item.quantity for item in self.items if item.is_active)
    
    @property
    def total_weight(self):
        """Calculate total weight of all items."""
        return sum((item.quantity * (item.unit_weight or 0)) for item in self.items if item.is_active)
    
    def calculate_totals(self):
        """Recalculate order totals based on items."""
        self.subtotal = sum(item.total_price for item in self.items if item.is_active)
        self.total_amount = self.subtotal + (self.tax_amount or 0) + (self.shipping_amount or 0) - (self.discount_amount or 0)
    
    def to_dict(self, include_relationships=True):
        """Convert order to dictionary."""
        data = super().to_dict()
        
        # Convert dates to ISO format
        if self.order_date:
            data['order_date'] = self.order_date.isoformat()
        if self.requested_delivery_date:
            data['requested_delivery_date'] = self.requested_delivery_date.isoformat()
        if self.confirmed_delivery_date:
            data['confirmed_delivery_date'] = self.confirmed_delivery_date.isoformat()
        if self.actual_delivery_date:
            data['actual_delivery_date'] = self.actual_delivery_date.isoformat()
        if self.payment_due_date:
            data['payment_due_date'] = self.payment_due_date.isoformat()
        
        # Add computed fields
        data['is_overdue'] = self.is_overdue
        data['payment_overdue'] = self.payment_overdue
        data['total_quantity'] = self.total_quantity
        data['total_weight'] = self.total_weight
        
        # Convert tags array to list
        if self.tags:
            data['tags'] = list(self.tags)
        
        if include_relationships:
            data['items'] = [item.to_dict(include_relationships=False) for item in self.items if item.is_active]
            data['shipments'] = [shipment.to_dict(include_relationships=False) for shipment in self.shipments if shipment.is_active]
        
        return data


class OrderItem(BaseModel):
    """Order item model for individual products/services in an order."""
    
    __tablename__ = 'order_items'
    __table_args__ = {'schema': 'orders'}
    
    order_id = Column(String(36), ForeignKey('orders.orders.uuid'), nullable=False)
    line_number = Column(Integer, nullable=False)  # Line item number within the order
    
    # Product information
    product_code = Column(String(100))
    product_name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    brand = Column(String(100))
    model = Column(String(100))
    
    # Quantity and pricing
    quantity = Column(DECIMAL(10, 3), nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    total_price = Column(DECIMAL(15, 2), nullable=False)
    currency = Column(String(3), default='USD')
    unit_of_measure = Column(String(20))  # pcs, kg, m, l, etc.
    
    # Discounts
    discount_percent = Column(DECIMAL(5, 2), default=0)
    discount_amount = Column(DECIMAL(10, 2), default=0)
    
    # Physical specifications
    unit_weight = Column(DECIMAL(10, 3))  # Weight per unit
    unit_volume = Column(DECIMAL(10, 3))  # Volume per unit
    dimensions = Column(String(100))  # L x W x H
    
    # Product specifications
    specifications = Column(Text)  # JSON string for detailed specs
    hs_code = Column(String(20))  # Harmonized System code for customs
    country_of_origin = Column(String(100))
    
    # Delivery information
    delivery_status = Column(String(50), default='pending')  # pending, processing, shipped, delivered
    requested_delivery_date = Column(Date)
    confirmed_delivery_date = Column(Date)
    actual_delivery_date = Column(Date)
    
    # Quality and compliance
    quality_grade = Column(String(50))
    certification = Column(String(100))
    batch_number = Column(String(100))
    serial_numbers = Column(ARRAY(String))  # For serialized items
    
    # Internal tracking
    notes = Column(Text)
    tags = Column(ARRAY(String))
    
    # Relationships
    order = relationship("Order", back_populates="items")
    
    def __repr__(self):
        return f'<OrderItem {self.product_name}>'
    
    @property
    def net_price(self):
        """Calculate net price after discount."""
        discount = 0
        if self.discount_amount:
            discount = float(self.discount_amount)
        elif self.discount_percent and self.total_price:
            discount = float(self.total_price) * (float(self.discount_percent) / 100)
        return float(self.total_price) - discount
    
    @property
    def total_weight(self):
        """Calculate total weight for this line item."""
        if self.unit_weight and self.quantity:
            return float(self.unit_weight) * float(self.quantity)
        return 0
    
    @property
    def total_volume(self):
        """Calculate total volume for this line item."""
        if self.unit_volume and self.quantity:
            return float(self.unit_volume) * float(self.quantity)
        return 0
    
    def to_dict(self, include_relationships=True):
        """Convert item to dictionary."""
        data = super().to_dict()
        
        # Convert dates to ISO format
        if self.requested_delivery_date:
            data['requested_delivery_date'] = self.requested_delivery_date.isoformat()
        if self.confirmed_delivery_date:
            data['confirmed_delivery_date'] = self.confirmed_delivery_date.isoformat()
        if self.actual_delivery_date:
            data['actual_delivery_date'] = self.actual_delivery_date.isoformat()
        
        # Add computed fields
        data['net_price'] = self.net_price
        data['total_weight'] = self.total_weight
        data['total_volume'] = self.total_volume
        
        # Convert arrays to lists
        if self.serial_numbers:
            data['serial_numbers'] = list(self.serial_numbers)
        if self.tags:
            data['tags'] = list(self.tags)
        
        if include_relationships and self.order:
            data['order_number'] = self.order.order_number
        
        return data


class OrderShipment(BaseModel):
    """Order shipment model for tracking partial or complete shipments."""
    
    __tablename__ = 'order_shipments'
    __table_args__ = {'schema': 'orders'}
    
    order_id = Column(String(36), ForeignKey('orders.orders.uuid'), nullable=False)
    shipment_number = Column(String(100), nullable=False, unique=True)
    
    # Shipment details
    shipment_date = Column(Date)
    estimated_delivery_date = Column(Date)
    actual_delivery_date = Column(Date)
    
    # Status
    status = Column(String(50), default='preparing')  # preparing, shipped, in_transit, delivered, returned
    
    # Shipping information
    carrier = Column(String(100))
    tracking_number = Column(String(100))
    shipping_method = Column(String(100))
    service_level = Column(String(50))  # standard, express, overnight
    
    # Addresses
    pickup_address = Column(Text)
    delivery_address = Column(Text)
    
    # Package information
    package_count = Column(Integer, default=1)
    total_weight = Column(DECIMAL(10, 3))
    total_volume = Column(DECIMAL(10, 3))
    dimensions = Column(String(100))
    
    # Costs
    shipping_cost = Column(DECIMAL(10, 2))
    insurance_cost = Column(DECIMAL(10, 2))
    customs_value = Column(DECIMAL(15, 2))
    currency = Column(String(3), default='USD')
    
    # Documentation
    waybill_number = Column(String(100))
    commercial_invoice_number = Column(String(100))
    packing_list_number = Column(String(100))
    
    # Customs and compliance
    customs_status = Column(String(50))  # pending, cleared, held, rejected
    customs_reference = Column(String(100))
    duty_amount = Column(DECIMAL(10, 2))
    
    # Internal tracking
    notes = Column(Text)
    special_instructions = Column(Text)
    
    # Relationships
    order = relationship("Order", back_populates="shipments")
    items = relationship("ShipmentItem", back_populates="shipment", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<OrderShipment {self.shipment_number}>'
    
    @property
    def is_overdue(self):
        """Check if shipment is overdue."""
        if self.estimated_delivery_date and self.status not in ['delivered', 'returned']:
            return date.today() > self.estimated_delivery_date
        return False
    
    @property
    def days_in_transit(self):
        """Calculate days in transit."""
        if self.shipment_date and self.status in ['shipped', 'in_transit']:
            return (date.today() - self.shipment_date).days
        elif self.shipment_date and self.actual_delivery_date:
            return (self.actual_delivery_date - self.shipment_date).days
        return 0
    
    def to_dict(self, include_relationships=True):
        """Convert shipment to dictionary."""
        data = super().to_dict()
        
        # Convert dates to ISO format
        if self.shipment_date:
            data['shipment_date'] = self.shipment_date.isoformat()
        if self.estimated_delivery_date:
            data['estimated_delivery_date'] = self.estimated_delivery_date.isoformat()
        if self.actual_delivery_date:
            data['actual_delivery_date'] = self.actual_delivery_date.isoformat()
        
        # Add computed fields
        data['is_overdue'] = self.is_overdue
        data['days_in_transit'] = self.days_in_transit
        
        if include_relationships:
            data['items'] = [item.to_dict(include_relationships=False) for item in self.items if item.is_active]
            if self.order:
                data['order_number'] = self.order.order_number
        
        return data


class ShipmentItem(BaseModel):
    """Shipment item model for tracking which order items are in each shipment."""
    
    __tablename__ = 'shipment_items'
    __table_args__ = {'schema': 'orders'}
    
    shipment_id = Column(String(36), ForeignKey('orders.order_shipments.uuid'), nullable=False)
    order_item_id = Column(String(36), ForeignKey('orders.order_items.uuid'), nullable=False)
    
    # Quantity shipped
    quantity_shipped = Column(DECIMAL(10, 3), nullable=False)
    
    # Package information
    package_number = Column(String(50))
    package_weight = Column(DECIMAL(10, 3))
    package_dimensions = Column(String(100))
    
    # Serial numbers for this shipment
    serial_numbers = Column(ARRAY(String))
    
    # Condition and quality
    condition = Column(String(50), default='good')  # good, damaged, defective
    quality_notes = Column(Text)
    
    # Relationships
    shipment = relationship("OrderShipment", back_populates="items")
    order_item = relationship("OrderItem")
    
    def __repr__(self):
        return f'<ShipmentItem {self.quantity_shipped}>'
    
    def to_dict(self, include_relationships=True):
        """Convert shipment item to dictionary."""
        data = super().to_dict()
        
        # Convert arrays to lists
        if self.serial_numbers:
            data['serial_numbers'] = list(self.serial_numbers)
        
        if include_relationships:
            if self.order_item:
                data['product_name'] = self.order_item.product_name
                data['product_code'] = self.order_item.product_code
            if self.shipment:
                data['shipment_number'] = self.shipment.shipment_number
        
        return data


class OrderDocument(BaseModel):
    """Order documents model for linking documents to orders."""
    
    __tablename__ = 'order_documents'
    __table_args__ = {'schema': 'orders'}
    
    order_id = Column(String(36), ForeignKey('orders.orders.uuid'), nullable=False)
    document_id = Column(String(36))  # Reference to documents.documents.uuid
    document_type = Column(String(50))  # invoice, packing_list, bill_of_lading, certificate, etc.
    title = Column(String(255))
    description = Column(Text)
    document_number = Column(String(100))
    issue_date = Column(Date)
    expiry_date = Column(Date)
    status = Column(String(50), default='draft')  # draft, issued, sent, received, expired
    
    # Relationships
    order = relationship("Order")
    
    def __repr__(self):
        return f'<OrderDocument {self.title}>'
    
    def to_dict(self):
        """Convert document to dictionary."""
        data = super().to_dict()
        
        if self.issue_date:
            data['issue_date'] = self.issue_date.isoformat()
        if self.expiry_date:
            data['expiry_date'] = self.expiry_date.isoformat()
        
        return data


class OrderPayment(BaseModel):
    """Order payment model for tracking payments against orders."""
    
    __tablename__ = 'order_payments'
    __table_args__ = {'schema': 'orders'}
    
    order_id = Column(String(36), ForeignKey('orders.orders.uuid'), nullable=False)
    payment_reference = Column(String(100), nullable=False)
    
    # Payment details
    payment_date = Column(Date, nullable=False)
    amount = Column(DECIMAL(15, 2), nullable=False)
    currency = Column(String(3), default='USD')
    payment_method = Column(String(50))  # wire_transfer, letter_of_credit, cash, check, etc.
    
    # Bank information
    bank_reference = Column(String(100))
    bank_name = Column(String(255))
    account_number = Column(String(100))
    
    # Status
    status = Column(String(50), default='pending')  # pending, confirmed, cleared, rejected
    
    # Notes
    notes = Column(Text)
    
    # Relationships
    order = relationship("Order")
    
    def __repr__(self):
        return f'<OrderPayment {self.payment_reference}>'
    
    def to_dict(self):
        """Convert payment to dictionary."""
        data = super().to_dict()
        
        if self.payment_date:
            data['payment_date'] = self.payment_date.isoformat()
        
        return data

