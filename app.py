from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import models

# This file contains the main Flask routes for the trekking app.
# It handles user login, registration, dashboards, trekking bookings,
# staff approval, trek creation, and status updates.

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trekking.db'
app.config['SECRET_KEY'] = 'dev-secret-key'

# Connect the database to the Flask app so the models can be used.
models.db.init_app(app)

# Create a shorter name for the database object used throughout the project.
db = models.db

# Redirect the site root to the login page.
@app.route('/')
def home():
    return redirect(url_for('login'))

# Show the registration form and process new user sign-up.
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        # Prevent duplicate usernames.
        existing_user = models.User.query.filter_by(username=username).first()
        if existing_user:
            return "User already exists! Try logging in."

        # Hash the password before saving it so it is not stored as plain text.
        hashed_pw = generate_password_hash(password)

        # Staff accounts need admin approval, while trekkers and admins are approved immediately.
        is_approved = False if role == 'staff' else True

        # Create and save the new user account.
        new_user = models.User(username=username, password=hashed_pw, role=role, is_approved=is_approved)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

# Handle the login form and start a session for the logged-in user.
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = models.User.query.filter_by(username=username).first()

        # Check that the user exists and that the password is correct.
        if user and check_password_hash(user.password, password):
            if not user.is_approved:
                return "Your staff account is pending Admin approval."

            # Store the user identity in the session so other routes can identify them.
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            return "Invalid username or password."

    return render_template('login.html')

# Show the correct dashboard depending on whether the user is an admin, staff, or trekker.
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = models.User.query.get(session['user_id'])

    if user.role == 'admin':
        # Admin dashboard: show overall app statistics and pending staff approvals.
        total_users = models.User.query.filter_by(role='trekker').count()
        total_staff = models.User.query.filter_by(role='staff').count()
        total_treks = models.Trek.query.count()

        pending_staff = models.User.query.filter_by(role='staff', is_approved=False).all()

        return render_template('admin_dashboard.html', user=user,
                               total_users=total_users, total_staff=total_staff,
                               total_treks=total_treks, pending_staff=pending_staff)

    elif user.role == 'staff':
        # Staff dashboard: show only the treks assigned to this staff member.
        my_treks = models.Trek.query.filter_by(staff_id=user.id).all()
        return render_template('staff_dashboard.html', user=user, my_treks=my_treks)

    else:
        # Trekker dashboard: show open treks and the user's booking history.
        search_diff = request.args.get('difficulty')
        search_loc = request.args.get('location')

        query = models.Trek.query.filter_by(status='Open')

        if search_diff:
            query = query.filter(models.Trek.difficulty == search_diff)
        if search_loc:
            query = query.filter(models.Trek.location.ilike(f'%{search_loc}%'))

        available_treks = query.all()

        my_bookings = models.Booking.query.filter_by(user_id=user.id).all()

        return render_template('user_dashboard.html', user=user,
                               available_treks=available_treks, my_bookings=my_bookings)

# Allow a trekker to book an open trek if slots are still available.
@app.route('/book_trek/<int:trek_id>')
def book_trek(trek_id):

    if 'role' not in session or session['role'] != 'trekker':
        return redirect(url_for('dashboard'))

    trek = models.Trek.query.get(trek_id)

    if trek and trek.status == 'Open' and trek.total_slots > 0:
        # Reduce the slot count and create a booking record.
        trek.total_slots -= 1

        new_booking = models.Booking(user_id=session['user_id'], trek_id=trek.id)
        db.session.add(new_booking)

        db.session.commit()

    return redirect(url_for('dashboard'))

# Approve a staff account from the admin dashboard.
@app.route('/approve_staff/<int:id>')
def approve_staff(id):

    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('dashboard'))

    staff = models.User.query.get(id)
    if staff:
        # Set the approval flag to True and save the change.
        staff.is_approved = True
        db.session.commit()

    return redirect(url_for('dashboard'))

# Create a new trek from the admin dashboard form.
@app.route('/create_trek', methods=['GET', 'POST'])
def create_trek():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        difficulty = request.form.get('difficulty')
        location = request.form.get('location')
        total_slots = request.form.get('total_slots')
        staff_id = request.form.get('staff_id')

        print(f"--- DEBUG: Received staff_id from HTML form: {staff_id} ---")

        # Prevent creating a trek without assigning a staff member.
        if not staff_id:
            flash("System Error: You must assign a staff member!")
            return redirect(url_for('create_trek'))

        # Store the new trek in the database.
        new_trek = models.Trek(
            name=name, difficulty=difficulty, location=location,
            total_slots=total_slots, staff_id=int(staff_id)
        )
        db.session.add(new_trek)
        db.session.commit()

        print(f"--- DEBUG: Successfully saved Trek! Assigned to Staff ID: {new_trek.staff_id} ---")
        return redirect(url_for('dashboard'))

    approved_staff = models.User.query.filter_by(role='staff', is_approved=True).all()
    return render_template('create_trek.html', approved_staff=approved_staff)

    approved_staff = models.User.query.filter_by(role='staff', is_approved=True).all()
    return render_template('create_trek.html', approved_staff=approved_staff)

    approved_staff = models.User.query.filter_by(role='staff', is_approved=True).all()
    return render_template('create_trek.html', approved_staff=approved_staff)

# Clear the session and log the current user out.
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Allow staff members to change the status of treks assigned to them.
@app.route('/update_trek_status/<int:trek_id>', methods=['POST'])
def update_trek_status(trek_id):
    if 'role' not in session or session['role'] != 'staff':
        return redirect(url_for('dashboard'))

    trek = models.Trek.query.get(trek_id)

    if trek and trek.staff_id == session['user_id']:
        trek.status = request.form.get('status')
        db.session.commit()

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
