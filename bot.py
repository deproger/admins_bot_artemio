import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
import pytz

# Загрузка переменных из .env
load_dotenv()

# Конфигурация
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Moscow')
MORNING_TIME = os.getenv('MORNING_TIME', '09:00').split(':')
EVENING_TIME = os.getenv('EVENING_TIME', '20:00').split(':')

# Чек-листы
MORNING_CHECKLIST = [
    ("Привет! Какой администратор сегодня на смене?", "text"),
    ("Кто сегодня работает из мастеров?", "text"),
    ("Кто-то опоздал?", "text"),
    ("Кофемашина в порядке? Есть пенка, не течёт?", "yesno"),
    ("Уборка в порядке? Входная дверь, окна чистые?", "yesno"),
    ("В зоне рецепции есть лишние предметы?", "yesno"),
    ("В туалете нет запаха, есть полотенца, бумага, освежитель?", "yesno")
]

EVENING_CHECKLIST = [
    ("День прошел без происшествий?", "yesno"),
    ("Предлагали кому-то из клиентов Ruha?", "yesno"),
    ("Заканчиваются ли какие-то расходники? (воротники, кофе, молоко, сахар, шоколад и т.д.)", "yesno"),
    ("Были ли конфликтные ситуации?", "yesno"),
    ("Напоминание перед уходом:", "reminder", "Не забудьте выключить кондиционер, телевизор, нагреватель полотенец")
]

# Файлы данных
USERS_FILE = 'users.txt'
LOGS_DIR = 'logs'

# Хранение данных
user_data = {}

# Инициализация клиента
client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)


def setup():
    """Создает необходимые директории и файлы"""
    os.makedirs(LOGS_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        open(USERS_FILE, 'w').close()

def load_users():
    """Загружает список пользователей"""
    with open(USERS_FILE, 'r') as f:
        return {int(line.strip()) for line in f if line.strip()}

def save_user(user_id):
    """Сохраняет нового пользователя"""
    users = load_users()
    users.add(user_id)
    with open(USERS_FILE, 'w') as f:
        for uid in users:
            f.write(f"{uid}\n")

async def send_checklist(user_id, checklist_type):
    """Начинает отправку чек-листа"""
    checklist = MORNING_CHECKLIST if checklist_type == 'morning' else EVENING_CHECKLIST
    user_data[user_id] = {
        'checklist': checklist,
        'answers': [],
        'details': [],
        'current_question': 0,
        'type': checklist_type,
        'date': datetime.now().strftime('%Y-%m-%d')
    }
    
    greeting = "🌞 Доброе утро! Чек-лист БРО (утро)" if checklist_type == 'morning' else "🌙 Добрый вечер! Чек-лист БРО (вечер)"
    await client.send_message(user_id, greeting)
    await ask_question(user_id)

async def ask_question(user_id):
    """Задает следующий вопрос из чек-листа"""
    data = user_data[user_id]
    if data['current_question'] < len(data['checklist']):
        question, qtype, *extra = data['checklist'][data['current_question']]
        
        if qtype == 'yesno':
            buttons = [[Button.inline('Да', b'yes'), Button.inline('Нет', b'no')]]
            await client.send_message(user_id, question, buttons=buttons)
        elif qtype == 'text':
            await client.send_message(user_id, f"{question}\n(Ответьте текстовым сообщением)")
        elif qtype == 'reminder':
            data['answers'].append(None)
            data['details'].append(extra[0])
            data['current_question'] += 1
            await ask_question(user_id)
    else:
        await finish_checklist(user_id)

async def finish_checklist(user_id):
    """Завершает чек-лист и отправляет отчет"""
    data = user_data[user_id]
    checklist_type = "Утренний" if data['type'] == 'morning' else "Вечерний"
    
    # Формируем отчет
    report = f"📋 {checklist_type} чек-лист БРО {data['date']}\n\n"
    for i, (question, qtype, *_) in enumerate(data['checklist']):
        report += f"{question}\n"
        
        if qtype in ('yesno', 'text'):
            if qtype == 'yesno':
                answer = "Да" if data['answers'][i] else "Нет"
                report += f"Ответ: {answer}\n"
            if i < len(data['details']) and data['details'][i]:
                report += f"Подробности: {data['details'][i]}\n"
        elif qtype == 'reminder':
            report += f"Напоминание: {data['details'][i]}\n"
        
        report += "\n"
    
    # Сохраняем в лог
    log_file = os.path.join(LOGS_DIR, f"{data['type']}_{data['date']}.txt")
    with open(log_file, 'a') as f:
        f.write(f"=== Отчет от пользователя {user_id} ===\n")
        f.write(report)
        f.write("\n")
    
    # Отправляем отчет
    await client.send_message(ADMIN_ID, f"📩 Новый отчет от @{(await client.get_entity(user_id)).username}:\n\n{report}")
    await client.send_message(user_id, "✅ Спасибо! Чек-лист отправлен руководителю.")
    del user_data[user_id]

async def check_time(target_hour, target_minute):
    """Проверяет наступление времени для отправки"""
    now = datetime.now(pytz.timezone(TIMEZONE))
    return now.hour == target_hour and now.minute == target_minute

async def schedule_checklists():
    """Планировщик отправки чек-листов"""
    while True:
        # Утренний чек-лист
        if await check_time(int(MORNING_TIME[0]), int(MORNING_TIME[1])):
            for user_id in load_users():
                try:
                    await send_checklist(user_id, 'morning')
                    await asyncio.sleep(1)  # Задержка между отправками
                except Exception as e:
                    print(f"Ошибка при отправке утреннего чек-листа пользователю {user_id}: {e}")
        
        # Вечерний чек-лист
        elif await check_time(int(EVENING_TIME[0]), int(EVENING_TIME[1])):
            for user_id in load_users():
                try:
                    await send_checklist(user_id, 'evening')
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"Ошибка при отправке вечернего чек-листа пользователю {user_id}: {e}")
        
        await asyncio.sleep(30)  # Проверяем каждые 30 секунд

@client.on(events.CallbackQuery)
async def callback_handler(event):
    """Обработчик кнопок Да/Нет"""
    user_id = event.sender_id
    if user_id not in user_data:
        return
    
    data = user_data[user_id]
    answer = event.data == b'yes'
    data['answers'].append(answer)
    
    if not answer:
        await event.respond("Пожалуйста, укажите подробности:")
        data['waiting_for_details'] = True
    else:
        data['details'].append(None)
        data['current_question'] += 1
    
    await ask_question(user_id)
    await event.delete()

@client.on(events.NewMessage)
async def message_handler(event):
    """Обработчик текстовых сообщений"""
    user_id = event.sender_id
    
    # Команды администратора
    if user_id == ADMIN_ID:
        if event.text.lower() == '/test':
            await send_test_checklists(event)
        elif event.text.lower() == '/users':
            users = load_users()
            await event.respond(f"Всего подписчиков: {len(users)}\nID: {', '.join(map(str, users))}")
        return
    
    # Подписка новых пользователей
    if user_id not in load_users():
        save_user(user_id)
        await event.respond("👋 Добро пожаловать! Вы подписаны на ежедневные чек-листы БРО.")
        return
    
    # Обработка ответов на вопросы
    if user_id in user_data:
        data = user_data[user_id]
        
        if data.get('waiting_for_details'):
            data['details'].append(event.text)
            data['current_question'] += 1
            data['waiting_for_details'] = False
            await ask_question(user_id)
        elif data['current_question'] < len(data['checklist']):
            qtype = data['checklist'][data['current_question']][1]
            if qtype == 'text':
                data['answers'].append(True)  # Для текстовых вопросов
                data['details'].append(event.text)
                data['current_question'] += 1
                await ask_question(user_id)

async def send_test_checklists(event=None):
    """Тестовая отправка чек-листов"""
    users = load_users()
    if not users:
        msg = "❌ Нет подписчиков для отправки"
        print(msg)
        if event: await event.respond(msg)
        return
    
    msg = f"Начинаю тестовую отправку для {len(users)} пользователей..."
    print(msg)
    if event: await event.respond(msg)
    
    for user_id in users:
        try:
            await send_checklist(user_id, 'morning')
            await asyncio.sleep(1)
        except Exception as e:
            error = f"Ошибка при отправке пользователю {user_id}: {e}"
            print(error)
            if event: await event.respond(error)
    
    msg = "✅ Тестовая отправка завершена"
    print(msg)
    if event: await event.respond(msg)

async def main():
    """Основная функция"""
    setup()
    await client.start()
    print("🤖 Бот БРО чек-листов запущен!")
    await schedule_checklists()

if __name__ == '__main__':
    client.loop.run_until_complete(main())