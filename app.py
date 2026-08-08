from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text, or_
from sqlalchemy.exc import NoSuchTableError
import models

# Main routes for the trekking app.
# These cover sign-in, staff approval, bookings, and admin management.

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trekking.db'
app.config['SECRET_KEY'] = 'dev-secret-key'

# Connect the database to the Flask app.
models.db.init_app(app)

# Short name for the database object used through the app.
db = models.db

# Keep older databases compatible with the new approval tracking.
def ensure_user_columns():
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('user')]
        except NoSuchTableError:
            columns = []

        if 'approval_status' not in columns and columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE user ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'approved'"))

        if columns:
            # Backfill existing rows so older databases still behave correctly.
            with db.session.begin():
                models.User.query.filter_by(role='staff', is_approved=True).update({'approval_status': 'approved'})
                models.User.query.filter_by(role='staff', is_approved=False).update({'approval_status': 'pending'})
                models.User.query.filter(models.User.role != 'staff').update({'approval_status': 'approved'})

ensure_user_columns()

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
            flash("That username is already taken.")
            return redirect(url_for('register'))

        # Hash the password before saving it so it is not stored as plain text.
        hashed_pw = generate_password_hash(password)

        # Staff accounts need admin approval, while trekkers and admins are approved immediately.
        is_approved = False if role == 'staff' else True
        approval_status = 'pending' if role == 'staff' else 'approved'

        # Create and save the new user account.
        new_user = models.User(
            username=username,
            password=hashed_pw,
            role=role,
            is_approved=is_approved,
            approval_status=approval_status
        )
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

            if user.is_blacklisted:
                flash("This account has been deactivated by the admin.")
                return redirect(url_for('login'))

            if user.approval_status == 'rejected':
                flash("Your staff account was rejected by the admin.")
                return redirect(url_for('login'))

            if user.approval_status == 'pending':
                flash("Your staff account is still waiting for approval.")
                return redirect(url_for('login'))

            # Store the user identity in the session.
            session['user_id'] = user.id
            session['role'] = user.role
            flash("Welcome back.")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.")
            return redirect(url_for('login'))

    return render_template('login.html')

# Show the correct dashboard depending on whether the user is an admin, staff, or trekker.
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = models.User.query.get(session['user_id'])

    if user.role == 'admin':
        search_query = request.args.get('search', '').strip()

        # Admin dashboard statistics.
        total_users = models.User.query.filter_by(role='trekker').count()
        total_staff = models.User.query.filter_by(role='staff').count()
        total_treks = models.Trek.query.count()
        total_bookings = models.Booking.query.count()
        active_staff = models.User.query.filter_by(role='staff', approval_status='approved', is_blacklisted=False).count()
        available_slots = models.Trek.query.with_entities(db.func.sum(models.Trek.total_slots)).scalar() or 0

        pending_staff = models.User.query.filter_by(role='staff', approval_status='pending').all()
        rejected_staff = models.User.query.filter_by(role='staff', approval_status='rejected').all()

        all_users_query = models.User.query
        all_treks_query = models.Trek.query

        if search_query:
            search_term = f"%{search_query}%"
            try:
                search_id = int(search_query)
            except ValueError:
                search_id = None

            all_users_query = all_users_query.filter(
                or_(models.User.username.ilike(search_term), models.User.role.ilike(search_term), models.User.id == search_id) if search_id is not None else or_(models.User.username.ilike(search_term), models.User.role.ilike(search_term))
            )
            all_treks_query = all_treks_query.filter(
                or_(models.Trek.name.ilike(search_term), models.Trek.location.ilike(search_term), models.Trek.difficulty.ilike(search_term), models.Trek.id == search_id) if search_id is not None else or_(models.Trek.name.ilike(search_term), models.Trek.location.ilike(search_term), models.Trek.difficulty.ilike(search_term))
            )

        all_users = all_users_query.all()
        all_treks = all_treks_query.all()

        return render_template('admin_dashboard.html', user=user,
                               total_users=total_users, total_staff=total_staff,
                               total_treks=total_treks, total_bookings=total_bookings,
                               active_staff=active_staff, available_slots=available_slots,
                               pending_staff=pending_staff, rejected_staff=rejected_staff,
                               all_users=all_users, all_treks=all_treks, search_query=search_query)

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
        existing_booking = models.Booking.query.filter_by(user_id=session['user_id'], trek_id=trek.id).first()

        if existing_booking:
            flash("You already have a booking for this trek.")
        else:
            # Reduce the slot count and create a booking record.
            trek.total_slots -= 1

            new_booking = models.Booking(user_id=session['user_id'], trek_id=trek.id)
            db.session.add(new_booking)

            db.session.commit()
            flash("Your booking was saved.")

    return redirect(url_for('dashboard'))

# Approve a staff account from the admin dashboard.
@app.route('/approve_staff/<int:id>')
def approve_staff(id):

    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('dashboard'))

    staff = models.User.query.get(id)
    if staff and staff.role == 'staff':
        staff.is_approved = True
        staff.approval_status = 'approved'
        db.session.commit()
        flash("Staff account approved.")

    return redirect(url_for('dashboard'))

# Reject a staff account from the admin dashboard.
@app.route('/reject_staff/<int:id>')
def reject_staff(id):

    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('dashboard'))

    staff = models.User.query.get(id)
    if staff and staff.role == 'staff':
        staff.is_approved = False
        staff.approval_status = 'rejected'
        db.session.commit()
        flash("Staff account rejected.")

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
            flash("Please assign a staff member before creating the trek.")
            return redirect(url_for('create_trek'))

        # Store the new trek in the database.
        new_trek = models.Trek(
            name=name, difficulty=difficulty, location=location,
            total_slots=total_slots, staff_id=int(staff_id)
        )
        db.session.add(new_trek)
        db.session.commit()

        flash("The trek was created successfully.")
        print(f"--- DEBUG: Successfully saved Trek! Assigned to Staff ID: {new_trek.staff_id} ---")
        return redirect(url_for('dashboard'))

    approved_staff = models.User.query.filter_by(role='staff', approval_status='approved').all()
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

# Toggle a user's active or blocked state from the admin dashboard.
@app.route('/toggle_blacklist/<int:user_id>')
def toggle_blacklist(user_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('dashboard'))
    
    target_user = models.User.query.get(user_id)
    if target_user and target_user.role != 'admin':
        target_user.is_blacklisted = not target_user.is_blacklisted
        db.session.commit()
        flash("Account status updated.")
    
    return redirect(url_for('dashboard'))

# Enforce Blacklist on Login
# UPDATE your existing login route to check for blacklisting:
# Add this right after `if user and check_password_hash(...)`:
# if user.is_blacklisted:
#     return "Your account has been blacklisted/deactivated by Admin."

# Edit or delete a trek from the admin dashboard.
@app.route('/edit_trek/<int:trek_id>', methods=['GET', 'POST'])
def edit_trek(trek_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('dashboard'))
        
    trek = models.Trek.query.get(trek_id)
    if request.method == 'POST':
        trek.name = request.form.get('name')
        trek.difficulty = request.form.get('difficulty')
        trek.location = request.form.get('location')
        trek.total_slots = int(request.form.get('total_slots'))
        staff_id = request.form.get('staff_id')
        trek.staff_id = int(staff_id) if staff_id else None
        
        db.session.commit()
        flash("The trek details were updated.")
        return redirect(url_for('dashboard'))
        
    approved_staff = models.User.query.filter_by(role='staff', approval_status='approved').all()
    return render_template('edit_trek.html', trek=trek, approved_staff=approved_staff)

@app.route('/delete_trek/<int:trek_id>')
def delete_trek(trek_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('dashboard'))
        
    trek = models.Trek.query.get(trek_id)
    if trek:
        # Remove related bookings before deleting the trek.
        models.Booking.query.filter_by(trek_id=trek.id).delete()
        db.session.delete(trek)
        db.session.commit()
        flash("The trek was removed.")
        
    return redirect(url_for('dashboard'))

# Let a logged-in user update their profile details.
@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = models.User.query.get(session['user_id'])
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        new_password = request.form.get('password', '').strip()

        if new_username:
            existing_user = models.User.query.filter_by(username=new_username).first()
            if existing_user and existing_user.id != user.id:
                flash("That username is already taken.")
                return redirect(url_for('edit_profile'))
            user.username = new_username

        if new_password:
            user.password = generate_password_hash(new_password)

        db.session.commit()
        flash("Your profile was updated.")
        return redirect(url_for('dashboard'))

    return render_template('edit_profile.html', user=user)

# Let assigned staff update the number of slots left for a trek.
@app.route('/update_trek_slots/<int:trek_id>', methods=['POST'])
def update_trek_slots(trek_id):
    if 'role' not in session or session['role'] != 'staff':
        return redirect(url_for('dashboard'))
        
    trek = models.Trek.query.get(trek_id)
    if trek and trek.staff_id == session['user_id']:
        new_slots = request.form.get('total_slots')
        if new_slots:
            trek.total_slots = int(new_slots)
            db.session.commit()
            
    return redirect(url_for('dashboard'))

# Simple API endpoint that returns the current treks as JSON.
@app.route('/api/treks', methods=['GET'])
def api_treks():
    treks = models.Trek.query.all()
    trek_list = []
    for t in treks:
        trek_list.append({
            'id': t.id,
            'name': t.name,
            'difficulty': t.difficulty,
            'location': t.location,
            'total_slots': t.total_slots,
            'status': t.status
        })
    return {'status': 'success', 'treks': trek_list}

if __name__ == '__main__':
    app.run(debug=True)
