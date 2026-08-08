from app import app, db
import models
from werkzeug.security import generate_password_hash

with app.app_context():
    # Check if an admin already exists to prevent duplicates
    admin_exists = models.User.query.filter_by(role='admin').first()
    
    if not admin_exists:
        # Create the superuser
        admin = models.User(
            username='admin',
            password=generate_password_hash('admin123'), # Default password
            role='admin',
            is_approved=True 
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user locked and loaded.")
    else:
        print("Admin already exists in the database.")