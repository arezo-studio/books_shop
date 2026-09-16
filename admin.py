from app import app, db, User

with app.app_context():
    users = User.query.all()
    print("\n--- لیست کاربران ---")
    for u in users:
        print(f"ID: {u.id} | Username: {u.username} | Admin: {u.is_admin}" )
