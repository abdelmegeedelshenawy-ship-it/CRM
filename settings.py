"""
Shared configuration settings for CRM platform microservices.
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create database config from environment variables."""
        return cls(
            url=os.getenv('DATABASE_URL', 'postgresql://crm_user:crm_password@localhost:5432/crm_platform'),
            pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '20')),
            pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', '30')),
            pool_recycle=int(os.getenv('DB_POOL_RECYCLE', '3600')),
            echo=os.getenv('DB_ECHO', 'false').lower() == 'true'
        )


@dataclass
class RedisConfig:
    """Redis configuration settings."""
    
    url: str
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    
    @classmethod
    def from_env(cls) -> 'RedisConfig':
        """Create Redis config from environment variables."""
        return cls(
            url=os.getenv('REDIS_URL', 'redis://localhost:6379'),
            max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', '10')),
            socket_timeout=int(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
            socket_connect_timeout=int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5'))
        )


@dataclass
class RabbitMQConfig:
    """RabbitMQ configuration settings."""
    
    url: str
    heartbeat: int = 600
    blocked_connection_timeout: int = 300
    
    @classmethod
    def from_env(cls) -> 'RabbitMQConfig':
        """Create RabbitMQ config from environment variables."""
        return cls(
            url=os.getenv('RABBITMQ_URL', 'amqp://crm_user:crm_password@localhost:5672'),
            heartbeat=int(os.getenv('RABBITMQ_HEARTBEAT', '600')),
            blocked_connection_timeout=int(os.getenv('RABBITMQ_BLOCKED_CONNECTION_TIMEOUT', '300'))
        )


@dataclass
class AuthConfig:
    """Authentication configuration settings."""
    
    secret_key: str
    algorithm: str = 'HS256'
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    @classmethod
    def from_env(cls) -> 'AuthConfig':
        """Create auth config from environment variables."""
        return cls(
            secret_key=os.getenv('JWT_SECRET_KEY', 'your-secret-key-here'),
            algorithm=os.getenv('JWT_ALGORITHM', 'HS256'),
            access_token_expire_minutes=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30')),
            refresh_token_expire_days=int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '7'))
        )


@dataclass
class StorageConfig:
    """File storage configuration settings."""
    
    type: str  # 'local' or 's3'
    local_path: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_region: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_endpoint: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: tuple = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif')
    
    @classmethod
    def from_env(cls) -> 'StorageConfig':
        """Create storage config from environment variables."""
        return cls(
            type=os.getenv('STORAGE_TYPE', 'local'),
            local_path=os.getenv('STORAGE_LOCAL_PATH', '/tmp/crm_uploads'),
            s3_bucket=os.getenv('S3_BUCKET'),
            s3_region=os.getenv('S3_REGION'),
            s3_access_key=os.getenv('S3_ACCESS_KEY'),
            s3_secret_key=os.getenv('S3_SECRET_KEY'),
            s3_endpoint=os.getenv('S3_ENDPOINT'),
            max_file_size=int(os.getenv('MAX_FILE_SIZE', str(10 * 1024 * 1024))),
            allowed_extensions=tuple(os.getenv('ALLOWED_EXTENSIONS', '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif').split(','))
        )


@dataclass
class EmailConfig:
    """Email configuration settings."""
    
    smtp_server: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    use_tls: bool = True
    from_email: str
    from_name: str = 'CRM Platform'
    
    @classmethod
    def from_env(cls) -> 'EmailConfig':
        """Create email config from environment variables."""
        return cls(
            smtp_server=os.getenv('SMTP_SERVER', 'localhost'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_username=os.getenv('SMTP_USERNAME', ''),
            smtp_password=os.getenv('SMTP_PASSWORD', ''),
            use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            from_email=os.getenv('FROM_EMAIL', 'noreply@crm.com'),
            from_name=os.getenv('FROM_NAME', 'CRM Platform')
        )


@dataclass
class SMSConfig:
    """SMS configuration settings."""
    
    provider: str  # 'twilio', 'aws_sns', etc.
    api_key: str
    api_secret: str
    from_number: str
    
    @classmethod
    def from_env(cls) -> 'SMSConfig':
        """Create SMS config from environment variables."""
        return cls(
            provider=os.getenv('SMS_PROVIDER', 'twilio'),
            api_key=os.getenv('SMS_API_KEY', ''),
            api_secret=os.getenv('SMS_API_SECRET', ''),
            from_number=os.getenv('SMS_FROM_NUMBER', '')
        )


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    
    level: str = 'INFO'
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    file_path: Optional[str] = None
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    @classmethod
    def from_env(cls) -> 'LoggingConfig':
        """Create logging config from environment variables."""
        return cls(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            format=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            file_path=os.getenv('LOG_FILE_PATH'),
            max_bytes=int(os.getenv('LOG_MAX_BYTES', str(10 * 1024 * 1024))),
            backup_count=int(os.getenv('LOG_BACKUP_COUNT', '5'))
        )


@dataclass
class AppConfig:
    """Main application configuration."""
    
    environment: str = 'development'
    debug: bool = False
    host: str = '0.0.0.0'
    port: int = 5000
    cors_origins: list = None
    
    # Service configurations
    database: DatabaseConfig = None
    redis: RedisConfig = None
    rabbitmq: RabbitMQConfig = None
    auth: AuthConfig = None
    storage: StorageConfig = None
    email: EmailConfig = None
    sms: SMSConfig = None
    logging: LoggingConfig = None
    
    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ['*']
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Create app config from environment variables."""
        cors_origins = os.getenv('CORS_ORIGINS', '*').split(',')
        
        return cls(
            environment=os.getenv('ENVIRONMENT', 'development'),
            debug=os.getenv('DEBUG', 'false').lower() == 'true',
            host=os.getenv('HOST', '0.0.0.0'),
            port=int(os.getenv('PORT', '5000')),
            cors_origins=cors_origins,
            database=DatabaseConfig.from_env(),
            redis=RedisConfig.from_env(),
            rabbitmq=RabbitMQConfig.from_env(),
            auth=AuthConfig.from_env(),
            storage=StorageConfig.from_env(),
            email=EmailConfig.from_env(),
            sms=SMSConfig.from_env(),
            logging=LoggingConfig.from_env()
        )


# Global configuration instance
config = AppConfig.from_env()


def get_config() -> AppConfig:
    """Get the global configuration instance."""
    return config


def update_config(**kwargs):
    """Update configuration values."""
    global config
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

