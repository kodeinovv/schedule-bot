import telebot
import requests
import re
import datetime
import os
from flask import Flask, request
from bs4 import BeautifulSoup
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКИ ---
BOT_TOKEN = '9118032841:AAEUyIqUxUFYmFRm2GKnyW2WDEReWVEUD7k'
SCHEDULE_URL = 'http://techn.sstu.ru/schedule/spo_2026/cg22.htm'

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- ПАРСЕР ---
def get_schedule_text(action):
    try:
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
        response = requests.get(SCHEDULE_URL, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', class_='inf')
        if not table:
            return "Не удалось найти таблицу с расписанием на странице."
        
        rows = table.find_all('tr')
        days_data = {}
        current_date = None
        
        date_pattern = re.compile(r'\d{2}\.\d{2}\.\d{4}\s+[А-Яа-я]{2}-\d')
        
        for row in rows:
            cells = row.find_all('td')
            cell_texts = []
            for cell in cells:
                text = cell.get_text(separator=' ', strip=True)
                if text:
                    cell_texts.append(text)
            
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
                        time_info = time_info.replace(date_match.group(0), '').strip()
                        time_info = time_info.lstrip('| -').strip()

                    if not time_info and len(cell_texts) >= 2:
                        time_info = cell_texts[1]
                        cell_texts = cell_texts[1:] 

                    if current_date:
                        if len(cell_texts) >= 2:
                            subject_info = cell_texts[1]
                            if len(cell_texts) > 2:
                                subject_info += f"\n    ➡ {cell_texts[2]}"
                            days_data[current_date].append(f"🔹 <b>{time_info}</b>\n    {subject_info}")
                        else:
                            days_data[current_date].append(f"🔹 {line}")
        
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
                    if pairs:
                        result_text += '\n'.join(pairs) + "\n\n"
                    else:
                        result_text += "Пар нет! Отдыхай 🎉\n\n"
            if not found:
                result_text = f"На сегодня ({today_str}) пар нет (или расписание ещё не обновлено)."
                
        elif action == 'tomorrow':
            found = False
            for date, pairs in days_data.items():
                if tomorrow_str in date:
                    found = True
                    result_text += f"📅 <b>{date}</b>\n"
                    if pairs:
                        result_text += '\n'.join(pairs) + "\n\n"
                    else:
                        result_text += "Пар нет! Отдыхай 🎉\n\n"
            if not found:
                result_text = f"На завтра ({tomorrow_str}) пар нет (или расписание ещё не обновлено)."
                
        else:
            for date, pairs in days_data.items():
                result_text += f"\n📅 <b>{date}</b>\n"
                if pairs:
                    result_text += '\n'.join(pairs) + "\n"
                else:
                    result_text += "Пар нет 🎉\n"
                    
        return result_text.strip()
    except Exception as e:
        return f"Ошибка: {e}"

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start_message(message):
    markup = InlineKeyboardMarkup(row_width=2)
    btn_today = InlineKeyboardButton("📅 Сегодня", callback_data="today")
    btn_tomorrow = InlineKeyboardButton("📅 Завтра", callback_data="tomorrow")
    btn_week = InlineKeyboardButton("🗓 На неделю", callback_data="week")
    markup.add(btn_today, btn_tomorrow)
    markup.add(btn_week)
    
    bot.send_message(message.chat.id, "Привет! Выбери, на какой день показать расписание:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['today', 'tomorrow', 'week'])
def callback_schedule(call):
    bot.answer_callback_query(call.id, "Загружаю...")
    action = call.data
    schedule_text = get_schedule_text(action)
    
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

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
    if render_url:
        bot.set_webhook(url=f"{render_url}/{BOT_TOKEN}")
    return "Webhook set!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
    if render_url:
        bot.set_webhook(url=f"{render_url}/{B
