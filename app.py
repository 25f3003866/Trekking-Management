from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import models # Import the models file

# 1. Configuration
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trekking.db'
app.config['SECRET_KEY'] = 'dev-secret-key'

# 2. Safely connect the database to the app
models.db.init_app(app)

# 3. Create a local reference so your existing code (like db.session.commit) still works
db = models.db 

# ... (Keep all your routes from @app.route('/') downwards exactly as they are) ...

# 1.5 Base Route (Redirects to Login)
@app.route('/')
def home():
    return redirect(url_for('login'))

# 2. Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        # Check if user already exists
        existing_user = models.User.query.filter_by(username=username).first()
        if existing_user:
            return "User already exists! Try logging in."

        # Hash the password for security
        hashed_pw = generate_password_hash(password)
        
        # Determine approval status (Staff need admin approval)
        is_approved = False if role == 'staff' else True

        # Save to database
        new_user = models.User(username=username, password=hashed_pw, role=role, is_approved=is_approved)
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

# 3. Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = models.User.query.filter_by(username=username).first()

        # Check password and approval status
        if user and check_password_hash(user.password, password):
            if not user.is_approved:
                return "Your staff account is pending Admin approval."
            
            # Log the user in by saving their ID in the session dictionary
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            return "Invalid username or password."

    return render_template('login.html')

# 4. Dashboard Route
@app.route('/dashboard')
def dashboard():
    # 1. Security Check
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 2. Identify the User
    user = models.User.query.get(session['user_id'])
    
    # 3. Traffic Control (Role-Based Routing)
    if user.role == 'admin':
        # Gather stats required by the project statement
        total_users = models.User.query.filter_by(role='trekker').count()
        total_staff = models.User.query.filter_by(role='staff').count()
        total_treks = models.Trek.query.count()
        
        # Get staff who need approval
        pending_staff = models.User.query.filter_by(role='staff', is_approved=False).all()
        
        return render_template('admin_dashboard.html', user=user, 
                               total_users=total_users, total_staff=total_staff, 
                               total_treks=total_treks, pending_staff=pending_staff)
                               
    elif user.role == 'staff':
        # Fetch only the treks assigned to the currently logged-in staff member
        my_treks = models.Trek.query.filter_by(staff_id=user.id).all()
        return render_template('staff_dashboard.html', user=user, my_treks=my_treks)
        
    # ... (Keep the admin and staff blocks exactly as they are) ...
    
    else: # This is the Trekker (User) logic
        # 1. Handle Search and Filter Inputs
        search_diff = request.args.get('difficulty')
        search_loc = request.args.get('location')

        # Start with a base query: Only show treks that are 'Open'
        query = models.Trek.query.filter_by(status='Open')

        # Apply filters if the user searched for them
        if search_diff:
            query = query.filter(models.Trek.difficulty == search_diff)
        if search_loc:
            # .ilike() makes the location search case-insensitive
            query = query.filter(models.Trek.location.ilike(f'%{search_loc}%'))
            
        available_treks = query.all()
        
        # 2. Get the user's booking history
        my_bookings = models.Booking.query.filter_by(user_id=user.id).all()
        
        return render_template('user_dashboard.html', user=user, 
                               available_treks=available_treks, my_bookings=my_bookings)

# 3. Book a Trek Route
@app.route('/book_trek/<int:trek_id>')
def book_trek(trek_id):
    # Security: Only trekkers can book
    if 'role' not in session or session['role'] != 'trekker':
        return redirect(url_for('dashboard'))
        
    trek = models.Trek.query.get(trek_id)
    
    # Core Logic: Prevent overbooking and ensure trek is open
    if trek and trek.status == 'Open' and trek.total_slots > 0:
        # 1. Deduct a slot
        trek.total_slots -= 1
        
        # 2. Create the booking record
        new_booking = models.Booking(user_id=session['user_id'], trek_id=trek.id)
        db.session.add(new_booking)
        
        # 3. Save both changes to the database
        db.session.commit()
        
    return redirect(url_for('dashboard'))

# --- ADMIN ACTIONS ---

# 1. Approve Staff Route
@app.route('/approve_staff/<int:id>')
def approve_staff(id):
    # Security: Ensure only admins can do this
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('dashboard'))
    
    # Find the staff member by their ID
    staff = models.User.query.get(id)
    if staff:
        staff.is_approved = True # Change the status
        db.session.commit()      # Save to database
    
    return redirect(url_for('dashboard'))

# 2. Create Trek Route
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
        
        # 1. Print to VS Code terminal to prove what the browser sent
        print(f"--- DEBUG: Received staff_id from HTML form: {staff_id} ---")
        
        # 2. Block the creation if the staff_id is missing
        if not staff_id:
            flash("System Error: You must assign a staff member!")
            return redirect(url_for('create_trek'))
        
        # 3. Save to database
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
        
    # Fetch all approved staff to populate the Admin's dropdown menu
    approved_staff = models.User.query.filter_by(role='staff', is_approved=True).all()
    return render_template('create_trek.html', approved_staff=approved_staff)
        
    # Fetch all approved staff to populate the Admin's dropdown menu
    approved_staff = models.User.query.filter_by(role='staff', is_approved=True).all()
    return render_template('create_trek.html', approved_staff=approved_staff)

# 5. Logout Route
@app.route('/logout')
def logout():
    session.clear() # Wipes the login data
    return redirect(url_for('login'))

@app.route('/update_trek_status/<int:trek_id>', methods=['POST'])
def update_trek_status(trek_id):
    if 'role' not in session or session['role'] != 'staff':
        return redirect(url_for('dashboard'))
        
    trek = models.Trek.query.get(trek_id)
    
    # Security: Ensure the staff modifying this trek is the one assigned to it
    if trek and trek.staff_id == session['user_id']:
        trek.status = request.form.get('status')
        db.session.commit()
        
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)