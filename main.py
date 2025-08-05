from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user # Импортируем login_required и current_user
from datetime import datetime

# Импортируем db и модели из основного приложения
from models import db, Lesson, BlogPost, Application, SiteContent

# Создаем Blueprint для основных маршрутов
main_bp = Blueprint('main', __name__, url_prefix='')

# Функция для получения контента сайта (скопирована из app.py)
def get_site_content(page_name, section_name, content_key, default_value=''):
    content = SiteContent.query.filter_by(
        page_name=page_name,
        section_name=section_name,
        content_key=content_key
    ).first()
    return content.content_value if content else default_value

@main_bp.route('/')
def index():
    # Получаем контент для главной страницы из базы данных
    hero_title = get_site_content('index', 'hero', 'title', 'Английский язык для детей')
    hero_subtitle = get_site_content('index', 'hero', 'subtitle', 'Индивидуальные занятия с опытным преподавателем')
    about_text = get_site_content('index', 'about', 'text', '''Здравствуйте! Меня зовут Саликова Ольга Александровна.
    Я преподаватель английского языка с более чем 8-летним опытом работы. Специализируюсь на обучении детей школьного возраста. 
    Моя методика основана на игровом подходе, что делает процесс обучения увлекательным и эффективным.''')
    
    return render_template('index.html', 
                         hero_title=hero_title,
                         hero_subtitle=hero_subtitle,
                         about_text=about_text)

@main_bp.route('/services')
def services():
    # Загружаем уроки из базы данных
    lessons = Lesson.query.all()
    if not lessons:
        lessons = [
            {
                'title': 'Английский для начинающих',
                'description': 'Основы грамматики и лексики для детей 7-10 лет',
                'age_group': '7-10 лет',
                'duration': '60 минут'
            },
            {
                'title': 'Разговорный английский',
                'description': 'Развитие навыков устной речи у детей 11-14 лет',
                'age_group': '11-14 лет',
                'duration': '90 минут'
            }
        ]
    return render_template('services.html', lessons=lessons)

@main_bp.route('/contacts')
def contacts():
    return render_template('contacts.html')

@main_bp.route('/blog')
def blog():
    posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.created_at.desc()).all()
    return render_template('blog.html', posts=posts)

# Отправка заявки на обучение
@main_bp.route('/submit_application', methods=['POST'])
def submit_application():
    try:
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        child_age = request.form.get('child_age')
        message = request.form.get('message')
        
        if not name or not phone:
            return jsonify({'error': 'Имя и телефон обязательны для заполнения'}), 400
        
        # Создаем новую заявку
        application = Application(
            name=name,
            phone=phone,
            email=email,
            child_age=child_age,
            message=message
        )
        db.session.add(application)
        db.session.commit()
        
        return jsonify({'success': 'Заявка успешно отправлена! Мы свяжемся с вами в ближайшее время.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Ошибка при отправке заявки. Попробуйте позже.'}), 500

# Личный кабинет
@main_bp.route('/dashboard')
@login_required  # Добавляем декоратор прямо здесь
def dashboard():
    return render_template('dashboard.html')

# Обновление профиля (оставляем в main, так как это общая функция)
@main_bp.route('/update_profile', methods=['POST'])
@login_required  # Добавляем декоратор прямо здесь
def update_profile():
    # from flask_login import current_user - уже импортирован выше
    phone = request.form['phone']
    current_user.phone = phone
    db.session.commit()
    flash('Профиль успешно обновлен!', 'success')
    return redirect(url_for('main.dashboard'))
