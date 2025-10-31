from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

def start_keyboard():
    return ReplyKeyboardMarkup([["Хочу узнать больше"]], resize_keyboard=True)

def presentation_keyboard():
    buttons = [
        [InlineKeyboardButton("Административная гибкость", callback_data='admin_flex')],
        [InlineKeyboardButton("Индивидуальный подход", callback_data='individual')],
        [InlineKeyboardButton("Прозрачность и системность", callback_data='transparency')],
        [InlineKeyboardButton("Теперь мне всё понятно!", callback_data='next')]
    ]
    return InlineKeyboardMarkup(buttons)

def skills_keyboard():
    return ReplyKeyboardMarkup([["Хард", "Софт", "Селф"]], resize_keyboard=True, one_time_keyboard=True)

def qa_keyboard():
    return ReplyKeyboardMarkup(
        [["Хочу присоединиться к вам"], ["У меня остались вопросы"]],
        resize_keyboard=True
    )