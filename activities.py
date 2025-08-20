"""
Deal activity management routes for tracking interactions and tasks.
"""

import sys
import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import and_, or_, func, desc

# Add shared path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'shared'))

from shared.utils.auth import require_auth, require_roles, require_tenant_access
from shared.utils.events import EventPublisher, EventFactory, EventType
from shared.models.base import AuditLog
from src.models.deal_models import Deal, DealActivity

activities_bp = Blueprint('activities', __name__)


@activities_bp.route('', methods=['GET'])
@require_auth
@require_tenant_access
def get_activities(tenant_id):
    """Get all activities for the tenant."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        deal_id = request.args.get('deal_id', '').strip()
        activity_type = request.args.get('activity_type', '').strip()
        completed_filter = request.args.get('completed')
        overdue_only = request.args.get('overdue_only', 'false').lower() == 'true'
        upcoming_only = request.args.get('upcoming_only', 'false').lower() == 'true'
        sort_by = request.args.get('sort_by', 'activity_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Date filters
        activity_after = request.args.get('activity_after')
        activity_before = request.args.get('activity_before')
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Build query
            query = session.query(DealActivity).filter(
                and_(DealActivity.tenant_id == tenant_id, DealActivity.is_active == True)
            )
            
            # Apply filters
            if deal_id:
                query = query.filter(DealActivity.deal_id == deal_id)
            
            if activity_type:
                query = query.filter(DealActivity.activity_type == activity_type)
            
            if completed_filter is not None:
                completed = completed_filter.lower() == 'true'
                query = query.filter(DealActivity.completed == completed)
            
            if overdue_only:
                query = query.filter(
                    and_(
                        DealActivity.completed == False,
                        DealActivity.due_date < datetime.utcnow()
                    )
                )
            
            if upcoming_only:
                query = query.filter(
                    and_(
                        DealActivity.completed == False,
                        DealActivity.due_date >= datetime.utcnow()
                    )
                )
            
            # Date filters
            if activity_after:
                query = query.filter(DealActivity.activity_date >= datetime.fromisoformat(activity_after))
            if activity_before:
                query = query.filter(DealActivity.activity_date <= datetime.fromisoformat(activity_before))
            
            # Apply sorting
            if sort_by == 'activity_date':
                sort_column = DealActivity.activity_date
            elif sort_by == 'due_date':
                sort_column = DealActivity.due_date
            elif sort_by == 'created_at':
                sort_column = DealActivity.created_at
            elif sort_by == 'activity_type':
                sort_column = DealActivity.activity_type
            elif sort_by == 'priority':
                sort_column = DealActivity.priority
            else:
                sort_column = DealActivity.activity_date
            
            if sort_order.lower() == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            activities = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            activities_data = [activity.to_dict(include_relationships=True) for activity in activities]
            
            return jsonify({
                'activities': activities_data,
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
        current_app.logger.error(f"Get activities error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@activities_bp.route('/<activity_id>', methods=['GET'])
@require_auth
@require_tenant_access
def get_activity(activity_id, tenant_id):
    """Get a specific activity by ID."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get activity with deal
            activity = session.query(DealActivity).filter(
                and_(
                    DealActivity.uuid == activity_id,
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True
                )
            ).first()
            
            if not activity:
                return jsonify({'error': 'Activity not found'}), 404
            
            return jsonify(activity.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get activity error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@activities_bp.route('', methods=['POST'])
@require_auth
@require_roles('admin', 'manager', 'sales', 'support')
@require_tenant_access
def create_activity(tenant_id):
    """Create a new activity."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Validate required fields
        required_fields = ['deal_id', 'activity_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Validate deal exists
            deal = session.query(Deal).filter(
                and_(
                    Deal.uuid == data['deal_id'],
                    Deal.tenant_id == tenant_id,
                    Deal.is_active == True
                )
            ).first()
            
            if not deal:
                return jsonify({'error': 'Deal not found'}), 404
            
            # Parse dates
            activity_date = datetime.utcnow()
            if data.get('activity_date'):
                activity_date = datetime.fromisoformat(data['activity_date'])
            
            next_action_date = None
            if data.get('next_action_date'):
                next_action_date = datetime.fromisoformat(data['next_action_date'])
            
            due_date = None
            if data.get('due_date'):
                due_date = datetime.fromisoformat(data['due_date'])
            
            # Create activity
            activity = DealActivity(
                deal_id=data['deal_id'],
                activity_type=data['activity_type'],
                subject=data.get('subject'),
                description=data.get('description'),
                activity_date=activity_date,
                duration_minutes=data.get('duration_minutes'),
                outcome=data.get('outcome'),
                next_action=data.get('next_action'),
                next_action_date=next_action_date,
                completed=data.get('completed', True),
                attendees=data.get('attendees', []),
                location=data.get('location'),
                meeting_type=data.get('meeting_type'),
                due_date=due_date,
                priority=data.get('priority', 'medium'),
                tenant_id=tenant_id,
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            
            session.add(activity)
            session.flush()  # Get the activity ID
            
            # Update deal's updated_at timestamp
            deal.updated_at = datetime.utcnow()
            deal.updated_by = request.current_user['user_id']
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='deal_activity',
                entity_id=activity.uuid,
                action='CREATE',
                new_values=json.dumps(activity.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish activity created event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_deal_event(
                        EventType.DEAL_ACTIVITY_CREATED,
                        tenant_id=tenant_id,
                        deal_id=data['deal_id'],
                        deal_data={
                            'activity_id': activity.uuid,
                            'activity_type': activity.activity_type,
                            'deal_title': deal.title
                        },
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish activity created event: {e}")
            
            return jsonify(activity.to_dict(include_relationships=True)), 201
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Create activity error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@activities_bp.route('/<activity_id>', methods=['PUT'])
@require_auth
@require_roles('admin', 'manager', 'sales', 'support')
@require_tenant_access
def update_activity(activity_id, tenant_id):
    """Update an activity."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get activity
            activity = session.query(DealActivity).filter(
                and_(
                    DealActivity.uuid == activity_id,
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True
                )
            ).first()
            
            if not activity:
                return jsonify({'error': 'Activity not found'}), 404
            
            # Store old values for audit
            old_values = activity.to_dict()
            
            # Update allowed fields
            updatable_fields = [
                'activity_type', 'subject', 'description', 'duration_minutes',
                'outcome', 'next_action', 'completed', 'location', 'meeting_type',
                'priority'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(activity, field, data[field])
            
            # Handle date fields
            if 'activity_date' in data:
                if data['activity_date']:
                    activity.activity_date = datetime.fromisoformat(data['activity_date'])
            
            if 'next_action_date' in data:
                if data['next_action_date']:
                    activity.next_action_date = datetime.fromisoformat(data['next_action_date'])
                else:
                    activity.next_action_date = None
            
            if 'due_date' in data:
                if data['due_date']:
                    activity.due_date = datetime.fromisoformat(data['due_date'])
                else:
                    activity.due_date = None
            
            # Update attendees
            if 'attendees' in data:
                activity.attendees = data['attendees']
            
            activity.updated_by = request.current_user['user_id']
            activity.updated_at = datetime.utcnow()
            
            # Update deal's updated_at timestamp
            if activity.deal:
                activity.deal.updated_at = datetime.utcnow()
                activity.deal.updated_by = request.current_user['user_id']
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='deal_activity',
                entity_id=activity_id,
                action='UPDATE',
                old_values=json.dumps(old_values),
                new_values=json.dumps(activity.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            return jsonify(activity.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Update activity error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@activities_bp.route('/<activity_id>', methods=['DELETE'])
@require_auth
@require_roles('admin', 'manager', 'sales')
@require_tenant_access
def delete_activity(activity_id, tenant_id):
    """Soft delete an activity."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get activity
            activity = session.query(DealActivity).filter(
                and_(
                    DealActivity.uuid == activity_id,
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True
                )
            ).first()
            
            if not activity:
                return jsonify({'error': 'Activity not found'}), 404
            
            # Store old values for audit
            old_values = activity.to_dict()
            
            # Soft delete
            activity.is_active = False
            activity.updated_by = request.current_user['user_id']
            activity.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='deal_activity',
                entity_id=activity_id,
                action='DELETE',
                old_values=json.dumps(old_values),
                new_values='{"is_active": false}',
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            return jsonify({'message': 'Activity deleted successfully'}), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Delete activity error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@activities_bp.route('/<activity_id>/complete', methods=['POST'])
@require_auth
@require_roles('admin', 'manager', 'sales', 'support')
@require_tenant_access
def complete_activity(activity_id, tenant_id):
    """Mark an activity as completed."""
    try:
        data = request.get_json() or {}
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get activity
            activity = session.query(DealActivity).filter(
                and_(
                    DealActivity.uuid == activity_id,
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True
                )
            ).first()
            
            if not activity:
                return jsonify({'error': 'Activity not found'}), 404
            
            # Store old values for audit
            old_values = activity.to_dict()
            
            # Mark as completed
            activity.completed = True
            activity.outcome = data.get('outcome', activity.outcome)
            activity.next_action = data.get('next_action', activity.next_action)
            
            if data.get('next_action_date'):
                activity.next_action_date = datetime.fromisoformat(data['next_action_date'])
            
            activity.updated_by = request.current_user['user_id']
            activity.updated_at = datetime.utcnow()
            
            # Update deal's updated_at timestamp
            if activity.deal:
                activity.deal.updated_at = datetime.utcnow()
                activity.deal.updated_by = request.current_user['user_id']
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='deal_activity',
                entity_id=activity_id,
                action='COMPLETE',
                old_values=json.dumps(old_values),
                new_values=json.dumps(activity.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            return jsonify(activity.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Complete activity error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@activities_bp.route('/upcoming', methods=['GET'])
@require_auth
@require_tenant_access
def get_upcoming_activities(tenant_id):
    """Get upcoming activities for the current user."""
    try:
        # Get query parameters
        days_ahead = int(request.args.get('days_ahead', 7))
        assigned_to = request.args.get('assigned_to', request.current_user['user_id'])
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Calculate date range
            from datetime import timedelta
            end_date = datetime.utcnow() + timedelta(days=days_ahead)
            
            # Get upcoming activities
            activities = session.query(DealActivity).join(Deal).filter(
                and_(
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True,
                    DealActivity.completed == False,
                    DealActivity.due_date.isnot(None),
                    DealActivity.due_date >= datetime.utcnow(),
                    DealActivity.due_date <= end_date,
                    Deal.assigned_to == assigned_to,
                    Deal.is_active == True
                )
            ).order_by(DealActivity.due_date.asc()).all()
            
            # Convert to dict
            activities_data = [activity.to_dict(include_relationships=True) for activity in activities]
            
            return jsonify({
                'activities': activities_data,
                'count': len(activities_data)
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get upcoming activities error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@activities_bp.route('/overdue', methods=['GET'])
@require_auth
@require_tenant_access
def get_overdue_activities(tenant_id):
    """Get overdue activities for the current user."""
    try:
        # Get query parameters
        assigned_to = request.args.get('assigned_to', request.current_user['user_id'])
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get overdue activities
            activities = session.query(DealActivity).join(Deal).filter(
                and_(
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True,
                    DealActivity.completed == False,
                    DealActivity.due_date < datetime.utcnow(),
                    Deal.assigned_to == assigned_to,
                    Deal.is_active == True
                )
            ).order_by(DealActivity.due_date.asc()).all()
            
            # Convert to dict
            activities_data = [activity.to_dict(include_relationships=True) for activity in activities]
            
            return jsonify({
                'activities': activities_data,
                'count': len(activities_data)
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get overdue activities error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@activities_bp.route('/stats', methods=['GET'])
@require_auth
@require_tenant_access
def get_activity_stats(tenant_id):
    """Get activity statistics for the tenant."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get basic counts
            total_activities = session.query(DealActivity).filter(
                and_(DealActivity.tenant_id == tenant_id, DealActivity.is_active == True)
            ).count()
            
            completed_activities = session.query(DealActivity).filter(
                and_(
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True,
                    DealActivity.completed == True
                )
            ).count()
            
            pending_activities = session.query(DealActivity).filter(
                and_(
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True,
                    DealActivity.completed == False
                )
            ).count()
            
            overdue_activities = session.query(DealActivity).filter(
                and_(
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True,
                    DealActivity.completed == False,
                    DealActivity.due_date < datetime.utcnow()
                )
            ).count()
            
            # Count by type
            type_counts = session.query(
                DealActivity.activity_type, func.count(DealActivity.id)
            ).filter(
                and_(DealActivity.tenant_id == tenant_id, DealActivity.is_active == True)
            ).group_by(DealActivity.activity_type).all()
            
            # Count by outcome
            outcome_counts = session.query(
                DealActivity.outcome, func.count(DealActivity.id)
            ).filter(
                and_(
                    DealActivity.tenant_id == tenant_id,
                    DealActivity.is_active == True,
                    DealActivity.completed == True,
                    DealActivity.outcome.isnot(None)
                )
            ).group_by(DealActivity.outcome).all()
            
            return jsonify({
                'total_activities': total_activities,
                'completed_activities': completed_activities,
                'pending_activities': pending_activities,
                'overdue_activities': overdue_activities,
                'completion_rate': (completed_activities / total_activities * 100) if total_activities > 0 else 0,
                'by_type': dict(type_counts),
                'by_outcome': dict(outcome_counts)
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get activity stats error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

