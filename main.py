import os
import sys
import redis
import logging
from logging.handlers import RotatingFileHandler

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'shared'))

from flask import Flask, send_from_directory
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import shared utilities
from shared.models.base import Base, DatabaseManager
from shared.utils.auth import AuthManager
from shared.config.settings import AppConfig

# Import service-specific modules
from src.models.auth_models import User, UserRole
from src.routes.auth import auth_bp
from src.routes.users import users_bp

def create_app():
    """Application factory pattern."""
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Load configuration
    config = AppConfig.from_env()
    
    # Configure Flask app
    app.config['SECRET_KEY'] = config.auth.secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = config.database.url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': config.database.pool_size,
        'max_overflow': config.database.max_overflow,
        'pool_timeout': config.database.pool_timeout,
        'pool_recycle': config.database.pool_recycle,
        'echo': config.database.echo
    }
    
    # Enable CORS for all origins
    CORS(app, origins=config.cors_origins)
    
    # Initialize database
    db_manager = DatabaseManager(config.database.url)
    app.db_manager = db_manager
    
    # Initialize Redis client
    try:
        redis_client = redis.from_url(config.redis.url)
        redis_client.ping()  # Test connection
        app.redis_client = redis_client
    except Exception as e:
        app.logger.warning(f"Redis connection failed: {e}")
        app.redis_client = None
    
    # Initialize auth manager
    app.auth_manager = AuthManager(config.auth.secret_key, app.redis_client)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'auth-service'}, 200
    
    # Serve frontend files
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        static_folder_path = app.static_folder
        if static_folder_path is None:
            return "Static folder not configured", 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                return "index.html not found", 404
    
    # Configure logging
    if not app.debug:
        if config.logging.file_path:
            file_handler = RotatingFileHandler(
                config.logging.file_path,
                maxBytes=config.logging.max_bytes,
                backupCount=config.logging.backup_count
            )
            file_handler.setFormatter(logging.Formatter(config.logging.format))
            file_handler.setLevel(getattr(logging, config.logging.level))
            app.logger.addHandler(file_handler)
        
        app.logger.setLevel(getattr(logging, config.logging.level))
    
    # Create database tables
    with app.app_context():
        try:
            db_manager.create_tables()
            app.logger.info("Database tables created successfully")
        except Exception as e:
            app.logger.error(f"Failed to create database tables: {e}")
    
    return app

app = create_app()

if __name__ == '__main__':
    config = AppConfig.from_env()
    app.run(
        host=config.host,
        port=config.port,
        debug=config.debug
    )

