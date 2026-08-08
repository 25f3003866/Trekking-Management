from flask_sqlalchemy import SQLAlchemy

# Initialize the SQLAlchemy database object used by the whole app.
db = SQLAlchemy()

# User model stores login information and account role.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='trekker')
    is_approved = db.Column(db.Boolean, default=True)

# Trek model stores the details of each trekking trip.
class Trek(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Open')

    # A trek can be assigned to one staff member.
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    staff = db.relationship('User', backref='assigned_treks')

# Booking model links a user to a trek they have reserved.
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey('trek.id'), nullable=False)
    status = db.Column(db.String(20), default='Confirmed')

    trek = db.relationship('Trek', backref='bookings')
    user = db.relationship('User', backref='my_bookings')
