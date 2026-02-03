from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, QueuePool
from backend.models.db_models import Base
from backend.config import settings
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


def create_db_engine():
    """
    Create database engine with appropriate settings based on database type.
    
    Supports:
    - SQLite: For local development (single-threaded, static pool)
    - PostgreSQL: For AWS production (connection pooling, optimized for concurrent access)
    """
    database_url = settings.database_url
    
    if database_url.startswith("sqlite"):
        # SQLite configuration for local development
        logger.info("Configuring SQLite database for local development")
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.debug
        )
    elif database_url.startswith("postgresql"):
        # PostgreSQL configuration for AWS production
        logger.info("Configuring PostgreSQL database for production")
        return create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=settings.debug
        )
    else:
        # Default configuration for other databases
        logger.warning(f"Unknown database type, using default configuration: {database_url[:20]}...")
        return create_engine(
            database_url,
            echo=settings.debug
        )


# Create engine based on configuration
engine = create_db_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def get_db() -> Session:
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context():
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()
