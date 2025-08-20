"""
Order management routes for CRUD operations on orders.
"""

import sys
import os
import json
from datetime import datetime, date
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import joinedload

# Add shared path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'shared'))

from shared.utils.auth import require_auth, require_roles, require_tenant_access
from shared.utils.events import EventPublisher, EventFactory, EventType
from shared.models.base import AuditLog
from src.models.order_models import Order, OrderItem, OrderShipment, OrderDocument, OrderPayment

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('', methods=['GET'])
@require_auth
@require_tenant_access
def get_orders(tenant_id):
    """Get all orders for the tenant."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        payment_status_filter = request.args.get('payment_status', '').strip()
        fulfillment_status_filter = request.args.get('fulfillment_status', '').strip()
        assigned_to_filter = request.args.get('assigned_to', '').strip()
        company_id_filter = request.args.get('company_id', '').strip()
        priority_filter = request.args.get('priority', '').strip()
        overdue_only = request.args.get('overdue_only', 'false').lower() == 'true'
        sort_by = request.args.get('sort_by', 'order_date')
        sort_order = request.args.get('sort_order', 'desc')
        include_items = request.args.get('include_items', 'false').lower() == 'true'
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Build query
            query = session.query(Order).filter(
                and_(Order.tenant_id == tenant_id, Order.is_active == True)
            )
            
            # Apply filters
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Order.order_number.ilike(search_term),
                        Order.notes.ilike(search_term)
                    )
                )
            
            if status_filter:
                query = query.filter(Order.status == status_filter)
            
            if payment_status_filter:
                query = query.filter(Order.payment_status == payment_status_filter)
            
            if fulfillment_status_filter:
                query = query.filter(Order.fulfillment_status == fulfillment_status_filter)
            
            if assigned_to_filter:
                query = query.filter(Order.assigned_to == assigned_to_filter)
            
            if company_id_filter:
                query = query.filter(Order.company_id == company_id_filter)
            
            if priority_filter:
                query = query.filter(Order.priority == priority_filter)
            
            if overdue_only:
                query = query.filter(
                    and_(
                        Order.confirmed_delivery_date < date.today(),
                        Order.status.notin_(['delivered', 'cancelled'])
                    )
                )
            
            # Apply sorting
            if sort_by == 'order_number':
                sort_column = Order.order_number
            elif sort_by == 'order_date':
                sort_column = Order.order_date
            elif sort_by == 'total_amount':
                sort_column = Order.total_amount
            elif sort_by == 'delivery_date':
                sort_column = Order.confirmed_delivery_date
            elif sort_by == 'created_at':
                sort_column = Order.created_at
            elif sort_by == 'updated_at':
                sort_column = Order.updated_at
            else:
                sort_column = Order.order_date
            
            if sort_order.lower() == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Include items if requested
            if include_items:
                query = query.options(joinedload(Order.items))
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            orders = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            orders_data = [order.to_dict(include_relationships=include_items) for order in orders]
            
            return jsonify({
                'orders': orders_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get orders error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/<order_id>', methods=['GET'])
@require_auth
@require_tenant_access
def get_order(order_id, tenant_id):
    """Get a specific order by ID."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get order with items and shipments
            order = session.query(Order).options(
                joinedload(Order.items),
                joinedload(Order.shipments)
            ).filter(
                and_(
                    Order.uuid == order_id,
                    Order.tenant_id == tenant_id,
                    Order.is_active == True
                )
            ).first()
            
            if not order:
                return jsonify({'error': 'Order not found'}), 404
            
            return jsonify(order.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get order error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('', methods=['POST'])
@require_auth
@require_roles('admin', 'manager', 'sales', 'logistics')
@require_tenant_access
def create_order(tenant_id):
    """Create a new order."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Validate required fields
        if not data.get('order_number'):
            return jsonify({'error': 'Order number is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Check if order number already exists
            existing_order = session.query(Order).filter(
                and_(
                    Order.order_number == data['order_number'],
                    Order.tenant_id == tenant_id,
                    Order.is_active == True
                )
            ).first()
            
            if existing_order:
                return jsonify({'error': 'Order number already exists'}), 409
            
            # Parse dates
            order_date = date.today()
            if data.get('order_date'):
                order_date = datetime.fromisoformat(data['order_date']).date()
            
            requested_delivery_date = None
            if data.get('requested_delivery_date'):
                requested_delivery_date = datetime.fromisoformat(data['requested_delivery_date']).date()
            
            confirmed_delivery_date = None
            if data.get('confirmed_delivery_date'):
                confirmed_delivery_date = datetime.fromisoformat(data['confirmed_delivery_date']).date()
            
            payment_due_date = None
            if data.get('payment_due_date'):
                payment_due_date = datetime.fromisoformat(data['payment_due_date']).date()
            
            # Create order
            order = Order(
                order_number=data['order_number'],
                deal_id=data.get('deal_id'),
                company_id=data.get('company_id'),
                contact_id=data.get('contact_id'),
                order_date=order_date,
                requested_delivery_date=requested_delivery_date,
                confirmed_delivery_date=confirmed_delivery_date,
                status=data.get('status', 'pending'),
                payment_status=data.get('payment_status', 'pending'),
                fulfillment_status=data.get('fulfillment_status', 'pending'),
                subtotal=data.get('subtotal', 0),
                tax_amount=data.get('tax_amount', 0),
                shipping_amount=data.get('shipping_amount', 0),
                discount_amount=data.get('discount_amount', 0),
                total_amount=data.get('total_amount', 0),
                currency=data.get('currency', 'USD'),
                payment_terms=data.get('payment_terms'),
                payment_due_date=payment_due_date,
                shipping_method=data.get('shipping_method'),
                shipping_address=data.get('shipping_address'),
                billing_address=data.get('billing_address'),
                incoterms=data.get('incoterms'),
                port_of_loading=data.get('port_of_loading'),
                port_of_discharge=data.get('port_of_discharge'),
                country_of_origin=data.get('country_of_origin'),
                destination_country=data.get('destination_country'),
                assigned_to=data.get('assigned_to', request.current_user['user_id']),
                priority=data.get('priority', 'medium'),
                notes=data.get('notes'),
                internal_notes=data.get('internal_notes'),
                tags=data.get('tags', []),
                custom_fields=json.dumps(data.get('custom_fields', {})),
                tenant_id=tenant_id,
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            
            session.add(order)
            session.flush()  # Get the order ID
            
            # Add order items if provided
            if data.get('items'):
                for item_data in data['items']:
                    item = OrderItem(
                        order_id=order.uuid,
                        line_number=item_data.get('line_number', 1),
                        product_code=item_data.get('product_code'),
                        product_name=item_data['product_name'],
                        description=item_data.get('description'),
                        category=item_data.get('category'),
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                        total_price=item_data['total_price'],
                        currency=item_data.get('currency', 'USD'),
                        unit_of_measure=item_data.get('unit_of_measure'),
                        discount_percent=item_data.get('discount_percent', 0),
                        discount_amount=item_data.get('discount_amount', 0),
                        unit_weight=item_data.get('unit_weight'),
                        specifications=item_data.get('specifications'),
                        hs_code=item_data.get('hs_code'),
                        country_of_origin=item_data.get('country_of_origin'),
                        tenant_id=tenant_id,
                        created_by=request.current_user['user_id'],
                        updated_by=request.current_user['user_id']
                    )
                    session.add(item)
            
            # Recalculate totals
            order.calculate_totals()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='order',
                entity_id=order.uuid,
                action='CREATE',
                new_values=json.dumps(order.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish order created event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_order_event(
                        EventType.ORDER_CREATED,
                        tenant_id=tenant_id,
                        order_id=order.uuid,
                        order_data=order.to_dict(),
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish order created event: {e}")
            
            # Reload order with relationships
            order = session.query(Order).options(
                joinedload(Order.items),
                joinedload(Order.shipments)
            ).filter(Order.uuid == order.uuid).first()
            
            return jsonify(order.to_dict(include_relationships=True)), 201
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Create order error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/<order_id>', methods=['PUT'])
@require_auth
@require_roles('admin', 'manager', 'sales', 'logistics')
@require_tenant_access
def update_order(order_id, tenant_id):
    """Update an order."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get order
            order = session.query(Order).filter(
                and_(
                    Order.uuid == order_id,
                    Order.tenant_id == tenant_id,
                    Order.is_active == True
                )
            ).first()
            
            if not order:
                return jsonify({'error': 'Order not found'}), 404
            
            # Store old values for audit
            old_values = order.to_dict()
            old_status = order.status
            
            # Update allowed fields
            updatable_fields = [
                'status', 'payment_status', 'fulfillment_status', 'subtotal',
                'tax_amount', 'shipping_amount', 'discount_amount', 'total_amount',
                'payment_terms', 'shipping_method', 'shipping_address', 'billing_address',
                'tracking_number', 'carrier', 'incoterms', 'port_of_loading',
                'port_of_discharge', 'country_of_origin', 'destination_country',
                'assigned_to', 'priority', 'notes', 'internal_notes'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(order, field, data[field])
            
            # Handle date fields
            if 'requested_delivery_date' in data:
                if data['requested_delivery_date']:
                    order.requested_delivery_date = datetime.fromisoformat(data['requested_delivery_date']).date()
                else:
                    order.requested_delivery_date = None
            
            if 'confirmed_delivery_date' in data:
                if data['confirmed_delivery_date']:
                    order.confirmed_delivery_date = datetime.fromisoformat(data['confirmed_delivery_date']).date()
                else:
                    order.confirmed_delivery_date = None
            
            if 'actual_delivery_date' in data:
                if data['actual_delivery_date']:
                    order.actual_delivery_date = datetime.fromisoformat(data['actual_delivery_date']).date()
                else:
                    order.actual_delivery_date = None
            
            if 'payment_due_date' in data:
                if data['payment_due_date']:
                    order.payment_due_date = datetime.fromisoformat(data['payment_due_date']).date()
                else:
                    order.payment_due_date = None
            
            # Update tags and custom fields
            if 'tags' in data:
                order.tags = data['tags']
            
            if 'custom_fields' in data:
                order.custom_fields = json.dumps(data['custom_fields'])
            
            order.updated_by = request.current_user['user_id']
            order.updated_at = datetime.utcnow()
            
            # If status changed to delivered, set actual delivery date
            if 'status' in data and data['status'] == 'delivered' and not order.actual_delivery_date:
                order.actual_delivery_date = date.today()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='order',
                entity_id=order_id,
                action='UPDATE',
                old_values=json.dumps(old_values),
                new_values=json.dumps(order.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish order updated event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_order_event(
                        EventType.ORDER_UPDATED,
                        tenant_id=tenant_id,
                        order_id=order.uuid,
                        order_data=order.to_dict(),
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish order updated event: {e}")
            
            return jsonify(order.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Update order error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@orders_bp.route('/stats', methods=['GET'])
@require_auth
@require_tenant_access
def get_order_stats(tenant_id):
    """Get order statistics for the tenant."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get basic counts
            total_orders = session.query(Order).filter(
                and_(Order.tenant_id == tenant_id, Order.is_active == True)
            ).count()
            
            # Count by status
            status_counts = session.query(
                Order.status, func.count(Order.id)
            ).filter(
                and_(Order.tenant_id == tenant_id, Order.is_active == True)
            ).group_by(Order.status).all()
            
            # Count by payment status
            payment_status_counts = session.query(
                Order.payment_status, func.count(Order.id)
            ).filter(
                and_(Order.tenant_id == tenant_id, Order.is_active == True)
            ).group_by(Order.payment_status).all()
            
            # Value statistics
            value_stats = session.query(
                func.sum(Order.total_amount),
                func.avg(Order.total_amount),
                func.max(Order.total_amount),
                func.min(Order.total_amount)
            ).filter(
                and_(Order.tenant_id == tenant_id, Order.is_active == True, Order.total_amount.isnot(None))
            ).first()
            
            # Overdue orders
            overdue_orders = session.query(Order).filter(
                and_(
                    Order.tenant_id == tenant_id,
                    Order.is_active == True,
                    Order.confirmed_delivery_date < date.today(),
                    Order.status.notin_(['delivered', 'cancelled'])
                )
            ).count()
            
            return jsonify({
                'total_orders': total_orders,
                'overdue_orders': overdue_orders,
                'by_status': dict(status_counts),
                'by_payment_status': dict(payment_status_counts),
                'value_stats': {
                    'total': float(value_stats[0]) if value_stats[0] else 0,
                    'average': float(value_stats[1]) if value_stats[1] else 0,
                    'max': float(value_stats[2]) if value_stats[2] else 0,
                    'min': float(value_stats[3]) if value_stats[3] else 0
                }
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get order stats error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

