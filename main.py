import os
import qrcode
from io import BytesIO
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()


# Создаем состояния для диалога
class QRDesign(StatesGroup):
    waiting_for_url = State()
    waiting_for_fill = State()
    waiting_for_back = State()


class AdminStates(StatesGroup):
    waiting_broadcast = State()


# Настройки бота
API_TOKEN = os.getenv('BOT_TOKEN')
if not API_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
admin_router = Router()

# База данных для хранения настроек (в памяти)
user_settings = {}
user_stats = {}  # Для хранения статистики пользователей


# Проверка прав администратора
def is_admin(user_id: int) -> bool:
    ADMINS = [int(admin_id) for admin_id in os.getenv('ADMIN_IDS', '').split(',') if admin_id]
    return user_id in ADMINS


# Клавиатуры
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎨 Создать QR-код"), KeyboardButton(text="⚙️ Настройки дизайна")],
            [KeyboardButton(text="📊 Моя статистика"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


def get_settings_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎨 Изменить цвета"), KeyboardButton(text="🔄 Сбросить настройки")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )


def get_qr_actions_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сгенерировать еще", callback_data="qr_regenerate")],
        [InlineKeyboardButton(text="🎨 Изменить цвета", callback_data="qr_redesign")],
        [InlineKeyboardButton(text="📱 Поделиться", callback_data="qr_share")]
    ])


def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🔄 Сброс кэша", callback_data="admin_clear_cache")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
    ])


# Функции для QR-кода
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

    # Обновляем статистику
    if user_id not in user_stats:
        user_stats[user_id] = {'qr_count': 0, 'last_active': datetime.now()}
    user_stats[user_id]['qr_count'] += 1
    user_stats[user_id]['last_active'] = datetime.now()

    return BufferedInputFile(buf.read(), filename="qr_code.png")


# Основные команды бота
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🤖 **QR Designer Bot**\n\n"
        "Создавайте стильные QR-коды за секунды!\n"
        "Просто отправьте ссылку или используйте кнопки ниже:",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("design"))
async def cmd_design(message: Message, state: FSMContext):
    await message.answer(
        "🎨 Настройка дизайна QR-кода\n\n"
        "Введите цвет заливки в HEX формате:\n"
        "• #FF0000 - красный\n"
        "• #0000FF - синий\n"
        "• #000000 - черный (по умолчанию)\n\n"
        "Пример: #FF5733",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(QRDesign.waiting_for_fill)


@dp.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    user_settings.pop(message.from_user.id, None)
    await state.clear()
    await message.answer("✅ Настройки дизайна сброшены до значений по умолчанию")


@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer(
        "🛠️ **Админ-панель QR Designer Bot**\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard()
    )


# Обработчики быстрых кнопок
@dp.message(F.text == "🎨 Создать QR-код")
async def quick_create_qr(message: Message):
    await message.answer(
        "Отправьте ссылку для создания QR-кода:",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(F.text == "⚙️ Настройки дизайна")
async def quick_settings(message: Message):
    await message.answer(
        "⚙️ **Настройки дизайна**",
        reply_markup=get_settings_keyboard()
    )


@dp.message(F.text == "🎨 Изменить цвета")
async def quick_change_colors(message: Message, state: FSMContext):
    await cmd_design(message, state)


@dp.message(F.text == "🔄 Сбросить настройки")
async def quick_reset_settings(message: Message):
    user_settings.pop(message.from_user.id, None)
    await message.answer("✅ Настройки сброшены")


@dp.message(F.text == "◀️ Назад")
async def quick_back(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )


@dp.message(F.text == "📊 Моя статистика")
async def quick_stats(message: Message):
    user_id = message.from_user.id
    settings = user_settings.get(user_id, {})
    stats = user_stats.get(user_id, {})

    await message.answer(
        f"📊 **Ваша статистика:**\n\n"
        f"• Текущие цвета:\n"
        f"  Заливка: {settings.get('fill_color', 'черный')}\n"
        f"  Фон: {settings.get('back_color', 'белый')}\n"
        f"• QR-кодов создано: {stats.get('qr_count', 0)}\n"
        f"• Последняя активность: {stats.get('last_active', 'нет данных')}"
    )


@dp.message(F.text == "ℹ️ Помощь")
async def quick_help(message: Message):
    await message.answer(
        "ℹ️ **Помощь по боту:**\n\n"
        "• Отправьте ссылку для создания QR-кода\n"
        "• Используйте настройки для изменения цветов\n"
        "• Поддерживаются цвета в HEX-формате (#FF0000)\n\n"
        "**Команды:**\n"
        "/start - Главное меню\n"
        "/design - Настройка цветов\n"
        "/reset - Сброс настроек\n"
        "/admin - Админ-панель (только для админов)",
        reply_markup=get_main_keyboard()
    )


# Обработчики состояний дизайна
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
        "Пример: https://example.com",
        reply_markup=get_main_keyboard()
    )
    await state.set_state(QRDesign.waiting_for_url)


# Обработчик ссылок для QR-кода
@dp.message(F.text.startswith(('http://', 'https://')))
async def process_url(message: Message, state: FSMContext):
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
                    f"Фон: {back_color}",
            reply_markup=get_qr_actions_keyboard()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при генерации QR-кода: {str(e)}")


# Инлайн-обработчики для быстрых действий с QR-кодом
@dp.callback_query(F.data.startswith("qr_"))
async def handle_qr_actions(callback: CallbackQuery, state: FSMContext):
    action = callback.data

    if action == "qr_regenerate":
        await callback.message.answer("Отправьте ссылку для нового QR-кода:")
        await callback.answer()

    elif action == "qr_redesign":
        await cmd_design(callback.message, state)
        await callback.answer()

    elif action == "qr_share":
        await callback.answer("📱 Поделитесь изображением с друзьями!")


# Админ-панель обработчики
@admin_router.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: CallbackQuery, state: FSMContext):
    action = callback.data

    if action == "admin_stats":
        stats = await get_bot_stats()
        await callback.message.edit_text(
            f"📊 **Статистика бота:**\n\n"
            f"• Пользователей: {stats['users_count']}\n"
            f"• QR-кодов создано: {stats['qr_count']}\n"
            f"• Активных за сутки: {stats['active_today']}\n"
            f"• Админов: {stats['admins_count']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
            ])
        )

    elif action == "admin_broadcast":
        await callback.message.edit_text(
            "📢 **Рассылка сообщений**\n\n"
            "Отправьте сообщение для рассылки всем пользователям:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Отмена", callback_data="admin_back")]
            ])
        )
        await state.set_state(AdminStates.waiting_broadcast)

    elif action == "admin_users":
        users_list = await get_recent_users()
        await callback.message.edit_text(
            f"👥 **Последние пользователи:**\n\n{users_list}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
            ])
        )

    elif action == "admin_clear_cache":
        user_settings.clear()
        await callback.answer("✅ Кэш настроек очищен")
        await admin_panel(callback.message)

    elif action == "admin_close":
        await callback.message.delete()

    elif action == "admin_back":
        await admin_panel(callback.message)

    await callback.answer()


# Обработчик рассылки
@admin_router.message(AdminStates.waiting_broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    users = list(user_stats.keys())
    success = 0
    failed = 0

    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 {message.text}")
            success += 1
        except:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена:\n"
        f"• Успешно: {success}\n"
        f"• Не доставлено: {failed}"
    )
    await state.clear()
    await admin_panel(message)


# Функции для статистики
async def get_bot_stats():
    today = datetime.now().date()
    active_today = sum(1 for stats in user_stats.values()
                       if stats.get('last_active').date() == today)

    return {
        "users_count": len(user_stats),
        "qr_count": sum(stats.get('qr_count', 0) for stats in user_stats.values()),
        "active_today": active_today,
        "admins_count": len([admin_id for admin_id in os.getenv('ADMIN_IDS', '').split(',') if admin_id])
    }


async def get_recent_users():
    if not user_stats:
        return "Нет данных о пользователях"

    recent_users = sorted(user_stats.items(),
                          key=lambda x: x[1].get('last_active', datetime.min),
                          reverse=True)[:10]

    result = "Последние 10 пользователей:\n\n"
    for user_id, stats in recent_users:
        result += f"👤 ID: {user_id}\n"
        result += f"   QR-кодов: {stats.get('qr_count', 0)}\n"
        result += f"   Активен: {stats.get('last_active').strftime('%Y-%m-%d %H:%M')}\n\n"

    return result


# Добавляем роутер админ-панели в диспетчер
dp.include_router(admin_router)


# Запуск бота
async def main():
    print("🤖 QR Designer Bot запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())