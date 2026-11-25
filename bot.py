import telebot
import requests
import re
import datetime
import os
import traceback
from flask import Flask, request
from bs4 import BeautifulSoup
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКИ ---
BOT_TOKEN = '9118032841:AAEUyIqUxUFYmFRm2GKnyW2WDEReWVEUD7k'
SCHEDULE_URL = 'http://techn.sstu.ru/schedule/spo_2026/cg22.htm'

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

def get_schedule_text(action):
    try:
        headers = {'Cache-Control': 'no-cache'}
        response = requests.get(SCHEDULE_URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', class_='inf')
        if not table:
            return "Не удалось найти таблицу."
        
        rows = table.find_all('tr')
        days_data = {}
        current_date = None
        date_pattern = re.compile(r'\d{2}\.\d{2}\.\d{4}\s+[А-Яа-я]{2}-\d')
        
        for row in rows:
            cells = row.find_all('td')
            cell_texts = [cell.get_text(separator=' ', strip=True) for cell in cells if cell.get_text(strip=True)]
            
            if cell_texts:
                line = ' | '.join(cell_texts)
                if "День" in line and "Пара" in line:
                    continue
                
                date_match = date_pattern.search(line)
                
                if date_match and "Пара" not in line:
                    current_date = date_match.group(0)
                    days_data[current_date] = []
                
                elif "Пара" in line:
                    time_info = cell_texts[0]
                    if date_match:
                        current_date = date_match.group(0)
                        if current_date not in days_data:
                            days_data[current_date] = []
                        time_info = time_info.replace(date_match.group(0), '').strip().lstrip('| -').strip()

                    if current_date:
                        if len(cell_texts) >= 2:
                            subject_info = cell_texts[1]
                            if len(cell_texts) > 2:
                                subject_info += f"\n    ➡ {cell_texts[2]}"
                            days_data[current_date].append(f"🔹 <b>{time_info}</b>\n    {subject_info}")
        
        today = datetime.datetime.now()
        today_str = today.strftime('%d.%m.%Y')
        tomorrow_str = (today + datetime.timedelta(days=1)).strftime('%d.%m.%Y')
        
        result_text = ""
        
        if action == 'today':
            found = False
            for date, pairs in days_data.items():
                if today_str in date:
                    found = True
                    result_text += f"📅 <b>{date}</b>\n"
                    result_text += ('\n'.join(pairs) + "\n\n") if pairs else "Пар нет! Отдыхай 🎉\n\n"
            if not found: result_text = f"На сегодня ({today_str}) пар нет."
                
        elif action == 'tomorrow':
            found = False
            for date, pairs in days_data.items():
                if tomorrow_str in date:
                    found = True
                    result_text += f"📅 <b>{date}</b>\n"
                    result_text += ('\n'.join(pairs) + "\n\n") if pairs else "Пар нет! Отдыхай 🎉\n\n"
            if not found: result_text = f"На завтра ({tomorrow_str}) пар нет."
                
        else:
            for date, pairs in days_data.items():
                result_text += f"\n📅 <b>{date}</b>\n"
                result_text += ('\n'.join(pairs) + "\n") if pairs else "Пар нет 🎉\n"
                    
        return result_text.strip()
    except Exception as e:
        return f"Ошибка: {e}"

@bot.message_handler(commands=['start'])
def start_message(message):
    print(f"ОТЛАДКА: Получена команда /start от {message.chat.id}")
    try:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📅 Сегодня", callback_data="today"),
            InlineKeyboardButton("📅 Завтра", callback_data="tomorrow"),
            InlineKeyboardButton("🗓 На неделю", callback_data="week")
        )
        bot.send_message(message.chat.id, "Привет! Выбери день:", reply_markup=markup)
        print("ОТЛАДКА: Сообщение успешно отправлено!")
    except Exception as e:
        print(f"ОТЛАДКА ОШИБКА ОТПРАВКИ: {e}")

# --- ВЕБ-СЕРВЕР ---
@app.route('/', methods=['GET'])
def index():
    return "Bot is running!", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    print("ОТЛАДКА: Получен POST-запрос от Telegram!")
    try:
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return "!", 200
    except Exception as e:
        print("ОТЛАДКА ОШИБКА ОБРАБОТКИ:")
        print(traceback.format_exc())
        return "Error", 500
