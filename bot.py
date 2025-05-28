from telethon import TelegramClient, events, Button
from datetime import datetime
import asyncio
import pytz
import os

# Настройки (замените на свои реальные данные)
API_ID = 2040
API_HASH = 'b18441a1ff607e10a989891a5462e627'
BOT_TOKEN = '7471754956:AAG89p6t1lkFt_jsrn4nFoHiLVdRtOzI0Y4'
ADMIN_ID = 464586595
# ADMIN_ID = 5477341107
USERS_FILE = 'users.txt'

# Чек-листы
MORNING_CHECKLIST = [
    "1. Проверил почту?",
    "2. Проверил задачи на сегодня?",
    "3. Составил план работы?"
]

EVENING_CHECKLIST = [
    "1. Выполнил все основные задачи?",
    "2. Ответил на все сообщения?",
    "3. Подготовил план на завтра?"
]

# Хранение данных
user_data = {}

client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def load_users():
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, 'r') as f:
        return {int(line.strip()) for line in f if line.strip()}

def save_user(user_id):
    users = load_users()
    users.add(user_id)
    with open(USERS_FILE, 'w') as f:
        for uid in users:
            f.write(f"{uid}\n")

async def send_checklist(user_id, checklist_type):
    checklist = MORNING_CHECKLIST if checklist_type == 'morning' else EVENING_CHECKLIST
    user_data[user_id] = {
        'checklist': checklist,
        'answers': [],
        'details': [],
        'current_question': 0,
        'type': checklist_type
    }
    
    await client.send_message(user_id, f"📋 {'Утренний' if checklist_type == 'morning' else 'Вечерний'} чек-лист:")
    await ask_question(user_id)

async def ask_question(user_id):
    data = user_data[user_id]
    if data['current_question'] < len(data['checklist']):
        question = data['checklist'][data['current_question']]
        # Используем правильный метод создания кнопок
        buttons = [
            [Button.inline('Да', b'yes'), Button.inline('Нет', b'no')]
        ]
        await client.send_message(user_id, question, buttons=buttons)
    else:
        await finish_checklist(user_id)

async def finish_checklist(user_id):
    data = user_data[user_id]
    checklist_type = "Утренний" if data['type'] == 'morning' else "Вечерний"
    
    report = f"📊 {checklist_type} чек-лист от {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    for i in range(len(data['checklist'])):
        report += f"{data['checklist'][i]}\nОтвет: {'Да' if data['answers'][i] else 'Нет'}"
        if not data['answers'][i] and i < len(data['details']):
            report += f"\nПояснение: {data['details'][i]}\n"
        report += "\n"
    
    await client.send_message(ADMIN_ID, report)
    await client.send_message(user_id, "Спасибо! Чек-лист отправлен руководителю.")
    del user_data[user_id]

async def send_test_checklists():
    users = load_users()
    if not users:
        print("Нет пользователей для отправки")
        return
    
    print(f"Начинаю тестовую отправку для {len(users)} пользователей...")
    for user_id in users:
        try:
            print(f"Отправляю тестовый чек-лист пользователю {user_id}")
            await send_checklist(user_id, 'morning')
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Ошибка при отправке пользователю {user_id}: {str(e)}")
    print("Тестовая отправка завершена")

async def schedule_checklists():
    while True:
        now = datetime.now(pytz.timezone('Europe/Moscow')).time()
        
        if now.hour == 9 and now.minute == 0:
            for user_id in load_users():
                try:
                    await send_checklist(user_id, 'morning')
                except Exception as e:
                    print(f"Ошибка при отправке пользователю {user_id}: {str(e)}")
        
        elif now.hour == 18 and now.minute == 0:
            for user_id in load_users():
                try:
                    await send_checklist(user_id, 'evening')
                except Exception as e:
                    print(f"Ошибка при отправке пользователю {user_id}: {str(e)}")
        
        await asyncio.sleep(60)

@client.on(events.CallbackQuery)
async def callback_handler(event):
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
        data['current_question'] += 1
        data['details'].append(None)
        await ask_question(user_id)
    
    await event.delete()

@client.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    
    if user_id == ADMIN_ID:
        if event.text.lower() == '/test':
            await send_test_checklists()
        return
    
    if user_id not in load_users():
        save_user(user_id)
        await event.respond("Вы подписаны на ежедневные чек-листы!")
    
    if user_id in user_data:
        data = user_data[user_id]
        if data.get('waiting_for_details'):
            data['details'].append(event.text)
            data['current_question'] += 1
            data['waiting_for_details'] = False
            await ask_question(user_id)

async def main():
    await client.start()
    print("Бот запущен!")
    await send_test_checklists()  # Тестовая отправка при запуске
    await schedule_checklists()

if __name__ == '__main__':
    client.loop.run_until_complete(main())