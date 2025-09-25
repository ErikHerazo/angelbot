import os
import pyodbc


# -----------------------------------------------------------------------------
# Load environment variables
# These must be defined in your environment (or in your Docker .env file).
# If any of them are missing, the connection attempt will fail.
# -----------------------------------------------------------------------------
DB_SERVER   = os.getenv("AZURE_SQL_SERVER")
DB_NAME     = os.getenv("AZURE_SQL_DB")
DB_USER     = os.getenv("AZURE_SQL_USER")
DB_PASSWORD = os.getenv("AZURE_SQL_PASSWORD")
DB_DRIVER   = os.getenv("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")
DB_TIMEOUT  = os.getenv("AZURE_SQL_TIMEOUT", "30")


# -----------------------------------------------------------------------------
# Build the ODBC connection string.
# Notes:
#   - Encrypt=yes → Required by Azure SQL for secure connections.
#   - TrustServerCertificate=no → Ensures certificate validation is enforced.
#   - Connection Timeout → Maximum time (in seconds) before giving up.
# -----------------------------------------------------------------------------
CONNECTION_STRING = f"""
DRIVER={{{DB_DRIVER}}};
SERVER={DB_SERVER};
DATABASE={DB_NAME};
UID={DB_USER};
PWD={DB_PASSWORD};
Encrypt=yes;
TrustServerCertificate=no;
Connection Timeout={DB_TIMEOUT};
"""

# -----------------------------------------------------------------------------
# Test connection logic
#   1. Attempt to connect to the Azure SQL Database.
#   2. Run "SELECT GETDATE();" to confirm connectivity.
#   3. Print either success (with server datetime) or detailed error message.
# -----------------------------------------------------------------------------
try:
    with pyodbc.connect(CONNECTION_STRING) as conn:     # Connection opens here
        with conn.cursor() as cursor:                   # Cursor context manager
            cursor.execute("SELECT GETDATE();")         # Test query
            row = cursor.fetchone()
            print("✅ Conexión exitosa a Azure SQL. Fecha/hora del servidor:", row[0])
    # Both connection and cursor are automatically closed when exiting the 'with' blocks
except pyodbc.Error as e:
    # Handles database-specific errors (driver, login, network issues)
    print("❌ Error de conexión a SQL:", e)
except Exception as e:
    # Handles any other unexpected exceptions
    print("⚠️ Error inesperado:", e)
