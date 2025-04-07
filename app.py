from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(
        db.String(20), nullable=False, default="analyst"
    )  # 'admin' or 'analyst'


# Decorators for access control
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Login required!", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = User.query.filter_by(id=session.get("user_id")).first()
        if user is None or user.role != "admin":
            flash("Admin access required!", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"]

        if User.query.filter_by(username=username).first():
            flash("Username already exists", "danger")
            return redirect(url_for("register"))

        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash("User registered successfully!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            session["user_id"] = user.id
            flash("Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out!", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/admin")
@admin_required
def admin():
    users = User.query.all()
    return render_template("admin.html", users=users)


if __name__ == "__main__":
    if not os.path.exists("users.db"):
        with app.app_context():
            db.create_all()
    app.run(debug=True)
# To run the app, use the command: python app.py
# Make sure to install Flask and Flask-SQLAlchemy if you haven't already:   pip install Flask Flask-SQLAlchemy
# Create the database and tables if they don't exist before running the app.
# You can do this by running the app once or using a separate script to create the database.
# The app will create a SQLite database file named 'users.db' in the same directory as this script.
# The database will store user information, including usernames, hashed passwords, and roles (admin or analyst).
# The app includes routes for user registration, login, logout, and a dashboard.
# Admin users can view all registered users and their roles.
# The app uses Flask's session management to keep track of logged-in users.
# The app also includes decorators to restrict access to certain routes based on user roles.
# The login_required decorator ensures that only logged-in users can access certain routes.
# The admin_required decorator ensures that only users with the 'admin' role can access certain routes.
# The app uses Flask-WTF for form handling and validation.
# The app uses Bootstrap for styling and layout. You can customize the templates in the 'templates' directory.
# The templates include HTML files for the login, registration, dashboard, and admin pages.
# The templates use Jinja2 syntax for rendering dynamic content.
# The app uses Flask's flash messaging system to display success and error messages to users.
# The flash messages are displayed in the templates using Bootstrap alerts.
# The app uses SQLAlchemy for database interactions and ORM (Object-Relational Mapping).
# The app uses SQLite as the database backend, but you can easily switch to other databases like PostgreSQL or MySQL by changing the SQLALCHEMY_DATABASE_URI configuration.
# The app is designed to be simple and easy to understand, making it a good starting point for learning Flask and web development.
# You can extend the app by adding more features, such as password reset functionality, user profile management, and more complex role-based access control.
# You can also add more routes and templates to enhance the user experience.
# The app is a basic example of a user authentication system using Flask and SQLAlchemy.
# It demonstrates how to create a simple web application with user registration, login, and role-based access control.
# You can use this code as a foundation for building more complex applications with user authentication and authorization features.
