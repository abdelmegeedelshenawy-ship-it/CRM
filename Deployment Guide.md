# Deployment Guide

This guide covers deployment options for the Export CRM Platform, from development to production environments.

## Table of Contents

1. [Development Deployment](#development-deployment)
2. [Production Deployment](#production-deployment)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Deployment](#cloud-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Database Setup](#database-setup)
8. [SSL/TLS Configuration](#ssltls-configuration)
9. [Monitoring and Logging](#monitoring-and-logging)
10. [Backup and Recovery](#backup-and-recovery)

## Development Deployment

### Prerequisites
- Docker and Docker Compose
- Git
- Node.js 18+ (for frontend development)
- Python 3.11+ (for backend development)

### Quick Start
```bash
# Clone the repository
git clone <repository-url>
cd crm-platform

# Copy environment template
cp .env.example .env

# Start all services
docker-compose up -d

# Initialize database
docker-compose exec postgres psql -U crm_user -d crm_db -f /docker-entrypoint-initdb.d/01_init_database.sql
docker-compose exec postgres psql -U crm_user -d crm_db -f /docker-entrypoint-initdb.d/02_seed_data.sql

# Access the application
# Frontend: http://localhost:3000
# API Gateway: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Development Services
The development environment includes:
- **Frontend**: React development server (Port 3000)
- **API Gateway**: Flask application (Port 8000)
- **Microservices**: 9 Flask services (Ports 5001-5009)
- **PostgreSQL**: Database server (Port 5432)
- **RabbitMQ**: Message broker (Port 5672, Management: 15672)
- **Redis**: Cache server (Port 6379)

## Production Deployment

### System Requirements
- **CPU**: 4+ cores
- **RAM**: 8GB+ (16GB recommended)
- **Storage**: 100GB+ SSD
- **OS**: Ubuntu 20.04+ or CentOS 8+
- **Network**: Static IP with domain name

### Production Architecture
```
Internet → Load Balancer → API Gateway → Microservices
                       ↓
                   Database Cluster
                       ↓
                   Message Queue
```

### Production Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone and setup
git clone <repository-url>
cd crm-platform
cp .env.production .env

# Edit production environment
nano .env

# Deploy with production compose
docker-compose -f docker-compose.prod.yml up -d
```

## Docker Deployment

### Production Docker Compose
```yaml
version: '3.8'

services:
  # API Gateway
  api-gateway:
    build:
      context: ./api-gateway
      dockerfile: Dockerfile.prod
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - RABBITMQ_URL=${RABBITMQ_URL}
    depends_on:
      - postgres
      - redis
      - rabbitmq
    restart: unless-stopped

  # Authentication Service
  auth-service:
    build:
      context: ./services/auth
      dockerfile: Dockerfile.prod
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    depends_on:
      - postgres
    restart: unless-stopped

  # Database
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/sql:/docker-entrypoint-initdb.d
    restart: unless-stopped

  # Message Broker
  rabbitmq:
    image: rabbitmq:3.11-management
    environment:
      - RABBITMQ_DEFAULT_USER=${RABBITMQ_USER}
      - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASSWORD}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: unless-stopped

  # Cache
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./ssl:/etc/ssl/certs
    depends_on:
      - api-gateway
    restart: unless-stopped

volumes:
  postgres_data:
  rabbitmq_data:
  redis_data:
```

### Building Production Images
```bash
# Build all services
docker-compose -f docker-compose.prod.yml build

# Build specific service
docker-compose -f docker-compose.prod.yml build auth-service

# Push to registry
docker tag crm-platform_auth-service:latest your-registry/crm-auth:latest
docker push your-registry/crm-auth:latest
```

## Kubernetes Deployment

### Prerequisites
- Kubernetes cluster (1.24+)
- kubectl configured
- Helm 3.x (optional)

### Namespace Setup
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: crm-platform
  labels:
    name: crm-platform
```

### ConfigMap
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: crm-config
  namespace: crm-platform
data:
  FLASK_ENV: "production"
  DATABASE_HOST: "postgres-service"
  REDIS_HOST: "redis-service"
  RABBITMQ_HOST: "rabbitmq-service"
```

### Secrets
```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: crm-secrets
  namespace: crm-platform
type: Opaque
data:
  DATABASE_PASSWORD: <base64-encoded-password>
  JWT_SECRET_KEY: <base64-encoded-secret>
  REDIS_PASSWORD: <base64-encoded-password>
  RABBITMQ_PASSWORD: <base64-encoded-password>
```

### Database Deployment
```yaml
# postgres.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: crm-platform
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: "crm_db"
        - name: POSTGRES_USER
          value: "crm_user"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: crm-secrets
              key: DATABASE_PASSWORD
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 100Gi
```

### Service Deployment
```yaml
# auth-service.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: crm-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-service
        image: your-registry/crm-auth:latest
        ports:
        - containerPort: 5001
        env:
        - name: FLASK_ENV
          valueFrom:
            configMapKeyRef:
              name: crm-config
              key: FLASK_ENV
        - name: DATABASE_URL
          value: "postgresql://crm_user:$(DATABASE_PASSWORD)@postgres-service:5432/crm_db"
        - name: DATABASE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: crm-secrets
              key: DATABASE_PASSWORD
        livenessProbe:
          httpGet:
            path: /health
            port: 5001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 5001
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Ingress Configuration
```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: crm-ingress
  namespace: crm-platform
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - crm.yourdomain.com
    secretName: crm-tls
  rules:
  - host: crm.yourdomain.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-gateway-service
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80
```

### Deploy to Kubernetes
```bash
# Apply all manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -n crm-platform

# View logs
kubectl logs -f deployment/auth-service -n crm-platform

# Scale services
kubectl scale deployment auth-service --replicas=5 -n crm-platform
```

## Cloud Deployment

### AWS Deployment

#### EKS Setup
```bash
# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Create EKS cluster
eksctl create cluster \
  --name crm-platform \
  --version 1.24 \
  --region us-west-2 \
  --nodegroup-name workers \
  --node-type m5.large \
  --nodes 3 \
  --nodes-min 1 \
  --nodes-max 10 \
  --managed

# Configure kubectl
aws eks update-kubeconfig --region us-west-2 --name crm-platform
```

#### RDS Setup
```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier crm-postgres \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.3 \
  --master-username crmuser \
  --master-user-password YourSecurePassword \
  --allocated-storage 100 \
  --storage-type gp2 \
  --vpc-security-group-ids sg-xxxxxxxxx \
  --db-subnet-group-name crm-subnet-group \
  --backup-retention-period 7 \
  --multi-az
```

### Azure Deployment

#### AKS Setup
```bash
# Create resource group
az group create --name crm-platform-rg --location eastus

# Create AKS cluster
az aks create \
  --resource-group crm-platform-rg \
  --name crm-platform-aks \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group crm-platform-rg --name crm-platform-aks
```

### GCP Deployment

#### GKE Setup
```bash
# Create GKE cluster
gcloud container clusters create crm-platform \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-2 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 10

# Get credentials
gcloud container clusters get-credentials crm-platform --zone us-central1-a
```

## Environment Configuration

### Environment Variables
```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@host:5432/dbname
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=crm_db
DATABASE_USER=crm_user
DATABASE_PASSWORD=secure_password

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=redis_password

# RabbitMQ Configuration
RABBITMQ_URL=amqp://user:password@localhost:5672
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=crm_user
RABBITMQ_PASSWORD=rabbitmq_password

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key
JWT_ACCESS_TOKEN_EXPIRES=900  # 15 minutes
JWT_REFRESH_TOKEN_EXPIRES=604800  # 7 days

# Application Configuration
FLASK_ENV=production
DEBUG=false
SECRET_KEY=your-flask-secret-key
CORS_ORIGINS=https://yourdomain.com

# Service URLs
AUTH_SERVICE_URL=http://auth-service:5001
CLIENTS_SERVICE_URL=http://clients-service:5002
DEALS_SERVICE_URL=http://deals-service:5003
ORDERS_SERVICE_URL=http://orders-service:5004

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=/var/log/crm/app.log

# Email Configuration (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true

# File Storage (optional)
STORAGE_TYPE=local  # or s3, azure, gcs
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=crm-documents
```

### Production Environment Template
```bash
# .env.production
FLASK_ENV=production
DEBUG=false

# Database
DATABASE_URL=postgresql://crm_user:${DB_PASSWORD}@postgres-cluster:5432/crm_db

# Redis
REDIS_URL=redis://:${REDIS_PASSWORD}@redis-cluster:6379

# RabbitMQ
RABBITMQ_URL=amqp://crm_user:${RABBITMQ_PASSWORD}@rabbitmq-cluster:5672

# Security
JWT_SECRET_KEY=${JWT_SECRET}
SECRET_KEY=${FLASK_SECRET}

# CORS
CORS_ORIGINS=https://crm.yourdomain.com,https://api.yourdomain.com

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/crm/app.log
```

## Database Setup

### PostgreSQL Configuration
```sql
-- Create database and user
CREATE DATABASE crm_db;
CREATE USER crm_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE crm_db TO crm_user;

-- Configure for production
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
SELECT pg_reload_conf();
```

### Database Migration
```bash
# Run migrations
docker-compose exec auth-service python -c "
from src.main import app
with app.app_context():
    app.db_manager.create_tables()
"

# Load seed data
docker-compose exec postgres psql -U crm_user -d crm_db -f /docker-entrypoint-initdb.d/02_seed_data.sql

# Backup database
docker-compose exec postgres pg_dump -U crm_user crm_db > backup.sql

# Restore database
docker-compose exec -T postgres psql -U crm_user crm_db < backup.sql
```

## SSL/TLS Configuration

### Let's Encrypt with Certbot
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d crm.yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Nginx Configuration
```nginx
# /etc/nginx/sites-available/crm-platform
server {
    listen 80;
    server_name crm.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name crm.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/crm.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/crm.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring and Logging

### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'crm-services'
    static_configs:
      - targets: ['localhost:5001', 'localhost:5002', 'localhost:5003']
    metrics_path: /metrics
    scrape_interval: 5s
```

### Grafana Dashboard
```json
{
  "dashboard": {
    "title": "CRM Platform Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(flask_http_request_total[5m])",
            "legendFormat": "{{service}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "flask_http_request_duration_seconds",
            "legendFormat": "{{service}}"
          }
        ]
      }
    ]
  }
}
```

### ELK Stack Setup
```yaml
# docker-compose.elk.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.8.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data

  logstash:
    image: docker.elastic.co/logstash/logstash:8.8.0
    ports:
      - "5044:5044"
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: docker.elastic.co/kibana/kibana:8.8.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200

volumes:
  elasticsearch_data:
```

## Backup and Recovery

### Database Backup
```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="crm_db"
DB_USER="crm_user"

# Create backup
docker-compose exec postgres pg_dump -U $DB_USER $DB_NAME > $BACKUP_DIR/crm_backup_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/crm_backup_$DATE.sql

# Remove old backups (keep last 7 days)
find $BACKUP_DIR -name "crm_backup_*.sql.gz" -mtime +7 -delete

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/crm_backup_$DATE.sql.gz s3://your-backup-bucket/database/
```

### Application Backup
```bash
#!/bin/bash
# app-backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# Backup application files
tar -czf $BACKUP_DIR/app_backup_$DATE.tar.gz \
  --exclude='node_modules' \
  --exclude='venv' \
  --exclude='__pycache__' \
  /path/to/crm-platform

# Upload to S3
aws s3 cp $BACKUP_DIR/app_backup_$DATE.tar.gz s3://your-backup-bucket/application/
```

### Recovery Procedures
```bash
# Database Recovery
gunzip crm_backup_20231201_120000.sql.gz
docker-compose exec -T postgres psql -U crm_user crm_db < crm_backup_20231201_120000.sql

# Application Recovery
tar -xzf app_backup_20231201_120000.tar.gz -C /path/to/restore/
```

### Automated Backup with Cron
```bash
# Add to crontab
0 2 * * * /path/to/backup.sh
0 3 * * 0 /path/to/app-backup.sh  # Weekly app backup
```

## Health Checks and Monitoring

### Health Check Endpoints
```python
# Health check implementation
@app.route('/health')
def health_check():
    checks = {
        'database': check_database(),
        'redis': check_redis(),
        'rabbitmq': check_rabbitmq(),
        'disk_space': check_disk_space(),
        'memory': check_memory()
    }
    
    status = 'healthy' if all(checks.values()) else 'unhealthy'
    return {'status': status, 'checks': checks}
```

### Monitoring Script
```bash
#!/bin/bash
# monitor.sh

SERVICES=("auth-service" "clients-service" "deals-service" "orders-service")
API_GATEWAY="http://localhost:8000"

for service in "${SERVICES[@]}"; do
    response=$(curl -s -o /dev/null -w "%{http_code}" $API_GATEWAY/health)
    if [ $response -ne 200 ]; then
        echo "Service $service is down"
        # Send alert
        curl -X POST -H 'Content-type: application/json' \
          --data '{"text":"Service '$service' is down"}' \
          $SLACK_WEBHOOK_URL
    fi
done
```

This deployment guide provides comprehensive instructions for deploying the Export CRM Platform in various environments, from development to production-ready cloud deployments. Choose the deployment method that best fits your infrastructure requirements and scale.

