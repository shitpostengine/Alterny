import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import password
# КОНФИГУРАЦИЯ - ЗАПОЛНИТЕ ЭТИ ДАННЫЕ

def send_test_email(body):
    """Простой тест отправки email"""
    YANDEX_EMAIL = "botAlterny@yandex.ru"
    YANDEX_APP_PASSWORD = password
    EMAIL_TO = "gleb.krasnow@ya.ru"
    # Создаем письмо
    msg = MIMEMultipart()
    msg['From'] = YANDEX_EMAIL
    msg['To'] = EMAIL_TO  # Отправляем себе
    msg['Subject'] = "Тест отправки Python"

    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        print("🔄 Подключаемся к Яндекс SMTP...")

        # Подключаемся к серверу
        server = smtplib.SMTP('smtp.yandex.ru', 587)
        server.set_debuglevel(1)  # Включаем подробные логи

        print("🔐 Включаем шифрование...")
        server.starttls()

        print("🔑 Авторизуемся...")
        print(f"Email: {YANDEX_EMAIL}")
        print(f"Пароль приложения: {YANDEX_APP_PASSWORD}")

        server.login(YANDEX_EMAIL, YANDEX_APP_PASSWORD)

        print("📤 Отправляем письмо...")
        server.send_message(msg)

        print("🔒 Закрываем соединение...")
        server.quit()

        print("✅ Письмо успешно отправлено!")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Ошибка аутентификации: {e}")
        print("\nВозможные причины:")
        print("1. Неправильный пароль приложения")
        print("2. Яндекс временно заблокировал доступ")
        print("3. Не включен доступ по SMTP в настройках почты")
        return False

    except Exception as e:
        print(f"❌ Другая ошибка: {e}")
        return False


# Запускаем тест
if __name__ == "__main__":
    print("=== ТЕСТ ОТПРАВКИ ПИСЬМА ===")
    send_test_email()