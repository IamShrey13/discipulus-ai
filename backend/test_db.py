
from app.database import test_database_connection

try:
    result = test_database_connection()
    print(f"Database connection successful: {result}")
except Exception as error:
    print(f"Database connection failed: {error}")
    raise
