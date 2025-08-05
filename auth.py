from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

# Импортируем db и модели из основного приложения
from models import db, User

# Создаем Blueprint для аутентификации
auth_bp = Blueprint('auth', __name__, url_prefix='')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        
        # Проверка существования пользователя
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует!', 'error')
            return redirect(url_for('auth.register'))
        
        # Создание нового пользователя (ученика)
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            is_teacher=False
        )
        user.set_password(password) # Этот метод определен в models.py
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password): # Этот метод определен в models.py
            login_user(user)
            flash('Вы успешно вошли в систему!', 'success')
            # Перенаправляем на dashboard после входа
            return redirect(url_for('main.dashboard'))
        else:
            flash('Неверный email или пароль!', 'error')
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы!', 'info')
    return redirect(url_for('main.index'))
