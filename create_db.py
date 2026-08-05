from app import app, db
# Import models so SQLAlchemy knows what tables to create
import models 

with app.app_context():
    db.create_all()
    print("Database and tables generated successfully.")