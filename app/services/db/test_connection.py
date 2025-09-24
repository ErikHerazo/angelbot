import pyodbc
import os

DB_SERVER   = os.getenv("AZURE_SQL_SERVER")
DB_NAME     = os.getenv("AZURE_SQL_DB")
DB_USER     = os.getenv("AZURE_SQL_USER")
DB_PASSWORD = os.getenv("AZURE_SQL_PASSWORD")

CONNECTION_STRING = f"""
DRIVER={{ODBC Driver 17 for SQL Server}};
SERVER={DB_SERVER};
DATABASE={DB_NAME};
UID={DB_USER};
PWD={DB_PASSWORD};
Encrypt=yes;
TrustServerCertificate=no;
Connection Timeout=30;
"""

try:
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    cursor.execute("SELECT GETDATE();")
    row = cursor.fetchone()
    print("✅ Conexión exitosa a Azure SQL. Fecha/hora del servidor:", row[0])
    conn.close()
except Exception as e:
    print("❌ Error de conexión:", str(e))
