from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import mysql.connector
from datetime import datetime
import logging
import os
import random  # Add this for coin data generation

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MySQL Configuration
db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'Muthu@200630'),
    'database': os.environ.get('DB_NAME', 'expense_tracker'),
    'auth_plugin': 'mysql_native_password'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        logger.info("Database connection successful")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Database connection failed: {err}")
        flash('Database connection error', 'danger')
        return None

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_template_vars():
    return {
        'datetime': datetime,
        'current_user': {'is_authenticated': 'user_id' in session}
    }

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    flash('Login successful!', 'success')
                    return redirect(url_for('view_expenses'))
                else:
                    flash('Invalid email or password', 'danger')
            except mysql.connector.Error as err:
                logger.error(f"Login error: {err}")
                flash('Login failed. Please try again.', 'danger')
            finally:
                cursor.close()
                conn.close()
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('Email already registered', 'danger')
                    return redirect(url_for('register'))
                
                hashed_pw = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                    (username, email, hashed_pw)
                )
                conn.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            except mysql.connector.Error as err:
                conn.rollback()
                logger.error(f"Registration error: {err}")
                flash('Registration failed. Please try again.', 'danger')
            finally:
                cursor.close()
                conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# Expense Routes
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('view_expenses'))
    return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])
        except ValueError:
            flash('Invalid amount entered', 'danger')
            return redirect(url_for('add_expense'))
            
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        expense_date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        if not amount or not category:
            flash('Amount and Category are required fields', 'danger')
            return redirect(url_for('add_expense'))
        
        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('add_expense'))
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO expenses (user_id, amount, category, description, expense_date) VALUES (%s, %s, %s, %s, %s)",
                (session['user_id'], amount, category, description, expense_date)
            )
            cursor.execute("INSERT IGNORE INTO categories (name) VALUES (%s)", (category,))
            conn.commit()
            flash('Expense added successfully!', 'success')
            return redirect(url_for('view_expenses'))
        except mysql.connector.Error as err:
            conn.rollback()
            logger.error(f"Expense add error: {err}")
            flash('Error saving expense. Please try again.', 'danger')
            return redirect(url_for('add_expense'))
        finally:
            cursor.close()
            conn.close()
    
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('add_expense.html', today=today)

@app.route('/view')
@login_required
def view_expenses():
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('home'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, amount, category, description, 
                   DATE_FORMAT(expense_date, '%Y-%m-%d') as formatted_date
            FROM expenses 
            WHERE user_id = %s
            ORDER BY expense_date DESC
        """, (session['user_id'],))
        expenses = cursor.fetchall()
        
        cursor.execute("SELECT SUM(amount) as total FROM expenses WHERE user_id = %s", (session['user_id'],))
        total = cursor.fetchone()['total'] or 0
        
        return render_template('view_expenses.html', 
                             expenses=expenses, 
                             total=total,
                             current_page='view_expenses')
    except mysql.connector.Error as err:
        logger.error(f"View expenses error: {err}")
        flash('Error loading expenses', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

@app.route('/summary')
@login_required
def monthly_summary():
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('home'))
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT SUM(amount) as total 
            FROM expenses 
            WHERE user_id = %s AND DATE_FORMAT(expense_date, '%Y-%m') = %s
        """, (session['user_id'], month))
        total = cursor.fetchone()['total'] or 0
        
        cursor.execute("""
            SELECT category, SUM(amount) as category_total 
            FROM expenses 
            WHERE user_id = %s AND DATE_FORMAT(expense_date, '%Y-%m') = %s
            GROUP BY category
            ORDER BY category_total DESC
        """, (session['user_id'], month))
        categories = cursor.fetchall()
        
        cursor.execute("""
            SELECT DISTINCT DATE_FORMAT(expense_date, '%Y-%m') as month 
            FROM expenses 
            WHERE user_id = %s
            ORDER BY month DESC
        """, (session['user_id'],))
        available_months = [m['month'] for m in cursor.fetchall()]
        
        return render_template('monthly_summary.html',
                            month=month,
                            total=total,
                            categories=categories,
                            available_months=available_months,
                            current_page='monthly_summary')
    except mysql.connector.Error as err:
        logger.error(f"Monthly summary error: {err}")
        flash('Error generating summary', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

# Add new route for profile settings
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                # Check if email exists
                cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", 
                               (new_email, session['user_id']))
                if cursor.fetchone():
                    flash('Email already in use', 'danger')
                    return redirect(url_for('profile'))
                
                # Update profile
                cursor.execute(
                    "UPDATE users SET username = %s, email = %s WHERE id = %s",
                    (new_username, new_email, session['user_id'])  # Ensure this parenthesis is closed
                )
                conn.commit()
                session['username'] = new_username
                flash('Profile updated!', 'success')
            except mysql.connector.Error as err:
                conn.rollback()
                flash(f'Error updating profile: {err}', 'danger')  # Handle the exception
            finally:
                cursor.close()  # Ensure the cursor is closed
                conn.close()  # Ensure the connection is closed
            
        return redirect(url_for('profile'))
    
    # Handle GET request
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT username, email FROM users WHERE id = %s", 
                           (session['user_id'],))
            user = cursor.fetchone()
            return render_template('profile.html', user=user)
        except mysql.connector.Error as err:
            flash(f'Error loading profile: {err}', 'danger')
            return redirect(url_for('home'))
        finally:
            cursor.close()
            conn.close()
if __name__ == '__main__':
    app.run(debug=True)
app.run(debug=True, port=8000)
