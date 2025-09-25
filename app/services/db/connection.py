# app/services/db/connection.py
import os
import pyodbc


def get_connection() -> pyodbc.Connection:
    """
    Establish and return a new connection to the Azure SQL Database.

    Environment Variables
    ---------------------
    SQL_SERVER_NAME : str
        The logical SQL server name (e.g., 'myserver').
    SQL_DB_NAME : str
        The database name.
    SQL_ADMIN_USER : str
        The SQL user name.
    SQL_ADMIN_PASS : str
        The SQL user password.
    ODBC_DRIVER : str, optional
        The ODBC driver name. Defaults to 'ODBC Driver 18 for SQL Server'.

    Returns
    -------
    pyodbc.Connection
        A live connection object to the database.

    Raises
    ------
    KeyError
        If any required environment variable is missing.
    pyodbc.Error
        If the connection fails due to invalid credentials or network issues.
    """
    driver = os.getenv("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")

    server = f"{os.environ['SQL_SERVER_NAME']}.database.windows.net"
    db_name = os.environ["SQL_DB_NAME"]
    user = os.environ["SQL_ADMIN_USER"]
    password = os.environ["SQL_ADMIN_PASS"]

    conn_str = f"""
        DRIVER={{{driver}}};
        SERVER={server};
        DATABASE={db_name};
        UID={user};
        PWD={password};
        Encrypt=yes;
        TrustServerCertificate=no;
        Connection Timeout=30;
    """
    return pyodbc.connect(conn_str)
