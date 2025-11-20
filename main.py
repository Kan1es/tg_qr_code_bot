import os
import qrcode
from io import BytesIO
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()


# Создаем состояния для диалога
class QRDesign(StatesGroup):
    waiting_for_url = State()
    waiting_for_fill = State()
    waiting_for_back = State()


# Настройки бота
API_TOKEN = os.getenv('BOT_TOKEN')
if not API_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# База данных для хранения настроек (в памяти)
user_settings = {}


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🤖 QR Code Generator Bot\n\n"
        "Отправьте мне ссылку для создания QR-кода\n"
        "Используйте /design для настройки цветов\n"
        "/reset - сбросить настройки дизайна"
    )


@dp.message(Command("design"))
async def cmd_design(message: Message, state: FSMContext):
    await message.answer(
        "🎨 Настройка дизайна QR-кода\n\n"
        "Введите цвет заливки в HEX формате:\n"
        "• #FF0000 - красный\n"
        "• #0000FF - синий\n"
        "• #000000 - черный (по умолчанию)\n\n"
        "Пример: #FF5733"
    )
    await state.set_state(QRDesign.waiting_for_fill)


@dp.message(QRDesign.waiting_for_fill)
async def process_fill_color(message: Message, state: FSMContext):
    if not is_valid_hex(message.text):
        await message.answer("❌ Неверный формат цвета. Используйте HEX формат (#FF0000):")
        return

    user_settings[message.from_user.id] = {"fill_color": message.text}
    await message.answer(
        "✅ Цвет заливки сохранен!\n\n"
        "Теперь введите цвет фона в HEX формате:\n"
        "• #FFFFFF - белый (по умолчанию)\n"
        "• #FFFF00 - желтый\n"
        "• #00FF00 - зеленый\n\n"
        "Пример: #FFFFFF"
    )
    await state.set_state(QRDesign.waiting_for_back)


@dp.message(QRDesign.waiting_for_back)
async def process_back_color(message: Message, state: FSMContext):
    if not is_valid_hex(message.text):
        await message.answer("❌ Неверный формат цвета. Используйте HEX формат (#FFFFFF):")
        return

    user_settings[message.from_user.id]["back_color"] = message.text
    await message.answer(
        "✅ Настройки дизайна сохранены!\n\n"
        "Теперь отправьте мне ссылку для создания QR-кода\n"
        "Пример: https://example.com"
    )
    await state.set_state(QRDesign.waiting_for_url)


@dp.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    user_settings.pop(message.from_user.id, None)
    await state.clear()
    await message.answer("✅ Настройки дизайна сброшены до значений по умолчанию")


def is_valid_hex(color: str) -> bool:
    """Проверяет валидность HEX-цвета"""
    color = color.strip().lstrip('#')
    return len(color) == 6 and all(c in '0123456789ABCDEFabcdef' for c in color)


def generate_qr(url: str, user_id: int) -> BufferedInputFile:
    """Генерирует QR-код с настройками пользователя"""
    settings = user_settings.get(user_id, {})

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(
        fill_color=settings.get('fill_color', 'black'),
        back_color=settings.get('back_color', 'white')
    )

    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return BufferedInputFile(buf.read(), filename="qr_code.png")


@dp.message(F.text)
async def process_url(message: Message, state: FSMContext):
    # Проверяем что это ссылка
    if not message.text.startswith(('http://', 'https://')):
        await message.answer("❌ Пожалуйста, отправьте валидную ссылку (начинается с http:// или https://)")
        return

    try:
        await message.answer("⏳ Генерирую QR-код...")
        qr_file = generate_qr(message.text, message.from_user.id)

        # Получаем текущие настройки пользователя для отображения в подписи
        settings = user_settings.get(message.from_user.id, {})
        fill_color = settings.get('fill_color', 'черный')
        back_color = settings.get('back_color', 'белый')

        await message.answer_photo(
            photo=qr_file,
            caption=f"✅ Ваш QR-код\n\n"
                    f"Ссылка: {message.text}\n"
                    f"Цвет: {fill_color}\n"
                    f"Фон: {back_color}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при генерации QR-кода: {str(e)}")


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())