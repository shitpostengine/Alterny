import sqlite3


def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()

    # Создаем таблицы
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  chat_id INTEGER UNIQUE,
                  username TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS applications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  language TEXT,
                  mode TEXT,
                  age INTEGER,
                  level TEXT)''')
    conn.commit()
    conn.close()


def save_application(chat_id, username, data):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()

    # Сохраняем пользователя
    c.execute("INSERT OR IGNORE INTO users (chat_id, username) VALUES (?, ?)",
              (chat_id, username))

    # Получаем ID пользователя
    c.execute("SELECT id FROM users WHERE chat_id = ?", (chat_id,))
    user_id = c.fetchone()[0]

    # Сохраняем заявку
    c.execute("INSERT INTO applications (user_id, language, mode, age, level) VALUES (?, ?, ?, ?, ?)",
              (user_id, data['language'], data['mode'], data['age'], data['level']))

    conn.commit()
    conn.close()
    return True