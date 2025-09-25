from app.services.db.users import insert_user


if __name__ == "__main__":
    # Datos de prueba
    name = "Allison Karoline"
    email = "erikherazojimenez@outlook.com"

    success = insert_user(name, email)
    if success:
        print("✅ User inserted successfully!")
    else:
        print("❌ User insertion failed.")
