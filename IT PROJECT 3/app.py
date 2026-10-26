
from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, send_file, flash
)
import sqlite3
import random
import io
import secrets

from werkzeug.security import generate_password_hash, check_password_hash

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib.units import mm


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)
app.secret_key = "angel-project-secret-key"
DATABASE = "angel.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# =========================================================
# CREATE / UPDATE DATABASE
# =========================================================

def create_database():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS luggage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT UNIQUE NOT NULL,
            passenger TEXT NOT NULL,
            flight TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            weight TEXT NOT NULL,
            status TEXT NOT NULL,
            location TEXT NOT NULL,
            journey_status TEXT,
            alert_status TEXT,
            registered_at TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            employee_name TEXT,
            action TEXT NOT NULL,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create customer user accounts
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active'
        )
    """)

    # Live-agent conversations
    connection.execute("""
        CREATE TABLE IF NOT EXISTS support_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT UNIQUE NOT NULL,
            tracking_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Waiting',
            assigned_employee_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_employee_id) REFERENCES employees(id)
        )
    """)

    # Messages exchanged between passengers and employees
    connection.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            sender_employee_id INTEGER,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id)
                REFERENCES support_conversations(id),
            FOREIGN KEY (sender_employee_id)
                REFERENCES employees(id)
        )
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_conversations_status
        ON support_conversations(status, updated_at)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_messages_conversation
        ON support_messages(conversation_id, id)
    """)

    # Check existing luggage columns
    luggage_columns = connection.execute(
        "PRAGMA table_info(luggage)"
    ).fetchall()

    existing_columns = [
        column["name"] for column in luggage_columns
    ]

    if "journey_status" not in existing_columns:
        connection.execute(
            "ALTER TABLE luggage ADD COLUMN journey_status TEXT"
        )

    if "alert_status" not in existing_columns:
        connection.execute(
            "ALTER TABLE luggage ADD COLUMN alert_status TEXT"
        )

    if "registered_at" not in existing_columns:
        connection.execute(
            "ALTER TABLE luggage ADD COLUMN registered_at TEXT"
        )

    if "user_id" not in existing_columns:
        connection.execute(
            "ALTER TABLE luggage ADD COLUMN user_id INTEGER"
        )


    # Migrate existing luggage
    connection.execute("""
        UPDATE luggage
        SET journey_status = status
        WHERE journey_status IS NULL
        AND status NOT IN ('Delayed', 'Lost')
    """)

    connection.execute("""
        UPDATE luggage
        SET journey_status = 'Checked In',
            alert_status = status
        WHERE status IN ('Delayed', 'Lost')
        AND journey_status IS NULL
    """)

    connection.execute("""
        UPDATE luggage
        SET registered_at = CURRENT_TIMESTAMP
        WHERE registered_at IS NULL
    """)

    # Test luggage
    test_luggage = [
        (
            "ANGEL-1001", "Reuel", "SA123", "Durban",
            "Johannesburg", "18.4 kg", "Checked In",
            "King Shaka International Airport"
        ),
        (
            "ANGEL-1002", "Leshiv Hansraj", "FA456", "Durban",
            "Cape Town", "21.7 kg", "Loaded onto Aircraft",
            "King Shaka International Airport"
        ),
        (
            "ANGEL-1003", "Akheel", "FA789", "Johannesburg",
            "Durban", "16.2 kg", "In Transit",
            "Johannesburg OR Tambo International Airport"
        )
    ]

    for luggage in test_luggage:
        connection.execute("""
            INSERT OR IGNORE INTO luggage (
                tracking_id, passenger, flight, origin,
                destination, weight, status, location,
                journey_status, alert_status, registered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            luggage[0], luggage[1], luggage[2], luggage[3],
            luggage[4], luggage[5], luggage[6], luggage[7],
            luggage[6], None
        ))

    # Create Cameron supervisor if missing
    supervisor = connection.execute("""
        SELECT id FROM employees WHERE username = ?
    """, ("cameron.samivelu",)).fetchone()

    if supervisor is None:
        connection.execute("""
            INSERT INTO employees
                (full_name, username, password_hash, role, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Cameron Samivelu",
            "cameron.samivelu",
            generate_password_hash("Angel123"),
            "Supervisor",
            "Active"
        ))

    # Create Gareth employee if missing
    existing_employee = connection.execute("""
        SELECT id FROM employees WHERE username = ?
    """, ("gareth.singh",)).fetchone()

    if existing_employee is None:
        connection.execute("""
            INSERT INTO employees
                (full_name, username, password_hash, role, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "Gareth Singh",
            "gareth.singh",
            generate_password_hash("Angel123"),
            "Employee",
            "Active"
        ))

    connection.commit()
    connection.close()


# =========================================================
# ACTIVITY LOGGER
# =========================================================

def log_activity(action, details=""):
    if "employee_id" not in session:
        return

    connection = get_db()
    connection.execute("""
        INSERT INTO activity_log
            (employee_id, employee_name, action, details)
        VALUES (?, ?, ?, ?)
    """, (
        session.get("employee_id"),
        session.get("employee_name"),
        action,
        details
    ))
    connection.commit()
    connection.close()


# =========================================================
# LIVE-AGENT HELPERS
# =========================================================

def employee_is_logged_in():
    if "employee_id" not in session:
        return False

    connection = get_db()
    employee = connection.execute("""
        SELECT id, status, role, full_name
        FROM employees
        WHERE id = ?
    """, (session["employee_id"],)).fetchone()
    connection.close()

    return (
        employee is not None
        and employee["status"] == "Active"
        and employee["role"] == session.get("employee_role")
    )


def passenger_conversation(connection, reference):
    """Only allow access to the conversation held in this browser session."""
    conversation_id = session.get("support_conversation_id")
    tracking_id = session.get("support_tracking_id")

    if not conversation_id or not tracking_id or not reference:
        return None

    return connection.execute("""
        SELECT *
        FROM support_conversations
        WHERE id = ?
          AND reference = ?
          AND tracking_id = ?
    """, (
        conversation_id,
        reference,
        tracking_id
    )).fetchone()


def serialize_messages(connection, conversation_id):
    rows = connection.execute("""
        SELECT id, sender_type, sender_employee_id, message, created_at
        FROM support_messages
        WHERE conversation_id = ?
        ORDER BY id ASC
    """, (conversation_id,)).fetchall()

    return [
        {
            "id": row["id"],
            "sender_type": row["sender_type"],
            "sender_employee_id": row["sender_employee_id"],
            "message": row["message"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]


def employee_can_access_conversation(conversation):
    if not employee_is_logged_in():
        return False

    assigned_id = conversation["assigned_employee_id"]
    current_id = session["employee_id"]
    role = session.get("employee_role")

    return (
        assigned_id is None
        or assigned_id == current_id
        or role in ("Supervisor", "Admin")
    )


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# ABOUT US
# =========================================================

@app.route("/about-us")
def about_us():
    return render_template(
        "information_page.html",
        page_title="About ANGEL",
        page_label="About Us",
        page_description=(
            "Learn about ANGEL, our luggage tracking project and "
            "the purpose behind the system."
        ),
        sections=[
            {
                "heading": "What is ANGEL?",
                "paragraphs": [
                    "ANGEL stands for Airport Navigation & Guidance "
                    "for Every Luggage.",
                    "It is a web-based project designed to help "
                    "passengers and airport staff manage luggage "
                    "information, review recorded journey statuses "
                    "and access support."
                ]
            },
            {
                "heading": "What ANGEL aims to provide",
                "paragraphs": [
                    "The system brings luggage registration, tracking "
                    "information, customer accounts and support "
                    "functionality together in one place."
                ],
                "items": [
                    "Luggage registration and tracking references.",
                    "Recorded luggage status and last known location.",
                    "Customer-specific luggage history when records "
                    "are linked to the customer's account.",
                    "Support assistance through the ANGEL interface.",
                    "Employee and management tools for authorised "
                    "operations."
                ]
            },
            {
                "heading": "Our project objective",
                "paragraphs": [
                    "Our objective is to demonstrate how a digital "
                    "system can make luggage information easier to "
                    "record, find and manage for both passengers "
                    "and employees."
                ]
            }
        ]
    )


# =========================================================
# LEGAL INFORMATION
# =========================================================

@app.route("/legal")
def legal():
    return render_template(
        "information_page.html",
        page_title="Legal Information",
        page_label="Legal",
        page_description=(
            "Important information about the scope, limitations "
            "and intended use of the ANGEL prototype."
        ),
        sections=[
            {
                "heading": "Project status",
                "paragraphs": [
                    "ANGEL is currently a project prototype intended "
                    "to demonstrate luggage management and tracking "
                    "workflows. It is not represented as an official "
                    "airline or airport-operated service."
                ]
            },
            {
                "heading": "Flight and luggage information",
                "paragraphs": [
                    "Luggage and flight details displayed by ANGEL "
                    "come from records available in the project "
                    "database. Unless a live airline-data integration "
                    "is separately implemented, this information must "
                    "not be treated as a live airline timetable or "
                    "confirmed departure, arrival or delay information."
                ]
            },
            {
                "heading": "Accuracy and availability",
                "paragraphs": [
                    "Displayed information depends on the accuracy "
                    "and completeness of the records entered into "
                    "the system. A missing or outdated record may "
                    "not reflect the actual physical location or "
                    "condition of a bag."
                ]
            },
            {
                "heading": "Related policies",
                "paragraphs": [
                    "Please read the Terms and Conditions and Privacy "
                    "Policy pages for further information about "
                    "intended system use and the data handled by "
                    "this prototype."
                ]
            }
        ]
    )


# =========================================================
# TERMS AND CONDITIONS
# =========================================================

@app.route("/terms-and-conditions")
def terms_and_conditions():
    return render_template(
        "information_page.html",
        page_title="Terms & Conditions",
        page_label="Terms of Use",
        page_description=(
            "Guidance for using the ANGEL luggage tracking "
            "and management prototype."
        ),
        sections=[
            {
                "heading": "1. Purpose of the system",
                "paragraphs": [
                    "ANGEL is designed to demonstrate digital luggage "
                    "registration, tracking records, customer accounts "
                    "and support workflows. Features and information "
                    "may change as the project develops."
                ]
            },
            {
                "heading": "2. Account responsibility",
                "paragraphs": [
                    "Customers should provide accurate information "
                    "when creating an account and should keep their "
                    "login credentials private. Do not use another "
                    "person's account without permission."
                ]
            },
            {
                "heading": "3. Tracking information",
                "paragraphs": [
                    "Tracking references and journey statuses reflect "
                    "records stored in ANGEL. They do not independently "
                    "confirm the real-time location of a physical bag "
                    "or the operational status of an airline flight."
                ]
            },
            {
                "heading": "4. Acceptable use",
                "paragraphs": [
                    "Users should not attempt to access accounts, "
                    "passenger records or management functions "
                    "without authorisation, interfere with the "
                    "system, or deliberately submit misleading "
                    "information."
                ]
            },
            {
                "heading": "5. Prototype limitations",
                "paragraphs": [
                    "ANGEL is a project prototype. Availability, "
                    "record accuracy and the behaviour of individual "
                    "features may be limited by the demonstration "
                    "environment and the data available."
                ]
            },
            {
                "heading": "6. Questions and support",
                "paragraphs": [
                    "For questions about a record or a problem using "
                    "the system, use the available ANGEL support "
                    "features or contact an authorised project "
                    "Supervisor or Administrator."
                ]
            }
        ]
    )


# =========================================================
# PRIVACY POLICY
# =========================================================

@app.route("/privacy-policy")
def privacy_policy():
    return render_template(
        "information_page.html",
        page_title="Privacy Policy",
        page_label="Privacy",
        page_description=(
            "An overview of the types of information handled by "
            "ANGEL and how that information is used in the prototype."
        ),
        sections=[
            {
                "heading": "1. Information handled by ANGEL",
                "paragraphs": [
                    "Depending on the features used, the prototype "
                    "may store customer names and usernames, password "
                    "hashes, luggage tracking references, flight "
                    "numbers, departure and destination details, "
                    "luggage weight, journey statuses, locations "
                    "and registration dates."
                ]
            },
            {
                "heading": "2. Support conversations",
                "paragraphs": [
                    "Information submitted through the support "
                    "function may be stored so that a conversation "
                    "can be displayed and handled by the support "
                    "workflow."
                ]
            },
            {
                "heading": "3. How information is used",
                "paragraphs": [
                    "The information is used to demonstrate customer "
                    "accounts, luggage tracking, personal luggage "
                    "history, employee operations and support "
                    "functionality."
                ]
            },
            {
                "heading": "4. Access to records",
                "paragraphs": [
                    "Personal luggage history is intended to be "
                    "limited to records linked to the logged-in "
                    "customer account. Employee and management "
                    "features provide access according to the "
                    "permissions implemented in the application."
                ]
            },
            {
                "heading": "5. Credentials and account safety",
                "paragraphs": [
                    "The application stores password hashes rather "
                    "than saving customer passwords as readable "
                    "plain text. Users should still choose a "
                    "strong password and must not share it."
                ]
            },
            {
                "heading": "6. Prototype and third-party resources",
                "paragraphs": [
                    "ANGEL is a project prototype and has not been "
                    "independently audited for production privacy "
                    "or security requirements. Some visual assets "
                    "may load from external font or icon services."
                ]
            },
            {
                "heading": "7. Questions or corrections",
                "paragraphs": [
                    "If you have a question about a demonstration "
                    "record or believe information is incorrect, "
                    "contact an authorised project Supervisor or "
                    "Administrator so the record can be reviewed."
                ]
            }
        ]
    )


# =========================================================
# CUSTOMER FLIGHT HISTORY
# =========================================================

@app.route("/flights")
def flights():
    search_term = request.args.get("search", "").strip()

    # Signed-out visitors see the login prompt.
    # Do not query or expose any customer's luggage records.
    customer_id = session.get("user_id")

    if customer_id is None:
        return render_template(
            "flights.html",
            customer_name=None,
            customer_history=[],
            search_term=search_term
        )

    connection = get_db()

    try:
        # Validate the logged-in customer account.
        customer = connection.execute("""
            SELECT id, full_name, status
            FROM users
            WHERE id = ?
        """, (customer_id,)).fetchone()

        if customer is None or customer["status"] != "Active":
            session.pop("user_id", None)
            session.pop("user_name", None)

            flash("Your account is unavailable. Please log in again.")

            return redirect(url_for("user_login"))

        # Search only the luggage records linked to this customer.
        like_term = f"%{search_term}%"

        customer_history = connection.execute("""
            SELECT
                tracking_id,
                flight,
                origin,
                destination,
                journey_status,
                status,
                alert_status,
                location,
                registered_at
            FROM luggage
            WHERE user_id = ?
              AND (
                    ? = ''
                    OR tracking_id LIKE ?
                    OR flight LIKE ?
                    OR origin LIKE ?
                    OR destination LIKE ?
              )
            ORDER BY
                COALESCE(registered_at, '') DESC,
                id DESC
        """, (
            customer_id,
            search_term,
            like_term,
            like_term,
            like_term,
            like_term
        )).fetchall()

        customer_name = customer["full_name"]

    finally:
        connection.close()

    return render_template(
        "flights.html",
        customer_name=customer_name,
        customer_history=customer_history,
        search_term=search_term
    )


# =========================================================
# FAQ PAGE
# =========================================================

@app.route("/faq")
def faq():
    return render_template("faq.html")

# =========================================================
# CUSTOMER REGISTRATION
# =========================================================

@app.route("/user-register", methods=["GET", "POST"])
def user_register():
    if request.method == "GET":
        return render_template("user_register.html")

    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([full_name, username, password, confirm_password]):
        flash("Please complete all fields.")
        return redirect(url_for("user_register"))

    if len(password) < 8:
        flash("Your password must contain at least 8 characters.")
        return redirect(url_for("user_register"))

    if password != confirm_password:
        flash("Your passwords do not match.")
        return redirect(url_for("user_register"))

    connection = get_db()

    try:
        connection.execute("""
            INSERT INTO users (full_name, username, password_hash)
            VALUES (?, ?, ?)
        """, (
            full_name,
            username,
            generate_password_hash(password)
        ))

        connection.commit()

    except sqlite3.IntegrityError:
        flash("That username already exists. Please choose another.")
        return redirect(url_for("user_register"))

    finally:
        connection.close()

    flash("Account created successfully. Please log in.", "success")
    return redirect(url_for("user_login"))


# =========================================================
# CUSTOMER LOGIN
# =========================================================

@app.route("/user-login", methods=["GET", "POST"])
def user_login():
    if request.method == "GET":
        return render_template("user_login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    connection = get_db()

    user = connection.execute("""
        SELECT id, full_name, username, password_hash, status
        FROM users
        WHERE username = ?
    """, (username,)).fetchone()

    connection.close()

    if (
        user is None
        or user["status"] != "Active"
        or not check_password_hash(user["password_hash"], password)
    ):
        flash("Invalid username or password, or the account is inactive.")
        return redirect(url_for("user_login"))

    # Start a customer session without changing employee session fields.
    session.pop("user_id", None)
    session["user_id"] = user["id"]
    session["user_name"] = user["full_name"]

    return redirect(url_for("user_dashboard"))

# =========================================================
# CUSTOMER FORGOT PASSWORD PAGE
# =========================================================

@app.route("/user-forgot-password", methods=["GET"])
def user_forgot_password():
    return render_template("forgot_password.html")


# =========================================================
# CUSTOMER DASHBOARD
# =========================================================

@app.route("/user-dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    connection = get_db()

    user = connection.execute("""
        SELECT id, full_name, status
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if user is None or user["status"] != "Active":
        connection.close()
        session.pop("user_id", None)
        session.pop("user_name", None)
        flash("Your account is unavailable. Please contact support.")
        return redirect(url_for("user_login"))

    # Only show luggage linked to this customer's account.
    luggage = connection.execute("""
        SELECT tracking_id, passenger, flight, origin, destination,
               weight, status, location, journey_status, alert_status,
               registered_at
        FROM luggage
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user["id"],)).fetchall()

    connection.close()

    return render_template(
        "user_dashboard.html",
        customer_name=user["full_name"],
        luggage=luggage
    )


# =========================================================
# CUSTOMER LUGGAGE REGISTRATION
# =========================================================

@app.route("/user-register-luggage", methods=["GET", "POST"])
def register_customer_luggage():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    if request.method == "GET":
        return render_template("user_register_luggage.html")

    passenger = request.form.get("passenger", "").strip()
    flight = request.form.get("flight", "").strip()
    origin = request.form.get("origin", "").strip()
    destination = request.form.get("destination", "").strip()
    weight = request.form.get("weight", "").strip()

    if not all([passenger, flight, origin, destination, weight]):
        flash("Please complete all luggage fields.")
        return redirect(url_for("register_customer_luggage"))

    connection = get_db()

    try:
        # Confirm that the logged-in customer is still active.
        customer = connection.execute("""
            SELECT id
            FROM users
            WHERE id = ? AND status = 'Active'
        """, (session["user_id"],)).fetchone()

        if customer is None:
            session.pop("user_id", None)
            session.pop("user_name", None)
            flash("Your account is unavailable. Please contact support.")
            return redirect(url_for("user_login"))

        # Generate a unique tracking ID using ANGEL's existing format.
        tracking_id = None

        for _ in range(20):
            possible_id = "ANGEL-" + str(random.randint(10000, 99999))

            existing = connection.execute("""
                SELECT id FROM luggage WHERE tracking_id = ?
            """, (possible_id,)).fetchone()

            if existing is None:
                tracking_id = possible_id
                break

        if tracking_id is None:
            flash("Could not generate a tracking ID. Please try again.")
            return redirect(url_for("register_customer_luggage"))

        # Link the luggage to the logged-in customer,
        # not to a customer ID supplied by the form.
        connection.execute("""
            INSERT INTO luggage (
                user_id, tracking_id, passenger, flight,
                origin, destination, weight, status, location,
                journey_status, alert_status, registered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            session["user_id"],
            tracking_id,
            passenger,
            flight,
            origin,
            destination,
            weight,
            "Checked In",
            origin,
            "Checked In",
            None
        ))

        connection.commit()

    finally:
        connection.close()

    flash(f"Luggage registered successfully! Your tracking ID is {tracking_id}.")
    return redirect(url_for("user_dashboard"))


# =========================================================
# CUSTOMER LOGOUT
# =========================================================

@app.route("/user-logout")
def user_logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    flash("You have been logged out.")
    return redirect(url_for("user_login"))

# =========================================================
# EMPLOYEE LOGIN PAGE
# =========================================================

@app.route("/employee-login", methods=["GET"])
def employee_login():
    return render_template("employee_login.html")


# =========================================================
# EMPLOYEE LOGIN
# =========================================================

@app.route("/employee-login", methods=["POST"])
def employee_login_process():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    connection = get_db()
    employee = connection.execute("""
        SELECT * FROM employees WHERE username = ?
    """, (username,)).fetchone()
    connection.close()

    if employee is None:
        return render_template(
            "employee_login.html",
            error="Invalid username or password."
        )

    if employee["status"] != "Active":
        return render_template(
            "employee_login.html",
            error="This employee account is currently disabled."
        )

    if not check_password_hash(employee["password_hash"], password):
        return render_template(
            "employee_login.html",
            error="Invalid username or password."
        )

    session["employee_id"] = employee["id"]
    session["employee_name"] = employee["full_name"]
    session["employee_role"] = employee["role"]

    log_activity("Employee Login", "Employee logged into ANGEL.")

    return redirect(url_for("employee_dashboard"))


# =========================================================
# EMPLOYEE DASHBOARD
# =========================================================

@app.route("/employee-dashboard")
def employee_dashboard():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    return render_template(
        "employee_dashboard.html",
        employee_name=session["employee_name"],
        employee_role=session["employee_role"]
    )


# =========================================================
# CUSTOMER DATABASE
# =========================================================

@app.route("/customers", methods=["GET"])
def customers():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    connection = get_db()

    try:
        customer_rows = connection.execute("""
            SELECT id, full_name, username, status
            FROM users
            ORDER BY id DESC
        """).fetchall()
    finally:
        connection.close()

    return render_template(
        "customers.html",
        customers=customer_rows
    )


# =========================================================
# EDIT CUSTOMER DETAILS
# =========================================================

@app.route("/customers/edit/<int:customer_id>", methods=["GET", "POST"])
def edit_customer(customer_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    connection = get_db()

    try:
        customer = connection.execute("""
            SELECT id, full_name, username, status
            FROM users
            WHERE id = ?
        """, (customer_id,)).fetchone()

        if customer is None:
            return "Customer not found.", 404

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            username = request.form.get("username", "").strip()

            if not full_name or not username:
                flash("Please complete all fields.")
                return redirect(
                    url_for("edit_customer", customer_id=customer_id)
                )

            try:
                connection.execute("""
                    UPDATE users
                    SET full_name = ?, username = ?
                    WHERE id = ?
                """, (full_name, username, customer_id))

                connection.commit()

            except sqlite3.IntegrityError:
                flash("That username is already in use.")
                return redirect(
                    url_for("edit_customer", customer_id=customer_id)
                )

            flash("Customer details updated successfully.")

            log_activity(
                "Customer Updated",
                f"Updated customer account ID {customer_id}."
            )

            return redirect(url_for("customers"))

    finally:
        connection.close()

    return render_template(
        "edit_customer.html",
        customer=customer
    )


# =========================================================
# ACTIVATE OR DEACTIVATE CUSTOMER
# =========================================================

@app.route("/customers/status/<int:customer_id>", methods=["POST"])
def change_customer_status(customer_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    connection = get_db()

    try:
        customer = connection.execute("""
            SELECT id, full_name, status
            FROM users
            WHERE id = ?
        """, (customer_id,)).fetchone()

        if customer is None:
            flash("Customer not found.")
            return redirect(url_for("customers"))

        new_status = (
            "Inactive"
            if customer["status"] == "Active"
            else "Active"
        )

        connection.execute("""
            UPDATE users
            SET status = ?
            WHERE id = ?
        """, (new_status, customer_id))

        connection.commit()

    finally:
        connection.close()

    log_activity(
        "Customer Status Changed",
        f"Customer ID {customer_id} changed to {new_status}."
    )

    flash(f"Customer account is now {new_status}.")

    return redirect(url_for("customers"))


# =========================================================
# EMPLOYEE LOGOUT
# =========================================================

@app.route("/employee-logout")
def employee_logout():
    log_activity("Employee Logout", "Employee logged out of ANGEL.")
    session.clear()
    return redirect(url_for("employee_login"))


# =========================================================
# LUGGAGE REGISTRATION PAGE
# =========================================================

@app.route("/admin")
def admin():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    connection = get_db()

    customers = connection.execute("""
        SELECT id, full_name, username
        FROM users
        WHERE status = 'Active'
        ORDER BY full_name ASC
    """).fetchall()

    connection.close()

    return render_template(
        "admin.html",
        customers=customers
    )

# =========================================================
# MANAGEMENT DASHBOARD
# =========================================================

@app.route("/management")
def management():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    return render_template(
        "management.html",
        employee_name=session["employee_name"]
    )


# =========================================================
# EMPLOYEE ACCOUNTS
# =========================================================

@app.route("/employees")
def employees():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    connection = get_db()
    employee_rows = connection.execute("""
        SELECT id, full_name, username, role, status
        FROM employees
        ORDER BY id ASC
    """).fetchall()
    connection.close()

    return render_template("employees.html", employees=employee_rows)


# =========================================================
# CREATE EMPLOYEE
# =========================================================

@app.route("/employees/create", methods=["POST"])
def create_employee():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "Employee")

    if not full_name or not username or not password:
        return "Please complete all required fields.", 400

    if role not in ["Employee", "Supervisor", "Admin"]:
        return "Invalid employee role.", 400

    connection = get_db()

    existing_employee = connection.execute("""
        SELECT id FROM employees WHERE username = ?
    """, (username,)).fetchone()

    if existing_employee:
        connection.close()
        return "That username is already in use.", 400

    connection.execute("""
        INSERT INTO employees
            (full_name, username, password_hash, role, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        full_name,
        username,
        generate_password_hash(password),
        role,
        "Active"
    ))

    connection.commit()
    connection.close()

    log_activity(
        "Employee Created",
        f"Created employee account: {username} ({role})."
    )

    return redirect(url_for("employees"))


# =========================================================
# EDIT EMPLOYEE PAGE
# =========================================================

@app.route("/employees/edit/<int:employee_id>", methods=["GET"])
def edit_employee(employee_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    connection = get_db()
    employee = connection.execute("""
        SELECT id, full_name, username, role, status
        FROM employees WHERE id = ?
    """, (employee_id,)).fetchone()
    connection.close()

    if employee is None:
        return "Employee not found.", 404

    return render_template("edit_employee.html", employee=employee)


# =========================================================
# UPDATE EMPLOYEE
# =========================================================

@app.route("/employees/edit/<int:employee_id>", methods=["POST"])
def update_employee(employee_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip()
    role = request.form.get("role", "Employee")
    status = request.form.get("status", "Active")

    if not full_name or not username:
        return "Name and username are required.", 400

    if role not in ["Employee", "Supervisor", "Admin"]:
        return "Invalid employee role.", 400

    if status not in ["Active", "Disabled"]:
        return "Invalid employee status.", 400

    connection = get_db()

    duplicate = connection.execute("""
        SELECT id FROM employees
        WHERE username = ? AND id != ?
    """, (username, employee_id)).fetchone()

    if duplicate:
        connection.close()
        return "That username is already in use.", 400

    connection.execute("""
        UPDATE employees
        SET full_name = ?, username = ?, role = ?, status = ?
        WHERE id = ?
    """, (full_name, username, role, status, employee_id))

    connection.commit()
    connection.close()

    log_activity("Employee Updated", f"Updated employee ID {employee_id}.")

    return redirect(url_for("employees"))


# =========================================================
# CHANGE EMPLOYEE PASSWORD
# =========================================================

@app.route("/employees/password/<int:employee_id>", methods=["POST"])
def change_employee_password(employee_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    password = request.form.get("password", "")

    if not password:
        return "Password is required.", 400

    connection = get_db()
    employee = connection.execute("""
        SELECT username FROM employees WHERE id = ?
    """, (employee_id,)).fetchone()

    if employee is None:
        connection.close()
        return "Employee not found.", 404

    connection.execute("""
        UPDATE employees SET password_hash = ? WHERE id = ?
    """, (generate_password_hash(password), employee_id))

    connection.commit()
    connection.close()

    log_activity(
        "Password Changed",
        f"Changed password for employee: {employee['username']}."
    )

    return redirect(url_for("employees"))


# =========================================================
# RESET EMPLOYEE PASSWORD PAGE
# =========================================================

@app.route("/employees/password/<int:employee_id>", methods=["GET"])
def reset_employee_password(employee_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    connection = get_db()
    employee = connection.execute("""
        SELECT id, full_name, username
        FROM employees WHERE id = ?
    """, (employee_id,)).fetchone()
    connection.close()

    if employee is None:
        return "Employee not found.", 404

    return render_template(
        "reset_employee_password.html",
        employee=employee
    )


# =========================================================
# ENABLE / DISABLE EMPLOYEE
# =========================================================

@app.route("/employees/toggle/<int:employee_id>", methods=["POST"])
def toggle_employee_status(employee_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    if employee_id == session.get("employee_id"):
        return "You cannot disable your own account.", 400

    connection = get_db()
    employee = connection.execute("""
        SELECT username, status FROM employees WHERE id = ?
    """, (employee_id,)).fetchone()

    if employee is None:
        connection.close()
        return "Employee not found.", 404

    new_status = "Disabled" if employee["status"] == "Active" else "Active"

    connection.execute("""
        UPDATE employees SET status = ? WHERE id = ?
    """, (new_status, employee_id))

    connection.commit()
    connection.close()

    log_activity(
        "Employee Status Changed",
        f"{employee['username']} changed to {new_status}."
    )

    return redirect(url_for("employees"))


# =========================================================
# DELETE EMPLOYEE
# =========================================================

@app.route("/employees/delete/<int:employee_id>", methods=["POST"])
def delete_employee(employee_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    if employee_id == session.get("employee_id"):
        return "You cannot delete your own account.", 400

    connection = get_db()
    employee = connection.execute("""
        SELECT username FROM employees WHERE id = ?
    """, (employee_id,)).fetchone()

    if employee is None:
        connection.close()
        return "Employee not found.", 404

    connection.execute("""
        DELETE FROM employees WHERE id = ?
    """, (employee_id,))

    connection.commit()
    connection.close()

    log_activity(
        "Employee Deleted",
        f"Deleted employee account: {employee['username']}."
    )

    return redirect(url_for("employees"))


# =========================================================
# ROLES & PERMISSIONS
# =========================================================

@app.route("/roles")
def roles():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    connection = get_db()
    employee_rows = connection.execute("""
        SELECT id, full_name, username, role, status
        FROM employees
        ORDER BY role ASC, full_name ASC
    """).fetchall()
    connection.close()

    return render_template("roles.html", employees=employee_rows)


# =========================================================
# UPDATE EMPLOYEE ROLE
# =========================================================

@app.route("/roles/update/<int:employee_id>", methods=["POST"])
def update_employee_role(employee_id):
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    role = request.form.get("role", "")

    if role not in ["Employee", "Supervisor", "Admin"]:
        return "Invalid role.", 400

    if employee_id == session.get("employee_id"):
        return "You cannot change your own role.", 400

    connection = get_db()
    employee = connection.execute("""
        SELECT username FROM employees WHERE id = ?
    """, (employee_id,)).fetchone()

    if employee is None:
        connection.close()
        return "Employee not found.", 404

    connection.execute("""
        UPDATE employees SET role = ? WHERE id = ?
    """, (role, employee_id))

    connection.commit()
    connection.close()

    log_activity(
        "Employee Role Changed",
        f"{employee['username']} role changed to {role}."
    )

    return redirect(url_for("roles"))


# =========================================================
# SYSTEM OVERVIEW
# =========================================================

@app.route("/overview")
def overview():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    connection = get_db()

    total_employees = connection.execute(
        "SELECT COUNT(*) FROM employees"
    ).fetchone()[0]

    active_employees = connection.execute("""
        SELECT COUNT(*) FROM employees WHERE status = 'Active'
    """).fetchone()[0]

    disabled_employees = connection.execute("""
        SELECT COUNT(*) FROM employees WHERE status = 'Disabled'
    """).fetchone()[0]

    total_luggage = connection.execute(
        "SELECT COUNT(*) FROM luggage"
    ).fetchone()[0]

    checked_in = connection.execute("""
        SELECT COUNT(*) FROM luggage
        WHERE journey_status = 'Checked In' OR status = 'Checked In'
    """).fetchone()[0]

    loaded = connection.execute("""
        SELECT COUNT(*) FROM luggage
        WHERE journey_status = 'Loaded onto Aircraft'
        OR status = 'Loaded onto Aircraft'
    """).fetchone()[0]

    transit = connection.execute("""
        SELECT COUNT(*) FROM luggage
        WHERE journey_status = 'In Transit' OR status = 'In Transit'
    """).fetchone()[0]

    delayed = connection.execute("""
        SELECT COUNT(*) FROM luggage
        WHERE alert_status = 'Delayed' OR status = 'Delayed'
    """).fetchone()[0]

    lost = connection.execute("""
        SELECT COUNT(*) FROM luggage
        WHERE alert_status = 'Lost' OR status = 'Lost'
    """).fetchone()[0]

    connection.close()

    statistics = {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "disabled_employees": disabled_employees,
        "total_luggage": total_luggage,
        "checked_in": checked_in,
        "loaded": loaded,
        "transit": transit,
        "delayed": delayed,
        "lost": lost
    }

    return render_template("overview.html", statistics=statistics)


# =========================================================
# ACTIVITY LOG
# =========================================================

@app.route("/activity-log")
def activity_log():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    connection = get_db()
    activities = connection.execute("""
        SELECT id, employee_name, action, details, timestamp
        FROM activity_log
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()
    connection.close()

    return render_template("activity_log.html", activities=activities)


# =========================================================
# DOWNLOAD ACTIVITY LOG AS PDF
# =========================================================

@app.route("/activity-log/pdf")
def activity_log_pdf():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return redirect(url_for("employee_dashboard"))

    connection = get_db()
    activities = connection.execute("""
        SELECT id, employee_name, action, details, timestamp
        FROM activity_log
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()
    connection.close()

    pdf_buffer = io.BytesIO()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "AngelTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "AngelSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        alignment=TA_CENTER,
        spaceAfter=14
    )

    cell_style = ParagraphStyle(
        "CellStyle",
        parent=styles["Normal"],
        fontSize=8,
        leading=10
    )

    story = [
        Paragraph("ANGEL", title_style),
        Paragraph("Employee Activity Log", subtitle_style),
        Paragraph(
            f"Generated for {session.get('employee_name', 'Employee')}",
            subtitle_style
        ),
        Spacer(1, 5 * mm)
    ]

    table_data = [[
        Paragraph("<b>ID</b>", cell_style),
        Paragraph("<b>Employee</b>", cell_style),
        Paragraph("<b>Action</b>", cell_style),
        Paragraph("<b>Details</b>", cell_style),
        Paragraph("<b>Date / Time</b>", cell_style)
    ]]

    for activity in activities:
        table_data.append([
            Paragraph(str(activity["id"]), cell_style),
            Paragraph(activity["employee_name"] or "Unknown", cell_style),
            Paragraph(activity["action"] or "", cell_style),
            Paragraph(activity["details"] or "", cell_style),
            Paragraph(activity["timestamp"] or "", cell_style)
        ])

    activity_table = Table(
        table_data,
        colWidths=[
            15 * mm, 42 * mm, 45 * mm, 120 * mm, 42 * mm
        ],
        repeatRows=1
    )

    activity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white, colors.HexColor("#F3F4F6")
        ]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5)
    ]))

    story.append(activity_table)
    document.build(story)
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="ANGEL_Activity_Log.pdf"
    )


# =========================================================
# LIVE STATUS PAGE
# =========================================================

@app.route("/live-status")
def live_status():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    return render_template("live_status.html")


# =========================================================
# FIND LUGGAGE FOR LIVE STATUS
# =========================================================

@app.route("/live-status/search", methods=["GET"])
def live_status_search():
    if "employee_id" not in session:
        return jsonify({
            "success": False,
            "message": "Employee login required."
        }), 401

    tracking_id = request.args.get("id", "").upper().strip()

    if not tracking_id:
        return jsonify({
            "success": False,
            "message": "Please enter a luggage tracking ID."
        })

    connection = get_db()
    luggage = connection.execute("""
        SELECT tracking_id, passenger, flight, origin, destination,
               weight, status, location, journey_status, alert_status,
               registered_at
        FROM luggage
        WHERE tracking_id = ?
    """, (tracking_id,)).fetchone()
    connection.close()

    if luggage:
        journey_status = luggage["journey_status"] or luggage["status"]

        return jsonify({
            "success": True,
            "luggage": {
                "tracking_id": luggage["tracking_id"],
                "passenger": luggage["passenger"],
                "flight": luggage["flight"],
                "origin": luggage["origin"],
                "destination": luggage["destination"],
                "weight": luggage["weight"],
                "status": journey_status,
                "journey_status": journey_status,
                "alert_status": luggage["alert_status"],
                "location": luggage["location"],
                "registered_at": luggage["registered_at"]
            }
        })

    return jsonify({
        "success": False,
        "message": "Luggage tracking ID not found."
    })


# =========================================================
# UPDATE LIVE STATUS
# =========================================================

@app.route("/live-status/update", methods=["POST"])
def update_live_status():
    if "employee_id" not in session:
        return jsonify({
            "success": False,
            "message": "Employee login required."
        }), 401

    tracking_id = request.form.get("tracking_id", "").upper().strip()
    status = request.form.get("status", "").strip()
    location = request.form.get("location", "").strip()

    if not tracking_id:
        return jsonify({
            "success": False,
            "message": "Tracking ID is required."
        })

    if not status:
        return jsonify({
            "success": False,
            "message": "Please select a luggage status."
        })

    if not location:
        return jsonify({
            "success": False,
            "message": "Please enter the current location."
        })

    allowed_statuses = [
        "Checked In",
        "Loaded onto Aircraft",
        "In Transit",
        "Arrived at Destination",
        "Ready for Collection",
        "Collected",
        "Delayed",
        "Lost"
    ]

    if status not in allowed_statuses:
        return jsonify({
            "success": False,
            "message": "Invalid luggage status."
        })

    connection = get_db()
    luggage = connection.execute("""
        SELECT id, status, journey_status, alert_status
        FROM luggage
        WHERE tracking_id = ?
    """, (tracking_id,)).fetchone()

    if luggage is None:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Luggage tracking ID not found."
        })

    if status in ["Delayed", "Lost"]:
        journey_status = luggage["journey_status"] or luggage["status"]

        if journey_status in ["Delayed", "Lost"]:
            journey_status = "Checked In"

        connection.execute("""
            UPDATE luggage
            SET status = ?, journey_status = ?, alert_status = ?, location = ?
            WHERE tracking_id = ?
        """, (journey_status, journey_status, status, location, tracking_id))
    else:
        connection.execute("""
            UPDATE luggage
            SET status = ?, journey_status = ?, alert_status = NULL, location = ?
            WHERE tracking_id = ?
        """, (status, status, location, tracking_id))

    connection.commit()
    connection.close()

    log_activity(
        "Luggage Status Updated",
        f"{tracking_id} updated to {status} at {location}."
    )

    return jsonify({
        "success": True,
        "message": "Luggage live status updated successfully."
    })


# =========================================================
# EMPLOYEE LUGGAGE SEARCH PAGE
# =========================================================

@app.route("/employee-luggage", methods=["GET"])
def employee_luggage():
    if "employee_id" not in session:
        return redirect(url_for("employee_login"))

    search = request.args.get("search", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    connection = get_db()

    query = """
        SELECT id, tracking_id, passenger, flight, origin, destination,
               weight, status, location, journey_status, alert_status,
               registered_at
        FROM luggage
        WHERE 1 = 1
    """
    parameters = []

    if search:
        query += """
            AND (tracking_id LIKE ? OR passenger LIKE ? OR flight LIKE ?)
        """
        search_value = f"%{search}%"
        parameters.extend([search_value, search_value, search_value])

    if date_from:
        query += " AND date(registered_at) >= date(?)"
        parameters.append(date_from)

    if date_to:
        query += " AND date(registered_at) <= date(?)"
        parameters.append(date_to)

    query += " ORDER BY datetime(registered_at) DESC"

    luggage = connection.execute(query, parameters).fetchall()
    connection.close()

    return render_template(
        "employee_luggage.html",
        luggage=luggage,
        search=search,
        date_from=date_from,
        date_to=date_to
    )


# =========================================================
# EMPLOYEE LUGGAGE SEARCH API
# =========================================================

@app.route("/employee-luggage/search", methods=["GET"])
def employee_luggage_search():
    if "employee_id" not in session:
        return jsonify({
            "success": False,
            "message": "Employee login required."
        }), 401

    search = request.args.get("search", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    connection = get_db()

    query = """
        SELECT id, tracking_id, passenger, flight, origin, destination,
               weight, status, location, journey_status, alert_status,
               registered_at
        FROM luggage
        WHERE 1 = 1
    """
    parameters = []

    if search:
        query += """
            AND (tracking_id LIKE ? OR passenger LIKE ? OR flight LIKE ?)
        """
        search_value = f"%{search}%"
        parameters.extend([search_value, search_value, search_value])

    if date_from:
        query += " AND date(registered_at) >= date(?)"
        parameters.append(date_from)

    if date_to:
        query += " AND date(registered_at) <= date(?)"
        parameters.append(date_to)

    query += " ORDER BY datetime(registered_at) DESC"

    luggage = connection.execute(query, parameters).fetchall()
    connection.close()

    results = []

    for item in luggage:
        journey_status = item["journey_status"] or item["status"]

        results.append({
            "id": item["id"],
            "tracking_id": item["tracking_id"],
            "passenger": item["passenger"],
            "flight": item["flight"],
            "origin": item["origin"],
            "destination": item["destination"],
            "weight": item["weight"],
            "status": journey_status,
            "journey_status": journey_status,
            "alert_status": item["alert_status"],
            "location": item["location"],
            "registered_at": item["registered_at"]
        })

    return jsonify({
        "success": True,
        "count": len(results),
        "luggage": results
    })


# =========================================================
# REMOVE PASSENGER
# =========================================================

@app.route("/employee-luggage/delete-passenger", methods=["POST"])
def delete_luggage_passenger():
    if "employee_id" not in session:
        return jsonify({
            "success": False,
            "message": "Employee login required."
        }), 401

    if session.get("employee_role") not in ["Supervisor", "Admin"]:
        return jsonify({
            "success": False,
            "message": "You do not have permission to remove passengers."
        }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Invalid delete request."
        }), 400

    passenger = str(data.get("passenger", "")).strip()
    luggage_ids = data.get("luggage_ids", [])

    if not passenger:
        return jsonify({
            "success": False,
            "message": "Passenger name is required."
        }), 400

    if not isinstance(luggage_ids, list):
        return jsonify({
            "success": False,
            "message": "Invalid luggage record list."
        }), 400

    valid_ids = []

    for luggage_id in luggage_ids:
        try:
            converted_id = int(luggage_id)
            if converted_id > 0:
                valid_ids.append(converted_id)
        except (TypeError, ValueError):
            continue

    valid_ids = list(dict.fromkeys(valid_ids))

    if not valid_ids:
        return jsonify({
            "success": False,
            "message": "No luggage records were selected."
        }), 400

    connection = get_db()
    placeholders = ",".join("?" for _ in valid_ids)

    rows = connection.execute(
        f"""
        SELECT id, tracking_id, passenger
        FROM luggage
        WHERE id IN ({placeholders})
        """,
        valid_ids
    ).fetchall()

    if not rows:
        connection.close()
        return jsonify({
            "success": False,
            "message": "The selected luggage records no longer exist."
        }), 404

    mismatched_records = [
        row["id"] for row in rows
        if row["passenger"].strip().lower() != passenger.lower()
    ]

    if mismatched_records:
        connection.close()
        return jsonify({
            "success": False,
            "message": "One or more selected records do not belong to this passenger."
        }), 400

    connection.execute(
        f"DELETE FROM luggage WHERE id IN ({placeholders})",
        valid_ids
    )

    deleted_count = connection.execute(
        "SELECT changes()"
    ).fetchone()[0]

    connection.commit()
    connection.close()

    tracking_ids = [row["tracking_id"] for row in rows]

    log_activity(
        "Passenger Removed",
        f"Removed passenger '{passenger}'. Deleted {deleted_count} luggage "
        f"record(s): {', '.join(tracking_ids)}."
    )

    return jsonify({
        "success": True,
        "message": f"{passenger} was removed successfully.",
        "deleted_count": deleted_count
    })


# =========================================================
# VIEW LUGGAGE ALIAS
# =========================================================

@app.route("/view-luggage", methods=["GET"])
def view_luggage():
    return redirect(url_for("employee_luggage"))


# =========================================================
# PUBLIC LUGGAGE TRACKING
# =========================================================

@app.route("/track", methods=["GET"])
def track_luggage():
    tracking_id = request.args.get("id", "").upper().strip()

    if not tracking_id:
        return jsonify({
            "success": False,
            "message": "Please enter a luggage tracking ID."
        })

    connection = get_db()
    luggage = connection.execute("""
        SELECT tracking_id, passenger, flight, origin, destination,
               weight, status, location, journey_status, alert_status,
               registered_at
        FROM luggage
        WHERE tracking_id = ?
    """, (tracking_id,)).fetchone()
    connection.close()

    if luggage:
        journey_status = luggage["journey_status"] or luggage["status"]

        return jsonify({
            "success": True,
            "tracking_id": luggage["tracking_id"],
            "luggage": {
                "passenger": luggage["passenger"],
                "flight": luggage["flight"],
                "from": luggage["origin"],
                "to": luggage["destination"],
                "weight": luggage["weight"],
                "status": journey_status,
                "journey_status": journey_status,
                "alert_status": luggage["alert_status"],
                "location": luggage["location"],
                "registered_at": luggage["registered_at"]
            }
        })

    return jsonify({
        "success": False,
        "message": "Luggage tracking ID not found."
    })


# =========================================================
# REGISTER NEW LUGGAGE
# =========================================================

@app.route("/admin/add", methods=["POST"])
def add_luggage():
    if "employee_id" not in session:
        return jsonify({
            "success": False,
            "message": "Employee login required."
        }), 401

    passenger = request.form.get("passenger", "").strip()
    flight = request.form.get("flight", "").strip()
    origin = request.form.get("origin", "").strip()
    destination = request.form.get("destination", "").strip()
    weight = request.form.get("weight", "").strip()

    if not all([passenger, flight, origin, destination, weight]):
        return jsonify({
            "success": False,
            "message": "Please complete all fields."
        }), 400

    connection = get_db()

    try:
        # Automatically link the luggage to a customer account
        # only when exactly one active account matches the
        # passenger's full name.
        matching_customers = connection.execute("""
            SELECT id
            FROM users
            WHERE status = 'Active'
              AND LOWER(TRIM(full_name)) = LOWER(TRIM(?))
            ORDER BY id ASC
        """, (passenger,)).fetchall()

        user_id = None

        if len(matching_customers) == 1:
            user_id = matching_customers[0]["id"]

        # Generate a unique tracking ID.
        tracking_id = None

        for _ in range(20):
            possible_id = "ANGEL-" + str(random.randint(10000, 99999))

            existing = connection.execute("""
                SELECT id
                FROM luggage
                WHERE tracking_id = ?
            """, (possible_id,)).fetchone()

            if existing is None:
                tracking_id = possible_id
                break

        if tracking_id is None:
            return jsonify({
                "success": False,
                "message": "Could not generate a unique tracking ID. Please try again."
            }), 500

        # Save the luggage. A customer account is optional.
        connection.execute("""
            INSERT INTO luggage (
                user_id,
                tracking_id,
                passenger,
                flight,
                origin,
                destination,
                weight,
                status,
                location,
                journey_status,
                alert_status,
                registered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            user_id,
            tracking_id,
            passenger,
            flight,
            origin,
            destination,
            weight,
            "Checked In",
            origin,
            "Checked In",
            None
        ))

        connection.commit()

    finally:
        connection.close()

    log_activity(
        "Luggage Registered",
        f"Registered luggage {tracking_id} for {passenger}."
    )

    return jsonify({
        "success": True,
        "tracking_id": tracking_id
    })

# =========================================================
# LIVE AGENT: PASSENGER STARTS A CHAT
# POST /support/start
# JSON: {"tracking_id": "ANGEL-1001"}
# =========================================================

@app.route("/support/start", methods=["POST"])
def support_start():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        data = request.form

    tracking_id = str(data.get("tracking_id", "")).strip().upper()

    if not tracking_id:
        return jsonify({
            "success": False,
            "message": "Please enter your luggage tracking ID."
        }), 400

    connection = get_db()

    luggage = connection.execute("""
        SELECT tracking_id FROM luggage WHERE tracking_id = ?
    """, (tracking_id,)).fetchone()

    if luggage is None:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Tracking ID not found. Please check it and try again."
        }), 404

    # Reuse this browser's existing open conversation for this tracking ID.
    existing = connection.execute("""
        SELECT id, reference, status
        FROM support_conversations
        WHERE id = ?
          AND tracking_id = ?
          AND status != 'Resolved'
    """, (
        session.get("support_conversation_id", -1),
        tracking_id
    )).fetchone()

    if existing:
        session["support_tracking_id"] = tracking_id
        session["support_conversation_id"] = existing["id"]
        connection.close()

        return jsonify({
            "success": True,
            "reference": existing["reference"],
            "status": existing["status"],
            "message": "Your existing support conversation is available."
        })

    reference = "ANGEL-SUP-" + secrets.token_hex(4).upper()

    cursor = connection.execute("""
        INSERT INTO support_conversations (reference, tracking_id, status)
        VALUES (?, ?, 'Waiting')
    """, (reference, tracking_id))

    conversation_id = cursor.lastrowid

    connection.execute("""
        INSERT INTO support_messages (conversation_id, sender_type, message)
        VALUES (?, 'system', ?)
    """, (
        conversation_id,
        "Your request is in the queue. An ANGEL employee will join when available."
    ))

    connection.commit()
    connection.close()

    session["support_tracking_id"] = tracking_id
    session["support_conversation_id"] = conversation_id

    return jsonify({
        "success": True,
        "reference": reference,
        "status": "Waiting",
        "message": "You're in the queue. Please stay in this chat while you wait."
    }), 201


# =========================================================
# LIVE AGENT: PASSENGER READS MESSAGES
# GET /support/messages?reference=ANGEL-SUP-XXXXXXXX
# =========================================================

@app.route("/support/messages", methods=["GET"])
def support_passenger_messages():
    reference = request.args.get("reference", "").strip().upper()

    connection = get_db()
    conversation = passenger_conversation(connection, reference)

    if conversation is None:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Support conversation not found for this session."
        }), 404

    result = {
        "success": True,
        "reference": conversation["reference"],
        "status": conversation["status"],
        "messages": serialize_messages(connection, conversation["id"])
    }

    connection.close()
    return jsonify(result)


# =========================================================
# LIVE AGENT: PASSENGER SENDS A MESSAGE
# POST /support/send
# JSON: {"reference": "...", "message": "..."}
# =========================================================

@app.route("/support/send", methods=["POST"])
def support_passenger_send():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Invalid message request."
        }), 400

    reference = str(data.get("reference", "")).strip().upper()
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({
            "success": False,
            "message": "Please enter a message."
        }), 400

    if len(message) > 2000:
        return jsonify({
            "success": False,
            "message": "Messages must be 2,000 characters or fewer."
        }), 400

    connection = get_db()
    conversation = passenger_conversation(connection, reference)

    if conversation is None:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Support conversation not found for this session."
        }), 404

    if conversation["status"] == "Resolved":
        connection.close()
        return jsonify({
            "success": False,
            "message": "This conversation is resolved. Please start a new request."
        }), 409

    connection.execute("""
        INSERT INTO support_messages (conversation_id, sender_type, message)
        VALUES (?, 'passenger', ?)
    """, (conversation["id"], message))

    connection.execute("""
        UPDATE support_conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (conversation["id"],))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Message sent."
    })


# =========================================================
# LIVE AGENT: EMPLOYEE SUPPORT INBOX
# GET /support/employee/inbox
# =========================================================

@app.route("/support/employee/inbox", methods=["GET"])
def support_employee_inbox():
    if not employee_is_logged_in():
        return jsonify({
            "success": False,
            "message": "Active employee login required."
        }), 401

    connection = get_db()

    rows = connection.execute("""
        SELECT
            c.id,
            c.reference,
            c.tracking_id,
            COALESCE(l.passenger, 'Passenger') AS passenger_name,
            c.status,
            c.assigned_employee_id,
            c.created_at,
            c.updated_at,
            e.full_name AS assigned_employee,
            (
                SELECT m.message
                FROM support_messages m
                WHERE m.conversation_id = c.id
                ORDER BY m.id DESC
                LIMIT 1
            ) AS last_message

        FROM support_conversations c

        LEFT JOIN luggage l
            ON UPPER(TRIM(l.tracking_id)) =
               UPPER(TRIM(c.tracking_id))

        LEFT JOIN employees e
            ON e.id = c.assigned_employee_id

        WHERE c.status IN ('Waiting', 'In Progress')

        ORDER BY
            CASE c.status
                WHEN 'Waiting' THEN 0
                ELSE 1
            END,
            c.updated_at ASC
    """).fetchall()

    conversations = [
        {
            "id": row["id"],
            "reference": row["reference"],
            "tracking_id": row["tracking_id"],
            "passenger_name": row["passenger_name"],
            "status": row["status"],
            "assigned_employee_id": row["assigned_employee_id"],
            "assigned_employee": row["assigned_employee"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_message": row["last_message"] or ""
        }
        for row in rows
    ]

    connection.close()

    return jsonify({
        "success": True,
        "conversations": conversations
    })

# =========================================================
# SUPPORT INBOX PAGE
# =========================================================

@app.route("/support/inbox", methods=["GET"])
def support_inbox_page():
    if not employee_is_logged_in():
        return redirect(url_for("employee_login"))

    return render_template("support_inbox.html")



# =========================================================
# LIVE AGENT: EMPLOYEE ACCEPTS A CHAT
# POST /support/employee/accept/<conversation_id>
# =========================================================

@app.route(
    "/support/employee/accept/<int:conversation_id>",
    methods=["POST"]
)
def support_employee_accept(conversation_id):
    if not employee_is_logged_in():
        return jsonify({
            "success": False,
            "message": "Active employee login required."
        }), 401

    connection = get_db()

    conversation = connection.execute("""
        SELECT id, status, assigned_employee_id
        FROM support_conversations
        WHERE id = ?
    """, (conversation_id,)).fetchone()

    if conversation is None:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Support conversation not found."
        }), 404

    if conversation["status"] == "Resolved":
        connection.close()
        return jsonify({
            "success": False,
            "message": "This conversation has already been resolved."
        }), 409

    employee_id = session["employee_id"]

    if (
        conversation["assigned_employee_id"] is not None
        and conversation["assigned_employee_id"] != employee_id
    ):
        connection.close()
        return jsonify({
            "success": False,
            "message": "Another employee has already accepted this conversation."
        }), 409

    connection.execute("""
        UPDATE support_conversations
        SET status = 'In Progress',
            assigned_employee_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (employee_id, conversation_id))

    connection.execute("""
        INSERT INTO support_messages (
            conversation_id, sender_type, sender_employee_id, message
        )
        VALUES (?, 'system', ?, ?)
    """, (
        conversation_id,
        employee_id,
        f"{session.get('employee_name', 'An ANGEL employee')} has joined the conversation."
    ))

    connection.commit()
    connection.close()

    log_activity(
        "Support Conversation Accepted",
        f"Accepted support conversation ID {conversation_id}."
    )

    return jsonify({
        "success": True,
        "message": "Conversation accepted."
    })


# =========================================================
# LIVE AGENT: EMPLOYEE READS CHAT MESSAGES
# GET /support/employee/messages/<conversation_id>
# =========================================================

@app.route(
    "/support/employee/messages/<int:conversation_id>",
    methods=["GET"]
)
def support_employee_messages(conversation_id):
    if not employee_is_logged_in():
        return jsonify({
            "success": False,
            "message": "Active employee login required."
        }), 401

    connection = get_db()

    conversation = connection.execute("""
        SELECT * FROM support_conversations WHERE id = ?
    """, (conversation_id,)).fetchone()

    if conversation is None:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Support conversation not found."
        }), 404

    if not employee_can_access_conversation(conversation):
        connection.close()
        return jsonify({
            "success": False,
            "message": "This conversation is assigned to another employee."
        }), 403

    result = {
        "success": True,
        "conversation": {
            "id": conversation["id"],
            "reference": conversation["reference"],
            "tracking_id": conversation["tracking_id"],
            "status": conversation["status"],
            "assigned_employee_id": conversation["assigned_employee_id"]
        },
        "messages": serialize_messages(connection, conversation_id)
    }

    connection.close()
    return jsonify(result)


# =========================================================
# LIVE AGENT: EMPLOYEE SENDS A REPLY
# POST /support/employee/send/<conversation_id>
# JSON: {"message": "..."}
# =========================================================

@app.route(
    "/support/employee/send/<int:conversation_id>",
    methods=["POST"]
)
def support_employee_send(conversation_id):
    if not employee_is_logged_in():
        return jsonify({
            "success": False,
            "message": "Active employee login required."
        }), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "message": "Invalid message request."
        }), 400

    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({
            "success": False,
            "message": "Please enter a message."
        }), 400

    if len(message) > 2000:
        return jsonify({
            "success": False,
            "message": "Messages must be 2,000 characters or fewer."
        }), 400

    connection = get_db()

    conversation = connection.execute("""
        SELECT * FROM support_conversations WHERE id = ?
    """, (conversation_id,)).fetchone()

    if conversation is None:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Support conversation not found."
        }), 404

    employee_id = session["employee_id"]

    if conversation["status"] == "Resolved":
        connection.close()
        return jsonify({
            "success": False,
            "message": "This conversation has been resolved."
        }), 409

    if conversation["assigned_employee_id"] != employee_id:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Accept this conversation before replying."
        }), 403

    connection.execute("""
        INSERT INTO support_messages (
            conversation_id, sender_type, sender_employee_id, message
        )
        VALUES (?, 'employee', ?, ?)
    """, (conversation_id, employee_id, message))

    connection.execute("""
        UPDATE support_conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (conversation_id,))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Reply sent."
    })


# =========================================================
# LIVE AGENT: RESOLVE A CHAT
# POST /support/employee/resolve/<conversation_id>
# =========================================================

@app.route(
    "/support/employee/resolve/<int:conversation_id>",
    methods=["POST"]
)
def support_employee_resolve(conversation_id):
    if not employee_is_logged_in():
        return jsonify({
            "success": False,
            "message": "Active employee login required."
        }), 401

    connection = get_db()

    conversation = connection.execute("""
        SELECT * FROM support_conversations WHERE id = ?
    """, (conversation_id,)).fetchone()

    if conversation is None:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Support conversation not found."
        }), 404

    employee_id = session["employee_id"]
    role = session.get("employee_role")

    if conversation["status"] == "Resolved":
        connection.close()
        return jsonify({
            "success": True,
            "message": "This conversation is already resolved."
        })

    if (
        conversation["assigned_employee_id"] != employee_id
        and role not in ("Supervisor", "Admin")
    ):
        connection.close()
        return jsonify({
            "success": False,
            "message": "Only the assigned employee or a supervisor/admin can resolve this conversation."
        }), 403

    connection.execute("""
        UPDATE support_conversations
        SET status = 'Resolved',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (conversation_id,))

    connection.execute("""
        INSERT INTO support_messages (
            conversation_id, sender_type, sender_employee_id, message
        )
        VALUES (?, 'system', ?, ?)
    """, (
        conversation_id,
        employee_id,
        "This support conversation has been marked as resolved."
    ))

    connection.commit()
    connection.close()

    log_activity(
        "Support Conversation Resolved",
        f"Resolved support conversation ID {conversation_id}."
    )

    return jsonify({
        "success": True,
        "message": "Conversation resolved."
    })


# =========================================================
# RUN ANGEL
# =========================================================

if __name__ == "__main__":
    create_database()
    app.run(host="0.0.0.0", port=5000, debug=False)
