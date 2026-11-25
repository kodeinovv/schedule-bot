import telebot
import requests
import re
import datetime
import os
import threading
from flask import Flask
from bs4 import BeautifulSoup
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКИ ---
BOT_TOKEN = '118032841:AAH3VxWpIgBWm3DT-hqD42uinFMvMYYR-2c'
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
        
        # --- ИСПРАВЛЕНИЕ ЧАСОВОГО ПОЯСА ---
        # Берем время UTC (Лондон) и прибавляем 4 часа (Саратов).
        # Если у тебя московское время, поменяй на hours=3
        today = datetime.datetime.utcnow() + datetime.timedelta(hours=4)
        
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
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📅 Сегодня", callback_data="today"),
        InlineKeyboardButton("📅 Завтра", callback_data="tomorrow"),
        InlineKeyboardButton("🗓 На неделю", callback_data="week")
    )
    bot.send_message(message.chat.id, "Привет! Выбери день:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['today', 'tomorrow', 'week'])
def callback_schedule(call):
    bot.answer_callback_query(call.id, "Загружаю...")
    schedule_text = get_schedule_text(call.data)
    
    if len(schedule_text) > 4000:
        chunks = schedule_text.split('\n📅 ')
        current_chunk = "📅 " + chunks[0] if chunks[0] else ""
        for chunk in chunks[1:]:
            if len(current_chunk) + len(chunk) > 4000:
                bot.send_message(call.message.chat.id, current_chunk, parse_mode='HTML')
                current_chunk = "📅 " + chunk
            else:
                current_chunk += "\n📅 " + chunk
        if current_chunk:
            bot.send_message(call.message.chat.id, current_chunk, parse_mode='HTML')
    else:
        bot.send_message(call.message.chat.id, schedule_text, parse_mode='HTML')

# --- ЗАПУСК БОТА В ФОНЕ ---
def run_bot():
    bot.remove_webhook()
    bot.infinity_polling()

threading.Thread(target=run_bot, daemon=True).start()

# --- ВЕБ-СЕРВЕР ---
@app.route('/', methods=['GET'])
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
