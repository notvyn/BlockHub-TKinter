from datetime import datetime, timezone
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# DATABASE MODELS
# Create Announcement Database Model
class Announcements(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text)
    link = db.Column(db.String(600), nullable=True)
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Format Date
    def formatted_date(self):
        if self.date_added:
            return self.date_added.strftime("%a, %b %d, %Y")
        return "No Date Available"

    # Foreign Key to Link Users (refer to primary key)
    poster_id = db.Column(db.Integer, db.ForeignKey('users.id'))

# Create Course Database Model
class Categories(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    is_preset = db.Column(db.Boolean, default=False)
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# Create Class Summary Database Model
class ClassSummaries(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Key to Link Users (refer to primary key)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))

    content = db.Column(db.Text)
    scheduled_date = db.Column(db.DateTime, nullable=False)
    note = db.Column(db.Text)
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Format Date
    def formatted_scheduled_date(self):
        if self.scheduled_date:
            return self.scheduled_date.strftime("%a, %b %d, %Y")
        return "No Date Available"

# Create Course Database Model
class Courses(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    instructor = db.Column(db.String(200), nullable=False)
    units = db.Column(db.Numeric(precision=3, scale=2), nullable=False)
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    schedules = db.relationship('Schedules', backref='course', lazy=True, cascade="all, delete-orphan")
    deadlines = db.relationship('Deadlines', backref='course', lazy=True, cascade="all, delete-orphan")
    summaries = db.relationship('ClassSummaries', backref='course', lazy=True, cascade="all, delete-orphan")

# Create Deadlines Database Model
class Deadlines(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Key to Link Users (refer to primary key)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))

    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    category = db.relationship('Categories')

    description = db.Column(db.Text)
    date_given = db.Column(db.DateTime, nullable=False)
    date_deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(120), nullable=False)
    note = db.Column(db.Text, nullable=True)
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    is_archived = db.Column(db.Boolean, default=False)

    # Format Date
    def formatted_date_given(self):
        if self.date_given:
            return self.date_given.strftime("%d-%b-%Y")
        return "No Date Available"
    
    # Format Date
    def formatted_date_deadline(self):
        if self.date_deadline:
            return self.date_deadline.strftime("%a, %b %d, %Y")
        return "No Date Available"

# Create Link Database Model
class Links(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    link = db.Column(db.Text)
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
        
# Create Schedule Database Model
class Schedules(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    day = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))

# Create User Database Model
class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)  
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    role = db.Column(db.String(20), default="student", nullable=False)

    posts = db.relationship('Announcements', backref='poster', cascade="all, delete-orphan")

    # Hashed Password
    password_hash = db.Column(db.String(200), nullable=False)
    
    @property
    def password(self):
        raise AttributeError('Password is not a readable attribute!')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Create A String
    def __repr__(self):
        return '<User %r>' % self.name