"""
User management routes for CRUD operations on users.
"""

import sys
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_, or_

# Add shared path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'shared'))

from shared.utils.auth import require_auth, require_roles, require_tenant_access, RoleManager
from shared.utils.events import EventPublisher, EventFactory, EventType
from shared.models.base import AuditLog
from src.models.auth_models import User, UserRole

users_bp = Blueprint('users', __name__)


@users_bp.route('', methods=['GET'])
@require_auth
@require_tenant_access
def get_users(tenant_id):
    """Get all users for the tenant."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        search = request.args.get('search', '').strip()
        role_filter = request.args.get('role', '').strip()
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Build query
            query = session.query(User).filter(User.tenant_id == tenant_id)
            
            if active_only:
                query = query.filter(User.is_active == True)
            
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        User.first_name.ilike(search_term),
                        User.last_name.ilike(search_term),
                        User.email.ilike(search_term)
                    )
                )
            
            if role_filter:
                query = query.join(UserRole).filter(
                    and_(
                        UserRole.role == role_filter,
                        UserRole.is_active == True
                    )
                )
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            users = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            users_data = [user.to_dict() for user in users]
            
            return jsonify({
                'users': users_data,
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
        current_app.logger.error(f"Get users error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@users_bp.route('/<user_id>', methods=['GET'])
@require_auth
@require_tenant_access
def get_user(user_id, tenant_id):
    """Get a specific user by ID."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get user
            user = session.query(User).filter(
                and_(
                    User.uuid == user_id,
                    User.tenant_id == tenant_id,
                    User.is_active == True
                )
            ).first()
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            return jsonify(user.to_dict()), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get user error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@users_bp.route('', methods=['POST'])
@require_auth
@require_roles('admin', 'manager')
@require_tenant_access
def create_user(tenant_id):
    """Create a new user."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        email = data['email'].lower().strip()
        password = data['password']
        
        # Validate email format
        if '@' not in email:
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password strength
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Check if email already exists
            existing_user = session.query(User).filter(User.email == email).first()
            if existing_user:
                return jsonify({'error': 'Email already exists'}), 409
            
            # Hash password
            auth_manager = current_app.auth_manager
            password_hash = auth_manager.hash_password(password)
            
            # Create user
            user = User(
                email=email,
                password_hash=password_hash,
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data.get('phone'),
                language=data.get('language', 'en'),
                timezone=data.get('timezone', 'UTC'),
                tenant_id=tenant_id,
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            
            session.add(user)
            session.flush()  # Get the user ID
            
            # Assign roles
            roles = data.get('roles', ['sales'])  # Default role
            for role in roles:
                if role in RoleManager.ROLES:
                    user_role = UserRole(
                        user_id=user.uuid,
                        role=role,
                        granted_by=request.current_user['user_id'],
                        tenant_id=tenant_id,
                        created_by=request.current_user['user_id'],
                        updated_by=request.current_user['user_id']
                    )
                    session.add(user_role)
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='user',
                entity_id=user.uuid,
                action='CREATE',
                new_values=str(user.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish user created event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_audit_event(
                        tenant_id=tenant_id,
                        entity_type='user',
                        entity_id=user.uuid,
                        action='CREATE',
                        new_values=user.to_dict(),
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish user created event: {e}")
            
            return jsonify(user.to_dict()), 201
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Create user error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@users_bp.route('/<user_id>', methods=['PUT'])
@require_auth
@require_roles('admin', 'manager')
@require_tenant_access
def update_user(user_id, tenant_id):
    """Update a user."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get user
            user = session.query(User).filter(
                and_(
                    User.uuid == user_id,
                    User.tenant_id == tenant_id,
                    User.is_active == True
                )
            ).first()
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Store old values for audit
            old_values = user.to_dict()
            
            # Update allowed fields
            updatable_fields = ['first_name', 'last_name', 'phone', 'language', 'timezone']
            for field in updatable_fields:
                if field in data:
                    setattr(user, field, data[field])
            
            # Update email if provided and different
            if 'email' in data and data['email'] != user.email:
                new_email = data['email'].lower().strip()
                if '@' not in new_email:
                    return jsonify({'error': 'Invalid email format'}), 400
                
                # Check if email already exists
                existing_user = session.query(User).filter(
                    and_(User.email == new_email, User.uuid != user_id)
                ).first()
                if existing_user:
                    return jsonify({'error': 'Email already exists'}), 409
                
                user.email = new_email
                user.email_verified = False  # Reset email verification
            
            user.updated_by = request.current_user['user_id']
            user.updated_at = datetime.utcnow()
            
            # Update roles if provided
            if 'roles' in data:
                # Deactivate existing roles
                existing_roles = session.query(UserRole).filter(
                    and_(
                        UserRole.user_id == user_id,
                        UserRole.is_active == True
                    )
                ).all()
                
                for role in existing_roles:
                    role.is_active = False
                    role.updated_by = request.current_user['user_id']
                    role.updated_at = datetime.utcnow()
                
                # Add new roles
                for role in data['roles']:
                    if role in RoleManager.ROLES:
                        user_role = UserRole(
                            user_id=user_id,
                            role=role,
                            granted_by=request.current_user['user_id'],
                            tenant_id=tenant_id,
                            created_by=request.current_user['user_id'],
                            updated_by=request.current_user['user_id']
                        )
                        session.add(user_role)
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='user',
                entity_id=user_id,
                action='UPDATE',
                old_values=str(old_values),
                new_values=str(user.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            return jsonify(user.to_dict()), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Update user error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@users_bp.route('/<user_id>', methods=['DELETE'])
@require_auth
@require_roles('admin')
@require_tenant_access
def delete_user(user_id, tenant_id):
    """Soft delete a user."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get user
            user = session.query(User).filter(
                and_(
                    User.uuid == user_id,
                    User.tenant_id == tenant_id,
                    User.is_active == True
                )
            ).first()
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Prevent self-deletion
            if user_id == request.current_user['user_id']:
                return jsonify({'error': 'Cannot delete your own account'}), 400
            
            # Store old values for audit
            old_values = user.to_dict()
            
            # Soft delete
            user.is_active = False
            user.updated_by = request.current_user['user_id']
            user.updated_at = datetime.utcnow()
            
            # Deactivate user roles
            user_roles = session.query(UserRole).filter(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.is_active == True
                )
            ).all()
            
            for role in user_roles:
                role.is_active = False
                role.updated_by = request.current_user['user_id']
                role.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='user',
                entity_id=user_id,
                action='DELETE',
                old_values=str(old_values),
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
            
            return jsonify({'message': 'User deleted successfully'}), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Delete user error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@users_bp.route('/roles', methods=['GET'])
@require_auth
def get_available_roles():
    """Get list of available roles."""
    try:
        roles = []
        for role_name, role_info in RoleManager.ROLES.items():
            roles.append({
                'name': role_name,
                'description': role_info['description'],
                'permissions': role_info['permissions']
            })
        
        return jsonify({'roles': roles}), 200
        
    except Exception as e:
        current_app.logger.error(f"Get roles error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

