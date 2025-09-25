from .connection import get_connection


def ensure_users_table() -> None:
    """
    Ensures that the 'users' table exists in the database.
    If it does not exist, it will be created.

    Table schema:
        id    INT PRIMARY KEY IDENTITY(1,1)
        name  NVARCHAR(255) NOT NULL
        email NVARCHAR(255) UNIQUE NOT NULL
    """
    create_table_query = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
    CREATE TABLE users (
        id INT PRIMARY KEY IDENTITY(1,1),
        name NVARCHAR(255) NOT NULL,
        email NVARCHAR(255) UNIQUE NOT NULL
    );
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
    except Exception as error:
        print(f"⚠️ Failed to ensure 'users' table exists: {error}")


def insert_user(name: str, email: str) -> bool:
    """
    Inserts a new user record into the 'users' table.
    Ensures the table exists before attempting insertion.

    Parameters
    ----------
    name : str
        The user's full name.
    email : str
        The user's email address.

    Returns
    -------
    bool
        True if the user was successfully inserted, False otherwise.
    """
    insert_query = """
        INSERT INTO users (name, email)
        VALUES (?, ?);
    """

    try:
        ensure_users_table()  # Make sure the table exists before insertion

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(insert_query, (name, email))
                conn.commit()
        return True

    except Exception as error:
        print(f"❌ Failed to insert user [{email}]: {error}")
        return False
