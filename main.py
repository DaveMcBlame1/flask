from flask import Flask, render_template, request, redirect, url_for, session, abort, send_from_directory, jsonify, g
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from functools import wraps
from werkzeug.utils import secure_filename
import os
from PIL import Image
from mysql.connector import connection

# Initialize the Flask app
app = Flask(__name__, template_folder='source')
app.config["SECRET_KEY"] = "your_secret_key"  # Set a secret key for session management
app.config["UPLOAD_FOLDER"] = "data/profileexchange"  # Folder to store uploaded files
app.config["PROFILE_FOLDER"] = "data/profiles"  # Folder to store profile pictures
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # Limit file uploads to 5 MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

bcrypt = Bcrypt(app)
socketio = SocketIO(app, async_mode="eventlet", ping_timeout=60, ping_interval=25)

AUTHORIZED_USERS = ['Owner', 'DaveMcBlame']
users = {}  # Dictionary to track users by their session IDs

# Connect to the database
def get_db():
    if 'db' not in g:
        g.db = connection.MySQLConnection(user='root', password='sGdUDCMPlffiKHJxTDRsrlqOrywwBJHR',
                                          host='mysql.railway.internal', port='3306',
                                          database='railway')
        cursor = g.db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(80) UNIQUE NOT NULL,
                            password VARCHAR(200) NOT NULL,
                            profile_picture TEXT
                        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS bannedusers (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(255) UNIQUE NOT NULL
                        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            username VARCHAR(80) NOT NULL,
                            message VARCHAR(500) NOT NULL,
                            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )''')
        g.db.commit()
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Create a User model
def get_user_by_username(username):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    return cursor.fetchone()

def create_user(username, password):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
    db.commit()

def get_all_banned_users():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM bannedusers")
    return cursor.fetchall()

def ban_user(username):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO bannedusers (username) VALUES (%s)", (username,))
    db.commit()

def unban_user(username):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM bannedusers WHERE username = %s", (username,))
    db.commit()

def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("username") not in AUTHORIZED_USERS:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Custom route to serve static files with access control
@app.route('/static/<path:filename>')
@owner_required
def custom_static(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

@app.route('/data/<path:filename>')
def data(filename):
    return send_from_directory('data', filename)

# Context processor to add user to all templates
@app.context_processor
def inject_user():
    if "username" in session:
        user = get_user_by_username(session["username"])
        return dict(user=user)
    return dict(user=None)

# Routes or endpoints
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/support")
def support():
    return render_template("support.html")

@app.route("/trigger-error")
def trigger_error():
    raise Exception("This is a test exception to trigger the Flask debugger")

@app.route("/changelogs")
def changelogs():
    return render_template("changelogs.html")

@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect(url_for("login"))
    
    user = get_user_by_username(session["username"])
    if not user:
        return "User not found", 404

    return render_template("profile.html", user=user)

# User authentication
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
        if get_user_by_username(username):
            return "Username already taken!"
        create_user(username, password)
        return redirect(url_for("login"))
    return render_template("register.html")

# User login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        
        if not username or not password:
            return "Username and password cannot be empty!"

        user = get_user_by_username(username)
        if user:
            try:
                if bcrypt.check_password_hash(user[2], password):
                    session["username"] = username  # Store the username in the session
                    return redirect(url_for("chat"))  # Redirect to the chat page after successful login
            except ValueError:
                abort(404)
        return "Invalid credentials!"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)  # Remove the username from the session
    return render_template("logout.html")

# Chat room
@app.route("/chat")
def chat():
    if "username" not in session:
        return redirect(url_for("login"))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT 50")
    messages = cursor.fetchall()
    messages.reverse()
    
    # Include profile picture URL with each message
    messages_with_pics = []
    for msg in messages:
        user = get_user_by_username(msg[1])
        profile_picture = user[3] if user and user[3] else 'images/profile-placeholder.png'
        profile_picture_url = url_for('data', filename='profiles/' + profile_picture) if user and user[3] else url_for('static', filename=profile_picture)
        messages_with_pics.append({
            'username': msg[1],
            'message': msg[2],
            'id': msg[0],
            'profile_picture_url': profile_picture_url
        })
    
    return render_template("chat.html", username=session["username"], messages=messages_with_pics)

@app.route("/more_messages/<int:offset>")
def more_messages(offset):
    if "username" not in session:
        return redirect(url_for("login"))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT 25 OFFSET %s", (offset,))
    messages = cursor.fetchall()
    messages.reverse()
    return jsonify([{
        'id': msg[0],
        'username': msg[1],
        'message': msg[2],
        'timestamp': msg[3]
    } for msg in messages])

@socketio.on('delete_message')
def handle_delete_message(data):
    username = session.get("username")
    if username in AUTHORIZED_USERS:  # Check if the username is in the list of authorized users
        message_id = data['message_id']
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
        db.commit()
        emit('message_deleted', {'message_id': message_id}, broadcast=True)
        emit('message', {'username': 'System', 'message': f'Message {message_id} deleted by {username}', 'system': True}, broadcast=True)
    else:
        emit('message', {'username': 'System', 'message': 'You do not have permission to delete messages', 'system': True}, broadcast=True)

@socketio.on('message')
def handle_message(data):
    username = session.get("username")
    if username:
        # Check if the user is banned
        if username in [user[1] for user in get_all_banned_users()]:
            emit('message', {
                'username': 'System',
                'message': 'You are banned from chatting.',
                'system': True,
                'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
            })
            return

        message_text = data['message']
        if message_text.startswith('/'):
            # Check for user permissions
            if username not in AUTHORIZED_USERS:
                emit('message', {
                    'username': 'System',
                    'message': 'You do not have permission to execute commands',
                    'system': True,
                    'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
                })
                return

            # Handle command
            if len(message_text[1:].split()) > 0:
                command, *args = message_text[1:].split()
            else:
                # Handle the case where there's not enough data
                print("Error: message_text does not contain enough values")

            if command == 'delete' and len(args) == 1:
                if username not in AUTHORIZED_USERS:
                    emit('message', {
                        'username': 'System',
                        'message': 'You do not have permission to delete messages',
                        'system': True,
                        'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
                    })
                    return

                message_id = args[0]
                db = get_db()
                cursor = db.cursor()
                cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
                db.commit()
                emit('message_deleted', {'message_id': message_id}, broadcast=True)
                emit('message', {
                    'username': 'System',
                    'message': f'Message {message_id} deleted by {username}',
                    'system': True,
                    'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
                }, broadcast=True)
            elif command == 'ban' and len(args) == 1:
                user_to_ban = args[0]
                user = get_user_by_username(user_to_ban)
                if user and user_to_ban not in [user[1] for user in get_all_banned_users()]:
                    ban_user(user_to_ban)
                    emit('message', {
                        'username': 'System',
                        'message': f'User {user_to_ban} has been banned by {username}',
                        'system': True,
                        'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
                    }, broadcast=True)
                else:
                    emit('message', {
                        'username': 'System',
                        'message': f'User {user_to_ban} is already banned or does not exist.',
                        'system': True,
                        'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
                    }, broadcast=True)
            elif command == 'unban' and len(args) == 1:
                user_to_unban = args[0]
                user = get_user_by_username(user_to_unban)
                if user:
                    unban_user(user_to_unban)
                    emit('message', {
                        'username': 'System',
                        'message': f'User {user_to_unban} has been unbanned by {username}',
                        'system': True,
                        'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
                    }, broadcast=True)
                else:
                    emit('message', {
                        'username': 'System',
                        'message': f'User {user_to_unban} does not exist.',
                        'system': True,
                        'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
                    }, broadcast=True)
            else:
                emit('message', {
                    'username': 'System',
                    'message': 'Invalid command or arguments',
                    'system': True,
                    'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')  # Default system profile picture
                }, broadcast=True)
        else:
            # Normal message
            db = get_db()
            cursor = db.cursor()
            cursor.execute("INSERT INTO messages (username, message) VALUES (%s, %s)", (username, message_text))
            db.commit()
            message_id = cursor.lastrowid

            # Include profile picture URL with the message
            user = get_user_by_username(username)
            profile_picture = user[3] if user and user[3] else 'images/profile-placeholder.png'
            profile_picture_url = url_for('data', filename='profiles/' + profile_picture) if user and user[3] else url_for('static', filename=profile_picture)

            emit('message', {
                'username': username,
                'message': message_text,
                'message_id': message_id,
                'profile_picture_url': profile_picture_url,
                'system': False
            }, broadcast=True)

@socketio.on('typing')
def on_typing():
    username = session.get("username")
    if username:
        emit('user_typing', {'username': username}, broadcast=True)

@socketio.on('stop_typing')
def on_stop_typing():
    username = session.get("username")
    if username:
        emit('user_stopped_typing', {'username': username}, broadcast=True)

@socketio.on('connect')
def on_connect():
    username = session.get("username")
    if username:
        # Check if the user is already connected
        for sid, user in users.items():
            if user == username:
                # Notify the previous connection about the disconnection
                emit('force_disconnect', {'message': 'You have been disconnected because you logged in from another tab.'}, room=sid)
                # Disconnect the previous connection
                disconnect(sid)
                break

        users[request.sid] = username
        emit('user_joined', {'username': username}, broadcast=True)
        emit('update_user_list', list(users.values()), broadcast=True)
        # Announce in the chat that the user has joined
        emit('message', {'username': 'System', 'message': f'{username} has joined the chat', 'system': True, 'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')}, broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    username = users.pop(request.sid, 'Unknown')
    emit('user_left', {'username': username}, broadcast=True)
    emit('update_user_list', list(users.values()), broadcast=True)
    # Announce in the chat that the user has left
    emit('message', {'username': 'System', 'message': f'{username} has left the chat', 'system': True, 'profile_picture_url': url_for('static', filename='images/profile-placeholder.png')}, broadcast=True)

# Endpoint to get the list of connected users
@app.route("/connected_users")
def connected_users():
    return jsonify(users)

# Route to handle profile picture upload
@app.route("/upload_profile_picture", methods=["POST"])
def upload_profile_picture():
    if "username" not in session:
        return redirect(url_for("login"))

    file = request.files["profile_picture"]
    if file:
        user = get_user_by_username(session["username"])
        if not user:
            return "User not found", 404

        filename = secure_filename(file.filename)
        original_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(original_path)

        # Convert the image to PNG, resize to 128x128, and remove metadata
        img = Image.open(original_path)
        img = img.resize((128, 128))
        png_filename = f"{user[0]}.png"  # Use the user's ID for the filename
        png_path = os.path.join(app.config["PROFILE_FOLDER"], png_filename)
        img.save(png_path, "PNG")

        # Delete the original file
        os.remove(original_path)

        # Update user's profile picture in the database
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET profile_picture = %s WHERE id = %s", (png_filename, user[0]))
        db.commit()

        return redirect(url_for("profile"))

    return "No file uploaded", 400

# Admin panel
@app.route("/testing")
@owner_required
def logs():
    return render_template("testing.html")

# Error handling
@app.errorhandler(404)
def page_not_found(error):
    return render_template('/error/404.html'), 404

@app.errorhandler(403)
def access_denied(error):
    return render_template('/error/403.html'), 403

if __name__ == "__main__":
    socketio.run(app, port=int(os.environ.get("PORT", 5000)))