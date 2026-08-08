from app import app, db
import models
from werkzeug.security import generate_password_hash

# This script creates the default admin account if it does not already exist.
# It is useful for setting up the project the first time.

with app.app_context():
    # Check whether an admin user already exists before creating one.
    admin_exists = models.User.query.filter_by(role='admin').first()

    if not admin_exists:
        # Create the default admin account with a simple starter password.
        admin = models.User(
            username='admin',
            password=generate_password_hash('admin123'),
            role='admin',
            is_approved=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user locked and loaded.")
    else:
        print("Admin already exists in the database.")
