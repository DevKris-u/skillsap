from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
import os

# Konfiguracja logowania
logging.basicConfig(filename='skillswap.log', level=logging.INFO)

# Inicjalizacja aplikacji
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super-secret-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:////tmp/skillswap.db')
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
    skills_offered = db.Column(db.String(500))
    skills_wanted = db.Column(db.String(500))
    location = db.Column(db.String(100), index=True)
    category = db.Column(db.String(100))  # Kategoria umiejętności
    points = db.Column(db.Integer, default=10)
    badges = db.Column(db.String(500), default='')
    notifications = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)  # Średnia ocena
    rating_count = db.Column(db.Integer, default=0)  # Liczba ocen

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    skill = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')
    rating = db.Column(db.Integer, nullable=True)  # Ocena sesji (1-5)
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
        <h4><i class="bi bi-share"></i> SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link"><i class="bi bi-house"></i> Strona główna</a><br>
        {% if current_user.is_authenticated %}
            <a href="{{ url_for('profile') }}" class="btn btn-link"><i class="bi bi-person"></i> Profil</a><br>
            <a href="{{ url_for('search') }}" class="btn btn-link"><i class="bi bi-search"></i> Szukaj</a><br>
            <a href="{{ url_for('messages') }}" class="btn btn-link"><i class="bi bi-chat"></i> Wiadomości {% if current_user.notifications %} ({{ current_user.notifications }}) {% endif %}</a><br>
            <a href="{{ url_for('logout') }}" class="btn btn-link"><i class="bi bi-box-arrow-right"></i> Wyloguj</a>
        {% else %}
            <a href="{{ url_for('login') }}" class="btn btn-link"><i class="bi bi-box-arrow-in-right"></i> Zaloguj</a><br>
            <a href="{{ url_for('register') }}" class="btn btn-link"><i class="bi bi-person-plus"></i> Zarejestruj</a>
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
        <p class="text-center">Wymieniaj umiejętności i ucz się od innych!</p>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
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
        <h4><i class="bi bi-share"></i> SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link"><i class="bi bi-house"></i> Strona główna</a><br>
        <a href="{{ url_for('login') }}" class="btn btn-link"><i class="bi bi-box-arrow-in-right"></i> Zaloguj</a><br>
        <a href="{{ url_for('register') }}" class="btn btn-link"><i class="bi bi-person-plus"></i> Zarejestruj</a>
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
                <input type="text" name="username" class="form-control" required minlength="3">
            </div>
            <div class="mb-3">
                <label class="form-label">Email</label>
                <input type="email" name="email" class="form-control" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Hasło</label>
                <input type="password" name="password" class="form-control" required minlength="6">
            </div>
            <div class="mb-3">
                <label class="form-label">Umiejętności oferowane</label>
                <input type="text" name="skills_offered" class="form-control" placeholder="np. fotografia,gotowanie">
            </div>
            <div class="mb-3">
                <label class="form-label">Kategoria umiejętności</label>
                <select name="category" class="form-select">
                    <option value="">Wybierz kategorię</option>
                    {% for category in categories %}
                        <option value="{{ category }}">{{ category }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">Umiejętności pożądane</label>
                <input type="text" name="skills_wanted" class="form-control" placeholder="np. angielski,taniec">
            </div>
            <div class="mb-3">
                <label class="form-label">Lokalizacja</label>
                <input type="text" name="location" class="form-control" placeholder="np. Warszawa">
            </div>
            <button type="submit" class="btn btn-primary"><i class="bi bi-person-plus"></i> Zarejestruj</button>
        </form>
        <p class="text-center mt-3">Masz konto? <a href="{{ url_for('login') }}">Zaloguj się</a></p>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
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
        <h4><i class="bi bi-share"></i> SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link"><i class="bi bi-house"></i> Strona główna</a><br>
        <a href="{{ url_for('login') }}" class="btn btn-link"><i class="bi bi-box-arrow-in-right"></i> Zaloguj</a><br>
        <a href="{{ url_for('register') }}" class="btn btn-link"><i class="bi bi-person-plus"></i> Zarejestruj</a>
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
            <button type="submit" class="btn btn-success"><i class="bi bi-box-arrow-in-right"></i> Zaloguj</button>
        </form>
        <p class="text-center mt-3">Nie masz konta? <a href="{{ url_for('register') }}">Zarejestruj się</a></p>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

PROFILE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Profil</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4><i class="bi bi-share"></i> SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link"><i class="bi bi-house"></i> Strona główna</a><br>
        <a href="{{ url_for('profile') }}" class="btn btn-link"><i class="bi bi-person"></i> Profil</a><br>
        <a href="{{ url_for('search') }}" class="btn btn-link"><i class="bi bi-search"></i> Szukaj</a><br>
        <a href="{{ url_for('messages') }}" class="btn btn-link"><i class="bi bi-chat"></i> Wiadomości {% if user.notifications %} ({{ user.notifications }}) {% endif %}</a><br>
        <a href="{{ url_for('logout') }}" class="btn btn-link"><i class="bi bi-box-arrow-right"></i> Wyloguj</a>
    </div>
    <div class="content">
        <h1 class="text-center">Profil {{ user.username }}</h1>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="alert alert-info">
                    {% for message in messages %}
                        <p>{{ message }}</p>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        <div class="card col-md-8 mx-auto">
            <div class="card-body">
                <p><strong><i class="bi bi-envelope"></i> Email:</strong> {{ user.email }}</p>
                <p><strong><i class="bi bi-gear"></i> Umiejętności oferowane:</strong> {{ user.skills_offered or "Brak" }}</p>
                <p><strong><i class="bi bi-search"></i> Umiejętności pożądane:</strong> {{ user.skills_wanted or "Brak" }}</p>
                <p><strong><i class="bi bi-geo-alt"></i> Lokalizacja:</strong> {{ user.location or "Brak" }}</p>
                <p><strong><i class="bi bi-star"></i> Ocena:</strong> {{ "%.1f" % user.rating if user.rating_count else "Brak ocen" }} ({{ user.rating_count }} ocen)</p>
                <p><strong><i class="bi bi-coin"></i> Punkty:</strong> {{ user.points }} <a href="{{ url_for('buy_points') }}" class="btn btn-sm btn-warning"><i class="bi bi-cart"></i> Kup punkty</a></p>
                <p><strong><i class="bi bi-award"></i> Odznaki:</strong> {{ user.badges or "Brak" }}</p>
                <p><strong><i class="bi bi-bar-chart"></i> Statystyki:</strong> Sesje: {{ stats.sessions }}, Wiadomości: {{ stats.messages }}</p>
                {% if user.id == current_user.id %}
                    <a href="{{ url_for('edit_profile') }}" class="btn btn-warning btn-sm"><i class="bi bi-pencil"></i> Edytuj profil</a>
                    {% if user.notifications %}
                        <a href="{{ url_for('clear_notifications') }}" class="btn btn-secondary btn-sm"><i class="bi bi-bell"></i> Wyczyść powiadomienia</a>
                    {% endif %}
                {% endif %}
            </div>
        </div>
        {% if user.id == current_user.id %}
            <h3 class="mt-4">Twoje sesje</h3>
            <ul class="list-group col-md-8 mx-auto">
                {% for session in sessions %}
                    <li class="list-group-item">
                        <strong>{{ session.skill }}</strong> ({{ session.category or "Brak kategorii" }}) z 
                        {{ session.teacher.username if session.student_id == current_user.id else session.student.username }} 
                        (Status: {{ session.status }})
                        {% if session.status == 'pending' and session.teacher_id == current_user.id %}
                            <a href="{{ url_for('update_session', session_id=session.id, action='accept') }}" class="btn btn-success btn-sm"><i class="bi bi-check"></i> Akceptuj</a>
                            <a href="{{ url_for('update_session', session_id=session.id, action='reject') }}" class="btn btn-danger btn-sm"><i class="bi bi-x"></i> Odrzuć</a>
                        {% endif %}
                        {% if session.status == 'accepted' %}
                            <a href="{{ url_for('update_session', session_id=session.id, action='complete') }}" class="btn btn-primary btn-sm"><i class="bi bi-check-circle"></i> Zakończ</a>
                        {% endif %}
                        {% if session.status == 'completed' and session.student_id == current_user.id and not session.rating %}
                            <form action="{{ url_for('rate_session', session_id=session.id) }}" method="POST" class="d-inline">
                                <select name="rating" required>
                                    <option value="1">1</option>
                                    <option value="2">2</option>
                                    <option value="3">3</option>
                                    <option value="4">4</option>
                                    <option value="5">5</option>
                                </select>
                                <button type="submit" class="btn btn-info btn-sm"><i class="bi bi-star"></i> Oceń</button>
                            </form>
                        {% endif %}
                    </li>
                {% endfor %}
            </ul>
        {% endif %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

EDIT_PROFILE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Edytuj profil</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .sidebar { position: fixed; top: 0; left: 0; height: 100%; width: 200px; background-color: #f8f9fa; padding: 20px; }
        .content { margin-left: 220px; padding: 20px; }
        @media (max-width: 768px) { .sidebar { width: 100%; height: auto; position: relative; } .content { margin-left: 0; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <h4><i class="bi bi-share"></i> SkillSwap</h4>
        <a href="{{ url_for('index') }}" class="btn btn-link"><i class="bi bi-house"></i> Strona główna</a><br>
        <a href="{{ url_for('profile') }}" class="btn btn-link"><i class="bi bi-person"></i> Profil</a><br>
        <a href="{{ url_for('search') }}" class="btn btn-link"><i class="bi bi-search"></i> Szukaj</a><br>
        <a href="{{ url_for('messages') }}" class="btn btn-link"><i class="bi bi-chat"></i> Wiadomości</a><br>
        <a href="{{ url_for('logout') }}" class="btn btn-link"><i class="bi bi-box-arrow-right"></i> Wyloguj</a>
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
                <input type="text" name="username" class="form-control" value="{{ user.username }}" required minlength="3">
            </div>
            <div class="mb-3">
                <label class="form-label">Umiejętności oferowane</label>
                <input type="text" name="skills_offered" class="form-control" value="{{ user.skills_offered or '' }}">
            </div>
            <div class="mb-3">
                <label class="form-label">Kategoria umiejętności</label>
                <select name="category" class="form-select">
                    <option value="">Wybierz kategorię</option>
                    {% for category in categories %}
                        <option value="{{ category }}" {% if category == user.category %}selected{% endif %}>{{ category }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label">Umiejętności pożądane</label>
                <input type="text" name="ski
