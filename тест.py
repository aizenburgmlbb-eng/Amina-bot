import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8397692001:AAGaxr3My_8H3w0V1f3oC-ao6oUV4a1jKiI"
CHANNEL_ID = -1003825160417
DB_PATH = "counters.db"

PHOTO_FILE_ID = "AgACAgIAAxkBAAIQfmrYHJtO-C_Kvr5aNSmrDLdPxrFVAALkImsbC8vBSoH8VGhq2PpAAQADAgADdwADPQQ"
CAPTION = "Ⲕⲧⲟ ⲧы ⲙⲏⲉ?"

# ключи счётчиков
K_FRIEND = "friend"
K_PASSER = "passer"
K_WANT = "want"

# ================== БД ==================
def db_init() -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS counters ("
            "name TEXT PRIMARY KEY, value INTEGER NOT NULL DEFAULT 0)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS votes ("
            "user_id INTEGER PRIMARY KEY, choice TEXT NOT NULL)"
        )
        for name in (K_FRIEND, K_PASSER, K_WANT):
            con.execute(
                "INSERT OR IGNORE INTO counters (name, value) VALUES (?, 0)",
                (name,),
            )


def get_counts() -> dict[str, int]:
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute("SELECT name, value FROM counters").fetchall()
    return {name: value for name, value in rows}


def get_user_choice(user_id: int) -> str | None:
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT choice FROM votes WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row[0] if row else None


def set_user_choice(user_id: int, choice: str) -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO votes (user_id, choice) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET choice = excluded.choice",
            (user_id, choice),
        )


def change_counter(name: str, delta: int) -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "UPDATE counters SET value = value + ? WHERE name = ?",
            (delta, name),
        )


# ================== КЛАВИАТУРА ==================
def build_kb() -> InlineKeyboardMarkup:
    c = get_counts()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Друг ({c[K_FRIEND]})", callback_data=K_FRIEND
                ),
                InlineKeyboardButton(
                    text=f"прохожий ({c[K_PASSER]})", callback_data=K_PASSER
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"тот, кто хочет подружиться ({c[K_WANT]})",
                    callback_data=K_WANT,
                )
            ],
        ]
    )


# ================== ХЕНДЛЕРЫ ==================
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    # отправляем сообщение в канал
    await message.bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=PHOTO_FILE_ID,
        caption=CAPTION,
        reply_markup=build_kb(),
    )
    await message.answer("Сообщение отправлено в канал.")


@dp.callback_query(F.data.in_({K_FRIEND, K_PASSER, K_WANT}))
async def on_vote(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    new_choice = callback.data
    old_choice = get_user_choice(user_id)

    if old_choice == new_choice:
        # повторно на ту же кнопку — нельзя
        await callback.answer("Вы уже выбрали этот вариант", show_alert=False)
        return

    if old_choice is None:
        change_counter(new_choice, +1)
    else:
        change_counter(old_choice, -1)
        change_counter(new_choice, +1)

    set_user_choice(user_id, new_choice)

    # обновляем сообщение в канале (текст кнопок)
    try:
        await callback.message.edit_reply_markup(reply_markup=build_kb())
    except Exception:
        # если ничего не изменилось / нет прав / не то сообщение
        pass

    await callback.answer("Голос учтён")


async def main() -> None:
    db_init()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())