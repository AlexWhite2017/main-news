import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from bs4 import BeautifulSoup
import asyncio
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse
import uvicorn

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Настройки вебхука для Render
TOKEN = os.environ["BOT_TOKEN"]  # Токен из переменных окружения
PORT = int(os.environ.get("PORT", 8000))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "") + "/webhook"

# Создаем приложение Telegram
application = Application.builder().token(TOKEN).build()

class NewsParser:
    """Парсер новостей из популярных российских источников"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def parse_ria_news(self, max_news: int = 5) -> list:
        """Парсинг новостей с RIA.ru - федеральные новости"""
        try:
            url = "https://ria.ru/"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            news_items = []
            # Современные селекторы для RIA.ru
            articles = soup.select('a.cell-list__item-link, a.list-item__content')[:max_news]
            
            for article in articles:
                try:
                    title_elem = article.select_one('.cell-list__item-title, .list-item__title')
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = article.get('href', '')
                        if link and not link.startswith('http'):
                            link = 'https://ria.ru' + link
                        
                        news_items.append({
                            'title': title,
                            'link': link,
                            'source': 'RIA Новости'
                        })
                except Exception as e:
                    logger.warning(f"Ошибка парсинга RIA: {e}")
                    continue
            
            return news_items
        except Exception as e:
            logger.error(f"Ошибка RIA: {e}")
            return []
    
    def parse_tass_news(self, max_news: int = 5) -> list:
        """Парсинг новостей с TASS.ru - официальное агентство"""
        try:
            url = "https://tass.ru/"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            news_items = []
            articles = soup.select('.news-line__item, .news-card')[:max_news]
            
            for article in articles:
                try:
                    title_elem = article.select_one('.news-line__item-title, .news-card__title')
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link_elem = article.find('a')
                        link = link_elem.get('href', '') if link_elem else ''
                        if link and not link.startswith('http'):
                            link = 'https://tass.ru' + link
                        
                        news_items.append({
                            'title': title,
                            'link': link,
                            'source': 'ТАСС'
                        })
                except Exception as e:
                    logger.warning(f"Ошибка парсинга ТАСС: {e}")
                    continue
            
            return news_items
        except Exception as e:
            logger.error(f"Ошибка ТАСС: {e}")
            return []
    
    def parse_belpressa_news(self, max_news: int = 5) -> list:
        """Парсинг новостей Белгорода с Belpressa.ru"""
        try:
            url = "https://www.belpressa.ru/news/"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            news_items = []
            articles = soup.select('.news-list-item, .news-item')[:max_news]
            
            for article in articles:
                try:
                    title_elem = article.select_one('h2, .news-title, .title')
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link_elem = article.find('a')
                        link = link_elem.get('href', '') if link_elem else ''
                        if link and not link.startswith('http'):
                            link = 'https://www.belpressa.ru' + link
                        
                        news_items.append({
                            'title': title,
                            'link': link,
                            'source': 'БелПресса'
                        })
                except Exception as e:
                    logger.warning(f"Ошибка парсинга БелПресса: {e}")
                    continue
            
            return news_items
        except Exception as e:
            logger.error(f"Ошибка БелПресса: {e}")
            return []
    
    def parse_belru_news(self, max_news: int = 5) -> list:
        """Парсинг новостей Белгорода с Bel.ru"""
        try:
            url = "https://www.bel.ru/news/"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            news_items = []
            articles = soup.select('.news-item, .article-item')[:max_news]
            
            for article in articles:
                try:
                    title_elem = article.select_one('.news-title, .title, h3')
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link_elem = article.find('a')
                        link = link_elem.get('href', '') if link_elem else ''
                        if link and not link.startswith('http'):
                            link = 'https://www.bel.ru' + link
                        
                        news_items.append({
                            'title': title,
                            'link': link,
                            'source': 'Бел.Ру'
                        })
                except Exception as e:
                    logger.warning(f"Ошибка парсинга Бел.Ру: {e}")
                    continue
            
            return news_items
        except Exception as e:
            logger.error(f"Ошибка Бел.Ру: {e}")
            return []

# Создаем экземпляр парсера
news_parser = NewsParser()

# ===== ОБРАБОТЧИКИ КОМАНД ТЕЛЕГРАМ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Федеральные новости", callback_data="federal_news")],
        [InlineKeyboardButton("🏙️ Новости Белгорода", callback_data="belgorod_news")],
        [InlineKeyboardButton("🔄 Обновить новости", callback_data="refresh_news")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📰 *Добро пожаловать в Новостной Бот!*\n\n"
        "Я предоставляю актуальные новости:\n"
        "• 🇷🇺 Федеральные новости России\n"
        "• 🏙️ Новости Белгорода и области\n\n"
        "Выберите категорию новостей:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /help"""
    help_text = (
        "ℹ️ *Помощь по боту*\n\n"
        "*Основные команды:*\n"
        "/start - начать работу с ботом\n"
        "/news - получить свежие новости\n"
        "/help - эта справка\n\n"
        "*Источники новостей:*\n"
        "• RIA Новости\n"
        "• ТАСС\n"
        "• БелПресса\n"
        "• Бел.Ру\n\n"
        "🔄 Новости обновляются при каждом запросе"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /news"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Федеральные новости", callback_data="federal_news")],
        [InlineKeyboardButton("🏙️ Новости Белгорода", callback_data="belgorod_news")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📰 Выберите категорию новостей:",
        reply_markup=reply_markup
    )

# ===== ОБРАБОТЧИК КНОПОК =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "federal_news":
        await send_federal_news(query)
    elif data == "belgorod_news":
        await send_belgorod_news(query)
    elif data == "refresh_news":
        await refresh_news_menu(query)
    elif data == "help":
        await show_help(query)

async def send_federal_news(query):
    """Отправка федеральных новостей"""
    await query.edit_message_text("📡 Загружаю федеральные новости...")
    
    # Парсим новости из нескольких источников
    ria_news = news_parser.parse_ria_news(3)
    tass_news = news_parser.parse_tass_news(3)
    
    all_news = ria_news + tass_news
    
    if not all_news:
        message = "❌ Не удалось загрузить федеральные новости. Попробуйте позже."
    else:
        message = "🇷🇺 *ФЕДЕРАЛЬНЫЕ НОВОСТИ*\n\n"
        for i, news in enumerate(all_news[:6], 1):  # Ограничиваем 6 новостями
            message += f"{i}. [{news['source']}] {news['title']}\n"
            message += f"   🔗 [Читать]({news['link']})\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="federal_news")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="refresh_news")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown',
        disable_web_page_preview=False
    )

async def send_belgorod_news(query):
    """Отправка новостей Белгорода"""
    await query.edit_message_text("📡 Загружаю новости Белгорода...")
    
    # Парсим новости из белгородских источников
    belpressa_news = news_parser.parse_belpressa_news(4)
    belru_news = news_parser.parse_belru_news(4)
    
    all_news = belpressa_news + belru_news
    
    if not all_news:
        message = "❌ Не удалось загрузить новости Белгорода. Попробуйте позже."
    else:
        message = "🏙️ *НОВОСТИ БЕЛГОРОДА И ОБЛАСТИ*\n\n"
        for i, news in enumerate(all_news[:8], 1):  # Ограничиваем 8 новостями
            message += f"{i}. [{news['source']}] {news['title']}\n"
            message += f"   🔗 [Читать]({news['link']})\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="belgorod_news")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="refresh_news")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown',
        disable_web_page_preview=False
    )

async def refresh_news_menu(query):
    """Обновление главного меню"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Федеральные новости", callback_data="federal_news")],
        [InlineKeyboardButton("🏙️ Новости Белгорода", callback_data="belgorod_news")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📰 *Главное меню*\n\n"
        "Выберите категорию новостей:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def show_help(query):
    """Показ справки"""
    help_text = (
        "ℹ️ *Помощь по боту*\n\n"
        "*Источники новостей:*\n"
        "• RIA Новости - федеральные\n"
        "• ТАСС - федеральные\n"
        "• БелПресса - Белгород\n"
        "• Бел.Ру - Белгород\n\n"
        "*Как использовать:*\n"
        "1. Выберите категорию новостей\n"
        "2. Нажмите на ссылку для чтения\n"
        "3. Используйте '🔄 Обновить' для актуальных новостей\n\n"
        "📞 Поддержка: @Alex_De_White"
    )
    
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="refresh_news")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ===== ВЕБХУК ЭНДПОИНТЫ ДЛЯ RENDER =====
async def webhook(request: Request) -> Response:
    """Эндпоинт для вебхуков от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return Response()
    except Exception as e:
        logger.error(f"Ошибка в вебхуке: {e}")
        return Response(status_code=500)

async def health_check(request: Request) -> PlainTextResponse:
    """Эндпоинт для проверки здоровья приложения"""
    return PlainTextResponse("OK")

async def set_webhook():
    """Установка вебхука при запуске"""
    if WEBHOOK_URL:
        await application.bot.set_webhook(url=f"{WEBHOOK_URL}")
        logger.info(f"Вебхук установлен: {WEBHOOK_URL}")
    else:
        logger.warning("RENDER_EXTERNAL_URL не установлен, вебхук не настроен")

# ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ =====
def setup_handlers():
    """Регистрация всех обработчиков"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CallbackQueryHandler(button_handler))

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====
async def main():
    """Основная функция запуска"""
    logger.info("🔄 Инициализация новостного бота...")
    
    # Регистрируем обработчики
    setup_handlers()
    
    # Запускаем приложение
    await application.initialize()
    await application.start()
    
    # Устанавливаем вебхук
    await set_webhook()
    
    # Создаем Starlette приложение
    starlette_app = Starlette(routes=[
        Route("/webhook", webhook, methods=["POST"]),
        Route("/healthcheck", health_check, methods=["GET"]),
        Route("/", health_check, methods=["GET"]),
    ])
    
    # Запускаем сервер
    config = uvicorn.Config(
        app=starlette_app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    logger.info(f"🤖 Новостной бот запущен на порту {PORT}")
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
