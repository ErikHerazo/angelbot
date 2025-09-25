import os
import pyodbc


# Get environment variables
DB_SERVER   = os.getenv("AZURE_SQL_SERVER")
DB_NAME     = os.getenv("AZURE_SQL_DB")
DB_USER     = os.getenv("AZURE_SQL_USER")
DB_PASSWORD = os.getenv("AZURE_SQL_PASSWORD")
DB_DRIVER   = os.getenv("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")
DB_TIMEOUT  = os.getenv("AZURE_SQL_TIMEOUT", "30")

# connection chain
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

try:
    with pyodbc.connect(CONNECTION_STRING) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT GETDATE();")
            row = cursor.fetchone()
            print("✅ Conexión exitosa a Azure SQL. Fecha/hora del servidor:", row[0])
except pyodbc.Error as e:
    print("❌ Error de conexión a SQL:", e)
except Exception as e:
    print("⚠️ Error inesperado:", e)
