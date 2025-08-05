import sqlite3
import os
import zipfile
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import shutil

def create_backup():
    """Создание резервной копии базы данных"""
    try:
        # Создаем имя файла с датой
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}"
        backup_path = f"backups/{backup_filename}"
        
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
        return None

def send_backup_email(backup_file, email_config):
    """Отправка резервной копии на email"""
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = email_config['from_email']
        msg['To'] = email_config['to_email']
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
        server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
        server.starttls()
        server.login(email_config['from_email'], email_config['password'])
        text = msg.as_string()
        server.sendmail(email_config['from_email'], email_config['to_email'], text)
        server.quit()
        
        print(f"Резервная копия отправлена на {email_config['to_email']}")
        return True
        
    except Exception as e:
        print(f"Ошибка при отправке email: {e}")
        return False

def cleanup_old_backups(max_backups=30):
    """Удаление старых резервных копий (оставляем только последние 30)"""
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

def backup_and_send():
    """Основная функция резервного копирования"""
    print(f"Начинаем создание резервной копии: {datetime.now()}")
    
    # Конфигурация email (измените на свои данные)
    email_config = {
        'from_email': 'your_email@gmail.com',  # Ваш email
        'to_email': 'recipient@gmail.com',     # Email получателя
        'password': 'your_app_password',       # Пароль приложения
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587
    }
    
    # Создаем резервную копию
    backup_file = create_backup()
    
    if backup_file:
        # Отправляем на email
        if send_backup_email(backup_file, email_config):
            print("Резервная копия успешно создана и отправлена!")
        else:
            print("Резервная копия создана, но не отправлена на email")
        
        # Очищаем старые резервные копии
        cleanup_old_backups()
    else:
        print("Ошибка при создании резервной копии")

if __name__ == "__main__":
    backup_and_send()
