import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from database import Database
from games.blackjack import BlackjackGame
from games.dice import DiceGame, DiceBet

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Проверка наличия токена
if not TOKEN:
    logger.error("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не установлен!")
    logger.error("Добавьте переменную окружения TELEGRAM_BOT_TOKEN")
    sys.exit(1)

# Инициализация БД
db = Database()

# Состояния для ConversationHandler
BET_AMOUNT, GAME_ACTION, DICE_BET_TYPE, DICE_BET_AMOUNT, DICE_TARGET = range(5)

# Словарь для хранения активных игр
active_games = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовая команда"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    welcome_message = (
        f"🎰 Добро пожаловать в Telegram Casino!\n\n"
        f"💰 Ваш баланс: {user['balance']} 💵\n\n"
        f"Выберите игру:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🃏 Блэкджек (21)", callback_data="game_blackjack")],
        [InlineKeyboardButton("🎲 Кости (Дайс)", callback_data="game_dice")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("💸 Пополнить баланс (тест)", callback_data="add_balance")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "game_blackjack":
        await ask_blackjack_bet(query, user_id)
    
    elif query.data == "game_dice":
        await show_dice_options(query, user_id)
    
    elif query.data == "stats":
        await show_stats(query, user_id)
    
    elif query.data == "add_balance":
        db.add_balance(user_id, 500)
        balance = db.get_balance(user_id)
        await query.edit_text(f"✅ Вам добавлено 500 💵\nНовый баланс: {balance} 💵")
    
    elif query.data.startswith("blackjack_bet_"):
        bet = int(query.data.split("_")[2])
        await start_blackjack(query, user_id, bet)
    
    elif query.data.startswith("blackjack_"):
        action = query.data.split("_")[1]
        await handle_blackjack_action(query, user_id, action)
    
    elif query.data.startswith("dice_bet_"):
        bet_type = query.data.split("_")[2]
        await handle_dice_bet(query, user_id, bet_type)
    
    elif query.data == "back_menu":
        await show_main_menu(query)


async def ask_blackjack_bet(query, user_id: int):
    """Просит выбрать ставку для Блэкджека"""
    balance = db.get_balance(user_id)
    
    message = f"💰 Выберите ставку\nВаш баланс: {balance} 💵"
    
    bets = [100, 250, 500, 1000]
    keyboard = []
    
    for bet in bets:
        if bet <= balance:
            keyboard.append(
                [InlineKeyboardButton(f"{bet} 💵", callback_data=f"blackjack_bet_{bet}")]
            )
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(message, reply_markup=reply_markup)


async def start_blackjack(query, user_id: int, bet: int):
    """Начинает игру в Блэкджек"""
    balance = db.get_balance(user_id)
    
    if bet > balance:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    # Создаём игру
    game = BlackjackGame(bet)
    active_games[user_id] = game
    
    # Отправляем текущее состояние
    status = game.get_status()
    
    keyboard = []
    if not game.game_over:
        keyboard = [
            [InlineKeyboardButton("🎴 Hit (взять карту)", callback_data="blackjack_hit")],
            [InlineKeyboardButton("🛑 Stand (отказаться)", callback_data="blackjack_stand")],
        ]
    else:
        keyboard = [[InlineKeyboardButton("◀️ Меню", callback_data="back_menu")]]
    
    keyboard.append([InlineKeyboardButton("❌ Выход", callback_data="back_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(f"🃏 БЛЭКДЖЕК\n\n{status}", reply_markup=reply_markup)


async def handle_blackjack_action(query, user_id: int, action: str):
    """Обрабатывает действия в Блэкджеке"""
    if user_id not in active_games:
        await query.answer("❌ Игра не активна", show_alert=True)
        return
    
    game = active_games[user_id]
    
    if action == "hit":
        if game.player_hit():
            if game.get_hand_value(game.player_hand) == 21:
                game.dealer_play()
        else:
            game.game_over = True
    
    elif action == "stand":
        game.dealer_play()
    
    # Получаем результат
    if game.game_over:
        result_type, winnings, message = game.result
        db.add_balance(user_id, winnings)
    
    status = game.get_status()
    
    keyboard = []
    if not game.game_over:
        keyboard = [
            [InlineKeyboardButton("🎴 Hit (взять карту)", callback_data="blackjack_hit")],
            [InlineKeyboardButton("🛑 Stand (отказаться)", callback_data="blackjack_stand")],
        ]
    else:
        balance = db.get_balance(user_id)
        keyboard = [
            [InlineKeyboardButton("🎰 Новая игра", callback_data="game_blackjack")],
            [InlineKeyboardButton("◀️ Меню", callback_data="back_menu")],
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(f"🃏 БЛЭКДЖЕК\n\n{status}", reply_markup=reply_markup)


async def show_dice_options(query, user_id: int):
    """Показывает опции для игры в кости"""
    balance = db.get_balance(user_id)
    
    message = f"🎲 КОСТИ\n\nВыберите тип ставки\n💰 Баланс: {balance} 💵"
    
    keyboard = [
        [InlineKeyboardButton("⬆️ Больше 7", callback_data="dice_bet_higher")],
        [InlineKeyboardButton("⬇️ Меньше 7", callback_data="dice_bet_lower")],
        [InlineKeyboardButton("➕ Чётное", callback_data="dice_bet_even")],
        [InlineKeyboardButton("➖ Нечётное", callback_data="dice_bet_odd")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_menu")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_text(message, reply_markup=reply_markup)


async def handle_dice_bet(query, user_id: int, bet_type: str):
    """Обрабатывает выбор типа ставки в костях"""
    balance = db.get_balance(user_id)
    
    message = f"💰 Выберите ставку\n💵 Баланс: {balance}"
    
    bets = [50, 100, 250, 500]
    keyboard = []
    
    for bet in bets:
        if bet <= balance:
            keyboard.append(
                [InlineKeyboardButton(f"{bet} 💵", callback_data=f"dice_play_{bet_type}_{bet}")]
            )
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="game_dice")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Нужно создать новый запрос так как мы меняем callback
    context.user_data['pending_bet_type'] = bet_type
    await query.edit_text(message, reply_markup=reply_markup)


async def show_stats(query, user_id: int):
    """Показывает статистику пользователя"""
    stats = db.get_stats(user_id)
    
    message = (
        f"📊 ВАША СТАТИСТИКА\n\n"
        f"💰 Баланс: {stats['balance']} 💵\n"
        f"✅ Выиграно: {stats['total_won']} 💵\n"
        f"❌ Проиграно: {stats['total_lost']} 💵\n"
        f"🎮 Игр сыграно: {stats['games_played']}\n"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_text(message, reply_markup=reply_markup)


async def show_main_menu(query):
    """Показывает главное меню"""
    await start(query, None)


def main():
    """Основная функция бота"""
    # Создаём приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бот
    logger.info("✅ Бот запущен!")
    application.run_polling()


if __name__ == '__main__':
    main()
