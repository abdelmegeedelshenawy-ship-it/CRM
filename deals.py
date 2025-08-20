"""
Deal management routes for CRUD operations on deals.
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
from src.models.deal_models import Deal, DealActivity, DealStage, DealProduct, DealNote, DealDocument

deals_bp = Blueprint('deals', __name__)


@deals_bp.route('', methods=['GET'])
@require_auth
@require_tenant_access
def get_deals(tenant_id):
    """Get all deals for the tenant."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        search = request.args.get('search', '').strip()
        stage_filter = request.args.get('stage', '').strip()
        status_filter = request.args.get('status', '').strip()
        assigned_to_filter = request.args.get('assigned_to', '').strip()
        company_id_filter = request.args.get('company_id', '').strip()
        priority_filter = request.args.get('priority', '').strip()
        overdue_only = request.args.get('overdue_only', 'false').lower() == 'true'
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_order = request.args.get('sort_order', 'desc')
        include_activities = request.args.get('include_activities', 'false').lower() == 'true'
        
        # Date filters
        created_after = request.args.get('created_after')
        created_before = request.args.get('created_before')
        expected_close_after = request.args.get('expected_close_after')
        expected_close_before = request.args.get('expected_close_before')
        
        # Value filters
        min_value = request.args.get('min_value')
        max_value = request.args.get('max_value')
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Build query
            query = session.query(Deal).filter(
                and_(Deal.tenant_id == tenant_id, Deal.is_active == True)
            )
            
            # Apply filters
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Deal.title.ilike(search_term),
                        Deal.description.ilike(search_term)
                    )
                )
            
            if stage_filter:
                query = query.filter(Deal.stage == stage_filter)
            
            if status_filter:
                query = query.filter(Deal.status == status_filter)
            
            if assigned_to_filter:
                query = query.filter(Deal.assigned_to == assigned_to_filter)
            
            if company_id_filter:
                query = query.filter(Deal.company_id == company_id_filter)
            
            if priority_filter:
                query = query.filter(Deal.priority == priority_filter)
            
            if overdue_only:
                query = query.filter(
                    and_(
                        Deal.expected_close_date < date.today(),
                        Deal.status == 'open'
                    )
                )
            
            # Date filters
            if created_after:
                query = query.filter(Deal.created_at >= datetime.fromisoformat(created_after))
            if created_before:
                query = query.filter(Deal.created_at <= datetime.fromisoformat(created_before))
            if expected_close_after:
                query = query.filter(Deal.expected_close_date >= datetime.fromisoformat(expected_close_after).date())
            if expected_close_before:
                query = query.filter(Deal.expected_close_date <= datetime.fromisoformat(expected_close_before).date())
            
            # Value filters
            if min_value:
                query = query.filter(Deal.value >= float(min_value))
            if max_value:
                query = query.filter(Deal.value <= float(max_value))
            
            # Apply sorting
            if sort_by == 'title':
                sort_column = Deal.title
            elif sort_by == 'value':
                sort_column = Deal.value
            elif sort_by == 'probability':
                sort_column = Deal.probability
            elif sort_by == 'expected_close_date':
                sort_column = Deal.expected_close_date
            elif sort_by == 'created_at':
                sort_column = Deal.created_at
            elif sort_by == 'updated_at':
                sort_column = Deal.updated_at
            elif sort_by == 'stage':
                sort_column = Deal.stage
            else:
                sort_column = Deal.updated_at
            
            if sort_order.lower() == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Include activities if requested
            if include_activities:
                query = query.options(joinedload(Deal.activities))
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            deals = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            deals_data = [deal.to_dict(include_relationships=include_activities) for deal in deals]
            
            return jsonify({
                'deals': deals_data,
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
        current_app.logger.error(f"Get deals error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@deals_bp.route('/<deal_id>', methods=['GET'])
@require_auth
@require_tenant_access
def get_deal(deal_id, tenant_id):
    """Get a specific deal by ID."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get deal with activities
            deal = session.query(Deal).options(
                joinedload(Deal.activities)
            ).filter(
                and_(
                    Deal.uuid == deal_id,
                    Deal.tenant_id == tenant_id,
                    Deal.is_active == True
                )
            ).first()
            
            if not deal:
                return jsonify({'error': 'Deal not found'}), 404
            
            return jsonify(deal.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get deal error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@deals_bp.route('', methods=['POST'])
@require_auth
@require_roles('admin', 'manager', 'sales')
@require_tenant_access
def create_deal(tenant_id):
    """Create a new deal."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Validate required fields
        if not data.get('title'):
            return jsonify({'error': 'Deal title is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Parse dates
            expected_close_date = None
            if data.get('expected_close_date'):
                expected_close_date = datetime.fromisoformat(data['expected_close_date']).date()
            
            actual_close_date = None
            if data.get('actual_close_date'):
                actual_close_date = datetime.fromisoformat(data['actual_close_date']).date()
            
            # Create deal
            deal = Deal(
                title=data['title'],
                description=data.get('description'),
                company_id=data.get('company_id'),
                contact_id=data.get('contact_id'),
                stage=data.get('stage', 'lead'),
                value=data.get('value'),
                currency=data.get('currency', 'USD'),
                probability=data.get('probability', 0),
                expected_close_date=expected_close_date,
                actual_close_date=actual_close_date,
                source=data.get('source'),
                assigned_to=data.get('assigned_to', request.current_user['user_id']),
                status=data.get('status', 'open'),
                priority=data.get('priority', 'medium'),
                tags=data.get('tags', []),
                custom_fields=json.dumps(data.get('custom_fields', {})),
                lead_score=data.get('lead_score', 0),
                qualification_notes=data.get('qualification_notes'),
                competitor_info=data.get('competitor_info'),
                decision_criteria=data.get('decision_criteria'),
                budget_range=data.get('budget_range'),
                decision_timeframe=data.get('decision_timeframe'),
                tenant_id=tenant_id,
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            
            session.add(deal)
            session.flush()  # Get the deal ID
            
            # Add initial activity
            initial_activity = DealActivity(
                deal_id=deal.uuid,
                activity_type='note',
                subject='Deal Created',
                description=f"Deal '{deal.title}' was created",
                activity_date=datetime.utcnow(),
                completed=True,
                tenant_id=tenant_id,
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(initial_activity)
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='deal',
                entity_id=deal.uuid,
                action='CREATE',
                new_values=json.dumps(deal.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish deal created event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_deal_event(
                        EventType.DEAL_CREATED,
                        tenant_id=tenant_id,
                        deal_id=deal.uuid,
                        deal_data=deal.to_dict(),
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish deal created event: {e}")
            
            # Reload deal with activities
            deal = session.query(Deal).options(
                joinedload(Deal.activities)
            ).filter(Deal.uuid == deal.uuid).first()
            
            return jsonify(deal.to_dict(include_relationships=True)), 201
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Create deal error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@deals_bp.route('/<deal_id>', methods=['PUT'])
@require_auth
@require_roles('admin', 'manager', 'sales')
@require_tenant_access
def update_deal(deal_id, tenant_id):
    """Update a deal."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get deal
            deal = session.query(Deal).filter(
                and_(
                    Deal.uuid == deal_id,
                    Deal.tenant_id == tenant_id,
                    Deal.is_active == True
                )
            ).first()
            
            if not deal:
                return jsonify({'error': 'Deal not found'}), 404
            
            # Store old values for audit
            old_values = deal.to_dict()
            old_stage = deal.stage
            
            # Update allowed fields
            updatable_fields = [
                'title', 'description', 'company_id', 'contact_id', 'stage',
                'value', 'currency', 'probability', 'source', 'assigned_to',
                'status', 'priority', 'lead_score', 'qualification_notes',
                'competitor_info', 'decision_criteria', 'budget_range',
                'decision_timeframe'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(deal, field, data[field])
            
            # Handle date fields
            if 'expected_close_date' in data:
                if data['expected_close_date']:
                    deal.expected_close_date = datetime.fromisoformat(data['expected_close_date']).date()
                else:
                    deal.expected_close_date = None
            
            if 'actual_close_date' in data:
                if data['actual_close_date']:
                    deal.actual_close_date = datetime.fromisoformat(data['actual_close_date']).date()
                else:
                    deal.actual_close_date = None
            
            # Update tags and custom fields
            if 'tags' in data:
                deal.tags = data['tags']
            
            if 'custom_fields' in data:
                deal.custom_fields = json.dumps(data['custom_fields'])
            
            deal.updated_by = request.current_user['user_id']
            deal.updated_at = datetime.utcnow()
            
            # If stage changed, add activity
            if 'stage' in data and data['stage'] != old_stage:
                stage_activity = DealActivity(
                    deal_id=deal.uuid,
                    activity_type='note',
                    subject='Stage Changed',
                    description=f"Deal stage changed from '{old_stage}' to '{data['stage']}'",
                    activity_date=datetime.utcnow(),
                    completed=True,
                    tenant_id=tenant_id,
                    created_by=request.current_user['user_id'],
                    updated_by=request.current_user['user_id']
                )
                session.add(stage_activity)
                
                # Publish stage change event
                try:
                    with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                        event = EventFactory.create_deal_event(
                            EventType.DEAL_STAGE_CHANGED,
                            tenant_id=tenant_id,
                            deal_id=deal.uuid,
                            deal_data={
                                'old_stage': old_stage,
                                'new_stage': data['stage'],
                                'deal_title': deal.title
                            },
                            user_id=request.current_user['user_id']
                        )
                        publisher.publish(event)
                except Exception as e:
                    current_app.logger.warning(f"Failed to publish stage change event: {e}")
            
            # If status changed to won/lost, set actual close date
            if 'status' in data and data['status'] in ['won', 'lost'] and not deal.actual_close_date:
                deal.actual_close_date = date.today()
                
                # Publish won/lost event
                try:
                    with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                        event_type = EventType.DEAL_WON if data['status'] == 'won' else EventType.DEAL_LOST
                        event = EventFactory.create_deal_event(
                            event_type,
                            tenant_id=tenant_id,
                            deal_id=deal.uuid,
                            deal_data=deal.to_dict(),
                            user_id=request.current_user['user_id']
                        )
                        publisher.publish(event)
                except Exception as e:
                    current_app.logger.warning(f"Failed to publish deal status event: {e}")
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='deal',
                entity_id=deal_id,
                action='UPDATE',
                old_values=json.dumps(old_values),
                new_values=json.dumps(deal.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish deal updated event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_deal_event(
                        EventType.DEAL_UPDATED,
                        tenant_id=tenant_id,
                        deal_id=deal.uuid,
                        deal_data=deal.to_dict(),
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish deal updated event: {e}")
            
            return jsonify(deal.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Update deal error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@deals_bp.route('/<deal_id>', methods=['DELETE'])
@require_auth
@require_roles('admin', 'manager')
@require_tenant_access
def delete_deal(deal_id, tenant_id):
    """Soft delete a deal."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get deal
            deal = session.query(Deal).filter(
                and_(
                    Deal.uuid == deal_id,
                    Deal.tenant_id == tenant_id,
                    Deal.is_active == True
                )
            ).first()
            
            if not deal:
                return jsonify({'error': 'Deal not found'}), 404
            
            # Store old values for audit
            old_values = deal.to_dict()
            
            # Soft delete deal and related records
            deal.is_active = False
            deal.updated_by = request.current_user['user_id']
            deal.updated_at = datetime.utcnow()
            
            # Soft delete activities
            for activity in deal.activities:
                if activity.is_active:
                    activity.is_active = False
                    activity.updated_by = request.current_user['user_id']
                    activity.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='deal',
                entity_id=deal_id,
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
            
            return jsonify({'message': 'Deal deleted successfully'}), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Delete deal error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@deals_bp.route('/pipeline', methods=['GET'])
@require_auth
@require_tenant_access
def get_pipeline(tenant_id):
    """Get pipeline view of deals grouped by stage."""
    try:
        # Get query parameters
        assigned_to_filter = request.args.get('assigned_to', '').strip()
        company_id_filter = request.args.get('company_id', '').strip()
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Build base query
            query = session.query(Deal).filter(
                and_(
                    Deal.tenant_id == tenant_id,
                    Deal.is_active == True,
                    Deal.status == 'open'
                )
            )
            
            # Apply filters
            if assigned_to_filter:
                query = query.filter(Deal.assigned_to == assigned_to_filter)
            
            if company_id_filter:
                query = query.filter(Deal.company_id == company_id_filter)
            
            # Get deals grouped by stage
            deals = query.all()
            
            # Group by stage
            pipeline = {}
            total_value = 0
            total_weighted_value = 0
            
            for deal in deals:
                stage = deal.stage
                if stage not in pipeline:
                    pipeline[stage] = {
                        'stage': stage,
                        'deals': [],
                        'count': 0,
                        'total_value': 0,
                        'weighted_value': 0
                    }
                
                deal_dict = deal.to_dict(include_relationships=False)
                pipeline[stage]['deals'].append(deal_dict)
                pipeline[stage]['count'] += 1
                
                if deal.value:
                    pipeline[stage]['total_value'] += float(deal.value)
                    total_value += float(deal.value)
                
                weighted_val = deal.weighted_value
                pipeline[stage]['weighted_value'] += weighted_val
                total_weighted_value += weighted_val
            
            # Convert to list and sort by typical stage order
            stage_order = ['lead', 'qualified', 'proposal', 'negotiation', 'closed_won', 'closed_lost']
            pipeline_list = []
            
            for stage in stage_order:
                if stage in pipeline:
                    pipeline_list.append(pipeline[stage])
            
            # Add any custom stages not in the standard order
            for stage, data in pipeline.items():
                if stage not in stage_order:
                    pipeline_list.append(data)
            
            return jsonify({
                'pipeline': pipeline_list,
                'summary': {
                    'total_deals': len(deals),
                    'total_value': total_value,
                    'total_weighted_value': total_weighted_value
                }
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get pipeline error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@deals_bp.route('/stats', methods=['GET'])
@require_auth
@require_tenant_access
def get_deal_stats(tenant_id):
    """Get deal statistics for the tenant."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get basic counts
            total_deals = session.query(Deal).filter(
                and_(Deal.tenant_id == tenant_id, Deal.is_active == True)
            ).count()
            
            open_deals = session.query(Deal).filter(
                and_(Deal.tenant_id == tenant_id, Deal.is_active == True, Deal.status == 'open')
            ).count()
            
            won_deals = session.query(Deal).filter(
                and_(Deal.tenant_id == tenant_id, Deal.is_active == True, Deal.status == 'won')
            ).count()
            
            lost_deals = session.query(Deal).filter(
                and_(Deal.tenant_id == tenant_id, Deal.is_active == True, Deal.status == 'lost')
            ).count()
            
            # Count by stage
            stage_counts = session.query(
                Deal.stage, func.count(Deal.id)
            ).filter(
                and_(Deal.tenant_id == tenant_id, Deal.is_active == True, Deal.status == 'open')
            ).group_by(Deal.stage).all()
            
            # Count by priority
            priority_counts = session.query(
                Deal.priority, func.count(Deal.id)
            ).filter(
                and_(Deal.tenant_id == tenant_id, Deal.is_active == True, Deal.status == 'open')
            ).group_by(Deal.priority).all()
            
            # Value statistics
            value_stats = session.query(
                func.sum(Deal.value),
                func.avg(Deal.value),
                func.max(Deal.value),
                func.min(Deal.value)
            ).filter(
                and_(Deal.tenant_id == tenant_id, Deal.is_active == True, Deal.value.isnot(None))
            ).first()
            
            # Overdue deals
            overdue_deals = session.query(Deal).filter(
                and_(
                    Deal.tenant_id == tenant_id,
                    Deal.is_active == True,
                    Deal.status == 'open',
                    Deal.expected_close_date < date.today()
                )
            ).count()
            
            return jsonify({
                'total_deals': total_deals,
                'open_deals': open_deals,
                'won_deals': won_deals,
                'lost_deals': lost_deals,
                'overdue_deals': overdue_deals,
                'win_rate': (won_deals / (won_deals + lost_deals) * 100) if (won_deals + lost_deals) > 0 else 0,
                'by_stage': dict(stage_counts),
                'by_priority': dict(priority_counts),
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
        current_app.logger.error(f"Get deal stats error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

