from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os, re, time, csv, sqlite3, threading
import sys
import signal
import spidev

# Import RPi servo controller
from rpi_servo import get_servo_controller, cleanup_servo_controller

# Import TTS manager
try:
    from text_to_speech import speak, TTS_AVAILABLE, engine, test_speech, test_audio_system
    print("✓ TTS manager imported successfully")
except Exception as e:
    print(f"TTS manager import failed: {e}")
    TTS_AVAILABLE = False
    engine = None

from weblookup import fetch_intake_instructions

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback_secret_key')

DATABASE = 'users.db'

servo_controller = get_servo_controller()  # Create a single instance

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\nReceived signal {signum}. Shutting down gracefully...")
    cleanup_servo_controller(servo_controller)
    sys.exit(0)

def verify_password(stored_password, provided_password):
    """Verify password with fallback support for different hashing methods"""
    print(f"Verifying password for stored hash: {stored_password[:20]}...")
    
    # First, try simple SHA256 hash comparison (since we know our passwords are stored this way)
    try:
        import hashlib
        hashed_provided = hashlib.sha256(provided_password.encode()).hexdigest()
        result = stored_password == hashed_provided
        print(f"SHA256 verification result: {result}")
        if result:
            return True
    except Exception as e:
        print(f"Error with SHA256 password check: {e}")
    
    # Fallback to werkzeug's check_password_hash for legacy passwords
    try:
        result = check_password_hash(stored_password, provided_password)
        print(f"Werkzeug verification result: {result}")
        return result
    except Exception as e:
        print(f"Error with werkzeug password check: {e}")
        return False

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Create users table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        is_admin BOOLEAN DEFAULT 0
    )
    ''')

    # Create tray_settings table with the new schema
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tray_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        user_id INTEGER NOT NULL,
        tray_number INTEGER NOT NULL,
        description TEXT NOT NULL,
        alert BOOLEAN,
        dispense_time DATETIME,
        interval TEXT,
        color TEXT,
        dispense_count INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')

    # Add name column to tray_settings if it doesn't exist
    try:
        cursor.execute('ALTER TABLE tray_settings ADD COLUMN name TEXT')
        print("Added name column to tray_settings table")
    except sqlite3.OperationalError:
        # Column already exists, ignore error
        pass

    # Add is_admin column to users if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0')
        print("Added is_admin column to users table")
    except sqlite3.OperationalError:
        # Column already exists, ignore error
        pass

    # Safely add dispense_count column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE tray_settings ADD COLUMN dispense_count INTEGER DEFAULT 0')
        print("Added dispense_count column to tray_settings table")
    except sqlite3.OperationalError:
        # Column already exists, ignore error
        pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS medicine (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generic_name TEXT,
        brand_name TEXT,
        dosage_strength TEXT,
        dosage_form TEXT,
        classification TEXT,
        pharmacologic_category TEXT,
        manufacturer TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dispense_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        tray_number INTEGER,
        medicine_description TEXT,
        dispense_time TEXT
    )
    ''')

    # Create admin account if it doesn't exist
    admin_username = 'admin'
    cursor.execute('SELECT * FROM users WHERE username = ?', (admin_username,))
    admin_exists = cursor.fetchone()
    
    if not admin_exists:
        try:
            admin_password = generate_password_hash('admin123', method='sha256')  # Use sha256 for compatibility
            cursor.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)', 
                          (admin_username, admin_password, 1))
            print("Created admin account with username: admin, password: admin123")
        except Exception as e:
            print(f"Error creating admin account: {e}")
            # Fallback to simple hash if needed
            import hashlib
            admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
            cursor.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)', 
                          (admin_username, admin_password, 1))
            print("Created admin account with fallback hashing")

    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect(DATABASE)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()
    cursor.execute(query, args)
    rv = cursor.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def migrate_passwords():
    """Migrate existing passwords to compatible format if needed"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, password FROM users')
        users = cursor.fetchall()
        
        for user_id, password in users:
            # Check if password is already in simple hash format
            if len(password) == 64 and all(c in '0123456789abcdef' for c in password.lower()):
                # Already in SHA256 format, skip
                continue
            
            # Try to verify with werkzeug to see if it's a valid hash
            try:
                # Test with a dummy password to see if the hash format is valid
                check_password_hash(password, 'dummy')
                # If no exception, the hash format is valid, skip migration
                continue
            except Exception:
                # Hash format is not compatible, migrate to simple SHA256
                print(f"Migrating password for user ID {user_id}")
                # We can't recover the original password, so we'll set a default
                # In a real scenario, you'd want to force password reset
                import hashlib
                new_password = hashlib.sha256('changeme123'.encode()).hexdigest()
                cursor.execute('UPDATE users SET password = ? WHERE id = ?', (new_password, user_id))
        
        conn.commit()
        conn.close()
        print("Password migration completed")
    except Exception as e:
        print(f"Error during password migration: {e}")

init_db()
migrate_passwords()

default_tray_settings = [
    {"number": 1, "description": "No Medicine", "alert": False, "time": "", "color": ""},
    {"number": 2, "description": "No Medicine", "alert": False, "time": "", "color": ""}
]

default_system_settings = {
    "trays_installed": 2,
    "reset_time": "06:00",
    "clock_screensaver": False,
    "volume": 100,
    "mute": False,
    "dst": False,
    "utc_offset": "+00:00",
}

# Import medicine web lookup
try:
    from weblookup import test_mims, test_all_sources
    print("✓ Medicine weblookup imported successfully")
except Exception as e:
    print(f"Medicine weblookup import failed: {e}")

@app.route('/')
def homepage():
    return redirect(url_for('login'))

def get_tray_status_and_countdown():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ts.tray_number, ts.description, ts.dispense_time, ts.dispense_count, 
               ts.name, u.username 
        FROM tray_settings ts 
        LEFT JOIN users u ON ts.user_id = u.id
    ''')
    trays = cursor.fetchall()
    conn.close()
    status = []
    now = datetime.now()
    for tray in trays:
        tray_number, description, dispense_time, dispense_count, name, username = tray
        # Use name if available, otherwise fall back to username
        display_name = name if name else username if username else "Unknown"
        
        if dispense_time:
            try:
                dt = datetime.strptime(dispense_time, "%Y-%m-%dT%H:%M")
                countdown = int((dt - now).total_seconds())
                countdown = countdown if countdown > 0 else 0
                next_dispense = dt.strftime("%B %d, %Y, %I:%M %p")
            except Exception:
                countdown = None
                next_dispense = dispense_time
        else:
            countdown = None
            next_dispense = "N/A"
        status.append({
            'tray_number': tray_number,
            'description': description,
            'next_dispense': next_dispense,
            'countdown': countdown,
            'dispense_count': dispense_count,
            'username': display_name
        })
    return status

@app.route('/login', methods=['GET', 'POST'])
def login():
    tray_status = get_tray_status_and_countdown()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query_db('SELECT * FROM users WHERE username = ?', (username,), one=True)
        if user and verify_password(user[2], password):  
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[3] if len(user) > 3 else False
            flash('Welcome, you have successfully logged in', 'success')
            # Redirect admin users directly to admin dashboard
            if user[3] if len(user) > 3 else False:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Invalid Username or Password', 'danger')
    return render_template('login.html', tray_status=tray_status)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query_db('SELECT * FROM users WHERE username = ?', (username,), one=True)
        if user:
            flash('Username already exists', 'danger')
        else:
            try:
                hashed_password = generate_password_hash(password, method='sha256')
                query_db('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                print(f"Error hashing password: {e}")
                # Fallback to simple hash if needed
                import hashlib
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                query_db('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))

    return render_template('register.html')

def insert_tray_settings(user_id, tray_number, description, dispense_time, interval, color, name=None):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Get username if name is not provided
    if not name:
        cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        user_result = cursor.fetchone()
        name = user_result[0] if user_result else "Unknown"
    
    cursor.execute('''
    INSERT INTO tray_settings (user_id, tray_number, description, dispense_time, interval, color, name)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, tray_number, description, dispense_time, interval, color, name))
    
    conn.commit()
    conn.close()

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    tray_status = get_tray_status_and_countdown()
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Fetch recent dispense history (last 10 for this user)
    cursor.execute('SELECT username, tray_number, medicine_description, dispense_time FROM dispense_history WHERE user_id = ? ORDER BY dispense_time DESC LIMIT 10', (user_id,))
    dispense_history = cursor.fetchall()
    conn.close()

    # Filter tray_status for this user only (if user_id is stored in tray_settings, otherwise show all)
    # If you want to show only trays for this user, you can filter here if needed.

    return render_template('dashboard.html', tray_status=tray_status, dispense_history=dispense_history, is_admin=is_admin)

@app.route('/medicine_select', methods=['GET', 'POST'])
def medicine_select():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    medicines = []
    message = ''
    if request.method == 'POST':
        search_input = request.form.get('searchInput', '').strip().lower()
        if not search_input:
            message = 'Please enter a valid search query.'
        else:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM medicine
                WHERE LOWER(brand_name) LIKE ?
            ''', (f'%{search_input}%',))
            results = cursor.fetchall()
            conn.close()
            medicines = [
                {
                    'Generic Name': row[1],
                    'Brand Name': row[2],
                    'Dosage Strength': row[3],
                    'Dosage Form': row[4],
                    'Classification': row[5],
                    'Pharmacologic Category': row[6],
                    'Manufacturer': row[7]
                }
                for row in results
            ]
            if not medicines:
                message = 'No results found. Try searching for another Medicine Brand Name.'
    is_admin = session.get('is_admin', False)
    return render_template('medicine_select.html', medicines=medicines, message=message, is_admin=is_admin)

@app.route('/tray_setup', methods=['GET', 'POST'])
def tray_setup():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    tray_status = get_tray_status_and_countdown()
    # Get description from GET params if available
    description = request.args.get('description', '')
    
    # Get user's trays for reset options
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # If admin, show all trays, otherwise show only user's trays
    if is_admin:
        cursor.execute('SELECT tray_number, description, dispense_count, name FROM tray_settings')
        user_trays = cursor.fetchall()
    else:
        cursor.execute('SELECT tray_number, description, dispense_count, name FROM tray_settings WHERE user_id = ?', (user_id,))
        user_trays = cursor.fetchall()
    conn.close()
    
    if request.method == 'POST':
        user_id = session['user_id']
        tray_number = int(request.form['tray_number'])
        
        # Check if tray is already occupied
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tray_settings WHERE tray_number = ?', (tray_number,))
        existing = cursor.fetchone()
        
        if existing:
            existing_user_id = existing[2]  # user_id is now at index 2 due to new schema
            if existing_user_id != user_id and not is_admin:
                conn.close()
                flash('This tray is already assigned to another user. You cannot modify it.', 'danger')
                return render_template('tray_setup.html', tray_status=tray_status, description=description, user_trays=user_trays, is_admin=is_admin)
            else:
                conn.close()
                flash('This tray is already occupied. Please reset the tray before making changes.', 'danger')
                return render_template('tray_setup.html', tray_status=tray_status, description=description, user_trays=user_trays, is_admin=is_admin)
        conn.close()
        
        description = request.form['description']
        alert = request.form.get('alert') == 'yes'
        dispense_time = request.form['time']
        interval = request.form['interval']
        color = request.form['color']
        
        # Get username for the name field
        username = session.get('username', 'Unknown')
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tray_settings WHERE user_id = ?', (user_id,))
        existing_tray_setting = cursor.fetchone()

        if existing_tray_setting:
            cursor.execute('''
            UPDATE tray_settings
            SET tray_number = ?, description = ?, alert = ?, dispense_time = ?, interval = ?, color = ?, name = ?
            WHERE user_id = ?
            ''', (tray_number, description, alert, dispense_time, interval, color, username, user_id))
            conn.commit()
            flash('Tray settings updated successfully!', 'success')
        else:
            try:
                cursor.execute('''
                INSERT INTO tray_settings (user_id, tray_number, description, alert, dispense_time, interval, color, name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, tray_number, description, alert, dispense_time, interval, color, username))
                conn.commit()
                flash('Tray settings saved successfully!', 'success')
            except sqlite3.IntegrityError:
                flash('This tray is already assigned to another user.', 'danger')

        conn.close()

        return render_template('tray_setup.html', tray_status=tray_status, description=description, user_trays=user_trays, is_admin=is_admin)

    # For GET, pass description if available
    return render_template('tray_setup.html', tray_status=tray_status, description=description, user_trays=user_trays, is_admin=is_admin)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('homepage'))

@app.route("/search", methods=["POST"])
def search_result():
    search_input = request.form['searchInput'].strip().lower()
    if not search_input:
        return render_template("medicine.html", medicines=[], message="Please enter a valid search query.")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM medicine
    WHERE LOWER(brand_name) LIKE ?
    ''', (f'%{search_input}%',))
    results = cursor.fetchall()
    conn.close()

    medicines = [
        {
            "Generic Name": row[1],
            "Brand Name": row[2],
            "Dosage Strength": row[3],
            "Dosage Form": row[4],
            "Classification": row[5],
            "Pharmacologic Category": row[6],
            "Manufacturer": row[7]
        }
        for row in results
    ]

    if medicines:
        return render_template("medicine.html", medicines=medicines)
    else:
        return render_template("medicine.html", medicines=[], message="No results found. Try searching for another Medicine Brand Name.")

@app.route("/dispense", methods=["POST", "GET"])
def dispense():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)

    if user:
        username = user[1]
    else:
        username = "Guest"

    medicine_description = request.form.get('description', "No Medicine Selected")
    tray_number = request.form.get('tray_number', None)
    # Log dispense event
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO dispense_history (user_id, username, tray_number, medicine_description, dispense_time) VALUES (?, ?, ?, ?, ?)',
                   (user_id, username, tray_number, medicine_description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return render_template('dispense.html', username=username, medicine_description=medicine_description)

@app.route('/save_dispense_settings', methods=['POST'])
def save_dispense_settings():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    tray_number = int(request.form['tray_number'])
    description = request.form['description']
    alert = request.form.get('alert') == 'yes'
    dispense_time = request.form['time']
    interval = request.form['interval']
    color = request.form['color']
    username = session.get('username', 'Unknown')
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Check if tray_number is already assigned
    cursor.execute('SELECT * FROM tray_settings WHERE tray_number = ?', (tray_number,))
    existing = cursor.fetchone()
    
    if existing:
        existing_user_id = existing[2]  # user_id is now at index 2 due to new schema
        if existing_user_id != user_id and not is_admin:
            conn.close()
            flash('This tray is already assigned to another user. You cannot modify it.', 'danger')
            return redirect(url_for('tray_setup'))
        # Update the existing tray for this user
        cursor.execute('''
        UPDATE tray_settings
        SET description = ?, alert = ?, dispense_time = ?, interval = ?, color = ?, name = ?
        WHERE tray_number = ?
        ''', (description, alert, dispense_time, interval, color, username, tray_number))
        conn.commit()
        flash('Tray settings updated successfully!', 'success')
    else:
        try:
            cursor.execute('''
            INSERT INTO tray_settings (user_id, tray_number, description, alert, dispense_time, interval, color, name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, tray_number, description, alert, dispense_time, interval, color, username))
            conn.commit()
            flash('Tray settings saved successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('This tray is already assigned to another user.', 'danger')
    conn.close()
    
    return redirect(url_for('dashboard'))

# Servo control functions are now handled by servo_controller.py

def move_tray_1(medicine_name, tray_id):
    print("Moving Tray 1")
    # Check dispense count first
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT dispense_count FROM tray_settings WHERE id = ?', (tray_id,))
    result = cursor.fetchone()
    if result:
        dispense_count = result[0]
        if dispense_count >= 30:
            speak(f"All medicine has been dispensed from Tray 1. {medicine_name}. Please refill the tray.")
            conn.close()
            return False
        
        # Increment dispense count
        cursor.execute('UPDATE tray_settings SET dispense_count = ? WHERE id = ?', (dispense_count + 1, tray_id))
        conn.commit()
        conn.close()
        
        # Use persistent servo controller to dispense
        if servo_controller:
            servo_controller.dispense_from_tray_1(medicine_name)
        
        instructions = fetch_intake_instructions(medicine_name)
        speak(f"Medicine dispensed from Tray 1. {medicine_name}. Instructions: {instructions}")
        
        return True
    conn.close()
    return False

def move_tray_2(medicine_name, tray_id):
    print("Moving Tray 2")
    # Check dispense count first
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT dispense_count FROM tray_settings WHERE id = ?', (tray_id,))
    result = cursor.fetchone()
    if result:
        dispense_count = result[0]
        if dispense_count >= 30:
            speak(f"All medicine has been dispensed from Tray 2. {medicine_name}. Please refill the tray.")
            conn.close()
            return False
        
        # Increment dispense count
        cursor.execute('UPDATE tray_settings SET dispense_count = ? WHERE id = ?', (dispense_count + 1, tray_id))
        conn.commit()
        conn.close()
        
        # Use persistent servo controller to dispense
        if servo_controller:
            servo_controller.dispense_from_tray_2(medicine_name)
        
        instructions = fetch_intake_instructions(medicine_name)
        speak(f"Medicine dispensed from Tray 2. {medicine_name}. Instructions: {instructions}")
        
        return True
    conn.close()
    return False

def get_tray():
    count = 0
    while True:
        if count > 3:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tray_settings")
            results = cursor.fetchall()
            conn.close()
            count = 0  # Reset count after fetching new data

            # Collect trays due for dispensing
            trays_due = []
            now = datetime.now()
            for row in results:
                try:
                    # Check if dispense_time exists and is a string
                    if row[6] is None or not isinstance(row[6], str):
                        continue
                    # Convert row[6] (dispense_time) to datetime
                    row_time = datetime.strptime(row[6], "%Y-%m-%dT%H:%M")
                    if row_time < now:
                        trays_due.append(row)
                except Exception as e:
                    print(f"Error processing row for due check: {row}, Error: {e}")

            # Sort trays by tray_number (row[3])
            trays_due.sort(key=lambda r: r[3])

            # Dispense trays one at a time, in order
            for row in trays_due:
                try:
                    # Extract interval from row[7] (interval column)
                    interval_str = row[7] if row[7] else "1"
                    interv = int(re.search(r'\d+', interval_str).group()) if re.search(r'\d+', interval_str) else 1
                    row_time = datetime.strptime(row[6], "%Y-%m-%dT%H:%M")
                    updated_time = row_time + timedelta(hours=interv)
                    updated_time_str = updated_time.strftime("%Y-%m-%dT%H:%M")

                    print(f"Updating dispense_time for ID {row[0]} to {updated_time_str}")

                    # Update database
                    conn = sqlite3.connect(DATABASE)
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE tray_settings
                        SET dispense_time = ?
                        WHERE id = ?
                    ''', (updated_time_str, row[0]))
                    conn.commit()

                    # Dispense in order
                    tray_number = row[3]  # tray_number is at index 3
                    description = row[4]  # description is at index 4
                    if tray_number == 1:
                        move_tray_1(description, row[0])
                    elif tray_number == 2:
                        move_tray_2(description, row[0])
                    # Add more elifs for more trays if needed
                    conn.close()
                except Exception as e:
                    print(f"Error processing row: {row}, Error: {e}")
                # Wait a short time before next tray to ensure sequential operation
                time.sleep(5)

        count += 1
        time.sleep(2)

thread = threading.Thread(target=get_tray, daemon=True)
thread.start()


@app.route('/reset_tray', methods=['POST'])
def reset_tray():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    tray_number = int(request.form['tray_number'])
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tray_settings WHERE tray_number = ?', (tray_number,))
    existing = cursor.fetchone()
    
    if not existing:
        conn.close()
        flash('Tray does not exist or is already reset.', 'warning')
        return redirect(url_for('tray_setup'))
    
    existing_user_id = existing[2]  # user_id is now at index 2 due to new schema
    
    if existing_user_id != user_id and not is_admin:
        conn.close()
        flash('You cannot reset a tray assigned to another user.', 'danger')
        return redirect(url_for('tray_setup'))
    
    cursor.execute('DELETE FROM tray_settings WHERE tray_number = ?', (tray_number,))
    conn.commit()
    conn.close()
    flash(f'Tray {tray_number} has been reset.', 'success')
    return redirect(url_for('tray_setup'))

@app.route('/reset_dispense_count', methods=['POST'])
def reset_dispense_count():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    is_admin = session.get('is_admin', False)
    tray_number = int(request.form['tray_number'])
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tray_settings WHERE tray_number = ?', (tray_number,))
    existing = cursor.fetchone()
    
    if not existing:
        conn.close()
        flash('Tray does not exist.', 'warning')
        return redirect(url_for('tray_setup'))
    
    existing_user_id = existing[2]  # user_id is now at index 2 due to new schema
    
    if existing_user_id != user_id and not is_admin:
        conn.close()
        flash('You cannot reset dispense count for a tray assigned to another user.', 'danger')
        return redirect(url_for('tray_setup'))
    
    cursor.execute('UPDATE tray_settings SET dispense_count = 0 WHERE tray_number = ?', (tray_number,))
    conn.commit()
    conn.close()
    flash(f'Dispense count for Tray {tray_number} has been reset to 0.', 'success')
    return redirect(url_for('tray_setup'))

@app.route('/admin_delete_tray', methods=['POST'])
def admin_delete_tray():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    is_admin = session.get('is_admin', False)
    if not is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    tray_number = int(request.form['tray_number'])
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tray_settings WHERE tray_number = ?', (tray_number,))
    conn.commit()
    conn.close()
    
    flash(f'Tray {tray_number} has been deleted by admin.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    is_admin = session.get('is_admin', False)
    if not is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Get statistics
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_admin = 0')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM tray_settings')
    total_trays = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM medicine')
    total_medicines = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM dispense_history WHERE date(dispense_time) = date("now")')
    today_dispenses = cursor.fetchone()[0]
    
    # Get all users with their tray counts
    cursor.execute('''
        SELECT u.username, u.id, 
               (SELECT COUNT(*) FROM tray_settings ts WHERE ts.user_id = u.id) as active_trays
        FROM users u 
        WHERE u.is_admin = 0
        ORDER BY u.username
    ''')
    users_data = cursor.fetchall()
    
    users = []
    for user_data in users_data:
        users.append({
            'username': user_data[0],
            'id': user_data[1],
            'active_trays': user_data[2],
            'registration_date': 'N/A'  # Could add registration date column if needed
        })
    
    # Get all trays with user information
    cursor.execute('''
        SELECT ts.id, ts.tray_number, u.username, ts.description, ts.dispense_time, ts.dispense_count
        FROM tray_settings ts
        JOIN users u ON ts.user_id = u.id
        ORDER BY ts.tray_number
    ''')
    trays_data = cursor.fetchall()
    
    trays = []
    for tray_data in trays_data:
        trays.append({
            'id': tray_data[0],
            'tray_number': tray_data[1],
            'username': tray_data[2],
            'description': tray_data[3],
            'next_dispense': tray_data[4] if tray_data[4] else 'Not set',
            'dispense_count': tray_data[5]
        })
    
    # Get all medicines
    cursor.execute('SELECT id, generic_name, brand_name FROM medicine ORDER BY generic_name')
    medicines_data = cursor.fetchall()
    
    medicines = []
    for medicine_data in medicines_data:
        medicines.append({
            'id': medicine_data[0],
            'generic_name': medicine_data[1],
            'brand_name': medicine_data[2]
        })
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         total_users=total_users,
                         total_trays=total_trays,
                         total_medicines=total_medicines,
                         today_dispenses=today_dispenses,
                         users=users,
                         trays=trays,
                         medicines=medicines)

@app.route('/admin_add_user', methods=['POST'])
def admin_add_user():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    is_admin = session.get('is_admin', False)
    if not is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    is_admin_user = request.form.get('is_admin') == '1'
    
    if not username or not password:
        flash('Username and password are required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        import hashlib
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)', 
                      (username, hashed_password, is_admin_user))
        conn.commit()
        conn.close()
        
        flash(f'User {username} has been created successfully.', 'success')
    except sqlite3.IntegrityError:
        flash(f'Username {username} already exists.', 'danger')
    except Exception as e:
        flash(f'Error creating user: {e}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_delete_user', methods=['POST'])
def admin_delete_user():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    is_admin = session.get('is_admin', False)
    if not is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    username = request.form.get('username', '').strip()
    
    if not username:
        flash('Username is required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if username == 'admin':
        flash('Cannot delete the admin account.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Get user ID
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user_result = cursor.fetchone()
        
        if not user_result:
            flash(f'User {username} not found.', 'warning')
            return redirect(url_for('admin_dashboard'))
        
        user_id = user_result[0]
        
        # Delete user's trays first
        cursor.execute('DELETE FROM tray_settings WHERE user_id = ?', (user_id,))
        
        # Delete user
        cursor.execute('DELETE FROM users WHERE username = ?', (username,))
        
        conn.commit()
        conn.close()
        
        flash(f'User {username} and all associated trays have been deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting user: {e}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_edit_medicine', methods=['POST'])
def admin_edit_medicine():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    is_admin = session.get('is_admin', False)
    if not is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    medicine_id = request.form.get('medicine_id')
    generic_name = request.form.get('generic_name', '').strip()
    brand_name = request.form.get('brand_name', '').strip()
    dosage_strength = request.form.get('dosage_strength', '').strip()
    
    if not medicine_id or not generic_name or not brand_name:
        flash('Medicine ID, generic name, and brand name are required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE medicine 
            SET generic_name = ?, brand_name = ?, dosage_strength = ?
            WHERE id = ?
        ''', (generic_name, brand_name, dosage_strength, medicine_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash('Medicine updated successfully.', 'success')
        else:
            flash('Medicine not found.', 'warning')
        
        conn.close()
    except Exception as e:
        flash(f'Error updating medicine: {e}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_edit_dispense_time', methods=['POST'])
def admin_edit_dispense_time():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    is_admin = session.get('is_admin', False)
    if not is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    tray_id = request.form.get('tray_id')
    dispense_time = request.form.get('dispense_time')
    interval = request.form.get('interval', '12')
    
    if not tray_id or not dispense_time:
        flash('Tray ID and dispense time are required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tray_settings 
            SET dispense_time = ?, interval = ?
            WHERE id = ?
        ''', (dispense_time, interval, tray_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash('Dispense time updated successfully.', 'success')
        else:
            flash('Tray not found.', 'warning')
        
        conn.close()
    except Exception as e:
        flash(f'Error updating dispense time: {e}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_reset_all_dispenses', methods=['POST'])
def admin_reset_all_dispenses():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    is_admin = session.get('is_admin', False)
    if not is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('UPDATE tray_settings SET dispense_count = 0')
        conn.commit()
        conn.close()
        
        flash('All dispense counts have been reset to 0.', 'success')
    except Exception as e:
        flash(f'Error resetting dispense counts: {e}', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_reset_password', methods=['POST'])
def admin_reset_password():
    if 'user_id' not in session:
        flash('Please log in to access this page.', 'danger')
        return redirect(url_for('login'))
    
    is_admin = session.get('is_admin', False)
    if not is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    username = request.form.get('username', '')
    if not username:
        flash('Username is required.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        import hashlib
        new_password = hashlib.sha256('1234'.encode()).hexdigest()
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password = ? WHERE username = ?', (new_password, username))
        
        if cursor.rowcount > 0:
            conn.commit()
            flash(f'Password for user {username} has been reset to "1234".', 'success')
        else:
            flash(f'User {username} not found.', 'warning')
        
        conn.close()
    except Exception as e:
        flash(f'Error resetting password: {e}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/emergency_reset_admin', methods=['GET', 'POST'])
def emergency_reset_admin():
    """Emergency route to reset admin password - use only if locked out"""
    if request.method == 'POST':
        try:
            import hashlib
            new_password = hashlib.sha256('admin123'.encode()).hexdigest()
            
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password = ? WHERE username = ?', (new_password, 'admin'))
            
            if cursor.rowcount > 0:
                conn.commit()
                flash('Admin password has been reset to "admin123".', 'success')
            else:
                # Create admin account if it doesn't exist
                cursor.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)', 
                              ('admin', new_password, 1))
                conn.commit()
                flash('Admin account created with password "admin123".', 'success')
            
            conn.close()
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error resetting admin password: {e}', 'danger')
    
    return render_template('emergency_reset.html')

@app.route('/debug_password/<username>')
def debug_password(username):
    """Debug route to check password hash format - remove in production"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            password_hash = result[0]
            return {
                'username': username,
                'hash_length': len(password_hash),
                'hash_start': password_hash[:20] + '...',
                'is_hex': all(c in '0123456789abcdef' for c in password_hash.lower()),
                'hash_type': 'werkzeug' if password_hash.startswith('pbkdf2:') else 'simple_sha256'
            }
        else:
            return {'error': 'User not found'}
    except Exception as e:
        return {'error': str(e)}

@app.route('/test_speech')
def test_speech():
    """Test route to enable and test speech functionality"""
    try:
        from text_to_speech import test_speech as tts_test
        return tts_test()
    except Exception as e:
        return {
            'status': 'error', 
            'message': f'Speech test failed: {str(e)}', 
            'tts_available': TTS_AVAILABLE,
            'engine_status': engine is not None
        }

@app.route('/test_mims/<medicine_name>')
def test_mims(medicine_name):
    """Test route to manually test MIMS scraping for a specific medicine"""
    try:
        from weblookup import test_mims as mims_test
        return mims_test(medicine_name)
    except Exception as e:
        return {
            'status': 'error',
            'medicine': medicine_name,
            'error': str(e)
        }

@app.route('/test_all_sources/<medicine_name>')
def test_all_sources(medicine_name):
    """Test route to check all web sources for a specific medicine"""
    try:
        from weblookup import test_all_sources as sources_test
        return sources_test(medicine_name)
    except Exception as e:
        return {
            'status': 'error',
            'medicine': medicine_name,
            'error': str(e)
        }

@app.route('/test_speech_with_medicine/<medicine_name>')
def test_speech_with_medicine(medicine_name):
    """Test route to fetch medicine instructions and speak them"""
    try:
        # Fetch instructions
        instructions = fetch_intake_instructions(medicine_name)
        
        # Speak the instructions
        speak(f"Medicine dispensed: {medicine_name}. {instructions}")
        
        return {
            'status': 'success',
            'medicine': medicine_name,
            'instructions': instructions,
            'tts_available': TTS_AVAILABLE,
            'message': 'Instructions spoken successfully'
        }
    except Exception as e:
        return {
            'status': 'error',
            'medicine': medicine_name,
            'error': str(e),
            'tts_available': TTS_AVAILABLE
        }

@app.route('/test_audio_system')
def test_audio_system():
    """Test and configure audio system"""
    try:
        from text_to_speech import test_audio_system as audio_test
        return audio_test()
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'tts_available': TTS_AVAILABLE
        }

@app.route('/admin_change_password', methods=['POST'])
def admin_change_password():
    username = request.form.get('username')
    # TODO: Implement actual change password logic (e.g., show modal, set new password)
    print(f"Change password requested for user: {username}")
    return '', 200

if __name__ == '__main__':
    print("Starting Medical Dispenser with 3.5\" display support...")
    print("Web interface available at: http://localhost:5000")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start Flask app in a separate thread to allow display to work
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Wait a few seconds for the server to start
    import subprocess
    import time
    time.sleep(5)
    
    # Open Chromium in kiosk mode to the admin dashboard
    try:
        subprocess.Popen(['chromium-browser', '--kiosk', 'http://localhost:5000/admin_dashboard'])
    except FileNotFoundError:
        print("Chromium browser not found. Please install it with 'sudo apt-get install chromium-browser'.")
    
    # Keep the main thread alive for display updates
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Medical Dispenser...")
        cleanup_servo_controller(servo_controller)