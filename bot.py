# bot.py — telegram-bot for the language school (python-telegram-bot v20+)
import logging
import sqlite3
import os
import asyncio
from typing import Dict, Any, Optional
from config import BOT_TOKEN, password
from decorator import send_test_email

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== НАСТРОЙКИ (заполнить) ==================
TOKEN = BOT_TOKEN
BASE_DIR = os.path.dirname(__file__)

# Папки с медиа
VIDEOS_DIR = os.path.join(BASE_DIR, "assets")
IMAGES_DIR = os.path.join(BASE_DIR, "assets")

# Файлы
WELCOME_VIDEO = os.path.join(VIDEOS_DIR, "welcome.mp4")
SPEECH_VIDEO = os.path.join(VIDEOS_DIR, "speech_tips.mp4")
SOFT_SKILLS_VIDEO = os.path.join(VIDEOS_DIR, "soft_skills_intro.mp4")
SKILLS_PYRAMID_IMAGE = os.path.join(IMAGES_DIR, "skills_pyramid.jpg")

# Почта администратора и SMTP
ADMIN_EMAIL = "gleb.krasnow@ya.ru"
SMTP_HOST = "smtp.yandex.ru"
SMTP_PORT = 465
SMTP_USER = "gleb.krasnow@ya.ru"
SMTP_PASSWORD = "Wellewonka5898"
FROM_EMAIL = SMTP_USER

# База данных
DB_PATH = os.path.join(BASE_DIR, "bot_data.db")
# =========================================================

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Последовательность шагов по ТЗ
STEPS = [
    "speech",        # Заголовок «Свободная и грамотная речь...»
    "soft_skills",   # Мягкие навыки
    "comfort",       # Комфортное поддерживающее пространство
    "method",        # Как будем действовать? (методика)
    "parent",        # Что требуется от родителя?
    "homework",      # Метод 4П — домашка
    "features",      # Особенности восточных языков
]

# ========================= БД ===========================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER UNIQUE,
        username TEXT
    )
    """
    )
    c.execute(
        """
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        who TEXT,
        language TEXT,
        age TEXT,
        class TEXT,
        format TEXT,
        level TEXT,
        experience TEXT,
        goal TEXT,
        comments TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )
    conn.commit()
    conn.close()


def save_application(chat_id: int, username: Optional[str], form: Dict[str, Any]) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (chat_id, username) VALUES (?, ?)", (chat_id, username)
    )
    c.execute("SELECT id FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    user_id = row[0] if row else None
    c.execute(
        """
    INSERT INTO applications
    (user_id, who, language, age, class, format, level, experience, goal, comments)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            user_id,
            form.get("who"),
            form.get("language"),
            form.get("age"),
            form.get("class"),
            form.get("format"),
            form.get("level"),
            form.get("experience"),
            form.get("goal"),
            form.get("comments"),
        ),
    )
    conn.commit()
    conn.close()


# ========================= Email ===========================
def send_email(subject: str, body: str, to_email: str = ADMIN_EMAIL) -> None:
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            if SMTP_PORT == 587:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(msg["From"], [msg["To"]], msg.as_string())
        logger.info("Email sent to %s", to_email)
    except Exception as e:
        logger.exception("Failed to send email: %s", e)


# ========================= UI helpers ===========================
def nav_keyboard(step_name: str) -> InlineKeyboardMarkup:
    """
    Возвращает 4 кнопки: Далее, Подробнее, Назад, Сразу к анкете
    callback_data формат: 'next:<step>', 'details:<step>', 'back:<step>', 'form'
    """
    if step_name in ['speech', 'method']:
        idx = STEPS.index(step_name) if step_name in STEPS else 0
        next_idx = min(idx + 1, len(STEPS) - 1)
        back_idx = max(idx - 1, 0)
        buttons = [
            [
                InlineKeyboardButton("Далее ▶️", callback_data=f"next:{STEPS[next_idx]}"),
            ],
            [
                InlineKeyboardButton("Назад ◀️", callback_data=f"back:{STEPS[back_idx]}"),
                InlineKeyboardButton("Сразу к анкете 📝", callback_data="form"),
            ],
        ]
    else:
        idx = STEPS.index(step_name) if step_name in STEPS else 0
        next_idx = min(idx + 1, len(STEPS) - 1)
        back_idx = max(idx - 1, 0)
        buttons = [
            [
                InlineKeyboardButton("Далее ▶️", callback_data=f"next:{STEPS[next_idx]}"),
                InlineKeyboardButton("Подробнее ℹ️", callback_data=f"details:{step_name}"),
            ],
            [
                InlineKeyboardButton("Назад ◀️", callback_data=f"back:{STEPS[back_idx]}"),
                InlineKeyboardButton("Сразу к анкете 📝", callback_data="form"),
            ],
        ]
    return InlineKeyboardMarkup(buttons)


def simple_button(text: str, callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=callback)]])


# ========================= Отправка контента ===========================
async def try_send_video(bot, chat_id: int, path: str, caption: Optional[str] = None):
    if path and os.path.isfile(path):
        try:
            with open(path, "rb") as f:
                await bot.send_video(chat_id=chat_id, video=f, caption=caption)
            return True
        except Exception as e:
            logger.exception("Error sending video %s: %s", path, e)
            await bot.send_message(chat_id=chat_id, text=f"[Видео {os.path.basename(path)} недоступно]")
            return False
    else:
        await bot.send_message(chat_id=chat_id, text=f"[Видео не найдено: {path}]")
        return False


async def try_send_photo(bot, chat_id: int, path: str, caption: Optional[str] = None):
    if path and os.path.isfile(path):
        try:
            with open(path, "rb") as f:
                await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
            return True
        except Exception as e:
            logger.exception("Error sending photo %s: %s", path, e)
            await bot.send_message(chat_id=chat_id, text=f"[Картинка {os.path.basename(path)} недоступна]")
            return False
    else:
        await bot.send_message(chat_id=chat_id, text=f"[Картинка не найдена: {path}]")
        return False


# ========================= Handlers ===========================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — отправляем приветственное видео и кнопку 'Хочу узнать больше'"""
    chat_id = update.effective_chat.id
    # Сбросим пользовательские данные
    context.user_data.clear()

    # Попытка отправки видео
    sent = await try_send_video(context.bot, chat_id, WELCOME_VIDEO, "")
    # Если видео не отправили — отправим текст
    if not sent:
        await context.bot.send_message(chat_id=chat_id, text="Привет! (видео отсутствует)")

    # Кнопка "Хочу узнать больше"
    await context.bot.send_message(
        chat_id=chat_id,
        text="Нажмите «Хочу узнать больше», чтобы пройти дальше.",
        reply_markup=simple_button("Хочу узнать больше", "go_speech"),
    )
    # Установим шаг для пользователя (необязательно)
    context.user_data["current_step"] = "speech"


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех callback_data — маршрутизирует по шагам."""
    query = update.callback_query
    assert query is not None
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    # Навигация по шагам
    if data == "go_speech":
        context.user_data["current_step"] = "speech"
        await show_speech_step(chat_id, context)
        return

    if data.startswith("next:") or data.startswith("back:") or data.startswith("details:"):
        mode, step = data.split(":", 1)
        context.user_data["current_step"] = step
        if mode == "next" or mode == "back":
            await show_step(step, chat_id, context)
        else:  # details
            await show_details(step, chat_id, context)
        return

    if data == "form":
        # Начинаем заполнение анкеты
        await start_form(chat_id, context)
        return

    # Кнопки после отправки анкеты (ссылки)
    if data == "site":
        await context.bot.send_message(chat_id=chat_id, text="Откройте сайт: https://alterny.ru/")
        return
    if data == "socials":
        await context.bot.send_message(chat_id=chat_id, text="Наши соцсети:\nVK: https://vk.com/alternyschool\nTG: https://t.me/schoolAlterny")
        return
    if data == "memo":
        await context.bot.send_message(chat_id=chat_id, text="Скачать памятку: https://tchkrosta.ru/pamyatka.pdf")
        return


async def show_step(step_name: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает основной контент для шага (без детального пояснения)."""
    bot = context.bot
    if step_name == "speech":
        await bot.send_message(chat_id=chat_id, text="*Свободная и грамотная речь на языке — как этого достичь?*", parse_mode="Markdown")
        await try_send_video(bot, chat_id, SPEECH_VIDEO, "Наши кредо:\n"
                                                         "- Язык невозможно выучить однажды раз и навсегда\n"
                                                         "- Сложного языка не бывает\n"
                                                         "- Верим в талант каждого\n", )
        # next keyboard
        await bot.send_message(chat_id=chat_id, text="Готовы дальше?", reply_markup=nav_keyboard("speech"))

    elif step_name == "soft_skills":
        await bot.send_message(chat_id=chat_id, text="*Мягкие навыки — это про что?*", parse_mode="Markdown")
        await try_send_video(bot, chat_id, SOFT_SKILLS_VIDEO, "")
        await try_send_photo(bot, chat_id, SKILLS_PYRAMID_IMAGE, "Пирамида навыков")
        # краткий перечень
        await bot.send_message(chat_id=chat_id, text="Мягкие навыки — это ваши человеческие умения, "
                                                     "которые делают вас не просто специалистом, а хорошим сотрудником, "
                                                     "надежным коллегой и приятным человеком.", reply_markup=nav_keyboard("soft_skills"))
    elif step_name == "comfort":
        await bot.send_message(chat_id=chat_id, text="*Комфортное поддерживающее пространство — это что?*", parse_mode="Markdown")
        await bot.send_message(chat_id=chat_id, text=(
            "- Административная гибкость\n"
            "- Защита интересов ребёнка\n"
            "- Индивидуальный подход\n"
            "- Прозрачность процесса\n"
            "- Системность\n"
        ))
        await bot.send_message(chat_id=chat_id, text="Узнать больше?", reply_markup=nav_keyboard("comfort"))

    elif step_name == "method":
        await bot.send_message(chat_id=chat_id, text="*Как будем действовать?*", parse_mode="Markdown")
        await bot.send_message(chat_id=chat_id, text=(
            "Наш основной инструмент — системно-деятельностная методика полного языкового погружения и проживания смыслов, это:\n"
            "1. Отсутствие языкового барьера\n"
            "2. Готовность понимать иностранную речь на слух и вступать в коммуникацию на соответствующем уровне\n"
            "3. Ориентиры — международные экзамены\n"
            "4. Доказанная эффективность\n"
            "5. Природосообразность (естественность)\n\n"
            "Наш основной инструмент — Естественность:\n"
            "- Естественность процесса освоения языка\n"
            "- Естественность речи учителя\n"
            "- Естественность контекста"
        ))
        await bot.send_message(chat_id=chat_id, text="А что требуется от родителя?", reply_markup=nav_keyboard("method"))

    elif step_name == "parent":
        await bot.send_message(chat_id=chat_id, text="*А что требуется от родителя?*", parse_mode="Markdown")
        await bot.send_message(chat_id=chat_id, text=(
            "Если Вы родитель, то от Вас нужны только сущие мелочи:\n"
            "1. Грамотная поддержка процесса, понимание всех членов семьи\n"
            "2. Техническое обеспечение\n"
            "3. Регулярное прослушивание/напоминание\n"
            "4. Отклик на обратную связь\n"
            "5. Поощрение творческого подхода в ДЗ\n"
        ))
        await bot.send_message(chat_id=chat_id, text="Продолжим?", reply_markup=nav_keyboard("parent"))

    elif step_name == "homework":
        await bot.send_message(chat_id=chat_id, text="*Про домашние задания — Метод 4П*", parse_mode="Markdown")
        await bot.send_message(chat_id=chat_id, text=(
            "В домашнем задании используем «Метод 4П»:\n"
            "1. Послушайте\n2. Проживите\n3. Повторите\n4. Перепишите\n\n"
            "Это значит, что каждый день (кроме дней занятий) нужно сделать домашку, высланную педагогом."
        ))
        await bot.send_message(chat_id=chat_id, text="Дальше?", reply_markup=nav_keyboard("homework"))

    elif step_name == "features":
        await bot.send_message(chat_id=chat_id, text="*Особенности восточных языков*", parse_mode="Markdown")
        await bot.send_message(chat_id=chat_id, text="Здесь — краткий текст про особенности восточных языков.")
        # Кнопка перехода к анкете
        await bot.send_message(chat_id=chat_id, text="Готовы к анкете?", reply_markup=simple_button("Перейдем к анкете", "form"))
    else:
        await context.bot.send_message(chat_id=chat_id, text="Упс... Ошибка")


async def show_speech_step(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await show_step("speech", chat_id, context)


async def show_details(step_name: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показываем расширенное пояснение для шага"""
    bot = context.bot
    if step_name == "comfort":
        await bot.send_message(chat_id=chat_id, text=(
            "*Административная гибкость:* варианты расписания, переносы занятий и т.п.\n\n"
            "*Защита интересов ребёнка:* педагог выбирает задания, соответствующие уровню и темпу ребёнка.\n\n"
            "*Индивидуальный подход:* план обучения под конкретного ученика.\n\n"
            "*Прозрачность:* родитель всегда видит программу и результаты.\n\n"
            "*Системность:* обучение построено по шагам и повторениям."
        ), parse_mode="Markdown")
    elif step_name == "soft_skills":
        await bot.send_message(chat_id=chat_id, text=(
            "Мягкие навыки (или гибкие навыки, социальные навыки) — это неспециализированные, но очень важные умения, которые помогают человеку эффективно взаимодействовать с другими людьми, управлять собой и успешно решать задачи в любой сфере. Это про то, КАК вы работаете и общаетесь, а не про ваши конкретные профессиональные знания.\n\n"
            "Простыми словами это:\n"
            "1.  Умение ладить с людьми: Находить общий язык с коллегами, клиентами, начальством. Быть вежливым, уважительным, приятным в общении.\n"
            "2.  Умение работать в команде: Действовать сообща, помогать другим, делиться идеями, не тянуть одеяло на себя, доверять коллегам.\n"
            "3.  Умение ясно говорить и писать: Объяснять свои мысли понятно, слушать других, задавать вопросы, писать сообщения без ошибок и так, чтобы тебя поняли.\n"
            "4.  Умение решать проблемы: Не паниковать при трудностях, спокойно искать разные варианты выхода из сложной ситуации, анализировать.\n"
            "5.  Умение управлять своим временем: Успевать делать важные дела к сроку, не откладывать на потом, планировать свой день.\n"
            "6.  Умение справляться со стрессом: Не срываться, когда что-то пошло не так, сохранять спокойствие и работоспособность под давлением.\n"
            "7.  Умение учиться новому: Быть открытым к новым знаниям, не бояться спрашивать, уметь быстро осваивать новые программы или подходы.\n"
            "8.  Умение приспосабливаться: Легко переключаться между задачами, спокойно реагировать на изменения (в планах, требованиях, технологиях).\n"
            "9.  Критическое мышление: Не верить всему на слово, уметь анализировать информацию, видеть плюсы и минусы, делать собственные выводы.\n"
            "10. Ответственность: Выполнять свои обещания, отвечать за свою работу и поступки, признавать ошибки.\n\n"
            "Почему они важны?\n"
            "*   Работают везде: Они нужны и врачу, и программисту, и продавцу, и учителю.\n"
            "*   Помогают строить карьеру: Часто именно мягкие навыки, а не только твердые знания, помогают получить повышение или новую работу.\n"
            "*   Делают работу эффективнее: Когда люди умеют договариваться, работать вместе и решать проблемы, дела идут лучше.\n"
            "*   Создают комфортную атмосферу: С человеком, у которого развиты мягкие навыки, приятно и легко работать."
        ), parse_mode="Markdown")
    elif step_name == "homework":
        await bot.send_message(chat_id=chat_id, text=(
            "В домашнем задании используем «Метод 4П»:\n"
            "1. Послушайте \n"
            "2. Проживите \n"
            "3. Повторите \n"
            "4. Перепишите \n\n"
            "Это значит, что каждый день (кроме дней, когда есть занятия по языку) "
            "нужно сделать домашку, высланную педагогом в день занятия, бла бла бла…."
        ), parse_mode="Markdown")
    else:
        # Для остальных шагов можно показать более подробный текст
        await bot.send_message(chat_id=chat_id, text=f"[Подробнее про {step_name}] — более развёрнутая информация здесь.")
    # после деталей — показываем навигационную клавиатуру текущего шага
    await bot.send_message(chat_id=chat_id, text="Продолжим?", reply_markup=nav_keyboard(step_name))


# ========================= Анкета ===========================
FORM_QUESTIONS = [
    ("who", "Кто будет заниматься? Напишите: 'Я сам' или 'Я отдаю ребенка'"),
    ("language", "Какой язык вас интересует?"),
    ("age", "Возраст (числом) или диапазон"),
    ("class", "Класс (если применимо)"),
    ("format", "Формат: онлайн / оффлайн / гибрид"),
    ("level", "Уровень языка (Нулевой / Начинающий / Средний / Продвинутый)"),
    ("experience", "Языковой опыт (школьный англ., билингвальная семья, геймерский англ., смотрим мультики и т.д.)"),
    ("goal", "Цель изучения (вкратце)"),
    ("comments", "Комментарии (если есть)"),
]


async def start_form(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Инициализация формы и первый вопрос"""
    context.user_data["in_form"] = True
    context.user_data["form"] = {}
    context.user_data["form_step"] = 0
    # убрать inline-клавиатуру и дать простой ввод
    await context.bot.send_message(chat_id=chat_id, text="Начинаем анкету. Ответьте на вопросы по порядку. Можно ввести '-' если поле оставить пустым.")
    question = FORM_QUESTIONS[0][1]
    # Для удобства — показываем быстрые варианты для первого вопроса
    reply_kb = ReplyKeyboardMarkup([["Я сам"], ["Я отдаю ребенка"]], one_time_keyboard=True, resize_keyboard=True)
    await context.bot.send_message(chat_id=chat_id, text=question, reply_markup=reply_kb)


async def form_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текстовых сообщений во время заполнения анкеты"""
    if not context.user_data.get("in_form"):
        # Игнорируем, если не в форме
        return

    text = update.message.text.strip()
    step_idx = int(context.user_data.get("form_step", 0))
    key = FORM_QUESTIONS[step_idx][0]
    # сохраняем ответ
    context.user_data["form"][key] = text
    step_idx += 1
    context.user_data["form_step"] = step_idx

    if step_idx < len(FORM_QUESTIONS):
        # задаём следующий вопрос
        qtext = FORM_QUESTIONS[step_idx][1]
        # при следующих вопросах уберём ReplyKeyboard
        await update.message.reply_text(qtext, reply_markup=ReplyKeyboardRemove())
    else:
        # форма заполнена
        form = context.user_data.get("form", {})
        chat_id = update.effective_chat.id
        user = update.effective_user
        # Сохраняем в БД
        try:
            save_application(user.id, user.username, form)
            print("=== Отправка письма через Яндекс ===")
            # Данные для отправки
            test_recipients = ['gleb.krasnow@ya.ru']  # Отправляем себе для теста
            test_subject = "Новая анкета"
            form_body = ("Пользователь заполнил новую анкету:"
                         f"{form}")

            print(f"Отправитель: gleb.krasnow@ya.ru")
            print(f"Получатель: {test_recipients[0]}")
            print(f"Тема: {test_subject}")
            print("-" * 50)

            # Отправка письма
            send_test_email(form_body)
        except Exception as e:
            logger.exception("Failed saving application to DB: %s", e)
        # Отправляем на почту администратору (синхронная, но быстрая) — запускаем в отдельном потоке
        subject = "Новая заявка из Telegram-бота"
        body_lines = [f"{k}: {v}" for k, v in form.items()]
        body = f"Новая заявка от {user.username} (chat_id={user.id}):\n\n" + "\n".join(body_lines)

        # Отправим email асинхронно, чтобы не блокировать обработчик
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, send_email, subject, body, ADMIN_EMAIL)

        # Подтвердим пользователю и предложим ссылки
        await update.message.reply_text("Ваша анкета успешно отправлена! Пока мы её изучаем, вы можете:", reply_markup=ReplyKeyboardRemove())
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Изучить наш сайт", url="https://tchkrosta.ru")],
                [InlineKeyboardButton("Посетить наши соцсети", url="https://vk.com")],
                [InlineKeyboardButton("Скачать памятку родителя", url="https://tchkrosta.ru/pamyatka.pdf")],
            ]
        )
        await update.message.reply_text("Выберите:", reply_markup=kb)
        # Сброс состояния формы
        context.user_data.pop("in_form", None)
        context.user_data.pop("form", None)
        context.user_data.pop("form_step", None)
        # Также можно уведомить администратора внутри Telegram (если есть ADMIN_CHAT_ID)
        # Но мы используем email по ТЗ


# ========================= Misc handlers ===========================
async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сообщения вне формы и не кнопок — даём подсказку"""
    if context.user_data.get("in_form"):
        # формы обрабатываются в form_message_handler
        return
    await update.message.reply_text("Нажмите /start чтобы начать диалог с ботом или используйте кнопки.")


# ========================= Main ===========================
def main():
    # Инициализация БД
    init_db()
    # Проверки путей (подсказки в лог)
    for p in (WELCOME_VIDEO, SPEECH_VIDEO, SOFT_SKILLS_VIDEO, SKILLS_PYRAMID_IMAGE):
        if not os.path.isfile(p):
            logger.warning("Медиа-файл не найден: %s", p)

    if TOKEN == "ВАШ_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("Пожалуйста, укажите TOKEN в начале файла.")
        return

    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(callback_router))
    # message handler for form (text) - must be before unknown handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, form_message_handler))
    # fallback for unknown messages
    application.add_handler(MessageHandler(filters.ALL, unknown_message))

    logger.info("Bot started (polling)...")
    application.run_polling()


if __name__ == "__main__":
    main()
