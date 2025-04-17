from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
import os
import functools

# Konfiguracja
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super-secret-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///skillswap.db').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
logging.basicConfig(filename='skillswap.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    category = db.Column(db.String(100))
    points = db.Column(db.Integer, default=10)
    badges = db.Column(db.String(500), default='')
    notifications = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    skill = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')
    rating = db.Column(db.Integer)
    teacher = db.relationship('User', foreign_keys=[teacher_id])
    student = db.relationship('User', foreign_keys=[student_id])

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

# Funkcje pomocnicze
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def handle_db_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            logging.error(f'Błąd w {func.__name__}: {str(e)}')
            flash(f'Błąd: {str(e)}')
            return redirect(url_for('index'))
    return wrapper

def validate_form(form, is_register=True):
    username = form.get('username', '').strip()
    email = form.get('email', '').strip().lower() if is_register else current_user.email
    password = form.get('password', '') if is_register else None

    if len(username) < 3:
        flash('Nazwa użytkownika musi mieć co najmniej 3 znaki!')
        return False
    if is_register:
        if len(password) < 6:
            flash('Hasło musi mieć co najmniej 6 znaków!')
            return False
        if not email or '@' not in email:
            flash('Niepoprawny email!')
            return False
        if User.query.filter_by(email=email).first():
            flash('Email już istnieje!')
            return False
    if username != current_user.username and User.query.filter_by(username=username).first():
        flash('Nazwa użytkownika już istnieje!')
        return False
    return True

# Szablony HTML
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}SkillSwap{% endblock %}</title>
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
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="alert alert-{% if 'Błędny' in messages[0] or 'Niepoprawny' in messages[0] %}danger{% else %}info{% endif %}">
                    {% for message in messages %}
                        <p>{{ message }}</p>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

INDEX_HTML = """
{% extends "base.html" %}
{% block title %}SkillSwap{% endblock %}
{% block content %}
    <h1 class="text-center">Witaj w SkillSwap!</h1>
    <p class="text-center">Wymieniaj umiejętności i ucz się od innych!</p>
{% endblock %}
"""

REGISTER_HTML = """
{% extends "base.html" %}
{% block title %}Rejestracja{% endblock %}
{% block content %}
    <h1 class="text-center">Rejestracja</h1>
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
{% endblock %}
"""

LOGIN_HTML = """
{% extends "base.html" %}
{% block title %}Logowanie{% endblock %}
{% block content %}
    <h1 class="text-center">Logowanie</h1>
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
{% endblock %}
"""

PROFILE_HTML = """
{% extends "base.html" %}
{% block title %}Profil{% endblock %}
{% block content %}
    <h1 class="text-center">Profil {{ user.username }}</h1>
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
                    <strong>{{ session.skill }}</strong> ({{ session.category or "Brak" }}) z 
                    {{ session.teacher.username if session.student_id == current_user.id else session.student.username }} 
                    ({{ session.status }})
                    {% if session.status == 'pending' and session.teacher_id == current_user.id %}
                        <a href="{{ url_for('update_session', session_id=session.id, action='accept') }}" class="btn btn-success btn-sm"><i class="bi bi-check"></i></a>
                        <a href="{{ url_for('update_session', session_id=session.id, action='reject') }}" class="btn btn-danger btn-sm"><i class="bi bi-x"></i></a>
                    {% elif session.status == 'accepted' %}
                        <a href="{{ url_for('update_session', session_id=session.id, action='complete') }}" class="btn btn-primary btn-sm"><i class="bi bi-check-circle"></i></a>
                    {% elif session.status == 'completed' and session.student_id == current_user.id and not session.rating %}
                        <form action="{{ url_for('rate_session', session_id=session.id) }}" method="POST" class="d-inline">
                            <select name="rating" required>
                                <option value="1">1</option>
                                <option value="2">2</option>
                                <option value="3">3</option>
                                <option value="4">4</option>
                                <option value="5">5</option>
                            </select>
                            <button type="submit" class="btn btn-info btn-sm"><i class="bi bi-star"></i></button>
                        </form>
                    {% endif %}
                </li>
            {% endfor %}
        </ul>
    {% endif %}
{% endblock %}
"""

EDIT_PROFILE_HTML = """
{% extends "base.html" %}
{% block title %}Edytuj profil{% endblock %}
{% block content %}
    <h1 class="text-center">Edytuj profil</h1>
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
            <input type="text" name="skills_wanted" class="form-control" value="{{ user.skills_wanted or '' }}">
        </div>
        <div class="mb-3">
            <label class="form-label">Lokalizacja</label>
            <input type="text" name="location" class="form-control" value="{{ user.location or '' }}">
        </div>
        <button type="submit" class="btn btn-primary"><i class="bi bi-save"></i> Zapisz</button>
    </form>
    <p class="text-center mt-3"><a href="{{ url_for('profile') }}">Wróć do profilu</a></p>
{% endblock %}
"""

SEARCH_HTML = """
{% extends "base.html" %}
{% block title %}Wyszukiwanie{% endblock %}
{% block content %}
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
        <button type="submit" class="btn btn-primary"><i class="bi bi-search"></i> Szukaj</button>
    </form>
    {% if users %}
        <h3 class="mt-4">Wyniki wyszukiwania</h3>
        <ul class="list-group col-md-8 mx-auto">
            {% for user in users %}
                <li class="list-group-item">
                    <a href="{{ url_for('user_profile', user_id=user.id) }}"><strong>{{ user.username }}</strong></a> 
                    ({{ user.skills_offered or "Brak" }} - {{ user.category or "Brak" }}) 
                    <a href="{{ url_for('session', teacher_id=user.id) }}" class="btn btn-success btn-sm"><i class="bi bi-calendar"></i></a>
                    <a href="{{ url_for('send_message', receiver_id=user.id) }}" class="btn btn-info btn-sm"><i class="bi bi-chat"></i></a>
                </li>
            {% endfor %}
        </ul>
    {% endif %}
{% endblock %}
"""

SESSION_HTML = """
{% extends "base.html" %}
{% block title %}Umów sesję{% endblock %}
{% block content %}
    <h1 class="text-center">Umów sesję z {{ teacher.username }}</h1>
    <p class="text-center">{{ teacher.skills_offered or "Brak" }} ({{ teacher.category or "Brak" }})</p>
    <form method="POST" class="col-md-6 mx-auto">
        <div class="mb-3">
            <label class="form-label">Umiejętność do nauki</label>
            <input type="text" name="skill" class="form-control" required minlength="2">
        </div>
        <button type="submit" class="btn btn-primary"><i class="bi bi-calendar"></i> Umów</button>
    </form>
    <p class="text-center mt-3"><a href="{{ url_for('search') }}">Wróć do wyszukiwania</a></p>
{% endblock %}
"""

MESSAGES_HTML = """
{% extends "base.html" %}
{% block title %}Wiadomości{% endblock %}
{% block content %}
    <h1 class="text-center">Wiadomości</h1>
    {% if conversations %}
        <h3>Rozmowy</h3>
        <ul class="list-group col-md-8 mx-auto">
            {% for conv in conversations %}
                <li class="list-group-item">
                    <a href="{{ url_for('messages', receiver_id=conv.user_id) }}"><strong>{{ conv.username }}</strong> {% if conv.unread %} ({{ conv.unread }}) {% endif %}</a>
                </li>
            {% endfor %}
        </ul>
    {% endif %}
    {% if messages %}
        <h3 class="mt-4">Rozmowa z {{ receiver.username }}</h3>
        <ul class="list-group col-md-8 mx-auto">
            {% for message in messages %}
                <li class="list-group-item {% if not message.is_read and message.receiver_id == current_user.id %}list-group-item-warning{% endif %}">
                    <strong>{{ message.sender.username }}:</strong> {{ message.content }} ({{ message.timestamp.strftime('%Y-%m-%d %H:%M') }})
                </li>
            {% endfor %}
        </ul>
        <h4 class="mt-4">Wyślij wiadomość</h4>
        <form method="POST" action="{{ url_for('send_message', receiver_id=receiver_id) }}" class="col-md-6 mx-auto">
            <div class="mb-3">
                <label class="form-label">Treść</label>
                <textarea name="content" class="form-control" required minlength="1"></textarea>
            </div>
            <button type="submit" class="btn btn-primary"><i class="bi bi-send"></i> Wyślij</button>
        </form>
    {% endif %}
    <p class="text-center mt-3"><a href="{{ url_for('profile') }}">Wróć do profilu</a></p>
{% endblock %}
"""

BUY_POINTS_HTML = """
{% extends "base.html" %}
{% block title %}Kup punkty{% endblock %}
{% block content %}
    <h1 class="text-center">Kup punkty</h1>
    <p class="text-center">Wybierz pakiet (symulacja):</p>
    <form method="POST" class="col-md-6 mx-auto">
        <div class="mb-3">
            <label class="form-label">Pakiet</label>
            <select name="points" class="form-select">
                <option value="10">10 punktów</option>
                <option value="50">50 punktów</option>
                <option value="100">100 punktów</option>
            </select>
        </div>
        <button type="submit" class="btn btn-primary"><i class="bi bi-cart"></i> Kup</button>
    </form>
    <p class="text-center mt-3"><a href="{{ url_for('profile') }}">Wróć do profilu</a></p>
{% endblock %}
"""

# Trasy
@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/register', methods=['GET', 'POST'])
@handle_db_errors
def register():
    if request.method == 'POST':
        if not validate_form(request.form):
            return redirect(url_for('register'))
        user = User(
            username=request.form['username'].strip(),
            email=request.form['email'].strip().lower(),
            password=generate_password_hash(request.form['password']),
            skills_offered=request.form.get('skills_offered', '').strip() or None,
            skills_wanted=request.form.get('skills_wanted', '').strip() or None,
            location=request.form.get('location', '').strip() or None,
            category=request.form.get('category', '') or None,
            points=10
        )
        db.session.add(user)
        db.session.commit()
        logging.info(f'Rejestracja: {user.username}')
        flash('Rejestracja udana! Zaloguj się.')
        return redirect(url_for('login'))
    return render_template_string(REGISTER_HTML, categories=SKILL_CATEGORIES.keys())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email'].lower()).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            logging.info(f'Logowanie: {user.username}')
            return redirect(url_for('profile'))
        flash('Błędny email lub hasło!')
        return redirect(url_for('login'))
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
@login_required
def logout():
    logging.info(f'Wylogowanie: {current_user.username}')
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@app.route('/profile/<int:user_id>')
@login_required
def user_profile(user_id=None):
    user = User.query.get_or_404(user_id or current_user.id)
    sessions = Session.query.filter((Session.teacher_id == user.id) | (Session.student_id == user.id)).all() if user.id == current_user.id else []
    stats = {
        'sessions': len(sessions),
        'messages': Message.query.filter((Message.sender_id == user.id) | (Message.receiver_id == user.id)).count()
    }
    return render_template_string(PROFILE_HTML, user=user, sessions=sessions, stats=stats)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
@handle_db_errors
def edit_profile():
    if request.method == 'POST':
        if not validate_form(request.form, is_register=False):
            return redirect(url_for('edit_profile'))
        current_user.username = request.form['username'].strip()
        current_user.skills_offered = request.form.get('skills_offered', '').strip() or None
        current_user.category = request.form.get('category', '') or None
        current_user.skills_wanted = request.form.get('skills_wanted', '').strip() or None
        current_user.location = request.form.get('location', '').strip() or None
        db.session.commit()
        logging.info(f'Edycja profilu: {current_user.username}')
        flash('Profil zaktualizowany!')
        return redirect(url_for('profile'))
    return render_template_string(EDIT_PROFILE_HTML, user=current_user, categories=SKILL_CATEGORIES)

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'POST':
        query = User.query
        if skill := request.form.get('skill', '').strip().lower():
            query = query.filter(User.skills_offered.ilike(f'%{skill}%'))
        if category := request.form.get('category', '').strip():
            query = query.filter(User.category == category)
        if location := request.form.get('location', '').strip().lower():
            query = query.filter(User.location.ilike(f'%{location}%'))
        users = query.filter(User.id != current_user.id).all()
        return render_template_string(SEARCH_HTML, users=users, categories=SKILL_CATEGORIES)
    return render_template_string(SEARCH_HTML, categories=SKILL_CATEGORIES)

@app.route('/session/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
@handle_db_errors
def session(teacher_id):
    teacher = User.query.get_or_404(teacher_id)
    if teacher_id == current_user.id:
        flash('Nie możesz umówić sesji z samym sobą!')
        return redirect(url_for('search'))
    if request.method == 'POST':
        skill = request.form['skill'].strip()
        if len(skill) < 2:
            flash('Umiejętność musi mieć co najmniej 2 znaki!')
            return redirect(url_for('session', teacher_id=teacher_id))
        if current_user.points < 5:
            flash('Potrzeba 5 punktów!')
            return redirect(url_for('session', teacher_id=teacher_id))
        if Session.query.filter_by(teacher_id=teacher_id, student_id=current_user.id, status='pending').first():
            flash('Masz już oczekującą sesję!')
            return redirect(url_for('profile'))
        session = Session(teacher_id=teacher_id, student_id=current_user.id, skill=skill, category=teacher.category)
        current_user.points -= 5
        teacher.notifications += 1
        db.session.add(session)
        db.session.commit()
        logging.info(f'Sesja: {current_user.username} z {teacher.username}')
        flash('Sesja umówiona!')
        return redirect(url_for('profile'))
    return render_template_string(SESSION_HTML, teacher=teacher)

@app.route('/update_session/<int:session_id>/<action>')
@login_required
@handle_db_errors
def update_session(session_id, action):
    session = Session.query.get_or_404(session_id)
    if session.teacher_id != current_user.id:
        flash('Brak uprawnień!')
        return redirect(url_for('profile'))
    if action == 'accept':
        session.status = 'accepted'
    elif action == 'reject':
        session.status = 'rejected'
        User.query.get(session.student_id).points += 5
    elif action == 'complete':
        session.status = 'completed'
        teacher = User.query.get(session.teacher_id)
        teacher.points += 10
        if Session.query.filter_by(teacher_id=teacher.id, status='completed').count() >= 10 and 'Mistrz Nauczania' not in (teacher.badges or ''):
            teacher.badges = (teacher.badges or '') + ',Mistrz Nauczania'
    db.session.commit()
    flash(f'Sesja: {action}')
    return redirect(url_for('profile'))

@app.route('/rate_session/<int:session_id>', methods=['POST'])
@login_required
@handle_db_errors
def rate_session(session_id):
    session = Session.query.get_or_404(session_id)
    if session.student_id != current_user.id or session.status != 'completed' or session.rating:
        flash('Nie możesz ocenić tej sesji!')
        return redirect(url_for('profile'))
    rating = int(request.form['rating'])
    if rating < 1 or rating > 5:
        flash('Ocena od 1 do 5!')
        return redirect(url_for('profile'))
    session.rating = rating
    teacher = User.query.get(session.teacher_id)
    teacher.rating_count += 1
    teacher.rating = ((teacher.rating * (teacher.rating_count - 1)) + rating) / teacher.rating_count
    teacher.notifications += 1
    db.session.commit()
    flash('Sesja oceniona!')
    return redirect(url_for('profile'))

@app.route('/messages', methods=['GET'])
@app.route('/messages/<int:receiver_id>', methods=['GET', 'POST'])
@login_required
@handle_db_errors
def messages(receiver_id=None):
    if request.method == 'POST':
        content = request.form['content'].strip()
        if not content:
            flash('Wiadomość nie może być pusta!')
            return redirect(url_for('messages', receiver_id=receiver_id))
        receiver = User.query.get_or_404(receiver_id)
        db.session.add(Message(sender_id=current_user.id, receiver_id=receiver_id, content=content))
        receiver.notifications += 1
        current_user.points += 1
        db.session.commit()
        flash('Wiadomość wysłana!')
        return redirect(url_for('messages', receiver_id=receiver_id))
    if receiver_id:
        unread = Message.query.filter_by(receiver_id=current_user.id, sender_id=receiver_id, is_read=False).all()
        for msg in unread:
            msg.is_read = True
        current_user.notifications = max(0, current_user.notifications - len(unread))
        db.session.commit()
    conversations = db.session.query(
        User.id.label('user_id'), User.username,
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
        receiver = User.query.get_or_404(receiver_id)
    return render_template_string(MESSAGES_HTML, conversations=conversations, messages=messages, receiver=receiver, receiver_id=receiver_id)

@app.route('/send_message/<int:receiver_id>')
@login_required
def send_message(receiver_id):
    return redirect(url_for('messages', receiver_id=receiver_id))

@app.route('/buy_points', methods=['GET', 'POST'])
@login_required
@handle_db_errors
def buy_points():
    if request.method == 'POST':
        current_user.points += int(request.form['points'])
        db.session.commit()
        flash(f'Dodano punkty!')
        return redirect(url_for('profile'))
    return render_template_string(BUY_POINTS_HTML)

@app.route('/clear_notifications')
@login_required
@handle_db_errors
def clear_notifications():
    current_user.notifications = 0
    db.session.commit()
    flash('Powiadomienia wyczyszczone!')
    return redirect(url_for('profile'))

# Inicjalizacja bazy danych
if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            logging.info("Baza danych zainicjalizowana.")
        except Exception as e:
            logging.error(f"Błąd inicjalizacji bazy danych: {str(e)}")
    app.run(debug=True, host='0.0.0.0', port=5000)
