import sqlite3
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    Updater, 
    CommandHandler, 
    MessageHandler, 
    CallbackContext, 
    CallbackQueryHandler,
    filters
)
from telegram.ext.filters import TEXT, COMMAND

# Настройки бота
TOKEN = ''
DB_NAME = 'quiz_bot.db'
YOUR_ADMIN_ID = 123456789 # id должен быть числом 

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            answered BOOLEAN DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            score INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

# Добавление пользователя в базу
def add_user(user):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, score)
        VALUES (?, ?, ?, ?, 0)
    ''', (user.id, user.username, user.first_name, user.last_name))
    
    conn.commit()
    conn.close()

# Получение случайного неотвеченного вопроса
def get_random_question():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, question, answer FROM questions WHERE answered = 0
    ''')
    
    questions = cursor.fetchall()
    conn.close()
    
    if questions:
        return random.choice(questions)
    return None

# Пометить вопрос как отвеченный
def mark_question_answered(question_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE questions SET answered = 1 WHERE id = ?
    ''', (question_id,))
    
    conn.commit()
    conn.close()

# Добавление балла пользователю
def add_score(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users SET score = score + 1 WHERE user_id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()

# Получение таблицы лидеров
def get_leaderboard():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT username, first_name, last_name, score FROM users
        ORDER BY score DESC
        LIMIT 10
    ''')
    
    leaders = cursor.fetchall()
    conn.close()
    
    return leaders

# Добавление нового вопроса (для админа)
def add_question(question, answer):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO questions (question, answer) VALUES (?, ?)
    ''', (question, answer))
    
    conn.commit()
    conn.close()

# Обработчик команды /start
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    add_user(user)
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я бот для викторины. "
        "Используй /quiz чтобы получить вопрос или /leaderboard чтобы увидеть таблицу лидеров."
    )

# Обработчик команды /quiz
async def quiz(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    add_user(user)
    
    question_data = get_random_question()
    
    if question_data:
        question_id, question, answer = question_data
        context.chat_data['current_question'] = (question_id, answer)
        
        await chat.send_message(
            f"Вопрос: {question}\n\n"
            "Отвечайте в чате! Первый правильный ответ получит балл."
        )
    else:
        await chat.send_message("Извините, нет доступных вопросов.")

# Обработчик сообщений (проверка ответов)
async def check_answer(update: Update, context: CallbackContext):
    chat = update.effective_chat
    user = update.effective_user
    message_text = update.message.text.lower().strip()
    
    if 'current_question' not in context.chat_data:
        return
    
    question_id, correct_answer = context.chat_data['current_question']
    correct_answer = correct_answer.lower().strip()
    
    if message_text.lower() == correct_answer.lower():
        add_user(user)
        add_score(user.id)
        mark_question_answered(question_id)
        
        del context.chat_data['current_question']
        
        await chat.send_message(
            f"Правильно, {user.first_name}! 🎉\n"
            f"Ты получаешь 1 балл. Твой текущий счет: {get_user_score(user.id)}"
        )

# Получение счета пользователя
def get_user_score(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT score FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else 0

# Обработчик команды /leaderboard
async def leaderboard(update: Update, context: CallbackContext):
    leaders = get_leaderboard()
    
    if not leaders:
        await update.message.reply_text("Таблица лидеров пуста.")
        return
    
    leaderboard_text = "🏆 Таблица лидеров:\n\n"
    for i, (username, first_name, last_name, score) in enumerate(leaders, 1):
        name = username or f"{first_name} {last_name}".strip()
        leaderboard_text += f"{i}. {name}: {score} баллов\n"
    
    await update.message.reply_text(leaderboard_text)

# Обработчик команды /add_question (только для админов)
async def add_question_command(update: Update, context: CallbackContext):
    user = update.effective_user
    
    # Проверка на админа (замените YOUR_ADMIN_ID на ваш ID)
    if user.id != YOUR_ADMIN_ID:
        await update.message.reply_text("Извините, эта команда только для администраторов.")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /add_question 'Вопрос' 'Ответ'")
        return
    
    question = ' '.join(context.args[:-1])
    answer = context.args[-1]
    
    add_question(question, answer)
    await update.message.reply_text(f"Вопрос добавлен: {question} (Ответ: {answer})")

def main():
    init_db()
    
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("add_question", add_question_command))
    
    # Обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer))
    
    application.run_polling()

if __name__ == '__main__':
    main()
