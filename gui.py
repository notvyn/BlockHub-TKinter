"""
BlockHub GUI Configuration and Initialization
---------------------------------------------
This section handles the environment setup, library imports, and global 
constants required for the Tkinter desktop application.
"""

# 1. Standard Library Imports
import os
import json
import re
import random
import webbrowser
from datetime import datetime, timezone, date
from urllib.parse import urlparse
from collections import defaultdict

# 2. Third-Party Library Imports
import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash

# 3. Local Application Imports
# Importing the Flask-SQLAlchemy setup and models from the backend
from main import (
    app, db, Users, Announcements, Categories, 
    ClassSummaries, Courses, Deadlines, Links, Schedules
)
from custom_widgets import TimePicker, ScrollableFrame

# --- GLOBAL CONFIGURATIONS ---

# Validation pattern for university SR-Code (Format: 00-00000)
SR_CODE_PATTERN = r'^\d{2}-\d{5}$'

# File path for local persistent storage of user session tokens
SESSION_FILE = "user_session.json"

# Application-wide color palette (Hex codes)
COLORS = {
    'gray':      '#343a40', 
    'purple':    '#573280',
    'black':     '#000000',
    'white':     '#ffffff',
    'red':       '#ff3b30',
    'yellow':    '#ffcc00',
    'blue':      '#33A7C8',
    'green':     '#34c759',
    'darkgray':  '#555555',
    'lightgray': '#ECECEC'
}

class MainGUI(tk.Tk):
    """
    The central orchestration layer for the BlockHub Desktop Application.

    BlockHub is a comprehensive academic management tool designed for Computer Science 
    students to centralize deadlines, course materials, and class announcements. 
    This class inherits from `tk.Tk` and acts as the Primary Controller, managing 
    the application lifecycle, user authentication state, and dynamic UI routing.

    The architecture follows a Single-Page Application (SPA) pattern within Tkinter, 
    where a central container is cleared and repopulated to transition between 
    different functional modules (Dashboard, Deadlines, etc.).

    Attributes:
        current_user (Users | None): A reference to the currently authenticated 
            SQLAlchemy User model. If None, the app operates in a restricted 'Guest' state.
        container (tk.Frame): The master UI component that hosts all dynamic screens.
    """

    # ----- Core Lifecycle & Configuration ------
    # handle the startup, styling, and basic housekeeping of the application window.

    def __init__(self):
        """
        Initializes the BlockHub application window and core configurations.

        Sets up the primary window geometry, applies modern 'Clam' theme overrides 
        for flat UI styling, handles the database app context, and triggers 
        the auto-login sequence.
        """
        super().__init__()
        self.title("BlockHub: Class Management and Announcement System")
        self.geometry("1200x700")
        
        # current_user is None until authentication succeeds via login or session restore
        self.current_user = None

        # Container is packed to fill the root window; all screens are children of this frame
        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)
        
        # UI Styling: Modernizing Tkinter's default look
        style = ttk.Style()
        style.theme_use('clam') 
        
        # Standardizing Combobox and DateEntry appearance across the app
        self._apply_custom_styles(style)

        # Automatically populates the Categories table with default school values
        self.seed_categories()

        # Attempt to bypass the login screen if a valid session exists locally
        self._attempt_session_restore()

    def _apply_custom_styles(self, style):
        """
        Applies consistent flat-design styling to TCombobox and DateEntry widgets.

        Args:
            style (ttk.Style): The style object tied to the Tkinter root.
        """
        # Configure the 'clam' theme colors for dropdowns
        style.configure("TCombobox", fieldbackground="white", background="white", borderwidth=0)
        style.configure("DateEntry", borderwidth=0, bordercolor="white")
        
        # Globally force the dropdown listbox (pop-up) to match the app's font and purple theme
        self.option_add('*TCombobox*Listbox.font', ("Arial", 12))
        self.option_add('*TCombobox*Listbox.selectBackground', COLORS['purple'])

        # Forces the background to stay white regardless of state (readonly, hover, etc.)
        style.map('TCombobox', fieldbackground=[('readonly', 'white')])
        style.map('TCombobox', selectbackground=[('readonly', 'white')])
        style.map('TCombobox', selectforeground=[('readonly', 'black')])

        # Softens the DateEntry to match the white background
        style.configure("DateEntry", borderwidth=0, relief="flat", fieldbackground="white", background=COLORS['purple'])

    def _attempt_session_restore(self):
        """
        Checks for a local session file to bypass the login screen.

        Returns:
            None: Redirects to dashboard if successful; otherwise, defaults to 
                the dashboard as a guest user.
        """
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    data = json.load(f)
                    user_id = data.get("user_id")
                    
                # We wrap the query in app_context to interact with the SQLAlchemy model
                with app.app_context():
                    user = Users.query.get(user_id)
                    if user:
                        self.current_user = user
                        self.show_dashboard()
                        return  # Exit early if auto-login works
            except Exception:
                # If the file is corrupt or the user ID no longer exists, we ignore and continue
                pass 
        
        # Fallback to guest dashboard or login screen
        self.show_dashboard()

    def clear_container(self):
        """
        Wipes the main UI workspace to facilitate a clean screen transition.

        This method iterates through every child widget currently packed, 
        gridded, or placed within the master 'container' frame and 
        permanently destroys them. This is essential for preventing 
        'widget stacking' where new screens are drawn over old ones.
        """
        # winfo_children() provides a list of all widgets inside the container
        for widget in self.container.winfo_children():
            widget.destroy()

    def prep_new_screen(self, active_page=None):
        """
        The master transition sequence for rendering a new interface module.

        Every 'show_page' function must call this first. It ensures the 
        previous UI is deleted, the database state is synchronized, and 
        the persistent navigation bar is redrawn with the correct context.

        Args:
            active_page (str, optional): The name of the current module 
                (e.g., 'deadlines') used to highlight the correct navbar button.
        """
        # 1. Clear the old interface
        self.clear_container()
        
        # 2. Sync database (Archive past deadlines before drawing the new view)
        self.auto_archive_deadlines()
        
        # 3. Re-draw the navigation components
        self.show_navbar(active_page)

    def redirect_user(self, frame_id):
        """
        An integer-based router for navigating between primary application screens.

        This centralizes the redirection logic, allowing forms and buttons to 
        request a screen change by ID rather than carrying direct references 
        to view functions.

        Args:
            frame_id (int): The index of the target view function within the 
                internal routing list (e.g., 0 for Dashboard, 4 for Deadlines).
        """
        redirect_to = [
            self.show_dashboard,        # 0
            self.show_announcements,    # 1
            self.show_summaries,        # 2
            self.show_courses,          # 3
            self.show_deadlines,        # 4
            self.show_links,            # 5
            self.show_archive_deadlines # 6
        ]

        # Boundary check to ensure the requested ID exists in the router
        if 0 <= frame_id < len(redirect_to):
            target_function = redirect_to[frame_id]
            target_function()

    def seed_categories(self):
        """Ensures the database has default categories upon startup."""
        default_categories = [
            'Activity', 'Assignment', 'Quiz', 'Exam', 'Project', 
            'Laboratory', 'Recitation', 'Research', 'Group Activity', 
            'Presentation', 'Practical Test', 'Requirements'
        ]
        
        try:
            with app.app_context():
                # Check if any categories exist
                if Categories.query.count() == 0:
                    for cat_title in default_categories:
                        new_cat = Categories(title=cat_title, is_preset=True)
                        db.session.add(new_cat)
                    db.session.commit()
        except Exception as e:
            print(f"⚠️ Seeding Error: {e}")

    # ----- Authentication & Session Management ------
    # Functions related to user identity, security, and account persistence.

    def clear_local_session(self):
        """
        Removes the persistent login token from the local machine.
        
        This is called during logout or account deletion to ensure the 
        '_attempt_session_restore' method doesn't find old credentials.
        """
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)

    def forgot_password(self):
        """
        Orchestrates a three-step password reset workflow.
        
        This method manages local state for OTP verification and uses a 
        simulated email notification system. It dynamically swaps UI frames 
        to guide the user through:
        Step 1: Email verification.
        Step 2: 4-digit OTP entry.
        Step 3: New password configuration.
        """
        frame = self.build_auth_base("Reset your Password")

        # Local state management for the reset process
        self.generated_otp = None
        self.reset_email = None

        # Container initialization for each step
        step1_frame = tk.Frame(frame)
        step2_frame = tk.Frame(frame)
        step3_frame = tk.Frame(frame)

        # Initial View
        step1_frame.pack(fill="x", pady=5)

        # --- STEP 1: EMAIL VERIFICATION ---
        email_entry = self.create_input(step1_frame, "Enter your account Email:")

        def send_otp():
            """Validates user existence and generates a simulated OTP."""
            email = email_entry.get()
            
            with app.app_context():
                user = Users.query.filter_by(email=email).first()
                if not user:
                    messagebox.showerror("Error", "No account found with that email address.")
                    return

            self.reset_email = email
            self.generated_otp = str(random.randint(1000, 9999))

            # DEBUG TIP: In a production app, this would trigger an SMTP mailer.
            email_simulation_text = (
                f"To: {email}\nSubject: Password Reset Request\n\n"
                f"Your BlockHub verification code is: {self.generated_otp}\n\n"
                "(Final project simulation context)"
            )
            messagebox.showinfo("📧 New Email Received!", email_simulation_text)

            # UI Transition
            step1_frame.pack_forget()
            step2_frame.pack(fill="x", pady=5)

        tk.Button(step1_frame, text="Send Verification Code", width=50, bg="#573280", 
                  fg="white", font=("Arial", 12), command=send_otp).pack(pady=10)

        # --- STEP 2: OTP VERIFICATION ---
        tk.Label(step2_frame, text="A code was sent to your email.", fg="green", 
                 font=("Arial", 10, "italic")).pack(anchor="w", pady=(0, 10))
        otp_entry = self.create_input(step2_frame, "Enter the 4-digit code:")

        def verify_otp():
            """Compares user input against the generated OTP."""
            if otp_entry.get() == self.generated_otp:
                step2_frame.pack_forget()
                step3_frame.pack(fill="x", pady=10)
            else:
                messagebox.showerror("Error", "Invalid verification code.")

        tk.Button(step2_frame, text="Verify Code", width=50, bg="#573280", 
                  fg="white", font=("Arial", 12), command=verify_otp).pack(pady=10)

        # --- STEP 3: PASSWORD CONFIGURATION ---
        new_pw_entry = self.create_input(step3_frame, "New Password:", is_password=True)
        confirm_pw_entry = self.create_input(step3_frame, "Confirm New Password:", is_password=True)

        def reset_password():
            """Hashes the new password and commits it to the database."""
            new_pw = new_pw_entry.get()
            
            if new_pw != confirm_pw_entry.get():
                messagebox.showerror("Error", "Passwords do not match.")
                return
            if len(new_pw) < 8:
                messagebox.showerror("Error", "Password must be at least 8 characters.")
                return

            with app.app_context():
                user = Users.query.filter_by(email=self.reset_email).first()
                # Security: Never store plain text passwords
                user.password_hash = generate_password_hash(new_pw)
                db.session.commit()

            messagebox.showinfo("Success", "Password updated! Please log in.")
            self.login()

        tk.Button(step3_frame, text="Reset Password", width=50, bg="#573280", 
                  fg="white", font=("Arial", 12), command=reset_password).pack(pady=5)

        footer_row = tk.Frame(frame)
        footer_row.pack(side="bottom", fill="x", pady=5)
        tk.Button(footer_row, text="← Back to Login", fg="gray", bd=0, 
                  cursor="hand2", font=("Arial", 10, "bold"), command=self.login).pack()

    def is_admin(self):
        """
        Evaluates the authorization level of the current session.

        This is used as a 'Gatekeeper' logic throughout the UI to determine 
        if administrative elements (like 'Add Deadline' or 'Edit' buttons) 
        should be rendered.

        Returns:
            bool: True if the user is authenticated and holds an 'officer' role; 
                  False otherwise (including guests).
        """
        # Safety check: Ensure a user object exists before checking attributes
        if self.current_user:
            return self.current_user.role == 'officer'
        return False

    def login(self):
        """
        Manages user authentication and local session persistence.
        
        Matches user credentials against hashed passwords in the DB. If 'Remember Me' 
        is enabled, it writes the user ID to 'user_session.json'.
        """
        frame = self.build_auth_base("Login to your Account")

        email_entry = self.create_input(frame, "Email:")
        pw_entry = self.create_input(frame, "Password:", is_password=True)

        options_frame = tk.Frame(frame)
        options_frame.pack(fill="x", pady=(5, 15))

        remember_var = tk.BooleanVar() 
        tk.Checkbutton(options_frame, text="Remember Me", variable=remember_var, 
                       font=("Arial", 10)).pack(side="left")

        forgot_pw_label = tk.Label(options_frame, text="Forgot Password?", 
                                   fg=COLORS["purple"], cursor="hand2", 
                                   font=("Arial", 10, "underline"))
        forgot_pw_label.pack(side="right")
        forgot_pw_label.bind("<Button-1>", lambda e: self.forgot_password())

        def attempt_login():
            """Validates credentials and initializes the application session."""
            email, password = email_entry.get(), pw_entry.get()
            with app.app_context():
                user = Users.query.filter_by(email=email).first()
                if user and check_password_hash(user.password_hash, password):
                    self.current_user = user
                    if remember_var.get():
                        self.save_local_session(user.id)
                    self.show_dashboard()
                else:
                    messagebox.showerror("Login Failed", "Invalid email or password.")

        tk.Button(frame, text="Log In", width=50, bg="#573280", fg="white", 
                  font=("Arial", 12), command=attempt_login).pack(pady=10)
        
        footer_row = tk.Frame(frame)
        footer_row.pack(pady=10, anchor="center")
        tk.Label(footer_row, text="Don't have an account?", font=("Arial", 12)).pack(side="left")
        tk.Button(footer_row, text="Sign up", fg="black", bd=0, cursor="hand2", 
                  font=("Arial", 12, "bold"), command=self.signup).pack(side="left")

    def logout(self):
        """
        Destroys the current session and redirects to guest mode.
        """
        self.current_user = None
        self.clear_local_session()
        self.show_dashboard()

    def save_local_session(self, user_id):
        """
        Persists the user's identity to a local JSON file.
        
        Args:
            user_id (int): The primary key of the authenticated user.
        """
        with open(SESSION_FILE, "w") as f:
            json.dump({"user_id": user_id}, f)

    def signup(self):
        """
        Handles new user registration with university-specific validation.
        
        Enforces SR-Code pattern matching and batstate-u.edu.ph domain 
        restrictions to ensure account authenticity.
        """
        frame = self.build_auth_base("Create your Account")

        name_entry = self.create_input(frame, "Name:")
        email_entry = self.create_input(frame, "Email:")
        pw_entry = self.create_input(frame, "Password:", is_password=True)
        confirm_pw_entry = self.create_input(frame, "Confirm Password:", is_password=True)

        tk.Label(frame, text="Select Role:", font=("Arial", 12)).pack(pady=2, anchor="w")
        role_select = ttk.Combobox(frame, values=["student", "officer"], state="readonly")
        role_select.pack(fill="x", pady=(0, 10))

        def attempt_signup():
            """Validates input, hashes passwords, and saves the user record."""
            name, email, password = name_entry.get(), email_entry.get(), pw_entry.get()
            confirm_password, role = confirm_pw_entry.get(), role_select.get()
            
            if not all([name, email, password, role]):
                messagebox.showwarning("Input Error", "All fields are required.")
                return
            
            # University Validation Logic
            sr_code = email.split('@')[0] 
            if not re.match(SR_CODE_PATTERN, sr_code) or not email.endswith("@g.batstate-u.edu.ph"):
                messagebox.showwarning("Input Error", "Enter a valid @g.batstate-u account.")
                return
            elif len(password) < 8:
                messagebox.showerror("Input Error", "Minimum 8 characters required.")
                return
            elif password != confirm_password:
                messagebox.showerror("Input Error", "Passwords do not match.")
                return

            with app.app_context():
                if Users.query.filter_by(email=email).first():
                    messagebox.showerror("Error", "Email already registered.")
                    return

                try:
                    # Security: Hash the password before storage
                    new_user = Users(name=name, email=email, 
                                     password_hash=generate_password_hash(password), 
                                     role=role)
                    db.session.add(new_user)
                    db.session.commit()
                    
                    self.current_user = new_user
                    messagebox.showinfo("Success", "Account created successfully!")
                    self.show_dashboard()
                except Exception as e:
                    db.session.rollback() 
                    messagebox.showerror("Database Error", f"Trace: {str(e)}")

        tk.Button(frame, text="Sign Up", width=50, bg="#573280", fg="white", 
                  font=("Arial", 12), command=attempt_signup).pack(pady=10)

        footer_row = tk.Frame(frame)
        footer_row.pack(pady=10, anchor="center")
        tk.Label(footer_row, text="Already have an account?", font=("Arial", 12)).pack(side="left")
        tk.Button(footer_row, text="Log In", fg="black", bd=0, cursor="hand2", 
                  font=("Arial", 12, "bold"), command=self.login).pack(side="left")

    # ----- Navigation & Global Layout Builders -----
    # High-level structural components that appear across multiple modules.

    def build_content_header_layout(self, title, add_command=None, columns=1, extra_buttons=None, add_button=True, active_page=None):
        """
        Assembles the standard scrollable page framework for browsing records.

        This is the "Mother of all Views." It combines the header bar (with 
        dynamic 'New' buttons) and a scrollable canvas so the app doesn't 
        break if there are 100+ items to display.

        Args:
            title (str): The page title (e.g., 'Deadlines'). Used for the 'New X' button.
            add_command (callable, optional): Function for the 'New' button.
            columns (int): How many columns the content grid should have.
            extra_buttons (bool, optional): If True, adds the 'View Archive' button.
            add_button (bool): Whether to show the 'New' button at all.
            active_page (str, optional): Used to highlight the navbar tab.

        Returns:
            tuple: (header_cont, scrollable_frame)
        """
        # Clear container and set navbar active state
        self.prep_new_screen(active_page)

        # Create the basic frame structure
        header_cont, cards_frame = self.create_content_frame(COLORS["white"], COLORS["black"], title, columns)

        # 1. Grammar Logic: Map plural page titles to singular button text
        # Example: 'Courses' -> 'New Course'
        title_map = {
            "Class Summaries": "Class Summary",
            "Announcements": "Announcement",
            "Categories": "Category",
            "Courses": "Course",
            "Deadlines": "Deadline",
            "Links": "Link",
            "Deadlines Archive": "Deadline"
        }
        title_text = title_map.get(title, title if title else "")

        # 2. Render Action Buttons (Admin Only)
        # DEBUG TIP: If the button doesn't appear, check self.is_admin() logic.
        if self.is_admin() and add_button and add_command:
            tk.Button(header_cont, text=f"New {title_text}", bg=COLORS['purple'], 
                      fg=COLORS['white'], font=("Arial", 10, "bold"), bd=0, 
                      padx=15, pady=8, command=add_command, cursor="hand2").pack(side="right", padx=10)

        # 3. Render Secondary Buttons (e.g., View Archive)
        if extra_buttons:
            tk.Button(header_cont, text="View Archive", bg="#7a7a7a", 
                      fg=COLORS['white'], font=("Arial", 10, "bold"), bd=0, 
                      padx=15, pady=8, command=self.show_archive_deadlines, cursor="hand2").pack(side="right", padx=10)

        # 4. Initialize the Scroller
        # Note: All cards must be children of 'my_scroller.scrollable_frame'
        my_scroller = ScrollableFrame(cards_frame)

        return header_cont, my_scroller.scrollable_frame

    def create_content_frame(self, bg_color, separator_color, title_text, columns):
        """
        Constructs the structural skeleton for a standard application page.

        This method generates a multi-layered layout consisting of a background 
        canvas, a title header, and a responsive grid system. It ensures that 
        every module (Deadlines, Courses, etc.) shares a unified visual 
        hierarchy and spacing.

        Args:
            bg_color (str): The hex color for the main page surface.
            separator_color (str): The hex color for the horizontal rule line.
            title_text (str): The string to display in the primary page header.
            columns (int): The number of grid columns to initialize for content.

        Returns:
            tuple: (header_container, cards_container) 
                - header_container: A frame for adding buttons (like 'Add New') 
                  next to the title.
                - cards_container: The grid frame where individual data cards 
                  should be drawn.
        """
        # 1. PRIMARY BACKGROUND CANVAS
        # This provides a consistent outer margin/gutter for the entire screen
        content_frame = tk.Frame(self.container, padx=10, pady=10, bg=COLORS["lightgray"])
        content_frame.pack(fill="both", expand=True)

        # 2. THE MAIN CONTENT SURFACE
        # The primary 'paper' surface where the information lives
        main_frame = tk.Frame(content_frame, bg=bg_color)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 3. HEADER COMPONENT
        # Holds the page title and provides space for action buttons on the right
        header_cont = tk.Frame(main_frame, bg=bg_color)
        header_cont.pack(fill="x", padx=15, pady=(20, 10))

        tk.Label(header_cont, text=title_text, bg=COLORS['white'], 
                 font=("Arial", 24, "bold")).pack(side="left", padx=10)

        # 4. VISUAL SEPARATOR
        # A thin horizontal rule to delineate the header from the content
        separator = tk.Frame(main_frame, bg=separator_color, height=2)
        separator.pack(fill="x", padx=20, pady=(0, 10))

        # 5. DATA GRID INITIALIZATION
        # The workspace where cards will be arranged
        cards_frame = tk.Frame(main_frame, bg=bg_color)
        cards_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Pre-configure grid weights for consistent alignment
        for i in range(columns):
            cards_frame.columnconfigure(i, weight=1, uniform="group1")
        
        return header_cont, cards_frame

    def show_navbar(self, active_page=None):
        """
        Constructs the persistent global navigation bar with dynamic active-state highlighting.
        
        Uses the 'is_admin' check to decide if the 'New Entry' menu should be visible.
        The layout is divided into Brand (Left), Navigation (Center), and Account (Right).
        """
        nav_frame = tk.Frame(self.container, pady=10)
        nav_frame.pack(fill="x", anchor="center")
        
        tk.Label(nav_frame, text="BlockHub", fg=COLORS["purple"], 
                 font=("Arial", 16, "bold")).pack(side="left", padx=(10, 0), pady=(5, 0))
        
        center_nav = tk.Frame(nav_frame)
        center_nav.place(relx=0.5, rely=0.5, anchor="center")

        def create_nav_btn(text, command, page_id):
            """Internal helper that toggles colors based on current routing."""
            is_active = (active_page == page_id)
            bg_color = COLORS["purple"] if is_active else self.cget("bg")
            fg_color = "white" if is_active else "black"
            
            tk.Button(center_nav, text=text, font=("Arial", 12), bg=bg_color, fg=fg_color, 
                      bd=0, padx=10, pady=2, command=command, cursor="hand2").pack(side="left", padx=5)

        # Admin-only nav entry
        if self.is_admin():
            create_nav_btn("New Entry", self.show_new_entry_menu, "new_entry")
                
        create_nav_btn("Dashboard", self.show_dashboard, "dashboard")
        create_nav_btn("Announcements", self.show_announcements, "announcements")
        create_nav_btn("Class Summary", self.show_summaries, "summaries")
        create_nav_btn("Courses", self.show_courses, "courses")
        create_nav_btn("Deadlines", self.show_deadlines, "deadlines")
        create_nav_btn("Links", self.show_links, "links")

        # Login / Logout toggle
        if self.current_user:
            tk.Button(nav_frame, text="Logout", font=("Arial", 12), command=self.logout).pack(side="right", padx=5)
        else:
            tk.Button(nav_frame, text="SignUp", bg="#573280", fg=COLORS["white"], 
                      font=("Arial", 12), command=self.signup).pack(side="right", padx=10)
            tk.Button(nav_frame, text="Login", fg=COLORS["black"], 
                      font=("Arial", 12), command=self.login).pack(side="right", padx=5)

        tk.Frame(self.container, bg="#000000", height=2).pack(fill="x")

    # ----- Form & Component Factories -----
    # The "UI Engine" that generates inputs, buttons, and validation.

    def create_card_button(self, parent, text=None, model=None, obj_id=None, edit_command=None, refresh_callback=None, text_button=None):
        """
        Constructs a contextual action bar for data cards (Dashboard, Deadlines, etc.).

        This utility automates the creation of 'View', 'Edit', and 'Delete' buttons. 
        It applies conditional logic to hide administrative tools from non-officer 
        users, ensuring that the interface remains secure and uncluttered for 
        standard student accounts.

        Args:
            parent (tk.Widget): The frame where the button row will be packed.
            text (str, optional): Label for the primary action button (e.g., 'View Post').
            model (db.Model, optional): The SQLAlchemy class for deletion operations.
            obj_id (int, optional): The unique database ID of the record being managed.
            edit_command (callable, optional): The function to trigger for editing.
            refresh_callback (callable, optional): The function to reload the view after deletion.
            text_button (callable, optional): The function linked to the primary action button.
        """
        # Container for the buttons, aligned to the bottom-right of the card
        btn_row = tk.Frame(parent, bg="white")
        btn_row.pack(side="bottom", anchor="e", pady=(10, 0))
        
        # --- PRIMARY ACTION BUTTON (VIEW/READ/ADD) ---
        if text and text_button:
            # Check for specialized 'Add Schedule' logic which requires admin rights
            if text_button == self.show_add_schedule_form:
                if self.is_admin():
                    tk.Button(btn_row, text=text, bg=COLORS["purple"], fg="white", 
                              bd=0, padx=10, pady=5, font=("Arial", 8, "bold"), 
                              cursor="hand2", 
                              command=lambda: self.show_add_schedule_form(obj_id)).pack(side="left", padx=5)
            
            # Universal buttons (e.g., 'Read More') available to all users
            else:
                tk.Button(btn_row, text=text, bg=COLORS["purple"], fg="white", 
                          bd=0, padx=10, pady=5, font=("Arial", 8, "bold"), 
                          cursor="hand2", 
                          command=lambda: text_button(obj_id)).pack(side="left", padx=5)
        
        # --- ADMINISTRATIVE CONTROLS (RESTRICTED) ---
        if self.is_admin():
            # Edit Button: Represented by a pencil icon (✎)
            if edit_command:
                tk.Button(btn_row, text="✎", bg="#e5e5e5", fg="black", 
                          font=("Arial", 12), bd=0, width=3, cursor="hand2", 
                          command=lambda: edit_command(obj_id)).pack(side="left", padx=(0, 8))
            
            # Delete Button: Represented by a trash icon (🗑)
            if model and obj_id and refresh_callback:
                tk.Button(btn_row, text="🗑", bg=COLORS['purple'], fg="white", 
                          font=("Arial", 12), bd=0, width=3, cursor="hand2", 
                          command=lambda: self.delete_record(model, obj_id, refresh_callback)).pack(side="left")

    def create_card_grid(self, parent, items, columns, card_builder, date=None):
        """
        An abstract layout manager that distributes data items into a responsive grid.

        This utility handles the geometric calculations for row and column indices. 
        It allows for a decoupled architecture where the grid logic is separate from 
        the specific design of the cards (Deadlines, Courses, etc.), enabling 
        high code reusability across different modules.

        Args:
            parent (tk.Widget): The container where the grid will be packed.
            items (list): A collection of SQLAlchemy model instances to be rendered.
            columns (int): The number of horizontal slots available in the grid.
            card_builder (callable): The specific function responsible for drawing 
                an individual card (e.g., self.build_deadline_card).
            date (datetime.date, optional): If provided, renders a header and 
                separator, grouping the items under a specific calendar day.
        """
        # --- SECTION: OPTIONAL DATE GROUPING ---
        if date: 
            # Format: 'Monday | April 19, 2026'
            date_str = date.strftime('%A | %B %d, %Y')
            tk.Label(parent, text=date_str, font=("Arial", 12), bg="white", 
                     fg="black").pack(anchor="w", padx=20, pady=(10, 5))

            cards_grid = tk.Frame(parent, bg="white")
            cards_grid.pack(fill="both", expand=True, padx=10)

            # Visual horizontal rule to separate date groups
            tk.Frame(parent, bg="black", height=2).pack(fill="x", padx=20, pady=20)
        else:
            cards_grid = tk.Frame(parent, bg="white")
            cards_grid.pack(fill="both", expand=True, padx=10)

        # --- SECTION: GRID CONFIGURATION ---
        # uniform="group1" ensures all columns have the exact same width
        for i in range(columns):
            cards_grid.columnconfigure(i, weight=1, uniform="group1")

        # --- SECTION: MATHEMATICAL MAPPING ---
        for i, item in enumerate(items):
            # i // columns (Integer Division) gives the Row index
            # i % columns (Modulus) gives the Column index
            row = i // columns
            col = i % columns
            
            # Delegation: Pass the calculated coordinates to the specific UI builder
            card_builder(cards_grid, row, col, item)

    def create_field(self, parent, ftype, placeholder, r, c, height):
        """
        A component factory that generates styled input fields with custom borders.

        This method standardizes the look and feel of form inputs by wrapping 
        standard Tkinter and ttk widgets inside a 'shadow' frame. This 
        approach bypasses the limited styling capabilities of native widgets 
        to achieve a modern, flat-design aesthetic.

        Args:
            parent (tk.Widget): The frame where the field and label will be gridded.
            ftype (str): The type of input to create ('textarea', 'combo', 'date', 'time', or 'text').
            placeholder (str): The text used for the field's descriptive label.
            r (int): The base row index in the parent grid.
            c (int): The column index in the parent grid.
            height (int): The height in rows (specifically for 'textarea').

        Returns:
            tk.Widget: A reference to the internal input widget for data retrieval.
        """
        # 1. FIELD LABEL
        # Placed at the top of the assigned slot (row 'r')
        tk.Label(parent, text=placeholder, font=("Arial", 12), bg="white").grid(
            row=r, column=c, padx=(10, 10), pady=(10, 2), sticky="w"
        )

        # 2. CUSTOM BORDER (SHADOW FRAME)
        # This frame acts as the 'border' for the inner widget, allowing for a 
        # consistent 2-pixel flat highlight (row 'r+1')
        shadow = tk.Frame(parent, bg="white", highlightbackground="#d9d9d9", 
                          highlightthickness=2, bd=0, takefocus=0)
        shadow.grid(row=r+1, column=c, padx=(10, 10), pady=(0, 10), sticky="ew")

        # 3. DYNAMIC WIDGET GENERATION
        if ftype == "textarea":
            # Multi-line text input
            widget = tk.Text(shadow, font=("Arial", 12), bd=0, height=height, 
                             width=1, padx=0, pady=2, highlightthickness=0, 
                             wrap="word", cursor="xterm")
            widget.pack(fill="both", expand=True, padx=5, pady=5)

        elif ftype == "combo":
            # Read-only dropdown selection
            widget = ttk.Combobox(shadow, font=("Arial", 12), state="readonly", cursor="xterm")
            widget.pack(fill="both", ipady=8) 

        elif ftype == "date":
            # Calendar picker with BlockHub purple branding
            widget = DateEntry(shadow, font=("Arial", 12), date_pattern='y-mm-dd', 
                               background=COLORS['purple'], foreground='white', 
                               headersbackground=COLORS['purple'], headersforeground='white', 
                               selectbackground=COLORS['purple'], selectforeground='white', 
                               normalbackground='white', normalforeground='black', 
                               cursor="xterm", bd=0, highlightthickness=0)
            widget.pack(fill="x", padx=2, pady=5)

            # UX Enhancement: Open the calendar instantly on single click
            widget.bind("<Button-1>", lambda e: widget.drop_down())

        elif ftype == "time":
            # Custom component for hour/minute selection
            widget = TimePicker(shadow)
            widget.pack(fill="x", expand=True, padx=2, pady=5)

        else:
            # Standard single-line text entry
            widget = tk.Entry(shadow, font=("Arial", 12), bg="white", fg="black", 
                              bd=0, insertbackground="black", cursor="xterm")
            widget.pack(fill="x", ipady=8, padx=2)

        return widget

    def create_form_button(self, parent, Model, frame_id, fields, obj_id=None, optional_fields=None):
        """
        Generates the standard 'Cancel' and 'Save' action pair for input forms.

        This utility handles the final submission logic for all data entry screens. 
        It dynamically binds the 'Save' button to either a creation or an update 
        method based on the presence of an object ID. Both buttons use 'expand=True' 
        and 'fill=x' to ensure a balanced, full-width appearance at the bottom of 
        the form.

        Args:
            parent (tk.Widget): The footer frame where the buttons will be placed.
            Model (db.Model): The SQLAlchemy class representing the data type 
                (e.g., Deadlines, Announcements).
            frame_id (int): The destination ID for 'redirect_user' upon completion 
                or cancellation.
            fields (dict): A collection of widget references containing user input.
            obj_id (int, optional): The ID of an existing record. If provided, 
                the button switches to 'Update' mode.
            optional_fields (list, optional): Keys within 'fields' that are not 
                required for database validation.
        """
        # 1. CANCEL BUTTON
        # Always redirects the user back to the previous view without saving
        tk.Button(parent, text="Cancel", fg=COLORS['white'], bg=COLORS['gray'], 
                  bd=0, cursor="hand2", font=("Arial", 12, "bold"), 
                  command=lambda: self.redirect_user(frame_id)).pack(
                      side="left", padx=5, expand=True, fill="x"
                  )

        # 2. DYNAMIC ACTION LOGIC
        # We use a lambda to delay execution until the user actually clicks
        if obj_id is None:
            # Creation Mode: Triggers a new database entry
            action = lambda: self.save_new_record(Model, fields, frame_id, optional_fields)
        else:
            # Edit Mode: Triggers an update to an existing record
            action = lambda: self.update_existing_record(Model, obj_id, fields, frame_id, optional_fields)

        # 3. SAVE BUTTON
        # Styled with the signature BlockHub purple to indicate the primary action
        tk.Button(parent, text="Save", fg=COLORS['white'], bg=COLORS['purple'], 
                  bd=0, cursor="hand2", font=("Arial", 12, "bold"), 
                  command=action).pack(
                      side="left", padx=5, expand=True, fill="x"
                  )

    def create_form_frame(self, text):
        """
        Builds a centered, high-contrast card layout for data entry and editing.

        This method creates the visual "sheet of paper" effect seen in the 
        Add/Edit screens. It uses relative placement to keep the form centered 
        and 'highlightthickness' to mimic a modern shadow/border effect.

        Args:
            text (str): The title text to be displayed in the purple header bar.

        Returns:
            tuple: (main_frame, footer_row)
                - main_frame: The central area for grid-based input fields.
                - footer_row: The bottom area for Cancel/Save buttons.
        """
        # Reset the UI and sync data before drawing the form
        self.prep_new_screen()

        # 1. Main Background (The 'Canvas' behind the card)
        content_frame = tk.Frame(self.container, bg=COLORS["lightgray"])
        content_frame.pack(fill="both", expand=True)

        # 2. Centered Form Card 
        # DEBUG TIP: If the form looks too narrow, increase 'width'. 
        # If it's too high/low, adjust 'rely' (0.05 = 5% from the top).
        form_card = tk.Frame(content_frame, bg=COLORS['white'], padx=40, pady=30, 
                             highlightbackground="#d9d9d9", highlightthickness=2, takefocus=0)
        form_card.place(relx=0.5, rely=0.05, anchor="n", width=900)

        # 3. Purple Header Label
        # Acts as the "Title Bar" of the form card
        header = tk.Label(form_card, text=text, bg=COLORS["purple"], fg="white", 
                          font=("Arial", 24, "bold"), pady=10)
        header.pack(fill="x", pady=(0, 20))

        # 4. Input Area (Where create_field will place widgets)
        main_frame = tk.Frame(form_card, bg=COLORS['white'])
        main_frame.pack(fill="x")

        # 5. Footer Area (Where create_form_button will place buttons)
        footer_row = tk.Frame(form_card, bg=COLORS['white'])
        footer_row.pack(fill="x", pady=10, anchor="center")

        return main_frame, footer_row

    def create_input(self, parent, label_text, is_password=False):
        """
        A streamlined helper for simple authentication or search entry boxes.

        Unlike 'create_field', this is optimized for vertical stacking (packing) 
        rather than grid placement. Ideal for Login or Register screens.

        Args:
            parent (tk.Widget): The container for the label and entry.
            label_text (str): The text appearing above the entry.
            is_password (bool): If True, masks characters with asterisks (*).

        Returns:
            tk.Entry: The entry widget for .get() calls.
        """
        # Field Label
        tk.Label(parent, text=label_text, font=("Arial", 12)).pack(pady=2, anchor="w")
        
        # Entry Configuration
        # DEBUG TIP: 'show' handles the password masking.
        show_char = "*" if is_password else ""
        entry = tk.Entry(parent, width=50, font=("Arial", 12), show=show_char)
        entry.pack(fill="x", pady=(0, 5))
        
        return entry

    def draw_deadline_urgency_bar(self, parent, deadline_date):
        """
        Renders a color-coded vertical indicator based on deadline proximity.

        This method calculates the temporal distance between the current time 
        (UTC) and the deadline. It then applies a specific color accent to 
        the UI card to visually represent the level of urgency.

        Color Logic:
            - Green: Deadline has passed (Overdue).
            - Red: Less than 48 hours remaining (Urgent).
            - Yellow: Between 2 and 7 days remaining (Upcoming).
            - Blue: More than 7 days remaining (Planned).

        Args:
            parent (tk.Widget): The card frame to which the bar will be attached.
            deadline_date (datetime): The target date/time for the deadline.
        """
        # 1. TEMPORAL NORMALIZATION
        # Ensure 'now' is UTC-aware to prevent subtraction errors with database dates
        now = datetime.now(timezone.utc)

        # Ensure the incoming deadline_date is also UTC-aware
        if deadline_date.tzinfo is None:
            deadline_date = deadline_date.replace(tzinfo=timezone.utc)

        # Push the deadline to 11:59:59 PM of that day
        deadline_date = deadline_date.replace(hour=23, minute=59, second=59)

        # 2. CALCULATION
        time_diff = deadline_date - now
        # Converting timedelta to a float of hours for granular comparison
        hours_left = time_diff.total_seconds() / 3600

        # 3. COLOR SELECTION LOGIC
        if hours_left < 0:
            # Overdue/Closed tasks
            accent_color = COLORS['purple']  
        elif hours_left < 48:
            # Within 2 days
            accent_color = COLORS['red']    
        elif hours_left < 168:
            # Within 1 week (7 days * 24 hours)
            accent_color = COLORS['yellow'] 
        else:
            # Over a week away
            accent_color = COLORS['blue']   

        # 4. COMPONENT RENDERING
        # A narrow vertical frame packed to the right side of the card
        color_bar = tk.Frame(parent, bg=accent_color, width=6)
        color_bar.pack(side="right", fill="y")
        
    def generate_form_fields(self, parent, field_definitions):
        """
        Dynamically generates and organizes input widgets into a multi-column grid.

        This is the core 'Form Engine' of the application. It:
        1. Calculates grid placement based on a 4-field column limit.
        2. Fetches foreign key data (Courses/Categories) from the database.
        3. Creates 'Translation Maps' so dropdowns show text but return IDs.
        4. Attaches these maps directly to the widgets for later extraction.

        Args:
            parent (tk.Widget): The frame where fields will be gridded.
            field_definitions (list): Tuples defining (name, type, label, [height]).

        Returns:
            dict: A mapping of {database_column_name: widget_reference}.
        """
        # Logic: Wrap to a new column after every 4 fields
        max_fields_per_col = 4 
        total_cols = (len(field_definitions) + max_fields_per_col - 1) // max_fields_per_col
        
        for i in range(total_cols):
            parent.columnconfigure(i, weight=1, uniform="equal")

        # Database Synchronization: Fetch list data for Comboboxes
        with app.app_context():
            courses_data = Courses.query.order_by(Courses.id).all()
            categories_data = Categories.query.order_by(Categories.id).all()

            # Translation Maps: { Display Text : Database ID }
            courses_map = {f"{c.code} | {c.title}": c.id for c in courses_data}
            categories_map = {c.title: c.id for c in categories_data}
        
        # Define the content for dropdown menus
        value_map = {
            'course_id': list(courses_map.keys()),
            'category_id': list(categories_map.keys()), 
            'status': ['Pending', 'Upcoming', 'Done', 'Dropped'],
            'day': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        }

        # Store maps for widgets that need to translate selection -> ID
        master_id_maps = {
            'course_id': courses_map,
            'category_id': categories_map
        }

        fields = {}

        for index, field in enumerate(field_definitions):            
            # Math: c = Column Index, r = Row Index (multipled by 2 for Label + Input)
            c = index // max_fields_per_col
            r = (index % max_fields_per_col) * 2  

            # UNPACKING: Extract internal ID name, widget type, and display label text.
            name, ftype, label = field[:3]
            height = field[3] if len(field) > 3 else 3

            # Instantiate the component via our Factory
            widget = self.create_field(parent, ftype, label, r, c, height)
            fields[name] = widget

            # Populate dropdown values if applicable
            if name in value_map:
                widget.configure(values=value_map[name])
                
            # ATTACHMENT: Bind the ID map to the widget object for 'extract_form_data'
            if name in master_id_maps:
                widget.id_map = master_id_maps[name]

        return fields

    def sort_schedule(self, courses):
        """
        Chronologically orders the weekly schedules for a collection of courses.

        Since databases often return rows in the order they were inserted, 
        this method applies a weighted sort to ensure schedules appear from 
        Monday through Sunday in the UI.

        Args:
            courses (list): A list of Course SQLAlchemy objects, each 
                containing a 'schedules' relationship.
        """
        # Assign numeric weights to days for logical sorting
        day_weights = {
            'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 
            'Thursday': 4, 'Friday': 5, 'Saturday': 6, 'Sunday': 7
        }

        for course in courses:
            # Sorts in-place based on the 'day' attribute of the schedule model
            course.schedules.sort(key=lambda s: day_weights.get(s.day, 0))

    def validate_url(self, url):
        """
        Validates if a string follows a proper URL structure.
        Returns the formatted URL if valid, or None if invalid.
        """
        # Regex to check for a basic domain structure (something.something)
        # It ensures there's at least one dot and valid characters.
        url_pattern = re.compile(
            r'^(?:http|ftp)s?://' # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
            r'localhost|' # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?' # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        temp_url = url.strip()
        
        # If it doesn't start with a protocol, prepended for the check
        if not temp_url.startswith(("http://", "https://")):
            # If it doesn't even have a dot, it's definitely not a link
            if "." not in temp_url:
                return None
            temp_url = "https://" + temp_url

        if re.match(url_pattern, temp_url):
            return temp_url
        return None

    # ----- Data Processing & Database Integration -----
    # The "Bridge" between the Tkinter front-end and the SQLAlchemy back-end.
    
    def auto_archive_deadlines(self):
        """
        Synchronizes deadline status and archive visibility with the current date.

        This is a critical maintenance function that:
        1. Refreshes the SQLAlchemy identity map to prevent stale data display.
        2. Evaluates every deadline against today's date.
        3. Automatically transitions past-due items to 'Done' and 'Archived'.
        4. Restores future items accidentally marked archived back to 'Active'.

        Note: 
            This method is called by 'prep_new_screen' to ensure data 
            integrity before any dashboard or list view is rendered.
        """
        try:
            with app.app_context():
                # Force SQLAlchemy to ignore cached memory and fetch from the DB file
                db.session.expire_all()
                
                today = date.today()
                all_deadlines = Deadlines.query.all()
                changes_made = False
                
                for d in all_deadlines:
                    # Defensive parsing: Handles date objects, datetime objects, or strings
                    t_date = d.date_deadline
                    if hasattr(t_date, 'date'): # Check if t_date is date type
                        t_date = t_date.date()
                    elif isinstance(t_date, str): # Check if t_date is string
                        # Transform to date
                        t_date = datetime.strptime(t_date.split()[0], '%Y-%m-%d').date()
                        
                    # Logic: If the deadline has passed (is older than today)
                    if t_date < today:
                        if d.status != 'Done' or d.is_archived != True:
                            d.status = 'Done'
                            d.is_archived = True
                            changes_made = True
                    # Logic: If the deadline is today or in the future
                    else:
                        if d.status != 'Pending' or d.is_archived != False:
                            d.status = 'Pending'
                            d.is_archived = False
                            changes_made = True
                            
                # Commit changes only if the loop found updates (improves performance)
                if changes_made:
                    db.session.commit()
                    
        except Exception as e:
            # Print to console for debugging without interrupting the user experience
            print(f"⚠️ Tkinter Auto-Archive Error: {e}")

    def delete_account(self):
        """
        Executes a destructive wipe of the current user's profile and session.
        
        Includes a critical confirmation check and 'try-except' block to handle
        potential database integrity errors (e.g., restricted foreign keys).
        """
        confirm = messagebox.askyesno(
            "Delete Account", 
            "Are you absolutely sure? This action cannot be undone."
        )
        
        if confirm:
            try:
                with app.app_context():
                    user_to_delete = Users.query.get(self.current_user.id)
                    if user_to_delete:
                        db.session.delete(user_to_delete)
                        db.session.commit()
                
                # Cleanup local state
                self.current_user = None
                self.clear_local_session()
                
                messagebox.showinfo("Account Deleted", "Your account has been successfully deleted.")
                self.show_dashboard()
                
            except Exception as e:
                # DEBUG TIP: Check if this user is linked to other records (Announcements/Courses)
                # that have 'RESTRICT' delete rules in the database schema.
                messagebox.showerror("Database Error", f"Could not delete account. \nError: {str(e)}")

    def delete_record(self, Model, obj_id, refresh_callback):
        """
        A universal utility to remove any database record by ID.
        
        Args:
            Model (db.Model): The SQLAlchemy class (e.g., Deadlines).
            obj_id (int): The primary key of the record.
            refresh_callback (callable): The function to redraw the UI after deletion.
        """
        confirm = messagebox.askyesno("Delete", "Are you sure? This cannot be undone.")
        
        if confirm:
            with app.app_context():
                obj = Model.query.get(obj_id)
                if obj:
                    db.session.delete(obj)
                    db.session.commit()
            
            # DEBUG TIP: Ensure the callback doesn't require arguments.
            if refresh_callback:
                refresh_callback()

    def extract_form_data(self, fields, maps=None, optional_fields=None):
        """
        Scrapes data from UI widgets and converts it into a DB-ready dictionary.
        
        This function handles the heavy lifting of:
        1. Determining widget types (Text, Entry, DateEntry, etc.).
        2. Sanitizing strings (.strip()).
        3. Mapping readable Combobox text back into integer IDs.
        4. Validating university-specific email patterns.
        
        Returns:
            dict | None: The cleaned data or None if validation fails.
        """
        if maps is None: maps = {}
        if optional_fields is None: optional_fields = ['note']

        clean_data = {}
        
        for column_name, widget in fields.items():
            # Widget extraction logic
            if isinstance(widget, tk.Text):
                value = widget.get("1.0", "end-1c").strip()
            elif hasattr(widget, "get_date"):
                value = widget.get_date()
            elif column_name.endswith("_id") and hasattr(widget, "id_map"):
                selected = widget.get()
                value = widget.id_map.get(selected)
                if value is None:
                    messagebox.showwarning("Selection Required", f"Select a valid {column_name[:-3].title()}.")
                    return None
            elif isinstance(widget, TimePicker):
                time_str = widget.get()
                value = datetime.strptime(time_str, "%H:%M").time() if time_str else None
            elif hasattr(widget, "get"):
                value = widget.get()
                if isinstance(value, str): value = value.strip()
            else:
                value = widget
                
            clean_data[column_name] = value

        # --- VALIDATION LAYER ---
        for key, val in clean_data.items():
            # Required Field Check
            if key not in optional_fields and (val is None or val == ""):
                messagebox.showwarning("Incomplete Form", f"Missing: {key.replace('_id', '').title()}")
                return None
            
            # University Email Validation (@g.batstate-u.edu.ph)
            if key == 'email':
                sr_code = val.split('@')[0] 
                if not re.match(SR_CODE_PATTERN, sr_code) or not val.endswith("@g.batstate-u.edu.ph"):
                    messagebox.showwarning("Input Error", "Enter a valid @g.batstate-u account.")
                    return None

        return clean_data

    def populate_form_data(self, fields, obj, formatters=None):
        """
        Pre-fills form widgets with data from an existing database record.
        
        This is the inverse of 'extract_form_data'. It performs a 'Reverse Lookup'
        on IDs to show readable text (e.g., 'CC 102') in dropdowns instead of integers.
        """
        if formatters is None: formatters = {}

        for column_name, widget in fields.items():
            value = getattr(obj, column_name, None)
            
            # Handle SQLAlchemy relationship objects (convert to ID)
            if hasattr(value, '_sa_instance_state'):
                value = getattr(value, 'id', value)
                
            if value is None: value = ""

            # Apply any special string formatting (e.g., date formatting)
            if column_name in formatters and value:
                value = formatters[column_name](value)

            # REVERSE LOOKUP: Convert ID to Display Name for Comboboxes
            if hasattr(widget, "id_map") and value:
                reverse_map = {v: k for k, v in widget.id_map.items()}
                value = reverse_map.get(value, value) 
                
            # Insert data into specific widget types
            if isinstance(widget, tk.Text):
                widget.delete("1.0", "end")
                widget.insert("1.0", value)
            elif hasattr(widget, "set_date") and value:
                widget.set_date(value)
            elif isinstance(widget, TimePicker):
                widget.set(value)
            elif isinstance(widget, ttk.Combobox):
                widget.set(str(value))
            elif hasattr(widget, "insert"):
                widget.delete(0, "end")
                widget.insert(0, str(value))

    def save_new_record(self, Model, fields, frame_id, optional_fields=None):
        """Extracts data and commits a NEW row to the database."""
        clean_data = self.extract_form_data(fields, optional_fields=optional_fields)
        if clean_data is None: return

        with app.app_context():
            new_record = Model(**clean_data) 
            db.session.add(new_record)
            db.session.commit()

        self.redirect_user(frame_id)

    def update_existing_record(self, Model, obj_id, fields, frame_id, optional_fields=None):
        """Extracts data and updates an EXISTING row in the database."""
        clean_data = self.extract_form_data(fields, optional_fields=optional_fields)
        if clean_data is None: return

        with app.app_context():
            record = Model.query.get(obj_id)
            for key, value in clean_data.items():
                setattr(record, key, value)
            db.session.commit()

            # DEBUG TIP: Refresh self.current_user if the Profile was edited
            if Model == Users and self.current_user and self.current_user.id == obj_id:
                self.current_user.name = clean_data.get('name', self.current_user.name)
                self.current_user.email = clean_data.get('email', self.current_user.email)

        self.redirect_user(frame_id)

    # ----- Module View Controllers ("Show" Functions) -----
    # The primary entry points for each module. These handle data fetching.
    
    def show_announcements(self):
        """
        Displays a chronological 2-column feed of all announcements.
        
        Fetches the total count for the header and joins the 'poster' 
        relationship to display user names on each card.
        """
        header_cont, scrollable_content = self.build_content_header_layout(
            title='Announcements', add_command=self.show_add_announcement_form, 
            columns=2, active_page="announcements"
        )

        with app.app_context():
            total_announcements = Announcements.query.count()
            # Sort by date added (Newest First)
            announcements = Announcements.query.options(joinedload(Announcements.poster)).order_by(
                Announcements.date_added.desc()
            ).all()

        # Metadata Header Label
        tk.Label(header_cont, text=f"Total Announcements: {total_announcements}", bg=COLORS['white'], 
                 fg="gray", font=("Arial", 10), pady=8).pack(side="right", padx=10)

        if not announcements:
            tk.Label(scrollable_content, text="No announcements posted", 
                     bg="white", fg="gray", font=("Arial", 12, "italic")).pack(pady=50)
        else:
            self.create_card_grid(parent=scrollable_content, items=announcements, 
                                  columns=2, card_builder=self.build_announcement_card)

    def show_archive_deadlines(self):
        """
        Renders a specialized view for completed or past-due deadlines.
        
        Filtering logic focuses exclusively on 'is_archived=True' records.
        """
        header_cont, scrollable_content = self.build_content_header_layout(
            title='Deadlines Archive', add_command=self.show_add_deadline_form, 
            columns=1, active_page="deadlines"
        )

        # Archive-specific navigation button
        tk.Button(header_cont, text="View Active Deadlines", bg="#7a7a7a", 
                  fg=COLORS['white'], font=("Arial", 10, "bold"), bd=0, padx=15, pady=8, 
                  command=self.show_deadlines, cursor="hand2").pack(side="right", padx=10)

        with app.app_context():
            # Query Logic: Filter for archived status
            deadlines = Deadlines.query.options(
                joinedload(Deadlines.course), joinedload(Deadlines.category)
            ).filter_by(is_archived=True).order_by(Deadlines.date_deadline.desc()).all()
            
            total_deadlines = len(deadlines)

        tk.Label(header_cont, text=f"Total Archived Deadlines: {total_deadlines}", bg=COLORS['white'], 
                 fg="gray", font=("Arial", 10), pady=8).pack(side="right", padx=10)

        if not deadlines:
            tk.Label(scrollable_content, text="No archived deadlines", 
                     bg="white", fg="gray", font=("Arial", 12, "italic")).pack(pady=50)
        else:
            self.create_card_grid(parent=scrollable_content, items=deadlines, 
                                  columns=1, card_builder=self.build_deadline_card) 

    def show_courses(self):
        """
        Displays the student's curriculum and calculates academic load.
        
        Pre-sorts nested schedules and sums unit values to display 
        the total credit load in the header.
        """
        header_cont, scrollable_content = self.build_content_header_layout(
            title='Courses', add_command=self.show_add_course_form, 
            columns=1, active_page="courses"
        )

        with app.app_context():
            courses = Courses.query.options(joinedload(Courses.schedules)).all()
            self.sort_schedule(courses)

            # Summation Logic: Converts unit strings to floats for math
            total_units = sum(float(c.units) for c in courses if c.units)
            total_courses = len(courses)

        tk.Label(header_cont, text=f"Total Units: {total_units}", bg=COLORS['white'], 
                 fg="gray", font=("Arial", 10), pady=8).pack(side="right", padx=10)

        tk.Label(header_cont, text=f"Total Courses: {total_courses}", bg=COLORS['white'], 
                 fg="gray", font=("Arial", 10), pady=8).pack(side="right", padx=10)

        if not courses:
            tk.Label(scrollable_content, text="No courses added", 
                     bg="white", fg="gray", font=("Arial", 12, "italic")).pack(pady=50)
        else:
            self.create_card_grid(parent=scrollable_content, items=courses, 
                                  columns=1, card_builder=self.build_course_card) 

    def show_dashboard(self):
        """
        The application's landing page and command center.
        
        Aggregates data from five distinct models and distributes them 
        into a weighted responsive grid. Features 'Lazy Loading' limits 
        (e.g., .limit(3)) to keep the dashboard performant and clean.
        """
        self.prep_new_screen("dashboard")

        # 1. DATA AGGREGATION
        with app.app_context():
            # Recent Deadlines (Next 3 tasks)
            pending_deadlines = Deadlines.query.options(
                joinedload(Deadlines.course), joinedload(Deadlines.category)
            ).filter_by(is_archived=False).order_by(Deadlines.date_deadline).limit(3).all()
            total_d = Deadlines.query.filter_by(is_archived=False).count()

            # Bookmarked Links
            links_list = Links.query.order_by(Links.date_added).limit(4).all()
            
            # Global Announcements
            announcements = Announcements.query.order_by(Announcements.date_added.desc()).limit(5).all()

            # Latest Summary Logic: Finds the most recent record that isn't in the future
            target_record = ClassSummaries.query.filter(
                ClassSummaries.scheduled_date <= date.today()
            ).order_by(ClassSummaries.scheduled_date.desc()).first()
            
            daily_summaries = []
            if target_record:
                daily_summaries = ClassSummaries.query.options(joinedload(ClassSummaries.course)).filter(
                    ClassSummaries.scheduled_date == target_record.scheduled_date
                ).all()

        # 2. DASHBOARD GRID GEOMETRY
        # DEBUG TIP: 'weight' determines how extra space is divided. 
        # Column 1 (Deadlines) is 3x wider than Columns 0 and 2.
        content_grid = tk.Frame(self.container, bg="#ECECEC", padx=10, pady=10)
        content_grid.pack(fill="both", expand=True)
        
        content_grid.columnconfigure(0, weight=1) # Profile Widget
        content_grid.columnconfigure(1, weight=3) # Deadlines Widget
        content_grid.columnconfigure(2, weight=1) # Links Widget
        content_grid.rowconfigure(1, weight=1)    # Bottom Row (Announcements/Summaries)

        # 3. COMPONENT ASSEMBLY
        # Top Row
        self.build_dash_profile(content_grid, row=0, col=0)
        self.build_dash_deadlines(content_grid, pending_deadlines, total_d, row=0, col=1)
        self.build_dash_links(content_grid, links_list, row=0, col=2)

        # Bottom Row
        self.build_dash_announcements(content_grid, announcements, row=1, col=0)
        self.build_dash_summaries(content_grid, daily_summaries, target_record, row=1, col=2)

    def show_deadlines(self):
        """
        Fetches active deadlines and renders them with a color-coded urgency legend.

        Ordering is handled by date (soonest first). This view serves as the primary
        task management hub for students, clearly displaying 'Pending' vs 'Urgent' states.
        """
        header_cont, scrollable_content = self.build_content_header_layout(
            title='Deadlines', add_command=self.show_add_deadline_form, 
            columns=1, active_page="deadlines"
        )

        tk.Button(header_cont, text="View Archive", bg="#7a7a7a", fg=COLORS['white'], 
                  font=("Arial", 10, "bold"), bd=0, padx=15, pady=8, 
                  command=self.show_archive_deadlines, cursor="hand2").pack(side="right", padx=10)

        with app.app_context():
            total_deadlines = Deadlines.query.filter_by(is_archived=False).count()
            # Sort by date_deadline (Ascending for most urgent first)
            deadlines = Deadlines.query.options(
                joinedload(Deadlines.course), joinedload(Deadlines.category)
            ).filter(Deadlines.is_archived==False).order_by(Deadlines.date_deadline).all()

        tk.Label(header_cont, text=f"Total Deadlines: {total_deadlines}", 
                 bg=COLORS['white'], fg="gray", font=("Arial", 10), pady=8).pack(side="right", padx=10)

        # THE LEGEND 
        # DEBUG TIP: This visually explains what the color bars on the cards mean.
        legend_frame = tk.Frame(header_cont, bg="white")
        legend_frame.pack(side="right", padx=15)

        def add_dot(text, color):
            item = tk.Frame(legend_frame, bg="white")
            item.pack(side="left", padx=5)
            tk.Frame(item, bg=color, width=10, height=10).pack(side="left", padx=(0, 4))
            tk.Label(item, text=text, bg="white", fg="gray", font=("Arial", 8)).pack(side="left")

        add_dot("< 2 days", COLORS['red'])
        add_dot("< 7 days", COLORS['yellow'])
        add_dot("> 7 days", COLORS['blue'])

        if not deadlines:
            tk.Label(scrollable_content, text="You're all caught up! ✅\nNo active deadlines right now.", 
                     bg="white", fg="gray", font=("Arial", 12, "italic")).pack(pady=50)
        else:
            self.create_card_grid(parent=scrollable_content, items=deadlines, 
                                  columns=1, card_builder=self.build_deadline_card) 

    def show_links(self):
        """Retrieves and renders all external bookmarks in a scrollable list."""
        header_cont, scrollable_content = self.build_content_header_layout(
            title='Links', add_command=self.show_add_link_form, 
            columns=1, active_page="links"
        )

        with app.app_context():
            links = Links.query.all()
            total_links = len(links)

        tk.Label(header_cont, text=f"Total Links: {total_links}", bg=COLORS['white'], 
                 fg="gray", font=("Arial", 10), pady=8).pack(side="right", padx=10)
        
        if not links:
            tk.Label(scrollable_content, text="No links yet", 
                     bg="white", fg="gray", font=("Arial", 12, "italic")).pack(pady=50)
        else:
            self.create_card_grid(parent=scrollable_content, items=links, 
                                  columns=1, card_builder=self.build_link_card)
     
    def show_new_entry_menu(self):
        """
        Renders the administrative hub for creating new database records.
        
        This acts as a 'Switchboard' for officers, providing large, 
        accessible buttons for every 'Add' form in the system.
        """
        # Initialize standard header; add_button=False as this IS the add menu
        header_cont, scrollable_content = self.build_content_header_layout(
            "New Entry", add_command=None, columns=1, 
            add_button=False, active_page="new_entry"
        )

        # Back Navigation
        tk.Button(header_cont, text="← Back", bg=COLORS['gray'], fg="white", 
                  font=("Arial", 10, "bold"), bd=0, padx=15, pady=8, 
                  command=self.show_dashboard, cursor="hand2").pack(side="right", padx=10)

        # Central Card for buttons
        card = tk.Frame(scrollable_content, bg="white", 
                        highlightbackground="#d9d9d9", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        def create_entry_button(text, command):
            """Internal helper for uniform vertical menu buttons."""
            tk.Button(card, text=text, font=("Arial", 16, "bold"), bg="white", 
                      fg=COLORS['purple'], cursor="hand2", 
                      command=command).pack(side="top", fill="both", expand=True, padx=10, pady=10)

        # Primary Admin Actions
        create_entry_button("Add Announcement", self.show_add_announcement_form)
        create_entry_button("Add Class Summary", self.show_add_summary_form)
        create_entry_button("Add Course", self.show_add_course_form)
        create_entry_button("Add Deadline", self.show_add_deadline_form)
        create_entry_button("Add Link", self.show_add_link_form)

    def show_summaries(self):
        """
        Displays lecture summaries grouped by date in a 3-column chronological grid.
        
        Includes advanced sorting: descending by date, then ascending by class start time.
        """
        header_cont, scrollable_content = self.build_content_header_layout(
            title='Class Summaries', add_command=self.show_add_summary_form, 
            columns=3, active_page="summaries"
        )

        with app.app_context():
            total_summaries = ClassSummaries.query.count()
            # Complex Sort: Date (Newest) -> Class Time (Morning first)
            summaries = ClassSummaries.query\
                .join(ClassSummaries.course)\
                .outerjoin(Courses.schedules)\
                .options(joinedload(ClassSummaries.course))\
                .order_by(ClassSummaries.scheduled_date.desc(), Schedules.start_time.asc())\
                .all()

        tk.Label(header_cont, text=f"Total Summaries: {total_summaries}", bg=COLORS['white'], 
                 fg="gray", font=("Arial", 10), pady=8).pack(side="right", padx=10)

        if not summaries:
            tk.Label(scrollable_content, text="No summaries found", 
                     bg="white", fg="gray", font=("Arial", 12, "italic")).pack(pady=50)
        else:
            grouped = defaultdict(list)
            for s in summaries:
                grouped[s.scheduled_date].append(s)

            sorted_dates = sorted(grouped.keys(), reverse=True)
            for s_date in sorted_dates:
                self.create_card_grid(parent=scrollable_content, items=grouped[s_date], 
                                      columns=3, card_builder=self.build_summary_card, date=s_date)

    def show_users(self):
        """
        Renders the Administrative User Management panel.
        
        Queries the database for all registered accounts and displays them 
        using the 'build_user_card' template. This view is restricted to 
        officers via the Navbar logic.
        """
        # Build the standard page layout
        header_cont, scrollable_content = self.build_content_header_layout(title="Users", columns=1)

        with app.app_context():
            total_users = Users.query.count()
            # Sort by registration date (Newest first)
            users = Users.query.order_by(Users.date_added.desc()).all()

        # Display total user count in the header
        tk.Label(header_cont, text=f"Total Users: {total_users}", bg=COLORS['white'], 
                 fg="gray", font=("Arial", 10), pady=8).pack(side="right", padx=10)

        if not users:
            tk.Label(scrollable_content, text="No users found", bg="white", 
                     fg="gray", font=("Arial", 12, "italic")).pack(pady=50)
        else:
            # Map user data into a 1-column card grid
            self.create_card_grid(parent=scrollable_content, items=users, 
                                  columns=1, card_builder=self.build_user_card)

    # ----- Form & Post Interface Controllers ("View/Add/Edit") -----
    # Specific UI interactions for individual records and data entry.

    def show_add_announcement_form(self):
        """Creates a new announcement and auto-links it to the current user."""
        frame, footer = self.create_form_frame("Add Announcement")

        fields = self.generate_form_fields(frame, [
            ("title", "text", "Title:"),
            ("content", "textarea", "Content:", 6),
            ("link", "textarea", "Links (Format -> Title: https://...):", 3)  
        ])

        if self.current_user:
            fields["poster_id"] = self.current_user.id
        
        self.create_form_button(footer, Announcements, 1, fields, optional_fields=['link'])

    def show_add_course_form(self):
        """Initializes a blank form for course creation."""
        frame, footer = self.create_form_frame("Add Course")
        fields = self.generate_form_fields(frame, [
            ("code", "text", "Code:"),
            ("title", "text", "Title:"),
            ("instructor", "text", "Instructor:"),
            ("units", "text", "Unit/s:")
        ])
        self.create_form_button(footer, Courses, 3, fields)

    def show_add_deadline_form(self):
        """Renders the deadline creation form with a course existence check."""
        with app.app_context():
            if Courses.query.count() == 0:
                messagebox.showwarning("No Courses Found", "Add a Course before creating a Deadline.")
                self.show_courses()
                return
        
        frame, footer = self.create_form_frame("Add Deadline")
        fields = self.generate_form_fields(frame, [
            ("course_id", "combo", "Course:"),
            ("description", "text", "Title/Description:"),
            ("category_id", "combo", "Category:"),
            ("date_given", "date", "Date Given:"),
            ("date_deadline", "date", "Deadline:"),
            ("status", "combo", "Status:"),
            ("note", "textarea", "Note/s:")
        ])
        self.create_form_button(footer, Deadlines, 4, fields)

    def show_add_link_form(self):
        """Renders a simple form for adding external resource URLs."""
        frame, footer = self.create_form_frame("Add Link")
        fields = self.generate_form_fields(frame, [
            ("title", "text", "Title:"),
            ("link", "text", "Link:")
        ])
        self.create_form_button(footer, Links, 5, fields)

    def show_add_schedule_form(self, obj_id):
        """
        Creates a time-slot entry for a specific course.
        
        Args:
            obj_id (int): The ID of the Course this schedule belongs to.
        """
        with app.app_context():
            course = Courses.query.get(obj_id)
            course_code = course.code if course else "Unknown Course"

        frame, footer = self.create_form_frame(f"Add Schedule for {course_code}")
        fields = self.generate_form_fields(frame, [
            ("day", "combo", "Day:"),
            ("start_time", "time", "Start Time:"),
            ("end_time", "time", "End Time:")
        ])
        
        # Logic: Inject the parent course ID into the fields dict manually
        fields["course_id"] = obj_id
        self.create_form_button(footer, Schedules, 3, fields)

    def show_add_summary_form(self):
        """Renders the class summary logger with a subject existence check."""
        with app.app_context():
            if Courses.query.count() == 0:
                messagebox.showwarning("No Courses Found", "Add a Course before logging a Summary.")
                self.show_courses()
                return

        frame, footer = self.create_form_frame("Add Class Summary")
        fields = self.generate_form_fields(frame, [
            ("course_id", "combo", "Course:"),
            ("scheduled_date", "date", "Scheduled Date:"),
            ("content", "textarea", "Content:"),
            ("note", "textarea", "Note/s:")    
        ])
        self.create_form_button(footer, ClassSummaries, 2, fields)

    def show_edit_announcement_form(self, obj_id):
        """
        Loads the announcement editor.
        
        Fetches an existing announcement and pre-fills the form. The 'links' field 
        uses a specific 'Title: URL' format for parsing during the save process.
        """
        with app.app_context():
            announcements = Announcements.query.get(obj_id)

        frame, footer = self.create_form_frame("Edit Announcement")
        fields = self.generate_form_fields(frame, [
            ("title", "text", "Title:"),
            ("content", "textarea", "Content:", 6),
            ("link", "textarea", "Links (Format -> Title: https://...):", 3)    
        ])

        self.populate_form_data(fields, announcements)
        # Redirect ID 1: Announcements Page
        self.create_form_button(footer, Announcements, 1, fields, obj_id=obj_id, optional_fields=['link'])
    
    def show_edit_course_form(self, obj_id):
        """
        Loads the course editor with a nested schedule management section.
        
        This is a complex form that lists linked 'Schedules' beneath the core 
        course details, allowing for instant deletion of specific time slots.
        """
        with app.app_context():
            # joinedload prevents multiple database hits inside the schedule loop
            courses = Courses.query.options(joinedload(Courses.schedules)).get(obj_id)
            # self.sort_schedule requires a list of course objects
            self.sort_schedule([courses]) 

        frame, footer = self.create_form_frame("Edit Course")
        fields = self.generate_form_fields(frame, [
            ("code", "text", "Code:"),
            ("title", "text", "Title:"),
            ("instructor", "text", "Instructor:"),
            ("units", "text", "Unit/s:")
        ])

        self.populate_form_data(fields, courses)

        # --- DYNAMIC SCHEDULES SECTION ---
        if courses.schedules:
            # DEBUG TIP: grid_size() helps place this section perfectly after the generated inputs
            total_cols, next_row = frame.grid_size()

            sched_wrapper = tk.Frame(frame, bg="white")
            sched_wrapper.grid(row=next_row, column=0, columnspan=total_cols, sticky="ew", pady=(5,5))

            tk.Frame(sched_wrapper, bg="#e5e5e5", height=2).pack(fill="x", padx=20, pady=(0, 5))
            tk.Label(sched_wrapper, text="Assigned Schedules", font=("Arial", 12, "bold"), 
                     bg="white", fg=COLORS['purple']).pack(anchor="w", padx=20)

            for sched in courses.schedules:
                sched_row = tk.Frame(sched_wrapper, bg="white")
                sched_row.pack(fill="x", padx=20, pady=2)

                # Format time to standard 12-hour clock (AM/PM)
                time_str = f"{sched.start_time.strftime('%I:%M %p')} - {sched.end_time.strftime('%I:%M %p')}"
                tk.Label(sched_row, text=f"• {sched.day}: {time_str}", 
                         font=("Arial", 11), bg="white", fg="gray").pack(side="left")

                # The delete button passes a lambda to refresh the current edit page
                tk.Button(sched_row, text="🗑", bg="white", fg="red", bd=0, cursor="hand2", 
                          command=lambda s_id=sched.id: self.delete_record(
                              Schedules, s_id, lambda: self.show_edit_course_form(obj_id))
                         ).pack(side="right")

            tk.Frame(sched_wrapper, bg="#e5e5e5", height=2).pack(fill="x", padx=20, pady=(5, 0))

        # Redirect ID 3: Courses Page
        self.create_form_button(footer, Courses, 3, fields, obj_id=obj_id)
    
    def show_edit_deadline_form(self, obj_id):
        """
        Loads the deadline editor with dynamic routing.
        
        Uses joinedload to pull Course/Category names. Redirects based on 
        whether the deadline is currently archived to maintain UX flow.
        """
        with app.app_context():
            deadlines = Deadlines.query.options(
                joinedload(Deadlines.course), 
                joinedload(Deadlines.category)
            ).get(obj_id)

        frame, footer = self.create_form_frame("Edit Deadline")
        fields = self.generate_form_fields(frame, [
            ("course_id", "combo", "Course:"),
            ("description", "text", "Title/Description:"),
            ("category_id", "combo", "Category:"),
            ("date_given", "date", "Date Given:"),
            ("date_deadline", "date", "Deadline:"),
            ("status", "combo", "Status:"),
            ("note", "textarea", "Note/s:")
        ])

        self.populate_form_data(fields, deadlines)

        # DEBUG TIP: If editing an archive, ensure it returns to Index 6 (Archive)
        target_frame = 4 if not deadlines.is_archived else 6
        self.create_form_button(footer, Deadlines, target_frame, fields, obj_id=obj_id)

    def show_edit_link_form(self, obj_id):
        """Simple editor for external resource links."""
        with app.app_context():
            links = Links.query.get(obj_id)

        frame, footer = self.create_form_frame("Edit Link")
        fields = self.generate_form_fields(frame, [
            ("title", "text", "Title:"),
            ("link", "text", "Link:")
        ])

        self.populate_form_data(fields, links)
        # Redirect ID 5: Links Page
        self.create_form_button(footer, Links, 5, fields, obj_id=obj_id)
    
    def show_edit_profile_form(self, obj_id):
        """
        User Profile Editor with Account Deletion 'Danger Zone'.
        
        Provides basic detail updates and a destructive action button 
        for account removal.
        """
        with app.app_context():
            users = Users.query.get(obj_id)

        frame, footer = self.create_form_frame("Edit Profile")
        fields = self.generate_form_fields(frame, [
            ("name", "text", "Name:"),
            ("email", "text", "Email:")
        ])

        self.populate_form_data(fields, users)
        
        # Redirect ID 0: Dashboard
        self.create_form_button(footer, Users, 0, fields, obj_id=obj_id)
        
        # --- DANGER ZONE SECTION ---
        total_cols, next_row = frame.grid_size()

        # Visual warning box for account deletion
        danger_zone = tk.Frame(frame, bg="#fff5f5", highlightbackground=COLORS['purple'], 
                               highlightthickness=1, padx=15, pady=10)
        danger_zone.grid(row=next_row, column=0, columnspan=total_cols, sticky="ew", pady=5)

        tk.Label(danger_zone, text="Permanently delete your account and all data.", 
                 font=("Arial", 9), bg="#fff5f5", fg=COLORS['purple']).pack(side="left")

        tk.Button(danger_zone, text="Delete", bg=COLORS['purple'], fg="white", 
                  font=("Arial", 9, "bold"), bd=0, padx=10, pady=2, cursor="hand2", 
                  command=self.delete_account).pack(side="right")

    def show_edit_summary_form(self, obj_id):
        """Editor for Class Summaries / Lecture Notes."""
        with app.app_context():
            summaries = ClassSummaries.query.options(joinedload(ClassSummaries.course)).get(obj_id)

        frame, footer = self.create_form_frame("Edit Class Summary")
        fields = self.generate_form_fields(frame, [
            ("course_id", "combo", "Course:"),
            ("scheduled_date", "date", "Scheduled Date:"),
            ("content", "textarea", "Content:"),
            ("note", "textarea", "Note/s:")    
        ])

        self.populate_form_data(fields, summaries)
        # Redirect ID 2: Class Summaries Page
        self.create_form_button(footer, ClassSummaries, 2, fields, obj_id=obj_id)

    def show_item_details(self, Model, obj_id, frame_title, back_command, field_blueprint, edit_command=None, refresh_callback=None):
        """
        A universal, full-screen reader view for detailed record inspection.

        This function acts as a 'Post Viewer'. It extracts data based on a blueprint 
        and renders it in a centered card. It features a specialized parser for links 
        to ensure external resources are always interactable.

        Args:
            field_blueprint (list): Tuples of (Label, AttributeName or Lambda).
        """
        self.prep_new_screen()

        with app.app_context():
            post = Model.query.get(obj_id)
            if not post: return

            # Translate the database model into a generic list of displayable data
            display_data = []
            for label, extractor in field_blueprint:
                value = extractor(post) if callable(extractor) else getattr(post, extractor, "")
                display_data.append((label, value))

        header_cont, cards_frame = self.create_content_frame(COLORS["white"], COLORS['black'], frame_title, 1)
        tk.Button(header_cont, text="← Back", bg=COLORS['gray'], fg="white", 
                  font=("Arial", 10, "bold"), bd=0, padx=15, pady=8, 
                  command=back_command, cursor="hand2").pack(side="right", padx=10)

        my_scroller = ScrollableFrame(cards_frame)
        wrapper = tk.Frame(my_scroller.scrollable_frame, bg=COLORS["white"])
        wrapper.pack(fill="both", expand=True)

        # Card Container
        post_card = tk.Frame(wrapper, bg="white", highlightbackground="#cccccc", 
                             highlightthickness=1, padx=40, pady=30)
        post_card.pack(anchor="n", fill="both", expand=True, padx=20, pady=20)

        for label, val in display_data:
            if not val: continue

            # --- DYNAMIC LINK HANDLING ---
            if label in ["Link:", "Links:"]:
                tk.Label(post_card, text=label, font=("Arial", 9, "bold"), 
                         fg="#888888", bg="white").pack(anchor="w", pady=(15, 0))
                
                for line in str(val).splitlines():
                    line = line.strip()
                    if not line: continue
                    
                    url_start = line.find("http") if "http" in line else line.find("www.")
                    if url_start != -1:
                        title_part = line[:url_start].strip().rstrip(":-| ")
                        url_part = line[url_start:].strip()
                        if url_part.startswith("www."): url_part = "https://" + url_part
                        
                        display_text = f"{title_part}: {url_part}" if title_part else url_part
                        tk.Button(post_card, text=f"🔗 {display_text}", font=("Arial", 11, "bold"), 
                                  bd=0, bg="white", fg=COLORS['purple'], cursor="hand2", 
                                  anchor="w", command=lambda u=url_part: webbrowser.open_new(u)
                                  ).pack(fill="x", pady=(2, 0))
                continue 

            # --- STANDARD ATTRIBUTE RENDERING ---
            tk.Label(post_card, text=label, font=("Arial", 9, "bold"), 
                     fg="#888888", bg="white").pack(anchor="w", pady=(15, 0))

            # Using tk.Text for dynamic height text boxes (allows for copying)
            val_text = tk.Text(post_card, font=("Arial", 13), fg="black", bg="white", 
                               bd=0, wrap="word", height=0, width=70)
            val_text.insert("1.0", str(val))
            val_text.configure(state="disabled") # Prevent editing in reader view
            val_text.pack(anchor="w", pady=(2, 0))
            
            # Auto-calculate necessary height
            num_lines = int(val_text.index("end-1c").split(".")[0])
            val_text.configure(height=num_lines)

        # Administrative Actions (Pencil / Trash)
        if self.is_admin() and edit_command and refresh_callback:
            tk.Frame(post_card, bg="#e5e5e5", height=2).pack(fill="x", pady=(30, 15))
            btn_row = tk.Frame(post_card, bg="white")
            btn_row.pack(side="bottom", anchor="e")

            tk.Button(btn_row, text="✎ Edit", bg="#e5e5e5", fg="black", font=("Arial", 10, "bold"), 
                      bd=0, padx=15, pady=6, cursor="hand2", 
                      command=lambda: edit_command(obj_id)).pack(side="left", padx=5)
            tk.Button(btn_row, text="🗑 Delete", bg=COLORS['purple'], fg="white", 
                      font=("Arial", 10, "bold"), bd=0, padx=15, pady=6, cursor="hand2", 
                      command=lambda: self.delete_record(Model, obj_id, refresh_callback)).pack(side="left", padx=5)
    
    def view_announcement(self, obj_id):
        """
        Detailed reader view for a single announcement.
        
        Defines the data 'blueprint' (how to extract and label each field) 
        and delegates rendering to the universal 'show_item_details' method.
        """
        # The Blueprint: (Label, Extraction Logic)
        blueprint = [
            ("Title:", "title"),
            ("Posted By:", lambda p: p.poster.name if p.poster else "Unknown Admin"),
            ("Date Posted:", lambda p: p.date_added.strftime('%A - %B %d, %Y')),
            ("Content:", "content"),
            ("Link:", "link")
        ]
        
        self.show_item_details(
            Model=Announcements,
            obj_id=obj_id,
            frame_title="View Announcement",
            back_command=self.show_announcements,
            field_blueprint=blueprint,
            edit_command=self.show_edit_announcement_form,
            refresh_callback=self.show_announcements # Refreshes announcement list on delete
        )

    def view_summary(self, obj_id):
        """
        Detailed reader view for a single class summary.
        
        Formats course codes and scheduled dates into a student-friendly 
        layout before passing to the universal detail viewer.
        """
        blueprint = [
            ("Course:", lambda p: f"{p.course.code} | {p.course.title}" if p.course else "No Course"),
            ("Scheduled Date:", lambda p: p.scheduled_date.strftime('%A - %B %d, %Y')),
            ("Summary Content:", "content"),
            ("Additional Notes:", "note")
        ]
        
        self.show_item_details(
            Model=ClassSummaries,
            obj_id=obj_id,
            frame_title="View Class Summary",
            back_command=self.show_summaries,
            field_blueprint=blueprint,
            edit_command=self.show_edit_summary_form,
            refresh_callback=self.show_summaries # Refreshes summary list on delete
        )

    # ----- Card Component Builders -----
    # The mathematical and visual templates for individual data items.

    def bind_auto_wrap(self, card, *labels, padding=40):
        """
        Implements dynamic text wrapping by listening to widget resize events.

        In a flexible grid layout, column widths change as the user resizes the 
        main window. This function binds a callback to the <Configure> event 
        of a parent widget to ensure that any associated text labels wrap 
        properly rather than clipping or forcing the window to expand.

        Args:
            card (tk.Widget): The parent container whose size determines the wrap limit.
            *labels (tk.Label): A variable number of Label widgets to be updated.
            padding (int): The horizontal space (in pixels) to subtract from the 
                card width to account for internal margins/padding.
        """
        def on_card_resize(event):
            """Recalculates wraplength based on the new actual width of the card."""
            # Calculate the available horizontal space for text
            new_wrap = event.width - padding
            
            # Defensive check to prevent setting a negative or zero wraplength
            if new_wrap > 0:
                for lbl in labels:
                    # Update the Tkinter wrap property dynamically
                    lbl.configure(wraplength=new_wrap)

        # Bind the '<Configure>' event (triggered on resize/movement) to our logic
        card.bind("<Configure>", on_card_resize)

    def build_announcement_card(self, grid_parent, row, column, announcement):
        """
        Constructs an interactable announcement card with an embedded link parser.

        This method handles complex string parsing to identify URLs within 
        the 'link' text field, converting them into clean, clickable buttons 
        that display the website domain (e.g., 'Google Classroom (google.com)').
        """
        card = tk.Frame(grid_parent, bg="white", highlightbackground="#d9d9d9", 
                        highlightthickness=1, padx=20, pady=20)
        card.grid(row=row, column=column, padx=10, pady=10, sticky="nsew")

        # Title: Purple and clickable
        title_text = f"{announcement.title}" if announcement.title else "No Title"
        title_label = tk.Label(card, text=title_text, font=("Arial", 16, "bold"), 
                               bg="white", cursor="hand2", fg=COLORS['purple'], 
                               wraplength=250, justify="left", anchor="w")
        title_label.pack(fill="x")
        title_label.bind("<Button-1>", lambda e, id=announcement.id: self.view_announcement(id))

        # Metadata: Poster details
        poster_name = announcement.poster.name if announcement.poster else "Unknown Poster"
        poster_label = tk.Label(card, text=f"Posted by: {poster_name}", font=("Arial", 10), 
                                bg="white", wraplength=250, justify="left")
        poster_label.pack(anchor="w")

        # Content Snippet
        tk.Label(card, text="Content:", font=("Arial", 10), bg="white", 
                 wraplength=250, justify="left").pack(anchor="w", pady=(5, 0))
        content_label = tk.Label(card, text=announcement.content, font=("Arial", 12), 
                                 bg="white", wraplength=250, justify="left")
        content_label.pack(anchor="w", pady=(2, 0))

        # --- DYNAMIC MULTI-LINK PARSER ---
        if announcement.link and announcement.link.strip():
            # 1. PRE-CHECK: Do any lines actually contain a link?
            lines = announcement.link.splitlines()
            has_any_link = any("http" in line or "www." in line for line in lines)
            
            if has_any_link:
                tk.Label(card, text="Attached Links:", font=("Arial", 10, "bold"), 
                        bg="white", fg="gray").pack(anchor="w", pady=(10, 0))
                
                for line in lines:
                    line = line.strip()
                    if not line: continue
                    
                    url_start = line.find("http") if "http" in line else line.find("www.")
                    
                    # 2. RENDER THE BUTTON ONLY IF URL SIGNATURE IS FOUND
                    if url_start != -1:
                        title_part = line[:url_start].strip().rstrip(":-| ")
                        raw_url = line[url_start:].strip()
                        
                        valid_url = self.validate_url(raw_url)
                        
                        if valid_url:
                            domain = urlparse(valid_url).netloc.replace("www.", "")
                            display_text = f"{title_part} ({domain})" if title_part else valid_url
                            btn_color = COLORS['purple']
                            btn_command = lambda u=valid_url: webbrowser.open_new(u)
                            icon = "🔗"
                        else:
                            display_text = f"{title_part} (Invalid Link)" if title_part else f"Invalid: {raw_url}"
                            btn_color = COLORS['red']
                            btn_command = lambda r=raw_url: messagebox.showerror("Link Error", f"'{r}' is not a valid URL.")
                            icon = "⚠️"

                        tk.Button(
                            card, text=f"{icon} {display_text}", font=("Arial", 11, "bold"), 
                            bd=0, bg="white", fg=btn_color, cursor="hand2", anchor="w", 
                            command=btn_command
                        ).pack(fill="x", pady=(2, 0))

        # Admin controls and dynamic wrapping
        self.create_card_button(card, "View Post", Announcements, announcement.id, 
                                self.show_edit_announcement_form, 
                                refresh_callback=self.show_announcements, 
                                text_button=self.view_announcement)
        self.bind_auto_wrap(card, title_label, poster_label, content_label)
    
    def build_auth_base(self, subtitle_text):
        """Standardizes the centered logo and subheader for login/signup/OTP screens."""
        self.prep_new_screen()
        frame = tk.Frame(self.container)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(frame, text="BlockHub", font=("Arial", 24, "bold")).pack(pady=5)
        tk.Label(frame, text="Note: Only g.batstate-u accounts are accepted.", 
                 fg=COLORS["gray"], font=("Arial", 10, "italic")).pack(pady=(0, 15))
        tk.Label(frame, text=subtitle_text, fg=COLORS["gray"], 
                 font=("Arial", 12)).pack(pady=(0, 5), anchor="w")
        return frame

    def build_course_card(self, grid_parent, row, column, course):
        """
        Constructs a wide-format course card.
        
        This layout uses a three-frame horizontal structure:
        - Left: Metadata (Code, Title, Instructor)
        - Middle: Chronological schedule list
        - Right: Units and Admin buttons
        """
        card = tk.Frame(grid_parent, bg="white", highlightbackground="#d9d9d9", highlightthickness=1)
        card.grid(row=row, column=column, padx=10, pady=8, sticky="ew")

        # Define proportional grid weights to prevent columns from overlapping
        card.columnconfigure(0, weight=3) # Metadata
        card.columnconfigure(1, weight=4) # Schedules
        card.columnconfigure(2, weight=0) # Controls

        # 1. RIGHT: Controls (Fixed Width)
        right_frame = tk.Frame(card, bg="white", padx=15, pady=15)
        right_frame.grid(row=0, column=2, sticky="ne") # Anchor to top-right
        
        btn_frame = tk.Frame(right_frame, bg="white")
        btn_frame.pack(anchor="e", pady=(0, 5))

        self.create_card_button(btn_frame, "Add Schedule", Courses, course.id, 
                                self.show_edit_course_form, 
                                refresh_callback=self.show_courses, 
                                text_button=self.show_add_schedule_form)

        tk.Label(right_frame, text=f"Units: {course.units if hasattr(course, 'units') else '3'}", 
                 font=("Arial", 10, "bold"), fg=COLORS['purple'], bg="white").pack(anchor="e")

        # 2. LEFT: Primary Info (Weight 3)
        left_frame = tk.Frame(card, bg="white", padx=15, pady=15)
        left_frame.grid(row=0, column=0, sticky="nsew")

        tk.Label(left_frame, text=f"Course Code: {course.code}", font=("Arial", 9), 
                 fg="#999999", bg="white", justify="left").pack(anchor="w")

        # CRITICAL FIX: Add justify="left" and an initial wraplength
        title_label = tk.Label(left_frame, text=course.title, font=("Arial", 14, "bold"), 
                               fg="black", bg="white", justify="left", wraplength=300)
        title_label.pack(anchor="w", pady=(2, 2))

        instructor = course.instructor if course.instructor else "No Instructor Assigned"
        instructor_label = tk.Label(left_frame, text=f"Instructor: {instructor}", font=("Arial", 9), 
                                    fg="#999999", bg="white", justify="left", wraplength=300)
        instructor_label.pack(anchor="w")

        # 3. MIDDLE: Schedules (Weight 4)
        middle_frame = tk.Frame(card, bg="white", padx=15, pady=15)
        middle_frame.grid(row=0, column=1, sticky="nsew")

        tk.Label(middle_frame, text="Schedules:", font=("Arial", 9, "bold"), 
                 fg="#666666", bg="white").pack(anchor="w")
        
        if hasattr(course, 'schedules') and course.schedules:
            for sched in course.schedules:
                time_fmt = f"{sched.start_time.strftime('%I:%M %p')} - {sched.end_time.strftime('%I:%M %p')}"
                tk.Label(middle_frame, text=f"• {sched.day}, {time_fmt}", 
                         font=("Arial", 9), fg="#4d4d4d", bg="white").pack(anchor="w", padx=(10, 0))
        else:
            tk.Label(middle_frame, text="• No schedule set", font=("Arial", 9, "italic"), 
                     fg="#999999", bg="white").pack(anchor="w", padx=(10, 0))

        # Dynamic wrap binding ensures the text breaks before hitting the middle column
        self.bind_auto_wrap(left_frame, title_label, instructor_label, padding=30)

    def build_dash_announcements(self, parent, announcements, row, col):
        """
        Renders a double-width scrolling announcement feed.
        
        Cleans and truncates announcement content to create a uniform 
        preview snippet, redirecting to the full view upon selection.
        """
        frame = tk.Frame(parent, bg=COLORS["purple"], padx=15, pady=15)
        # Spans 2 columns for a 'wide-screen' feed effect
        frame.grid(row=row, column=col, columnspan=2, sticky="nsew", padx=5, pady=5)

        tk.Label(frame, text="Announcements", font=("Arial", 16, "bold"), 
                 bg=COLORS["purple"], fg="white").pack(anchor="w")

        footer = tk.Frame(frame, bg=COLORS["purple"])
        footer.pack(side="bottom", fill="x", pady=(10, 0))

        tk.Button(footer, text="View All ➔", font=("Arial", 10, "bold"), bg=COLORS["purple"], 
                  fg="white", bd=0, cursor="hand2", command=self.show_announcements).pack(side="right")

        if not announcements:
            tk.Label(frame, text="No announcements posted", bg=COLORS['purple'], 
                     fg="white").pack(pady=10, anchor="w")
            return

        # Scroller prevents the dashboard from growing infinitely tall
        my_scroller = ScrollableFrame(frame, bg_color=COLORS["purple"], 
                                      scrollbar_color=COLORS["purple"], 
                                      trough_color=COLORS['purple'])

        for a in announcements:
            card = tk.Frame(my_scroller.scrollable_frame, bg="white")
            card.pack(fill="x", padx=(0, 15), pady=5)

            tk.Button(card, text=a.title, bg="white", anchor="w", font=("Arial", 14, "bold"), 
                      bd=0, fg=COLORS['purple'], cursor="hand2", 
                      command=lambda id=a.id: self.view_announcement(id)).pack(fill="x", pady=5, padx=5)
            
            # Sanitization Logic: Removes all internal newlines for a clean preview
            raw_content = a.content if a.content else ""
            clean_content = " ".join(raw_content.split())
            display_text = (clean_content[:150] + "...") if len(clean_content) > 150 else clean_content

            tk.Label(card, text=f"Content: {display_text}", bg="white", fg="gray", 
                     anchor="w", font=("Arial", 10), justify="left").pack(fill="x", pady=(0, 5), padx=5)

    def build_dash_deadlines(self, parent, deadlines, total, row, col):
        """
        Renders a condensed list of the most urgent upcoming deadlines.
        
        Includes a summary count and utilizes the 'urgency bar' helper 
        to maintain visual consistency with the main Deadline view.
        """
        frame = tk.Frame(parent, bg="white", padx=15, pady=15)
        frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        
        header = tk.Frame(frame, bg="white")
        header.pack(fill="x", padx=15, pady=10)
        
        tk.Label(header, text="Deadlines", font=("Arial", 20, "bold"), bg="white").pack(side="left")
        
        # Navigation link to the full Deadlines module
        tk.Button(header, text="View All ➔", font=("Arial", 10, "bold"), bg="white", 
                  fg="black", bd=0, cursor="hand2", command=self.show_deadlines).pack(side="right", padx=(5, 0))

        if total:
            tk.Label(header, text=f"Total Deadlines: {total}", bg="white", 
                     fg=COLORS['gray'], font=("Arial", 10)).pack(side="right")

        if not deadlines:
            tk.Label(frame, text="No upcoming deadlines ✨", bg="white", fg="gray").pack(padx=15, anchor="w")
            return

        for d in deadlines:
            card = tk.Frame(frame, bg="white", highlightbackground="#eeeeee", highlightthickness=1)
            card.pack(fill="x", pady=2, padx=15)
            
            txt_area = tk.Frame(card, bg="white", padx=10, pady=5)
            txt_area.pack(side="left", fill="both", expand=True)
            
            course_code = d.course.code if d.course else 'No Course'
            cat_title = d.category.title if d.category else 'Misc'
            
            course_label = tk.Label(txt_area, text=f"{course_code} | {cat_title}", font=("Arial", 8), 
                     fg="gray", bg="white")
            course_label.pack(anchor="w")
            
            desc_label = tk.Label(txt_area, text=d.description, font=("Arial", 10, "bold"), bg="white", wraplength=320, justify="left")
            desc_label.pack(anchor="w")
            
            date_str = d.date_deadline.strftime('%A - %B %d, %Y')
            date_label = tk.Label(txt_area, text=f"Submission: {date_str}", font=("Arial", 9), 
                 fg="#999999", bg="white", justify="left", wraplength=200)
            date_label.pack(anchor="w")
            
            # Reuses the standard urgency bar for cross-module visual language
            self.draw_deadline_urgency_bar(card, d.date_deadline)
            self.bind_auto_wrap(txt_area, course_label, desc_label, date_label)

    def build_dash_links(self, parent, links, row, col):
        """Renders a quick-access 'Bookmarks' tile on the Dashboard."""
        frame = tk.Frame(parent, bg=COLORS["purple"], padx=15, pady=15)
        frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        
        tk.Label(frame, text="Links", font=("Arial", 16, "bold"), 
                 bg=COLORS["purple"], fg="white").pack(anchor="w", pady=(0, 5))
        
        valid_links_count = 0  # Track how many links actually get drawn
        
        for l in links:
            # Check the link against your validation logic
            valid_url = self.validate_url(l.link)
            
            # Only draw the button if the URL passes the test
            if valid_url:
                btn = tk.Button(
                    frame, text=l.title, bg="white", fg="black", font=("Arial", 9, "bold"), 
                    anchor="w", padx=10, pady=5, justify="left", 
                    command=lambda url=valid_url: webbrowser.open(url)
                )
                btn.pack(fill="x", pady=2)
                valid_links_count += 1

        # If the database was empty, OR if all links failed validation
        if valid_links_count == 0:
            tk.Label(frame, text="No valid links to display", bg=COLORS['purple'], fg="white").pack(anchor="w")
    
    def build_dash_profile(self, parent, row, col):
        """
        Renders the personalized welcome widget on the Dashboard.
        
        Dynamically adjusts the greeting based on 'current_user' and displays 
        context-aware buttons (e.g., 'New Entry' for officers).
        """
        frame = tk.Frame(parent, bg="white", padx=20, pady=20)
        frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

        container = tk.Frame(frame, bg=COLORS["white"])
        container.pack(expand=True, fill="x", padx=50)
        
        if self.current_user:
            # Logic: Greet the user by their first name only
            parts = self.current_user.name.split()
            welcome_name = ' '.join(parts[:1])
        else:
            welcome_name = "Guest"
        
        tk.Label(container, text="Welcome,", bg="white", font=("Arial", 16)).pack(anchor="w")
        tk.Label(container, text=f"{welcome_name} !", bg="white", 
                 fg=COLORS["purple"], font=("Arial", 30, "bold")).pack(anchor="w")
        
        # Stylistic Horizontal Rule
        tk.Frame(container, bg="black", height=2).pack(fill="x", pady=10)
        
        btn_container = tk.Frame(container, bg=COLORS["white"])
        btn_container.pack(fill="x", pady=5)

        def create_user_button(text, command=None):
            tk.Button(btn_container, text=text, bg=COLORS['purple'], fg=COLORS['white'], 
                      font=("Arial", 12), cursor="hand2", command=command).pack(side="left", padx=(0, 5))

        if self.current_user:
            # Officer-only administrative shortcuts
            if self.current_user.role == 'officer':
                create_user_button("View Users", self.show_users)
                create_user_button("New Entry", self.show_new_entry_menu)
            
            create_user_button("Edit Profile", lambda: self.show_edit_profile_form(self.current_user.id))
        else:
            # Guest Call-to-Action
            tk.Label(btn_container, text="Get Started Today!", bg=COLORS['white'], 
                     font=("Arial", 12)).pack(side="left")
            tk.Button(btn_container, text="Login", bd=0, bg="white", fg=COLORS['purple'], 
                      font=("Arial", 12, "bold"), command=self.login).pack(side="left", padx=(0, 10))

    def build_dash_summaries(self, parent, summaries, target, row, col):
        """Displays a summary of lecture notes for the most recent academic date."""
        frame = tk.Frame(parent, bg="white", padx=15, pady=15)
        frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

        tk.Label(frame, text="Class Summaries", font=("Arial", 16, "bold"), bg="white").pack(anchor="w")
        
        footer = tk.Frame(frame, bg="white")
        footer.pack(side="bottom", fill="x")
        
        tk.Button(footer, text="View All ➔", font=("Arial", 10, "bold"), bg="white", 
                  fg="black", bd=0, cursor="hand2", command=self.show_summaries).pack(side="right")

        if not target:
            tk.Label(frame, text="No summaries yet", bg="white", fg="gray").pack(pady=5, anchor="w")
            return

        my_scroller = ScrollableFrame(frame)
        
        # TIME NORMALIZATION: Get the current UTC date to use as a baseline
        now_utc = datetime.now(timezone.utc)
        today_date = now_utc.date()

        # TIMEZONE SAFETY: Ensure target date is 'aware' to prevent comparison crashes
        if target.scheduled_date.tzinfo is None:
            aware_target = target.scheduled_date.replace(tzinfo=timezone.utc)
        else:
            aware_target = target.scheduled_date
        
        # DATE EXTRACTION: Strip hours/minutes to compare calendar days only
        target_date_only = aware_target.date()

        # FORMATTING: Convert the date into a readable string (e.g., Monday - Apr 20)
        date_str = aware_target.strftime('%A - %b %d, %Y')

        # LABEL LOGIC: Assign a status tag based on proximity to current day
        if target_date_only == today_date:
            date_label = f"{date_str} (Today)"
        elif target_date_only < today_date:
            date_label = f"{date_str} (Past Date)"
        else:
            date_label = f"{date_str} (Upcoming)"

        tk.Label(my_scroller.scrollable_frame, text=date_label, bg="white", fg="gray").pack(anchor="w", pady=(0, 10))
    
        for s in summaries:
            card = tk.Frame(my_scroller.scrollable_frame, bg="#f9f9f9", padx=10, pady=5)
            card.pack(fill="x", pady=2)
            
            course_code = s.course.code if s.course else "Unknown Course"
            tk.Label(card, text=course_code, font=("Arial", 10, "bold"), bg="#f9f9f9").pack(anchor="w")
            
            # Sanitization Logic: Removes all internal newlines for a clean preview
            raw_content = s.content if s.content else "No content provided."
            lines = [line.strip() for line in raw_content.splitlines()]
            clean_content = "\n".join(lines)

            content_label = tk.Label(card, text=clean_content, font=("Arial", 8), bg="#f9f9f9", justify="left", wraplength=300, anchor="w")
            content_label.pack(anchor="w", fill="x", pady=(2, 5))

            if s.note:
                raw_content = s.note if s.content else "No content provided."
                lines = [line.strip() for line in raw_content.splitlines()]
                clean_content = "\n".join(lines)

                tk.Label(card, text="Note/s:", font=("Arial", 8, "bold"), bg="#f9f9f9", justify="left", wraplength=300, anchor="w").pack(anchor="w", fill="x", pady=(2, 0))
                note_label = tk.Label(card, text=clean_content, font=("Arial", 8), bg="#f9f9f9", justify="left", wraplength=300, anchor="w")
                note_label.pack(anchor="w", fill="x", pady=(2, 5))

            # BIND AUTO-WRAP: Ensures the text adjusts if the window size changes
            self.bind_auto_wrap(card, content_label)
            self.bind_auto_wrap(card, note_label)

    def build_deadline_card(self, grid_parent, row, column, deadline):
        """Constructs a deadline card with proportionally distributed columns."""
        card = tk.Frame(grid_parent, bg="white", highlightbackground="#d9d9d9", highlightthickness=1)
        card.grid(row=row, column=column, padx=10, pady=10, sticky="nsew")

        # 1. VISUAL INDICATOR (Pack this first on the right so it hugs the edge)
        self.draw_deadline_urgency_bar(card, deadline.date_deadline)

        # 2. INNER CONTENT CONTAINER (Switches from Pack to Grid)
        content_container = tk.Frame(card, bg="white")
        content_container.pack(side="left", fill="both", expand=True)

        # Define the exact proportions for the columns
        content_container.columnconfigure(0, weight=4) # Left: Gets 4 parts of the space (Description)
        content_container.columnconfigure(1, weight=3) # Middle: Gets 3 parts of the space (Notes)
        content_container.columnconfigure(2, weight=0) # Right: Gets exactly the space it needs (Buttons)

        # --- LEFT FRAME (Description) ---
        left_frame = tk.Frame(content_container, bg="white", padx=15, pady=15)
        left_frame.grid(row=0, column=0, sticky="nsew")

        course_info = f"{deadline.course.code} | {deadline.category.title}" if deadline.course else "No Subject"
        tk.Label(left_frame, text=course_info, font=("Arial", 9), 
                 fg="#999999", bg="white", justify="left").pack(anchor="w")

        title_label = tk.Label(left_frame, text=deadline.description, font=("Arial", 14, "bold"), 
                               fg="black", bg="white", justify="left")
        title_label.pack(anchor="w", pady=(2, 2))

        date_str = deadline.date_deadline.strftime('%A - %B %d, %Y')
        tk.Label(left_frame, text=f"Submission: {date_str}", font=("Arial", 9), 
                 fg="#999999", bg="white", justify="left").pack(anchor="w")

        # --- MIDDLE FRAME (Notes) ---
        middle_frame = tk.Frame(content_container, bg="white", padx=15, pady=15)
        middle_frame.grid(row=0, column=1, sticky="nsew")

        if deadline.note:
            tk.Label(middle_frame, text="Note/s:", font=("Arial", 9, "bold"), 
                     fg="#666666", bg="white", justify="left").pack(anchor="w")
            note_label = tk.Label(middle_frame, text=deadline.note, font=("Arial", 9), 
                                  fg="#666666", bg="white", justify="left")
            note_label.pack(anchor="w")
            # Auto-wrap the notes just in case someone types a huge paragraph
            self.bind_auto_wrap(content_container, note_label)

        # --- RIGHT FRAME (Controls) ---
        right_frame = tk.Frame(content_container, bg="white", padx=15, pady=15)
        right_frame.grid(row=0, column=2, sticky="nsew")

        btn_frame = tk.Frame(right_frame, bg="white")
        btn_frame.pack(anchor="e", pady=(0, 5))

        refresh_cmd = self.show_deadlines if not deadline.is_archived else self.show_archive_deadlines
        self.create_card_button(btn_frame, None, Deadlines, deadline.id, 
                                self.show_edit_deadline_form, refresh_callback=refresh_cmd)

        tk.Label(right_frame, text=f"Status: {deadline.status}", font=("Arial", 10), 
                 fg="#666666", bg="white").pack(anchor="e")

        # Bind the title wrap to the new container
        self.bind_auto_wrap(content_container, title_label)

    def build_link_card(self, grid_parent, row, column, link):
        """ 
        Constructs a Link UI card. 
        Validates the URL format and displays an error state if the link is malformed.
        """
        card = tk.Frame(grid_parent, bg="white", highlightbackground="#d9d9d9", 
                        highlightthickness=1, padx=15, pady=10)
        card.grid(row=row, column=column, padx=10, pady=8, sticky="ew")

        # 1. VALIDATION LOGIC
        valid_url = self.validate_url(link.link)
        
        # 2. DEFINE THE ACTION
        if valid_url:
            display_color = "black"
            link_command = lambda: webbrowser.open_new(valid_url)
            icon = "🔗"
        else:
            # Error State: Use red text and show a warning instead of opening a link
            display_color = COLORS['red']
            link_command = lambda: messagebox.showerror("Link Error", 
                                                        f"The URL '{link.link}' is malformed.\n"
                                                        "Please edit this entry and provide a valid address.")
            icon = "⚠️ INVALID:"

        # 3. RIGHT SIDE: Action Buttons
        btn_frame = tk.Frame(card, bg="white")
        btn_frame.pack(side="right", fill="y") 
        self.create_card_button(btn_frame, None, Links, link.id, 
                                self.show_edit_link_form, refresh_callback=self.show_links)

        # 4. LEFT SIDE: Title Button
        title_btn = tk.Button(
            card, 
            text=f"{icon} {link.title}", 
            font=("Arial", 14, "bold"), 
            bd=0, 
            fg=display_color, 
            bg="white", 
            activebackground="white", 
            cursor="hand2",
            command=link_command, 
            anchor="w"
        )
        
        title_btn.pack(side="left", fill="both", expand=True)

    def build_summary_card(self, grid_parent, row, col, summary):
        """Constructs a lecture summary card with a 'Read More' expander."""
        card = tk.Frame(grid_parent, bg="white", highlightbackground="#d9d9d9", 
                        highlightthickness=1, padx=20, pady=20)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        course_text = f"{summary.course.code} | {summary.course.title}" if summary.course else "No Subject"
        title_label = tk.Label(card, text=course_text, font=("Arial", 12, "bold"), 
                               bg="white", cursor="hand2", fg=COLORS['purple'], 
                               wraplength=250, justify="left")
        title_label.pack(anchor="w")
        title_label.bind("<Button-1>", lambda e, id=summary.id: self.view_summary(id))

        if summary.content:
            content_label = tk.Label(card, text=summary.content, font=("Arial", 11), 
                                     bg="white", wraplength=250, justify="left")
            content_label.pack(anchor="w", pady=(5, 15))
            self.bind_auto_wrap(card, content_label)

        if summary.note:
            tk.Label(card, text="Note/s:", font=("Arial", 10, "bold"), bg="white").pack(anchor="w")
            note_label = tk.Label(card, text=summary.note, font=("Arial", 10), 
                                  bg="white", fg="#555555", wraplength=250, justify="left")
            note_label.pack(anchor="w", pady=(0, 20))
            self.bind_auto_wrap(card, note_label)

        self.create_card_button(card, "Read More", ClassSummaries, summary.id, 
                                self.show_edit_summary_form, refresh_callback=self.show_summaries, 
                                text_button=self.view_summary)
        self.bind_auto_wrap(card, title_label)

    def build_user_card(self, grid_parent, row, column, user):
        """Constructs a personnel card for the admin user-management view."""
        card = tk.Frame(grid_parent, bg="white", highlightbackground="#d9d9d9", 
                        highlightthickness=1, padx=20, pady=20)
        card.grid(row=row, column=column, padx=10, pady=10, sticky="nsew")

        title_label = tk.Label(card, text=user.name, font=("Arial", 16, "bold"), 
                               bg="white", fg=COLORS['purple'], wraplength=250, justify="left")
        title_label.pack(anchor="w")

        email_label = tk.Label(card, text=f"Email: {user.email}", font=("Arial", 10), 
                               bg="white", wraplength=250, justify="left")
        email_label.pack(anchor="w")

        role_label = tk.Label(card, text=f"Role: {user.role}", font=("Arial", 10), 
                              bg="white", wraplength=250, justify="left")
        role_label.pack(anchor="w")

        self.create_card_button(card, None, Users, user.id, self.show_edit_profile_form, self.show_users)
        self.bind_auto_wrap(card, title_label, email_label)

# --- APPLICATION ENTRY POINT ---
if __name__ == "__main__":
    """
    Bootstrap script for the BlockHub Desktop Application.
    Initializes the MainGUI and starts the Tkinter event loop.
    """
    app_gui = MainGUI()
    # DEBUG TIP: If the app crashes on launch, check the database path in app.py
    app_gui.mainloop()