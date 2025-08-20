-- CRM Platform Seed Data Script
-- This script inserts initial data for development and testing

-- Insert default tenant
INSERT INTO tenants (uuid, name, slug, domain, settings, subscription_plan, subscription_status, created_by, updated_by)
VALUES (
    'f47ac10b-58cc-4372-a567-0e02b2c3d479',
    'Dakahlia Agricultural Development Co.',
    'dakahlia-agri',
    'dakahlia-agri.crm.com',
    '{"branding": {"primary_color": "#2563eb", "secondary_color": "#1e40af", "logo_url": ""}, "features": {"analytics": true, "compliance": true, "multi_language": true}}',
    'enterprise',
    'active',
    'system',
    'system'
) ON CONFLICT (uuid) DO NOTHING;

-- Insert demo tenant for testing
INSERT INTO tenants (uuid, name, slug, domain, settings, subscription_plan, subscription_status, created_by, updated_by)
VALUES (
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'Demo Export Company',
    'demo-export',
    'demo.crm.com',
    '{"branding": {"primary_color": "#059669", "secondary_color": "#047857", "logo_url": ""}, "features": {"analytics": true, "compliance": false, "multi_language": false}}',
    'basic',
    'active',
    'system',
    'system'
) ON CONFLICT (uuid) DO NOTHING;

-- Insert admin user for Dakahlia Agricultural
INSERT INTO auth.users (uuid, email, password_hash, first_name, last_name, phone, language, timezone, email_verified, is_active, tenant_id, created_by, updated_by)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    'admin@dakahlia-agri.com',
    '$2b$12$LQv3c1yqBwEHxPuNYjHNTO.eeih0Zce0j2hJ8L2iEHvNjKjpcHzJO', -- password: admin123
    'System',
    'Administrator',
    '+20123456789',
    'en',
    'Africa/Cairo',
    true,
    true,
    'f47ac10b-58cc-4372-a567-0e02b2c3d479',
    'system',
    'system'
) ON CONFLICT (uuid) DO NOTHING;

-- Insert demo user
INSERT INTO auth.users (uuid, email, password_hash, first_name, last_name, phone, language, timezone, email_verified, is_active, tenant_id, created_by, updated_by)
VALUES (
    '6ba7b810-9dad-11d1-80b4-00c04fd430c8',
    'demo@demo-export.com',
    '$2b$12$LQv3c1yqBwEHxPuNYjHNTO.eeih0Zce0j2hJ8L2iEHvNjKjpcHzJO', -- password: admin123
    'Demo',
    'User',
    '+1234567890',
    'en',
    'UTC',
    true,
    true,
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'system',
    'system'
) ON CONFLICT (uuid) DO NOTHING;

-- Insert sales manager for Dakahlia
INSERT INTO auth.users (uuid, email, password_hash, first_name, last_name, phone, language, timezone, email_verified, is_active, tenant_id, created_by, updated_by)
VALUES (
    '6ba7b811-9dad-11d1-80b4-00c04fd430c8',
    'sales@dakahlia-agri.com',
    '$2b$12$LQv3c1yqBwEHxPuNYjHNTO.eeih0Zce0j2hJ8L2iEHvNjKjpcHzJO', -- password: admin123
    'Ahmed',
    'Hassan',
    '+20123456788',
    'ar',
    'Africa/Cairo',
    true,
    true,
    'f47ac10b-58cc-4372-a567-0e02b2c3d479',
    'system',
    'system'
) ON CONFLICT (uuid) DO NOTHING;

-- Assign roles to users
INSERT INTO auth.user_roles (user_id, role, granted_by, tenant_id)
VALUES 
    ('550e8400-e29b-41d4-a716-446655440000', 'admin', '550e8400-e29b-41d4-a716-446655440000', 'f47ac10b-58cc-4372-a567-0e02b2c3d479'),
    ('6ba7b810-9dad-11d1-80b4-00c04fd430c8', 'admin', '6ba7b810-9dad-11d1-80b4-00c04fd430c8', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'),
    ('6ba7b811-9dad-11d1-80b4-00c04fd430c8', 'manager', '550e8400-e29b-41d4-a716-446655440000', 'f47ac10b-58cc-4372-a567-0e02b2c3d479')
ON CONFLICT DO NOTHING;

-- Insert sample companies for Dakahlia tenant
INSERT INTO clients.companies (uuid, name, legal_name, industry, company_type, website, phone, email, tax_id, country, status, source, assigned_to, tenant_id, created_by, updated_by)
VALUES 
    ('c1a2b3c4-d5e6-f789-0123-456789abcdef', 'Gulf Fresh Foods LLC', 'Gulf Fresh Foods Limited Liability Company', 'Food & Beverage', 'distributor', 'https://gulffreshfoods.ae', '+971-4-1234567', 'info@gulffreshfoods.ae', 'AE123456789', 'UAE', 'active', 'website', '6ba7b811-9dad-11d1-80b4-00c04fd430c8', 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('d2b3c4d5-e6f7-8901-2345-6789abcdef01', 'Saudi Agricultural Imports', 'Saudi Agricultural Imports Company', 'Agriculture', 'importer', 'https://saudiagri.sa', '+966-11-9876543', 'procurement@saudiagri.sa', 'SA987654321', 'Saudi Arabia', 'active', 'referral', '6ba7b811-9dad-11d1-80b4-00c04fd430c8', 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('e3c4d5e6-f789-0123-4567-89abcdef0123', 'Kuwait Wholesale Market', 'Kuwait Wholesale Market WLL', 'Wholesale Trade', 'wholesaler', 'https://kuwaitmarket.kw', '+965-2-5555555', 'orders@kuwaitmarket.kw', 'KW555555555', 'Kuwait', 'prospect', 'trade_show', '6ba7b811-9dad-11d1-80b4-00c04fd430c8', 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system')
ON CONFLICT (uuid) DO NOTHING;

-- Insert company addresses
INSERT INTO clients.company_addresses (uuid, company_id, address_type, street_address, city, state_province, postal_code, country, is_primary, tenant_id, created_by, updated_by)
VALUES 
    ('a1b2c3d4-e5f6-7890-1234-567890abcdef', 'c1a2b3c4-d5e6-f789-0123-456789abcdef', 'business', 'Dubai Investment Park, Building 123', 'Dubai', 'Dubai', '12345', 'UAE', true, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('b2c3d4e5-f678-9012-3456-789abcdef012', 'd2b3c4d5-e6f7-8901-2345-6789abcdef01', 'business', 'King Fahd Road, Commercial District', 'Riyadh', 'Riyadh Province', '11564', 'Saudi Arabia', true, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('c3d4e5f6-7890-1234-5678-9abcdef01234', 'e3c4d5e6-f789-0123-4567-89abcdef0123', 'business', 'Shuwaikh Industrial Area, Block 1', 'Kuwait City', 'Al Asimah', '13001', 'Kuwait', true, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system')
ON CONFLICT (uuid) DO NOTHING;

-- Insert contacts
INSERT INTO clients.contacts (uuid, company_id, first_name, last_name, title, department, email, phone, mobile, preferred_language, preferred_contact_method, is_primary, tenant_id, created_by, updated_by)
VALUES 
    ('f1a2b3c4-d5e6-7890-1234-567890abcdef', 'c1a2b3c4-d5e6-f789-0123-456789abcdef', 'Mohammed', 'Al-Rashid', 'Procurement Manager', 'Purchasing', 'm.alrashid@gulffreshfoods.ae', '+971-4-1234567', '+971-50-1234567', 'en', 'email', true, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('f2b3c4d5-e6f7-8901-2345-6789abcdef01', 'd2b3c4d5-e6f7-8901-2345-6789abcdef01', 'Abdullah', 'Al-Saud', 'Import Director', 'Operations', 'a.alsaud@saudiagri.sa', '+966-11-9876543', '+966-50-9876543', 'ar', 'phone', true, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('f3c4d5e6-f789-0123-4567-89abcdef0123', 'e3c4d5e6-f789-0123-4567-89abcdef0123', 'Fatima', 'Al-Sabah', 'Business Development', 'Sales', 'f.alsabah@kuwaitmarket.kw', '+965-2-5555555', '+965-9-5555555', 'ar', 'email', true, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system')
ON CONFLICT (uuid) DO NOTHING;

-- Insert sample deals
INSERT INTO deals.deals (uuid, title, description, company_id, contact_id, stage, value, currency, probability, expected_close_date, source, assigned_to, status, priority, tags, tenant_id, created_by, updated_by)
VALUES 
    ('d1a2b3c4-e5f6-7890-1234-567890abcdef', 'Fresh Vegetables Supply Contract', 'Annual contract for fresh vegetables supply to UAE market', 'c1a2b3c4-d5e6-f789-0123-456789abcdef', 'f1a2b3c4-d5e6-7890-1234-567890abcdef', 'negotiation', 250000.00, 'USD', 75, '2025-09-15', 'website', '6ba7b811-9dad-11d1-80b4-00c04fd430c8', 'open', 'high', ARRAY['vegetables', 'annual_contract', 'uae'], 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('d2b3c4d5-e6f7-8901-2345-6789abcdef01', 'Citrus Fruits Export Deal', 'Seasonal citrus fruits export to Saudi Arabia', 'd2b3c4d5-e6f7-8901-2345-6789abcdef01', 'f2b3c4d5-e6f7-8901-2345-6789abcdef01', 'proposal', 180000.00, 'USD', 60, '2025-10-01', 'referral', '6ba7b811-9dad-11d1-80b4-00c04fd430c8', 'open', 'medium', ARRAY['citrus', 'seasonal', 'saudi'], 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('d3c4d5e6-f789-0123-4567-89abcdef0123', 'Organic Produce Partnership', 'Partnership for organic produce distribution in Kuwait', 'e3c4d5e6-f789-0123-4567-89abcdef0123', 'f3c4d5e6-f789-0123-4567-89abcdef0123', 'lead', 120000.00, 'USD', 30, '2025-11-30', 'trade_show', '6ba7b811-9dad-11d1-80b4-00c04fd430c8', 'open', 'medium', ARRAY['organic', 'partnership', 'kuwait'], 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system')
ON CONFLICT (uuid) DO NOTHING;

-- Insert sample orders
INSERT INTO orders.orders (uuid, order_number, deal_id, company_id, contact_id, status, order_date, required_date, total_amount, currency, payment_terms, payment_status, shipping_method, notes, tenant_id, created_by, updated_by)
VALUES 
    ('o1a2b3c4-e5f6-7890-1234-567890abcdef', 'ORD-2025-001', 'd1a2b3c4-e5f6-7890-1234-567890abcdef', 'c1a2b3c4-d5e6-f789-0123-456789abcdef', 'f1a2b3c4-d5e6-7890-1234-567890abcdef', 'confirmed', '2025-08-15', '2025-08-30', 45000.00, 'USD', 'Net 30', 'pending', 'Sea Freight', 'First shipment of vegetables for Q3', 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system')
ON CONFLICT (uuid) DO NOTHING;

-- Insert order items
INSERT INTO orders.order_items (uuid, order_id, product_code, product_name, description, quantity, unit_price, total_price, unit_of_measure, weight, tenant_id, created_by, updated_by)
VALUES 
    ('i1a2b3c4-e5f6-7890-1234-567890abcdef', 'o1a2b3c4-e5f6-7890-1234-567890abcdef', 'VEG-TOM-001', 'Fresh Tomatoes', 'Grade A fresh tomatoes', 1000.000, 2.50, 2500.00, 'kg', 1000.000, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('i2b3c4d5-e6f7-8901-2345-6789abcdef01', 'o1a2b3c4-e5f6-7890-1234-567890abcdef', 'VEG-CUC-001', 'Fresh Cucumbers', 'Grade A fresh cucumbers', 800.000, 1.80, 1440.00, 'kg', 800.000, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system'),
    ('i3c4d5e6-f789-0123-4567-89abcdef0123', 'o1a2b3c4-e5f6-7890-1234-567890abcdef', 'VEG-PEP-001', 'Bell Peppers', 'Mixed color bell peppers', 500.000, 3.20, 1600.00, 'kg', 500.000, 'f47ac10b-58cc-4372-a567-0e02b2c3d479', 'system', 'system')
ON CONFLICT (uuid) DO NOTHING;

