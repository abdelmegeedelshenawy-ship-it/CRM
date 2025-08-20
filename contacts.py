"""
Contact management routes for CRUD operations on contacts.
"""

import sys
import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload

# Add shared path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'shared'))

from shared.utils.auth import require_auth, require_roles, require_tenant_access
from shared.utils.events import EventPublisher, EventFactory, EventType
from shared.models.base import AuditLog
from src.models.client_models import Company, Contact, CommunicationLog, ClientNote

contacts_bp = Blueprint('contacts', __name__)


@contacts_bp.route('', methods=['GET'])
@require_auth
@require_tenant_access
def get_contacts(tenant_id):
    """Get all contacts for the tenant."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        search = request.args.get('search', '').strip()
        company_id = request.args.get('company_id', '').strip()
        department_filter = request.args.get('department', '').strip()
        language_filter = request.args.get('language', '').strip()
        sort_by = request.args.get('sort_by', 'last_name')
        sort_order = request.args.get('sort_order', 'asc')
        include_company = request.args.get('include_company', 'true').lower() == 'true'
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Build query
            query = session.query(Contact).filter(
                and_(Contact.tenant_id == tenant_id, Contact.is_active == True)
            )
            
            # Apply filters
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Contact.first_name.ilike(search_term),
                        Contact.last_name.ilike(search_term),
                        Contact.email.ilike(search_term),
                        Contact.phone.ilike(search_term),
                        Contact.title.ilike(search_term)
                    )
                )
            
            if company_id:
                query = query.filter(Contact.company_id == company_id)
            
            if department_filter:
                query = query.filter(Contact.department == department_filter)
            
            if language_filter:
                query = query.filter(Contact.preferred_language == language_filter)
            
            # Apply sorting
            if sort_by == 'first_name':
                sort_column = Contact.first_name
            elif sort_by == 'last_name':
                sort_column = Contact.last_name
            elif sort_by == 'email':
                sort_column = Contact.email
            elif sort_by == 'title':
                sort_column = Contact.title
            elif sort_by == 'created_at':
                sort_column = Contact.created_at
            elif sort_by == 'updated_at':
                sort_column = Contact.updated_at
            else:
                sort_column = Contact.last_name
            
            if sort_order.lower() == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Include company data if requested
            if include_company:
                query = query.options(joinedload(Contact.company))
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            contacts = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            contacts_data = [contact.to_dict(include_relationships=include_company) for contact in contacts]
            
            return jsonify({
                'contacts': contacts_data,
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
        current_app.logger.error(f"Get contacts error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/<contact_id>', methods=['GET'])
@require_auth
@require_tenant_access
def get_contact(contact_id, tenant_id):
    """Get a specific contact by ID."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get contact with company
            contact = session.query(Contact).options(
                joinedload(Contact.company)
            ).filter(
                and_(
                    Contact.uuid == contact_id,
                    Contact.tenant_id == tenant_id,
                    Contact.is_active == True
                )
            ).first()
            
            if not contact:
                return jsonify({'error': 'Contact not found'}), 404
            
            return jsonify(contact.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get contact error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('', methods=['POST'])
@require_auth
@require_roles('admin', 'manager', 'sales', 'support')
@require_tenant_access
def create_contact(tenant_id):
    """Create a new contact."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Validate required fields
        required_fields = ['first_name', 'last_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Validate company if provided
            company = None
            if data.get('company_id'):
                company = session.query(Company).filter(
                    and_(
                        Company.uuid == data['company_id'],
                        Company.tenant_id == tenant_id,
                        Company.is_active == True
                    )
                ).first()
                
                if not company:
                    return jsonify({'error': 'Company not found'}), 404
            
            # Check for duplicate email if provided
            if data.get('email'):
                existing_contact = session.query(Contact).filter(
                    and_(
                        Contact.email == data['email'],
                        Contact.tenant_id == tenant_id,
                        Contact.is_active == True
                    )
                ).first()
                
                if existing_contact:
                    return jsonify({'error': 'Contact with this email already exists'}), 409
            
            # Create contact
            contact = Contact(
                company_id=data.get('company_id'),
                first_name=data['first_name'],
                last_name=data['last_name'],
                title=data.get('title'),
                department=data.get('department'),
                email=data.get('email'),
                phone=data.get('phone'),
                mobile=data.get('mobile'),
                linkedin_url=data.get('linkedin_url'),
                preferred_language=data.get('preferred_language', 'en'),
                preferred_contact_method=data.get('preferred_contact_method', 'email'),
                is_primary=data.get('is_primary', False),
                notes=data.get('notes'),
                tags=data.get('tags', []),
                custom_fields=json.dumps(data.get('custom_fields', {})),
                tenant_id=tenant_id,
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            
            session.add(contact)
            session.flush()  # Get the contact ID
            
            # If this is marked as primary, unset other primary contacts for the same company
            if contact.is_primary and contact.company_id:
                other_contacts = session.query(Contact).filter(
                    and_(
                        Contact.company_id == contact.company_id,
                        Contact.uuid != contact.uuid,
                        Contact.is_primary == True,
                        Contact.is_active == True
                    )
                ).all()
                
                for other_contact in other_contacts:
                    other_contact.is_primary = False
                    other_contact.updated_by = request.current_user['user_id']
                    other_contact.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='contact',
                entity_id=contact.uuid,
                action='CREATE',
                new_values=json.dumps(contact.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Reload contact with company
            contact = session.query(Contact).options(
                joinedload(Contact.company)
            ).filter(Contact.uuid == contact.uuid).first()
            
            return jsonify(contact.to_dict(include_relationships=True)), 201
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Create contact error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/<contact_id>', methods=['PUT'])
@require_auth
@require_roles('admin', 'manager', 'sales', 'support')
@require_tenant_access
def update_contact(contact_id, tenant_id):
    """Update a contact."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get contact
            contact = session.query(Contact).filter(
                and_(
                    Contact.uuid == contact_id,
                    Contact.tenant_id == tenant_id,
                    Contact.is_active == True
                )
            ).first()
            
            if not contact:
                return jsonify({'error': 'Contact not found'}), 404
            
            # Store old values for audit
            old_values = contact.to_dict()
            
            # Validate company if being changed
            if 'company_id' in data and data['company_id'] != contact.company_id:
                if data['company_id']:
                    company = session.query(Company).filter(
                        and_(
                            Company.uuid == data['company_id'],
                            Company.tenant_id == tenant_id,
                            Company.is_active == True
                        )
                    ).first()
                    
                    if not company:
                        return jsonify({'error': 'Company not found'}), 404
            
            # Check for duplicate email if being changed
            if 'email' in data and data['email'] != contact.email:
                if data['email']:
                    existing_contact = session.query(Contact).filter(
                        and_(
                            Contact.email == data['email'],
                            Contact.uuid != contact_id,
                            Contact.tenant_id == tenant_id,
                            Contact.is_active == True
                        )
                    ).first()
                    
                    if existing_contact:
                        return jsonify({'error': 'Contact with this email already exists'}), 409
            
            # Update allowed fields
            updatable_fields = [
                'company_id', 'first_name', 'last_name', 'title', 'department',
                'email', 'phone', 'mobile', 'linkedin_url', 'preferred_language',
                'preferred_contact_method', 'is_primary', 'notes'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(contact, field, data[field])
            
            # Update tags and custom fields
            if 'tags' in data:
                contact.tags = data['tags']
            
            if 'custom_fields' in data:
                contact.custom_fields = json.dumps(data['custom_fields'])
            
            contact.updated_by = request.current_user['user_id']
            contact.updated_at = datetime.utcnow()
            
            # If this is marked as primary, unset other primary contacts for the same company
            if contact.is_primary and contact.company_id:
                other_contacts = session.query(Contact).filter(
                    and_(
                        Contact.company_id == contact.company_id,
                        Contact.uuid != contact.uuid,
                        Contact.is_primary == True,
                        Contact.is_active == True
                    )
                ).all()
                
                for other_contact in other_contacts:
                    other_contact.is_primary = False
                    other_contact.updated_by = request.current_user['user_id']
                    other_contact.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='contact',
                entity_id=contact_id,
                action='UPDATE',
                old_values=json.dumps(old_values),
                new_values=json.dumps(contact.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            return jsonify(contact.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Update contact error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/<contact_id>', methods=['DELETE'])
@require_auth
@require_roles('admin', 'manager', 'sales')
@require_tenant_access
def delete_contact(contact_id, tenant_id):
    """Soft delete a contact."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get contact
            contact = session.query(Contact).filter(
                and_(
                    Contact.uuid == contact_id,
                    Contact.tenant_id == tenant_id,
                    Contact.is_active == True
                )
            ).first()
            
            if not contact:
                return jsonify({'error': 'Contact not found'}), 404
            
            # Store old values for audit
            old_values = contact.to_dict()
            
            # Soft delete
            contact.is_active = False
            contact.updated_by = request.current_user['user_id']
            contact.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='contact',
                entity_id=contact_id,
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
            
            return jsonify({'message': 'Contact deleted successfully'}), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Delete contact error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/<contact_id>/communications', methods=['GET'])
@require_auth
@require_tenant_access
def get_contact_communications(contact_id, tenant_id):
    """Get communication history for a contact."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        communication_type = request.args.get('type', '').strip()
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Verify contact exists
            contact = session.query(Contact).filter(
                and_(
                    Contact.uuid == contact_id,
                    Contact.tenant_id == tenant_id,
                    Contact.is_active == True
                )
            ).first()
            
            if not contact:
                return jsonify({'error': 'Contact not found'}), 404
            
            # Build query
            query = session.query(CommunicationLog).filter(
                and_(
                    CommunicationLog.contact_id == contact_id,
                    CommunicationLog.tenant_id == tenant_id,
                    CommunicationLog.is_active == True
                )
            )
            
            if communication_type:
                query = query.filter(CommunicationLog.communication_type == communication_type)
            
            # Order by date descending
            query = query.order_by(CommunicationLog.communication_date.desc())
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            communications = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            communications_data = [comm.to_dict() for comm in communications]
            
            return jsonify({
                'communications': communications_data,
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
        current_app.logger.error(f"Get contact communications error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/<contact_id>/notes', methods=['GET'])
@require_auth
@require_tenant_access
def get_contact_notes(contact_id, tenant_id):
    """Get notes for a contact."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        note_type = request.args.get('type', '').strip()
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Verify contact exists
            contact = session.query(Contact).filter(
                and_(
                    Contact.uuid == contact_id,
                    Contact.tenant_id == tenant_id,
                    Contact.is_active == True
                )
            ).first()
            
            if not contact:
                return jsonify({'error': 'Contact not found'}), 404
            
            # Build query
            query = session.query(ClientNote).filter(
                and_(
                    ClientNote.contact_id == contact_id,
                    ClientNote.tenant_id == tenant_id,
                    ClientNote.is_active == True
                )
            )
            
            # Filter private notes (only show to creator unless admin)
            user_roles = request.current_user.get('roles', [])
            if 'admin' not in user_roles:
                query = query.filter(
                    or_(
                        ClientNote.is_private == False,
                        ClientNote.created_by == request.current_user['user_id']
                    )
                )
            
            if note_type:
                query = query.filter(ClientNote.note_type == note_type)
            
            # Order by created date descending
            query = query.order_by(ClientNote.created_at.desc())
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            notes = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            notes_data = [note.to_dict() for note in notes]
            
            return jsonify({
                'notes': notes_data,
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
        current_app.logger.error(f"Get contact notes error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@contacts_bp.route('/stats', methods=['GET'])
@require_auth
@require_tenant_access
def get_contact_stats(tenant_id):
    """Get contact statistics for the tenant."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get basic counts
            total_contacts = session.query(Contact).filter(
                and_(Contact.tenant_id == tenant_id, Contact.is_active == True)
            ).count()
            
            # Count by department
            department_counts = session.query(
                Contact.department, func.count(Contact.id)
            ).filter(
                and_(Contact.tenant_id == tenant_id, Contact.is_active == True, Contact.department.isnot(None))
            ).group_by(Contact.department).all()
            
            # Count by preferred language
            language_counts = session.query(
                Contact.preferred_language, func.count(Contact.id)
            ).filter(
                and_(Contact.tenant_id == tenant_id, Contact.is_active == True)
            ).group_by(Contact.preferred_language).all()
            
            # Count by preferred contact method
            method_counts = session.query(
                Contact.preferred_contact_method, func.count(Contact.id)
            ).filter(
                and_(Contact.tenant_id == tenant_id, Contact.is_active == True)
            ).group_by(Contact.preferred_contact_method).all()
            
            return jsonify({
                'total_contacts': total_contacts,
                'by_department': dict(department_counts),
                'by_language': dict(language_counts),
                'by_contact_method': dict(method_counts)
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get contact stats error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

