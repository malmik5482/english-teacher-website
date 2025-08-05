from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz # Для функции to_dict в Message

# Создаем экземпляр SQLAlchemy. Он будет инициализирован в app.py
db = SQLAlchemy()

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
    
    # Связи
    group_memberships = db.relationship('GroupMember', back_populates='user', lazy=True, cascade='all, delete-orphan')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', back_populates='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', back_populates='recipient', lazy=True)
    homework_files = db.relationship('StudentHomeworkFile', back_populates='student', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        # Импортируем здесь, так как check_password_hash уже импортирован
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
    
    # Связи
    members = db.relationship('GroupMember', back_populates='group', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])

# Модель участников групп
class GroupMember(db.Model):
    __tablename__ = 'group_member'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    group = db.relationship('Group', back_populates='members')
    user = db.relationship('User', back_populates='group_memberships')
    
    # Уникальность: пользователь может быть в группе только один раз
    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='unique_group_member'),)

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
    
    # Связи
    group = db.relationship('Group', foreign_keys=[group_id])
    student = db.relationship('User', foreign_keys=[student_id])
    creator = db.relationship('User', foreign_keys=[created_by])

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
    
    # Связи
    group = db.relationship('Group', foreign_keys=[group_id])
    student = db.relationship('User', foreign_keys=[student_id])
    schedule = db.relationship('Schedule', foreign_keys=[schedule_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    files = db.relationship('HomeworkFile', back_populates='homework', lazy=True, cascade='all, delete-orphan')
    student_files = db.relationship('StudentHomeworkFile', back_populates='homework', lazy=True, cascade='all, delete-orphan')

# Модель файлов домашних заданий (от преподавателя)
class HomeworkFile(db.Model):
    __tablename__ = 'homework_file'
    id = db.Column(db.Integer, primary_key=True)
    homework_id = db.Column(db.Integer, db.ForeignKey('homework.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # image, document, etc.
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь
    homework = db.relationship('Homework', back_populates='files')
    
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
    
    # Связи
    homework = db.relationship('Homework', back_populates='student_files')
    student = db.relationship('User', back_populates='homework_files')
    
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
    
    # Связи
    homework = db.relationship('Homework', foreign_keys=[homework_id])
    student = db.relationship('User', foreign_keys=[student_id])
    
    # Уникальность: ученик может иметь только один статус для каждого задания
    __table_args__ = (db.UniqueConstraint('homework_id', 'student_id', name='unique_student_homework'),)

# Модель файлов в чате
class ChatFile(db.Model):
    __tablename__ = 'chat_file'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # image, document, etc.
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь с сообщением
    message = db.relationship('Message', back_populates='files')
    
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
    
    # Связи
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='received_messages')
    files = db.relationship('ChatFile', back_populates='message', lazy=True)
    
    def to_dict(self):
        # Конвертируем время в локальное время пользователя
        # pytz уже импортирован в начале файла
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
            'files': [file.to_dict() for file in self.files]
        }
