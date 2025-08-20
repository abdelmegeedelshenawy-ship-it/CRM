"""
Shipment management routes for tracking order fulfillment.
"""

import sys
import os
import json
from datetime import datetime, date
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import and_, or_, func

# Add shared path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'shared'))

from shared.utils.auth import require_auth, require_roles, require_tenant_access
from shared.utils.events import EventPublisher, EventFactory, EventType
from shared.models.base import AuditLog
from src.models.order_models import Order, OrderShipment, ShipmentItem

shipments_bp = Blueprint('shipments', __name__)


@shipments_bp.route('', methods=['GET'])
@require_auth
@require_tenant_access
def get_shipments(tenant_id):
    """Get all shipments for the tenant."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        order_id_filter = request.args.get('order_id', '').strip()
        carrier_filter = request.args.get('carrier', '').strip()
        overdue_only = request.args.get('overdue_only', 'false').lower() == 'true'
        sort_by = request.args.get('sort_by', 'shipment_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Build query
            query = session.query(OrderShipment).filter(
                and_(OrderShipment.tenant_id == tenant_id, OrderShipment.is_active == True)
            )
            
            # Apply filters
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        OrderShipment.shipment_number.ilike(search_term),
                        OrderShipment.tracking_number.ilike(search_term)
                    )
                )
            
            if status_filter:
                query = query.filter(OrderShipment.status == status_filter)
            
            if order_id_filter:
                query = query.filter(OrderShipment.order_id == order_id_filter)
            
            if carrier_filter:
                query = query.filter(OrderShipment.carrier == carrier_filter)
            
            if overdue_only:
                query = query.filter(
                    and_(
                        OrderShipment.estimated_delivery_date < date.today(),
                        OrderShipment.status.notin_(['delivered', 'returned'])
                    )
                )
            
            # Apply sorting
            if sort_by == 'shipment_number':
                sort_column = OrderShipment.shipment_number
            elif sort_by == 'shipment_date':
                sort_column = OrderShipment.shipment_date
            elif sort_by == 'estimated_delivery_date':
                sort_column = OrderShipment.estimated_delivery_date
            elif sort_by == 'status':
                sort_column = OrderShipment.status
            else:
                sort_column = OrderShipment.shipment_date
            
            if sort_order.lower() == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            shipments = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            shipments_data = [shipment.to_dict(include_relationships=True) for shipment in shipments]
            
            return jsonify({
                'shipments': shipments_data,
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
        current_app.logger.error(f"Get shipments error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@shipments_bp.route('', methods=['POST'])
@require_auth
@require_roles('admin', 'manager', 'logistics')
@require_tenant_access
def create_shipment(tenant_id):
    """Create a new shipment."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Validate required fields
        required_fields = ['order_id', 'shipment_number']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Validate order exists
            order = session.query(Order).filter(
                and_(
                    Order.uuid == data['order_id'],
                    Order.tenant_id == tenant_id,
                    Order.is_active == True
                )
            ).first()
            
            if not order:
                return jsonify({'error': 'Order not found'}), 404
            
            # Check if shipment number already exists
            existing_shipment = session.query(OrderShipment).filter(
                and_(
                    OrderShipment.shipment_number == data['shipment_number'],
                    OrderShipment.tenant_id == tenant_id,
                    OrderShipment.is_active == True
                )
            ).first()
            
            if existing_shipment:
                return jsonify({'error': 'Shipment number already exists'}), 409
            
            # Parse dates
            shipment_date = date.today()
            if data.get('shipment_date'):
                shipment_date = datetime.fromisoformat(data['shipment_date']).date()
            
            estimated_delivery_date = None
            if data.get('estimated_delivery_date'):
                estimated_delivery_date = datetime.fromisoformat(data['estimated_delivery_date']).date()
            
            # Create shipment
            shipment = OrderShipment(
                order_id=data['order_id'],
                shipment_number=data['shipment_number'],
                shipment_date=shipment_date,
                estimated_delivery_date=estimated_delivery_date,
                status=data.get('status', 'preparing'),
                carrier=data.get('carrier'),
                tracking_number=data.get('tracking_number'),
                shipping_method=data.get('shipping_method'),
                service_level=data.get('service_level'),
                pickup_address=data.get('pickup_address'),
                delivery_address=data.get('delivery_address'),
                package_count=data.get('package_count', 1),
                total_weight=data.get('total_weight'),
                total_volume=data.get('total_volume'),
                dimensions=data.get('dimensions'),
                shipping_cost=data.get('shipping_cost'),
                insurance_cost=data.get('insurance_cost'),
                customs_value=data.get('customs_value'),
                currency=data.get('currency', 'USD'),
                notes=data.get('notes'),
                special_instructions=data.get('special_instructions'),
                tenant_id=tenant_id,
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            
            session.add(shipment)
            session.flush()  # Get the shipment ID
            
            # Update order fulfillment status
            if order.fulfillment_status == 'pending':
                order.fulfillment_status = 'processing'
                order.updated_by = request.current_user['user_id']
                order.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='shipment',
                entity_id=shipment.uuid,
                action='CREATE',
                new_values=json.dumps(shipment.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish shipment created event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_order_event(
                        EventType.SHIPMENT_CREATED,
                        tenant_id=tenant_id,
                        order_id=data['order_id'],
                        order_data={
                            'shipment_id': shipment.uuid,
                            'shipment_number': shipment.shipment_number,
                            'order_number': order.order_number
                        },
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish shipment created event: {e}")
            
            return jsonify(shipment.to_dict(include_relationships=True)), 201
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Create shipment error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@shipments_bp.route('/<shipment_id>/track', methods=['PUT'])
@require_auth
@require_roles('admin', 'manager', 'logistics')
@require_tenant_access
def update_shipment_tracking(shipment_id, tenant_id):
    """Update shipment tracking information."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get shipment
            shipment = session.query(OrderShipment).filter(
                and_(
                    OrderShipment.uuid == shipment_id,
                    OrderShipment.tenant_id == tenant_id,
                    OrderShipment.is_active == True
                )
            ).first()
            
            if not shipment:
                return jsonify({'error': 'Shipment not found'}), 404
            
            # Store old values for audit
            old_values = shipment.to_dict()
            old_status = shipment.status
            
            # Update tracking fields
            if 'status' in data:
                shipment.status = data['status']
            
            if 'tracking_number' in data:
                shipment.tracking_number = data['tracking_number']
            
            if 'carrier' in data:
                shipment.carrier = data['carrier']
            
            if 'estimated_delivery_date' in data:
                if data['estimated_delivery_date']:
                    shipment.estimated_delivery_date = datetime.fromisoformat(data['estimated_delivery_date']).date()
                else:
                    shipment.estimated_delivery_date = None
            
            if 'actual_delivery_date' in data:
                if data['actual_delivery_date']:
                    shipment.actual_delivery_date = datetime.fromisoformat(data['actual_delivery_date']).date()
                else:
                    shipment.actual_delivery_date = None
            
            if 'customs_status' in data:
                shipment.customs_status = data['customs_status']
            
            if 'notes' in data:
                shipment.notes = data['notes']
            
            shipment.updated_by = request.current_user['user_id']
            shipment.updated_at = datetime.utcnow()
            
            # If status changed to delivered, set actual delivery date
            if 'status' in data and data['status'] == 'delivered' and not shipment.actual_delivery_date:
                shipment.actual_delivery_date = date.today()
                
                # Update order status if all shipments are delivered
                order = shipment.order
                all_delivered = all(s.status == 'delivered' for s in order.shipments if s.is_active)
                if all_delivered:
                    order.status = 'delivered'
                    order.fulfillment_status = 'delivered'
                    order.actual_delivery_date = date.today()
                    order.updated_by = request.current_user['user_id']
                    order.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='shipment',
                entity_id=shipment_id,
                action='UPDATE',
                old_values=json.dumps(old_values),
                new_values=json.dumps(shipment.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish shipment updated event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_order_event(
                        EventType.SHIPMENT_UPDATED,
                        tenant_id=tenant_id,
                        order_id=shipment.order_id,
                        order_data={
                            'shipment_id': shipment.uuid,
                            'old_status': old_status,
                            'new_status': shipment.status,
                            'tracking_number': shipment.tracking_number
                        },
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish shipment updated event: {e}")
            
            return jsonify(shipment.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Update shipment tracking error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@shipments_bp.route('/stats', methods=['GET'])
@require_auth
@require_tenant_access
def get_shipment_stats(tenant_id):
    """Get shipment statistics for the tenant."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get basic counts
            total_shipments = session.query(OrderShipment).filter(
                and_(OrderShipment.tenant_id == tenant_id, OrderShipment.is_active == True)
            ).count()
            
            # Count by status
            status_counts = session.query(
                OrderShipment.status, func.count(OrderShipment.id)
            ).filter(
                and_(OrderShipment.tenant_id == tenant_id, OrderShipment.is_active == True)
            ).group_by(OrderShipment.status).all()
            
            # Count by carrier
            carrier_counts = session.query(
                OrderShipment.carrier, func.count(OrderShipment.id)
            ).filter(
                and_(
                    OrderShipment.tenant_id == tenant_id,
                    OrderShipment.is_active == True,
                    OrderShipment.carrier.isnot(None)
                )
            ).group_by(OrderShipment.carrier).all()
            
            # Overdue shipments
            overdue_shipments = session.query(OrderShipment).filter(
                and_(
                    OrderShipment.tenant_id == tenant_id,
                    OrderShipment.is_active == True,
                    OrderShipment.estimated_delivery_date < date.today(),
                    OrderShipment.status.notin_(['delivered', 'returned'])
                )
            ).count()
            
            # Average delivery time
            avg_delivery_time = session.query(
                func.avg(
                    func.extract('epoch', OrderShipment.actual_delivery_date - OrderShipment.shipment_date) / 86400
                )
            ).filter(
                and_(
                    OrderShipment.tenant_id == tenant_id,
                    OrderShipment.is_active == True,
                    OrderShipment.status == 'delivered',
                    OrderShipment.shipment_date.isnot(None),
                    OrderShipment.actual_delivery_date.isnot(None)
                )
            ).scalar()
            
            return jsonify({
                'total_shipments': total_shipments,
                'overdue_shipments': overdue_shipments,
                'average_delivery_days': float(avg_delivery_time) if avg_delivery_time else 0,
                'by_status': dict(status_counts),
                'by_carrier': dict(carrier_counts)
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get shipment stats error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

