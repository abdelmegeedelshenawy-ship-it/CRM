"""
Company management routes for CRUD operations on companies.
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
from src.models.client_models import Company, CompanyAddress, Contact, CommunicationLog, ClientNote

companies_bp = Blueprint('companies', __name__)


@companies_bp.route('', methods=['GET'])
@require_auth
@require_tenant_access
def get_companies(tenant_id):
    """Get all companies for the tenant."""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        industry_filter = request.args.get('industry', '').strip()
        company_type_filter = request.args.get('company_type', '').strip()
        assigned_to_filter = request.args.get('assigned_to', '').strip()
        country_filter = request.args.get('country', '').strip()
        sort_by = request.args.get('sort_by', 'name')
        sort_order = request.args.get('sort_order', 'asc')
        include_addresses = request.args.get('include_addresses', 'false').lower() == 'true'
        include_contacts = request.args.get('include_contacts', 'false').lower() == 'true'
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Build query
            query = session.query(Company).filter(
                and_(Company.tenant_id == tenant_id, Company.is_active == True)
            )
            
            # Apply filters
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Company.name.ilike(search_term),
                        Company.legal_name.ilike(search_term),
                        Company.email.ilike(search_term),
                        Company.phone.ilike(search_term)
                    )
                )
            
            if status_filter:
                query = query.filter(Company.status == status_filter)
            
            if industry_filter:
                query = query.filter(Company.industry == industry_filter)
            
            if company_type_filter:
                query = query.filter(Company.company_type == company_type_filter)
            
            if assigned_to_filter:
                query = query.filter(Company.assigned_to == assigned_to_filter)
            
            if country_filter:
                # Join with addresses to filter by country
                query = query.join(CompanyAddress).filter(CompanyAddress.country == country_filter)
            
            # Apply sorting
            if sort_by == 'name':
                sort_column = Company.name
            elif sort_by == 'created_at':
                sort_column = Company.created_at
            elif sort_by == 'updated_at':
                sort_column = Company.updated_at
            elif sort_by == 'status':
                sort_column = Company.status
            else:
                sort_column = Company.name
            
            if sort_order.lower() == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            companies = query.offset(offset).limit(per_page).all()
            
            # Convert to dict
            companies_data = []
            for company in companies:
                company_dict = company.to_dict(include_relationships=False)
                
                if include_addresses:
                    company_dict['addresses'] = [addr.to_dict(include_relationships=False) 
                                               for addr in company.addresses if addr.is_active]
                
                if include_contacts:
                    company_dict['contacts'] = [contact.to_dict(include_relationships=False) 
                                              for contact in company.contacts if contact.is_active]
                
                companies_data.append(company_dict)
            
            return jsonify({
                'companies': companies_data,
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
        current_app.logger.error(f"Get companies error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@companies_bp.route('/<company_id>', methods=['GET'])
@require_auth
@require_tenant_access
def get_company(company_id, tenant_id):
    """Get a specific company by ID."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get company with relationships
            company = session.query(Company).options(
                joinedload(Company.addresses),
                joinedload(Company.contacts)
            ).filter(
                and_(
                    Company.uuid == company_id,
                    Company.tenant_id == tenant_id,
                    Company.is_active == True
                )
            ).first()
            
            if not company:
                return jsonify({'error': 'Company not found'}), 404
            
            return jsonify(company.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get company error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@companies_bp.route('', methods=['POST'])
@require_auth
@require_roles('admin', 'manager', 'sales')
@require_tenant_access
def create_company(tenant_id):
    """Create a new company."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Company name is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Check if company name already exists for this tenant
            existing_company = session.query(Company).filter(
                and_(
                    Company.name == data['name'],
                    Company.tenant_id == tenant_id,
                    Company.is_active == True
                )
            ).first()
            
            if existing_company:
                return jsonify({'error': 'Company name already exists'}), 409
            
            # Create company
            company = Company(
                name=data['name'],
                legal_name=data.get('legal_name'),
                industry=data.get('industry'),
                company_type=data.get('company_type'),
                website=data.get('website'),
                phone=data.get('phone'),
                email=data.get('email'),
                tax_id=data.get('tax_id'),
                vat_number=data.get('vat_number'),
                registration_number=data.get('registration_number'),
                founded_year=data.get('founded_year'),
                employee_count=data.get('employee_count'),
                annual_revenue=data.get('annual_revenue'),
                currency=data.get('currency', 'USD'),
                status=data.get('status', 'prospect'),
                source=data.get('source'),
                assigned_to=data.get('assigned_to'),
                notes=data.get('notes'),
                tags=data.get('tags', []),
                custom_fields=json.dumps(data.get('custom_fields', {})),
                tenant_id=tenant_id,
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            
            session.add(company)
            session.flush()  # Get the company ID
            
            # Add addresses if provided
            if data.get('addresses'):
                for addr_data in data['addresses']:
                    address = CompanyAddress(
                        company_id=company.uuid,
                        address_type=addr_data.get('address_type', 'business'),
                        street_address=addr_data.get('street_address'),
                        city=addr_data.get('city'),
                        state_province=addr_data.get('state_province'),
                        postal_code=addr_data.get('postal_code'),
                        country=addr_data.get('country'),
                        is_primary=addr_data.get('is_primary', False),
                        tenant_id=tenant_id,
                        created_by=request.current_user['user_id'],
                        updated_by=request.current_user['user_id']
                    )
                    session.add(address)
            
            # Add contacts if provided
            if data.get('contacts'):
                for contact_data in data['contacts']:
                    contact = Contact(
                        company_id=company.uuid,
                        first_name=contact_data['first_name'],
                        last_name=contact_data['last_name'],
                        title=contact_data.get('title'),
                        department=contact_data.get('department'),
                        email=contact_data.get('email'),
                        phone=contact_data.get('phone'),
                        mobile=contact_data.get('mobile'),
                        linkedin_url=contact_data.get('linkedin_url'),
                        preferred_language=contact_data.get('preferred_language', 'en'),
                        preferred_contact_method=contact_data.get('preferred_contact_method', 'email'),
                        is_primary=contact_data.get('is_primary', False),
                        notes=contact_data.get('notes'),
                        tags=contact_data.get('tags', []),
                        custom_fields=json.dumps(contact_data.get('custom_fields', {})),
                        tenant_id=tenant_id,
                        created_by=request.current_user['user_id'],
                        updated_by=request.current_user['user_id']
                    )
                    session.add(contact)
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='company',
                entity_id=company.uuid,
                action='CREATE',
                new_values=json.dumps(company.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish company created event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_client_event(
                        EventType.CLIENT_CREATED,
                        tenant_id=tenant_id,
                        client_id=company.uuid,
                        client_data=company.to_dict(),
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish company created event: {e}")
            
            # Reload company with relationships
            company = session.query(Company).options(
                joinedload(Company.addresses),
                joinedload(Company.contacts)
            ).filter(Company.uuid == company.uuid).first()
            
            return jsonify(company.to_dict(include_relationships=True)), 201
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Create company error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@companies_bp.route('/<company_id>', methods=['PUT'])
@require_auth
@require_roles('admin', 'manager', 'sales')
@require_tenant_access
def update_company(company_id, tenant_id):
    """Update a company."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get company
            company = session.query(Company).filter(
                and_(
                    Company.uuid == company_id,
                    Company.tenant_id == tenant_id,
                    Company.is_active == True
                )
            ).first()
            
            if not company:
                return jsonify({'error': 'Company not found'}), 404
            
            # Store old values for audit
            old_values = company.to_dict()
            
            # Update allowed fields
            updatable_fields = [
                'name', 'legal_name', 'industry', 'company_type', 'website',
                'phone', 'email', 'tax_id', 'vat_number', 'registration_number',
                'founded_year', 'employee_count', 'annual_revenue', 'currency',
                'status', 'source', 'assigned_to', 'notes'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(company, field, data[field])
            
            # Update tags and custom fields
            if 'tags' in data:
                company.tags = data['tags']
            
            if 'custom_fields' in data:
                company.custom_fields = json.dumps(data['custom_fields'])
            
            company.updated_by = request.current_user['user_id']
            company.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='company',
                entity_id=company_id,
                action='UPDATE',
                old_values=json.dumps(old_values),
                new_values=json.dumps(company.to_dict()),
                user_id=request.current_user['user_id'],
                tenant_id=tenant_id,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', ''),
                created_by=request.current_user['user_id'],
                updated_by=request.current_user['user_id']
            )
            session.add(audit_log)
            
            session.commit()
            
            # Publish company updated event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_client_event(
                        EventType.CLIENT_UPDATED,
                        tenant_id=tenant_id,
                        client_id=company.uuid,
                        client_data=company.to_dict(),
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish company updated event: {e}")
            
            return jsonify(company.to_dict(include_relationships=True)), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Update company error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@companies_bp.route('/<company_id>', methods=['DELETE'])
@require_auth
@require_roles('admin', 'manager')
@require_tenant_access
def delete_company(company_id, tenant_id):
    """Soft delete a company."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get company
            company = session.query(Company).filter(
                and_(
                    Company.uuid == company_id,
                    Company.tenant_id == tenant_id,
                    Company.is_active == True
                )
            ).first()
            
            if not company:
                return jsonify({'error': 'Company not found'}), 404
            
            # Store old values for audit
            old_values = company.to_dict()
            
            # Soft delete company and related records
            company.is_active = False
            company.updated_by = request.current_user['user_id']
            company.updated_at = datetime.utcnow()
            
            # Soft delete addresses
            for address in company.addresses:
                if address.is_active:
                    address.is_active = False
                    address.updated_by = request.current_user['user_id']
                    address.updated_at = datetime.utcnow()
            
            # Soft delete contacts
            for contact in company.contacts:
                if contact.is_active:
                    contact.is_active = False
                    contact.updated_by = request.current_user['user_id']
                    contact.updated_at = datetime.utcnow()
            
            # Create audit log
            audit_log = AuditLog(
                entity_type='company',
                entity_id=company_id,
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
            
            # Publish company deleted event
            try:
                with EventPublisher(current_app.config.get('RABBITMQ_URL', 'amqp://localhost')) as publisher:
                    event = EventFactory.create_client_event(
                        EventType.CLIENT_DELETED,
                        tenant_id=tenant_id,
                        client_id=company.uuid,
                        client_data={'id': company.uuid, 'name': company.name},
                        user_id=request.current_user['user_id']
                    )
                    publisher.publish(event)
            except Exception as e:
                current_app.logger.warning(f"Failed to publish company deleted event: {e}")
            
            return jsonify({'message': 'Company deleted successfully'}), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Delete company error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@companies_bp.route('/stats', methods=['GET'])
@require_auth
@require_tenant_access
def get_company_stats(tenant_id):
    """Get company statistics for the tenant."""
    try:
        # Get database session
        session = current_app.db_manager.get_session()
        
        try:
            # Get basic counts
            total_companies = session.query(Company).filter(
                and_(Company.tenant_id == tenant_id, Company.is_active == True)
            ).count()
            
            # Count by status
            status_counts = session.query(
                Company.status, func.count(Company.id)
            ).filter(
                and_(Company.tenant_id == tenant_id, Company.is_active == True)
            ).group_by(Company.status).all()
            
            # Count by industry
            industry_counts = session.query(
                Company.industry, func.count(Company.id)
            ).filter(
                and_(Company.tenant_id == tenant_id, Company.is_active == True, Company.industry.isnot(None))
            ).group_by(Company.industry).all()
            
            # Count by company type
            type_counts = session.query(
                Company.company_type, func.count(Company.id)
            ).filter(
                and_(Company.tenant_id == tenant_id, Company.is_active == True, Company.company_type.isnot(None))
            ).group_by(Company.company_type).all()
            
            return jsonify({
                'total_companies': total_companies,
                'by_status': dict(status_counts),
                'by_industry': dict(industry_counts),
                'by_type': dict(type_counts)
            }), 200
            
        finally:
            current_app.db_manager.close_session(session)
            
    except Exception as e:
        current_app.logger.error(f"Get company stats error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

