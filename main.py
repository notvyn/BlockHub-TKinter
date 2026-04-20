import os
from flask import Flask
from sqlalchemy import or_
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Local Application Imports
from extensions import db, login_manager
from models import Users, Announcements, Categories, ClassSummaries, Courses, Deadlines, Links, Schedules  

# Create a Flask Instance
app = Flask(__name__)

# --- DATABASE SETUP (SQLite for Desktop App) ---
# This creates the 'blockhub.db' file in the same folder as this script
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'blockhub.db')

# Secret Key
app.config['SECRET_KEY'] = "secretKey123"

# Initialize the Database and Migration Tools
db.init_app(app)

# Flask_Login Configuration
login_manager.init_app(app)
login_manager.login_view = 'login'