import os
import logging
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from bs4 import BeautifulSoup
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
    """Улучшенный парсер новостей с резервными источниками"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        logger.info("🔄 Инициализирован улучшенный парсер новостей")
    
    def parse_ria_news(self, max_news: int = 5) -> list:
        """Парсинг новостей с RIA.ru"""
        try:
            url = "https://ria.ru/"
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = []
            
            # Универсальные селекторы для RIA
            articles = soup.select('[data-type="article"], .cell-list__item, .list-item, article')[:max_news*2]
            
            for article in articles:
                try:
                    title_elem = article.select_one('.cell-list__item-title, .list-item__title, h2, h3')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if len(title) < 10:
                        continue
                    
                    link_elem = article.find('a', href=True)
                    if link_elem:
                        link = link_elem['href']
                        if link and not link.startswith('http'):
                            link = 'https://ria.ru' + link
                    else:
                        continue
                    
                    news_items.append({
                        'title': title[:150],
                        'link': link,
                        'source': 'RIA Новости'
                    })
                    
                    if len(news_items) >= max_news:
                        break
                        
                except Exception as e:
                    continue
            
            logger.info(f"✅ RIA: получено {len(news_items)} новостей")
            return news_items
            
        except Exception as e:
            logger.error(f"❌ Ошибка RIA: {e}")
            return []
    
    def parse_tass_news(self, max_news: int = 5) -> list:
        """Парсинг новостей с TASS.ru"""
        try:
            url = "https://tass.ru/"
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = []
            
            articles = soup.select('.news-card, .news-line__item, [data-io-article-url]')[:max_news*2]
            
            for article in articles:
                try:
                    title_elem = article.select_one('.news-card__title, .news-line__item-title, h3')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if len(title) < 10:
                        continue
                    
                    link_elem = article.find('a', href=True)
                    if link_elem:
                        link = link_elem['href']
                        if link and not link.startswith('http'):
                            link = 'https://tass.ru' + link
                    else:
                        # Пробуем получить ссылку из data-атрибута
                        link = article.get('data-io-article-url', '')
                        if link and not link.startswith('http'):
                            link = 'https://tass.ru' + link
                    
                    if not link:
                        continue
                    
                    news_items.append({
                        'title': title[:150],
                        'link': link,
                        'source': 'ТАСС'
                    })
                    
                    if len(news_items) >= max_news:
                        break
                        
                except Exception as e:
                    continue
            
            logger.info(f"✅ ТАСС: получено {len(news_items)} новостей")
            return news_items
            
        except Exception as e:
            logger.error(f"❌ Ошибка ТАСС: {e}")
            return []
    
    def parse_belpressa_news(self, max_news: int = 5) -> list:
        """Парсинг новостей Белгорода с Belpressa.ru"""
        try:
            url = "https://www.belpressa.ru/news/"
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = []
            
            # Универсальные селекторы
            articles = soup.select('.news-item, article, .item, .news-list__item')[:max_news*3]
            
            for article in articles:
                try:
                    title_elem = article.select_one('h2, h3, .title, .news-title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if len(title) < 15:
                        continue
                    
                    link_elem = article.find('a', href=True)
                    if link_elem:
                        link = link_elem['href']
                        if link and not link.startswith('http'):
                            link = 'https://www.belpressa.ru' + link
                    else:
                        continue
                    
                    news_items.append({
                        'title': title[:200],
                        'link': link,
                        'source': 'БелПресса'
                    })
                    
                    if len(news_items) >= max_news:
                        break
                        
                except Exception as e:
                    continue
            
            # Резервный метод поиска
            if not news_items:
                all_links = soup.find_all('a', href=True)
                news_count = 0
                for link in all_links:
                    href = link['href']
                    if '/news/' in href and any(x in href for x in ['2024', '2025']):
                        title = link.get_text(strip=True)
                        if title and len(title) > 20:
                            full_link = href if href.startswith('http') else 'https://www.belpressa.ru' + href
                            news_items.append({
                                'title': title[:200],
                                'link': full_link,
                                'source': 'БелПресса'
                            })
                            news_count += 1
                            if news_count >= max_news:
                                break
            
            logger.info(f"✅ БелПресса: получено {len(news_items)} новостей")
            return news_items
            
        except Exception as e:
            logger.error(f"❌ Ошибка БелПресса: {e}")
            return []
    
    def parse_belru_news(self, max_news: int = 5) -> list:
        """Парсинг новостей Белгорода с Bel.ru"""
        try:
            url = "https://bel.ru/news/"
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = []
            
            articles = soup.select('.news-item, article, .item, [class*="news"]')[:max_news*3]
            
            for article in articles:
                try:
                    title_elem = article.select_one('h1, h2, h3, h4, .title, .news-title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    if len(title) < 15:
                        continue
                    
                    link_elem = article.find('a', href=True)
                    if link_elem:
                        link = link_elem['href']
                        if link and not link.startswith('http'):
                            link = 'https://bel.ru' + link
                    else:
                        continue
                    
                    news_items.append({
                        'title': title[:200],
                        'link': link,
                        'source': 'Бел.Ру'
                    })
                    
                    if len(news_items) >= max_news:
                        break
                        
                except Exception as e:
                    continue
            
            logger.info(f"✅ Бел.Ру: получено {len(news_items)} новостей")
            return news_items
            
        except Exception as e:
            logger.error(f"❌ Ошибка Бел.Ру: {e}")
            return []
    
    def parse_alternative_belgorod_news(self, max_news: int = 5) -> list:
        """Резервные источники новостей Белгорода"""
        try:
            news_items = []
            
            # Альтернативный источник - региональные новости
            alternative_sources = [
                {
                    'url': 'https://www.belnovosti.ru/',
                    'source': 'БелНовости',
                    'base': 'https://www.belnovosti.ru'
                }
            ]
            
            for source in alternative_sources:
                try:
                    response = requests.get(source['url'], headers=self.headers, timeout=10)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Ищем новости по ключевым словам
                    all_links = soup.find_all('a', href=True)
                    for link in all_links:
                        href = link['href']
                        title = link.get_text(strip=True)
                        
                        if (title and len(title) > 20 and 
                            any(word in title.lower() for word in ['белгород', 'област', 'город', 'новост'])):
                            
                            full_link = href if href.startswith('http') else source['base'] + href
                            news_items.append({
                                'title': title[:150],
                                'link': full_link,
                                'source': source['source']
                            })
                            
                            if len(news_items) >= max_news:
                                break
                                
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка альтернативного источника {source['source']}: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"❌ Ошибка альтернативных источников: {e}")
            return []

# Создаем экземпляр парсера
news_parser = NewsParser()

# ===== ОБРАБОТЧИКИ КОМАНД ТЕЛЕГРАМ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Федеральные новости", callback_data="federal_news")],
        [InlineKeyboardButton("🏙️ Новости Белгорода", callback_data="belgorod_news")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_news"),
         InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user = update.effective_user
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "📰 *Я ваш новостной бот*\n\n"
        "Я помогу вам быть в курсе последних событий:\n"
        "• 🇷🇺 Федеральные новости России\n" 
        "• 🏙️ Новости Белгорода и области\n\n"
        "Выберите категорию:"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /help"""
    help_text = (
        "ℹ️ *Помощь по боту*\n\n"
        "*Основные команды:*\n"
        "/start - начать работу\n"
        "/news - получить новости\n"
        "/help - эта справка\n\n"
        "*Источники новостей:*\n"
        "• RIA Новости - федеральные\n"
        "• ТАСС - федеральные\n" 
        "• БелПресса - Белгород\n"
        "• Бел.Ру - Белгород\n\n"
        "📞 *Поддержка:* @Alex_De_White"
    )
    
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="refresh_news")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

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
    await query.edit_message_text("📡 *Загружаю федеральные новости...*", parse_mode='Markdown')
    
    # Парсим новости асинхронно
    ria_news = await asyncio.get_event_loop().run_in_executor(None, news_parser.parse_ria_news, 4)
    tass_news = await asyncio.get_event_loop().run_in_executor(None, news_parser.parse_tass_news, 4)
    
    all_news = ria_news + tass_news
    
    if not all_news:
        message = (
            "❌ *Не удалось загрузить федеральные новости*\n\n"
            "Попробуйте:\n"
            "• Проверить интернет-соединение\n" 
            "• Попробовать позже\n"
            "• Написать в поддержку @Alex_De_White"
        )
    else:
        message = "🇷🇺 *ФЕДЕРАЛЬНЫЕ НОВОСТИ*\n\n"
        for i, news in enumerate(all_news[:6], 1):
            message += f"*{i}. {news['source']}*\n"
            message += f"{news['title']}\n"
            message += f"[Читать]({news['link']})\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="federal_news")],
        [InlineKeyboardButton("🏙️ Новости Белгорода", callback_data="belgorod_news")],
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
    """Отправка новостей Белгорода с резервными источниками"""
    await query.edit_message_text("📡 *Загружаю новости Белгорода...*", parse_mode='Markdown')
    
    # Парсим основные источники
    belpressa_news = await asyncio.get_event_loop().run_in_executor(None, news_parser.parse_belpressa_news, 3)
    belru_news = await asyncio.get_event_loop().run_in_executor(None, news_parser.parse_belru_news, 3)
    
    all_news = belpressa_news + belru_news
    
    # Если основные источники не дали результатов, используем резервные
    if not all_news:
        await query.edit_message_text("📡 *Ищу альтернативные источники...*", parse_mode='Markdown')
        alternative_news = await asyncio.get_event_loop().run_in_executor(None, news_parser.parse_alternative_belgorod_news, 6)
        all_news = alternative_news
    
    if not all_news:
        message = (
            "❌ *Не удалось загрузить новости Белгорода*\n\n"
            "Возможные причины:\n"
            "• Сайты временно недоступны\n"
            "• Изменилась структура сайтов\n"
            "• Проблемы с подключением\n\n"
            "Попробуйте позже или проверьте федеральные новости 🇷🇺"
        )
    else:
        message = "🏙️ *НОВОСТИ БЕЛГОРОДА И ОБЛАСТИ*\n\n"
        for i, news in enumerate(all_news[:6], 1):
            message += f"*{i}. {news['source']}*\n"
            message += f"{news['title']}\n"
            message += f"[Читать]({news['link']})\n\n"
        
        if not belpressa_news and not belru_news:
            message += "⚠️ *Используются альтернативные источники*\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="belgorod_news")],
        [InlineKeyboardButton("🇷🇺 Федеральные новости", callback_data="federal_news")],
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
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_news"),
         InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
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
        "📞 *Поддержка:* @Alex_De_White"
    )
    
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Федеральные новости", callback_data="federal_news")],
        [InlineKeyboardButton("🏙️ Новости Белгорода", callback_data="belgorod_news")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="refresh_news")]
    ]
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
        logger.error(f"❌ Ошибка в вебхуке: {e}")
        return Response(status_code=500)

async def health_check(request: Request) -> PlainTextResponse:
    """Эндпоинт для проверки здоровья приложения"""
    return PlainTextResponse("✅ Бот работает")

async def set_webhook():
    """Установка вебхука при запуске"""
    if WEBHOOK_URL:
        try:
            await application.bot.set_webhook(url=f"{WEBHOOK_URL}")
            logger.info(f"✅ Вебхук установлен: {WEBHOOK_URL}")
        except Exception as e:
            logger.error(f"❌ Ошибка установки вебхука: {e}")
    else:
        logger.warning("⚠️ RENDER_EXTERNAL_URL не установлен, вебхук не настроен")

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
    
    logger.info(f"✅ Новостной бот запущен на порту {PORT}")
    logger.info("🤖 Бот готов к работе!")
    
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
