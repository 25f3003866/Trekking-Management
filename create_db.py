from app import app, db

import models

# This script creates all database tables defined by the SQLAlchemy models.
# Run it once when setting up the project for the first time.

with app.app_context():
    db.create_all()
    print("Database and tables generated successfully.")
