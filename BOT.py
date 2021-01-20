import sqlite3
from datetime import date, datetime
from time import localtime

from aiogram import Dispatcher, Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils import executor

from STEP.config import TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
# dp.middleware.setup(LoggingMiddleware())

conn = sqlite3.connect("database.db")
cur = conn.cursor()
unique_key = 0  # Переменная для того, чтобы элементы записывались в последнюю строку (смотри ф-ю adding)

add_event_btn = KeyboardButton("Добавить событие")
show_event_btn = KeyboardButton("Показать все события на 3 дня")
output = ReplyKeyboardMarkup()
output.add(add_event_btn, show_event_btn)


class Reminder(StatesGroup):
    date_state = State()
    time_state = State()
    name_state = State()
    comm_state = State()
    last_one = State()


@dp.message_handler(commands='start', state="*")
async def start(message: types.Message):
    await message.answer("Выберете что будем делать:", reply_markup=output)


@dp.message_handler(Text(equals=["Добавить событие"]))
async def adding(message: types.Message):
    global unique_key
    cur.execute("""CREATE TABLE IF NOT EXISTS my_events(
       unique_key INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
       id_telegram INTEGER,
       date TEXT ,
       time TEXT,
       ev_name TEXT,
       ev_comm TEXT);
    """)

    cur.execute(f"""INSERT INTO my_events (id_telegram) VALUES ({message.from_user.id})""")
    unique_key = cur.lastrowid  # lastrowid - дичь, которая возвращает последний номер строки в таблице (int)
    conn.commit()
    await message.answer("В какой день напомнить?\n (дата формата YYYY-MM-DD)")
    await Reminder.date_state.set()


@dp.message_handler(state=Reminder.date_state, content_types=types.ContentTypes.TEXT)
async def set_date(message: types.Message):
    date = message.text

    conn.execute(f'UPDATE my_events SET date = ? WHERE unique_key = ?',
                 (date, unique_key))    # Пример использования. Записывает в последнюю строку, а не в произвольную
    conn.commit()
    await message.answer("в какое время напомнить?\n (время формата HH:MM)")
    await Reminder.next()


@dp.message_handler(state=Reminder.time_state, content_types=types.ContentTypes.TEXT)
async def set_time(message: types.Message):
    time = message.text

    conn.execute(f'UPDATE my_events SET time = ? WHERE unique_key = ?',
                 (time, unique_key))
    conn.commit()
    await message.answer("Как называется ваше событие?")
    await Reminder.next()


@dp.message_handler(state=Reminder.name_state, content_types=types.ContentTypes.TEXT)
async def set_name(message: types.Message):
    name = message.text

    conn.execute(f'UPDATE my_events SET ev_name = ? WHERE unique_key = ?',
                 (name, unique_key))
    conn.commit()
    await message.answer("Введите комментарий к событию")
    await Reminder.next()


# Проблемный участок.
@dp.message_handler(state=Reminder.comm_state)
async def set_comm(message: types.Message, state: FSMContext):
    name = message.text  # Считываю коммент

    conn.execute(f'UPDATE my_events SET ev_comm = ? WHERE unique_key = ?',
                 (name, unique_key))  # Записываю в бд
    conn.commit()

    # Беру ид пользователя чтобы не выводило других пользователей
    us_id = cur.execute("SELECT id_telegram FROM my_events;").fetchone()[0]
    running = True  # Переменная для остановки цикла в случае если бот отправил сообщение с данными

    # Цикл проверки времени и даты. Не заканчивается, пока не выведет напоминание
    while running:
        date_now = cur.execute("SELECT date('now');").fetchone()[0]     # Текущая дата
        time_now = datetime.now().strftime("%H:%M")     # Текащее время (часы и минуты)

        # Если в бд не находит нужную строку, то выдаёт значение None. из-за этого выдает ошибку ValueError. Я её ловлю.
        # По идее, когда время "сейчас" совпадает со временем из бд, то в переменную записывается результат и
        try:
            check_time = cur.execute("SELECT time FROM my_events WHERE time=?;", (time_now, date_now)).fetchone()[0]
            check_date = cur.execute("SELECT date FROM my_events WHERE ;", date_now).fetchone()[0]
        except ValueError:
            pass

        print("check", check_date)
        print("check", check_time)
        print("now", date_now)
        print("now", time_now)

        # Проверка. Если время и дата сейчас совпадает с временем и датой из бд, то выводится сообщение из бд.
        # if name != "Добавить событие":
        if check_date == date_now and check_time == time_now and us_id == message.from_user.id:
            await bot.send_message(message.from_user.id, "Здесь данные из бд короче")
            running = False

    else:
        print("вайл закончен")

    # else:
    #     await state.finish()

    # print("check", check_date)
    # print("check", check_time)
    # print("now", date_now)
    # print("now", time_now)
    all_results = cur.execute("SELECT * FROM my_events;").fetchall()
    print("Все э-ты бд: ", all_results)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
