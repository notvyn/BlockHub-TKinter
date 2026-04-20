# BlockHub: Centralized Student Portal
**Created By: John Calvin Samson, CS-1203**
\
*Final Project for the Course CC 102 | Advance Computer Programming*


## 📖 Project Overview
BlockHub is a comprehensive desktop application designed specifically for Computer Science students to streamline their academic workflow. Built to eliminate the noise and distractions of traditional social media groups, it acts as a dedicated hub for tracking critical deadlines, reading daily class summaries, and accessing important course announcements.

## ✨ Key Features

### 🎯 Smart Dashboard
* **Dynamic Feed:** A quick-glance view of the most urgent deadlines, recent announcements, and today's class summaries.
* **Smart Date Logic:** Automatically calculates and displays contextual tags like *(Today)* or *(Upcoming)* based on the current local time.
* **Personalized Greeting:** Welcomes the active user and provides quick access to profile settings.

### 📅 Advanced Deadline Management
* **Urgency Indicators:** Deadlines are visually color-coded based on temporal proximity:
  * 🔴 **Red:** Urgent (Less than 48 hours)
  * 🟡 **Yellow:** Upcoming (Less than 7 days)
  * 🔵 **Blue:** Planned (More than 7 days)
* **Auto-Archiving:** Tasks that pass their deadline date are automatically moved to a dedicated Archive view to keep the active list clutter-free.

### 📚 Academic Tracking
* **Course & Schedule Manager:** Log subjects, track unit loads, and view weekly schedules sorted chronologically from Monday to Sunday.
* **Class Summaries:** A clean, left-aligned reader view for lecture notes and takeaways, ensuring formatting (like bullet points) is perfectly preserved.
* **Link Parsing:** The application detects URLs in announcements and bookmarks, automatically converting them into clickable buttons that open in your default browser.

### 🔐 Role-Based Access Control
* **Student Role:** Can view all announcements, summaries, and deadlines.
* **Officer Role:** Has administrative privileges to create, edit, and delete records across all modules.

---

## 🛠️ Technology Stack
* **Language:** Python 3
* **Frontend UI:** Tkinter (Custom flat-design overrides, `ttk`, `tkcalendar`)
* **Backend Framework:** Flask Context (for ORM mapping)
* **Database:** SQLite (Local portable `.db` file)
* **ORM:** SQLAlchemy
* **Security:** Werkzeug (Password hashing & verification)

---

## 🚀 Setup & Installation Guide

### 1. Prerequisites
Ensure you have Python 3 installed on your machine.

### 2. Install Dependencies
Open your terminal or command prompt inside the project folder and install the required libraries:
```bash
pip install -r requirements.txt
```

### 3. Database Initialization
If you are running the application for the first time, you must generate the local SQLite database. Open your terminal, type `python` to open the interactive shell, and run the following commands:
```python
from main import app, db
app.app_context().push()
db.create_all()
exit()
```
*This will create a `blockhub.db` file in your root directory.*

### 4. Run the Application
Launch the graphical interface by running:
```bash
python main.py
```

---

## 📋 Usage & Account Guidelines

### Account Creation
To maintain academic integrity, BlockHub enforces strict domain validation for registration. 
* You **must** use a valid university email format (`00-00000@g.batstate-u.edu.ph`) to successfully create an account.
* Passwords must be a minimum of 8 characters.

### Navigation
The application uses a Single-Page Application (SPA) architecture. Use the top navigation bar to switch between the Dashboard, Announcements, Summaries, Courses, Deadlines, and Links.

---

## 📂 Project Structure
* `main.py` - The primary entry point that initializes the Tkinter UI and configures the local database connection.
* `gui.py` - The visual engine containing all Tkinter layouts, navigation routing, and form extraction logic.
* `models.py` - The SQLAlchemy database schemas defining tables for Users, Courses, Deadlines, etc.
* `extensions.py` - Setup files for core plugins.
* `custom_widgets.py` - Contains bespoke UI components like the scrollable canvas wrapper and a custom 12-hour TimePicker.
* `requirements.txt` - The clean, streamlined list of required Python packages.
