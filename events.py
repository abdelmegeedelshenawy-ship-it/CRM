"""
Event management utilities for microservices communication.
"""

import json
import pika
import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


class EventType(Enum):
    """Enumeration of event types in the CRM system."""
    
    # Client events
    CLIENT_CREATED = "client.created"
    CLIENT_UPDATED = "client.updated"
    CLIENT_DELETED = "client.deleted"
    
    # Deal events
    DEAL_CREATED = "deal.created"
    DEAL_UPDATED = "deal.updated"
    DEAL_STAGE_CHANGED = "deal.stage_changed"
    DEAL_WON = "deal.won"
    DEAL_LOST = "deal.lost"
    
    # Order events
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    ORDER_SHIPPED = "order.shipped"
    ORDER_DELIVERED = "order.delivered"
    ORDER_CANCELLED = "order.cancelled"
    
    # Document events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_UPDATED = "document.updated"
    DOCUMENT_DELETED = "document.deleted"
    
    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    
    # Notification events
    NOTIFICATION_SEND = "notification.send"
    EMAIL_SEND = "email.send"
    SMS_SEND = "sms.send"
    
    # Compliance events
    AUDIT_LOG = "audit.log"
    COMPLIANCE_CHECK = "compliance.check"


@dataclass
class Event:
    """Base event class for all system events."""
    
    event_type: str
    tenant_id: str
    entity_id: str
    entity_type: str
    data: Dict[str, Any]
    user_id: Optional[str] = None
    timestamp: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Event':
        """Create event from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class EventPublisher:
    """Publishes events to RabbitMQ message broker."""
    
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection = None
        self.channel = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """Establish connection to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(pika.URLParameters(self.rabbitmq_url))
            self.channel = self.connection.channel()
            
            # Declare exchange for events
            self.channel.exchange_declare(
                exchange='crm_events',
                exchange_type='topic',
                durable=True
            )
            
            self.logger.info("Connected to RabbitMQ")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def disconnect(self):
        """Close connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            self.logger.info("Disconnected from RabbitMQ")
    
    def publish(self, event: Event):
        """Publish an event to the message broker."""
        if not self.channel:
            self.connect()
        
        try:
            routing_key = event.event_type
            message = event.to_json()
            
            self.channel.basic_publish(
                exchange='crm_events',
                routing_key=routing_key,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json',
                    headers={
                        'tenant_id': event.tenant_id,
                        'entity_type': event.entity_type,
                        'timestamp': event.timestamp
                    }
                )
            )
            
            self.logger.info(f"Published event: {event.event_type} for {event.entity_type}:{event.entity_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")
            raise
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


class EventSubscriber:
    """Subscribes to events from RabbitMQ message broker."""
    
    def __init__(self, rabbitmq_url: str, service_name: str):
        self.rabbitmq_url = rabbitmq_url
        self.service_name = service_name
        self.connection = None
        self.channel = None
        self.handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """Establish connection to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(pika.URLParameters(self.rabbitmq_url))
            self.channel = self.connection.channel()
            
            # Declare exchange
            self.channel.exchange_declare(
                exchange='crm_events',
                exchange_type='topic',
                durable=True
            )
            
            # Declare queue for this service
            queue_name = f"crm_{self.service_name}_events"
            self.channel.queue_declare(queue=queue_name, durable=True)
            
            self.logger.info(f"Connected to RabbitMQ for service: {self.service_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def disconnect(self):
        """Close connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            self.logger.info("Disconnected from RabbitMQ")
    
    def subscribe(self, event_pattern: str, handler: Callable[[Event], None]):
        """Subscribe to events matching a pattern."""
        self.handlers[event_pattern] = handler
        
        queue_name = f"crm_{self.service_name}_events"
        self.channel.queue_bind(
            exchange='crm_events',
            queue=queue_name,
            routing_key=event_pattern
        )
        
        self.logger.info(f"Subscribed to events: {event_pattern}")
    
    def _handle_message(self, channel, method, properties, body):
        """Handle incoming message."""
        try:
            event = Event.from_json(body.decode('utf-8'))
            
            # Find matching handler
            for pattern, handler in self.handlers.items():
                if self._matches_pattern(event.event_type, pattern):
                    try:
                        handler(event)
                        self.logger.info(f"Handled event: {event.event_type}")
                    except Exception as e:
                        self.logger.error(f"Error handling event {event.event_type}: {e}")
            
            # Acknowledge message
            channel.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            # Reject message and don't requeue
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Check if event type matches subscription pattern."""
        if pattern == '*':
            return True
        if pattern == event_type:
            return True
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return event_type.startswith(prefix)
        return False
    
    def start_consuming(self):
        """Start consuming messages."""
        if not self.channel:
            self.connect()
        
        queue_name = f"crm_{self.service_name}_events"
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=self._handle_message
        )
        
        self.logger.info(f"Started consuming events for service: {self.service_name}")
        self.channel.start_consuming()
    
    def stop_consuming(self):
        """Stop consuming messages."""
        if self.channel:
            self.channel.stop_consuming()
            self.logger.info("Stopped consuming events")


class EventFactory:
    """Factory for creating common events."""
    
    @staticmethod
    def create_client_event(event_type: EventType, tenant_id: str, client_id: str, 
                           client_data: Dict[str, Any], user_id: str = None) -> Event:
        """Create a client-related event."""
        return Event(
            event_type=event_type.value,
            tenant_id=tenant_id,
            entity_id=client_id,
            entity_type='client',
            data=client_data,
            user_id=user_id
        )
    
    @staticmethod
    def create_deal_event(event_type: EventType, tenant_id: str, deal_id: str,
                         deal_data: Dict[str, Any], user_id: str = None) -> Event:
        """Create a deal-related event."""
        return Event(
            event_type=event_type.value,
            tenant_id=tenant_id,
            entity_id=deal_id,
            entity_type='deal',
            data=deal_data,
            user_id=user_id
        )
    
    @staticmethod
    def create_order_event(event_type: EventType, tenant_id: str, order_id: str,
                          order_data: Dict[str, Any], user_id: str = None) -> Event:
        """Create an order-related event."""
        return Event(
            event_type=event_type.value,
            tenant_id=tenant_id,
            entity_id=order_id,
            entity_type='order',
            data=order_data,
            user_id=user_id
        )
    
    @staticmethod
    def create_audit_event(tenant_id: str, entity_type: str, entity_id: str,
                          action: str, old_values: Dict = None, new_values: Dict = None,
                          user_id: str = None) -> Event:
        """Create an audit log event."""
        return Event(
            event_type=EventType.AUDIT_LOG.value,
            tenant_id=tenant_id,
            entity_id=entity_id,
            entity_type=entity_type,
            data={
                'action': action,
                'old_values': old_values,
                'new_values': new_values
            },
            user_id=user_id
        )

