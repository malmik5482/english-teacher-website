from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import shutil
import zipfile
import sqlalchemy
import traceback

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///english_teacher.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Максимальный размер файла 16MB

# Создаем папку для загрузок если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

# Делаем модели и datetime доступными в шаблонах
@app.context_processor
def inject_models():
    return {
        'StudentHomeworkStatus': StudentHomeworkStatus,
        'datetime': datetime
    }

# === МОДЕЛИ БАЗЫ ДАННЫХ ===

# Модель пользователя
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    is_teacher = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи (используем back_populates для избежания конфликтов)
    group_memberships_rel = db.relationship('GroupMember', back_populates='user', lazy=True, cascade='all, delete-orphan')
    sent_messages_rel = db.relationship('Message', foreign_keys='Message.sender_id', back_populates='sender', lazy=True)
    received_messages_rel = db.relationship('Message', foreign_keys='Message.recipient_id', back_populates='recipient', lazy=True)
    homework_files_rel = db.relationship('StudentHomeworkFile', back_populates='student', lazy=True, cascade='all, delete-orphan')
    created_groups_rel = db.relationship('Group', foreign_keys='Group.created_by', back_populates='creator')
    created_schedules_rel = db.relationship('Schedule', foreign_keys='Schedule.created_by', back_populates='creator')
    created_homeworks_rel = db.relationship('Homework', foreign_keys='Homework.created_by', back_populates='creator')
    homework_statuses_as_student_rel = db.relationship('StudentHomeworkStatus', foreign_keys='StudentHomeworkStatus.student_id', back_populates='student')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'

# Модель уроков
class Lesson(db.Model):
    __tablename__ = 'lesson'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    age_group = db.Column(db.String(50), nullable=True)
    duration = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Модель контента сайта (для CMS)
class SiteContent(db.Model):
    __tablename__ = 'site_content'
    id = db.Column(db.Integer, primary_key=True)
    page_name = db.Column(db.String(50), nullable=False)
    section_name = db.Column(db.String(50), nullable=False)
    content_key = db.Column(db.String(100), nullable=False)
    content_value = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Модель постов блога
class BlogPost(db.Model):
    __tablename__ = 'blog_post'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(200), nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Модель заявок на обучение
class Application(db.Model):
    __tablename__ = 'application'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    child_age = db.Column(db.String(50), nullable=True)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

# Модель групп
class Group(db.Model):
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_individual = db.Column(db.Boolean, default=False)  # Индивидуальные занятия
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Связи (используем back_populates)
    members_rel = db.relationship('GroupMember', back_populates='group', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by], back_populates='created_groups_rel')
    schedules_rel = db.relationship('Schedule', back_populates='group')
    homeworks_rel = db.relationship('Homework', back_populates='group')

# Модель участников групп
class GroupMember(db.Model):
    __tablename__ = 'group_member'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Уникальность: пользователь может быть в группе только один раз
    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='unique_group_member'),)
    
    # Связи (используем back_populates)
    group = db.relationship('Group', back_populates='members_rel')
    user = db.relationship('User', back_populates='group_memberships_rel')

# Модель расписания
class Schedule(db.Model):
    __tablename__ = 'schedule'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи (используем back_populates)
    group = db.relationship('Group', back_populates='schedules_rel')
    student = db.relationship('User', foreign_keys=[student_id])
    creator = db.relationship('User', foreign_keys=[created_by], back_populates='created_schedules_rel')
    homeworks_linked_rel = db.relationship('Homework', back_populates='schedule')

# Модель домашних заданий
class Homework(db.Model):
    __tablename__ = 'homework'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи (используем back_populates)
    group = db.relationship('Group', back_populates='homeworks_rel')
    student = db.relationship('User', foreign_keys=[student_id])
    schedule = db.relationship('Schedule', back_populates='homeworks_linked_rel')
    creator = db.relationship('User', foreign_keys=[created_by], back_populates='created_homeworks_rel')
    files_rel = db.relationship('HomeworkFile', back_populates='homework', lazy=True, cascade='all, delete-orphan')
    student_files_rel = db.relationship('StudentHomeworkFile', back_populates='homework', lazy=True, cascade='all, delete-orphan')
    statuses_rel = db.relationship('StudentHomeworkStatus', back_populates='homework', lazy=True, cascade='all, delete-orphan')

# Модель файлов домашних заданий (от преподавателя)
class HomeworkFile(db.Model):
    __tablename__ = 'homework_file'
    id = db.Column(db.Integer, primary_key=True)
    homework_id = db.Column(db.Integer, db.ForeignKey('homework.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # image, document, etc.
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь (используем back_populates)
    homework = db.relationship('Homework', back_populates='files_rel')
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat()
        }

# Модель файлов выполненных домашних заданий (от учеников)
class StudentHomeworkFile(db.Model):
    __tablename__ = 'student_homework_file'
    id = db.Column(db.Integer, primary_key=True)
    homework_id = db.Column(db.Integer, db.ForeignKey('homework.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # image, document, etc.
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    comment = db.Column(db.Text, nullable=True)
    
    # Связи (используем back_populates)
    homework = db.relationship('Homework', back_populates='student_files_rel')
    student = db.relationship('User', back_populates='homework_files_rel')
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat(),
            'comment': self.comment
        }

# Модель статусов домашних заданий у учеников
class StudentHomeworkStatus(db.Model):
    __tablename__ = 'student_homework_status'
    id = db.Column(db.Integer, primary_key=True)
    homework_id = db.Column(db.Integer, db.ForeignKey('homework.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='assigned')  # assigned, in_progress, completed, has_issues
    teacher_status = db.Column(db.String(20), default='sent')  # sent, under_review, reviewed
    submitted_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Уникальность: ученик может иметь только один статус для каждого задания
    __table_args__ = (db.UniqueConstraint('homework_id', 'student_id', name='unique_student_homework'),)
    
    # Связи (используем back_populates)
    homework = db.relationship('Homework', back_populates='statuses_rel')
    student = db.relationship('User', foreign_keys=[student_id], back_populates='homework_statuses_as_student_rel')

# Модель файлов в чате
class ChatFile(db.Model):
    __tablename__ = 'chat_file'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # image, document, etc.
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь с сообщением (используем back_populates)
    message = db.relationship('Message', back_populates='files_rel')
    
    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat()
        }

# Модель сообщений (чат)
class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи (используем back_populates)
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages_rel')
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='received_messages_rel')
    files_rel = db.relationship('ChatFile', back_populates='message', lazy=True)
    
    def to_dict(self):
        # Конвертируем время в локальное время пользователя
        local_tz = pytz.timezone('Europe/Moscow')  # Измените на ваш часовой пояс
        utc_time = self.created_at
        if utc_time.tzinfo is None:
            utc_time = pytz.utc.localize(utc_time)
        local_time = utc_time.astimezone(local_tz)
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'sender_name': f"{self.sender.first_name} {self.sender.last_name}",
            'content': self.content,
            'is_read': self.is_read,
            'created_at': local_time.isoformat(),
            'files': [file.to_dict() for file in self.files_rel]
        }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Получение контента сайта из базы данных
def get_site_content(page_name, section_name, content_key, default_value=''):
    content = SiteContent.query.filter_by(
        page_name=page_name,
        section_name=section_name,
        content_key=content_key
    ).first()
    return content.content_value if content else default_value

# Сохранение контента сайта в базу данных
def save_site_content(page_name, section_name, content_key, content_value):
    content = SiteContent.query.filter_by(
        page_name=page_name,
        section_name=section_name,
        content_key=content_key
    ).first()
    if content:
        content.content_value = content_value
        content.updated_at = datetime.utcnow()
    else:
        content = SiteContent(
            page_name=page_name,
            section_name=section_name,
            content_key=content_key,
            content_value=content_value
        )
        db.session.add(content)
    db.session.commit()

# Функции резервного копирования
def backup_database():
    """Функция резервного копирования"""
    try:
        # Создаем имя файла с датой
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}"
        backup_path = f"backups/{backup_filename}"
        
        # Создаем папку для резервных копий если её нет
        os.makedirs('backups', exist_ok=True)
        
        # Копируем базу данных
        if os.path.exists('english_teacher.db'):
            shutil.copy2('english_teacher.db', f"{backup_path}.db")
            print(f"База данных скопирована: {backup_path}.db")
        
        # Копируем папку uploads
        if os.path.exists('static/uploads'):
            shutil.copytree('static/uploads', f"{backup_path}_uploads", dirs_exist_ok=True)
            print(f"Папка uploads скопирована: {backup_path}_uploads")
        
        # Создаем ZIP архив
        zip_filename = f"{backup_path}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Добавляем базу данных
            if os.path.exists(f"{backup_path}.db"):
                zipf.write(f"{backup_path}.db", f"{backup_filename}.db")
            # Добавляем файлы из uploads
            if os.path.exists(f"{backup_path}_uploads"):
                for root, dirs, files in os.walk(f"{backup_path}_uploads"):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, f"{backup_path}_uploads")
                        zipf.write(file_path, f"uploads/{arc_path}")
        
        # Удаляем временные файлы
        if os.path.exists(f"{backup_path}.db"):
            os.remove(f"{backup_path}.db")
        if os.path.exists(f"{backup_path}_uploads"):
            shutil.rmtree(f"{backup_path}_uploads")
        
        print(f"Резервная копия создана: {zip_filename}")
        return zip_filename
    except Exception as e:
        print(f"Ошибка при создании резервной копии: {e}")
        traceback.print_exc()
        return None

def send_backup_email(backup_file, recipient_email):
    """Отправка резервной копии на email"""
    try:
        # Для тестирования - используйте свои данные
        from_email = "your_email@gmail.com"  # Замените на ваш email
        password = "your_app_password"       # Замените на пароль приложения
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = recipient_email
        msg['Subject'] = f"Резервная копия сайта - {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        
        # Текст сообщения
        body = f"""
        Здравствуйте!
        Это автоматическая резервная копия сайта преподавателя английского языка.
        Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        В архиве содержатся:
        - База данных сайта
        - Все загруженные файлы (изображения, документы)
        С уважением,
        Система резервного копирования
        """
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Прикрепляем файл
        if backup_file and os.path.exists(backup_file):
            with open(backup_file, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(backup_file)}'
            )
            msg.attach(part)
        
        # Подключаемся к SMTP серверу и отправляем
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(from_email, password)
        text = msg.as_string()
        server.sendmail(from_email, recipient_email, text)
        server.quit()
        
        print(f"Резервная копия отправлена на {recipient_email}")
        return True
    except Exception as e:
        print(f"Ошибка при отправке email: {e}")
        traceback.print_exc()
        return False

def cleanup_old_backups(max_backups=30):
    """Удаление старых резервных копий"""
    try:
        if not os.path.exists('backups'):
            return
        
        # Получаем список всех файлов
        files = [f for f in os.listdir('backups') if f.endswith('.zip')]
        files.sort(key=lambda x: os.path.getctime(os.path.join('backups', x)), reverse=True)
        
        # Удаляем старые файлы
        for file in files[max_backups:]:
            os.remove(os.path.join('backups', file))
            print(f"Удалена старая резервная копия: {file}")
    except Exception as e:
        print(f"Ошибка при очистке старых резервных копий: {e}")
        traceback.print_exc()

def daily_backup():
    """Ежедневное резервное копирование"""
    print(f"Начинаем ежедневное резервное копирование: {datetime.now()}")
    
    # Создаем резервную копию
    backup_file = backup_database()
    if backup_file:
        # Отправляем на email преподавателя
        recipient_email = "sal-olga@mail.ru"  # Email преподавателя
        if send_backup_email(backup_file, recipient_email):
            print("Резервная копия успешно создана и отправлена!")
        else:
            print("Резервная копия создана, но не отправлена на email")
        
        # Очищаем старые резервные копии
        cleanup_old_backups()
    else:
        print("Ошибка при создании резервной копии")

# === МАРШРУТЫ ===

@app.route('/')
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

@app.route('/services')
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

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/blog')
def blog():
    posts = BlogPost.query.filter_by(is_published=True).order_by(BlogPost.created_at.desc()).all()
    return render_template('blog.html', posts=posts)

# Отправка заявки на обучание
@app.route('/submit_application', methods=['POST'])
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

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
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
            return redirect(url_for('register'))
        
        # Создание нового пользователя (ученика)
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            is_teacher=False
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный email или пароль!', 'error')
    
    return render_template('login.html')

# Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы!', 'info')
    return redirect(url_for('index'))

# Личный кабинет
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# Обновление профиля
@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    phone = request.form['phone']
    current_user.phone = phone
    db.session.commit()
    flash('Профиль успешно обновлен!', 'success')
    return redirect(url_for('dashboard'))

# Админ панель
@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('admin_panel.html', users=users, posts=posts)

# Ученики (админ) - ИСПРАВЛЕННАЯ ФУНКЦИЯ
@app.route('/admin/students', methods=['GET', 'POST'])
@login_required
def admin_students():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Обработка добавления ученика в группу
    if request.method == 'POST':
        group_id = request.form.get('group_id')
        student_ids = request.form.getlist('student_ids')
        
        if group_id and student_ids:
            for student_id in student_ids:
                # Проверяем, что пользователь существует и не является преподавателем
                student = User.query.filter_by(id=student_id, is_teacher=False).first()
                if student:
                    # Проверяем, что студент еще не в группе
                    existing_member = GroupMember.query.filter_by(group_id=group_id, user_id=student_id).first()
                    if not existing_member:
                        member = GroupMember(group_id=group_id, user_id=student_id)
                        db.session.add(member)
            db.session.commit()
            flash('Ученики успешно добавлены в группу!', 'success')
            return redirect(url_for('admin_students'))
    
    # Получаем всех учеников (не преподавателей)
    students = User.query.filter_by(is_teacher=False).order_by(User.last_name).all()
    
    # Получаем все группы с количеством участников
    groups_with_counts = db.session.query(
        Group,
        db.func.count(GroupMember.id).label('member_count')
    ).outerjoin(GroupMember).filter(Group.is_individual == False).group_by(Group.id).all()
    
    # Получаем индивидуальные занятия с количеством участников
    individual_groups_with_counts = db.session.query(
        Group,
        db.func.count(GroupMember.id).label('member_count')
    ).outerjoin(GroupMember).filter(Group.is_individual == True).group_by(Group.id).all()
    
    return render_template('admin_students.html', 
                         students=students, 
                         groups_with_counts=groups_with_counts,
                         individual_groups_with_counts=individual_groups_with_counts)

# Группы (админ)
@app.route('/admin/groups')
@login_required
def admin_groups():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем все группы с количеством участников
    groups = db.session.query(
        Group,
        db.func.count(GroupMember.id).label('member_count')
    ).outerjoin(GroupMember).group_by(Group.id).all()
    
    return render_template('admin_groups.html', groups=groups)

# Создание группы
@app.route('/admin/groups/create', methods=['POST'])
@login_required
def create_group():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    name = request.form.get('name')
    description = request.form.get('description')
    is_individual = request.form.get('is_individual') == 'on'
    
    if not name:
        flash('Название группы обязательно!', 'error')
        return redirect(url_for('admin_groups'))
    
    group = Group(
        name=name,
        description=description,
        is_individual=is_individual,
        created_by=current_user.id
    )
    db.session.add(group)
    db.session.commit()
    
    flash('Группа успешно создана!', 'success')
    return redirect(url_for('admin_groups'))

# Удаление участника из группы
@app.route('/admin/groups/<int:group_id>/remove_member/<int:member_id>')
@login_required
def remove_group_member(group_id, member_id):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    member = GroupMember.query.get_or_404(member_id)
    if member.group_id != group_id:
        flash('Ошибка: участник не принадлежит этой группе!', 'error')
        return redirect(url_for('admin_groups'))
    
    db.session.delete(member)
    db.session.commit()
    
    flash('Участник успешно удален из группы!', 'success')
    return redirect(url_for('admin_groups'))

# Просмотр группы
@app.route('/admin/groups/<int:group_id>')
@login_required
def view_group(group_id):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    group = Group.query.get_or_404(group_id)
    members = GroupMember.query.filter_by(group_id=group_id).all()
    # Получаем всех учеников для возможности добавления
    all_students = User.query.filter_by(is_teacher=False).all()
    
    return render_template('view_group.html', group=group, members=members, all_students=all_students)

# Расписание преподавателя
@app.route('/admin/schedule')
@login_required
def admin_schedule():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем все события расписания на ближайшие 30 дней
    from datetime import timedelta
    start_date = datetime.now()
    end_date = start_date + timedelta(days=30)
    events = Schedule.query.filter(
        Schedule.start_time >= start_date,
        Schedule.start_time <= end_date
    ).order_by(Schedule.start_time).all()
    
    # Получаем группы и учеников для добавления в расписание
    groups = Group.query.all()
    students = User.query.filter_by(is_teacher=False).all()
    
    return render_template('admin_schedule.html', events=events, groups=groups, students=students)

# Создание события в расписании
@app.route('/admin/schedule/create', methods=['POST'])
@login_required
def create_schedule_event():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    title = request.form.get('title')
    description = request.form.get('description')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    group_id = request.form.get('group_id')
    
    if not title or not start_time or not end_time:
        flash('Заполните все обязательные поля!', 'error')
        return redirect(url_for('admin_schedule'))
    
    try:
        # Преобразуем строки в datetime
        start_dt = datetime.fromisoformat(start_time.replace('T', ' '))
        end_dt = datetime.fromisoformat(end_time.replace('T', ' '))
        
        # Проверяем, что время начала раньше времени окончания
        if start_dt >= end_dt:
            flash('Время начала должно быть раньше времени окончания!', 'error')
            return redirect(url_for('admin_schedule'))
        
        # Обрабатываем group_id - может быть None, число или строка student_X
        group_id_int = None
        student_id_int = None
        if group_id:
            if group_id.startswith('student_'):
                # Это индивидуальное занятие для конкретного ученика
                student_id_int = int(group_id.replace('student_', ''))
            else:
                # Это группа
                group_id_int = int(group_id)
        
        # Создаем событие
        event = Schedule(
            title=title,
            description=description,
            start_time=start_dt,
            end_time=end_dt,
            group_id=group_id_int,
            student_id=student_id_int,
            created_by=current_user.id
        )
        db.session.add(event)
        db.session.commit()
        
        flash('Событие успешно добавлено в расписание!', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(f'Ошибка в данных: {str(e)}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении события: {str(e)}', 'error')
    
    return redirect(url_for('admin_schedule'))

# Удаление события из расписания
@app.route('/admin/schedule/delete/<int:event_id>')
@login_required
def delete_schedule_event(event_id):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    event = Schedule.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    
    flash('Событие успешно удалено из расписания!', 'success')
    return redirect(url_for('admin_schedule'))

# Домашние задания преподавателя
@app.route('/admin/homework')
@login_required
def admin_homework():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем все домашние задания
    homeworks = Homework.query.order_by(Homework.created_at.desc()).all()
    # Получаем группы и учеников для добавления заданий
    groups = Group.query.all()
    students = User.query.filter_by(is_teacher=False).all()
    schedules = Schedule.query.filter(Schedule.start_time >= datetime.now()).order_by(Schedule.start_time).all()
    
    return render_template('admin_homework.html', homeworks=homeworks, groups=groups, students=students, schedules=schedules)

# Создание домашнего задания
@app.route('/admin/homework/create', methods=['POST'])
@login_required
def create_homework():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    title = request.form.get('title')
    description = request.form.get('description')
    deadline = request.form.get('deadline')
    group_id = request.form.get('group_id')
    student_id = request.form.get('student_id')
    schedule_id = request.form.get('schedule_id')
    
    if not title:
        flash('Название задания обязательно!', 'error')
        return redirect(url_for('admin_homework'))
    
    try:
        # Преобразуем deadline в datetime если он есть
        deadline_dt = None
        if deadline:
            deadline_dt = datetime.fromisoformat(deadline.replace('T', ' '))
        
        # Обрабатываем group_id и student_id
        group_id_int = None
        student_id_int = None
        schedule_id_int = None
        if group_id:
            group_id_int = int(group_id)
        if student_id:
            student_id_int = int(student_id)
        if schedule_id:
            schedule_id_int = int(schedule_id)
        
        # Создаем домашнее задание
        homework = Homework(
            title=title,
            description=description,
            deadline=deadline_dt,
            group_id=group_id_int,
            student_id=student_id_int,
            schedule_id=schedule_id_int,
            created_by=current_user.id
        )
        db.session.add(homework)
        db.session.flush()  # Получаем ID домашнего задания
        
        # Создаем статусы для учеников, избегая дубликатов
        try:
            if student_id_int:
                # Проверяем, существует ли уже статус для этой пары
                existing_status = StudentHomeworkStatus.query.filter_by(
                    homework_id=homework.id,
                    student_id=student_id_int
                ).first()
                if not existing_status:
                    # Индивидуальное задание
                    status = StudentHomeworkStatus(
                        homework_id=homework.id,
                        student_id=student_id_int,
                        status='assigned',
                        teacher_status='sent'
                    )
                    db.session.add(status)
            elif group_id_int:
                # Групповое задание
                group_members = GroupMember.query.filter_by(group_id=group_id_int).all()
                for member in group_members:
                    # Проверяем, существует ли уже статус для этой пары
                    existing_status = StudentHomeworkStatus.query.filter_by(
                        homework_id=homework.id,
                        student_id=member.user_id
                    ).first()
                    if not existing_status:
                        status = StudentHomeworkStatus(
                            homework_id=homework.id,
                            student_id=member.user_id,
                            status='assigned',
                            teacher_status='sent'
                        )
                        db.session.add(status)
            
            # Обработка загрузки файлов
            if 'files' in request.files:
                files = request.files.getlist('files')
                for file in files:
                    if file and file.filename != '':
                        # Определяем тип файла
                        if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                            file_type = 'image'
                        elif file.filename.lower().endswith(('.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx')):
                            file_type = 'document'
                        else:
                            file_type = 'other'
                        
                        # Создаем уникальное имя файла
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"homework_{timestamp}_{file.filename}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        
                        # Сохраняем файл
                        file.save(file_path)
                        
                        # Создаем запись в базе данных
                        homework_file = HomeworkFile(
                            homework_id=homework.id,
                            filename=file.filename,
                            file_path=f"uploads/{filename}",
                            file_type=file_type
                        )
                        db.session.add(homework_file)
            
            db.session.commit()
            flash('Домашнее задание успешно создано!', 'success')
        except sqlalchemy.exc.IntegrityError as e:
            # Откатываем транзакцию в случае ошибки уникальности
            db.session.rollback()
            flash('Ошибка при создании домашнего задания: возможно, статус уже существует.', 'error')
            return redirect(url_for('admin_homework'))
        except Exception as e:
            # Откатываем транзакцию в случае любой другой ошибки
            db.session.rollback()
            flash(f'Ошибка при создании домашнего задания: {str(e)}', 'error')
            return redirect(url_for('admin_homework'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при создании домашнего задания: {str(e)}', 'error')
        return redirect(url_for('admin_homework'))
    
    return redirect(url_for('admin_homework'))

# Удаление домашнего задания
@app.route('/admin/homework/delete/<int:homework_id>')
@login_required
def delete_homework(homework_id):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    homework = Homework.query.get_or_404(homework_id)
    db.session.delete(homework)
    db.session.commit()
    
    flash('Домашнее задание успешно удалено!', 'success')
    return redirect(url_for('admin_homework'))

# Обновление статуса домашнего задания у ученика (преподаватель)
@app.route('/admin/homework/<int:homework_id>/student/<int:student_id>/status', methods=['POST'])
@login_required
def update_student_homework_status(homework_id, student_id):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    teacher_status = request.form.get('teacher_status')
    review_notes = request.form.get('review_notes')
    
    # Получаем или создаем статус
    status = StudentHomeworkStatus.query.filter_by(
        homework_id=homework_id,
        student_id=student_id
    ).first()
    
    if not status:
        status = StudentHomeworkStatus(
            homework_id=homework_id,
            student_id=student_id
        )
        db.session.add(status)
    
    status.teacher_status = teacher_status
    status.review_notes = review_notes
    status.reviewed_at = datetime.utcnow()
    
    db.session.commit()
    flash('Статус домашнего задания обновлен!', 'success')
    return redirect(url_for('admin_homework'))

# Расписание ученика
@app.route('/student/schedule')
@login_required
def student_schedule():
    if current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем события для ученика (индивидуальные занятия и занятия его группы)
    individual_events = Schedule.query.filter_by(student_id=current_user.id).all()
    
    # Получаем события группы ученика
    group_events = []
    group_member = GroupMember.query.filter_by(user_id=current_user.id).first()
    if group_member:
        group_events = Schedule.query.filter_by(group_id=group_member.group_id).all()
    
    # Объединяем события и сортируем по времени
    all_events = individual_events + group_events
    all_events.sort(key=lambda x: x.start_time)
    
    return render_template('student_schedule.html', events=all_events)

# Домашние задания ученика
@app.route('/student/homework')
@login_required
def student_homework():
    if current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем индивидуальные домашние задания
    individual_homeworks = Homework.query.filter_by(student_id=current_user.id).all()
    
    # Получаем домашние задания группы ученика
    group_homeworks = []
    group_member = GroupMember.query.filter_by(user_id=current_user.id).first()
    if group_member:
        group_homeworks = Homework.query.filter_by(group_id=group_member.group_id).all()
    
    # Объединяем и сортируем по дате создания
    all_homeworks = individual_homeworks + group_homeworks
    all_homeworks.sort(key=lambda x: x.created_at, reverse=True)
    
    # Получаем статусы для каждого задания
    homework_statuses = {}
    for homework in all_homeworks:
        status = StudentHomeworkStatus.query.filter_by(
            homework_id=homework.id,
            student_id=current_user.id
        ).first()
        if not status:
            # Создаем статус если его нет
            status = StudentHomeworkStatus(
                homework_id=homework.id,
                student_id=current_user.id,
                status='assigned',
                teacher_status='sent'
            )
            db.session.add(status)
            db.session.commit()
        homework_statuses[homework.id] = status
    
    return render_template('student_homework.html', 
                         homeworks=all_homeworks, 
                         homework_statuses=homework_statuses)

# Обновление статуса домашнего задания у ученика
@app.route('/student/homework/<int:homework_id>/status', methods=['POST'])
@login_required
def update_my_homework_status(homework_id):
    if current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    status_value = request.form.get('status')
    
    # Получаем или создаем статус
    status = StudentHomeworkStatus.query.filter_by(
        homework_id=homework_id,
        student_id=current_user.id
    ).first()
    
    if not status:
        status = StudentHomeworkStatus(
            homework_id=homework_id,
            student_id=current_user.id,
            status=status_value,
            teacher_status='sent'
        )
        db.session.add(status)
    else:
        status.status = status_value
        status.submitted_at = datetime.utcnow()
    
    db.session.commit()
    flash('Статус домашнего задания обновлен!', 'success')
    return redirect(url_for('student_homework'))

# Просмотр домашнего задания учеником
@app.route('/student/homework/<int:homework_id>')
@login_required
def view_student_homework(homework_id):
    if current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем домашнее задание
    homework = Homework.query.get_or_404(homework_id)
    
    # Проверяем доступ к заданию
    has_access = False
    if homework.student_id == current_user.id:
        # Индивидуальное задание для этого ученика
        has_access = True
    else:
        # Проверяем, есть ли задание для группы ученика
        group_member = GroupMember.query.filter_by(user_id=current_user.id).first()
        if group_member and homework.group_id == group_member.group_id:
            has_access = True
    
    if not has_access:
        flash('У вас нет доступа к этому домашнему заданию!', 'error')
        return redirect(url_for('student_homework'))
    
    # Получаем статус ученика
    status = StudentHomeworkStatus.query.filter_by(
        homework_id=homework_id,
        student_id=current_user.id
    ).first()
    
    if not status:
        # Создаем статус если его нет
        status = StudentHomeworkStatus(
            homework_id=homework_id,
            student_id=current_user.id,
            status='assigned',
            teacher_status='sent'
        )
        db.session.add(status)
        db.session.commit()
    
    # Получаем файлы ученика по этому заданию
    student_files = StudentHomeworkFile.query.filter_by(
        homework_id=homework_id,
        student_id=current_user.id
    ).all()
    
    return render_template('view_student_homework.html', 
                         homework=homework, 
                         status=status,
                         student_files=student_files)

# Загрузка файла учеником для домашнего задания
@app.route('/student/homework/<int:homework_id>/upload', methods=['POST'])
@login_required
def upload_student_homework_file(homework_id):
    if current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем домашнее задание
    homework = Homework.query.get_or_404(homework_id)
    
    # Проверяем доступ к заданию
    has_access = False
    if homework.student_id == current_user.id:
        # Индивидуальное задание для этого ученика
        has_access = True
    else:
        # Проверяем, есть ли задание для группы ученика
        group_member = GroupMember.query.filter_by(user_id=current_user.id).first()
        if group_member and homework.group_id == group_member.group_id:
            has_access = True
    
    if not has_access:
        flash('У вас нет доступа к этому домашнему заданию!', 'error')
        return redirect(url_for('student_homework'))
    
    try:
        # Обработка загрузки файлов
        if 'files' in request.files:
            files = request.files.getlist('files')
            comment = request.form.get('comment', '')
            for file in files:
                if file and file.filename != '':
                    # Определяем тип файла
                    if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        file_type = 'image'
                    elif file.filename.lower().endswith(('.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx')):
                        file_type = 'document'
                    else:
                        file_type = 'other'
                    
                    # Создаем уникальное имя файла
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"student_homework_{timestamp}_{file.filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Сохраняем файл
                    file.save(file_path)
                    
                    # Создаем запись в базе данных
                    student_file = StudentHomeworkFile(
                        homework_id=homework_id,
                        student_id=current_user.id,
                        filename=file.filename,
                        file_path=f"uploads/{filename}",
                        file_type=file_type,
                        comment=comment
                    )
                    db.session.add(student_file)
            db.session.commit()
            flash('Файлы успешно загружены!', 'success')
        else:
            flash('Выберите файлы для загрузки!', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при загрузке файлов: {str(e)}', 'error')
    
    return redirect(url_for('view_student_homework', homework_id=homework_id))

# Удаление файла ученика
@app.route('/student/homework/file/<int:file_id>/delete')
@login_required
def delete_student_homework_file(file_id):
    if current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем файл
    student_file = StudentHomeworkFile.query.get_or_404(file_id)
    
    # Проверяем, что файл принадлежит текущему пользователю
    if student_file.student_id != current_user.id:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('student_homework'))
    
    try:
        # Удаляем файл с диска
        if os.path.exists(student_file.file_path):
            os.remove(student_file.file_path)
        
        # Удаляем запись из базы данных
        db.session.delete(student_file)
        db.session.commit()
        
        flash('Файл успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении файла: {str(e)}', 'error')
    
    return redirect(url_for('view_student_homework', homework_id=student_file.homework_id))

# Чат
@app.route('/chat')
@login_required
def chat():
    # Получаем все чаты пользователя (где он отправитель или получатель)
    sent_chats = db.session.query(User).join(Message, Message.recipient_id == User.id).filter(Message.sender_id == current_user.id).distinct().all()
    received_chats = db.session.query(User).join(Message, Message.sender_id == User.id).filter(Message.recipient_id == current_user.id).distinct().all()
    
    # Объединяем и убираем дубликаты
    all_chats = list(set(sent_chats + received_chats))
    
    # Получаем количество непрочитанных сообщений для каждого чата
    unread_counts = {}
    for chat_user in all_chats:
        unread_count = Message.query.filter(
            Message.sender_id == chat_user.id,
            Message.recipient_id == current_user.id,
            Message.is_read == False
        ).count()
        unread_counts[chat_user.id] = unread_count
    
    return render_template('chat.html', chats=all_chats, unread_counts=unread_counts)

# Чат с конкретным пользователем
@app.route('/chat/<int:user_id>')
@login_required
def chat_with_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Получаем сообщения между текущим пользователем и выбранным пользователем
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    # Помечаем сообщения как прочитанные
    for message in messages:
        if message.recipient_id == current_user.id and not message.is_read:
            message.is_read = True
    db.session.commit()
    
    return render_template('chat_room.html', user=user, messages=messages)

# Отправка сообщения
@app.route('/chat/send', methods=['POST'])
@login_required
def send_message():
    recipient_id = request.form.get('recipient_id')
    content = request.form.get('content')
    
    if not recipient_id:
        return jsonify({'error': 'Получатель обязателен'}), 400
    
    # Создаем сообщение
    message = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        content=content or ''  # Может быть пустым, если отправляем только файл
    )
    db.session.add(message)
    db.session.flush()  # Получаем ID сообщения
    
    # Обработка загрузки файлов
    if 'files' in request.files:
        files = request.files.getlist('files')
        for file in files:
            if file and file.filename != '':
                # Определяем тип файла
                if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    file_type = 'image'
                elif file.filename.lower().endswith(('.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx')):
                    file_type = 'document'
                else:
                    file_type = 'other'
                
                # Создаем уникальное имя файла
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"chat_{timestamp}_{file.filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Сохраняем файл
                file.save(file_path)
                
                # Создаем запись в базе данных
                chat_file = ChatFile(
                    message_id=message.id,
                    filename=file.filename,
                    file_path=f"uploads/{filename}",
                    file_type=file_type
                )
                db.session.add(chat_file)
    
    db.session.commit()
    return jsonify({'success': 'Сообщение отправлено', 'message': message.to_dict()})

# Заявки на обучение (админ)
@app.route('/admin/applications')
@login_required
def admin_applications():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    status = request.args.get('status', 'all')
    if status == 'all':
        applications = Application.query.order_by(Application.created_at.desc()).all()
    else:
        applications = Application.query.filter_by(status=status).order_by(Application.created_at.desc()).all()
    
    return render_template('admin_applications.html', applications=applications, current_status=status)

# Изменение статуса заявки
@app.route('/admin/application/<int:app_id>/status/<status>')
@login_required
def change_application_status(app_id, status):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    application = Application.query.get_or_404(app_id)
    application.status = status
    if status != 'new':
        application.processed_at = datetime.utcnow()
        application.processed_by = current_user.id
    else:
        application.processed_at = None
        application.processed_by = None
    
    db.session.commit()
    flash('Статус заявки успешно изменен!', 'success')
    return redirect(url_for('admin_applications'))

# Редактирование пользователя (админ)
@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.first_name = request.form['first_name']
        user.last_name = request.form['last_name']
        user.email = request.form['email']
        user.phone = request.form['phone']
        user.is_teacher = 'is_teacher' in request.form
        
        # Если указан новый пароль
        new_password = request.form.get('password')
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash('Пользователь успешно обновлен!', 'success')
        return redirect(url_for('admin_panel'))
    
    return render_template('edit_user.html', user=user)

# Удаление пользователя (админ)
@app.route('/admin/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Запретить удаление самого себя
    if user.id == current_user.id:
        flash('Нельзя удалить свою учетную запись!', 'error')
        return redirect(url_for('admin_panel'))
    
    db.session.delete(user)
    db.session.commit()
    
    flash('Пользователь успешно удален!', 'success')
    return redirect(url_for('admin_panel'))

# Админ панель - управление контентом
@app.route('/admin/content')
@login_required
def admin_content():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем текущий контент
    content_data = {}
    contents = SiteContent.query.all()
    for content in contents:
        key = f"{content.page_name}_{content.section_name}_{content.content_key}"
        content_data[key] = content.content_value
    
    return render_template('admin_content.html', content_data=content_data)

# Сохранение контента через AJAX
@app.route('/admin/save_content', methods=['POST'])
@login_required
def save_content():
    if not current_user.is_teacher:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    try:
        data = request.get_json()
        page_name = data.get('page_name')
        section_name = data.get('section_name')
        content_key = data.get('content_key')
        content_value = data.get('content_value')
        
        save_site_content(page_name, section_name, content_key, content_value)
        return jsonify({'success': 'Контент успешно сохранен'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Блог - управление постами
@app.route('/admin/blog')
@login_required
def admin_blog():
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('admin_blog.html', posts=posts)

# Создание/редактирование поста
@app.route('/admin/blog/edit/<int:post_id>', methods=['GET', 'POST'])
@app.route('/admin/blog/create', methods=['GET', 'POST'])
@login_required
def edit_blog_post(post_id=None):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    if post_id:
        post = BlogPost.query.get_or_404(post_id)
    else:
        post = BlogPost()
    
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.is_published = 'is_published' in request.form
        
        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                filename = f"blog_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                post.image_path = f"uploads/{filename}"
        
        if not post_id:  # Новый пост
            db.session.add(post)
        db.session.commit()
        
        flash('Пост успешно сохранен!', 'success')
        return redirect(url_for('admin_blog'))
    
    return render_template('edit_blog_post.html', post=post)

# Удаление поста
@app.route('/admin/blog/delete/<int:post_id>')
@login_required
def delete_blog_post(post_id):
    if not current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    
    flash('Пост успешно удален!', 'success')
    return redirect(url_for('admin_blog'))

# Вкладка "Группа" для ученика
@app.route('/student/group')
@login_required
def student_group():
    if current_user.is_teacher:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('dashboard'))
    
    # Получаем группу ученика
    group_member = GroupMember.query.filter_by(user_id=current_user.id).first()
    if not group_member:
        flash('Вы не состоите в группе!', 'info')
        return redirect(url_for('dashboard'))
    
    group = group_member.group
    members = GroupMember.query.filter_by(group_id=group.id).all()
    
    return render_template('student_group.html', group=group, members=members)

# Создание преподавателя
def create_teacher():
    print("=== Создание учетной записи преподавателя ===")
    
    # Удаляем старого преподавателя, если он есть
    old_teachers = User.query.filter_by(is_teacher=True).all()
    for old_teacher in old_teachers:
        if old_teacher.email != 'sal-olga@mail.ru':
            print(f"Удаляем старого преподавателя: {old_teacher.email}")
            db.session.delete(old_teacher)
    
    # Проверяем, существует ли уже новый преподаватель
    teacher = User.query.filter_by(email='sal-olga@mail.ru').first()
    if teacher:
        print(f"Преподаватель уже существует: {teacher.email}")
        print(f"ID: {teacher.id}, Имя: {teacher.first_name} {teacher.last_name}")
        return teacher
    
    # Создаем учетную запись преподавателя Ольги Саликовой
    teacher = User(
        email='sal-olga@mail.ru',           # Email преподавателя
        first_name='Ольга',                 # Имя преподавателя
        last_name='Саликова',               # Фамилия преподавателя
        phone='+79991234567',               # Номер телефона
        is_teacher=True                     # Флаг, что это преподаватель
    )
    teacher.set_password('passwork')        # Пароль для входа
    
    print(f"Создаем нового преподавателя: {teacher.email}")
    db.session.add(teacher)
    db.session.commit()
    
    print("Учетная запись преподавателя Ольги Саликовой создана успешно!")
    print(f"Email: sal-olga@mail.ru, Пароль: passwork")
    return teacher

# Функция для отладки - показывает всех пользователей
def show_all_users():
    users = User.query.all()
    print("\n=== Все пользователи в базе данных ===")
    for user in users:
        print(f"ID: {user.id}, Email: {user.email}, Имя: {user.first_name} {user.last_name}, Преподаватель: {user.is_teacher}")
        if hasattr(user, 'password_hash') and user.password_hash:
            print(f"  Хэш пароля: {user.password_hash[:50]}...")
    print("=====================================\n")

if __name__ == '__main__':
    with app.app_context():
        # Создаем все таблицы в базе данных
        print("Создание таблиц в базе данных...")
        db.create_all()
        print("Таблицы созданы")
        
        # Создаем учетную запись преподавателя
        teacher = create_teacher()
        
        # Показываем всех пользователей для отладки
        show_all_users()
        
        # Создаем папку для резервных копий
        os.makedirs('backups', exist_ok=True)
    
    # Запускаем планировщик резервного копирования
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=daily_backup, trigger="cron", hour=2, minute=0)  # Ежедневно в 02:00
    scheduler.start()
    
    # Завершаем работу планировщика при выходе
    atexit.register(lambda: scheduler.shutdown())
    
    # Запускаем приложение
    print("Запуск Flask приложения...")
    app.run(host='0.0.0.0', port=5000, debug=False)
