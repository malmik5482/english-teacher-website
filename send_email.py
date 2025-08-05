#!/usr/bin/env python3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sys
import os

def send_test_email():
    """Отправка тестового email через Gmail"""
    
    # Настройки (замените на свои)
    sender_email = "malmik1277@gmail.com"
    sender_password = "pgzb rrpm suco rjyz"  # Ваш пароль приложения
    recipient_email = "malmik1277@gmail.com"
    
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = "Тест отправки email - Резервное копирование"
        
        # Текст сообщения
        body = """
        Здравствуйте!
        
        Это тестовое сообщение от системы резервного копирования сайта преподавателя английского языка.
        
        Если вы получили это сообщение, значит настройки почты работают корректно.
        
        С уважением,
        Система резервного копирования
        """
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Подключаемся к серверу Gmail
        print("Подключение к серверу Gmail...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.set_debuglevel(1)  # Включаем отладку
        server.starttls()
        print("Авторизация...")
        server.login(sender_email, sender_password)
        print("Отправка сообщения...")
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        print("✅ Тестовое сообщение успешно отправлено!")
        print(f"Проверьте почту: {recipient_email}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при отправке email: {e}")
        return False

if __name__ == "__main__":
    print("=== Тест отправки email ===")
    success = send_test_email()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
