
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables from backend/.env.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Check the backend/.env file."
    )

# Create the PostgreSQL engine.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Create a reusable database session factory.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)

# Base class for SQLAlchemy models.
Base = declarative_base()


def test_database_connection() -> int:
    """Execute a simple query to verify PostgreSQL connectivity."""
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return result.scalar_one()


# Import models after Base is defined so their tables register correctly.
import app.models  # noqa: E402, F401  # pyright: ignore[reportUnusedImport]
