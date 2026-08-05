from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# 1. Initialize the Flask application
app = Flask(__name__)

# 2. Configure the database and security key
# This tells Flask to create a database file named 'trekking.db' in the current folder.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trekking.db'
app.config['SECRET_KEY'] = 'dev-secret-key' # Required for session management and login

# 3. Link SQLAlchemy to our Flask app
db = SQLAlchemy(app)

# 4. A basic test route to ensure the server works
@app.route('/')
def home():
    return "Trekking App Backend is running!"

if __name__ == '__main__':
    app.run(debug=True)