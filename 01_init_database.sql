-- CRM Platform Database Initialization Script
-- This script creates the initial database structure for all microservices

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas for different services
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS clients;
CREATE SCHEMA IF NOT EXISTS deals;
CREATE SCHEMA IF NOT EXISTS orders;
CREATE SCHEMA IF NOT EXISTS documents;
CREATE SCHEMA IF NOT EXISTS users;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS compliance;
CREATE SCHEMA IF NOT EXISTS notifications;

-- Create audit logs table (shared across all services)
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    user_id UUID,
    tenant_id UUID NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for audit logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

-- Tenants table (for multi-tenancy)
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255),
    settings JSONB DEFAULT '{}',
    subscription_plan VARCHAR(50) DEFAULT 'basic',
    subscription_status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for tenants
CREATE INDEX IF NOT EXISTS idx_tenants_slug ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_domain ON tenants(domain);

-- Users table (auth service)
CREATE TABLE IF NOT EXISTS auth.users (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    language VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'UTC',
    last_login TIMESTAMP,
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- User roles table
CREATE TABLE IF NOT EXISTS auth.user_roles (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(uuid),
    role VARCHAR(50) NOT NULL,
    granted_by UUID REFERENCES auth.users(uuid),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tenant_id UUID NOT NULL REFERENCES tenants(uuid)
);

-- Create indexes for auth tables
CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON auth.users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON auth.user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_tenant ON auth.user_roles(tenant_id);

-- Companies table (clients service)
CREATE TABLE IF NOT EXISTS clients.companies (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(255),
    industry VARCHAR(100),
    company_type VARCHAR(50),
    website VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(255),
    tax_id VARCHAR(100),
    vat_number VARCHAR(100),
    registration_number VARCHAR(100),
    founded_year INTEGER,
    employee_count INTEGER,
    annual_revenue DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(50) DEFAULT 'active',
    source VARCHAR(100),
    assigned_to UUID REFERENCES auth.users(uuid),
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Company addresses table
CREATE TABLE IF NOT EXISTS clients.company_addresses (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    company_id UUID NOT NULL REFERENCES clients.companies(uuid),
    address_type VARCHAR(50) DEFAULT 'business',
    street_address TEXT,
    city VARCHAR(100),
    state_province VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Contacts table
CREATE TABLE IF NOT EXISTS clients.contacts (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    company_id UUID REFERENCES clients.companies(uuid),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    title VARCHAR(100),
    department VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    mobile VARCHAR(20),
    linkedin_url VARCHAR(255),
    preferred_language VARCHAR(10) DEFAULT 'en',
    preferred_contact_method VARCHAR(50) DEFAULT 'email',
    is_primary BOOLEAN DEFAULT FALSE,
    notes TEXT,
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for clients tables
CREATE INDEX IF NOT EXISTS idx_companies_name ON clients.companies USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_companies_tenant ON clients.companies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_companies_assigned_to ON clients.companies(assigned_to);
CREATE INDEX IF NOT EXISTS idx_company_addresses_company ON clients.company_addresses(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON clients.contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON clients.contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_tenant ON clients.contacts(tenant_id);

-- Deals table (deals service)
CREATE TABLE IF NOT EXISTS deals.deals (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    company_id UUID REFERENCES clients.companies(uuid),
    contact_id UUID REFERENCES clients.contacts(uuid),
    stage VARCHAR(50) DEFAULT 'lead',
    value DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'USD',
    probability INTEGER DEFAULT 0,
    expected_close_date DATE,
    actual_close_date DATE,
    source VARCHAR(100),
    assigned_to UUID REFERENCES auth.users(uuid),
    status VARCHAR(50) DEFAULT 'open',
    priority VARCHAR(20) DEFAULT 'medium',
    tags TEXT[],
    custom_fields JSONB DEFAULT '{}',
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Deal activities table
CREATE TABLE IF NOT EXISTS deals.deal_activities (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    deal_id UUID NOT NULL REFERENCES deals.deals(uuid),
    activity_type VARCHAR(50) NOT NULL,
    subject VARCHAR(255),
    description TEXT,
    activity_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_minutes INTEGER,
    outcome VARCHAR(100),
    next_action TEXT,
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for deals tables
CREATE INDEX IF NOT EXISTS idx_deals_company ON deals.deals(company_id);
CREATE INDEX IF NOT EXISTS idx_deals_contact ON deals.deals(contact_id);
CREATE INDEX IF NOT EXISTS idx_deals_assigned_to ON deals.deals(assigned_to);
CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals.deals(stage);
CREATE INDEX IF NOT EXISTS idx_deals_tenant ON deals.deals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_deal_activities_deal ON deals.deal_activities(deal_id);

-- Orders table (orders service)
CREATE TABLE IF NOT EXISTS orders.orders (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    order_number VARCHAR(100) UNIQUE NOT NULL,
    deal_id UUID REFERENCES deals.deals(uuid),
    company_id UUID NOT NULL REFERENCES clients.companies(uuid),
    contact_id UUID REFERENCES clients.contacts(uuid),
    status VARCHAR(50) DEFAULT 'pending',
    order_date DATE DEFAULT CURRENT_DATE,
    required_date DATE,
    shipped_date DATE,
    delivery_date DATE,
    total_amount DECIMAL(15,2),
    currency VARCHAR(3) DEFAULT 'USD',
    payment_terms VARCHAR(100),
    payment_status VARCHAR(50) DEFAULT 'pending',
    shipping_method VARCHAR(100),
    shipping_address JSONB,
    billing_address JSONB,
    notes TEXT,
    custom_fields JSONB DEFAULT '{}',
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Order items table
CREATE TABLE IF NOT EXISTS orders.order_items (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    order_id UUID NOT NULL REFERENCES orders.orders(uuid),
    product_code VARCHAR(100),
    product_name VARCHAR(255) NOT NULL,
    description TEXT,
    quantity DECIMAL(10,3) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(15,2) NOT NULL,
    unit_of_measure VARCHAR(20),
    weight DECIMAL(10,3),
    dimensions JSONB,
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for orders tables
CREATE INDEX IF NOT EXISTS idx_orders_number ON orders.orders(order_number);
CREATE INDEX IF NOT EXISTS idx_orders_company ON orders.orders(company_id);
CREATE INDEX IF NOT EXISTS idx_orders_deal ON orders.orders(deal_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_tenant ON orders.orders(tenant_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON orders.order_items(order_id);

-- Documents table (documents service)
CREATE TABLE IF NOT EXISTS documents.documents (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_size BIGINT,
    mime_type VARCHAR(100),
    file_hash VARCHAR(64),
    document_type VARCHAR(50),
    category VARCHAR(100),
    entity_type VARCHAR(50),
    entity_id UUID,
    title VARCHAR(255),
    description TEXT,
    tags TEXT[],
    is_public BOOLEAN DEFAULT FALSE,
    access_level VARCHAR(20) DEFAULT 'private',
    version INTEGER DEFAULT 1,
    parent_document_id UUID REFERENCES documents.documents(uuid),
    tenant_id UUID NOT NULL REFERENCES tenants(uuid),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for documents table
CREATE INDEX IF NOT EXISTS idx_documents_entity ON documents.documents(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents.documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents.documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents.documents USING gin(filename gin_trgm_ops);

-- Create trigger function for updating timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for all tables
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON auth.users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON clients.companies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_company_addresses_updated_at BEFORE UPDATE ON clients.company_addresses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON clients.contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_deals_updated_at BEFORE UPDATE ON deals.deals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_deal_activities_updated_at BEFORE UPDATE ON deals.deal_activities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders.orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_order_items_updated_at BEFORE UPDATE ON orders.order_items FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents.documents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_audit_logs_updated_at BEFORE UPDATE ON audit_logs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

