import telebot
from telebot import types
import sqlite3
import uuid
import logging

# Танзимоти бот
BOT_TOKEN = "8028992264:AAGvvR6jGwHCSmOw4XFuLLkYRJx_h9HxKBg"
ADMIN_ID = 5615452654  # ID-и админ

bot = telebot.TeleBot(BOT_TOKEN)

# Логгинг
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Эҷоди базаи додаҳо
def init_database():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id TEXT UNIQUE,
            file_id TEXT,
            title TEXT,
            description TEXT,
            link TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            user_id INTEGER,
            channel_id TEXT,
            subscribed BOOLEAN,
            PRIMARY KEY (user_id, channel_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE,
            channel_name TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcast_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_content TEXT,
            post_type TEXT,
            file_id TEXT,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            total_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Гирифтани ҳамаи каналҳои фаъол
def get_active_channels():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id, channel_name FROM channels WHERE is_active = 1')
    channels = cursor.fetchall()
    conn.close()
    return channels

# Иловаи канал
def add_channel(channel_id, channel_name):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO channels (channel_id, channel_name, is_active) VALUES (?, ?, 1)', 
                   (channel_id, channel_name))
    conn.commit()
    conn.close()

# Хориҷ кардани канал
def remove_channel(channel_id):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE channels SET is_active = 0 WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

# Санҷиши обуна
def check_subscription(user_id, channel_id):
    try:
        member = bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# Санҷиши обуна ба ҳамаи каналҳо
def check_all_subscriptions(user_id):
    channels = get_active_channels()
    if not channels:
        return True  # Агар канале набошад, ҳамаро иҷозат дода
    
    for channel_id, channel_name in channels:
        if not check_subscription(user_id, channel_id):
            return False
    return True

# Захираи филм дар базаи додаҳо
def save_movie(movie_id, file_id, title, description=""):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    # Сохтани силкаи махсус
    link = f"https://t.me/{bot.get_me().username}?start={movie_id}"
    
    cursor.execute('''
        INSERT OR REPLACE INTO movies (movie_id, file_id, title, description, link)
        VALUES (?, ?, ?, ?, ?)
    ''', (movie_id, file_id, title, description, link))
    
    conn.commit()
    conn.close()
    
    return link

# Гирифтани филм аз базаи додаҳо
def get_movie(movie_id):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM movies WHERE movie_id = ?', (movie_id,))
    movie = cursor.fetchone()
    
    conn.close()
    return movie

# Функсияҳои рассылка
def save_broadcast_stats(post_content, post_type, file_id, sent_count, failed_count, total_count):
    """Захираи статистикаи рассылка"""
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO broadcast_posts (post_content, post_type, file_id, sent_count, failed_count, total_count)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (post_content, post_type, file_id, sent_count, failed_count, total_count))
    conn.commit()
    conn.close()

def send_broadcast_message(content, message_type, file_id=None):
    """Фиристодани паёми умумӣ ба ҳама корбарон"""
    users = get_all_users()
    sent_count = 0
    failed_count = 0
    total_count = len(users)
    
    for user_id in users:
        if user_id == ADMIN_ID:  # Ба худи админ нафиристем
            continue
            
        try:
            if message_type == 'text':
                bot.send_message(user_id, content, parse_mode='Markdown')
            elif message_type == 'photo':
                bot.send_photo(user_id, file_id, caption=content, parse_mode='Markdown')
            elif message_type == 'video':
                bot.send_video(user_id, file_id, caption=content, parse_mode='Markdown')
            elif message_type == 'document':
                bot.send_document(user_id, file_id, caption=content, parse_mode='Markdown')
            elif message_type == 'audio':
                bot.send_audio(user_id, file_id, caption=content, parse_mode='Markdown')
            elif message_type == 'voice':
                bot.send_voice(user_id, file_id, caption=content, parse_mode='Markdown')
            elif message_type == 'video_note':
                bot.send_video_note(user_id, file_id)
            elif message_type == 'sticker':
                bot.send_sticker(user_id, file_id)
                if content:  # Агар матн ҳам бошад
                    bot.send_message(user_id, content, parse_mode='Markdown')
            
            sent_count += 1
            
        except Exception as e:
            failed_count += 1
            logger.error(f"Хатогӣ ҳангоми фиристодан ба {user_id}: {e}")
    
    # Захираи статистика
    save_broadcast_stats(content, message_type, file_id, sent_count, failed_count, total_count)
    
    return sent_count, failed_count, total_count
# Ҷустуҷӯи филм бо ном
def search_movies_by_title(title):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM movies WHERE title LIKE ? LIMIT 10', (f'%{title}%',))
    movies = cursor.fetchall()
    conn.close()
    return movies

# Обработчики команд
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    # Захираи корбар дар базаи додаҳо
    save_user(user_id)
    
    # Санҷиш оё корбар бо силкаи махсус омадааст
    if len(message.text.split()) > 1:
        movie_id = message.text.split()[1]
        
        # Санҷиши обуна
        if check_all_subscriptions(user_id):
            # Корбар обуна шудааст, филмро фиристодан
            movie = get_movie(movie_id)
            if movie:
                try:
                    bot.send_video(
                        message.chat.id, 
                        movie[2],  # file_id
                        caption=f"🎬 {movie[3]}\n\n{movie[4]}",
                        reply_markup=get_main_keyboard(user_id)
                    )
                except:
                    bot.send_message(
                        message.chat.id,
                        "❌ Хатогӣ ҳангоми фиристодани филм. Лутфан баъдтар кӯшиш кунед.",
                        reply_markup=get_main_keyboard(user_id)
                    )
            else:
                bot.send_message(
                    message.chat.id, 
                    "❌ Филм ёфт нашуд.",
                    reply_markup=get_main_keyboard(user_id)
                )
        else:
            # Корбар обуна нашудааст
            show_subscription_requirement(message, movie_id)
    else:
        # Санҷиши обуна ҳангоми /start
        if not check_all_subscriptions(user_id) and user_id != ADMIN_ID:
            show_subscription_requirement(message)
        else:
            # Паёми саломӣ
            bot.send_message(
                message.chat.id,
                f"👋 Салом {message.from_user.first_name}!\n\n"
                "Ман боти паҳши филм ҳастам. Барои тамошои филмҳо ба каналҳои мо обуна шавед!",
                reply_markup=get_main_keyboard(user_id)
            )

def show_subscription_requirement(message, movie_id=None):
    channels = get_active_channels()
    
    if not channels:
        # Агар канале набошад, филмро бевосита фиристед
        if movie_id:
            movie = get_movie(movie_id)
            if movie:
                try:
                    bot.send_video(
                        message.chat.id,
                        movie[2],
                        caption=f"🎬 {movie[3]}\n\n{movie[4]}"
                    )
                except:
                    bot.send_message(message.chat.id, "❌ Хатогӣ ҳангоми фиристодани филм.")
        return
    
    markup = types.InlineKeyboardMarkup()
    
    # Тугмаҳои обуна
    for channel_id, channel_name in channels:
        channel_link = f"https://t.me/{channel_id[1:]}" if channel_id.startswith('@') else channel_id
        markup.add(types.InlineKeyboardButton(f"📢 {channel_name}", url=channel_link))
    
    # Тугмаи санҷиши обуна
    callback_data = f"check_sub_{movie_id}" if movie_id else "check_sub_general"
    markup.add(types.InlineKeyboardButton("✅ Санҷиши обуна", callback_data=callback_data))
    
    text = "📺 Барои тамошои филм аввал ба каналҳои зерин обуна шавед:\n\n"
    for i, (channel_id, channel_name) in enumerate(channels, 1):
        text += f"{i}️⃣ {channel_name}\n"
    text += "\nБаъд аз обуна шудан, тугмаи 'Санҷиши обуна'-ро пахш кунед."
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_sub'))
def check_subscription_callback(call):
    user_id = call.from_user.id
    
    if check_all_subscriptions(user_id):
        bot.answer_callback_query(call.id, "✅ Шумо ба ҳарду канал обуна шудаед!")
        
        # Агар movie_id дошта бошем, филмро фиристем
        if call.data.startswith('check_sub_') and len(call.data.split('_')) > 2:
            movie_id = call.data.split('_')[2]
            if movie_id != 'general':
                movie = get_movie(movie_id)
                if movie:
                    try:
                        bot.send_video(
                            call.message.chat.id,
                            movie[2],  # file_id
                            caption=f"🎬 {movie[3]}\n\n{movie[4]}"
                        )
                        bot.delete_message(call.message.chat.id, call.message.message_id)
                    except:
                        bot.send_message(
                            call.message.chat.id,
                            "❌ Хатогӣ ҳангоми фиристодани филм."
                        )
        else:
            bot.edit_message_text(
                "✅ Шумо ба ҳарду канал обуна шудаед!\n\n"
                "Акнун метавонед филмҳоро тамошо кунед.",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None
            )
            # Фиристодани тугмаҳои асосӣ
            bot.send_message(
                call.message.chat.id,
                "Менюи асосӣ:",
                reply_markup=get_main_keyboard(call.from_user.id)
            )
    else:
        bot.answer_callback_query(call.id, "❌ Шумо ҳанӯз ба ҳамаи каналҳо обуна нашудаед!")

# Командаҳои админ
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("➕ Илова кардани филм", callback_data="add_movie")
        )
        markup.add(
            types.InlineKeyboardButton("📋 Рӯйхати филмҳо", callback_data="list_movies")
        )
        markup.add(
            types.InlineKeyboardButton("🗑 Нест кардани филм", callback_data="delete_movie")
        )
        
        bot.send_message(
            message.chat.id,
            "🔧 Панели администратор:",
            reply_markup=markup
        )
    else:
        bot.send_message(message.chat.id, "❌ Шумо админ нестед.")

@bot.callback_query_handler(func=lambda call: call.data in ['add_by_file', 'add_by_id'])
def add_movie_method_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Шумо админ нестед!")
        return
    
    if call.data == 'add_by_file':
        bot.edit_message_text(
            "📹 Филми худро ба ман фиристед (видеофайл).\n\n"
            "Баъдан ман аз шумо номи филм ва тавсифро мепурсам.",
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler(call.message, process_movie_file)
    
    elif call.data == 'add_by_id':
        bot.edit_message_text(
            "🆔 File ID-и видеофайлро нависед:\n\n"
            "💡 **Чӣ тавр File ID гирифтан?**\n"
            "1. Филмро ба ботатон фиристед\n"
            "2. Аз Developer Tools File ID-ро нусха кунед\n"
            "3. Ё аз ботҳои махсус истифода баред\n\n"
            "Мисол: `BAADBAADrwADBREAAYag4B5vl-UWAgAC`",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(call.message, process_file_id_input)

def process_file_id_input(message):
    """Коркарди File ID-и дохилшуда"""
    file_id = message.text.strip()
    
    # Санҷиши File ID (оддӣ)
    if len(file_id) < 10 or ' ' in file_id:
        bot.send_message(
            message.chat.id,
            "❌ File ID нодуруст аст!\n\n"
            "File ID бояд:\n"
            "• Дарозтар аз 10 символ бошад\n"
            "• Бидуни фосила бошад\n"
            "• Аз ҳуруф ва рақамҳо иборат бошад\n\n"
            "Лутфан дубора кӯшиш кунед:"
        )
        bot.register_next_step_handler(message, process_file_id_input)
        return
    
    # Санҷиши кории File ID
    try:
        # Кӯшиши фиристодани видео барои санҷиш
        test_message = bot.send_video(
            message.chat.id,
            file_id,
            caption="🧪 Санҷиши File ID..."
        )
        
        # Агар муваффақ бошад, паёмро нест мекунем
        bot.delete_message(message.chat.id, test_message.message_id)
        
        # Идома додани раванди иловаи филм
        bot.send_message(
            message.chat.id,
            "✅ File ID дуруст аст!\n\n"
            "📝 Номи филмро нависед:"
        )
        bot.register_next_step_handler(message, process_movie_title_from_id, file_id)
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ File ID кор намекунад!\n\n"
            f"Хатогӣ: {str(e)[:100]}\n\n"
            f"Лутфан File ID-и дурустро нависед:"
        )
        bot.register_next_step_handler(message, process_file_id_input)

def process_movie_title_from_id(message, file_id):
    """Коркарди номи филм баъд аз File ID"""
    title = message.text.strip()
    
    bot.send_message(
        message.chat.id,
        "📝 Тавсифи филмро нависед (ё /skip барои гузариш):"
    )
    
    bot.register_next_step_handler(message, process_movie_description_from_id, file_id, title)

def process_movie_description_from_id(message, file_id, title):
    """Коркарди тавсиф ва анҷоми иловаи филм бо File ID"""
    description = message.text if message.text != '/skip' else ""
    
    # Сохтани ID-и якта барои филм
    movie_id = str(uuid.uuid4())[:8]
    
    # Захираи филм дар базаи додаҳо
    link = save_movie(movie_id, file_id, title, description)
    
    # Фиристодани натиҷа бо нишондодани филм
    try:
        bot.send_video(
            message.chat.id,
            file_id,
            caption=(
                f"✅ Филм бо муваффақият илова шуд!\n\n"
                f"🎬 Ном: {title}\n"
                f"🆔 ID: {movie_id}\n"
                f"🔗 Силка: {link}\n\n"
                f"Ин силкаро дар канали худ мубодила кунед!"
            )
        )
    except:
        bot.send_message(
            message.chat.id,
            f"✅ Филм илова шуд (File ID кор мекунад)!\n\n"
            f"🎬 Ном: {title}\n"
            f"🆔 ID: {movie_id}\n"
            f"🔗 Силка: {link}\n\n"
            f"Ин силкаро дар канали худ мубодила кунед!"
        )
@bot.callback_query_handler(func=lambda call: call.data in ['add_channel', 'list_channels', 'remove_channel'])
def channel_management_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Шумо админ нестед!")
        return
    
    if call.data == 'add_channel':
        bot.send_message(
            call.message.chat.id,
            "➕ ID-и канали навро нависед (мисол: @channel_name):"
        )
        bot.register_next_step_handler(call.message, process_channel_id)
    
    elif call.data == 'list_channels':
        channels = get_active_channels()
        if channels:
            text = "📋 Рӯйхати каналҳо:\n\n"
            for i, (channel_id, channel_name) in enumerate(channels, 1):
                text += f"{i}. {channel_name}\n   ID: {channel_id}\n\n"
        else:
            text = "📋 Ҳеҷ канал илова нашудааст."
        
        bot.send_message(call.message.chat.id, text)
    
    elif call.data == 'remove_channel':
        channels = get_active_channels()
        if channels:
            markup = types.InlineKeyboardMarkup()
            for channel_id, channel_name in channels:
                markup.add(
                    types.InlineKeyboardButton(
                        f"🗑 {channel_name}",
                        callback_data=f"remove_ch_{channel_id}"
                    )
                )
            
            bot.send_message(
                call.message.chat.id,
                "🗑 Кадом каналро хориҷ кардан мехоҳед?",
                reply_markup=markup
            )
        else:
            bot.send_message(call.message.chat.id, "📋 Канале барои хориҷ кардан нест.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_ch_'))
def remove_channel_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Шумо админ нестед!")
        return
    
    channel_id = call.data.replace('remove_ch_', '')
    remove_channel(channel_id)
    
    bot.answer_callback_query(call.id, "✅ Канал хориҷ карда шуд!")
    bot.edit_message_text(
        "✅ Канал бо муваффақият хориҷ карда шуд.",
        call.message.chat.id,
        call.message.message_id
    )

def process_channel_id(message):
    channel_id = message.text.strip()
    
    if not channel_id.startswith('@'):
        bot.send_message(message.chat.id, "❌ ID-и канал бояд бо @ оғоз шавад. Мисол: @my_channel")
        return
    
    bot.send_message(message.chat.id, "📝 Номи каналро нависед:")
    bot.register_next_step_handler(message, process_channel_name, channel_id)

# Гирифтани ҳамаи корбарони фаъоли бот
def get_all_users():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT user_id FROM user_subscriptions')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

# Захираи корбар дар базаи додаҳо
def save_user(user_id):
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO user_subscriptions (user_id, channel_id, subscribed) VALUES (?, ?, ?)', 
                   (user_id, 'temp', False))
    conn.commit()
    conn.close()

def process_channel_name(message, channel_id):
    channel_name = message.text.strip()
    
    try:
        # Санҷиши дастрасии канал
        chat = bot.get_chat(channel_id)
        add_channel(channel_id, channel_name)
        
        bot.send_message(
            message.chat.id,
            f"✅ Канал бо муваффақият илова шуд!\n\n"
            f"📢 Ном: {channel_name}\n"
            f"🆔 ID: {channel_id}\n\n"
            f"🔄 Ҳамаи корбарон аз шарти нави обуна огоҳ карда мешаванд..."
        )
        
        # Огоҳ кардани ҳамаи корбарон
        notify_users_about_new_channel(channel_id, channel_name)
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Хатогӣ: Канал ёфт нашуд ё бот админ нест.\n\n"
            f"Мутмаин шавед, ки:\n"
            f"• ID дуруст аст\n"
            f"• Бот дар канал админ аст"
        )

def notify_users_about_new_channel(channel_id, channel_name):
    """Огоҳкунии ҳамаи корбарон дар бораи канали нав"""
    users = get_all_users()
    
    markup = types.InlineKeyboardMarkup()
    channel_link = f"https://t.me/{channel_id[1:]}" if channel_id.startswith('@') else channel_id
    markup.add(types.InlineKeyboardButton(f"📢 Обуна ба {channel_name}", url=channel_link))
    markup.add(types.InlineKeyboardButton("✅ Санҷиши обуна", callback_data="check_new_sub"))
    
    message_text = (
        f"📢 ШАРТИ НАВ!\n\n"
        f"Барои идома додани истифодаи бот, шумо бояд ба канали нав низ обуна шавед:\n\n"
        f"🆕 {channel_name}\n\n"
        f"⚠️ То вақте ки ба ин канал обуна нашавед, наметавонед аз бот истифода баред."
    )
    
    successful = 0
    failed = 0
    
    for user_id in users:
        try:
            if user_id != ADMIN_ID:  # Админро огоҳ накунем
                bot.send_message(user_id, message_text, reply_markup=markup)
                successful += 1
        except:
            failed += 1
    
    # Гузориши натиҷа ба админ
    bot.send_message(
        ADMIN_ID,
        f"📊 Натиҷаи огоҳкунӣ:\n"
        f"✅ Муваффақ: {successful} корбар\n"
        f"❌ Ноком: {failed} корбар"
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_new_sub")
def check_new_subscription(call):
    user_id = call.from_user.id
    
    if check_all_subscriptions(user_id):
        bot.answer_callback_query(call.id, "✅ Шумо ба ҳамаи каналҳо обуна шудаед!")
        bot.edit_message_text(
            "✅ Табрик! Шумо ба ҳамаи каналҳо обуна шудаед.\n\n"
            "Акнун метавонед аз бот истифода баред.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
        # Фиристодани тугмаҳои асосӣ
        bot.send_message(
            call.message.chat.id,
            "Менюи асосӣ:",
            reply_markup=get_main_keyboard(user_id)
        )
    else:
        bot.answer_callback_query(call.id, "❌ Шумо ҳанӯз ба ҳамаи каналҳо обуна нашудаед!")
        
        # Нишон додани каналҳоеки обуна нашудаанд
        channels = get_active_channels()
        unsubscribed = []
        
        for channel_id, channel_name in channels:
            if not check_subscription(user_id, channel_id):
                unsubscribed.append((channel_id, channel_name))
        
        if unsubscribed:
            text = "❌ Шумо ба ин каналҳо ҳанӯз обуна нашудаед:\n\n"
            markup = types.InlineKeyboardMarkup()
            
            for channel_id, channel_name in unsubscribed:
                text += f"📢 {channel_name}\n"
                channel_link = f"https://t.me/{channel_id[1:]}" if channel_id.startswith('@') else channel_id
                markup.add(types.InlineKeyboardButton(f"📢 {channel_name}", url=channel_link))
            
            markup.add(types.InlineKeyboardButton("✅ Санҷиши обуна", callback_data="check_new_sub"))
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
@bot.callback_query_handler(func=lambda call: call.data in ['add_movie', 'list_movies', 'delete_movie'])
def admin_callback_handler(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Шумо админ нестед!")
        return
    
    if call.data == 'add_movie':
        bot.send_message(
            call.message.chat.id,
            "📹 Филми худро ба ман фиристед (видеофайл).\n\n"
            "Баъдан ман аз шумо номи филм ва тавсифро мепурсам."
        )
        bot.register_next_step_handler(call.message, process_movie_file)
    
    elif call.data == 'list_movies':
        movies = get_all_movies()
        if movies:
            text = "📋 Рӯйхати филмҳо:\n\n"
            for movie in movies:
                text += f"🎬 {movie[3]} (ID: {movie[1]})\n"
                text += f"🔗 {movie[5]}\n\n"
            
            bot.send_message(call.message.chat.id, text)
        else:
            bot.send_message(call.message.chat.id, "📋 Ҳанӯз филме илова нашудааст.")
    
    elif call.data == 'delete_movie':
        movies = get_all_movies()
        if movies:
            markup = types.InlineKeyboardMarkup()
            for movie in movies:
                markup.add(
                    types.InlineKeyboardButton(
                        f"🗑 {movie[3]}", 
                        callback_data=f"del_{movie[1]}"
                    )
                )
            
            bot.send_message(
                call.message.chat.id,
                "🗑 Кадом филмро нест кардан мехоҳед?",
                reply_markup=markup
            )
        else:
            bot.send_message(call.message.chat.id, "📋 Филме барои нест кардан нест.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_movie_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Шумо админ нестед!")
        return
    
    movie_id = call.data.split('_')[1]
    
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM movies WHERE movie_id = ?', (movie_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ Филм нест карда шуд!")
    bot.edit_message_text(
        "✅ Филм бо муваффақият нест карда шуд.",
        call.message.chat.id,
        call.message.message_id
    )

def process_movie_file(message):
    # Агар матн бошад, ehtimol File ID аст
    if message.content_type == 'text':
        file_id = message.text.strip()
        
        # Санҷиш оё ин File ID аст
        if len(file_id) > 10 and ' ' not in file_id and ('BAAC' in file_id or 'BQAC' in file_id or len(file_id) > 50):
            bot.send_message(
                message.chat.id,
                "🆔 Ман мебинам, ки шумо File ID фиристодаед!\n\n"
                "🧪 Санҷиш..."
            )
            
            # Санҷиши File ID
            try:
                test_message = bot.send_video(
                    message.chat.id,
                    file_id,
                    caption="🧪 Санҷиши File ID..."
                )
                
                # Агар муваффақ бошад
                bot.delete_message(message.chat.id, test_message.message_id)
                
                bot.send_message(
                    message.chat.id,
                    "✅ File ID дуруст аст!\n\n"
                    "📝 Номи филмро нависед:"
                )
                
                bot.register_next_step_handler(message, process_movie_title, file_id)
                return
                
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ File ID кор намекунад!\n\n"
                    f"Лутфан:\n"
                    f"• Видеофайл фиристед, ё\n"
                    f"• File ID-и дурустро нависед"
                )
                bot.register_next_step_handler(message, process_movie_file)
                return
        else:
            bot.send_message(
                message.chat.id,
                "❌ Ин File ID нодуруст менамояд.\n\n"
                "Лутфан:\n"
                "📹 Видеофайл фиристед, ё\n"
                "🆔 File ID-и дурустро нависед"
            )
            bot.register_next_step_handler(message, process_movie_file)
            return
    
    # Агар видеофайл бошад
    elif message.content_type == 'video':
        file_id = message.video.file_id
        
        bot.send_message(
            message.chat.id,
            "✅ Видеофайл қабул шуд!\n\n"
            "📝 Номи филмро нависед:"
        )
        
        bot.register_next_step_handler(message, process_movie_title, file_id)
    
    else:
        bot.send_message(
            message.chat.id,
            "❌ Лутфан:\n"
            "📹 Видеофайл фиристед, ё\n"
            "🆔 File ID-и видеоро нависед\n\n"
            "Мисоли File ID: `BAADBAADrwADBREAAYag4B5vl-UWAgAC`",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(message, process_movie_file)

def process_movie_title(message, file_id):
    title = message.text
    
    bot.send_message(
        message.chat.id,
        "📝 Тавсифи филмро нависед (ё /skip барои гузариш):"
    )
    
    bot.register_next_step_handler(message, process_movie_description, file_id, title)

def process_movie_description(message, file_id, title):
    description = message.text if message.text != '/skip' else ""
    
    # Сохтани ID-и якта барои филм
    movie_id = str(uuid.uuid4())[:8]
    
    # Захираи филм дар базаи додаҳо
    link = save_movie(movie_id, file_id, title, description)
    
    bot.send_message(
        message.chat.id,
        f"✅ Филм бо муваффақият илова шуд!\n\n"
        f"🎬 Ном: {title}\n"
        f"🆔 ID: {movie_id}\n"
        f"🔗 Силка: {link}\n\n"
        f"Ин силкаро дар канали худ мубодила кунед!"
    )

# Гирифтани ҳамаи филмҳо
def get_all_movies():
    conn = sqlite3.connect('movies.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM movies')
    movies = cursor.fetchall()
    
    conn.close()
    return movies

# Тугмаҳои асосии бот
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if user_id == ADMIN_ID:
        # Тугмаҳо барои админ
        markup.add("🔍 Поиск по ID", "🔎 Поиск по названию")
        markup.add("➕ Илова кардани филм", "📋 Рӯйхати филмҳо")
        markup.add("🗑 Нест кардани филм", "📢 Идораи каналҳо")
    else:
        # Тугмаҳо барои корбари оддӣ
        markup.add("🔍 Поиск по ID", "🔎 Поиск по названию")
    
    return markup

# Обработчик барои тугмаи "Поиск по ID"
@bot.message_handler(func=lambda message: message.text == "🔍 Поиск по ID")
def search_by_id_button(message):
    bot.send_message(
        message.chat.id,
        "🔍 ID-и филмро нависед:",
        reply_markup=types.ForceReply()
    )

# Обработчик барои тугмаи "Рассылка"
@bot.message_handler(func=lambda message: message.text == "📡 Рассылка")
def broadcast_button(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "📡 **Рассылка ба ҳамаи корбарон**\n\n"
            "Паёми худро фиристед. Ман онро ба ҳама корбарони бот мефиристам.\n\n"
            "💡 **Имкониятҳо:**\n"
            "• 📝 Матн\n"
            "• 🖼 Расм\n"
            "• 📹 Видео\n"
            "• 📄 Файл\n"
            "• 🎵 Аудио\n"
            "• 🎤 Овоз\n"
            "• 🎭 Стикер\n\n"
            "❌ Барои бекор кардан /cancel нависед",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(message, process_broadcast_content)
    else:
        bot.send_message(message.chat.id, "❌ Шумо админ нестед.")

# Обработчик барои тугмаи "Статистикаи рассылка"
@bot.message_handler(func=lambda message: message.text == "📊 Статистикаи рассылка")
def broadcast_stats_button(message):
    if message.from_user.id == ADMIN_ID:
        conn = sqlite3.connect('movies.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as total_broadcasts,
                   SUM(sent_count) as total_sent,
                   SUM(failed_count) as total_failed,
                   SUM(total_count) as total_attempts
            FROM broadcast_posts
        ''')
        
        stats = cursor.fetchone()
        
        cursor.execute('''
            SELECT post_content, post_type, sent_count, failed_count, total_count, created_at
            FROM broadcast_posts
            ORDER BY created_at DESC
            LIMIT 5
        ''')
        
        recent_broadcasts = cursor.fetchall()
        conn.close()
        
        text = "📊 **Статистикаи рассылка**\n\n"
        
        if stats and stats[0] > 0:
            text += f"📈 **Умумӣ:**\n"
            text += f"• Ҷамъи рассылкаҳо: {stats[0]}\n"
            text += f"• Фиристода шуд: {stats[1] or 0}\n"
            text += f"• Хатогӣ: {stats[2] or 0}\n"
            text += f"• Ҷамъи кӯшишҳо: {stats[3] or 0}\n\n"
            
            if recent_broadcasts:
                text += "📋 **5 рассылкаи охирин:**\n"
                for i, broadcast in enumerate(recent_broadcasts, 1):
                    content = broadcast[0][:30] + "..." if len(broadcast[0]) > 30 else broadcast[0]
                    text += f"{i}. {broadcast[1].upper()} - {broadcast[2]}/{broadcast[4]} ✅\n"
                    text += f"   📝 {content}\n"
        else:
            text += "📭 Ҳанӯз рассылка нашудааст."
        
        bot.send_message(message.chat.id, text, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "❌ Шумо админ нестед.")

def process_broadcast_content(message):
    """Коркарди мӯҳтавои рассылка"""
    if message.text and message.text == '/cancel':
        bot.send_message(
            message.chat.id,
            "❌ Рассылка бекор карда шуд.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        return
    
    # Муайян кардани навъи паём
    content = ""
    message_type = ""
    file_id = None
    
    if message.content_type == 'text':
        content = message.text
        message_type = 'text'
    elif message.content_type == 'photo':
        content = message.caption if message.caption else ""
        message_type = 'photo'
        file_id = message.photo[-1].file_id
    elif message.content_type == 'video':
        content = message.caption if message.caption else ""
        message_type = 'video'
        file_id = message.video.file_id
    elif message.content_type == 'document':
        content = message.caption if message.caption else ""
        message_type = 'document'
        file_id = message.document.file_id
    elif message.content_type == 'audio':
        content = message.caption if message.caption else ""
        message_type = 'audio'
        file_id = message.audio.file_id
    elif message.content_type == 'voice':
        content = message.caption if message.caption else ""
        message_type = 'voice'
        file_id = message.voice.file_id
    elif message.content_type == 'video_note':
        content = ""
        message_type = 'video_note'
        file_id = message.video_note.file_id
    elif message.content_type == 'sticker':
        content = "Стикер фиристода шуд"
        message_type = 'sticker'
        file_id = message.sticker.file_id
    else:
        bot.send_message(
            message.chat.id,
            "❌ Ин навъи паём дастгирӣ намешавад.\n"
            "Лутфан матн, расм, видео ё файл фиристед."
        )
        bot.register_next_step_handler(message, process_broadcast_content)
        return
    
    # Тасдиқи рассылка
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Тасдиқ кунед", callback_data=f"confirm_broadcast"),
        types.InlineKeyboardButton("❌ Бекор кунед", callback_data="cancel_broadcast")
    )
    
    users_count = len(get_all_users()) - 1  # -1 барои админ
    
    preview_text = f"📡 **Тасдиқи рассылка**\n\n"
    preview_text += f"📊 Ба {users_count} корбар фиристода мешавад\n"
    preview_text += f"🎯 Навъ: {message_type.upper()}\n\n"
    
    if content:
        preview_text += f"📝 **Мӯҳтаво:**\n{content[:200]}"
        if len(content) > 200:
            preview_text += "..."
    
    preview_text += f"\n\n⚠️ Пас аз тасдиқ, паём ба ҳама фиристода мешавад!"
    
    # Захираи маълумот барои истифодаи баъдина
    bot.broadcast_data = {
        'content': content,
        'type': message_type,
        'file_id': file_id
    }
    
    bot.send_message(
        message.chat.id,
        preview_text,
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_broadcast', 'cancel_broadcast'])
def broadcast_confirmation_callback(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Шумо админ нестед!")
        return
    
    if call.data == 'cancel_broadcast':
        bot.edit_message_text(
            "❌ Рассылка бекор карда шуд.",
            call.message.chat.id,
            call.message.message_id
        )
        if hasattr(bot, 'broadcast_data'):
            del bot.broadcast_data
        return
    
    if call.data == 'confirm_broadcast':
        if not hasattr(bot, 'broadcast_data'):
            bot.answer_callback_query(call.id, "❌ Маълумоти рассылка ёфт нашуд!")
            return
        
        broadcast_data = bot.broadcast_data
        
        bot.edit_message_text(
            "🔄 Рассылка оғоз ёфт...\n\n⏳ Лутфан интизор шавед...",
            call.message.chat.id,
            call.message.message_id
        )
        
        # Фиристодани рассылка
        try:
            sent_count, failed_count, total_count = send_broadcast_message(
                broadcast_data['content'],
                broadcast_data['type'],
                broadcast_data['file_id']
            )
            
            # Нишондодани натиҷа
            result_text = f"✅ **Рассылка анҷом ёфт!**\n\n"
            result_text += f"📊 **Натиҷаҳо:**\n"
            result_text += f"• ✅ Муваффақ: {sent_count}\n"
            result_text += f"• ❌ Хатогӣ: {failed_count}\n"
            result_text += f"• 📈 Ҷамъи кӯшишҳо: {total_count}\n"
            
            if total_count > 0:
                success_rate = (sent_count / total_count) * 100
                result_text += f"• 📊 Муваффақият: {success_rate:.1f}%"
            
            bot.edit_message_text(
                result_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            bot.edit_message_text(
                f"❌ Хатогӣ ҳангоми рассылка:\n{str(e)[:200]}",
                call.message.chat.id,
                call.message.message_id
            )
        
        # Пок кардани маълумот
        if hasattr(bot, 'broadcast_data'):
            del bot.broadcast_data
# Обработчик барои тугмаи "Поиск по названию"
@bot.message_handler(func=lambda message: message.text == "🔎 Поиск по названию")
def search_by_title_button(message):
    bot.send_message(
        message.chat.id,
        "🔎 Номи филмро нависед:",
        reply_markup=types.ForceReply()
    )

# Обработчик барои тугмаи "Идораи каналҳо"
@bot.message_handler(func=lambda message: message.text == "📢 Идораи каналҳо")
def manage_channels_button(message):
    if message.from_user.id == ADMIN_ID:
        channels = get_active_channels()
        markup = types.InlineKeyboardMarkup()
        
        markup.add(types.InlineKeyboardButton("➕ Илова кардани канал", callback_data="add_channel"))
        
        if channels:
            markup.add(types.InlineKeyboardButton("📋 Рӯйхати каналҳо", callback_data="list_channels"))
            markup.add(types.InlineKeyboardButton("🗑 Хориҷи канал", callback_data="remove_channel"))
        
        text = "📢 Идораи каналҳо:\n\n"
        if channels:
            text += f"Каналҳои ҷорӣ ({len(channels)}):\n"
            for channel_id, channel_name in channels:
                text += f"• {channel_name} ({channel_id})\n"
        else:
            text += "Ҳеҷ канал илова нашудааст."
        
        bot.send_message(message.chat.id, text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "❌ Шумо админ нестед.")
@bot.message_handler(func=lambda message: message.text == "➕ Илова кардани филм")
def add_movie_button(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "📹 Филми худро ба ман фиристед (видеофайл).\n\n"
            "Баъдан ман аз шумо номи филм ва тавсифро мепурсам."
        )
        bot.register_next_step_handler(message, process_movie_file)
    else:
        bot.send_message(message.chat.id, "❌ Шумо админ нестед.")

# Обработчик барои тугмаи "Рӯйхати филмҳо"
@bot.message_handler(func=lambda message: message.text == "📋 Рӯйхати филмҳо")
def list_movies_button(message):
    if message.from_user.id == ADMIN_ID:
        movies = get_all_movies()
        if movies:
            text = "📋 Рӯйхати филмҳо:\n\n"
            for movie in movies:
                text += f"🎬 {movie[3]} (ID: {movie[1]})\n"
                text += f"🔗 {movie[5]}\n\n"
            
            bot.send_message(message.chat.id, text)
        else:
            bot.send_message(message.chat.id, "📋 Ҳанӯз филме илова нашудааст.")
    else:
        bot.send_message(message.chat.id, "❌ Шумо админ нестед.")

# Обработчик барои тугмаи "Нест кардани филм"
@bot.message_handler(func=lambda message: message.text == "🗑 Нест кардани филм")
def delete_movie_button(message):
    if message.from_user.id == ADMIN_ID:
        movies = get_all_movies()
        if movies:
            markup = types.InlineKeyboardMarkup()
            for movie in movies:
                markup.add(
                    types.InlineKeyboardButton(
                        f"🗑 {movie[3]}", 
                        callback_data=f"del_{movie[1]}"
                    )
                )
            
            bot.send_message(
                message.chat.id,
                "🗑 Кадом филмро нест кардан мехоҳед?",
                reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, "📋 Филме барои нест кардан нест.")
    else:
        bot.send_message(message.chat.id, "❌ Шумо админ нестед.")

# Команда барои бекор кардани раванд
@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    bot.send_message(
        message.chat.id,
        "❌ Ҳама равандҳо бекор карда шуданд.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )
# Хатогиҳо
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    # Санҷиш барои ID-и филм
    if message.reply_to_message and message.reply_to_message.text == "🔍 ID-и филмро нависед:":
        movie_id = message.text
        user_id = message.from_user.id
        
        if check_all_subscriptions(user_id):
            movie = get_movie(movie_id)
            if movie:
                try:
                    bot.send_video(
                        message.chat.id,
                        movie[2],  # file_id
                        caption=f"🎬 {movie[3]}\n\n{movie[4]}"
                    )
                except:
                    bot.send_message(
                        message.chat.id,
                        "❌ Хатогӣ ҳангоми фиристодани филм."
                    )
            else:
                bot.send_message(message.chat.id, "❌ Филм бо ин ID ёфт нашуд.")
        else:
            bot.send_message(
                message.chat.id,
                "❌ Барои истифодаи бот аввал ба ҳамаи каналҳо обуна шавед!"
            )
            show_subscription_requirement(message, movie_id)
        return
    
    # Санҷиш барои номи филм
    if message.reply_to_message and message.reply_to_message.text == "🔎 Номи филмро нависед:":
        title = message.text
        user_id = message.from_user.id
        
        if check_all_subscriptions(user_id):
            movies = search_movies_by_title(title)
            if movies:
                if len(movies) == 1:
                    # Як филм ёфт шуд
                    movie = movies[0]
                    try:
                        bot.send_video(
                            message.chat.id,
                            movie[2],  # file_id
                            caption=f"🎬 {movie[3]}\n\n{movie[4]}"
                        )
                    except:
                        bot.send_message(message.chat.id, "❌ Хатогӣ ҳангоми фиристодани филм.")
                else:
                    # Якчанд филм ёфт шуд
                    markup = types.InlineKeyboardMarkup()
                    text = f"🔎 {len(movies)} та филм ёфт шуд:\n\n"
                    
                    for movie in movies:
                        text += f"🎬 {movie[3]} (ID: {movie[1]})\n"
                        markup.add(
                            types.InlineKeyboardButton(
                                f"📹 {movie[3][:30]}...",
                                callback_data=f"select_{movie[1]}"
                            )
                        )
                    
                    bot.send_message(message.chat.id, text, reply_markup=markup)
            else:
                bot.send_message(message.chat.id, f"❌ Филм бо номи '{title}' ёфт нашуд.")
        else:
            bot.send_message(
                message.chat.id,
                "❌ Барои истифодаи бот аввал ба ҳамаи каналҳо обуна шавед!"
            )
            show_subscription_requirement(message)
        return
    
    # Агар матн ID-и филм бошад
    movie = get_movie(message.text)
    if movie:
        if check_all_subscriptions(message.from_user.id):
            try:
                bot.send_video(
                    message.chat.id,
                    movie[2],  # file_id
                    caption=f"🎬 {movie[3]}\n\n{movie[4]}"
                )
            except:
                bot.send_message(
                    message.chat.id,
                    "❌ Хатогӣ ҳангоми фиристодани филм."
                )
        else:
            show_subscription_requirement(message, message.text)
    else:
        bot.send_message(
            message.chat.id,
            "🤔 Ман шуморо нафаҳмидам.\n\n"
            "Барои кор бо бот:\n"
            "• Аз силкаи махсус истифода кунед\n"
            "• Тугмаи 'Поиск по ID' ё 'Поиск по названию' -ро истифода кунед\n"
            "• Команда /start -ро истифода кунед"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def select_movie_callback(call):
    movie_id = call.data.replace('select_', '')
    movie = get_movie(movie_id)
    
    if movie:
        try:
            bot.send_video(
                call.message.chat.id,
                movie[2],  # file_id
                caption=f"🎬 {movie[3]}\n\n{movie[4]}"
            )
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            bot.send_message(call.message.chat.id, "❌ Хатогӣ ҳангоми фиристодани филм.")
    else:
        bot.answer_callback_query(call.id, "❌ Филм ёфт нашуд!")

if __name__ == '__main__':
    print("🤖 Бот оғоз ёфт...")
    init_database()
    
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        logger.error(f"Хатогӣ: {e}")
        print("❌ Хатогӣ дар кори бот!")