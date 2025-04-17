from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging

# Konfiguracja logowania
logging.basicConfig(filename='skillswap.log', level=logging.INFO)

# Inicjalizacja aplikacji
app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/skillswap.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Kategorie umiejętności
SKILL_CATEGORIES = {
    'Języki': ['angielski', 'hiszpański', 'niemiecki'],
    'Sztuka': ['fotografia', 'malarstwo', 'taniec'],
    'Technologia': ['programowanie', 'grafika komputerowa', 'cyberbezpieczeństwo'],
    'Inne': ['gotowanie', 'joga', 'ogrodnictwo']
}

# Modele bazy danych
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(120), nullable=False)
    skills_offered = db.Column(db.String(500))  # Umiejętności oferowane
    skills_wanted = db.Column(db.String(500))   # Umiejętności pożądane
    location = db.Column(db.String(100), index=True)  # Lokalizacja
    points = db.Column(db.Integer, default=10)  # Punkty
    badges = db.Column(db.String(500), default='')  # Odznaki
    notifications = db.Column(db.Integer, default=0)  # Liczba powiadomień

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    skill = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100))  # Kategoria umiejętności
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')
    teacher = db.relationship('User', foreign_keys=[teacher_id], lazy='select')
    student = db.relationship('User', foreign_keys=[student_id], lazy='select')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    sender = db.relationship('User', foreign_keys=[sender_id], lazy='select')
    receiver = db.relationship('User', foreign_keys=[receiver_id], lazy='select')

# Funkcja ładowania użytkownika
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Szablony HTML z Bootstrap
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>SkillSwap</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        {% if current_user.is_authenticated %}
            <a href="{{ url_for('profile') }}" class="btn btn-link">Profil</a><br>
            <a href="{{ url_for('search') }}" class="btn btn-link">Szukaj</a><br>
            <a href="{{ url_for('messages') }}" class="btn btn-link">Wiadomości</a><br>
            <a href="{{ url_for('logout') }}" class="btn btn-link">Wyloguj</a>
        {% else %}
            <a href="{{ url_for('login') }}" class="btn btn-link">Zaloguj</a><br>
            <a href="{{ url_for('register') }}" class="btn btn-link">Zarejestruj</a>
        {% endif %}
    </div>
    <div class="content">
        <h1 class="text-center">Witaj w SkillSwap!</h1>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="alert alert-info">
                    {% for message in messages %}
                        <p>{{ message }}</p>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        <p class="text-center">Wymieniaj umiejętności z innymi użytkownikami!</p>
    </div>
</body>
</html>
"""

REGISTER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Rejestracja</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        <a href="{{ url_for('login') }}" class="btn btn-link">Zaloguj</a><br>
        <a href="{{ url_for('register') }}" class="btn btn-link">Zarejestruj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Rejestracja</h1>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="alert alert-warning">
                    {% for message in messages %}
                        <p>{{ message }}</p>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        <form method="POST" class="col-md-6 mx-auto">
            <div class="mb-3">
                <label class="form-label">Nazwa użytkownika</label>
                <input type="text" name="username" class="form-control" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Email</label>
                <input type="email" name="email" class="form-control" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Hasło</label>
                <input type="password" name="password" class="form-control" minlength="6" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Umiejętności oferowane (oddziel przecinkami)</label>
                <input type="text" name="skills_offered" class="form-control" placeholder="np. fotografia,gotowanie">
            </div>
            <div class="mb-3">
                <label class="form-label">Kategoria umiejętności</label>
                <select name="category" class="form-select">
                    {% for category in categories %}
                        <option value="{{ category }}">{{ category }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">Umiejętności pożądane (oddziel przecinkami)</label>
                <input type="text" name="skills_wanted" class="form-control" placeholder="np. angielski,taniec">
            </div>
            <div class="mb-3">
                <label class="form-label">Lokalizacja</label>
                <input type="text" name="location" class="form-control" placeholder="np. Warszawa">
            </div>
            <button type="submit" class="btn btn-primary">Zarejestruj</button>
        </form>
        <p class="text-center mt-3">Masz konto? <a href="{{ url_for('login') }}">Zaloguj się</a></p>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Logowanie</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        <a href="{{ url_for('login') }}" class="btn btn-link">Zaloguj</a><br>
        <a href="{{ url_for('register') }}" class="btn btn-link">Zarejestruj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Logowanie</h1>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="alert alert-danger">
                    {% for message in messages %}
                        <p>{{ message }}</p>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        <form method="POST" class="col-md-6 mx-auto">
            <div class="mb-3">
                <label class="form-label">Email</label>
                <input type="email" name="email" class="form-control" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Hasło</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-success">Zaloguj</button>
        </form>
        <p class="text-center mt-3">Nie masz konta? <a href="{{ url_for('register') }}">Zarejestruj się</a></p>
    </div>
</body>
</html>
"""

PROFILE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Profil</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        <a href="{{ url_for('profile') }}" class="btn btn-link">Profil</a><br>
        <a href="{{ url_for('search') }}" class="btn btn-link">Szukaj</a><br>
        <a href="{{ url_for('messages') }}" class="btn btn-link">Wiadomości {% if user.notifications %} ({{ user.notifications }}) {% endif %}</a><br>
        <a href="{{ url_for('logout') }}" class="btn btn-link">Wyloguj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Profil {{ user.username }}</h1>
        <div class="card col-md-8 mx-auto">
            <div class="card-body">
                <p><strong>Email:</strong> {{ user.email }}</p>
                <p><strong>Umiejętności oferowane:</strong> {{ user.skills_offered }}</p>
                <p><strong>Umiejętności pożądane:</strong> {{ user.skills_wanted }}</p>
                <p><strong>Lokalizacja:</strong> {{ user.location }}</p>
                <p><strong>Punkty:</strong> {{ user.points }} <a href="{{ url_for('buy_points') }}" class="btn btn-sm btn-warning">Kup punkty</a></p>
                <p><strong>Odznaki:</strong> {{ user.badges or "Brak" }}</p>
                <p><strong>Statystyki:</strong> Sesje: {{ stats.sessions }}, Wiadomości: {{ stats.messages }}</p>
                {% if user.id == current_user.id %}
                    <a href="{{ url_for('edit_profile') }}" class="btn btn-warning btn-sm">Edytuj profil</a>
                {% endif %}
            </div>
        </div>
        {% if user.id == current_user.id %}
            <h3 class="mt-4">Twoje sesje</h3>
            <ul class="list-group col-md-8 mx-auto">
                {% for session in sessions %}
                    <li class="list-group-item">
                        <strong>{{ session.skill }}</strong> ({{ session.category }}) z 
                        {{ session.teacher.username if session.student_id == current_user.id else session.student.username }} 
                        (Status: {{ session.status }})
                        {% if session.status == 'pending' and session.teacher_id == current_user.id %}
                            <a href="{{ url_for('update_session', session_id=session.id, action='accept') }}" class="btn btn-success btn-sm">Akceptuj</a>
                            <a href="{{ url_for('update_session', session_id=session.id, action='reject') }}" class="btn btn-danger btn-sm">Odrzuć</a>
                        {% endif %}
                        {% if session.status == 'accepted' %}
                            <a href="{{ url_for('update_session', session_id=session.id, action='complete') }}" class="btn btn-primary btn-sm">Zakończ</a>
                        {% endif %}
                    </li>
                {% endfor %}
            </ul>
        {% endif %}
    </div>
</body>
</html>
"""

EDIT_PROFILE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Edytuj profil</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        <a href="{{ url_for('profile') }}" class="btn btn-link">Profil</a><br>
        <a href="{{ url_for('search') }}" class="btn btn-link">Szukaj</a><br>
        <a href="{{ url_for('messages') }}" class="btn btn-link">Wiadomości</a><br>
        <a href="{{ url_for('logout') }}" class="btn btn-link">Wyloguj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Edytuj profil</h1>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="alert alert-info">
                    {% for message in messages %}
                        <p>{{ message }}</p>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        <form method="POST" class="col-md-6 mx-auto">
            <div class="mb-3">
                <label class="form-label">Nazwa użytkownika</label>
                <input type="text" name="username" class="form-control" value="{{ user.username }}" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Umiejętności oferowane</label>
                <input type="text" name="skills_offered" class="form-control" value="{{ user.skills_offered }}">
            </div>
            <div class="mb-3">
                <label class="form-label">Kategoria umiejętności</label>
                <select name="category" class="form-select">
                    {% for category in categories %}
                        <option value="{{ category }}" {% if category == user.category %}selected{% endif %}>{{ category }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">Umiejętności pożądane</label>
                <input type="text" name="skills_wanted" class="form-control" value="{{ user.skills_wanted }}">
            </div>
            <div class="mb-3">
                <label class="form-label">Lokalizacja</label>
                <input type="text" name="location" class="form-control" value="{{ user.location }}">
            </div>
            <button type="submit" class="btn btn-primary">Zapisz zmiany</button>
        </form>
        <p class="text-center mt-3"><a href="{{ url_for('profile') }}">Wróć do profilu</a></p>
    </div>
</body>
</html>
"""

SEARCH_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Wyszukiwanie</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        <a href="{{ url_for('profile') }}" class="btn btn-link">Profil</a><br>
        <a href="{{ url_for('search') }}" class="btn btn-link">Szukaj</a><br>
        <a href="{{ url_for('messages') }}" class="btn btn-link">Wiadomości</a><br>
        <a href="{{ url_for('logout') }}" class="btn btn-link">Wyloguj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Szukaj użytkowników</h1>
        <form method="POST" class="col-md-6 mx-auto">
            <div class="mb-3">
                <label class="form-label">Umiejętność</label>
                <input type="text" name="skill" class="form-control" placeholder="np. fotografia" list="skills-list">
                <datalist id="skills-list">
                    {% for category, skills in categories.items() %}
                        {% for skill in skills %}
                            <option value="{{ skill }}">{{ skill }} ({{ category }})</option>
                        {% endfor %}
                    {% endfor %}
                </datalist>
            </div>
            <div class="mb-3">
                <label class="form-label">Kategoria</label>
                <select name="category" class="form-select">
                    <option value="">Wszystkie</option>
                    {% for category in categories.keys() %}
                        <option value="{{ category }}">{{ category }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">Lokalizacja</label>
                <input type="text" name="location" class="form-control" placeholder="np. Warszawa">
            </div>
            <button type="submit" class="btn btn-primary">Szukaj</button>
        </form>
        {% if users %}
            <h3 class="mt-4">Wyniki dla "{{ skill }}" w "{{ location }}"</h3>
            <ul class="list-group col-md-8 mx-auto">
                {% for user in users %}
                    <li class="list-group-item">
                        <a href="{{ url_for('user_profile', user_id=user.id) }}"><strong>{{ user.username }}</strong></a> 
                        ({{ user.skills_offered }} - {{ user.category or "Brak kategorii" }}) 
                        - <a href="{{ url_for('session', teacher_id=user.id) }}" class="btn btn-success btn-sm">Umów sesję</a>
                        - <a href="{{ url_for('send_message', receiver_id=user.id) }}" class="btn btn-info btn-sm">Wyślij wiadomość</a>
                    </li>
                {% endfor %}
            </ul>
        {% endif %}
    </div>
</body>
</html>
"""

SESSION_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Umów sesję</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        <a href="{{ url_for('profile') }}" class="btn btn-link">Profil</a><br>
        <a href="{{ url_for('search') }}" class="btn btn-link">Szukaj</a><br>
        <a href="{{ url_for('messages') }}" class="btn btn-link">Wiadomości</a><br>
        <a href="{{ url_for('logout') }}" class="btn btn-link">Wyloguj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Umów sesję z {{ teacher.username }}</h1>
        <p class="text-center">Umiejętności oferowane: {{ teacher.skills_offered }} ({{ teacher.category or "Brak kategorii" }})</p>
        <form method="POST" class="col-md-6 mx-auto">
            <div class="mb-3">
                <label class="form-label">Umiejętność do nauki</label>
                <input type="text" name="skill" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-primary">Umów sesję</button>
        </form>
        <p class="text-center mt-3"><a href="{{ url_for('search') }}">Wróć do wyszukiwania</a></p>
    </div>
</body>
</html>
"""

MESSAGES_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Wiadomości</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        <a href="{{ url_for('profile') }}" class="btn btn-link">Profil</a><br>
        <a href="{{ url_for('search') }}" class="btn btn-link">Szukaj</a><br>
        <a href="{{ url_for('messages') }}" class="btn btn-link">Wiadomości</a><br>
        <a href="{{ url_for('logout') }}" class="btn btn-link">Wyloguj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Wiadomości</h1>
        {% if conversations %}
            <h3>Twoje rozmowy</h3>
            <ul class="list-group col-md-8 mx-auto">
                {% for conv in conversations %}
                    <li class="list-group-item">
                        <a href="{{ url_for('messages', receiver_id=conv.user_id) }}">
                            <strong>{{ conv.username }}</strong> 
                            {% if conv.unread %} ({{ conv.unread }} nieprzeczytanych) {% endif %}
                        </a>
                    </li>
                {% endfor %}
            </ul>
        {% endif %}
        {% if messages %}
            <h3 class="mt-4">Rozmowa z {{ receiver.username }}</h3>
            <ul class="list-group col-md-8 mx-auto">
                {% for message in messages %}
                    <li class="list-group-item {% if not message.is_read and message.receiver_id == current_user.id %}list-group-item-warning{% endif %}">
                        <strong>{{ message.sender.username }}:</strong> {{ message.content }} 
                        ({{ message.timestamp.strftime('%Y-%m-%d %H:%M') }})
                    </li>
                {% endfor %}
            </ul>
            <h4 class="mt-4">Wyślij wiadomość</h4>
            <form method="POST" action="{{ url_for('send_message', receiver_id=receiver_id) }}" class="col-md-6 mx-auto">
                <div class="mb-3">
                    <label class="form-label">Treść wiadomości</label>
                    <textarea name="content" class="form-control" required></textarea>
                </div>
                <button type="submit" class="btn btn-primary">Wyślij</button>
            </form>
        {% endif %}
        <p class="text-center mt-3"><a href="{{ url_for('profile') }}">Wróć do profilu</a></p>
    </div>
</body>
</html>
"""

BUY_POINTS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Kup punkty</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4>SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link">Strona główna</a><br>
        <a href="{{ url_for('profile') }}" class="btn btn-link">Profil</a><br>
        <a href="{{ url_for('search') }}" class="btn btn-link">Szukaj</a><br>
        <a href="{{ url_for('messages') }}" class="btn btn-link">Wiadomości</a><br>
        <a href="{{ url_for('logout') }}" class="btn btn-link">Wyloguj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Kup punkty</h1>
        <p class="text-center">Wybierz pakiet punktów (symulacja):</p>
        <form method="POST" class="col-md-6 mx-auto">
            <div class="mb-3">
                <label class="form-label">Pakiet</label>
                <select name="points" class="form-select">
                    <option value="10">10 punktów (darmowe)</option>
                    <option value="50">50 punktów (darmowe)</option>
                    <option value="100">100 punktów (darmowe)</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">Kup</button>
        </form>
        <p class="text-center mt-3"><a href="{{ url_for('profile') }}">Wróć do profilu</a></p>
    </div>
</body>
</html>
"""

# Trasy aplikacji
@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        skills_offered = request.form['skills_offered'].strip()
        category = request.form['category']
        skills_wanted = request.form['skills_wanted'].strip()
        location = request.form['location'].strip()

        if len(password) < 6:
            flash('Hasło musi mieć co najmniej 6 znaków!')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email już istnieje!')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Nazwa użytkownika już istnieje!')
            return redirect(url_for('register'))

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            skills_offered=skills_offered,
            skills_wanted=skills_wanted,
            location=location,
            points=10,
            category=category
        )
        db.session.add(user)
        db.session.commit()
        logging.info(f'Rejestracja użytkownika: {username}')
        flash('Rejestracja udana! Zaloguj się.')
        return redirect(url_for('login'))

    return render_template_string(REGISTER_HTML, categories=SKILL_CATEGORIES.keys())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            logging.info(f'Logowanie użytkownika: {user.username}')
            return redirect(url_for('profile'))
        else:
            flash('Błędny email lub hasło!')
            return redirect(url_for('login'))

    return render_template_string(LOGIN_HTML)

@app.route('/logout')
@login_required
def logout():
    logging.info(f'Wylogowanie użytkownika: {current_user.username}')
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@app.route('/profile/<int:user_id>')
@login_required
def user_profile(user_id=None):
    user = User.query.get_or_404(user_id if user_id else current_user.id)
    sessions = Session.query.filter(
        (Session.teacher_id == user.id) | (Session.student_id == user.id)
    ).all() if user.id == current_user.id else []
    stats = {
        'sessions': Session.query.filter(
            (Session.teacher_id == user.id) | (Session.student_id == user.id)
        ).count(),
        'messages': Message.query.filter(
            (Message.sender_id == user.id) | (Message.receiver_id == user.id)
        ).count()
    }
    return render_template_string(PROFILE_HTML, user=user, sessions=sessions, stats=stats)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form['username'].strip()
        skills_offered = request.form['skills_offered'].strip()
        category = request.form['category']
        skills_wanted = request.form['skills_wanted'].strip()
        location = request.form['location'].strip()

        if username != current_user.username and User.query.filter_by(username=username).first():
            flash('Nazwa użytkownika już istnieje!')
            return redirect(url_for('edit_profile'))

        current_user.username = username
        current_user.skills_offered = skills_offered33
        current_user.category = category
        current_user.skills_wanted = skills_wanted
        current_user.location = location
        db.session.commit()
        logging.info(f'Edycja profilu: {current_user.username}')
        flash('Profil zaktualizowany!')
        return redirect(url_for('profile'))

    return render_template_string(EDIT_PROFILE_HTML, user=current_user, categories=SKILL_CATEGORIES)

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'POST':
        skill = request.form['skill'].strip().lower()
        category = request.form['category'].strip()
        location = request.form['location'].strip().lower()
        query = User.query
        if skill:
            query = query.filter(User.skills_offered.ilike(f'%{skill}%'))
        if category:
            query = query.filter(User.category == category)
        if location:
            query = query.filter(User.location.ilike(f'%{location}%'))
        users = query.filter(User.id != current_user.id).all()
        return render_template_string(SEARCH_HTML, users=users, skill=skill, location=location, categories=SKILL_CATEGORIES)
    return render_template_string(SEARCH_HTML, categories=SKILL_CATEGORIES)

@app.route('/session/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
def session(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    if request.method == 'POST':
        skill = request.form['skill'].strip()
        if current_user.points < 5:
            flash('Nie masz wystarczająco punktów (potrzeba 5)!')
            return redirect(url_for('session', teacher_id=teacher_id))
        session = Session(
            teacher_id=teacher_id,
            student_id=current_user.id,
            skill=skill,
            category=teacher.category
        )
        current_user.points -= 5
        teacher.notifications += 1
        db.session.add(session)
        db.session.commit()
        logging.info(f'Umówiono sesję: {current_user.username} z {teacher.username}')
        flash('Sesja umówiona! Czekaj na potwierdzenie.')
        return redirect(url_for('profile'))
    return render_template_string(SESSION_HTML, teacher=teacher)

@app.route('/update_session/<int:session_id>/<action>')
@login_required
def update_session(session_id, action):
    session = Session.query.get_or_404(session_id)
    if session.teacher_id != current_user.id:
        flash('Brak uprawnień!')
        return redirect(url_for('profile'))
    
    if action == 'accept':
        session.status = 'accepted'
    elif action == 'reject':
        session.status = 'rejected'
        student = User.query.get(session.student_id)
        student.points += 5
    elif action == 'complete':
        session.status = 'completed'
        teacher = User.query.get(session.teacher_id)
        teacher.points += 10
        completed_sessions = Session.query.filter_by(teacher_id=teacher.id, status='completed').count()
        if completed_sessions >= 10 and 'Mistrz Nauczania' not in (teacher.badges or ''):
            teacher.badges = (teacher.badges or '') + ',Mistrz Nauczania'
    
    db.session.commit()
    logging.info(f'Aktualizacja sesji {session_id}: {action}')
    flash(f'Sesja zaktualizowana: {action}')
    return redirect(url_for('profile'))

@app.route('/messages', methods=['GET'])
@app.route('/messages/<int:receiver_id>', methods=['GET', 'POST'])
@login_required
def messages(receiver_id=None):
    if request.method == 'POST':
        content = request.form['content'].strip()
        if not content:
            flash('Wiadomość nie może być pusta!')
            return redirect(url_for('messages', receiver_id=receiver_id))
        message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content
        )
        receiver = User.query.get(receiver_id)
        receiver.notifications += 1
        current_user.points += 1  # Punkt za wiadomość
        db.session.add(message)
        db.session.commit()
        logging.info(f'Wiadomość od {current_user.username} do {receiver.username}')
        flash('Wiadomość wysłana!')
        return redirect(url_for('messages', receiver_id=receiver_id))
    
    # Oznacz wiadomości jako przeczytane
    if receiver_id:
        unread = Message.query.filter_by(receiver_id=current_user.id, sender_id=receiver_id, is_read=False).all()
        for msg in unread:
            msg.is_read = True
        current_user.notifications = max(0, current_user.notifications - len(unread))
        db.session.commit()

    # Lista rozmów
    conversations = db.session.query(
        User.id.label('user_id'),
        User.username,
        db.func.count(Message.id).filter(Message.is_read == False, Message.receiver_id == current_user.id).label('unread')
    ).join(Message, (Message.sender_id == User.id) | (Message.receiver_id == User.id))\
     .filter((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id))\
     .group_by(User.id, User.username).all()

    messages = []
    receiver = None
    if receiver_id:
        messages = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id)) |
            ((Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp).all()
        receiver = User.query.get(receiver_id)
    
    return render_template_string(MESSAGES_HTML, conversations=conversations, messages=messages, receiver=receiver, receiver_id=receiver_id)

@app.route('/send_message/<int:receiver_id>')
@login_required
def send_message(receiver_id):
    return redirect(url_for('messages', receiver_id=receiver_id))

@app.route('/buy_points', methods=['GET', 'POST'])
@login_required
def buy_points():
    if request.method == 'POST':
        points = int(request.form['points'])
        current_user.points += points
        db.session.commit()
        logging.info(f'Kupiono {points} punktów przez {current_user.username}')
        flash(f'Dodano {points} punktów!')
        return redirect(url_for('profile'))
    return render_template_string(BUY_POINTS_HTML)

# Uruchomienie aplikacji
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
