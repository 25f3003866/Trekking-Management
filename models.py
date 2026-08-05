from app import db

# Unified User Table to handle Admins, Staff, and Trekkers
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='trekker') 
    is_approved = db.Column(db.Boolean, default=True) 

# Trek Table 
class Trek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Open')