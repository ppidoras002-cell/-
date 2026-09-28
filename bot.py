from __future__ import annotations
import asyncio
import re
import os
import time
import json
import html
import hashlib
import secrets
import string
from urllib.parse import urlencode
from datetime import date
import aiohttp
from aiohttp_socks import ProxyConnector
import aiosqlite
from pathlib import Path

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    MessageEntity,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton as _TelegramInlineKeyboardButton,
    InputMediaPhoto,
    FSInputFile,
    BufferedInputFile,
)

from config import (
    BOT_TOKEN,
    SHOP_NAME,
    ADMIN_ID,
    ADMIN_IDS,
    CRYPTO_PAY_TOKEN,
    DB_NAME,
    REQUIRED_CHANNEL,
    REQUIRED_CHANNEL_URL,
    SUPPORT_USERNAME,
    RUB_OWNER_USERNAME,
)

from database import (
    init_db,
    add_user,
    get_user_by_telegram_id,
    get_referral_balance,
    get_referral_stats,
    process_referral_on_start,
    create_withdrawal_request,
    get_pending_withdrawals,
    set_withdrawal_status,
    refund_withdrawal,
    get_payout_details,
    set_payout_details,
    user_has_paid_order,
    REF_REWARD_RUB,
    REF_MIN_WITHDRAW_RUB,
    create_catalog,
    get_catalogs,
    get_catalog,
    get_catalog_parent_id,
    get_catalog_children,
    has_catalog_children,
    delete_catalog,
    create_product,
    get_products,
    get_product,
    delete_product,
    toggle_product,
    get_setting,
    set_setting,
    create_order,
    get_order_code,
    get_order,
    add_receipt,
    update_order_status,
    get_user_orders,
    get_orders,
    get_roulette_data,
    set_roulette_result,
    consume_roulette_discount,
    get_products as _db_get_products,
    get_product as _db_get_product,
    create_product as _db_create_product,
)



# ============================================================
# НАСТРАИВАЕМЫЕ ТЕКСТЫ ИНТЕРФЕЙСА
# ============================================================
_BUTTON_TEXTS: dict[str, str] = {}
_BUTTON_ICONS: dict[str, str] = {}
_BUTTON_ICON_FALLBACKS: dict[str, str] = {}
_BUTTON_REGISTRY: dict[str, str] = {}
_BUTTON_EDITOR_KEYS: dict[str, str] = {}

# Разделы, доступные в редакторе интерфейса.
# key -> (название, ключ хранения, подсказка)
UI_EDITABLE = {
    "main": ("🏠 Главное меню", "main_menu_text", "Текст приветствия и главного экрана"),
    "shop": ("🛍 Магазин", "shop", "Текст магазина"),
    "catalog": ("📁 Каталог", "catalog", "Поддерживает {catalog_name}, {catalog_count}, {product_count}"),
    "product": ("📦 Карточка товара (название, описание, ЦЕНА)", "product", "Весь текст карточки товара. Переменные: {product_name}, {catalog_name}, {description}, {price_rub}, {price_usdt}, {quantity}, {quantity_line}. Можно вставлять Premium Emoji."),
    "payment": ("💳 Способ оплаты (К ОПЛАТЕ)", "payment", "Окно выбора оплаты. Переменные: {product_name}, {rub_price}, {usdt_price}, {discount}. Premium Emoji поддерживаются."),
    "rub_owner": ("💵 Оплата рублями через владельца", "rub_owner", "Экран оплаты рублями через владельца магазина. Premium Emoji в тексте сохраняются автоматически."),
    "stars_owner": ("⭐ Оплата Stars через владельца", "stars_owner", "Экран оплаты Telegram Stars через владельца магазина. Premium Emoji в тексте сохраняются автоматически."),
    "order_rub": ("🧾 Заказ / RUB", "order_rub", "Поддерживает {order_id}, {product_name}, {original_amount}, {amount}, {discount}, {card}"),
    "sbp_order": ("🏦 Заказ / СБП", "sbp_order", "Окно оплаты СБП. Поддерживает {order_id}, {product_name}, {original_amount}, {amount}, {discount}"),
    "order_usdt": ("₮ Заказ / USDT", "order_usdt", "Поддерживает {order_id}, {product_name}, {amount}"),
    "receipt": ("📸 Отправка чека", "receipt", "Поддерживает {order_id}"),
    "orders": ("📦 Мои заказы", "orders", "Поддерживает {orders_text}"),
    "stars": ("⭐ Telegram Stars — выбор получателя", "stars", "Экран выбора: себе или другу"),
    "stars_buy_self": ("⭐ Stars — покупка себе", "stars_buy_self", "Окно покупки Stars себе. Переменные: {recipient}, {min}, {max}"),
    "stars_buy_friend": ("🎁 Stars — покупка другу", "stars_buy_friend", "Окно ввода username друга"),
    "stars_username_invalid": ("❌ Stars — неверный username", "stars_username_invalid", "Сообщение об ошибочном формате username"),
    "stars_username_not_found": ("🔎 Stars — username не найден", "stars_username_not_found", "Сообщение, если публичный username не подтверждён Telegram"),
    "stars_self_no_username": ("⚠️ Stars — нет username", "stars_self_no_username", "Сообщение, если у покупателя нет username"),
    "stars_quantity": ("⭐ Stars — ввод количества", "stars_quantity", "Экран ввода количества. Переменные: {min}, {max}, {recipient}"),
    "stars_quantity_invalid": ("❌ Stars — неверное количество", "stars_quantity_invalid", "Ошибка количества Stars. Переменные: {min}, {max}"),
    "stars_payment": ("⭐ Telegram Stars — способы оплаты", "stars_payment", "Экран выбора оплаты Stars. Переменные: {quantity}, {recipient}, {price_rub}, {price_usdt}, {discount}"),
    "stars_order_rub": ("⭐ Stars — заказ / RUB", "stars_order_rub", "Окно заказа Stars с оплатой RUB. Переменные: {order_id}, {quantity}, {original_amount}, {amount}, {discount}, {card}"),
"stars_order_sbp": ("⭐ Stars — заказ / СБП", "stars_order_sbp", "Окно заказа Stars через СБП. Переменные: {order_id}, {quantity}, {original_amount}, {amount}, {discount}"),
    "stars_order_usdt": ("⭐ Stars — заказ / USDT", "stars_order_usdt", "Окно заказа Stars через Crypto Bot. Переменные: {order_id}, {quantity}, {amount}, {discount}"),
    "roblox": ("🎮 Roblox — ввод ника", "roblox", "Экран ввода ника Roblox"),
    "roblox_order_rub": ("🎮 Roblox — заказ / RUB", "roblox_order_rub", "Окно заказа Roblox с оплатой RUB. Переменные: {order_id}, {product_name}, {nickname}, {original_amount}, {amount}, {discount}, {card}"),
    "roblox_order_sbp": ("🎮 Roblox — заказ / СБП", "roblox_order_sbp", "Окно заказа Roblox через СБП. Переменные: {order_id}, {product_name}, {nickname}, {original_amount}, {amount}, {discount}"),
    "roblox_order_usdt": ("🎮 Roblox — заказ / USDT", "roblox_order_usdt", "Окно заказа Roblox через Crypto Bot. Переменные: {order_id}, {product_name}, {nickname}, {amount}"),
    "brawl": ("🎮 Brawl Stars — ввод ID", "brawl", "Экран ввода Brawl Stars ID"),
    "brawl_pass": ("🎫 Brawl Pass — ввод Supercell ID", "brawl_pass", "Экран ввода Supercell ID для Brawl Pass"),
    "brawl_order_rub": ("🎮 Brawl Stars — заказ / RUB", "brawl_order_rub", "Окно заказа Brawl Stars с оплатой RUB. Переменные: {order_id}, {product_name}, {id_label}, {original_amount}, {amount}, {discount}, {card}"),
    "brawl_pass_order_rub": ("🎫 Brawl Pass — заказ / RUB", "brawl_pass_order_rub", "Окно заказа Brawl Pass с оплатой RUB. Переменные: {order_id}, {product_name}, {id_label}, {original_amount}, {amount}, {discount}, {card}"),
    "brawl_order_usdt": ("🎮 Brawl Stars — заказ / USDT", "brawl_order_usdt", "Окно заказа Brawl Stars через Crypto Bot. Переменные: {order_id}, {product_name}, {id_label}, {amount}"),
    "profile": ("👤 Профиль", "profile", "Поддерживает {user_id}, {username}, {first_name}, {shop_name}, {balance}"),
    "balance_topup": ("💳 Пополнение баланса — способы", "balance_topup", "Окно выбора способа пополнения баланса"),
    "topup_card": ("🇷🇺 Пополнение — карта", "topup_card", "Окно ввода суммы для пополнения картой"),
    "topup_crypto": ("💳 Пополнение — Crypto Pay", "topup_crypto", "Поддерживает {asset}. Окно ввода суммы для Crypto Pay"),
    "topup_card_payment": ("🧾 Пополнение — оплата картой", "topup_card_payment", "Поддерживает {topup_id}, {amount}, {card}"),
    "topup_crypto_payment": ("💳 Пополнение — Crypto Pay счёт", "topup_crypto_payment", "Поддерживает {topup_id}, {amount}, {crypto_amount}, {asset}, {rate}"),
    "topup_receipt_sent": ("📸 Пополнение — чек отправлен", "topup_receipt_sent", "Поддерживает {topup_id}, {amount}"),
    "balance_payment_success": ("💰 Оплата с баланса — успех", "balance_payment_success", "Поддерживает {order_id}, {product_name}, {amount}, {balance}, {details}"),
    "balance_payment_insufficient": ("💰 Оплата с баланса — недостаточно средств", "balance_payment_insufficient", "Поддерживает {amount}, {balance}, {missing}"),
    "support": ("🆘 Поддержка", "support", "Текст поддержки"),
    "faq": ("❓ FAQ", "faq", "Текст FAQ"),
    "reviews": ("⭐ Отзывы", "reviews", "Текст экрана отзывов. Кнопка канала редактируется отдельно."),
    "rules": ("📋 Правила / Соглашения", "rules", "Текст правил"),
    "roulette": ("🎁 Рулетка", "roulette", "Текст рулетки"),
    "subscription": ("📢 Подписка", "subscription", "Текст проверки подписки"),
    "referral": ("🤝 Рефералка", "referral", "Весь текст окна. Переменные: {reward}, {min_withdraw}, {balance}, {total_refs}, {premium_refs}, {payout}, {ref_link}"),
    "referral_card": ("💳 Рефералка — ввод карты", "referral_card", "Текст запроса номера карты для вывода"),
    "referral_withdraw": ("🏧 Рефералка — вывод", "referral_withdraw", "Текст перед созданием заявки на вывод"),
    "payment_success": ("✅ Успешная оплата", "payment_success", "Поддерживает {order_id}, {product_text}, {payment_method}"),
    "payment_rejected": ("❌ Отклонённая оплата", "payment_rejected", "Поддерживает {order_id}, {product_text}"),
    "brawl_pass_order_rub": ("🎫 Brawl Pass — заказ / RUB", "brawl_pass_order_rub", "Поддерживает {order_id}, {product_name}, {id_label}, {original_amount}, {amount}, {discount}, {card}"),
    "admin_main": ("🔐 Админ-панель", "admin_main", "Главный экран админ-панели"),
    "admin_texts": ("🎨 Редактор интерфейса", "admin_texts", "Описание редактора интерфейса"),
    "admin_buttons": ("🔘 Редактор кнопок", "admin_buttons", "Описание редактора кнопок"),
    "admin_catalogs": ("📁 Управление каталогами", "admin_catalogs", "Экран управления каталогами"),
    "admin_products": ("📦 Управление товарами", "admin_products", "Экран управления товарами"),
    "admin_orders": ("🧾 Управление заказами", "admin_orders", "Экран заказов администратора"),
    "admin_settings": ("⚙️ Настройки магазина", "admin_settings", "Экран настроек магазина"),
    "admin_broadcast": ("📢 Рассылка", "admin_broadcast", "Экран создания рассылки"),
    "admin_stats": ("📊 Статистика", "admin_stats", "Экран статистики"),
}


# Нормализация ключей редактора: динамические callback_data (ID товара/каталога/заказа)
# сводятся к одному шаблону, поэтому редактор показывает и реально меняет ВСЕ
# пользовательские кнопки, даже если конкретный объект ещё ни разу не открывали.
_BUTTON_LABEL_ALIASES = {
    # Одинаковые пользовательские кнопки в разных экранах должны редактироваться
    # одной записью. Это особенно важно для кнопок, у которых разные callback_data.
    "🛍 магазин": "label:shop",
    "🎁 рулетка": "label:roulette",
    "👤 профиль": "label:profile",
    "📦 мои заказы": "label:orders",
    "🆘 поддержка": "label:support",
    "⭐ отзывы": "label:reviews",
    "📢 перейти в канал с отзывами": "label:reviews_channel",
    "❓ faq": "label:faq",
    "⁉️ faq": "label:faq",
    "📋 правила / соглашения": "label:rules",
    "⭐ telegram stars": "label:stars",
    "⭐ купить stars себе": "label:stars_buy_self",
    "🎁 купить stars другу": "label:stars_buy_friend",
    "✅ проверить подписку": "label:subscription_check",
    "🎰 крутить рулетку": "label:roulette_spin",
    "⬅️ назад": "label:back",
    "назад": "label:back",
    "🏠 главное меню": "label:back",
    "⬅️ главное меню": "label:back",
    "❌ отменить": "label:back",
    "отменить": "label:back",
    "💳 купить": "label:buy",
    "₽ купить за rub": "label:buy_rub",
    "₮ купить за usdt": "label:buy_usdt",
    "₽ оплатить rub": "label:pay_rub",
    "💵 оплатить рублями": "label:pay_rub_owner",
    "оплатить рублями": "label:pay_rub_owner",
    "⭐ оплатить stars": "label:pay_stars_owner",
    "оплатить stars": "label:pay_stars_owner",
    "₮ оплатить usdt": "label:pay_usdt",
    "💳 оплатить usdt": "label:pay_usdt",
    "₮ usdt": "label:pay_usdt",
    "📸 я оплатил — отправить чек": "label:receipt",
    "🔄 проверить оплату": "label:crypto_check",
    "🔎 проверить оплату": "label:sbp_check",
    "проверить оплату": "label:sbp_check",
    "🏦 оплатить сбп": "label:pay_sbp",
    "🏦 сбп": "label:pay_sbp",
    "🏦 оплатить сбп roblox": "label:roblox_pay_sbp",
    "⭐ оплатить rub": "label:stars_pay_rub",
    "⭐ оплатить usdt": "label:stars_pay_usdt",
    "🏦 оплатить сбп stars": "label:stars_pay_sbp",
    "📢 подписаться на канал": "label:required_channel",
    "💬 написать в поддержку": "label:support_contact",
    "📁 каталог": "label:catalog",
    "📦 товар": "label:product",
    "₽ оплатить": "label:pay_rub",
    "₮ оплатить": "label:pay_usdt",
}

def _button_key(callback_data=None, url=None, text=None):
    """Return the editor key for a logical button.

    IMPORTANT: dynamic catalog/product callbacks are checked BEFORE the
    text aliases. Otherwise a real catalog named "📁 Каталог" (or a product
    named "📦 Товар") can accidentally inherit the editor's generic
    `label:catalog` / `label:product` text. More importantly, renamed generic
    buttons must NEVER rename real catalog/product objects.
    """
    cb = str(callback_data or '')
    # Админские кнопки тоже являются частью редактора интерфейса.
    # Они получают отдельный namespace, чтобы их можно было менять независимо
    # от пользовательских кнопок.
    if cb.startswith("admin_"):
        return "admin_label:" + cb

    # Real catalog/product instances are object names, not generic editor
    # buttons. Their own name is preserved; only their Premium Emoji/icon is
    # handled explicitly by the dynamic keyboard builders.
    if cb.startswith(('user_catalog:', 'user_product:', 'catalog_view:', 'product_view:')):
        return None

    dynamic = {
        'pay_rub:': 'label:pay_rub',
        'pay_rub_owner:': 'label:owner_pay_rub',
        'stars_pay_rub_owner:': 'label:owner_pay_rub',
        'pay_stars_owner:': 'label:owner_pay_stars',
        'stars_pay_stars_owner:': 'label:owner_pay_stars',
        'pay_usdt:': 'label:pay_usdt',
        'pay_balance:': 'label:pay_balance',
        'buy:': 'label:buy',
        'stars_pay_rub:': 'label:stars_pay_rub',
        'stars_pay_usdt:': 'label:stars_pay_usdt',
        'stars_pay_balance:': 'label:pay_balance',
        'receipt:': 'label:receipt',
        'crypto_check:': 'label:crypto_check',
        'sbp_check:': 'label:sbp_check',
        'roblox_pay_sbp:': 'label:roblox_pay_sbp',
        'stars_pay_sbp:': 'label:stars_pay_sbp',
    }
    for prefix, key in dynamic.items():
        if cb.startswith(prefix):
            return key

    topup_dynamic = {
        "topup_crypto:USDT": "label:topup_usdt",
        "topup_crypto:TON": "label:topup_ton",
        "topup_crypto:": "label:topup_crypto",
        "topup_card_paid:": "label:topup_paid",
        "topup_crypto_check:": "label:topup_check",
    }
    for prefix, key in topup_dynamic.items():
        if cb.startswith(prefix):
            return key

    # Admin workflow callbacks are also editable. Dynamic IDs are kept
    # inside the key so the editor can address the exact logical button.
    admin_workflow_prefixes = (
        "payment_toggle:", "payment_toggle_all:", "settings_",
        "broadcast_", "catalog_add", "catalog_back_root", "catalog_delete_menu",
    )
    if cb.startswith(admin_workflow_prefixes):
        return "admin_label:" + cb

    # Additional payment/navigation callbacks used by older screens.
    extra_map = {
        "pay_yoomoney:button": "label:pay_sbp",
        "sbp_check:button": "label:sbp_check",
        "payments_disabled": "label:payments_disabled",
        "topup_pay:button": "label:topup_pay",
    }
    if cb in extra_map:
        return extra_map[cb]

    # Static/logical buttons may be recognised by their callback first.
    callback_map = {
        'payment_rub_owner:button': 'label:payment_rub_owner',
        'payment_stars_owner:button': 'label:payment_stars_owner',
        'shop': 'label:shop', 'roulette': 'label:roulette',
        'stars_buy_self': 'label:stars_buy_self', 'stars_buy_friend': 'label:stars_buy_friend',
        'profile': 'label:profile', 'orders': 'label:orders',
        'support': 'label:support', 'faq': 'label:faq',
        'reviews': 'label:reviews',
        'rules_menu': 'label:rules', 'stars_start': 'label:stars',
        'roblox_start': 'label:roblox', 'brawl_start': 'label:brawl',
        'subscription_check': 'label:subscription_check',
        'roulette_spin': 'label:roulette_spin',
        'back_main': 'label:back', 'back': 'label:back',
        'change_quantity': 'label:change_quantity',
        'referral_menu': 'label:referral',
        'referral_set_card': 'label:referral_set_card',
        'referral_withdraw': 'label:referral_withdraw',
        'referral': 'label:referral',
        'balance_topup': 'label:balance_topup',
        'topup_card': 'label:topup_card',
    }
    if cb in callback_map:
        return callback_map[cb]

    # Only if there is no meaningful callback do we use the visible text as
    # a legacy alias. This keeps the generic editor entries editable while
    # preventing them from hijacking dynamic object names.
    t = str(text or '').strip().lower()
    alias = _BUTTON_LABEL_ALIASES.get(t)
    if alias:
        return alias

    if url:
        if url == globals().get('REQUIRED_CHANNEL_URL'):
            return 'label:required_channel'
        u = str(url).lower()
        if "sentyrep" in u or u.rstrip("/").endswith("/sentyrep"):
            return "label:reviews_channel"
        if u.startswith("https://t.me/"):
            return "label:support_contact"
        return "url:" + str(url)
    return None


# Полный каталог пользовательских кнопок. Он заполняется при старте, а не только
# при открытии экранов, поэтому список редактора не зависит от того, какие
# разделы пользователь уже посещал.
_USER_BUTTON_DEFINITIONS = [
    ("label:shop", "🛍 Магазин"),
    ("label:roulette", "🎁 Рулетка"),
    ("label:profile", "👤 Профиль"),
    ("label:referral", "🤝 Рефералка"),
    ("label:referral_set_card", "💳 Добавить реквизиты"),
    ("label:referral_withdraw", "🏧 Вывести"),
    ("label:referral_open", "🤝 Открыть рефералку"),
    ("label:orders", "📦 Мои заказы"),
    ("label:support", "🆘 Поддержка"),
    ("label:faq", "❓ FAQ"),
    ("label:reviews", "⭐ Отзывы"),
    ("label:reviews_channel", "📢 Перейти в канал с отзывами"),
    ("label:rules", "📋 Правила / Соглашения"),
    ("label:stars", "⭐ Telegram Stars"),
    ("label:stars_buy_self", "⭐ Купить Stars себе"),
    ("label:stars_buy_friend", "🎁 Купить Stars другу"),
    ("label:roblox", "🎮 Roblox"),
    ("label:brawl", "🎮 Brawl Stars"),
    ("label:subscription_check", "✅ Проверить подписку"),
    ("label:roulette_spin", "🎰 Крутить рулетку"),
    ("label:back", "⬅️ Назад"), ("label:change_quantity", "⬅️ Изменить количество"),
    ("label:buy", "💳 Купить"),
    ("label:buy_rub", "₽ Купить за RUB"),
    ("label:buy_usdt", "₮ Купить за USDT"),
    ("label:pay_rub", "₽ Оплатить RUB"),
    ("label:payment_rub_owner", "💵 Оплата рублями"),
    ("label:payment_stars_owner", "⭐ Оплата Stars"),
    ("label:owner_pay_rub", "💵 Оплатить рублями"),
    ("label:owner_pay_stars", "⭐ Оплатить Stars"),
    ("label:pay_sbp", "🏦 Оплатить СБП"),
    ("label:roblox_pay_sbp", "🏦 Оплатить СБП для Roblox"),
    ("label:pay_usdt", "₮ Оплатить USDT"),
    ("label:pay_balance", "💰 Оплатить с баланса"),
    ("label:balance_topup", "💳 Пополнить баланс"),
    ("label:topup_card", "🇷🇺 Рубли на карту"),
    ("label:topup_usdt", "💵 USDT • Crypto Pay"),
    ("label:topup_ton", "💎 TON • Crypto Pay"),
    ("label:topup_paid", "📸 Я оплатил"),
    ("label:topup_check", "🔄 Проверить оплату"),
    ("label:topup_pay", "💳 Оплатить"),
    ("label:receipt", "📸 Я оплатил — отправить чек"),
    ("label:crypto_check", "🔄 Проверить оплату"),
    ("label:sbp_check", "🔎 Проверить оплату"),
    ("label:required_channel", "📢 Подписаться на канал"),
    ("label:support_contact", "💬 Написать в поддержку"),
    ("label:catalog", "📁 Каталог"),
    ("label:product", "📦 Товар"),
    ("label:stars_pay_rub", "₽ Оплатить RUB"),
    ("label:stars_pay_usdt", "₮ Оплатить USDT"),
    ("label:stars_pay_sbp", "🏦 Оплатить СБП для Stars"),
    ("label:pay_yoomoney", "🏦 Оплатить через ЮMoney"),
    ("label:payments_disabled", "❌ Оплата временно недоступна"),
    ("label:change_quantity", "⬅️ Изменить количество"),
    ("label:pay_sbp", "🏦 Оплатить СБП"),
    ("label:sbp_check", "🔎 Проверить оплату"),
    ("admin_label:broadcast_confirm", "🟢 Отправить всем"),
    ("admin_label:broadcast_cancel", "❌ Отмена"),
    ("admin_label:catalog_add", "➕ Создать каталог"),
    ("admin_label:catalog_back_root", "⬅️ Назад"),
    ("admin_label:catalog_delete_menu", "🗑 Удалить каталог"),
    ("admin_label:payment_toggle:rub", "₽ RUB / Карта"),
    ("admin_label:payment_toggle:rub_owner", "💵 RUB через владельца"),
    ("admin_label:payment_toggle:stars_owner", "⭐ Stars через владельца"),
    ("admin_label:payment_toggle:sbp", "🏦 СБП"),
    ("admin_label:payment_toggle:usdt", "₮ USDT"),
    ("admin_label:payment_toggle_all:off", "🔴 Отключить все оплаты"),
    ("admin_label:payment_toggle_all:on", "🟢 Включить все оплаты"),
    ("admin_label:settings_rub", "💳 Изменить RUB"),
    ("admin_label:settings_yoomoney", "🏦 Настроить СБП"),
    ("admin_label:settings_usdt", "₮ USDT"),
    # Все кнопки админ-панели — также редактируемые.
    ("admin_label:admin_catalogs", "📁 Каталоги"),
    ("admin_label:admin_products", "📦 Товары"),
    ("admin_label:admin_orders", "🧾 Заказы"),
    ("admin_label:admin_broadcast", "📢 Рассылка"),
    ("admin_label:admin_stats", "📊 Статистика"),
    ("admin_label:admin_settings", "⚙️ Настройки"),
    ("admin_label:admin_texts", "🎨 Редактор интерфейса"),
    ("admin_label:admin_back", "⬅️ Назад"),
    ("admin_label:admin_text_button_list", "🔘 Редактор кнопок"),
    ("admin_label:admin_ui_main", "🏠 Главное меню"),
    ("admin_label:admin_ui_shop", "🛍 Магазин"),
    ("admin_label:admin_ui_catalog", "📁 Каталог"),
    ("admin_label:admin_ui_product", "📦 Карточка товара"),
    ("admin_label:admin_ui_payment", "💳 Способ оплаты"),
    ("admin_label:admin_ui_rub_owner", "💵 Оплата рублями через владельца"),
    ("admin_label:admin_ui_order_rub", "🧾 Заказ / RUB"),
    ("admin_label:admin_ui_stars_order_rub", "⭐ Stars — заказ / RUB"),
    ("admin_label:admin_ui_sbp_order", "🏦 Заказ / СБП"),
    ("admin_label:admin_ui_stars_order_sbp", "⭐ Stars — заказ / СБП"),
    ("admin_label:admin_ui_order_usdt", "₮ Заказ / USDT"),
    ("admin_label:admin_ui_receipt", "📸 Отправка чека"),
    ("admin_label:admin_ui_orders", "📦 Мои заказы"),
    ("admin_label:admin_ui_stars", "⭐ Telegram Stars — выбор получателя"),
    ("admin_label:admin_ui_stars_buy_self", "⭐ Stars — покупка себе"),
    ("admin_label:admin_ui_stars_buy_friend", "🎁 Stars — покупка другу"),
    ("admin_label:admin_ui_stars_payment", "⭐ Stars — способы оплаты"),
    ("admin_label:admin_ui_stars_quantity", "⭐ Stars — ввод количества"),
    ("admin_label:admin_ui_roblox", "🎮 Roblox — ввод ника"),
    ("admin_label:admin_ui_brawl", "🎮 Brawl Stars — ввод ID"),
    ("admin_label:admin_ui_brawl_pass", "🎫 Brawl Pass — ввод Supercell ID"),
    ("admin_label:admin_ui_profile", "👤 Профиль"),
    ("admin_label:admin_ui_referral", "🤝 Рефералка"),
    ("admin_label:admin_ui_referral_card", "💳 Рефералка — карта"),
    ("admin_label:admin_ui_referral_withdraw", "🏧 Рефералка — вывод"),
    ("admin_label:admin_ui_support", "🆘 Поддержка"),
    ("admin_label:admin_ui_faq", "❓ FAQ"),
    ("admin_label:admin_ui_rules", "📋 Правила / Соглашения"),
    ("admin_label:admin_ui_roulette", "🎁 Рулетка"),
    ("admin_label:admin_ui_subscription", "📢 Подписка"),
    ("admin_label:admin_ui_preview", "👁 Предпросмотр"),
    ("admin_label:admin_ui_reset", "🧹 Сбросить текст"),
]

def _seed_user_button_registry():
    for key, label in _USER_BUTTON_DEFINITIONS:
        _BUTTON_REGISTRY.setdefault(key, label)


def _button_label(default_text: str, callback_data=None, url=None) -> str:
    key = _button_key(callback_data, url, default_text)
    if key:
        # Не регистрируем служебные/админские кнопки.
        if key.startswith("callback:admin_") or key.startswith("callback:catalog_") or key.startswith("callback:product_"):
            return default_text
        _BUTTON_REGISTRY.setdefault(key, default_text)
        saved = _BUTTON_TEXTS.get(key)
        if not saved:
            # Подхватываем старые сохранения из предыдущих версий редактора.
            legacy_keys = []
            for cb, legacy in (
                ("shop", "callback:shop"), ("roulette", "callback:roulette"),
                ("profile", "callback:profile"), ("orders", "callback:orders"),
                ("support", "callback:support"), ("faq", "callback:faq"),
                ("rules_menu", "callback:rules_menu"), ("stars_start", "callback:stars_start"),
                ("subscription_check", "callback:subscription_check"),
                ("roulette_spin", "callback:roulette_spin"),
                ("back_main", "callback:back_main"),
                ("buy", "callback:buy:{id}"),
                ("pay_rub", "callback:pay_rub:{id}"),
                ("pay_sbp", "callback:pay_sbp:{id}"),
                ("pay_usdt", "callback:pay_usdt:{id}"),
                ("receipt", "callback:receipt:{id}"),
                ("crypto_check", "callback:crypto_check:{id}:{id}"),
            ):
                if key == f"label:{cb}":
                    legacy_keys.append(legacy)
            for legacy in legacy_keys:
                if _BUTTON_TEXTS.get(legacy):
                    saved = _BUTTON_TEXTS[legacy]
                    break
        return saved if saved else default_text
    return default_text


def _auto_button_style(text: str | None, callback_data: str | None, url: str | None) -> str | None:
    """Цвет кнопки по смыслу (Bot API style).

    Единые правила интерфейса:
      success  = зелёный  — действие: купить, оплатить, подтвердить, проверить оплату
      primary  = синий    — навигация и информация
      danger   = красный  — назад, отмена, удалить, отклонить
      None     = прозрачная (карточки товаров в витрине)
    """
    t = (text or "").casefold()
    cb = (callback_data or "").casefold()
    raw = text or ""

    # Каталоги в витрине — синяя навигация.
    catalog_prefixes = (
        "user_catalog:", "catalog_view:", "product_catalog:",
        "catalog:", "open_catalog:",
    )
    if any(cb.startswith(p) for p in catalog_prefixes):
        return "primary"

    # Товары в витрине — без цветной подсветки.
    transparent_prefixes = (
        "user_product:", "product_view:", "open_product:",
    )
    if any(cb.startswith(p) for p in transparent_prefixes):
        return None

    # --- Красный: назад / отмена / удаление ---
    red_text = (
        "назад", "отмен", "удал", "отклон", "бан", "выкл", "сброс",
        "закрыть", "нет", "отписка",
    )
    red_cb = (
        "back", "cancel", "delete", "reject", "ban", "remove", "reset",
        "clear", "wd_no", "admin_reject", "payments_disabled",
    )
    if any(x in t for x in red_text) or any(x in cb for x in red_cb):
        return "danger"
    if "⬅️" in raw or "❌" in raw or "🗑" in raw:
        return "danger"

    # --- Зелёный: действие (купить / оплатить / подтвердить) ---
    green_text = (
        "купить", "оплат", "подтверд", "выплач", "я оплатил",
        "проверить оплату", "проверить подписку", "крутить",
        "добавить", "включить", "сохранить", "выдать", "создать",
        "пополнить",
    )
    green_cb = (
        "shop", "buy", "pay_", "pay_balance", "pay_rub", "pay_usdt",
        "pay_yoomoney", "pay_sbp", "pay_rub_owner", "pay_stars_owner",
        "stars_pay_", "topup", "confirm", "wd_ok", "check_pay",
        "crypto_check", "sbp_check", "yoomoney_check", "admin_confirm",
        "roulette_spin", "deliver", "subscription_check", "receipt",
    )
    if any(x in t for x in green_text) or any(cb.startswith(x) or x in cb for x in green_cb):
        return "success"
    if "✅" in raw or "💳" in raw or "🟢" in raw:
        return "success"
    # URL «Оплатить» в CryptoBot / платёжных ссылках
    if url and any(x in t for x in ("оплат", "pay", "invoice")):
        return "success"

    # --- Синий: навигация / информация ---
    blue_text = (
        "профиль", "реферал", "заказ", "поддерж", "faq", "правил", "рулетк",
        "каталог", "товар", "настрой", "статистик", "рассылк", "админ",
        "stars", "premium", "вывод", "отзыв", "магазин",
    )
    blue_cb = (
        "profile", "referral", "orders", "support", "faq", "rules", "roulette",
        "catalog", "product", "admin", "stars", "withdraw", "reviews",
        "balance_topup", "referral_menu", "referral_open",
    )
    if any(x in t for x in blue_text) or any(x in cb for x in blue_cb):
        return "primary"
    if url:
        return "primary"
    return "primary"


def InlineKeyboardButton(*args, **kwargs):
    # Единая точка переопределения текста, стиля и Premium Emoji-иконки
    # всех inline-кнопок бота. Telegram не поддерживает MessageEntity
    # внутри текста кнопки, но с Bot API 9.4 поддерживает
    # icon_custom_emoji_id — Premium Emoji слева от текста.
    #
    # Стили (принудительно по смыслу, даже если передали другой style):
    #   success = зелёный — купить / оплатить / подтвердить
    #   primary = синий   — навигация / информация
    #   danger  = красный — назад / отмена
    callback_data = kwargs.get("callback_data")
    url = kwargs.get("url")
    button_text = kwargs.get("text") if "text" in kwargs else (args[0] if args else None)
    key = _button_key(callback_data, url, button_text)

    cb_str = str(callback_data or "")
    if any(cb_str.startswith(p) for p in (
        "user_catalog:", "catalog_view:", "product_catalog:",
        "catalog:", "open_catalog:",
    )):
        # Каталоги всегда синие (навигация).
        kwargs["style"] = "primary"
    elif any(cb_str.startswith(p) for p in (
        "user_product:", "product_view:", "open_product:",
    )):
        # Товары в витрине — без цветной подсветки.
        kwargs.pop("style", None)
    else:
        # Всегда применяем семантический стиль: зелёный / синий / красный.
        # Жёстко заданный style в вызове больше не перебивает правила.
        auto = _auto_button_style(button_text, callback_data, url)
        if auto:
            kwargs["style"] = auto
        else:
            kwargs.pop("style", None)

    if "text" in kwargs:
        kwargs["text"] = _button_label(kwargs["text"], callback_data, url)
    elif args:
        args = list(args)
        if args:
            args[0] = _button_label(args[0], callback_data, url)
            args = tuple(args)

    # Recompute from the final button text so icon and label always use the same
    # semantic key.
    key = _button_key(callback_data, url, kwargs.get("text") if "text" in kwargs else (args[0] if args else None))
    # Подставляем сохранённый Premium Emoji (даже если передали icon_custom_emoji_id=None)
    if key and not kwargs.get("icon_custom_emoji_id"):
        kwargs.pop("icon_custom_emoji_id", None)
        icon_id = _BUTTON_ICONS.get(key)
        if not icon_id:
            # Backward compatibility with old callback-based editor keys.
            legacy_key = None
            cb = str(callback_data or "")
            if cb.startswith("crypto_check:"): legacy_key = "callback:crypto_check:{id}:{id}"
            elif cb.startswith("sbp_check:"): legacy_key = "callback:sbp_check:{id}"
            elif cb.startswith("stars_pay_sbp:"): legacy_key = "callback:stars_pay_sbp:{id}"
            elif cb.startswith(("pay_rub:", "pay_usdt:", "receipt:", "user_catalog:", "user_product:", "stars_pay_rub:", "stars_pay_usdt:", "stars_pay_sbp:")):
                legacy_key = "callback:" + cb.split(":",1)[0] + ":{id}"
            elif cb: legacy_key = "callback:" + cb
            if legacy_key:
                icon_id = _BUTTON_ICONS.get(legacy_key)
        if icon_id:
            # Bot API expects the custom emoji identifier as a string.
            # Do not put the emoji itself into button text: Telegram renders
            # the Premium Emoji before the label from this field.
            kwargs["icon_custom_emoji_id"] = str(icon_id)

    return _TelegramInlineKeyboardButton(*args, **kwargs)


async def _load_button_texts():
    _seed_user_button_registry()
    global _BUTTON_TEXTS, _BUTTON_ICONS, _BUTTON_ICON_FALLBACKS
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'button_text:%' OR key LIKE 'button_icon:%' OR key LIKE 'button_icon_fallback:%'"
        )
        rows = await cursor.fetchall()
    _BUTTON_TEXTS = {}
    _BUTTON_ICONS = {}
    _BUTTON_ICON_FALLBACKS = {}
    for key, value in rows:
        if key.startswith("button_text:"):
            _BUTTON_TEXTS[key[len("button_text:"):]] = value
        elif key.startswith("button_icon:"):
            _BUTTON_ICONS[key[len("button_icon:"):]] = value
        elif key.startswith("button_icon_fallback:"):
            _BUTTON_ICON_FALLBACKS[key[len("button_icon_fallback:"):]] = value

    # Migrate legacy callback-based editor entries to the canonical semantic
    # keys. This is what makes old Premium Emoji settings apply everywhere
    # instead of only to the first callback instance.
    legacy_to_canonical = {
        "callback:shop": "label:shop", "callback:roulette": "label:roulette",
        "callback:profile": "label:profile", "callback:orders": "label:orders",
        "callback:support": "label:support", "callback:faq": "label:faq",
        "callback:rules_menu": "label:rules", "callback:stars_start": "label:stars",
        "callback:subscription_check": "label:subscription_check",
        "callback:roulette_spin": "label:roulette_spin",
        "callback:back_main": "label:back", "callback:buy:{id}": "label:buy",
        "callback:pay_rub:{id}": "label:pay_rub",
        "callback:pay_rub_owner:{id}": "label:owner_pay_rub",
        "callback:pay_stars_owner:{id}": "label:owner_pay_stars",
        "callback:stars_pay_stars_owner:{id}": "label:owner_pay_stars",
        "callback:stars_pay_rub_owner:{id}": "label:owner_pay_rub",
        "callback:pay_sbp:{id}": "label:pay_sbp",
        "callback:pay_usdt:{id}": "label:pay_usdt",
        "callback:receipt:{id}": "label:receipt",
        "callback:crypto_check:{id}:{id}": "label:crypto_check",
        "callback:sbp_check:{id}": "label:sbp_check",
        "callback:stars_pay_sbp:{id}": "label:stars_pay_sbp",
        "callback:stars_pay_rub:{id}": "label:stars_pay_rub",
        "callback:stars_pay_usdt:{id}": "label:stars_pay_usdt",
    }
    for legacy, canonical in legacy_to_canonical.items():
        if canonical not in _BUTTON_TEXTS and legacy in _BUTTON_TEXTS:
            _BUTTON_TEXTS[canonical] = _BUTTON_TEXTS[legacy]
        if canonical not in _BUTTON_ICONS and legacy in _BUTTON_ICONS:
            _BUTTON_ICONS[canonical] = _BUTTON_ICONS[legacy]
        if canonical not in _BUTTON_ICON_FALLBACKS and legacy in _BUTTON_ICON_FALLBACKS:
            _BUTTON_ICON_FALLBACKS[canonical] = _BUTTON_ICON_FALLBACKS[legacy]




# ---------------------------------------------------------------------------
# User navigation cleanup
# Keep exactly one back/navigation button per user keyboard.  If a screen
# accidentally contains several buttons that only navigate backwards (for
# example "Изменить количество" + "Главное меню"), keep a single red
# "Назад" button. Admin keyboards are left untouched.
# ---------------------------------------------------------------------------
_OriginalInlineKeyboardMarkup = InlineKeyboardMarkup

def _is_admin_keyboard_button(button) -> bool:
    cb = getattr(button, "callback_data", None)
    return bool(cb and str(cb).startswith("admin_"))

def _is_back_button(button) -> bool:
    cb = str(getattr(button, "callback_data", "") or "")
    text = str(getattr(button, "text", "") or "").strip().lower()
    if cb == "back_main":
        return True
    if text in {
        "назад", "⬅️ назад", "главное меню", "🏠 главное меню",
        "отменить", "❌ отменить", "изменить количество",
        "⬅️ изменить количество",
    }:
        return True
    if text.endswith("назад") or text.endswith("отменить"):
        return True
    return False

def _clean_user_keyboard(rows):
    # Never touch admin-only keyboards.
    flat = [b for row in rows for b in row]
    if not flat or any(_is_admin_keyboard_button(b) for b in flat):
        return rows

    back_positions = []
    for ri, row in enumerate(rows):
        for bi, button in enumerate(row):
            if _is_back_button(button):
                back_positions.append((ri, bi, button))

    if len(back_positions) <= 1:
        # Even a single back button should use Telegram's red danger style.
        result = [list(row) for row in rows]
        if back_positions:
            ri, bi, button = back_positions[0]
            try:
                result[ri][bi] = button.model_copy(update={"text": _button_label("⬅️ Назад", callback_data=getattr(button, "callback_data", None)), "style": "danger"})
            except Exception:
                pass
        return result

    # Prefer an already-labelled "Назад" button; otherwise keep the last
    # navigation button (normally the bottom button) and turn it into Back.
    chosen = None
    for item in back_positions:
        t = str(getattr(item[2], "text", "") or "").strip().lower()
        if t in {"назад", "⬅️ назад"}:
            chosen = item
            break
    if chosen is None:
        chosen = back_positions[-1]

    keep_ri, keep_bi, keep_button = chosen
    result = []
    for ri, row in enumerate(rows):
        new_row = []
        for bi, button in enumerate(row):
            if _is_back_button(button) and not (ri == keep_ri and bi == keep_bi):
                continue
            if ri == keep_ri and bi == keep_bi:
                try:
                    button = button.model_copy(update={"text": _button_label("⬅️ Назад", callback_data=getattr(button, "callback_data", None)), "style": "danger"})
                except Exception:
                    pass
            new_row.append(button)
        if new_row:
            result.append(new_row)
    return result

def InlineKeyboardMarkup(*args, **kwargs):
    rows = kwargs.get("inline_keyboard")
    if rows is None and args:
        rows = args[0]
    if rows is not None:
        cleaned = _clean_user_keyboard(rows)
        if "inline_keyboard" in kwargs:
            kwargs["inline_keyboard"] = cleaned
        elif args:
            args = (cleaned,) + args[1:]
    return _OriginalInlineKeyboardMarkup(*args, **kwargs)

def _set_button_text_local(key: str, value: str):
    _BUTTON_TEXTS[key] = value
    _BUTTON_REGISTRY[key] = value


def _set_button_icon_local(key: str, value: str | None, fallback: str | None = None):
    if value:
        _BUTTON_ICONS[key] = str(value)
    else:
        _BUTTON_ICONS.pop(key, None)
    if fallback:
        _BUTTON_ICON_FALLBACKS[key] = fallback
    elif not value:
        _BUTTON_ICON_FALLBACKS.pop(key, None)


def _main_menu_defaults():
    return {
        "shop": "🛍 Магазин",
        "roulette": "🎁 Рулетка",
        "profile": "👤 Профиль",
        "referral": "🤝 Рефералка",
        "orders": "📦 Мои заказы",
        "support": "🆘 Поддержка",
        "faq": "⁉️ FAQ",
        "rules_menu": "📋 Правила / Соглашения",
        "reviews": "⭐ Отзывы",
    }


async def _get_main_menu_text():
    text = await get_setting("main_menu_text")
    if text:
        entities = await get_setting("main_menu_text_entities")
        return text, entities
    return (
        f"👋 Добро пожаловать в <b>{SHOP_NAME}</b>!\n\n"
        "🛍 Здесь вы можете приобрести аккаунты: <b><u>FunPay</u> и <u>Playerok</u></b>\n"
        "⭐ <b><u>Telegram Stars</u>, <u>Telegram Premium</u></b>\n"
        "🤖 <b><u>Подписки на различные ИИ</u></b>\n\n"
        "💥 И все это <b><u>быстро и выгодно!</u></b>\n\n"
        "<b>Выберите нужный раздел:</b>",
        None,
    )


async def _get_main_menu_message_payload():
    text, entities_json = await _get_main_menu_text()
    # Всегда рендерим сохранённые entities в HTML. Так одновременно работают
    # Premium Emoji, жирный/подчёркнутый текст и введённые админом <b>/<u> теги.
    if entities_json:
        return _render_custom_emoji_html(text, entities_json), [], False
    return text, [], False


async def _get_ui_text(key: str, default: str) -> tuple[str, str | None]:
    """Возвращает сохранённый текст интерфейса и entities Premium Emoji."""
    text = await get_setting(f"ui_text:{key}")
    entities = await get_setting(f"ui_entities:{key}")
    return (text if text is not None else default), entities


def _ui_text_default(key: str) -> str:
    return {
        "profile": "👤 <b>Ваш профиль</b>\n\n🆔 ID: <code>{user_id}</code>\n👤 Username: {username}\n📛 Имя: {first_name}\n💰 Баланс: <b>{balance:.2f} ₽</b>\n\n<b>Спасибо, что выбираете {shop_name}💜</b>",
        "balance_topup": "💳 <b>Пополнение баланса</b>\n\nВыберите способ пополнения:\n\n🇷🇺 <b>Рубли на карту</b> — ручная проверка по чеку.\n💵 <b>USDT</b> — автоматически через Crypto Pay.\n💎 <b>TON</b> — автоматически через Crypto Pay.",
        "topup_card": "🇷🇺 <b>Пополнение рублями</b>\n\nВведите сумму пополнения в рублях.\nНапример: <code>1000</code>",
        "topup_crypto": "💳 <b>Пополнение через Crypto Pay ({asset})</b>\n\nВведите сумму, на которую хотите пополнить баланс, в рублях.\nНапример: <code>1000</code> ₽\n\nCrypto Pay автоматически покажет к оплате эквивалент в {asset}.",
        "topup_card_payment": "🇷🇺 <b>Пополнение #{topup_id}</b>\n\n💰 К пополнению: <b>{amount} ₽</b>\n\n💳 Карта для оплаты:\n<code>{card}</code>\n\nПосле перевода нажмите кнопку ниже и отправьте фотографию чека.",
        "topup_crypto_payment": "💳 <b>Пополнение #{topup_id}</b>\n\n💰 Баланс пополнится на: <b>{amount} ₽</b>\n💵 <b>К оплате: {crypto_amount} {asset}</b>\n📈 Курс: 1 {asset} ≈ {rate} ₽\n\nСумма рассчитывается по курсу Crypto Pay. Перед оплатой проверьте сумму в счёте Crypto Bot.\n\nНажмите «Оплатить», затем после оплаты — «Проверить оплату».",
        "topup_receipt_sent": "✅ <b>Чек отправлен на проверку</b>\n\n🧾 Пополнение: <b>#{topup_id}</b>\n💰 Сумма: <b>{amount} ₽</b>\n\nПосле подтверждения администратора баланс будет пополнен.",
        "balance_payment_success": "✅ <b>Заказ оплачен с баланса!</b>\n\n🧾 Заказ: <b>#{order_id}</b>\n📦 <b>{product_name}</b>\n{details}\n💰 Списано: <b>{amount} ₽</b>\n💳 Новый баланс: <b>{balance} ₽</b>\n\nОжидайте выдачи товара.",
        "balance_payment_insufficient": "❌ <b>Недостаточно средств</b>\n\n💰 К оплате: <b>{amount} ₽</b>\n💳 На балансе: <b>{balance} ₽</b>\n📉 Не хватает: <b>{missing} ₽</b>\n\nПополните баланс и попробуйте снова.",
        "support": "🆘 <b>ПОДДЕРЖКА</b>\n\nНажмите кнопку ниже, чтобы перейти в чат с поддержкой.",
        "faq": "❓ <b>ЧАСТЫЕ ВОПРОСЫ</b>\n\n❔ <b>Как купить товар?</b>\n\nОткройте раздел «Товары», выберите нужную категорию и позицию, затем нажмите «Купить».\n\n📊 <b>Как оплатить товар?</b>\n\nВыберите нужный товар и способ оплаты, после оплаты отправьте чек.\n\n⭐️ <b>Когда придёт товар?</b>\n\nТовар приходит сразу после оплаты.\n\n⚙️ <b>Возможен ли возврат?</b>\n\nВозврат возможен только в случае, если товар оказался нерабочим на момент покупки.",
        "reviews": "⭐ <b>Отзывы</b>\n\nЗдесь собраны отзывы наших клиентов.\nНажмите кнопку ниже, чтобы перейти в канал с отзывами.",
        "rules": "🛡 <b>ПРАВИЛА МАГАЗИНА</b>\n\n💲 Оплата производится до выдачи товара.\n\n🌍 Товар выдаётся автоматически.\n\n📅 Возврат возможен только если товар оказался нерабочим на момент покупки. Для рассмотрения возврата обязательно нужна видеозапись покупки и проверки товара.\n\n⚙️ Перед покупкой внимательно ознакомьтесь с описанием товара и условиями выдачи.\n\n👁 Попытки обмана, подделка чеков и злоупотребления приводят к блокировке без возврата средств.\n\n📄 <b>Соглашение</b>\n\nПокупая товар в магазине, вы соглашаетесь с правилами сервиса.",
        "roulette": "🎁 <b>РУЛЕТКА</b>\n\n🎰 Испытайте удачу и получите скидку или рубли на баланс!\n\n🎁 Возможные награды: <b>5%</b>, <b>10%</b>, <b>15%</b> скидка или <b>1 ₽, 3 ₽, 5 ₽, 10 ₽, 20 ₽, 50 ₽</b> на баланс.\n\n💰 Денежная награда зачисляется автоматически.\n\nНажмите кнопку ниже, чтобы начать.",
        "subscription": "📢 <b>Для использования бота необходимо подписаться на наш канал.</b>\n\nПосле подписки нажмите «Проверить подписку».",
        "referral": "🎁 <b>Реферальная программа</b>\n\nЗа каждого друга с <b>Telegram Premium</b>: <b>+{reward} ₽</b>\n⚠️ Без Premium начисление не идёт.\n💰 Баланс можно только вывести (не для покупок).\n🏧 Минимальный вывод: <b>{min_withdraw} ₽</b>\n🛒 Для вывода нужен хотя бы <b>1 успешный заказ</b>.\n\n💰 Ваш баланс: <b>{balance} ₽</b>\n👥 Приглашено: <b>{total_refs}</b>\n⭐ С Premium: <b>{premium_refs}</b>\n\n💳 Реквизиты: {payout}\n\n🔗 Ваша ссылка:\n<code>{ref_link}</code>",
        "referral_card": "💳 <b>Реквизиты для вывода</b>\n\nОтправьте <b>номер карты</b> одним сообщением.\nПример: <code>2200700123456789</code>\n\nИли /cancel для отмены.",
        "referral_withdraw": "🏧 <b>Вывод реферального баланса</b>\n\nЗаявка будет создана на сохранённые реквизиты.",
        "shop": "🛍 <b>Магазин {shop_name}</b>\n\nВыберите нужный раздел:",
        "catalog": "<b>{catalog_name}</b>\n\nВыберите подкаталог или товар:",
        "product": "<b>{product_name}</b>\n\n{description}\n\n━━━━━━━━━━━━━━\n<b>ЦЕНА:</b>\n💰 <b>{price_rub} ₽</b>\n💎 <b>{price_usdt} USDT</b>{quantity_line}",
        "payment": "💳 <b>ВЫБЕРИТЕ СПОСОБ ОПЛАТЫ</b>\n\n📦 <b>{product_name}</b>\n\n━━━━━━━━━━━━━━\n💰 <b>К ОПЛАТЕ:</b>\n💵 <b>{rub_price} ₽</b>\n💎 <b>{usdt_price} USDT</b>{discount}\n━━━━━━━━━━━━━━\n\n👇 <b>Выберите удобный способ оплаты:</b>",
        "rub_owner": "💵 <b>Оплата рублями</b>\n\nОплата рублями производится <b>только через владельца магазина</b>.\n\nНажмите кнопку ниже, чтобы перейти в чат с <b>поддержкой</b> и начать сделку.",
        "stars_owner": "⭐ <b>Оплата Stars</b>\n\nОплата Stars производится <b>только через владельца магазина</b>.\n\nНажмите кнопку ниже, чтобы перейти в чат с <b>поддержкой</b> и начать сделку.",
        "order_rub": "🧾 <b>Заказ #{order_id}</b>\n\n📦 <b>{product_name}</b>\n💰 Сумма заказа: <b>{original_amount} ₽</b>{discount}\n💳 <b>ТОЧНАЯ СУММА К ОПЛАТЕ:</b> <code>{amount} ₽</code>\n\n⚠️ <b>ВАЖНО!</b> ПЕРЕВОДИТЕ ТОЛЬКО ТОЧНУЮ СУММУ, УКАЗАННУЮ ВЫШЕ.\n\n💳 <b>Оплата RUB</b>\n💳 Карта:\n<code>{card}</code>\n\n📸 После оплаты отправьте фотографию чека.",
        "sbp_order": "🏦 <b>Оплата через СБП</b>\n\n🧾 Заказ: <b>#{order_id}</b>\n📦 <b>{product_name}</b>\n\n💰 К оплате: <b>{amount} ₽</b>{discount}\n\nНажмите кнопку ниже, чтобы перейти на страницу перевода.\n\n⚠️ <b>Переведите точную сумму:</b> <code>{amount} ₽</code>\n\nПосле оплаты нажмите кнопку проверки оплаты.",
        "order_usdt": "🧾 <b>Заказ #{order_id}</b>\n\n📦 <b>{product_name}</b>\n💰 К оплате: <b>{amount} USDT</b>\n\n₮ <b>Оплата через Crypto Bot</b>\n\nНажмите кнопку ниже и оплатите счёт.",
        "receipt": "📸 <b>Заказ #{order_id}</b>\n\nОтправьте фотографию чека одним сообщением.",
        "payment_success": "✅ <b>Оплата получена!</b>\n\n🧾 Заказ: <b>#{order_id}</b>\n{product_text}\n💳 Оплата: <b>{payment_method}</b>\n\nОжидайте выдачи товара.",
        "payment_rejected": "❌ <b>Оплата отклонена</b>\n\n🧾 Заказ: <b>#{order_id}</b>\n{product_text}\n\nПожалуйста, проверьте оплату и обратитесь в поддержку.",
        "orders": "📦 <b>Мои заказы</b>\n\n{orders_text}",
        "stars": "⭐ <b>Telegram Stars</b>\n\nВыберите, кому отправить Stars:",
        "stars_buy_self": "⭐ <b>Покупка Stars себе</b>\n\n👤 Stars будут отправлены на ваш аккаунт: <b>{recipient}</b>\n\nВведите количество Stars от <b>{min}</b> до <b>{max}</b>:",
        "stars_buy_friend": "🎁 <b>Покупка Stars другу</b>\n\nВведите username Telegram получателя.\nНапример: <code>@username</code>",
        "stars_username_invalid": "❌ <b>Некорректный username</b>.\n\nВведите username Telegram длиной от 5 до 32 символов, например <code>@username</code>.",
        "stars_username_not_found": "🔎 <b>Username не подтверждён</b>.\n\nНе удалось подтвердить существование публичного профиля <b>{recipient}</b>. Проверьте username и попробуйте снова.",
        "stars_self_no_username": "❌ <b>У вас не установлен username Telegram.</b>\n\nУстановите username в настройках Telegram и попробуйте снова.",
        "stars_quantity": "⭐ <b>Количество Stars</b>\n\n👤 Получатель: <b>{recipient}</b>\n\nВведите количество Stars от <b>{min}</b> до <b>{max}</b>:",
        "stars_quantity_invalid": "❌ <b>Некорректное количество Stars.</b>\n\nВведите число от <b>{min}</b> до <b>{max}</b>.",
        "stars_payment": "⭐ <b>Telegram Stars</b>\n\n👤 Получатель: <b>{recipient}</b>\n⭐ Количество: <b>{quantity}</b> Stars\n\n💳 RUB: <b>{price_rub} ₽</b>\n₮ USDT: <b>{price_usdt} USDT</b>{discount}\n\n👇 <b>Выберите способ оплаты:</b>",
        "stars_order_rub": "🧾 <b>Заказ #{order_id}</b>\n\n⭐ <b>Telegram Stars</b>\n👤 Получатель: <b>{recipient}</b>\n⭐ Количество: <b>{quantity}</b>\n💰 Сумма заказа: <b>{original_amount} ₽</b>{discount}\n💳 <b>ТОЧНАЯ СУММА К ОПЛАТЕ:</b> <code>{amount} ₽</code>\n\n⚠️ <b>ВАЖНО!</b> ПЕРЕВОДИТЕ ТОЛЬКО ТОЧНУЮ СУММУ, УКАЗАННУЮ ВЫШЕ. ПЕРЕВОДИТЕ СУММУ КОПЕЙКА В КОПЕЙКУ, ИНАЧЕ ЗАКАЗ НЕ БУДЕТ ЗАСЧИТАН.\n\n💳 <b>Оплата RUB</b>\n💳 Карта:\n<code>{card}</code>\n\n📸 После оплаты отправьте фотографию чека.",
        "stars_order_sbp": "🧾 <b>Заказ #{order_id}</b>\n\n⭐ <b>Telegram Stars</b>\n👤 Получатель: <b>{recipient}</b>\n⭐ Количество: <b>{quantity}</b>\n💰 Сумма заказа: <b>{original_amount} ₽</b>{discount}\n🏦 <b>К оплате через СБП: {amount} ₽</b>\n\nНажмите кнопку ниже, чтобы перейти на страницу перевода.\n⚠️ <b>Переведите точную сумму: {amount} ₽</b>\n\nПосле оплаты нажмите кнопку проверки оплаты.",
        "stars_order_usdt": "🧾 <b>Заказ #{order_id}</b>\n\n⭐ <b>Telegram Stars</b>\n👤 Получатель: <b>{recipient}</b>\n⭐ Количество: <b>{quantity}</b>\n💰 К оплате: <b>{amount} USDT</b>{discount}\n\n₮ <b>Оплата через Crypto Bot</b>\n\nНажмите кнопку ниже и оплатите счёт.",
        "roblox": "🎮 <b>Roblox</b>\n\nВведите ваш <b>ник Roblox</b>, на который нужно выдать Robux.\n\nПример: <code>Builderman</code>",
        "roblox_order_rub": "🧾 <b>Заказ #{order_id}</b>\n\n📦 <b>{product_name}</b>\n👤 Ник Roblox: <code>{nickname}</code>\n\n💰 Сумма заказа: <b>{original_amount} ₽</b>{discount}\n💳 <b>ТОЧНАЯ СУММА К ОПЛАТЕ:</b> <code>{amount} ₽</code>\n\n⚠️ <b>ВАЖНО!</b> ПЕРЕВОДИТЕ ТОЛЬКО ТОЧНУЮ СУММУ, УКАЗАННУЮ ВЫШЕ. ПЕРЕВОДИТЕ СУММУ КОПЕЙКА В КОПЕЙКУ, ИНАЧЕ ЗАКАЗ НЕ БУДЕТ ЗАСЧИТАН.\n\n💳 <b>Оплата RUB</b>\n💳 Карта:\n<code>{card}</code>\n\n📸 После оплаты отправьте фотографию чека.",
        "roblox_order_sbp": "🧾 <b>Заказ #{order_id}</b>\n\n📦 <b>{product_name}</b>\n👤 Ник Roblox: <code>{nickname}</code>\n\n💰 Сумма заказа: <b>{original_amount} ₽</b>{discount}\n🏦 <b>ТОЧНАЯ СУММА К ОПЛАТЕ:</b> <code>{amount} ₽</code>\n\nНажмите кнопку ниже, чтобы перейти на страницу перевода.\n\n⚠️ <b>Переведите точную сумму:</b> <code>{amount} ₽</code>\n\nПосле оплаты нажмите кнопку проверки оплаты.",
        "roblox_order_usdt": "🧾 <b>Заказ #{order_id}</b>\n\n📦 <b>{product_name}</b>\n👤 Ник Roblox: <code>{nickname}</code>\n\n💰 К оплате: <b>{amount} USDT</b>\n\n₮ <b>Оплата через Crypto Bot</b>\n\nНажмите кнопку ниже и оплатите счёт.",
        "brawl": "🎮 <b>Brawl Stars</b>\n\nВведите ваш Brawl Stars ID:",
        "brawl_pass": "🎫 <b>Brawl Pass</b>\n\nВведите ваш <b>Supercell ID</b>.\n\nПример: <code>BraveBarbarian</code>",
        "brawl_order_rub": "🧾 <b>Заказ #{order_id}</b>\n\n📦 <b>{product_name}</b>\n{id_label}\n\n💰 Сумма заказа: <b>{original_amount} ₽</b>{discount}\n💳 <b>ТОЧНАЯ СУММА К ОПЛАТЕ:</b> <code>{amount} ₽</code>\n\n⚠️ <b>ВАЖНО!</b> ПЕРЕВОДИТЕ ТОЛЬКО ТОЧНУЮ СУММУ, УКАЗАННУЮ ВЫШЕ. ПЕРЕВОДИТЕ СУММУ КОПЕЙКА В КОПЕЙКУ, ИНАЧЕ ЗАКАЗ НЕ БУДЕТ ЗАСЧИТАН.\n\n💳 <b>Оплата RUB</b>\n💳 Карта:\n<code>{card}</code>\n\n📸 После оплаты отправьте фотографию чека.",
        "brawl_order_usdt": "🧾 <b>Заказ #{order_id}</b>\n\n{id_label}\n\n💰 К оплате: <b>{amount} USDT</b>\n\n₮ <b>Оплата через Crypto Bot</b>\n\nНажмите кнопку ниже и оплатите счёт.",
        "brawl_pass_order_rub": "🧾 <b>Заказ #{order_id}</b>\n\n🎫 <b>{product_name}</b>\n{id_label}\n\n💰 Сумма заказа: <b>{original_amount} ₽</b>{discount}\n💳 <b>ТОЧНАЯ СУММА К ОПЛАТЕ:</b> <code>{amount} ₽</code>\n\n💳 <b>Оплата RUB</b>\n💳 Карта:\n<code>{card}</code>\n\n📸 После оплаты отправьте фотографию чека.",
        "payment_success": "✅ <b>Оплата получена!</b>\n\n🧾 Заказ: <b>#{order_id}</b>\n{product_text}\n💳 Оплата: <b>{payment_method}</b>\n\nОжидайте выдачи товара.",
        "payment_rejected": "❌ <b>Оплата отклонена</b>\n\n🧾 Заказ: <b>#{order_id}</b>\n{product_text}\n\nПожалуйста, проверьте оплату и обратитесь в поддержку.",
        "admin_main": "🔐 <b>Админ-панель</b>\n\nУправление магазином, товарами, заказами, оплатами и интерфейсом.",
        "admin_texts": "🎨 <b>РЕДАКТОР ИНТЕРФЕЙСА</b>\n\nЗдесь можно редактировать пользовательские окна, HTML-форматирование и Premium Emoji.\n\n💎 Premium Emoji сохраняются из Telegram entities.",
        "admin_buttons": "🔘 <b>РЕДАКТОР КНОПОК</b>\n\nВыберите кнопку для редактирования. Можно менять название и Premium Emoji.",
        "admin_catalogs": "📁 <b>Управление каталогами</b>\n\nВыберите каталог или создайте новый:",
        "admin_products": "📦 <b>Товары</b>\n\nВыберите каталог:",
        "admin_orders": "{orders_text}",
        "admin_settings": "⚙️ <b>Настройки магазина</b>\n\n💳 <b>СПОСОБЫ ОПЛАТЫ</b>",
        "admin_broadcast": "📢 <b>Создание рассылки</b>\n\nОтправьте сообщение, которое хотите отправить пользователям.",
        "admin_stats": "{stats_text}",
    }.get(key, "")



async def get_ui_photo(key: str) -> str | None:
    """file_id фото для экрана интерфейса (ui_photo:<key>)."""
    value = await get_setting(f"ui_photo:{key}")
    value = (value or "").strip()
    return value or None


async def set_ui_photo(key: str, file_id: str | None):
    await set_setting(f"ui_photo:{key}", (file_id or "").strip())


async def clear_ui_photo(key: str):
    await set_setting(f"ui_photo:{key}", "")


async def _get_admin_ui_text(key: str, default: str, values: dict | None = None) -> str:
    """Return an editable admin-panel text with HTML + Premium Emoji entities."""
    text, entities = await _get_ui_text(key, default)
    rendered = _render_custom_emoji_html(text, entities) if entities else text
    if values:
        try:
            rendered = rendered.format(**values)
        except Exception:
            pass
    return rendered


def _format_ui_text(text: str, user=None) -> str:
    if user is None:
        return text.replace("{shop_name}", html.escape(SHOP_NAME))
    username = f"@{user.username}" if user.username else "не указан"
    values = {
        "shop_name": html.escape(SHOP_NAME),
        "user_id": str(user.id),
        "username": html.escape(username),
        "first_name": html.escape(user.first_name or ""),
    }
    try:
        return text.format(**values)
    except Exception:
        return text


async def _save_ui_text_from_message(key: str, message: Message):
    text = message.text or message.caption or ""
    entities = _custom_emoji_entities(message)
    await set_setting(f"ui_text:{key}", text)
    await set_setting(f"ui_entities:{key}", entities or "")


async def _get_rendered_ui_text(key: str, default: str, user=None) -> str:
    text, entities = await _get_ui_text(key, default)
    # Сначала восстанавливаем Premium Emoji по исходным UTF-16 offsets,
    # затем безопасно подставляем переменные шаблона уже в готовый HTML.
    rendered = _render_custom_emoji_html(text, entities) if entities else text
    if user is None:
        values = {"shop_name": html.escape(SHOP_NAME), "user_id": "", "username": "", "first_name": ""}
    else:
        values = {
            "shop_name": html.escape(SHOP_NAME),
            "user_id": str(user.id),
            "username": html.escape(f"@{user.username}" if user.username else "не указан"),
            "first_name": html.escape(user.first_name or ""),
        }
    for name, value in values.items():
        rendered = rendered.replace("{" + name + "}", value)
    return rendered


async def _get_rendered_template(key: str, default: str, values: dict) -> str:
    # {order_id} historically meant the internal numeric DB id. For display
    # templates, transparently replace it with the public random order code.
    values = dict(values)
    if "order_id" in values:
        try:
            values["order_id"] = await get_order_code(int(values["order_id"]))
        except (TypeError, ValueError):
            pass
    if "topup_id" in values:
        try:
            values["topup_id"] = await get_topup_code(int(values["topup_id"]))
        except (TypeError, ValueError):
            pass
    text, entities = await _get_ui_text(key, default)
    rendered = _render_custom_emoji_html(text, entities) if entities else text

    # These values may already contain Telegram HTML generated from saved
    # MessageEntity data (including Premium Emoji). Escaping them here turns
    # <tg-emoji>...</tg-emoji> and <b>...</b> into visible text — exactly the
    # bug that caused Premium Emoji markup to appear in product cards.
    safe_html_keys = {
        "product_name",
        "catalog_name",
        "description",
        "description_html",
        "product_text",
        "discount",
        "card",
        "details",
    }
    for name, value in values.items():
        replacement = (
            str(value)
            if name.endswith("_html") or name in safe_html_keys
            else html.escape(str(value))
        )
        rendered = rendered.replace("{" + name + "}", replacement)
    return rendered


def main_menu() -> InlineKeyboardMarkup:
    d = _main_menu_defaults()
    # Главное меню — единый стиль:
    #   зелёный = главное действие (Магазин)
    #   синий   = навигация (профиль, заказы, рефералка, FAQ…)
    #   красный = только назад/отмена (здесь нет)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_button_label(d["shop"], "shop"), style="success", callback_data="shop")],
            [InlineKeyboardButton(text=_button_label(d["referral"], "referral"), style="primary", callback_data="referral_menu")],
            [
                InlineKeyboardButton(text=_button_label(d["profile"], "profile"), style="primary", callback_data="profile"),
                InlineKeyboardButton(text=_button_label(d["orders"], "orders"), style="primary", callback_data="orders"),
            ],
            [
                InlineKeyboardButton(text=_button_label(d["roulette"], "roulette"), style="primary", callback_data="roulette"),
                InlineKeyboardButton(text=_button_label(d.get("reviews", "⭐ Отзывы"), "reviews"), style="primary", callback_data="reviews"),
            ],
            [
                InlineKeyboardButton(text=_button_label(d["faq"], "faq"), style="primary", callback_data="faq"),
                InlineKeyboardButton(text=_button_label(d["rules_menu"], "rules_menu"), style="primary", callback_data="rules_menu"),
            ],
            [InlineKeyboardButton(text=_button_label(d["support"], "support"), style="primary", callback_data="support")],
        ]
    )

async def ensure_product_quantity_db():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("PRAGMA table_info(products)")
        columns = await cursor.fetchall()
        names = {row[1] for row in columns}
        if "quantity" not in names:
            await db.execute(
                "ALTER TABLE products ADD COLUMN quantity INTEGER DEFAULT 0"
            )
        await db.commit()


async def answer_text_or_photo(
    message: Message,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    ui_key: str | None = None,
    photo: str | None = None,
):
    """Отправить окно как текст или как фото с подписью, используя фото из редактора UI."""
    photo_id = photo if photo is not None else (await get_ui_photo(ui_key) if ui_key else None)
    if photo_id:
        try:
            await message.answer_photo(photo=photo_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
            return
        except Exception as e:
            print(f"[DISPLAY] answer_text_or_photo photo failed: {e}")
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def create_product(
    catalog_id: int,
    name: str,
    description: str,
    image_file_id: str | None,
    price_rub: float,
    price_usdt: float,
    quantity: int = 0,
):
    product_id = await _db_create_product(
        catalog_id=catalog_id,
        name=name,
        description=description,
        image_file_id=image_file_id,
        price_rub=price_rub,
        price_usdt=price_usdt,
    )
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE products SET quantity = ? WHERE id = ?",
            (int(quantity), product_id),
        )
        await db.commit()
    return product_id


async def get_product(product_id: int):
    cursor_product = await _db_get_product(product_id)
    if not cursor_product:
        return cursor_product
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT quantity FROM products WHERE id = ?",
            (product_id,),
        )
        row = await cursor.fetchone()
    return tuple(cursor_product) + (int(row[0]) if row and row[0] is not None else 0,)


async def get_products(catalog_id: int | None = None):
    rows = await _db_get_products(catalog_id)
    if not rows:
        return rows
    ids = [row[0] for row in rows]
    placeholders = ",".join("?" for _ in ids)
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            f"SELECT id, quantity FROM products WHERE id IN ({placeholders})",
            ids,
        )
        quantities = {row[0]: int(row[1] or 0) for row in await cursor.fetchall()}
    return [tuple(row) + (quantities.get(row[0], 0),) for row in rows]


dp = Dispatcher()

REQUIRED_CHANNEL = REQUIRED_CHANNEL or os.getenv("REQUIRED_CHANNEL", "") or ""
REQUIRED_CHANNEL_URL = REQUIRED_CHANNEL_URL or os.getenv("REQUIRED_CHANNEL_URL", "") or ""

# Если в config.py указан только публичный URL канала, автоматически
# используем его username для get_chat_member().
if not REQUIRED_CHANNEL and REQUIRED_CHANNEL_URL:
    _channel_match = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)", str(REQUIRED_CHANNEL_URL))
    if _channel_match:
        REQUIRED_CHANNEL = "@" + _channel_match.group(1)


def subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Подписаться на канал",
                    style="primary",
                    url=REQUIRED_CHANNEL_URL,
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    style="success",
                    callback_data="subscription_check",
                )
            ],
        ]
    )


async def is_subscribed(bot: Bot, user_id: int, force: bool = False) -> bool:
    # Если канал не задан в .env — подписка не требуется
    if not REQUIRED_CHANNEL:
        return True
    now = time.monotonic()
    cached = _SUBSCRIPTION_CACHE.get(user_id)
    if not force and cached and now - cached[0] < _SUBSCRIPTION_CACHE_TTL:
        return cached[1]
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if member.status in {"creator", "administrator", "member"}:
            result = True
        elif member.status == "restricted":
            result = bool(getattr(member, "is_member", False))
        else:
            result = False
        _SUBSCRIPTION_CACHE[user_id] = (now, result)
        return result
    except Exception as e:
        print(f"[SUBSCRIPTION] check error for {user_id}: {e}")
        # В режиме обязательной подписки нельзя пропускать пользователя
        # при ошибке проверки: иначе обязательная подписка фактически обходится.
        return False


def get_cached_asset_id(cache_key: str) -> str | None:
    return _ASSET_FILE_ID_CACHE.get(cache_key)


def cache_asset_id(cache_key: str, file_id: str | None):
    if file_id:
        _ASSET_FILE_ID_CACHE[cache_key] = file_id


async def show_subscription_required(target):
    default = _ui_text_default("subscription") or (
        "🔒 <b>Доступ к магазину закрыт</b>\n\n"
        "Чтобы пользоваться ботом, сначала подпишитесь на наш канал.\n\n"
        "1️⃣ Нажмите <b>«📢 Подписаться на канал»</b>\n"
        "2️⃣ Подпишитесь на канал\n"
        "3️⃣ Нажмите <b>«✅ Проверить подписку»</b>"
    )
    text = await _get_rendered_ui_text("subscription", default)
    keyboard = subscription_keyboard()
    if isinstance(target, CallbackQuery):
        try:
            await show_text_or_photo(target, text, keyboard, ui_key="subscription")
        except Exception:
            await target.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=keyboard, parse_mode="HTML")


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        user_id = user.id
        # Администратор должен иметь доступ к админ-панели независимо от подписки.
        if is_admin(user_id):
            return await handler(event, data)
        # /start и кнопка проверки должны быть доступны без подписки.
        if isinstance(event, Message):
            if event.text and event.text.startswith("/start"):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            callback_data = event.data or ""
            # Кнопки возврата должны работать всегда. Они не открывают
            # защищённый раздел и не должны блокироваться проверкой подписки.
            if (
                callback_data == "subscription_check"
                or callback_data == "back_main"
                or callback_data == "admin_back"
                or callback_data.endswith("_back")
                or callback_data.startswith("catalog_back")
            ):
                return await handler(event, data)

        bot = data.get("bot")
        if bot is not None and await is_subscribed(bot, user_id):
            return await handler(event, data)

        await show_subscription_required(event)
        if isinstance(event, CallbackQuery):
            await event.answer("Сначала подпишитесь на канал", show_alert=True)
        return None


dp.message.outer_middleware(SubscriptionMiddleware())
dp.callback_query.outer_middleware(SubscriptionMiddleware())

SUPPORT_USERNAME = SUPPORT_USERNAME

STARS_MIN = 50
STARS_MAX = 10000

STARS_RUB_PER_100 = 125.0
STARS_USDT_PER_100 = 1.5

# Изображение каталога Telegram Stars. Файл входит в архив бота.
STARS_CATALOG_IMAGE = Path(__file__).resolve().parent / "assets" / "telegram_stars.jpg"

CRYPTO_PAY_API = "https://pay.crypt.bot/api"

# Прокси для запросов к внешним API
PROXY_URL = os.getenv("PROXY_URL", "").strip()



# ============================================================
# TELEGRAM CUSTOM / PREMIUM EMOJI
# ============================================================

def _extract_premium_emoji_id(message: Message) -> str | None:
    """Первый Premium Emoji (custom_emoji_id) из сообщения."""
    entities = list(message.entities or []) + list(message.caption_entities or [])
    for ent in entities:
        etype = getattr(ent, "type", None)
        etype_s = str(getattr(etype, "value", etype) or "").lower()
        cid = getattr(ent, "custom_emoji_id", None)
        if not cid:
            continue
        if "custom_emoji" in etype_s:
            return str(cid)
        # Иногда type приходит иначе, но id есть
        if cid and (etype_s.endswith("emoji") or "emoji" in etype_s):
            return str(cid)
    # Любой entity с custom_emoji_id
    for ent in entities:
        cid = getattr(ent, "custom_emoji_id", None)
        if cid:
            return str(cid)
    raw = _custom_emoji_entities(message)
    if raw:
        try:
            for e in json.loads(raw):
                if e.get("custom_emoji_id"):
                    t = str(e.get("type", "")).lower()
                    if (not t) or ("custom_emoji" in t) or ("emoji" in t):
                        return str(e["custom_emoji_id"])
        except Exception as exc:
            print(f"[BTN EMOJI] parse entities json: {exc}")
    return None


def _button_label_from_message(message: Message) -> str:
    """Текст кнопки без символов Premium Emoji (иконка идёт отдельно)."""
    raw = message.text or message.caption or ""
    entities = list(message.entities or []) + list(message.caption_entities or [])
    cuts = []
    for ent in entities:
        etype = getattr(ent, "type", None)
        etype_s = str(getattr(etype, "value", etype) or "").lower()
        cid = getattr(ent, "custom_emoji_id", None)
        if cid or "custom_emoji" in etype_s:
            start = int(getattr(ent, "offset", 0)) * 2
            length = int(getattr(ent, "length", 0)) * 2
            if length > 0:
                cuts.append((start, start + length))
    if not cuts:
        return raw.strip()
    utf16 = raw.encode("utf-16-le")
    cuts.sort()
    parts = []
    pos = 0
    for a, b in cuts:
        a = max(0, min(a, len(utf16)))
        b = max(0, min(b, len(utf16)))
        if pos < a:
            parts.append(utf16[pos:a])
        pos = max(pos, b)
    if pos < len(utf16):
        parts.append(utf16[pos:])
    try:
        cleaned = b"".join(parts).decode("utf-16-le")
    except Exception:
        cleaned = raw
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned


def _custom_emoji_entities(message: Message) -> str | None:
    """Сохраняет ВСЕ MessageEntity: жирный, подчёркнутый, ссылки,
    Premium Emoji и остальные поддерживаемые Telegram-сущности.
    Telegram offsets хранятся в UTF-16 code units.
    """
    entities = message.entities or message.caption_entities or []
    if not entities:
        return None
    items = []
    for entity in entities:
        etype = getattr(entity, "type", "")
        # aiogram 3: type может быть Enum (MessageEntityType.CUSTOM_EMOJI)
        if hasattr(etype, "value"):
            etype = etype.value
        item = {
            "type": str(etype),
            "offset": int(getattr(entity, "offset", 0)),
            "length": int(getattr(entity, "length", 0)),
        }
        for attr in ("url", "language", "custom_emoji_id", "user"):
            value = getattr(entity, attr, None)
            if value is not None:
                # user для text_mention не сериализуем целиком: это не нужно
                # для редактора интерфейса и может ломать JSON.
                if attr == "user":
                    continue
                item[attr] = str(value)
        items.append(item)
    return json.dumps(items, ensure_ascii=False) if items else None


def _telegram_entities_from_json(entities_json: str | None):
    """Восстанавливает MessageEntity из сохранённого JSON."""
    if not entities_json:
        return []
    try:
        raw = json.loads(entities_json)
    except Exception:
        return []
    result = []
    for item in raw or []:
        try:
            kwargs = {
                "type": item.get("type"),
                "offset": int(item.get("offset", 0)),
                "length": int(item.get("length", 0)),
            }
            for attr in ("url", "language", "custom_emoji_id"):
                if item.get(attr) is not None:
                    kwargs[attr] = item[attr]
            result.append(MessageEntity(**kwargs))
        except Exception:
            continue
    return result


def _utf16_boundaries(text: str):
    boundaries = [0]
    pos = 0
    for ch in text:
        pos += 2 if ord(ch) > 0xFFFF else 1
        boundaries.append(pos)
    return boundaries


def _u16_to_py(boundaries, offset: int) -> int:
    try:
        return boundaries.index(offset)
    except ValueError:
        for i, value in enumerate(boundaries):
            if value >= offset:
                return i
        return len(boundaries) - 1


def _render_custom_emoji_html(text: str | None, entities_json: str | None) -> str:
    """Восстанавливает сохранённые Telegram MessageEntity в валидный HTML.

    Ключевой момент: сущности с одинаковым концом должны закрываться в
    обратном порядке открытия. Иначе Telegram получает, например, </b>
    внутри <u> и отвечает ``Unmatched end tag``. Premium Emoji не открывает
    HTML-тег в стеке: он целиком заменяется на один <tg-emoji>...</tg-emoji>.
    """
    if not text:
        return ""
    try:
        raw = json.loads(entities_json or "[]")
    except Exception:
        raw = []

    boundaries = _utf16_boundaries(text)
    supported = []
    for order, e in enumerate(raw or []):
        typ = e.get("type")
        if typ not in {
            "bold", "italic", "underline", "strikethrough", "spoiler",
            "code", "pre", "text_link", "custom_emoji", "blockquote",
            "expandable_blockquote",
        }:
            continue
        try:
            a = _u16_to_py(boundaries, int(e.get("offset", 0)))
            b = _u16_to_py(boundaries, int(e.get("offset", 0)) + int(e.get("length", 0)))
        except Exception:
            continue
        if b > a:
            supported.append((a, b, e, order))

    tag_open = {
        "bold": "<b>", "italic": "<i>", "underline": "<u>",
        "strikethrough": "<s>", "spoiler": "<tg-spoiler>",
        "code": "<code>", "pre": "<pre>",
        "blockquote": "<blockquote>",
        "expandable_blockquote": "<blockquote expandable>",
    }
    tag_close = {
        "bold": "</b>", "italic": "</i>", "underline": "</u>",
        "strikethrough": "</s>", "spoiler": "</tg-spoiler>",
        "code": "</code>", "pre": "</pre>",
        "blockquote": "</blockquote>",
        "expandable_blockquote": "</blockquote>",
    }

    # Manual HTML typed by the administrator is allowed, but every other
    # literal '<' / '>' is escaped.
    allowed_tag = re.compile(
        r'</?(?:b|strong|i|em|u|ins|s|strike|del|tg-spoiler|code|pre|blockquote)'
        r'(?:\s+expandable)?\s*>', re.I
    )
    def safe_segment(seg: str) -> str:
        parts = re.split(r'(<\/?(?:b|strong|i|em|u|ins|s|strike|del|tg-spoiler|code|pre|blockquote)(?:\s+expandable)?\s*>)', seg, flags=re.I)
        return ''.join(part if allowed_tag.fullmatch(part or '') else html.escape(part) for part in parts)

    positions = {0, len(text)}
    for a, b, _, _ in supported:
        positions.add(a); positions.add(b)
    positions = sorted(positions)
    result = []
    active = []

    for idx, pos in enumerate(positions[:-1]):
        # Close only non-custom entities. For equal end positions, close in
        # reverse opening order; this guarantees properly nested HTML.
        closing = [x for x in active if x[1] == pos]
        for item in sorted(closing, key=lambda x: x[3], reverse=True):
            typ = item[2].get("type")
            if typ in tag_close:
                result.append(tag_close[typ])
            active.remove(item)

        opening = [x for x in supported if x[0] == pos]
        # Outer entities first. If ranges are equal, preserve Telegram's
        # original entity order so the reverse close above is deterministic.
        opening.sort(key=lambda x: (-(x[1] - x[0]), x[3]))
        custom_here = False
        for item in opening:
            a, b, e, order = item
            typ = e.get("type")
            if typ == "custom_emoji":
                emoji_id = html.escape(str(e.get("custom_emoji_id", "")), quote=True)
                fallback = text[a:b]
                if emoji_id and len(fallback) > 0:
                    result.append(f'<tg-emoji emoji-id="{emoji_id}">{html.escape(fallback)}</tg-emoji>')
                    custom_here = True
                continue
            if typ == "text_link":
                url = html.escape(str(e.get("url", "")), quote=True)
                result.append(f'<a href="{url}">')
            elif typ in tag_open:
                result.append(tag_open[typ])
            active.append(item)

        next_pos = positions[idx + 1]
        if not custom_here:
            result.append(safe_segment(text[pos:next_pos]))

    # Safety close in stack order if an unusual entity combination slipped in.
    for item in sorted(active, key=lambda x: x[3], reverse=True):
        typ = item[2].get("type")
        if typ == "text_link":
            result.append("</a>")
        elif typ in tag_close:
            result.append(tag_close[typ])
    return ''.join(result)


async def _save_custom_emoji_entities(table: str, entity_column: str, row_id: int, entities_json: str | None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            f"UPDATE {table} SET {entity_column} = ? WHERE id = ?",
            (entities_json, row_id),
        )
        await db.commit()


async def _get_text_entities(table: str, entity_column: str, row_id: int) -> str | None:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            f"SELECT {entity_column} FROM {table} WHERE id = ?",
            (row_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None



def _remove_custom_emoji_entities(text: str, entities_json: str | None):
    """Удаляет Premium Emoji из текста и пересчитывает остальные UTF-16 offsets."""
    try:
        raw = json.loads(entities_json or "[]")
    except Exception:
        raw = []
    boundaries = _utf16_boundaries(text)
    ranges=[]
    for e in raw:
        if e.get("type") == "custom_emoji":
            a=_u16_to_py(boundaries,int(e.get("offset",0))); b=_u16_to_py(boundaries,int(e.get("offset",0))+int(e.get("length",0)))
            if b>a: ranges.append((a,b))
    if not ranges:
        return text, raw
    ranges.sort(reverse=True)
    out=text
    for a,b in ranges: out=out[:a]+out[b:]
    new=[]
    for e in raw:
        if e.get("type")=="custom_emoji": continue
        old_off=int(e.get("offset",0)); shift=0
        for a,b in sorted(ranges):
            if b <= _u16_to_py(boundaries, old_off): shift += b-a
        e=dict(e); e["offset"]=max(0,old_off-shift); new.append(e)
    return out, new

# ============================================================
# FSM
# ============================================================

class CatalogState(StatesGroup):
    waiting_name = State()
    waiting_image = State()
    waiting_edit_name = State()
    waiting_edit_name_emoji = State()
    waiting_edit_image = State()


class ProductState(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    waiting_image = State()
    waiting_quantity = State()
    waiting_price_rub = State()
    waiting_price_usdt = State()
    waiting_edit_name = State()
    waiting_edit_name_emoji = State()
    waiting_edit_description = State()
    waiting_edit_image = State()
    waiting_edit_price_rub = State()
    waiting_edit_price_usdt = State()
    waiting_edit_quantity = State()


class PaymentSettingsState(StatesGroup):
    waiting_rub_card = State()
    waiting_sbp_link = State()
    waiting_yoomoney_wallet = State()
    waiting_usdt_network = State()
    waiting_usdt_wallet = State()


class ReceiptState(StatesGroup):
    waiting_receipt = State()


class BroadcastState(StatesGroup):
    waiting_message = State()


class StarsState(StatesGroup):
    waiting_friend_username = State()
    waiting_quantity = State()
    waiting_payment = State()


class BrawlState(StatesGroup):
    waiting_id = State()


class RobloxState(StatesGroup):
    waiting_nickname = State()


class InterfaceTextState(StatesGroup):
    waiting_main_menu_text = State()
    waiting_button_text = State()
    waiting_button_emoji = State()
    waiting_ui_text = State()
    waiting_ui_photo = State()


class WithdrawState(StatesGroup):
    waiting_details = State()
    waiting_card = State()

class TopupState(StatesGroup):
    waiting_amount = State()
    waiting_card_receipt = State()



# ============================================================
# ОБЩИЕ ФУНКЦИИ
# ============================================================



async def is_brawl_product(product):
    if not product:
        return False
    name = str(product[2]).casefold()
    catalog = str(product[8]).casefold() if len(product) > 8 else ""
    return (
        "brawl" in name
        or "гем" in name
        or "pass" in name
        or "brawl" in catalog
        or "brawl pass" in catalog
    )


def is_brawl_pass_product(product) -> bool:
    """Товары из каталога Brawl Pass или с pass в названии — просим Supercell ID."""
    if not product:
        return False
    name = str(product[2]).casefold()
    catalog = str(product[8]).casefold() if len(product) > 8 else ""
    if "brawl pass" in catalog or catalog.strip() == "brawl pass":
        return True
    if "brawlpass" in catalog.replace(" ", ""):
        return True
    if "brawl pass" in name or "brawlpass" in name.replace(" ", ""):
        return True
    # Любой товар внутри каталога, где в названии каталога есть pass + brawl
    if "brawl" in catalog and "pass" in catalog:
        return True
    return False


def is_valid_brawl_id(brawl_id: str) -> bool:
    return re.fullmatch(r"#[A-Z0-9]{8,12}", brawl_id.strip().upper()) is not None


def is_valid_player_id(player_id: str) -> bool:
    # Новый Supercell Player ID: это не старый тег с #.
    # Разрешаем буквы, цифры и подчёркивания; длина 3–30 символов.
    return re.fullmatch(r"[A-Za-z0-9_]{3,30}", player_id.strip()) is not None

def is_valid_roblox_nickname(nickname: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_]{3,20}", nickname.strip()) is not None



def _message_image_file_id(message: Message) -> str | None:
    """file_id фото: обычное photo или картинка как document."""
    if message.photo:
        return message.photo[-1].file_id
    doc = message.document
    if doc and getattr(doc, "mime_type", None):
        mime = str(doc.mime_type).lower()
        if mime.startswith("image/"):
            return doc.file_id
    return None


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def calculate_stars_rub(quantity: int) -> float:
    return round(
        quantity * STARS_RUB_PER_100 / 100,
        2,
    )


def calculate_stars_usdt(quantity: int) -> float:
    return round(
        quantity * STARS_USDT_PER_100 / 100,
        4,
    )


async def init_start_stats_db():
    """Создаёт таблицу для подсчёта всех нажатий /start."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS start_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_start_logs_started_at
            ON start_logs(started_at)
            """
        )
        await db.commit()


async def record_start(telegram_id: int):
    """Записывает каждое нажатие /start."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO start_logs (telegram_id) VALUES (?)",
            (telegram_id,),
        )
        await db.commit()


async def get_bot_stats():
    """Возвращает общую и дневную статистику."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users"
        )
        total_users = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM start_logs"
        )
        total_starts = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT telegram_id)
            FROM start_logs
            WHERE date(started_at, 'localtime') =
                  date('now', 'localtime')
            """
        )
        today_users = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM start_logs
            WHERE date(started_at, 'localtime') =
                  date('now', 'localtime')
            """
        )
        today_starts = (await cursor.fetchone())[0]

    return total_users, total_starts, today_users, today_starts


async def get_or_create_user(
    telegram_id: int,
    username,
    first_name,
):
    user = await get_user_by_telegram_id(telegram_id)

    if not user:
        await add_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )

        user = await get_user_by_telegram_id(telegram_id)

    return user


# ============================================================
# НАСТРОЙКА ФОТО ДЛЯ /START
# ============================================================
# Вставь сюда Telegram file_id фотографии.
# Если оставить пустым, /start будет работать как раньше
# и отправлять только текст с кнопками.
START_PHOTO_FILE_ID = ""
# Главное меню использует отдельную картинку главного меню.
START_PHOTO_PATH = Path(__file__).resolve().parent / "assets" / "main_menu.jpg"
if not START_PHOTO_PATH.exists():
    _png_fallback = Path(__file__).resolve().parent / "assets" / "main_menu.png"
    if _png_fallback.exists():
        START_PHOTO_PATH = _png_fallback

# Кэш Telegram file_id: после первой загрузки тяжёлые картинки больше не
# загружаются с компьютера при каждом нажатии кнопки. Это заметно ускоряет меню.
_ASSET_FILE_ID_CACHE: dict[str, str] = {}
_ASSET_FILE_ID_LOCK = asyncio.Lock()
_SUBSCRIPTION_CACHE: dict[int, tuple[float, bool]] = {}
_SUBSCRIPTION_CACHE_TTL = 60.0



async def show_main_menu(message: Message):
    """Send the editable main menu without falling back to the old hard-coded text.

    A malformed/too-long caption must not make /start lose both the custom text
    and the main-menu image. We first try the configured photo + caption, then
    retry with the same configured text without HTML entities, and only as a last
    resort send the same text as plain text.
    """
    text, entities, has_saved_entities = await _get_main_menu_message_payload()
    # Приоритет: фото из админки → START_PHOTO_FILE_ID → кэш → файл assets/
    photo_id = (
        await get_ui_photo("main_menu_text")
        or START_PHOTO_FILE_ID
        or get_cached_asset_id("main_menu")
    )
    parse_mode = None if has_saved_entities else "HTML"
    entity_list = entities if has_saved_entities else None

    async def _send_photo(photo):
        return await message.answer_photo(
            photo=photo,
            caption=text,
            caption_entities=entity_list,
            reply_markup=main_menu(),
            parse_mode=parse_mode,
        )

    admin_photo = await get_ui_photo("main_menu_text")
    # photo_id already prefers admin photo; if admin set photo — never fall back to assets/
    if photo_id:
        try:
            sent = await _send_photo(photo_id)
            if sent.photo:
                cache_asset_id("main_menu", sent.photo[-1].file_id)
            return
        except Exception as e:
            print(f"[MAIN MENU] photo failed: {e}")
            if admin_photo:
                # Админское фото битое — не подставляем старое из assets
                pass
            else:
                photo_id = None

    if not admin_photo and START_PHOTO_PATH.exists():
        try:
            sent = await _send_photo(FSInputFile(str(START_PHOTO_PATH)))
            if sent.photo:
                cache_asset_id("main_menu", sent.photo[-1].file_id)
            return
        except Exception as e:
            print(f"[MAIN MENU] local photo failed, keeping custom text: {e}")

    # Never replace an admin-edited greeting with the old hard-coded fallback.
    try:
        await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")
    except Exception as e:
        print(f"[MAIN MENU] HTML send failed, sending plain custom text: {e}")
        await message.answer(text, reply_markup=main_menu())


def make_button_rows(buttons, per_row=2):
    return [
        buttons[i:i + per_row]
        for i in range(0, len(buttons), per_row)
    ]


async def get_discounted_price(telegram_id: int, amount: float):
    discount, _ = await get_roulette_data(telegram_id)
    if not discount:
        return round(amount, 2), 0
    return round(amount * (1 - discount / 100), 2), int(discount)


async def send_main_menu_from_callback(
    callback: CallbackQuery,
    state: FSMContext | None = None,
):
    """Return to the main menu without losing the main-menu image.

    Telegram allows editMessageMedia to replace a text message with a photo,
    so we edit the existing message instead of deleting it first. This avoids
    the old behaviour where the message disappeared if sending the photo failed.
    """
    if state is not None:
        await state.clear()

    text, entities, has_saved_entities = await _get_main_menu_message_payload()
    parse_mode = None if has_saved_entities else "HTML"
    entity_list = entities if has_saved_entities else None
    # Приоритет: фото из админки → START_PHOTO_FILE_ID → кэш → файл assets/
    admin_photo = await get_ui_photo("main_menu_text")
    photo_id = admin_photo or START_PHOTO_FILE_ID or get_cached_asset_id("main_menu")
    # Локальный файл только если админ не задал своё фото
    local_photo = None if admin_photo else (START_PHOTO_PATH if START_PHOTO_PATH.exists() else None)

    # 1) Prefer the cached Telegram file_id, but never delete the current message
    # before a successful edit.
    if photo_id:
        try:
            edited = await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=photo_id,
                    caption=text,
                    caption_entities=entity_list,
                    parse_mode=parse_mode,
                ),
                reply_markup=main_menu(),
            )
            if getattr(edited, "photo", None):
                cache_asset_id("main_menu", edited.photo[-1].file_id)
            return
        except Exception as e:
            print(f"[MAIN MENU] cached photo edit failed: {e}")
            _ASSET_FILE_ID_CACHE.pop("main_menu", None)

    # 2) If the file_id is unavailable/expired, upload the local image directly.
    if local_photo:
        try:
            edited = await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(str(local_photo)),
                    caption=text,
                    caption_entities=entity_list,
                    parse_mode=parse_mode,
                ),
                reply_markup=main_menu(),
            )
            if getattr(edited, "photo", None):
                cache_asset_id("main_menu", edited.photo[-1].file_id)
            return
        except Exception as e:
            print(f"[MAIN MENU] local photo edit failed: {e}")

    # 3) Last-resort fallback. Do not remove the old message until the fallback
    # has a chance to be sent.
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                caption_entities=entity_list,
                reply_markup=main_menu(),
                parse_mode=parse_mode,
            )
        else:
            await callback.message.edit_text(
                text,
                entities=entity_list,
                reply_markup=main_menu(),
                parse_mode=parse_mode,
            )
    except Exception as e:
        print(f"[MAIN MENU] final edit failed: {e}")
        try:
            await callback.message.answer(
                text,
                entities=entity_list,
                reply_markup=main_menu(),
                parse_mode=parse_mode,
            )
            return
        except Exception as e2:
            print(f"[MAIN MENU] final answer failed: {e2}")
            raise


RUB_OWNER_USERNAME = RUB_OWNER_USERNAME
RUB_OWNER_MESSAGE = "Здравствуйте, хочу провести сделку с оплатой рублями."
STARS_OWNER_MESSAGE = "Здравствуйте, хочу провести сделку с оплатой Stars."


async def is_payment_enabled(method: str) -> bool:
    """Return whether a payment method is enabled. Missing settings default to enabled."""
    value = await get_setting(f"payment_{method.lower()}_enabled")
    if value is None:
        return True
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _payment_status(enabled: bool) -> str:
    return "🟢 ВКЛ" if enabled else "🔴 ВЫКЛ"


def _chunk_buttons(buttons: list, per_row: int = 2) -> list[list]:
    """Разбивает список кнопок на ряды по per_row штук (две колонки по умолчанию)."""
    if not buttons:
        return []
    rows = []
    for i in range(0, len(buttons), per_row):
        rows.append(buttons[i : i + per_row])
    return rows


async def product_payment_buttons(product_id: int):
    """Build the common payment-method keyboard for every DB product.

    Все способы оплаты — зелёные (действие). Стиль дополнительно
    принудительно выставляется в InlineKeyboardButton по смыслу.
    """
    buttons = []
    # Внутренний баланс не зависит от переключателей внешних способов оплаты.
    buttons.append(InlineKeyboardButton(
        text=_button_label("💰 Оплатить с баланса", callback_data=f"pay_balance:{product_id}"),
        style="success",
        callback_data=f"pay_balance:{product_id}",
    ))
    if await is_payment_enabled("rub"):
        key = "label:pay_rub"
        buttons.append(InlineKeyboardButton(text=_button_label("₽ RUB / Карта", callback_data=f"pay_rub:{product_id}"), style="success", callback_data=f"pay_rub:{product_id}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    if await is_payment_enabled("rub_owner"):
        key = "label:pay_rub_owner"
        buttons.append(InlineKeyboardButton(text=_button_label("💵 Оплата рублями", callback_data="payment_rub_owner:button"), style="success", callback_data=f"pay_rub_owner:{product_id}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    if await is_payment_enabled("stars_owner"):
        key = "label:pay_stars_owner"
        buttons.append(InlineKeyboardButton(text=_button_label("⭐ Оплата Stars", callback_data="payment_stars_owner:button"), style="success", callback_data=f"pay_stars_owner:{product_id}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    if await is_payment_enabled("sbp"):
        key = "label:pay_sbp"
        buttons.append(InlineKeyboardButton(text=_button_label("🏦 СБП", callback_data=f"pay_yoomoney:{product_id}"), style="success", callback_data=f"pay_yoomoney:{product_id}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    if await is_payment_enabled("usdt"):
        key = "label:pay_usdt"
        buttons.append(InlineKeyboardButton(text=_button_label("₮ USDT", callback_data=f"pay_usdt:{product_id}"), style="success", callback_data=f"pay_usdt:{product_id}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    return buttons


async def stars_payment_buttons(quantity: int, recipient: str = ""):
    """Build payment buttons for the built-in Telegram Stars product.

    Все способы оплаты — зелёные (действие).
    """
    buttons = []
    buttons.append(InlineKeyboardButton(text=_button_label("💰 Оплатить с баланса", callback_data=f"stars_pay_balance:{quantity}"), style="success", callback_data=f"stars_pay_balance:{quantity}", icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_balance")))
    if await is_payment_enabled("rub"):
        key = "label:stars_pay_rub"
        buttons.append(InlineKeyboardButton(text=_button_label("₽ Оплатить RUB", callback_data=f"stars_pay_rub:{quantity}"), style="success", callback_data=f"stars_pay_rub:{quantity}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    if await is_payment_enabled("rub_owner"):
        key = "label:pay_rub_owner"
        buttons.append(InlineKeyboardButton(text=_button_label("💵 Оплата рублями", callback_data="payment_rub_owner:button"), style="success", callback_data=f"stars_pay_rub_owner:{quantity}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    if await is_payment_enabled("usdt"):
        key = "label:stars_pay_usdt"
        buttons.append(InlineKeyboardButton(text=_button_label("₮ Оплатить USDT", callback_data=f"stars_pay_usdt:{quantity}:{recipient.lstrip(chr(64))}"), style="success", callback_data=f"stars_pay_usdt:{quantity}:{recipient.lstrip(chr(64))}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    if await is_payment_enabled("sbp"):
        key = "label:stars_pay_sbp"
        buttons.append(InlineKeyboardButton(text=_button_label("🏦 Оплатить СБП", callback_data=f"stars_pay_yoomoney:{quantity}"), style="success", callback_data=f"stars_pay_yoomoney:{quantity}", icon_custom_emoji_id=_BUTTON_ICONS.get(key)))
    return buttons


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📁 Каталоги", callback_data="admin_catalogs")],
            [InlineKeyboardButton(text="📦 Товары", callback_data="admin_products")],
            [InlineKeyboardButton(text="🧾 Заказы", callback_data="admin_orders")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
            [InlineKeyboardButton(text="🎨 Редактор интерфейса", callback_data="admin_texts")],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")],
        ]
    )


def back_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    style="danger",
                    callback_data="back_main",
                )
            ]
        ]
    )


def _extract_name_custom_emoji(name: str, entities_json: str | None):
    """Возвращает (текст без custom emoji, custom_emoji_id).
    Premium Emoji хранится как Telegram entity, поэтому обычный символ из текста
    не должен дублироваться в кнопке: ID передаём через icon_custom_emoji_id.
    """
    if not name or not entities_json:
        return name or "", None
    try:
        raw = json.loads(entities_json or "[]")
    except Exception:
        return name, None
    boundaries = _utf16_boundaries(name)
    ranges = []
    icon_id = None
    for e in raw:
        if e.get("type") != "custom_emoji" or not e.get("custom_emoji_id"):
            continue
        try:
            a = _u16_to_py(boundaries, int(e.get("offset", 0)))
            b = _u16_to_py(boundaries, int(e.get("offset", 0)) + int(e.get("length", 0)))
            if b > a:
                ranges.append((a, b))
                if icon_id is None:
                    icon_id = str(e.get("custom_emoji_id"))
        except Exception:
            continue
    if not ranges:
        return name, None
    out = name
    for a, b in sorted(ranges, reverse=True):
        out = out[:a] + out[b:]
    return out, icon_id

_CATALOG_NAME_ICONS = {}
_PRODUCT_NAME_ICONS = {}
_CATALOG_NAME_TEXTS = {}
_PRODUCT_NAME_TEXTS = {}

def _refresh_name_emoji_cache_local(kind: str, row_id: int, name: str, entities_json: str | None):
    icon_target = _CATALOG_NAME_ICONS if kind == "catalog" else _PRODUCT_NAME_ICONS
    text_target = _CATALOG_NAME_TEXTS if kind == "catalog" else _PRODUCT_NAME_TEXTS
    clean_name, icon_id = _extract_name_custom_emoji(name or "", entities_json)
    if icon_id:
        icon_target[int(row_id)] = icon_id
        text_target[int(row_id)] = clean_name
    else:
        icon_target.pop(int(row_id), None)
        text_target.pop(int(row_id), None)

async def _load_name_emoji_cache():
    _CATALOG_NAME_ICONS.clear(); _PRODUCT_NAME_ICONS.clear(); _CATALOG_NAME_TEXTS.clear(); _PRODUCT_NAME_TEXTS.clear()
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            cur = await db.execute("SELECT id, name, name_entities FROM catalogs")
            for row_id, name, entities in await cur.fetchall():
                clean, icon = _extract_name_custom_emoji(name, entities)
                if icon:
                    _CATALOG_NAME_ICONS[int(row_id)] = icon
                    _CATALOG_NAME_TEXTS[int(row_id)] = clean
            cur = await db.execute("SELECT id, name, name_entities FROM products")
            for row_id, name, entities in await cur.fetchall():
                clean, icon = _extract_name_custom_emoji(name, entities)
                if icon:
                    _PRODUCT_NAME_ICONS[int(row_id)] = icon
                    _PRODUCT_NAME_TEXTS[int(row_id)] = clean
    except Exception as e:
        print(f"[NAME EMOJI CACHE] {e}")



def _dynamic_object_button_icon(kind: str, object_id: int | None = None, object_name: str | None = None):
    """Возвращает Premium Emoji для динамического каталога/товара.

    Каталоги/товары, созданные кодом, не имеют name_entities, поэтому им
    автоматически применяется Premium Emoji из «Редактора кнопок».
    Индивидуальный Premium Emoji объекта имеет приоритет.
    """
    name_l = str(object_name or '').strip().lower()
    if kind == "catalog":
        own = _CATALOG_NAME_ICONS.get(int(object_id)) if object_id is not None else None
        if own:
            return own
        if "brawl stars" in name_l:
            return _BUTTON_ICONS.get("label:brawl") or _BUTTON_ICONS.get("label:catalog")
        if "roblox" in name_l and "robux" not in name_l:
            return _BUTTON_ICONS.get("label:roblox") or _BUTTON_ICONS.get("label:catalog")
        return _BUTTON_ICONS.get("label:catalog")
    own = _PRODUCT_NAME_ICONS.get(int(object_id)) if object_id is not None else None
    return own or _BUTTON_ICONS.get("label:product")


def _dynamic_object_button_text(kind: str, name: str, object_id: int | None = None, status: str = "") -> str:
    """Сохраняет собственное название объекта, применяя оформление редактора."""
    if kind == "catalog":
        clean = _CATALOG_NAME_TEXTS.get(int(object_id), name) if object_id is not None else name
    else:
        clean = _PRODUCT_NAME_TEXTS.get(int(object_id), name) if object_id is not None else name
    return f"{status} {clean}".strip()

def catalogs_keyboard(catalogs) -> InlineKeyboardMarkup:
    catalog_buttons = []

    for catalog_id, name, is_active in catalogs:
        status = "🟢" if is_active else "🔴"

        catalog_buttons.append(
            InlineKeyboardButton(
                text=_dynamic_object_button_text("catalog", name, catalog_id, status),
                callback_data=f"catalog_view:{catalog_id}",
                icon_custom_emoji_id=_dynamic_object_button_icon("catalog", catalog_id, name),
            )
        )

    buttons = make_button_rows(catalog_buttons, 2)

    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить каталог",
                callback_data="catalog_add",
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🗑 Удалить каталог",
                callback_data="catalog_delete_menu",
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                    style="danger",
                callback_data="admin_back",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_catalog_keyboard(catalogs) -> InlineKeyboardMarkup:
    catalog_buttons = []

    for catalog_id, name, is_active in catalogs:
        catalog_buttons.append(
            InlineKeyboardButton(
                text=_dynamic_object_button_text("catalog", name, catalog_id),
                callback_data=f"product_catalog:{catalog_id}",
                icon_custom_emoji_id=_dynamic_object_button_icon("catalog", catalog_id, name),
            )
        )

    buttons = make_button_rows(catalog_buttons, 2)

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                    style="danger",
                callback_data="admin_back",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


async def show_text_or_photo(
    callback: CallbackQuery,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    ui_key: str | None = None,
    photo: str | None = None,
):
    """Показать текст или фото+подпись для экрана меню.

    Если передан ui_key — подтягивается сохранённое фото экрана (ui_photo:<key>).
    photo можно передать явно (имеет приоритет).
    """
    photo_id = photo
    if photo_id is None and ui_key:
        photo_id = await get_ui_photo(ui_key)

    try:
        if photo_id:
            # Есть фото для этого меню
            if callback.message.photo:
                try:
                    await callback.message.edit_media(
                        media=InputMediaPhoto(media=photo_id, caption=text, parse_mode="HTML"),
                        reply_markup=keyboard,
                    )
                    return
                except Exception as e:
                    print(f"[DISPLAY] edit_media failed: {e}")
            try:
                await callback.message.delete()
            except Exception:
                pass
            try:
                await callback.message.answer_photo(
                    photo=photo_id,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return
            except Exception as e:
                print(f"[DISPLAY] answer_photo failed: {e}")
                # fallback to text

        # Без фото — обычный текст
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return

        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"[DISPLAY] {e}")
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            if photo_id:
                await callback.message.answer_photo(
                    photo=photo_id,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await callback.message.answer(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
        except Exception as e2:
            print(f"[DISPLAY NEW] {e2}")



async def crypto_api(
    method: str,
    data: dict | None = None,
):
    if not CRYPTO_PAY_TOKEN:
        raise RuntimeError(
            "CRYPTO_PAY_TOKEN не указан в config.py"
        )

    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
        "Content-Type": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=30)

    # Прокси используется только если PROXY_URL задан в переменных окружения.
    # Если прокси не задан, подключаемся напрямую.
    connector = ProxyConnector.from_url(PROXY_URL) if PROXY_URL else None

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
    ) as session:
        async with session.post(
            f"{CRYPTO_PAY_API}/{method}",
            headers=headers,
            json=data or {},
        ) as response:
            raw_text = await response.text()
            try:
                result = json.loads(raw_text)
            except Exception:
                raise RuntimeError(
                    f"Crypto Pay HTTP {response.status}: non-JSON response: {raw_text[:500]}"
                )

            if not result.get("ok"):
                error = result.get("error") or {}
                code = error.get("code", response.status) if isinstance(error, dict) else response.status
                name = error.get("name", "UNKNOWN") if isinstance(error, dict) else str(error)
                raise RuntimeError(
                    f"Crypto Pay API error: HTTP {response.status}, code={code}, name={name}, response={result}"
                )

            return result["result"]


async def ensure_balance_tables():
    """Создаёт таблицы внутреннего баланса и пополнений, не затрагивая существующую схему БД."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_balances (
                user_id INTEGER PRIMARY KEY,
                balance_rub REAL NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS balance_topups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                amount_rub REAL NOT NULL,
                method TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                invoice_id INTEGER,
                receipt_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                credited_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS balance_topup_codes (
                topup_id INTEGER PRIMARY KEY,
                code TEXT NOT NULL UNIQUE
            )
        """)
        await db.commit()


def _new_public_code(length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def get_topup_code(topup_id: int) -> str:
    """Возвращает стабильный публичный ID пополнения вида TJTV4CEK34."""
    topup_id = int(topup_id)
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT code FROM balance_topup_codes WHERE topup_id = ?",
            (topup_id,),
        )
        row = await cursor.fetchone()
        if row:
            return str(row[0])

        # Редко возможный конфликт решаем повторной генерацией.
        for _ in range(20):
            code = _new_public_code(10)
            try:
                await db.execute(
                    "INSERT INTO balance_topup_codes(topup_id, code) VALUES (?, ?)",
                    (topup_id, code),
                )
                await db.commit()
                return code
            except aiosqlite.IntegrityError:
                continue
        raise RuntimeError("Не удалось создать публичный ID пополнения")


async def get_balance_rub(telegram_id: int) -> float:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT balance_rub FROM user_balances WHERE user_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return float(row[0]) if row else 0.0


async def debit_balance_rub(telegram_id: int, amount_rub: float) -> bool:
    """Атомарно списывает сумму с внутреннего баланса. Возвращает False при нехватке средств."""
    amount_rub = round(float(amount_rub), 2)
    if amount_rub <= 0:
        return False
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            "UPDATE user_balances SET balance_rub = balance_rub - ? WHERE user_id = ? AND balance_rub >= ?",
            (amount_rub, telegram_id, amount_rub),
        )
        if cursor.rowcount != 1:
            await db.rollback()
            return False
        await db.commit()
        return True


async def credit_balance_rub(telegram_id: int, amount_rub: float):
    amount_rub = round(float(amount_rub), 2)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO user_balances(user_id, balance_rub) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance_rub = balance_rub + excluded.balance_rub
        """, (telegram_id, amount_rub))
        await db.commit()


async def create_topup(telegram_id: int, amount_rub: float, method: str, invoice_id: int | None = None) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO balance_topups(telegram_id, amount_rub, method, invoice_id) VALUES (?, ?, ?, ?)",
            (telegram_id, round(float(amount_rub), 2), method, invoice_id),
        )
        await db.commit()
        topup_id = int(cursor.lastrowid)
    await get_topup_code(topup_id)
    return topup_id


async def get_topup(topup_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT id, telegram_id, amount_rub, method, status, invoice_id, receipt_file_id FROM balance_topups WHERE id = ?", (topup_id,))
        return await cursor.fetchone()


async def set_topup_receipt(topup_id: int, file_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE balance_topups SET receipt_file_id = ?, status = 'waiting_review' WHERE id = ?", (file_id, topup_id))
        await db.commit()


async def finish_topup(topup_id: int, status: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT telegram_id, amount_rub, status FROM balance_topups WHERE id = ?", (topup_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        telegram_id, amount_rub, current_status = row
        if current_status != 'pending' and current_status != 'waiting_review':
            return row
        await db.execute(
            "UPDATE balance_topups SET status = ?, credited_at = CASE WHEN ? = 'paid' THEN CURRENT_TIMESTAMP ELSE credited_at END WHERE id = ?",
            (status, status, topup_id),
        )
        await db.commit()
    if status == 'paid':
        await credit_balance_rub(int(telegram_id), float(amount_rub))
    return row


async def get_crypto_rub_rate(asset: str) -> float:
    """Получает актуальный курс Crypto Pay: 1 asset в RUB.

    Crypto Pay API возвращает getExchangeRates как массив объектов
    (после crypto_api() это уже result без внешнего поля ``result``),
    поэтому здесь обрабатываем и список, и словарь для совместимости.
    """
    asset = asset.upper()
    result = await crypto_api("getExchangeRates")

    if isinstance(result, list):
        rates = result
    elif isinstance(result, dict):
        rates = result.get("items", result.get("rates", []))
    else:
        rates = []

    for item in rates:
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("source", "")).upper() == asset
            and str(item.get("target", "")).upper() == "RUB"
            and item.get("is_valid", True)
        ):
            try:
                rate = float(item.get("rate", 0))
            except (TypeError, ValueError):
                continue
            if rate > 0:
                return rate

    raise RuntimeError(f"Не найден актуальный курс {asset}/RUB в Crypto Pay")


async def create_crypto_topup_invoice(amount_rub: float, telegram_id: int, topup_id: int, asset: str):
    return await crypto_api(
        "createInvoice",
        {
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": f"{float(amount_rub):.2f}",
            "accepted_assets": asset,
            "description": f"Пополнение баланса #{await get_topup_code(topup_id)}",
            "payload": f"topup:{topup_id}:{telegram_id}",
            "allow_comments": False,
            "allow_anonymous": False,
            "expires_in": 3600,
        },
    )


async def create_crypto_invoice(
    amount: float,
    order_id: int,
):
    return await crypto_api(
        "createInvoice",
        {
            "asset": "USDT",
            "amount": f"{amount:.4f}",
            "description": f"Заказ #{await get_order_code(order_id)}",
            "payload": f"order:{order_id}",
            "allow_comments": False,
            "allow_anonymous": True,
            "expires_in": 3600,
        },
    )


async def get_crypto_invoice(invoice_id: int):
    result = await crypto_api(
        "getInvoices",
        {
            "invoice_ids": str(invoice_id),
        },
    )

    items = result.get("items", [])

    if not items:
        return None

    return items[0]


async def ensure_catalog_images_db():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("PRAGMA table_info(catalogs)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "image_file_id" not in columns:
            await db.execute("ALTER TABLE catalogs ADD COLUMN image_file_id TEXT")
            await db.commit()


async def get_catalog_image(catalog_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT image_file_id FROM catalogs WHERE id = ?", (catalog_id,))
        row = await cursor.fetchone()
    return row[0] if row else None


async def set_catalog_image(catalog_id: int, image_file_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE catalogs SET image_file_id = ? WHERE id = ?", (image_file_id, catalog_id))
        await db.commit()


async def get_created_catalog_id(name: str, parent_id):
    async with aiosqlite.connect(DB_NAME) as db:
        if parent_id is None:
            cursor = await db.execute("SELECT id FROM catalogs WHERE name = ? AND parent_id IS NULL ORDER BY id DESC LIMIT 1", (name,))
        else:
            cursor = await db.execute("SELECT id FROM catalogs WHERE name = ? AND parent_id = ? ORDER BY id DESC LIMIT 1", (name, parent_id))
        row = await cursor.fetchone()
    return row[0] if row else None


# ============================================================
# START
# ============================================================





@dp.callback_query(F.data == "subscription_check")
async def subscription_check_handler(callback: CallbackQuery):
    await callback.answer("Проверяю подписку…")
    if await is_subscribed(callback.bot, callback.from_user.id, force=True):
        try:
            await callback.message.delete()
        except Exception:
            pass
        await show_main_menu(callback.message)
    else:
        try:
            await callback.message.edit_text(
                "❌ <b>Подписка не найдена</b>\n\n"
                "Подпишитесь на наш канал по кнопке выше, затем нажмите «Проверить подписку» ещё раз.",
                reply_markup=subscription_keyboard(),
                parse_mode="HTML",
            )
        except Exception:
            await show_subscription_required(callback)


@dp.message(CommandStart())
async def start_handler(message: Message):
    # /start должен отвечать даже если статистика/БД временно недоступны.
    user_id = message.from_user.id
    # Реферальная ссылка: /start ref_123456789
    referrer_id = None
    try:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1:
            payload = parts[1].strip()
            if payload.startswith("ref_"):
                referrer_id = int(payload[4:])
    except Exception:
        referrer_id = None

    # Новый ли пользователь (до INSERT)
    was_new = False
    try:
        existing = await get_user_by_telegram_id(user_id)
        was_new = existing is None
    except Exception:
        was_new = False

    try:
        await add_user(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    except Exception as e:
        print(f"[START] add_user error for {user_id}: {e}")

    # Рефералка: только новый пользователь + Telegram Premium у приглашённого
    if was_new and referrer_id:
        is_premium = bool(getattr(message.from_user, "is_premium", False))
        try:
            rewarded, info = await process_referral_on_start(
                referred_telegram_id=user_id,
                referrer_telegram_id=referrer_id,
                is_premium=is_premium,
            )
            print(f"[REF] user={user_id} ref={referrer_id} premium={is_premium} -> {info}")
            if rewarded:
                try:
                    await message.bot.send_message(
                        referrer_id,
                        "🎉 По вашей ссылке пришёл пользователь с <b>Telegram Premium</b>!\n"
                        f"+<b>{int(REF_REWARD_RUB)} ₽</b> на реферальный баланс.\n"
                        f"Баланс можно только вывести (от {int(REF_MIN_WITHDRAW_RUB)} ₽).",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    print(f"[REF] notify referrer failed: {e}")
            elif not is_premium:
                # Можно тихо не писать приглашённому, или коротко:
                pass
        except Exception as e:
            print(f"[REF] process error: {e}")

    try:
        await record_start(user_id)
    except Exception as e:
        print(f"[START] record_start error for {user_id}: {e}")

    try:
        subscribed = await is_subscribed(message.bot, user_id, force=True)
    except Exception as e:
        print(f"[START] subscription check error for {user_id}: {e}")
        subscribed = False

    if not subscribed:
        try:
            await show_subscription_required(message)
        except Exception as e:
            print(f"[START] subscription screen error for {user_id}: {e}")
            await message.answer(
                "📢 <b>Для использования бота необходимо подписаться на наш канал.</b>\n\n"
                "После подписки нажмите «Проверить подписку»."
                , parse_mode="HTML",
            )
        return

    try:
        await show_main_menu(message)
    except Exception as e:
        print(f"[START] main menu error for {user_id}: {e}")
        # Гарантированный ответ на /start, даже если сломалась картинка/БД/кастомный текст.
        await message.answer(
            "👋 <b>Добро пожаловать в {shop_name}!</b>\n\n"
            "Выберите нужный раздел ниже:",
            reply_markup=main_menu(),
            parse_mode="HTML",
        )


# ============================================================
# ADMIN
# ============================================================

@dp.message(F.text == "/admin")
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            "⛔ У вас нет доступа к этой панели."
        )
        return

    admin_text = await _get_admin_ui_text(
        "admin_main",
        _ui_text_default("admin_main"),
    )
    await message.answer(
        admin_text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    await callback.answer()

    admin_text = await _get_admin_ui_text(
        "admin_main",
        _ui_text_default("admin_main"),
    )
    await callback.message.edit_text(
        admin_text,
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# ============================================================
# ТЕКСТЫ ИНТЕРФЕЙСА
# ============================================================

@dp.callback_query(F.data == "admin_texts")
async def admin_texts(callback: CallbackQuery, state: FSMContext):
    await _render_ui_editor(callback, state, page=0)


@dp.callback_query(F.data.startswith("admin_texts_page:"))
async def admin_texts_page(callback: CallbackQuery, state: FSMContext):
    try:
        page = int(callback.data.split(":")[1])
    except Exception:
        page = 0
    await _render_ui_editor(callback, state, page=page)


async def _render_ui_editor(callback: CallbackQuery, state: FSMContext, page: int = 0):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    try:
        await callback.answer()
    except Exception:
        pass

    editor_text = await _get_admin_ui_text(
        "admin_texts",
        _ui_text_default("admin_texts"),
    )
    items = list(UI_EDITABLE.items())
    per_page = 12
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(int(page), total_pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]

    rows = []
    for key, (title, _storage, _hint) in chunk:
        rows.append([InlineKeyboardButton(
            text=title,
            callback_data=f"admin_ui_{key}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_texts_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="admin_texts_page:" + str(page)))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_texts_page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="👁 Предпросмотр главного меню", callback_data="admin_ui_preview")])
    rows.append([InlineKeyboardButton(text="🧹 Сбросить текст", callback_data="admin_ui_reset")])
    rows.append([InlineKeyboardButton(text="🔘 Редактор кнопок", callback_data="admin_text_button_list")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="admin_back")])

    tip = chr(10) + chr(10) + f"👇 Окна {page + 1}/{total_pages}. Текст / Premium Emoji / фото:"
    body = editor_text + tip
    try:
        await callback.message.edit_text(
            body,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML",
        )
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            body,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("admin_ui_set_photo:"))
async def admin_ui_set_photo(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    if key not in UI_EDITABLE:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    title, storage_key, _ = UI_EDITABLE[key]
    await state.clear()
    await state.update_data(ui_key=storage_key, ui_edit_key=key)
    await state.set_state(InterfaceTextState.waiting_ui_photo)
    await callback.answer()
    await callback.message.edit_text(
        f"🖼 <b>Фото для: {html.escape(title)}</b>\n\n"
        "Отправьте <b>фотографию</b> одним сообщением.\n"
        "Она будет показываться на этом экране меню.\n\n"
        "Чтобы отменить — нажмите «Назад».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=f"admin_ui_{key}")]
        ]),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("admin_ui_clear_photo:"))
async def admin_ui_clear_photo(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    if key not in UI_EDITABLE:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    storage_key = UI_EDITABLE[key][1]
    await clear_ui_photo(storage_key)
    if storage_key == "main_menu_text":
        _ASSET_FILE_ID_CACHE.pop("main_menu", None)
    await callback.answer("Фото удалено")
    callback.data = f"admin_ui_{key}"
    await admin_ui_edit(callback, state)


@dp.message(InterfaceTextState.waiting_ui_photo)
async def admin_ui_photo_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("ui_key")
    edit_key = data.get("ui_edit_key")
    if not key:
        await state.clear()
        return
    if not message.photo:
        await message.answer("❌ Пришлите именно фото (не файл и не стикер).")
        return
    file_id = message.photo[-1].file_id
    await set_ui_photo(key, file_id)
    if key == "main_menu_text":
        _ASSET_FILE_ID_CACHE.pop("main_menu", None)
    await state.clear()
    await message.answer(
        "✅ <b>Фото сохранено для этого меню.</b>\n"
        "Теперь оно будет показываться пользователям на этом экране.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К редактору", callback_data=f"admin_ui_{edit_key}" if edit_key else "admin_texts")],
            [InlineKeyboardButton(text="🎨 Все тексты", callback_data="admin_texts")],
        ]),
    )


@dp.callback_query(F.data.startswith("admin_ui_"))
async def admin_ui_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    key = callback.data[len("admin_ui_"):]
    # set_photo / clear_photo обрабатываются отдельными хендлерами выше
    if key.startswith("set_photo") or key.startswith("clear_photo"):
        return
    if key in {"preview", "reset"} or key not in UI_EDITABLE:
        return
    title, storage_key, hint = UI_EDITABLE[key]
    await state.clear()
    await state.update_data(ui_key=storage_key, ui_edit_key=key)
    current, _ = await _get_ui_text(
        storage_key,
        _ui_text_default(storage_key) if storage_key != "main_menu_text" else (await _get_main_menu_text())[0],
    )
    photo = await get_ui_photo(storage_key)
    photo_status = "✅ фото установлено" if photo else "❌ фото нет"
    await state.set_state(InterfaceTextState.waiting_ui_text)
    await callback.answer()
    kb = [
        [InlineKeyboardButton(text="🖼 Поставить / заменить фото", callback_data=f"admin_ui_set_photo:{key}")],
        [InlineKeyboardButton(text="🗑 Убрать фото", callback_data=f"admin_ui_clear_photo:{key}")],
        [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="admin_texts")],
    ]
    body = (
        f"🎨 <b>{html.escape(title)}</b>" + chr(10) + chr(10)
        + f"{html.escape(hint)}" + chr(10) + chr(10)
        + f"🖼 Фото экрана: <b>{photo_status}</b>" + chr(10) + chr(10)
        + "Текущий текст:" + chr(10)
        + f"<blockquote>{(current or '')[:3000]}</blockquote>" + chr(10) + chr(10)
        + "✏️ Отправьте <b>новый текст одним сообщением</b>." + chr(10)
        + "Или нажмите кнопку ниже, чтобы поставить фото на это меню." + chr(10)
        + "Можно использовать HTML: <b>жирный</b>, <u>подчёркивание</u>, <i>курсив</i>." + chr(10)
        + "💎 Premium Emoji из отправленного сообщения сохранятся автоматически."
    )
    try:
        await callback.message.edit_text(
            body,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"[UI EDIT] edit failed: {e}")
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            body,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML",
        )



async def _render_button_editor(callback: CallbackQuery, page: int = 0):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    items = list(_BUTTON_REGISTRY.items())
    if not items:
        items = list(_BUTTON_TEXTS.items())

    per_page = 20
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(int(page), total_pages - 1))
    start = page * per_page
    page_items = items[start:start + per_page]

    rows = []
    _BUTTON_EDITOR_KEYS.clear()
    for idx, (key, default) in enumerate(page_items):
        label = (_BUTTON_TEXTS.get(key) or default or key).replace("\n", " ")[:40]
        edit_id = str(idx)
        _BUTTON_EDITOR_KEYS[edit_id] = key
        icon_mark = "💎 " if _BUTTON_ICONS.get(key) else ""
        rows.append([_TelegramInlineKeyboardButton(
            text=f"🔘 {icon_mark}{label}",
            callback_data=f"admin_button_edit_id:{edit_id}",
        )])

    nav = []
    if page > 0:
        nav.append(_TelegramInlineKeyboardButton(text="◀️", callback_data=f"admin_text_button_page:{page - 1}"))
    if page < total_pages - 1:
        nav.append(_TelegramInlineKeyboardButton(text="▶️", callback_data=f"admin_text_button_page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([_TelegramInlineKeyboardButton(text="⬅️ Назад", callback_data="admin_texts")])

    text = await _get_admin_ui_text(
        "admin_buttons",
        _ui_text_default("admin_buttons"),
        {"page": page + 1, "total_pages": total_pages, "count": len(items)},
    )
    # Если администратор не добавил эти переменные в шаблон, показываем их
    # отдельной строкой, сохраняя обратную совместимость.
    if "{page}" not in (await _get_ui_text("admin_buttons", _ui_text_default("admin_buttons")))[0]:
        text += f"\n\nСтраница {page + 1}/{total_pages} · Всего кнопок: {len(items)}"
    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    except Exception as e:
        print(f"[BUTTON EDITOR] render failed: {e}")
    finally:
        try:
            await callback.answer()
        except Exception:
            pass


@dp.callback_query(F.data == "admin_text_button_list")
async def admin_text_button_list(callback: CallbackQuery, state: FSMContext | None = None):
    await _render_button_editor(callback, 0)


@dp.callback_query(F.data.startswith("admin_text_button_page:"))
async def admin_text_button_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    try:
        page = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("❌ Ошибка страницы", show_alert=True)
        return
    await _render_button_editor(callback, page)


@dp.callback_query(F.data.startswith("admin_button_edit_id:"))
async def admin_button_edit_id(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    edit_id = callback.data.split(":", 1)[1]
    key = _BUTTON_EDITOR_KEYS.get(edit_id)
    if not key:
        await callback.answer("❌ Список кнопок устарел. Откройте редактор заново.", show_alert=True)
        return
    await admin_button_edit_by_key(callback, state, key, edit_id=edit_id)


@dp.callback_query(F.data.startswith("admin_button_edit:"))
async def admin_button_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    # Может прийти полный key или edit_id через state
    key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if key not in _BUTTON_REGISTRY and data.get("button_key"):
        key = data["button_key"]
    await admin_button_edit_by_key(callback, state, key, edit_id=data.get("button_edit_id"))


async def admin_button_edit_by_key(
    callback: CallbackQuery,
    state: FSMContext,
    key: str,
    edit_id: str | None = None,
):
    if key not in _BUTTON_REGISTRY:
        await callback.answer("❌ Кнопка не найдена", show_alert=True)
        return
    await state.clear()
    await state.update_data(button_key=key, button_edit_id=edit_id or "")
    # НЕ ставим waiting_button_text здесь — иначе emoji/текст путаются
    current = _BUTTON_TEXTS.get(key) or _BUTTON_REGISTRY[key]
    icon_id = _BUTTON_ICONS.get(key)
    await callback.answer()
    # Короткие callback без обрезки ключа — key живёт в FSM
    kb = [
        [InlineKeyboardButton(text="✏️ Текст + Premium Emoji", callback_data="admin_btn_do:text")],
        [InlineKeyboardButton(text="🗑 Убрать Premium Emoji", callback_data="admin_btn_do:emoji_clear")],
        [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="admin_text_button_list")],
    ]
    try:
        await callback.message.edit_text(
            f"🔘 <b>Редактирование кнопки</b>\n\n"
            f"Ключ: <code>{html.escape(key)}</code>\n"
            f"Текущее название: <b>{html.escape(current)}</b>\n"
            f"💎 Premium Emoji: <b>{'установлен (' + str(icon_id) + ')' if icon_id else 'не установлен'}</b>\n\n"
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML",
        )
    except Exception as e:
        print(f"[BTN EDIT] {e}")
        await callback.message.answer(
            f"🔘 <b>Редактирование кнопки</b>\n\n"
            f"Ключ: <code>{html.escape(key)}</code>\n"
            f"Текущее название: <b>{html.escape(current)}</b>\n"
            f"💎 Premium Emoji: <b>{'есть' if icon_id else 'нет'}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("admin_btn_do:"))
async def admin_btn_do(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    key = data.get("button_key")
    if not key or key not in _BUTTON_REGISTRY:
        await callback.answer("❌ Сначала выберите кнопку в списке заново", show_alert=True)
        return

    if action == "text":
        await state.set_state(InterfaceTextState.waiting_button_text)
        await callback.answer()
        await callback.message.edit_text(
            "✏️ <b>Текст кнопки + Premium Emoji</b>"
            + chr(10) + chr(10)
            + "Отправьте <b>одним сообщением</b>:"
            + chr(10)
            + "• в начале — Premium Emoji (по желанию)"
            + chr(10)
            + "• затем текст кнопки"
            + chr(10) + chr(10)
            + "Бот сам поставит emoji слева на кнопке и сохранит текст.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="admin_btn_do:back")
            ]]),
            parse_mode="HTML",
        )
        return

    if action == "emoji_clear":
        await set_setting(f"button_icon:{key}", "")
        await set_setting(f"button_icon_fallback:{key}", "")
        _set_button_icon_local(key, None, None)
        await callback.answer("🗑 Premium Emoji убран")
        await admin_button_edit_by_key(callback, state, key, edit_id=data.get("button_edit_id"))
        return

    if action == "back":
        await admin_button_edit_by_key(callback, state, key, edit_id=data.get("button_edit_id"))
        return

    await callback.answer("Неизвестное действие", show_alert=True)


@dp.message(InterfaceTextState.waiting_button_text)
async def admin_button_text_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text and not message.caption:
        await message.answer("❌ Отправьте текст (можно с Premium Emoji в начале).")
        return
    data = await state.get_data()
    key = data.get("button_key")
    if not key:
        await state.clear()
        await message.answer("❌ Сессия сброшена. Откройте редактор кнопок заново.")
        return

    try:
        label = _button_label_from_message(message)
    except Exception as e:
        print(f"[BTN] label extract error: {e}")
        label = (message.text or message.caption or "").strip()
    if not label:
        label = (message.text or message.caption or "").strip()
    # Если прислали только emoji — оставляем прежний текст кнопки
    if not label or not any(ch.isalnum() or ord(ch) > 127 for ch in label):
        prev = _BUTTON_TEXTS.get(key) or _BUTTON_REGISTRY.get(key) or "Кнопка"
        # если label пустой после вырезания emoji
        if not label.strip():
            label = prev

    try:
        icon_id = _extract_premium_emoji_id(message)
    except Exception as e:
        print(f"[BTN] emoji extract error: {e}")
        icon_id = None

    print(f"[BTN SAVE] key={key!r} label={label!r} icon={icon_id!r}")

    await set_setting(f"button_text:{key}", label)
    _set_button_text_local(key, label)

    if icon_id:
        await set_setting(f"button_icon:{key}", icon_id)
        _set_button_icon_local(key, icon_id)

    await state.clear()
    await state.update_data(button_key=key)

    note = (
        f"💎 Premium Emoji: <code>{html.escape(icon_id)}</code>"
        if icon_id
        else "💎 Premium Emoji в сообщении не было (иконка не менялась)"
    )
    try:
        preview_kwargs = {"text": label, "callback_data": "admin_text_button_list"}
        if icon_id:
            preview_kwargs["icon_custom_emoji_id"] = icon_id
        preview = _TelegramInlineKeyboardButton(**preview_kwargs)
        await message.answer(
            f"✅ <b>Кнопка обновлена</b>{chr(10)}"
            f"Текст: <b>{html.escape(label)}</b>{chr(10)}"
            f"{note}{chr(10)}{chr(10)}Превью:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [preview],
                [InlineKeyboardButton(text="⬅️ К списку кнопок", callback_data="admin_text_button_list")],
            ]),
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(
            f"✅ Сохранено.{chr(10)}Текст: <b>{html.escape(label)}</b>{chr(10)}"
            f"{note}{chr(10)}<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ К списку кнопок", callback_data="admin_text_button_list"),
            ]]),
        )



@dp.callback_query(F.data == "admin_ui_preview")
async def admin_ui_preview(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.answer()
    text, entities = await _get_main_menu_text()
    rendered = _render_custom_emoji_html(text, entities) if entities else text
    await callback.message.answer(
        "👁 <b>Предпросмотр главного меню</b>\n\n" + rendered,
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "admin_ui_reset")
async def admin_ui_reset(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    buttons = []
    for key, (title, _, _) in UI_EDITABLE.items():
        buttons.append([InlineKeyboardButton(text=f"🧹 {title}", callback_data=f"admin_ui_reset_one:{key}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="admin_texts")])
    await callback.message.edit_text("🧹 <b>Сбросить сохранённый текст</b>\n\nВыбери раздел:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


@dp.callback_query(F.data.startswith("admin_ui_reset_one:"))
async def admin_ui_reset_one(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    if key not in UI_EDITABLE:
        await callback.answer("❌ Раздел не найден", show_alert=True)
        return
    storage_key = UI_EDITABLE[key][1]
    await set_setting(f"ui_text:{storage_key}", "")
    await set_setting(f"ui_entities:{storage_key}", "")
    await set_setting(f"ui_photo:{storage_key}", "")
    if storage_key == "main_menu_text":
        await set_setting("main_menu_text", "")
        await set_setting("main_menu_text_entities", "")
    await callback.answer("✅ Сброшено")
    await admin_texts(callback, FSMContext) if False else callback.message.edit_text("✅ <b>Текст сброшен.</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ К редактору", callback_data="admin_texts")]]), parse_mode="HTML")


@dp.message(InterfaceTextState.waiting_ui_text)
async def admin_ui_text_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text and not message.caption:
        await message.answer("❌ Отправь текстовым сообщением.")
        return
    data = await state.get_data()
    key = data.get("ui_key")
    if not key:
        await state.clear()
        return
    text = message.text or message.caption or ""
    entities = _custom_emoji_entities(message)
    if key == "main_menu_text":
        await set_setting("main_menu_text", text)
        await set_setting("main_menu_text_entities", entities or "")
    else:
        await set_setting(f"ui_text:{key}", text)
        await set_setting(f"ui_entities:{key}", entities or "")
    await state.clear()
    await message.answer("✅ <b>Текст сохранён.</b>\n\n💎 Premium Emoji также сохранены.", parse_mode="HTML")


# ============================================================
# КАТАЛОГИ
# ============================================================

@dp.callback_query(F.data == "admin_catalogs")
async def admin_catalogs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    catalogs = await get_catalogs()

    await callback.answer()

    await callback.message.edit_text(await _get_admin_ui_text(
        "admin_catalogs",
        _ui_text_default("admin_catalogs"),
    ),
        reply_markup=catalogs_keyboard(catalogs),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("catalog_add"))
async def catalog_add(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    parent_id = None
    if callback.data.startswith("catalog_add:"):
        try:
            parent_id = int(callback.data.split(":", 1)[1])
        except (ValueError, IndexError):
            await callback.answer("❌ Некорректный каталог.", show_alert=True)
            return

        parent = await get_catalog(parent_id)
        if not parent:
            await callback.answer("❌ Родительский каталог не найден.", show_alert=True)
            return

    await state.clear()
    await state.update_data(parent_id=parent_id)
    await state.set_state(CatalogState.waiting_name)

    await callback.answer()

    if parent_id is None:
        text = (
            "➕ <b>Создание каталога</b>\n\n"
            "Введите название каталога:"
        )
    else:
        parent = await get_catalog(parent_id)
        text = (
            "➕ <b>Создание подкаталога</b>\n\n"
            f" Родительский каталог: <b>{parent[1]}</b>\n\n"
            "Введите название подкаталога:"
        )

    await callback.message.answer(text, parse_mode="HTML")


@dp.message(CatalogState.waiting_name)
async def catalog_name(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    if not message.text:
        await message.answer(
            "❌ Введите название текстом."
        )
        return

    name = message.text.strip()
    name_entities = _custom_emoji_entities(message)

    if len(name) < 2:
        await message.answer(
            "❌ Название слишком короткое."
        )
        return

    data = await state.get_data()
    parent_id = data.get("parent_id")

    await state.update_data(name=name, name_entities=name_entities)
    await state.set_state(CatalogState.waiting_image)
    await message.answer(
        "🖼 <b>Отправьте картинку каталога.</b>\n\n"
        "Она будет показываться пользователям при открытии каталога.\n"
        "Если картинка не нужна, напишите <code>нет</code>.",
        parse_mode="HTML",
    )


@dp.message(CatalogState.waiting_image)
async def catalog_image(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    file_id = _message_image_file_id(message)
    if file_id:
        image_file_id = file_id
    elif message.text and message.text.strip().lower() == "нет":
        image_file_id = None
    else:
        await message.answer(
            "❌ Отправьте <b>фотографию</b> (или картинку файлом) или напишите <code>нет</code>.",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    parent_id = data.get("parent_id")
    name = data.get("name")
    if not name:
        await state.clear()
        await message.answer("❌ Не удалось создать каталог.")
        return

    try:
        # create_catalog возвращает реальный ID созданной записи.
        # Не ищем каталог повторно по имени: при одинаковых названиях это могло
        # выбрать другую запись и сохранить Premium Emoji не в тот каталог.
        catalog_id = await create_catalog(name, parent_id=parent_id)
        if catalog_id:
            await _save_custom_emoji_entities(
                "catalogs",
                "name_entities",
                catalog_id,
                data.get("name_entities"),
            )
        if catalog_id:
            await set_catalog_image(catalog_id, image_file_id)
            _refresh_name_emoji_cache_local("catalog", int(catalog_id), name, data.get("name_entities"))
    except Exception as e:
        print(f"Ошибка создания каталога: {e}")
        await state.clear()
        await message.answer("❌ Не удалось создать каталог.")
        return

    await state.clear()
    if parent_id is None:
        await message.answer(f"✅ Каталог <b>{name}</b> успешно создан!", parse_mode="HTML")
        catalogs = await get_catalogs()
        await message.answer("📁 <b>Каталоги</b>", reply_markup=catalogs_keyboard(catalogs), parse_mode="HTML")
    else:
        await message.answer(f"✅ Подкаталог <b>{name}</b> успешно создан!", parse_mode="HTML")
        children = await get_catalogs(parent_id)
        parent = await get_catalog(parent_id)
        await message.answer(f"📁 <b>{parent[1] if parent else 'Каталог'}</b>", reply_markup=catalog_children_keyboard(parent_id, children), parse_mode="HTML")



def catalog_children_keyboard(parent_id: int, children) -> InlineKeyboardMarkup:
    buttons = []
    for catalog_id, name, is_active in children:
        status = "🟢" if is_active else "🔴"
        buttons.append([
            InlineKeyboardButton(
                text=_dynamic_object_button_text("catalog", name, catalog_id, status),
                callback_data=f"catalog_view:{catalog_id}",
                icon_custom_emoji_id=_dynamic_object_button_icon("catalog", catalog_id, name),
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить подкаталог",
            callback_data=f"catalog_add:{parent_id}",
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
                    style="danger",
            callback_data="catalog_back_root",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ============================================================
# ПЕРЕНОС ТОВАРОВ И КАТАЛОГОВ
# ============================================================

async def _admin_get_all_catalogs():
    """Возвращает все каталоги для выбора места переноса."""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id, name, parent_id, is_active FROM catalogs ORDER BY id"
        )
        return await cursor.fetchall()


async def _admin_get_catalog_descendants(catalog_id: int) -> set[int]:
    """Находит всех потомков каталога, чтобы запретить циклический перенос."""
    rows = await _admin_get_all_catalogs()
    children = {}
    for row_id, _name, parent_id, _is_active in rows:
        children.setdefault(parent_id, []).append(row_id)

    descendants = set()
    stack = list(children.get(catalog_id, []))
    while stack:
        current = stack.pop()
        if current in descendants:
            continue
        descendants.add(current)
        stack.extend(children.get(current, []))
    return descendants


async def _admin_move_product(product_id: int, catalog_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id FROM catalogs WHERE id = ?",
            (catalog_id,),
        )
        if not await cursor.fetchone():
            return False
        await db.execute(
            "UPDATE products SET catalog_id = ? WHERE id = ?",
            (catalog_id, product_id),
        )
        await db.commit()
    return True


async def _admin_move_catalog(catalog_id: int, parent_id: int | None) -> tuple[bool, str]:
    catalog = await get_catalog(catalog_id)
    if not catalog:
        return False, "Каталог не найден."

    if parent_id == catalog_id:
        return False, "Нельзя переместить каталог в самого себя."

    descendants = await _admin_get_catalog_descendants(catalog_id)
    if parent_id is not None and parent_id in descendants:
        return False, "Нельзя переместить каталог внутрь его подкаталога."

    if parent_id is not None:
        destination = await get_catalog(parent_id)
        if not destination:
            return False, "Каталог назначения не найден."

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE catalogs SET parent_id = ? WHERE id = ?",
            (parent_id, catalog_id),
        )
        await db.commit()
    return True, "Каталог перемещён."


def _catalog_move_keyboard(catalogs, current_catalog_id: int, current_parent_id: int | None):
    buttons = []
    for catalog_id, name, parent_id, is_active in catalogs:
        if catalog_id == current_catalog_id:
            continue
        status = "🟢" if is_active else "🔴"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {name}",
                callback_data=f"catalog_move_to:{current_catalog_id}:{catalog_id}",
            )
        ])

    # Перенос в корень доступен только для подкаталога.
    if current_parent_id is not None:
        buttons.append([
            InlineKeyboardButton(
                text="📁 В корень",
                callback_data=f"catalog_move_to:{current_catalog_id}:0",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
                    style="danger",
            callback_data=f"catalog_view:{current_catalog_id}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.callback_query(F.data.startswith("catalog_move:"))
async def catalog_move(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        catalog_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный каталог.", show_alert=True)
        return

    catalog = await get_catalog(catalog_id)
    if not catalog:
        await callback.answer("Каталог не найден.", show_alert=True)
        return

    all_catalogs = await _admin_get_all_catalogs()
    descendants = await _admin_get_catalog_descendants(catalog_id)
    current_parent_id = await get_catalog_parent_id(catalog_id)
    available = [
        row for row in all_catalogs
        if row[0] != catalog_id and row[0] not in descendants
    ]

    # Не показываем текущего родителя как новое место назначения.
    available = [row for row in available if row[0] != current_parent_id]

    if not available and current_parent_id is None:
        await callback.answer("Нет доступных каталогов для переноса.", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        f"📦 <b>Перенос каталога</b>\n\n"
        f"Каталог: <b>{catalog[1]}</b>\n\n"
        "Выберите новый родительский каталог:",
        reply_markup=_catalog_move_keyboard(
            available,
            catalog_id,
            current_parent_id,
        ),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("catalog_move_to:"))
async def catalog_move_to(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    try:
        catalog_id = int(parts[1])
        parent_id = int(parts[2])
    except ValueError:
        await callback.answer("❌ Некорректный каталог.", show_alert=True)
        return

    parent_id = None if parent_id == 0 else parent_id
    ok, result = await _admin_move_catalog(catalog_id, parent_id)
    if not ok:
        await callback.answer(f"❌ {result}", show_alert=True)
        return

    await callback.answer("✅ Каталог перемещён.", show_alert=True)

    if parent_id is not None:
        # Перерисовываем экран назначения без повторного callback-вызова.
        destination = await get_catalog(parent_id)
        children = await get_catalog_children(parent_id)
        products = await get_products(parent_id)
        buttons = []
        for child_id, name, is_active in children:
            status = "🟢" if is_active else "🔴"
            buttons.append([InlineKeyboardButton(
                text=_dynamic_object_button_text("catalog", name, child_id, status),
                callback_data=f"catalog_view:{child_id}",
                icon_custom_emoji_id=_dynamic_object_button_icon("catalog", child_id, name),
            )])
        destination_parent_id = await get_catalog_parent_id(parent_id)
        buttons.extend([
            [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"catalog_edit:{parent_id}")],
            [InlineKeyboardButton(text="🔀 Переместить каталог", callback_data=f"catalog_move:{parent_id}")],
            [InlineKeyboardButton(text="➕ Добавить подкаталог", callback_data=f"catalog_add:{parent_id}")],
            [InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"product_add:{parent_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=(f"catalog_view:{destination_parent_id}" if destination_parent_id else "admin_catalogs"))],
        ])
        text = (
            f"📁 <b>{destination[1]}</b>\n\n"
            f"📂 Подкаталогов: {len(children)}\n"
            f"📦 Товаров: {len(products)}"
        )
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    else:
        catalogs = await get_catalogs()
        await callback.message.edit_text(
            "📁 <b>Управление каталогами</b>\n\nВыберите каталог или создайте новый:",
            reply_markup=catalogs_keyboard(catalogs),
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("product_move:"))
async def product_move(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        product_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный товар.", show_alert=True)
        return

    product = await get_product(product_id)
    if not product:
        await callback.answer("Товар не найден.", show_alert=True)
        return

    all_catalogs = await _admin_get_all_catalogs()
    current_catalog_id = product[1]
    available = [row for row in all_catalogs if row[0] != current_catalog_id]

    if not available:
        await callback.answer("Нет другого каталога для переноса.", show_alert=True)
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"{'🟢' if row[3] else '🔴'} {row[1]}",
            callback_data=f"product_move_to:{product_id}:{row[0]}",
        )]
        for row in available
    ]
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
                    style="danger",
            callback_data=f"product_view:{product_id}",
        )
    ])

    await callback.answer()
    move_text = (
        f"📦 <b>Перенос товара</b>\n\n"
        f"Товар: <b>{product[2]}</b>\n\n"
        "Выберите новый каталог:"
    )
    move_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(
            move_text,
            reply_markup=move_keyboard,
            parse_mode="HTML",
        )
    except Exception:
        # product_view может быть фото-сообщением — в этом случае заменяем его текстовым экраном.
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            move_text,
            reply_markup=move_keyboard,
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("product_move_to:"))
async def product_move_to(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    try:
        product_id = int(parts[1])
        catalog_id = int(parts[2])
    except ValueError:
        await callback.answer("❌ Некорректные данные.", show_alert=True)
        return

    if not await _admin_move_product(product_id, catalog_id):
        await callback.answer("❌ Не удалось переместить товар.", show_alert=True)
        return

    await callback.answer("✅ Товар перемещён.", show_alert=True)
    product = await get_product(product_id)
    if not product:
        return
    text, keyboard = await build_product_admin_view(product)
    if product[4]:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=product[4],
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("catalog_view:"))
async def catalog_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        catalog_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный каталог.", show_alert=True)
        return

    catalog = await get_catalog(catalog_id)
    if not catalog:
        await callback.answer("Каталог не найден.", show_alert=True)
        return

    children = await get_catalog_children(catalog_id)
    products = await get_products(catalog_id)
    parent_id = await get_catalog_parent_id(catalog_id)

    catalog_name_html = _render_custom_emoji_html(
        catalog[1],
        await _get_text_entities('catalogs', 'name_entities', catalog_id),
    )
    text = (
        f" <b>{catalog_name_html}</b>\n\n"
        f" Подкаталогов: {len(children)}\n"
        f" Товаров: {len(products)}\n"
    )

    if not children and not products:
        text += "\nЗдесь пока ничего нет."
    elif products:
        text += "\n <b>Товары в этом каталоге:</b>\n"
        for product in products:
            status = "🟢" if product[6] else "🔴"
            text += f"{status} <b>{product[1]}</b> — ₽ {float(product[4]):.2f} | ₮ {float(product[5]):.2f} USDT\n"

    buttons = []
    for child_id, name, is_active in children:
        status = "🟢" if is_active else "🔴"
        buttons.append([
            InlineKeyboardButton(
                text=_dynamic_object_button_text("catalog", name, child_id, status),
                callback_data=f"catalog_view:{child_id}",
                icon_custom_emoji_id=_dynamic_object_button_icon("catalog", child_id, name),
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="✏️ Переименовать",
            callback_data=f"catalog_edit:{catalog_id}",
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="🔀 Переместить каталог",
            callback_data=f"catalog_move:{catalog_id}",
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить подкаталог",
            callback_data=f"catalog_add:{catalog_id}",
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить товар",
            callback_data=f"product_add:{catalog_id}",
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
                    style="danger",
            callback_data=(f"catalog_view:{parent_id}" if parent_id else "admin_catalogs"),
        )
    ])

    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    # Фирменная картинка для каталога Roblox
    if "roblox" in str(catalog[1]).lower() and "robux" not in str(catalog[1]).lower():
        roblox_image = Path(__file__).resolve().parent / "assets" / "roblox_catalog.png"
        if roblox_image.exists():
            try:
                if callback.message.photo:
                    await callback.message.delete()
                await callback.message.answer_photo(
                    photo=FSInputFile(str(roblox_image)),
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return
            except Exception as e:
                print(f"[ROBLOX CATALOG PHOTO] {e}")

    # Фирменная картинка для подкаталога Robux
    if "robux" in str(catalog[1]).lower():
        robux_image = Path(__file__).resolve().parent / "assets" / "robux_catalog.png"
        if robux_image.exists():
            try:
                if callback.message.photo:
                    await callback.message.delete()
                await callback.message.answer_photo(
                    photo=FSInputFile(str(robux_image)),
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                return
            except Exception as e:
                print(f"[ROBUX CATALOG PHOTO] {e}")

    image_file_id = await get_catalog_image(catalog_id)
    if image_file_id:
        try:
            if callback.message.photo:
                await callback.message.edit_media(media=InputMediaPhoto(media=image_file_id, caption=text, parse_mode="HTML"), reply_markup=keyboard)
            else:
                await callback.message.delete()
                await callback.message.answer_photo(photo=image_file_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
            return
        except Exception as e:
            print(f"Ошибка показа фото каталога в админке: {e}")
    await show_text_or_photo(callback, text, keyboard)


@dp.callback_query(F.data.startswith("catalog_edit:"))
async def catalog_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    try:
        catalog_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный каталог.", show_alert=True)
        return
    catalog = await get_catalog(catalog_id)
    if not catalog:
        await callback.answer("Каталог не найден.", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "✏️ <b>Редактирование каталога</b>\n\n"
        f"📁 <b>{catalog[1]}</b>\n\nВыберите, что изменить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название", callback_data=f"catalog_edit_field:name:{catalog_id}")],
            [InlineKeyboardButton(text="💎 Premium Emoji названия", callback_data=f"catalog_edit_field:name_emoji:{catalog_id}")],
            [InlineKeyboardButton(text="🗑 Убрать Premium Emoji", callback_data=f"catalog_edit_field:name_emoji_clear:{catalog_id}")],
            [InlineKeyboardButton(text="🖼 Фото", callback_data=f"catalog_edit_field:image:{catalog_id}")],
            [InlineKeyboardButton(text="🟢/🔴 Вкл./Выкл.", callback_data=f"catalog_toggle:{catalog_id}" )],
            [InlineKeyboardButton(text="🔀 Переместить", callback_data=f"catalog_move:{catalog_id}" )],
            [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=f"catalog_view:{catalog_id}")],
        ]),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("catalog_edit_field:"))
async def catalog_edit_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Некорректное поле.", show_alert=True)
        return
    field, catalog_id_raw = parts[1], parts[2]
    try:
        catalog_id = int(catalog_id_raw)
    except ValueError:
        await callback.answer("❌ Некорректный каталог.", show_alert=True)
        return
    catalog = await get_catalog(catalog_id)
    if not catalog:
        await callback.answer("Каталог не найден.", show_alert=True)
        return
    await state.clear()
    await state.update_data(catalog_id=catalog_id)
    if field == "name":
        await state.set_state(CatalogState.waiting_edit_name)
        prompt = f"📝 Введите новое название каталога:\n\nТекущее: <b>{catalog[1]}</b>"
    elif field == "name_emoji":
        await state.set_state(CatalogState.waiting_edit_name_emoji)
        prompt = "💎 Отправьте одним сообщением Premium Emoji, который нужно добавить в начало названия каталога."
    elif field == "name_emoji_clear":
        entities_json = await _get_text_entities("catalogs", "name_entities", catalog_id)
        try:
            new_name, raw = _remove_custom_emoji_entities(catalog[1], entities_json)
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE catalogs SET name = ?, name_entities = ? WHERE id = ?", (new_name, json.dumps(raw, ensure_ascii=False) if raw else None, catalog_id))
                await db.commit()
            # Синхронизируем локальный кэш с БД, чтобы старый icon_custom_emoji_id
            # не остался в кнопках после удаления Premium Emoji.
            _refresh_name_emoji_cache_local(
                "catalog",
                int(catalog_id),
                new_name,
                json.dumps(raw, ensure_ascii=False) if raw else None,
            )
            await callback.answer("✅ Premium Emoji удалён.")
            return
        except Exception as e:
            print(f"Ошибка удаления Premium Emoji каталога: {e}")
            await callback.answer("❌ Не удалось удалить Premium Emoji.", show_alert=True)
            return
    elif field == "image":
        await state.set_state(CatalogState.waiting_edit_image)
        prompt = "🖼 Отправьте новое фото каталога или напишите <code>нет</code>, чтобы удалить фото:"
    else:
        await callback.answer("❌ Неизвестное поле.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(prompt, parse_mode="HTML")


@dp.message(CatalogState.waiting_edit_name_emoji)
async def catalog_edit_name_emoji(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    entities = message.entities or []
    custom = next((e for e in entities if getattr(e, "type", "") == "custom_emoji"), None)
    if not custom or not message.text:
        await message.answer("❌ Отправьте именно Premium Emoji одним сообщением.")
        return
    data = await state.get_data()
    catalog_id = data.get("catalog_id")
    catalog = await get_catalog(catalog_id) if catalog_id else None
    if not catalog:
        await state.clear(); await message.answer("❌ Каталог не найден."); return
    emoji_text = message.text[_u16_to_py(_utf16_boundaries(message.text), custom.offset):_u16_to_py(_utf16_boundaries(message.text), custom.offset + custom.length)]
    emoji_len = custom.length
    old_json = await _get_text_entities("catalogs", "name_entities", catalog_id)
    # Сначала физически удаляем старые Premium Emoji из имени, а уже потом
    # добавляем новый. Иначе старый символ остаётся обычным Unicode-эмодзи.
    base_name, raw = _remove_custom_emoji_entities(str(catalog[1] or ""), old_json)
    shifted = []
    for e in raw:
        e = dict(e); e["offset"] = int(e.get("offset", 0)) + emoji_len
        shifted.append(e)
    shifted.append({"type":"custom_emoji","offset":0,"length":emoji_len,"custom_emoji_id":str(getattr(custom, "custom_emoji_id", ""))})
    name = f"{emoji_text}{base_name}"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE catalogs SET name = ?, name_entities = ? WHERE id = ?", (name, json.dumps(shifted, ensure_ascii=False), catalog_id))
        await db.commit()
    _refresh_name_emoji_cache_local("catalog", int(catalog_id), name, json.dumps(shifted, ensure_ascii=False))
    await state.clear()
    await message.answer("✅ Premium Emoji добавлен в название каталога.")
    catalogs = await get_catalogs(await get_catalog_parent_id(catalog_id))
    await message.answer("📁 <b>Каталоги</b>", reply_markup=catalogs_keyboard(catalogs), parse_mode="HTML")


@dp.message(CatalogState.waiting_edit_name)
async def catalog_edit_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Название слишком короткое.")
        return

    data = await state.get_data()
    catalog_id = data.get("catalog_id")
    name = message.text.strip()
    name_entities = _custom_emoji_entities(message)

    if not catalog_id:
        await state.clear()
        await message.answer("❌ Каталог не найден.")
        return

    try:
        import aiosqlite
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE catalogs SET name = ?, name_entities = ? WHERE id = ?",
                (name, name_entities, catalog_id),
            )
            await db.commit()
    except Exception as e:
        print(f"Ошибка переименования каталога: {e}")
        await state.clear()
        await message.answer("❌ Не удалось изменить каталог.")
        return

    _refresh_name_emoji_cache_local("catalog", int(catalog_id), name, name_entities)
    await state.clear()
    await message.answer(
        f"✅ Каталог переименован в <b>{_render_custom_emoji_html(name, name_entities)}</b>.",
        parse_mode="HTML",
    )

    catalog = await get_catalog(catalog_id)
    if catalog:
        children = await get_catalog_children(catalog_id)
        products = await get_products(catalog_id)
        parent_id = await get_catalog_parent_id(catalog_id)
        text = (
            f"📁 <b>{catalog[1]}</b>\n\n"
            f"📂 Подкаталогов: {len(children)}\n"
            f"📦 Товаров: {len(products)}"
        )
        buttons = []
        for child_id, child_name, is_active in children:
            status = "🟢" if is_active else "🔴"
            buttons.append([InlineKeyboardButton(
                text=_dynamic_object_button_text("catalog", child_name, child_id, status),
                callback_data=f"catalog_view:{child_id}",
                icon_custom_emoji_id=_dynamic_object_button_icon("catalog", child_id, name),
            )])
        buttons.append([InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"catalog_edit:{catalog_id}")])
        buttons.append([InlineKeyboardButton(text="🔀 Переместить каталог", callback_data=f"catalog_move:{catalog_id}")])
        buttons.append([InlineKeyboardButton(text="➕ Добавить подкаталог", callback_data=f"catalog_add:{catalog_id}")])
        buttons.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"product_add:{catalog_id}")])
        buttons.append([InlineKeyboardButton(
            text="⬅️ Назад",
                    style="danger",
            callback_data=(f"catalog_view:{parent_id}" if parent_id else "admin_catalogs"),
        )])
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML",
        )


@dp.message(CatalogState.waiting_edit_image)
async def catalog_edit_image(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    file_id = _message_image_file_id(message)
    if file_id:
        image_file_id = file_id
    elif message.text and message.text.strip().lower() == "нет":
        image_file_id = None
    else:
        await message.answer(
            "❌ Отправьте <b>фотографию</b> (или картинку файлом) или напишите <code>нет</code>.",
            parse_mode="HTML",
        )
        return
    data = await state.get_data()
    catalog_id = data.get("catalog_id")
    if not catalog_id:
        await state.clear(); await message.answer("❌ Каталог не найден."); return
    try:
        await set_catalog_image(catalog_id, image_file_id)
    except Exception as e:
        print(f"Ошибка изменения фото каталога: {e}")
        await state.clear(); await message.answer("❌ Не удалось изменить фото каталога."); return
    await state.clear()
    await message.answer("✅ Фото каталога обновлено.")
    catalog = await get_catalog(catalog_id)
    if catalog:
        children = await get_catalog_children(catalog_id)
        products = await get_products(catalog_id)
        parent_id = await get_catalog_parent_id(catalog_id)
        text = f"📁 <b>{catalog[1]}</b>\n\n📂 Подкаталогов: {len(children)}\n📦 Товаров: {len(products)}"
        buttons = [[InlineKeyboardButton(text=f"{'🟢' if active else '🔴'} {name}", callback_data=f"catalog_view:{cid}")] for cid, name, active in children]
        buttons += [
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"catalog_edit:{catalog_id}")],
            [InlineKeyboardButton(text="🔀 Переместить каталог", callback_data=f"catalog_move:{catalog_id}")],
            [InlineKeyboardButton(text="➕ Добавить подкаталог", callback_data=f"catalog_add:{catalog_id}")],
            [InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"product_add:{catalog_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=(f"catalog_view:{parent_id}" if parent_id else "admin_catalogs"))],
        ]
        keyboard=InlineKeyboardMarkup(inline_keyboard=buttons)
        image=await get_catalog_image(catalog_id)
        if False and image:
            await message.answer_photo(photo=image, caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("catalog_toggle:"))
async def catalog_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    try:
        catalog_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный каталог.", show_alert=True)
        return
    catalog = await get_catalog(catalog_id)
    if not catalog:
        await callback.answer("Каталог не найден.", show_alert=True)
        return
    new_status = 0 if int(catalog[2] or 0) else 1
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE catalogs SET is_active = ? WHERE id = ?", (new_status, catalog_id))
        await db.commit()
    await callback.answer("✅ Статус каталога изменён.", show_alert=True)
    # Вернуться к карточке каталога, сохранив текущую структуру управления.
    catalog = await get_catalog(catalog_id)
    children = await get_catalog_children(catalog_id)
    products = await get_products(catalog_id)
    parent_id = await get_catalog_parent_id(catalog_id)
    buttons = [[InlineKeyboardButton(text=f"{'🟢' if active else '🔴'} {name}", callback_data=f"catalog_view:{cid}")] for cid, name, active in children]
    buttons += [
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"catalog_edit:{catalog_id}")],
        [InlineKeyboardButton(text="🔀 Переместить каталог", callback_data=f"catalog_move:{catalog_id}")],
        [InlineKeyboardButton(text="➕ Добавить подкаталог", callback_data=f"catalog_add:{catalog_id}")],
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"product_add:{catalog_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=(f"catalog_view:{parent_id}" if parent_id else "admin_catalogs"))],
    ]
    text = f"📁 <b>{catalog[1]}</b>\n\n📂 Подкаталогов: {len(children)}\n📦 Товаров: {len(products)}\n\nСтатус: {'🟢 Активен' if new_status else '🔴 Выключен'}"
    image = await get_catalog_image(catalog_id)
    try:
        if False and image and callback.message.photo:
            await callback.message.edit_media(media=InputMediaPhoto(media=image, caption=text, parse_mode="HTML"), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        elif False and image:
            await callback.message.delete()
            await callback.message.answer_photo(photo=image, caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        else:
            await show_text_or_photo(callback, text, InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception as e:
        print(f"[CATALOG TOGGLE] {e}")


@dp.callback_query(F.data == "catalog_delete_menu")
async def catalog_delete_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    catalogs = await get_catalogs()

    if not catalogs:
        await callback.answer(
            "Каталогов пока нет.",
            show_alert=True,
        )
        return

    buttons = []

    for catalog_id, name, is_active in catalogs:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 {name}",
                    callback_data=f"catalog_delete:{catalog_id}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                    style="danger",
                callback_data="admin_catalogs",
            )
        ]
    )

    await callback.answer()

    await callback.message.edit_text(
        "🗑 <b>Удаление каталога</b>\n\n"
        "Выберите каталог:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("catalog_delete:"))
async def catalog_delete_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    try:
        catalog_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный каталог.",
            show_alert=True,
        )
        return

    catalog = await get_catalog(catalog_id)

    if not catalog:
        await callback.answer(
            "Каталог уже удалён.",
            show_alert=True,
        )
        return

    await delete_catalog(catalog_id)

    await callback.answer(
        "Каталог удалён.",
        show_alert=True,
    )

    catalogs = await get_catalogs()

    await callback.message.edit_text(
        " <b>Управление каталогами</b>\n\n"
        "Выберите каталог или создайте новый:",
        reply_markup=catalogs_keyboard(catalogs),
        parse_mode="HTML",
    )


# ============================================================
# ТОВАРЫ
# ============================================================

@dp.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    catalogs = await get_catalogs()

    await callback.answer()

    if not catalogs:
        await callback.message.edit_text(await _get_admin_ui_text(
        "admin_products",
        _ui_text_default("admin_products"),
    ),
        reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=" Каталоги",
                            callback_data="admin_catalogs",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="⬅️ Назад",
                    style="danger",
                            callback_data="admin_back",
                        )
                    ],
                ]
            ),
            parse_mode="HTML",
        )
        return

    await callback.message.edit_text(
        " <b>Товары</b>\n\n"
        "Выберите каталог:",
        reply_markup=product_catalog_keyboard(catalogs),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("product_catalog:"))
async def product_catalog(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        catalog_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный каталог.", show_alert=True)
        return

    catalog = await get_catalog(catalog_id)
    if not catalog:
        await callback.answer("Каталог не найден.", show_alert=True)
        return

    products = await get_products(catalog_id)
    children = await get_catalog_children(catalog_id)
    parent_id = await get_catalog_parent_id(catalog_id)

    buttons = []

    child_buttons = []
    for child_id, name, is_active in children:
        status = "🟢" if is_active else "🔴"
        child_buttons.append(
            InlineKeyboardButton(
                text=_dynamic_object_button_text("catalog", name, child_id, status),
                callback_data=f"product_catalog:{child_id}",
                icon_custom_emoji_id=_dynamic_object_button_icon("catalog", child_id, name),
            )
        )

    buttons.extend(make_button_rows(child_buttons, 2))

    product_buttons = []
    for product in products:
        status = "🟢" if product[6] else "🔴"
        product_buttons.append(
            InlineKeyboardButton(
                text=_dynamic_object_button_text("product", product[1], product[0], status),
                callback_data=f"product_view:{product[0]}",
                icon_custom_emoji_id=_dynamic_object_button_icon("product", product[0], product[1]),
            )
        )

    buttons.extend(make_button_rows(product_buttons, 2))

    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить товар",
            callback_data=f"product_add:{catalog_id}",
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
                    style="danger",
            callback_data=(f"product_catalog:{parent_id}" if parent_id else "admin_products"),
        )
    ])

    await callback.answer()
    await callback.message.edit_text(
        f" <b>{catalog[1]}</b>\n\n"
        "Выберите подкаталог или товар:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


# ============================================================
# ДОБАВЛЕНИЕ ТОВАРА
# ============================================================

@dp.callback_query(F.data.startswith("product_add:"))
async def product_add(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    try:
        catalog_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный каталог.",
            show_alert=True,
        )
        return

    catalog = await get_catalog(catalog_id)

    if not catalog:
        await callback.answer(
            "Каталог не найден.",
            show_alert=True,
        )
        return

    await state.clear()

    await state.update_data(
        catalog_id=catalog_id
    )

    await state.set_state(
        ProductState.waiting_name
    )

    await callback.answer()

    await callback.message.answer(
        "➕ <b>Добавление товара</b>\n\n"
        f" Каталог: <b>{catalog[1]}</b>\n\n"
        "1️⃣ Введите название товара:",
        parse_mode="HTML",
    )


@dp.message(ProductState.waiting_name)
async def product_name(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    if not message.text:
        await message.answer(
            "❌ Введите название текстом."
        )
        return

    name = message.text.strip()
    name_entities = _custom_emoji_entities(message)

    if not name:
        await message.answer(
            "❌ Название не может быть пустым."
        )
        return

    await state.update_data(
        name=name,
        name_entities=name_entities,
    )

    await state.set_state(
        ProductState.waiting_description
    )

    await message.answer(
        "2️⃣ Введите описание товара:"
    )


@dp.message(ProductState.waiting_description)
async def product_description(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    if not message.text:
        await message.answer(
            "❌ Введите описание текстом."
        )
        return

    await state.update_data(
        description=message.text.strip(),
        description_entities=_custom_emoji_entities(message),
    )

    await state.set_state(
        ProductState.waiting_image
    )

    await message.answer(
        "3️⃣ Отправьте фотографию товара.\n\n"
        "Если фото не нужно, напишите:\n"
        "<code>нет</code>",
        parse_mode="HTML",
    )


@dp.message(ProductState.waiting_image)
async def product_image(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    file_id = _message_image_file_id(message)
    if file_id:
        await state.update_data(image_file_id=file_id)
        await message.answer("✅ Фото принято.")
    elif message.text and message.text.lower().strip() == "нет":
        await state.update_data(image_file_id=None)
    else:
        await message.answer(
            "❌ Отправьте <b>фотографию</b> (или картинку файлом) "
            "или напишите <code>нет</code>.",
            parse_mode="HTML",
        )
        return

    await state.set_state(
        ProductState.waiting_quantity
    )

    await message.answer(
        "4️⃣ Введите количество товара.\n\n"
        "Например: <code>100</code>\n"
        "ℹ️ После покупки это количество автоматически уменьшаться НЕ будет.",
        parse_mode="HTML",
    )


@dp.message(ProductState.waiting_quantity)
async def product_quantity(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    if not message.text:
        await message.answer("❌ Введите количество целым числом.")
        return

    try:
        quantity = int(message.text.strip())
        if quantity < 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Некорректное количество.\n"
            "Введите целое число от 0 и выше."
        )
        return

    await state.update_data(quantity=quantity)
    await state.set_state(ProductState.waiting_price_rub)
    await message.answer(
        "5️⃣ Введите цену в RUB.\n\n"
        "Например: <code>1499</code>",
        parse_mode="HTML",
    )


@dp.message(ProductState.waiting_price_rub)
async def product_price_rub(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    if not message.text:
        await message.answer(
            "❌ Введите цену числом."
        )
        return

    try:
        price = float(
            message.text.replace(",", ".")
        )

        if price < 0:
            raise ValueError

    except ValueError:
        await message.answer(
            "❌ Некорректная цена.\n"
            "Например: <code>1499</code>",
            parse_mode="HTML",
        )
        return

    await state.update_data(
        price_rub=price
    )

    await state.set_state(
        ProductState.waiting_price_usdt
    )

    await message.answer(
        "5️⃣ Введите цену в USDT.\n\n"
        "Например: <code>15.99</code>",
        parse_mode="HTML",
    )


@dp.message(ProductState.waiting_price_usdt)
async def product_price_usdt(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    if not message.text:
        await message.answer(
            "❌ Введите цену числом."
        )
        return

    try:
        price = float(
            message.text.replace(",", ".")
        )

        if price < 0:
            raise ValueError

    except ValueError:
        await message.answer(
            "❌ Некорректная цена.\n"
            "Например: <code>15.99</code>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()

    try:
        product_id = await create_product(
            catalog_id=data["catalog_id"],
            name=data["name"],
            description=data["description"],
            image_file_id=data.get("image_file_id"),
            price_rub=data["price_rub"],
            price_usdt=price,
            quantity=data.get("quantity", 0),
        )
    except Exception as e:
        print(f"Ошибка создания товара: {e}")

        await state.clear()

        await message.answer(
            "❌ Не удалось создать товар."
        )
        return

    await _save_custom_emoji_entities("products", "name_entities", product_id, data.get("name_entities"))
    await _save_custom_emoji_entities("products", "description_entities", product_id, data.get("description_entities"))

    await state.clear()

    await message.answer(
        "✅ <b>Товар создан!</b>\n\n"
        f"🆔 ID: <code>{product_id}</code>\n"
        f" {_render_custom_emoji_html(data['name'], data.get('name_entities'))}\n"
        f"₽ {data['price_rub']:.2f}\n"
        f"₮ {price:.2f} USDT\n"
        f"📦 Количество: <b>∞ Бесконечное</b>",
        parse_mode="HTML",
    )


# ============================================================
# ПРОСМОТР ТОВАРА В АДМИНКЕ
# ============================================================

async def build_product_admin_view(product):
    (
        product_id,
        catalog_id,
        name,
        description,
        image_file_id,
        price_rub,
        price_usdt,
        is_active,
        catalog_name,
        quantity,
    ) = product

    status = (
        "🟢 Активен"
        if is_active
        else "🔴 Выключен"
    )

    name_entities = await _get_text_entities('products', 'name_entities', product_id)
    description_entities = await _get_text_entities('products', 'description_entities', product_id)
    name_html = _render_custom_emoji_html(name, name_entities)
    description_html = _render_custom_emoji_html(description, description_entities)
    text = (
        f" <b>{name_html}</b>\n\n"
        f" {html.escape(str(catalog_name or ''))}\n"
        f"📝 {description_html}\n\n"
        f"₽ {float(price_rub):.2f}\n"
        f"₮ {float(price_usdt):.2f} USDT\n"
        f"📦 Количество: <b>∞ Бесконечное</b>\n\n" if int(quantity or 0) == 0 else f"📦 Количество: <b>{int(quantity or 0)}</b> шт.\n\n"
        f"Статус: {status}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=f"product_edit:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔀 Переместить",
                    callback_data=f"product_move:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟢/🔴 Вкл./Выкл.",
                    callback_data=f"product_toggle:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"product_delete:{product_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    style="danger",
                    callback_data=f"product_catalog:{catalog_id}",
                )
            ],
        ]
    )

    return text, keyboard


@dp.callback_query(F.data.startswith("product_view:"))
async def product_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    try:
        product_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный товар.",
            show_alert=True,
        )
        return

    product = await get_product(product_id)

    if not product:
        await callback.answer(
            "Товар не найден.",
            show_alert=True,
        )
        return

    try:
        text, keyboard = await build_product_admin_view(product)
    except Exception as e:
        print(f"Ошибка построения карточки товара {product_id}: {e}")
        # Fallback для старых/нестандартных записей БД.
        text = (
            f"📦 <b>{html.escape(str(product[2] or 'Товар'))}</b>\n\n"
            f"📁 Каталог: {html.escape(str(product[8] or ''))}\n"
            f"₽ {float(product[5] or 0):.2f}\n"
            f"₮ {float(product[6] or 0):.4f} USDT\n"
            f"📦 Количество: <b>{int(product[9] or 0)}</b> шт."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"product_edit:{product_id}"),
            InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=f"product_catalog:{product[1]}")
        ]])

    await callback.answer()

    if product[4]:
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await callback.message.delete()

                await callback.message.answer_photo(
                    photo=product[4],
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )

            return

        except Exception as e:
            print(f"Ошибка показа фото товара: {e}")

    await show_text_or_photo(
        callback,
        text,
        keyboard,
    )


@dp.callback_query(F.data.startswith("product_edit:"))
async def product_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        product_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный товар.", show_alert=True)
        return

    product = await get_product(product_id)
    if not product:
        await callback.answer("Товар не найден.", show_alert=True)
        return

    await state.clear()
    await state.update_data(product_id=product_id)
    await callback.answer()
    await callback.message.answer(
        f"✏️ <b>Редактирование товара</b>\n\n"
        f"📦 <b>{_render_custom_emoji_html(product[2], await _get_text_entities('products', 'name_entities', product_id))}</b>\n\n"
        "Выберите, что изменить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название", callback_data=f"product_edit_field:name:{product_id}")],
            [InlineKeyboardButton(text="💎 Premium Emoji названия", callback_data=f"product_edit_field:name_emoji:{product_id}")],
            [InlineKeyboardButton(text="🗑 Убрать Premium Emoji", callback_data=f"product_edit_field:name_emoji_clear:{product_id}")],
            [InlineKeyboardButton(text="📄 Описание", callback_data=f"product_edit_field:description:{product_id}")],
            [InlineKeyboardButton(text="🖼 Фото", callback_data=f"product_edit_field:image:{product_id}")],
            [InlineKeyboardButton(text="💵 Цена RUB", callback_data=f"product_edit_field:rub:{product_id}")],
            [InlineKeyboardButton(text="₮ Цена USDT", callback_data=f"product_edit_field:usdt:{product_id}")],
            [InlineKeyboardButton(text="📦 Количество", callback_data=f"product_edit_field:quantity:{product_id}")],
            [InlineKeyboardButton(text="∞ Бесконечное количество", callback_data=f"product_set_unlimited:{product_id}")],
            [InlineKeyboardButton(text="🟢/🔴 Вкл./Выкл.", callback_data=f"product_toggle:{product_id}" )],
            [InlineKeyboardButton(text="🔀 Переместить", callback_data=f"product_move:{product_id}" )],
            [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=f"product_view:{product_id}" )],
        ]),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("product_edit_field:"))
async def product_edit_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Некорректное поле.", show_alert=True)
        return

    field, product_id_raw = parts[1], parts[2]
    try:
        product_id = int(product_id_raw)
    except ValueError:
        await callback.answer("❌ Некорректный товар.", show_alert=True)
        return

    product = await get_product(product_id)
    if not product:
        await callback.answer("Товар не найден.", show_alert=True)
        return

    if field == "name_emoji_clear":
        entities_json = await _get_text_entities("products", "name_entities", product_id)
        try:
            new_name, raw = _remove_custom_emoji_entities(product[2], entities_json)
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE products SET name = ?, name_entities = ? WHERE id = ?", (new_name, json.dumps(raw, ensure_ascii=False) if raw else None, product_id))
                await db.commit()
            # Синхронизируем локальный кэш с БД.
            _refresh_name_emoji_cache_local(
                "product",
                int(product_id),
                new_name,
                json.dumps(raw, ensure_ascii=False) if raw else None,
            )
            await callback.answer("✅ Premium Emoji удалён.")
            return
        except Exception as e:
            print(f"Ошибка удаления Premium Emoji товара: {e}")
            await callback.answer("❌ Не удалось удалить Premium Emoji.", show_alert=True)
            return

    states = {
        "name": (ProductState.waiting_edit_name, "📝 Введите новое название:"),
        "name_emoji": (ProductState.waiting_edit_name_emoji, "💎 Отправьте одним сообщением Premium Emoji, который нужно добавить в начало названия товара."),
        "description": (ProductState.waiting_edit_description, "📄 Введите новое описание:"),
        "image": (ProductState.waiting_edit_image, "🖼 Отправьте новое фото или напишите <code>нет</code>, чтобы удалить фото:"),
        "rub": (ProductState.waiting_edit_price_rub, "💵 Введите новую цену в RUB:"),
        "usdt": (ProductState.waiting_edit_price_usdt, "₮ Введите новую цену в USDT:"),
        "quantity": (ProductState.waiting_edit_quantity, "📦 Введите новое количество товара (целое число от 0) или <code>∞</code> для бесконечного количества:"),
    }
    if field not in states:
        await callback.answer("❌ Неизвестное поле.", show_alert=True)
        return

    await state.clear()
    await state.update_data(product_id=product_id)
    await state.set_state(states[field][0])
    await callback.answer()
    await callback.message.answer(states[field][1], parse_mode="HTML")


async def _refresh_product_after_edit(message: Message, product_id: int):
    product = await get_product(product_id)
    if not product:
        return
    text, keyboard = await build_product_admin_view(product)
    if product[4]:
        try:
            await message.answer_photo(
                photo=product[4],
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@dp.message(ProductState.waiting_edit_name_emoji)
async def product_edit_name_emoji(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    entities = message.entities or []
    custom = next((e for e in entities if getattr(e, "type", "") == "custom_emoji"), None)
    if not custom or not message.text:
        await message.answer("❌ Отправьте именно Premium Emoji одним сообщением.")
        return
    data = await state.get_data(); product_id = data.get("product_id")
    product = await get_product(product_id) if product_id else None
    if not product:
        await state.clear(); await message.answer("❌ Товар не найден."); return
    boundaries = _utf16_boundaries(message.text)
    a = _u16_to_py(boundaries, custom.offset); b = _u16_to_py(boundaries, custom.offset + custom.length)
    emoji_text = message.text[a:b]; emoji_len = custom.length
    # Загружаем текущие сущности имени товара перед заменой Premium Emoji.
    # Раньше old_json здесь не определялся, из-за чего редактирование названия
    # падало с NameError и обработчик не сохранял Premium Emoji.
    old_json = await _get_text_entities("products", "name_entities", product_id)

    # Удаляем старые Premium Emoji физически из имени перед добавлением нового,
    # иначе старый символ остаётся обычным Unicode-эмодзи.
    base_name, raw = _remove_custom_emoji_entities(str(product[2] or ""), old_json)
    shifted=[]
    for e in raw:
        e=dict(e); e["offset"]=int(e.get("offset",0))+emoji_len; shifted.append(e)
    shifted.append({"type":"custom_emoji","offset":0,"length":emoji_len,"custom_emoji_id":str(getattr(custom,"custom_emoji_id", ""))})
    name=f"{emoji_text}{base_name}"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE products SET name = ?, name_entities = ? WHERE id = ?", (name,json.dumps(shifted,ensure_ascii=False),product_id)); await db.commit()
    _refresh_name_emoji_cache_local("product", int(product_id), name, json.dumps(shifted, ensure_ascii=False))
    await state.clear(); await message.answer("✅ Premium Emoji добавлен в название товара."); await _refresh_product_after_edit(message, product_id)


@dp.message(ProductState.waiting_edit_name)
async def product_edit_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("❌ Название слишком короткое.")
        return
    data = await state.get_data()
    product_id = data.get("product_id")
    if not product_id:
        await state.clear(); await message.answer("❌ Товар не найден."); return
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE products SET name = ?, name_entities = ? WHERE id = ?",
                (message.text.strip(), _custom_emoji_entities(message), product_id),
            )
            await db.commit()
    except Exception as e:
        print(f"Ошибка изменения названия товара: {e}")
        await state.clear(); await message.answer("❌ Не удалось изменить товар."); return
    _refresh_name_emoji_cache_local("product", int(product_id), message.text.strip(), _custom_emoji_entities(message))
    await state.clear()
    await message.answer("✅ Название товара обновлено.")
    await _refresh_product_after_edit(message, product_id)


@dp.message(ProductState.waiting_edit_description)
async def product_edit_description(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        await message.answer("❌ Введите описание текстом.")
        return
    data = await state.get_data(); product_id = data.get("product_id")
    if not product_id:
        await state.clear(); await message.answer("❌ Товар не найден."); return
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE products SET description = ?, description_entities = ? WHERE id = ?",
                (message.text.strip(), _custom_emoji_entities(message), product_id),
            )
            await db.commit()
    except Exception as e:
        print(f"Ошибка изменения описания товара: {e}")
        await state.clear(); await message.answer("❌ Не удалось изменить товар."); return
    await state.clear(); await message.answer("✅ Описание товара обновлено."); await _refresh_product_after_edit(message, product_id)


@dp.message(ProductState.waiting_edit_image)
async def product_edit_image(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    file_id = _message_image_file_id(message)
    if file_id:
        image_file_id = file_id
    elif message.text and message.text.strip().lower() == "нет":
        image_file_id = None
    else:
        await message.answer(
            "❌ Отправьте <b>фотографию</b> (или картинку файлом) или напишите <code>нет</code>.",
            parse_mode="HTML",
        )
        return
    data = await state.get_data(); product_id = data.get("product_id")
    if not product_id:
        await state.clear(); await message.answer("❌ Товар не найден."); return
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE products SET image_file_id = ? WHERE id = ?", (image_file_id, product_id))
            await db.commit()
    except Exception as e:
        print(f"Ошибка изменения фото товара: {e}")
        await state.clear(); await message.answer("❌ Не удалось изменить товар."); return
    await state.clear(); await message.answer("✅ Фото товара обновлено."); await _refresh_product_after_edit(message, product_id)


async def _save_product_price(message: Message, state: FSMContext, column: str, label: str):
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        await message.answer("❌ Введите цену числом.")
        return
    try:
        price = float(message.text.replace(",", "."))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Некорректная цена. Например: <code>1499</code>", parse_mode="HTML")
        return
    data = await state.get_data(); product_id = data.get("product_id")
    if not product_id:
        await state.clear(); await message.answer("❌ Товар не найден."); return
    try:
        import aiosqlite
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"UPDATE products SET {column} = ? WHERE id = ?", (price, product_id))
            await db.commit()
    except Exception as e:
        print(f"Ошибка изменения цены товара: {e}")
        await state.clear(); await message.answer("❌ Не удалось изменить цену."); return
    await state.clear(); await message.answer(f"✅ {label} обновлена."); await _refresh_product_after_edit(message, product_id)


@dp.message(ProductState.waiting_edit_price_rub)
async def product_edit_price_rub(message: Message, state: FSMContext):
    await _save_product_price(message, state, "price_rub", "Цена RUB")


@dp.message(ProductState.waiting_edit_price_usdt)
async def product_edit_price_usdt(message: Message, state: FSMContext):
    await _save_product_price(message, state, "price_usdt", "Цена USDT")


@dp.message(ProductState.waiting_edit_quantity)
async def product_edit_quantity(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text:
        await message.answer("❌ Введите количество числом или <code>∞</code> для бесконечного количества.", parse_mode="HTML")
        return
    raw = message.text.strip().lower()
    if raw in {"∞", "бесконечно", "бесконечное", "бесконечный", "unlimited", "infinity"}:
        quantity = 0
    else:
        try:
            quantity = int(raw)
            if quantity < 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Некорректное количество. Введите целое число от 0 и выше или <code>∞</code>.", parse_mode="HTML")
            return
    data = await state.get_data()
    product_id = data.get("product_id")
    if not product_id:
        await state.clear()
        await message.answer("❌ Товар не найден.")
        return
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE products SET quantity = ? WHERE id = ?", (quantity, product_id))
            await db.commit()
    except Exception as e:
        print(f"Ошибка изменения количества товара: {e}")
        await state.clear()
        await message.answer("❌ Не удалось изменить количество.")
        return
    await state.clear()
    await message.answer(f"✅ Количество товара обновлено: <b>{quantity}</b> шт.", parse_mode="HTML")
    await _refresh_product_after_edit(message, product_id)


@dp.callback_query(F.data.startswith("product_set_unlimited:"))
async def product_set_unlimited(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    try:
        product_id = int((callback.data or "").split(":", 1)[1])
    except (TypeError, ValueError, IndexError):
        await callback.answer("❌ Некорректный товар.", show_alert=True)
        return
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE products SET quantity = 0 WHERE id = ?", (product_id,))
            await db.commit()
        await callback.answer("∞ Количество установлено как бесконечное.")
        await _refresh_product_after_edit(callback.message, product_id)
    except Exception as e:
        print(f"Ошибка установки бесконечного количества: {e}")
        await callback.answer("❌ Не удалось изменить количество.", show_alert=True)


@dp.callback_query(F.data.startswith("product_toggle:"))
async def product_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    try:
        product_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный товар.",
            show_alert=True,
        )
        return

    product = await get_product(product_id)

    if not product:
        await callback.answer(
            "Товар не найден.",
            show_alert=True,
        )
        return

    await toggle_product(product_id)

    product = await get_product(product_id)

    if not product:
        await callback.answer(
            "Товар не найден.",
            show_alert=True,
        )
        return

    await callback.answer(
        "Статус изменён.",
        show_alert=True,
    )

    text, keyboard = await build_product_admin_view(product)

    if product[4]:
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            else:
                await callback.message.delete()

                await callback.message.answer_photo(
                    photo=product[4],
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )

            return

        except Exception:
            pass

    await show_text_or_photo(
        callback,
        text,
        keyboard,
    )


@dp.callback_query(F.data.startswith("product_delete:"))
async def product_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    try:
        product_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный товар.",
            show_alert=True,
        )
        return

    product = await get_product(product_id)

    if not product:
        await callback.answer(
            "Товар уже удалён.",
            show_alert=True,
        )
        return

    catalog_id = product[1]

    await delete_product(product_id)

    await callback.answer(
        "Товар удалён.",
        show_alert=True,
    )

    catalog = await get_catalog(catalog_id)
    products = await get_products(catalog_id)

    product_buttons = []

    for item in products:
        product_buttons.append(
            InlineKeyboardButton(
                text=f"{'🟢' if item[6] else '🔴'} {item[1]}",
                callback_data=f"product_view:{item[0]}",
            )
        )

    buttons = make_button_rows(product_buttons, 2)

    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить товар",
                callback_data=f"product_add:{catalog_id}",
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                    style="danger",
                callback_data="admin_products",
            )
        ]
    )

    catalog_name = catalog[1] if catalog else "Каталог"

    await callback.message.edit_text(
        f" <b>{catalog_name}</b>\n\n"
        " Товары:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
        parse_mode="HTML",
    )


# ============================================================
# МАГАЗИН
# ============================================================

@dp.callback_query(F.data == "shop")
async def shop_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    await callback.answer()
    await state.clear()

    catalogs = await get_catalogs()
    active_catalogs = [c for c in catalogs if c[2] == 1]

    buttons = [
        [
            InlineKeyboardButton(
                text=_button_label("⭐ Telegram Stars", "stars_start"),
                callback_data="stars_start",
            )
        ]
    ]

    catalog_buttons = [
        InlineKeyboardButton(
            text=_dynamic_object_button_text("catalog", name, catalog_id),
            style="primary",
            callback_data=f"user_catalog:{catalog_id}",
            icon_custom_emoji_id=_dynamic_object_button_icon("catalog", catalog_id, name),
        )
        for catalog_id, name, is_active in active_catalogs
    ]
    buttons.extend(make_button_rows(catalog_buttons, 2))

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
                    style="danger",
            callback_data="back_main",
        )
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = await _get_rendered_template("shop", _ui_text_default("shop"), {})

    await show_text_or_photo(callback, text, keyboard, ui_key="shop")


@dp.callback_query(F.data.startswith("user_catalog:"))
async def user_catalog(callback: CallbackQuery):
    """Open a user catalog reliably, including catalog/product buttons."""
    await callback.answer()
    try:
        catalog_id = int((callback.data or "").split(":", 1)[1])
        catalog = await get_catalog(catalog_id)
        if not catalog or catalog[2] != 1:
            await callback.answer("❌ Каталог недоступен.", show_alert=True)
            return

        children = await get_catalog_children(catalog_id)
        active_children = [c for c in children if len(c) >= 3 and c[2] == 1]
        products = await get_products(catalog_id)
        active_products = [p for p in products if len(p) >= 7 and p[6] == 1]

        buttons = []
        for child_id, name, is_active in active_children:
            child_entities = await _get_text_entities("catalogs", "name_entities", int(child_id))
            child_text, child_icon = _extract_name_custom_emoji(str(name), child_entities)
            buttons.append([InlineKeyboardButton(
                text=str(child_text),
                style="primary",
                callback_data=f"user_catalog:{child_id}",
                icon_custom_emoji_id=child_icon or _dynamic_object_button_icon("catalog", child_id, name),
            )])
        for product in active_products:
            product_entities = await _get_text_entities("products", "name_entities", int(product[0]))
            product_text, product_icon = _extract_name_custom_emoji(str(product[1]), product_entities)
            buttons.append([InlineKeyboardButton(text=str(product_text), callback_data=f"user_product:{product[0]}", icon_custom_emoji_id=product_icon or _dynamic_object_button_icon("product", product[0], product[1]))])

        parent_id = await get_catalog_parent_id(catalog_id)
        buttons.append([InlineKeyboardButton(
            text="⬅️ Назад",
            style="danger",
            callback_data=f"user_catalog:{parent_id}" if parent_id else "shop",
        )])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        catalog_entities = await _get_text_entities("catalogs", "name_entities", catalog_id)
        catalog_name_html = _render_custom_emoji_html(str(catalog[1]), catalog_entities)
        text = await _get_rendered_template(
            "catalog",
            _ui_text_default("catalog"),
            {
                "catalog_name": catalog_name_html,
                "catalog_count": len(active_children),
                "product_count": len(active_products),
            },
        )

        await show_text_or_photo(callback, text, keyboard, ui_key="catalog")

    except Exception as e:
        print(f"[USER CATALOG ERROR] {e}")
        try:
            await callback.answer("❌ Не удалось открыть каталог. Попробуйте ещё раз.", show_alert=True)
        except Exception:
            pass


# ============================================================
# TELEGRAM STARS
# ============================================================

async def _check_public_telegram_username(bot: Bot, username: str) -> bool:
    """Проверка, что публичный Telegram username реально существует.

    1) bot.get_chat(@username) — если бот может резолвить.
    2) Парсинг публичной страницы https://t.me/username:
       - несуществующий аккаунт: "If you have Telegram, you can contact..."
       - существующий: есть tgme_page_photo / tgme_page_extra / description.
    """
    clean = str(username or "").lstrip("@").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", clean):
        return False

    # 1. Bot API
    try:
        chat = await bot.get_chat(f"@{clean}")
        if chat is not None:
            return True
    except Exception as exc:
        # UsernameNotOccupied / BadRequest / etc. — идём на веб-проверку
        print(f"[STARS USERNAME CHECK] get_chat(@{clean}): {type(exc).__name__}: {exc}")

    # 2. Публичная страница t.me
    url = f"https://t.me/{clean}"
    timeout = aiohttp.ClientTimeout(total=12)
    try:
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as session:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return False
                html_text = await resp.text(errors="ignore")

        lowered = html_text.lower()

        # Явные признаки НЕсуществующего username
        not_found_markers = (
            "if you have <strong>telegram</strong>, you can contact",
            "if you have telegram, you can contact",
            "tgme_icon_user",  # дефолтная иконка «пользователь не найден»
        )
        # На несуществующих страницах обычно нет фото профиля и extra-блока
        has_not_found_text = any(m in lowered for m in not_found_markers)
        has_photo = "tgme_page_photo" in lowered or "tgme_page_photo_image" in lowered
        has_extra = "tgme_page_extra" in lowered
        has_description = "tgme_page_description" in lowered
        has_title = "tgme_page_title" in lowered

        if has_not_found_text and not has_photo and not has_extra:
            return False

        # Существующий публичный профиль / канал / группа
        if has_photo or has_extra:
            return True
        if has_title and has_description and not has_not_found_text:
            return True

        # og:type profile / telegram
        if 'property="og:type" content="profile"' in lowered:
            return True
        if "telegram:user" in lowered and has_title:
            return True

        return False
    except Exception as exc:
        print(f"[STARS USERNAME CHECK] web verify @{clean}: {exc}")
        # При сетевой ошибке не пускаем дальше — просим ввести username ещё раз
        return False


@dp.callback_query(F.data == "stars_start")
async def stars_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    text = await _get_rendered_ui_text("stars", _ui_text_default("stars"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_button_label("⭐ Купить Stars себе", "stars_buy_self"), style="primary", callback_data="stars_buy_self", icon_custom_emoji_id=_BUTTON_ICONS.get("label:stars_buy_self"))],
        [InlineKeyboardButton(text=_button_label("🎁 Купить Stars другу", "stars_buy_friend"), style="primary", callback_data="stars_buy_friend", icon_custom_emoji_id=_BUTTON_ICONS.get("label:stars_buy_friend"))],
        [InlineKeyboardButton(text=_button_label("⬅️ Назад", "back"), style="danger", callback_data="shop", icon_custom_emoji_id=_BUTTON_ICONS.get("label:back"))],
    ])

    await show_text_or_photo(callback, text, keyboard, ui_key="stars")


@dp.callback_query(F.data == "stars_buy_self")
async def stars_buy_self(callback: CallbackQuery, state: FSMContext):
    username = callback.from_user.username
    if not username:
        text = await _get_rendered_ui_text("stars_self_no_username", _ui_text_default("stars_self_no_username"), callback.from_user)
        await callback.answer("❌ Нет username", show_alert=True)
        await show_text_or_photo(callback, text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_button_label("⬅️ Назад", "back"), style="danger", callback_data="stars_start", icon_custom_emoji_id=_BUTTON_ICONS.get("label:back"))]]), ui_key="stars_self_no_username")
        return

    recipient = "@" + username
    await state.clear()
    await state.update_data(stars_recipient=recipient, stars_recipient_type="self")
    await state.set_state(StarsState.waiting_quantity)
    text = await _get_rendered_template("stars_buy_self", _ui_text_default("stars_buy_self"), {
        "recipient": html.escape(recipient), "min": STARS_MIN, "max": STARS_MAX,
    })
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_button_label("⬅️ Назад", "back"), style="danger", callback_data="stars_start", icon_custom_emoji_id=_BUTTON_ICONS.get("label:back"))]])
    await show_text_or_photo(callback, text, keyboard, ui_key="stars_buy_self")


@dp.callback_query(F.data == "stars_buy_friend")
async def stars_buy_friend(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(StarsState.waiting_friend_username)
    text = await _get_rendered_ui_text("stars_buy_friend", _ui_text_default("stars_buy_friend"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_button_label("⬅️ Назад", "back"), style="danger", callback_data="stars_start", icon_custom_emoji_id=_BUTTON_ICONS.get("label:back"))]])
    await show_text_or_photo(callback, text, keyboard, ui_key="stars_buy_friend")


@dp.message(StarsState.waiting_friend_username)
async def stars_friend_username(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    username = raw.lstrip("@").strip()
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=_button_label("⬅️ Назад", "back"),
            style="danger",
            callback_data="stars_start",
            icon_custom_emoji_id=_BUTTON_ICONS.get("label:back"),
        )
    ]])

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        invalid = await _get_rendered_ui_text(
            "stars_username_invalid",
            _ui_text_default("stars_username_invalid"),
        )
        await message.answer(
            invalid + "\n\n✏️ Введите <b>существующий</b> username ещё раз:",
            parse_mode="HTML",
            reply_markup=back_kb,
        )
        return

    recipient = "@" + username
    await message.answer("🔎 Проверяю username...")

    exists = await _check_public_telegram_username(message.bot, username)
    if not exists:
        not_found = await _get_rendered_template(
            "stars_username_not_found",
            _ui_text_default("stars_username_not_found"),
            {"recipient": html.escape(recipient)},
        )
        await message.answer(
            not_found
            + "\n\n✏️ Введите <b>действительный</b> username Telegram "
            "(например <code>@durov</code>):",
            parse_mode="HTML",
            reply_markup=back_kb,
        )
        return

    await state.update_data(stars_recipient=recipient, stars_recipient_type="friend")
    await state.set_state(StarsState.waiting_quantity)
    qty_text = await _get_rendered_template(
        "stars_quantity",
        _ui_text_default("stars_quantity"),
        {
            "recipient": html.escape(recipient),
            "min": STARS_MIN,
            "max": STARS_MAX,
        },
    )
    await message.answer(qty_text, reply_markup=back_kb, parse_mode="HTML")


@dp.message(StarsState.waiting_quantity)
async def stars_quantity(message: Message, state: FSMContext):
    if not message.text:
        await message.answer(await _get_rendered_ui_text("stars_quantity_invalid", _ui_text_default("stars_quantity_invalid"), message.from_user), parse_mode="HTML")
        return

    try:
        quantity = int(message.text.strip())
    except ValueError:
        await message.answer(await _get_rendered_template("stars_quantity_invalid", _ui_text_default("stars_quantity_invalid"), {"min": STARS_MIN, "max": STARS_MAX}), parse_mode="HTML")
        return

    if quantity < STARS_MIN or quantity > STARS_MAX:
        await message.answer(await _get_rendered_template("stars_quantity_invalid", _ui_text_default("stars_quantity_invalid"), {"min": STARS_MIN, "max": STARS_MAX}), parse_mode="HTML")
        return

    data = await state.get_data()
    recipient = data.get("stars_recipient")
    if not recipient:
        await message.answer("❌ Получатель Stars не выбран. Начните покупку заново.")
        await state.clear()
        return

    await state.update_data(stars_quantity=quantity)
    await state.set_state(StarsState.waiting_payment)

    price_rub, discount = await get_discounted_price(message.from_user.id, calculate_stars_rub(quantity))
    price_usdt, _ = await get_discounted_price(message.from_user.id, calculate_stars_usdt(quantity))
    discount_line = f"\n🎁 Скидка: <b>{discount}%</b>" if discount else ""

    payment_buttons = await stars_payment_buttons(quantity, recipient)
    rows = _chunk_buttons(payment_buttons, 2)
    if not payment_buttons:
        no_payment_notice = True
    else:
        no_payment_notice = False
    rows.append([InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="stars_start")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    text = await _get_rendered_template("stars_payment", _ui_text_default("stars_payment"), {
        "quantity": f"{quantity:,}",
        "recipient": html.escape(recipient),
        "price_rub": f"{price_rub:.2f}",
        "price_usdt": f"{price_usdt:.4f}",
        "discount": discount_line,
    })
    if no_payment_notice:
        text += "\n\n⛔ <b>Все способы оплаты временно отключены.</b>"
    await answer_text_or_photo(message, text, keyboard=keyboard, ui_key="stars_payment")


# ============================================================
# STARS RUB
# ============================================================

@dp.callback_query(F.data.startswith("stars_pay_stars_owner:"))
async def stars_pay_stars_owner(callback: CallbackQuery, state: FSMContext):
    if not await is_payment_enabled("stars_owner"):
        await callback.answer("⛔ Оплата Stars через владельца отключена администратором.", show_alert=True)
        return
    data = await state.get_data()
    recipient = data.get("stars_recipient") or "не указан"
    await state.clear()
    text = await _get_rendered_ui_text("stars_owner", _ui_text_default("stars_owner"))
    text += f"\n\n👤 Получатель Stars: <b>{html.escape(recipient)}</b>"
    quantity = (callback.data or "").split(":", 1)[1] if ":" in (callback.data or "") else ""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_button_label("⭐ Оплатить Stars", callback_data=f"stars_pay_stars_owner:{quantity}"), style="success", url="https://t.me/" + RUB_OWNER_USERNAME + "?" + urlencode({"text": STARS_OWNER_MESSAGE}), icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_stars_owner"))],
        [InlineKeyboardButton(text=_button_label("⬅️ Назад", callback_data="stars_start"), style="danger", callback_data="stars_start", icon_custom_emoji_id=_BUTTON_ICONS.get("label:back"))],
    ])
    await callback.answer()
    await show_text_or_photo(callback, text, keyboard, ui_key="stars_owner")


@dp.callback_query(F.data.startswith("stars_pay_rub_owner:"))
async def stars_pay_rub_owner(callback: CallbackQuery, state: FSMContext):
    if not await is_payment_enabled("rub_owner"):
        await callback.answer("⛔ Оплата рублями через владельца отключена администратором.", show_alert=True)
        return
    data = await state.get_data()
    recipient = data.get("stars_recipient") or "не указан"
    await state.clear()
    try:
        quantity = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректное количество Stars.", show_alert=True)
        return

    text = await _get_rendered_ui_text(
        "rub_owner",
        _ui_text_default("rub_owner"),
    )
    text += f"\n\n👤 Получатель Stars: <b>{html.escape(recipient)}</b>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=_button_label("💵 Оплатить рублями", callback_data="pay_rub_owner:button"),
            style="success",
            icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_rub_owner"),
            url="https://t.me/" + RUB_OWNER_USERNAME + "?" + urlencode({"text": RUB_OWNER_MESSAGE}),
        )],
        [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="stars_start")],
    ])
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data.startswith("stars_pay_balance:"))
async def stars_pay_balance(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parts = (callback.data or "").split(":")
    recipient = data.get("stars_recipient")
    if not recipient:
        await callback.answer("❌ Получатель Stars не указан. Начните покупку заново.", show_alert=True)
        return
    try:
        quantity = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректное количество Stars.", show_alert=True); return
    if quantity < STARS_MIN or quantity > STARS_MAX:
        await callback.answer("❌ Некорректное количество Stars.", show_alert=True); return
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    if not user:
        await callback.answer("❌ Не удалось создать пользователя.", show_alert=True); return
    original_amount = calculate_stars_rub(quantity)
    amount, discount = await get_discounted_price(callback.from_user.id, original_amount)
    balance = await get_balance_rub(callback.from_user.id)
    if balance + 1e-9 < amount:
        missing = amount - balance
        text = await _get_rendered_template("balance_payment_insufficient", _ui_text_default("balance_payment_insufficient"), {"amount": f"{amount:.2f}", "balance": f"{balance:.2f}", "missing": f"{missing:.2f}"})
        await callback.answer("❌ Недостаточно средств.", show_alert=True)
        await answer_text_or_photo(callback.message, text, ui_key="balance_payment_insufficient"); return
    try:
        order_id = await create_order(user_id=user[0], product_id=None, payment_method="BALANCE", amount=amount, stars_quantity=quantity, stars_recipient=recipient)
        if not await debit_balance_rub(callback.from_user.id, amount):
            raise RuntimeError("balance debit failed")
        await update_order_status(order_id, "paid")
        if discount:
            await consume_roulette_discount(callback.from_user.id)
    except Exception as e:
        print(f"Ошибка оплаты Stars с баланса: {e}")
        await callback.answer("❌ Не удалось провести оплату.", show_alert=True); return
    new_balance = await get_balance_rub(callback.from_user.id)
    await state.clear()
    text = await _get_rendered_template("balance_payment_success", _ui_text_default("balance_payment_success"), {"order_id": order_id, "product_name": "⭐ Telegram Stars", "amount": f"{amount:.2f}", "balance": f"{new_balance:.2f}", "details": f"👤 Получатель: <b>{html.escape(recipient)}</b>\n⭐ Количество: <b>{quantity:,}</b>"})
    await callback.answer("✅ Оплата прошла успешно!", show_alert=True)
    await callback.message.answer(text, parse_mode="HTML")


@dp.callback_query(F.data.startswith("stars_pay_rub:"))
async def stars_pay_rub(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await is_payment_enabled("rub"):
        await callback.answer("⛔ Оплата RUB отключена администратором.", show_alert=True)
        return
    data = await state.get_data()
    parts = (callback.data or "").split(":")
    # Передаём получателя прямо в callback для USDT, чтобы он не зависел
    # только от FSM-состояния после нажатия кнопки оплаты.
    recipient = data.get("stars_recipient")
    if len(parts) >= 3 and parts[2].strip():
        recipient = "@" + parts[2].lstrip("@")
    if not recipient:
        await callback.answer("❌ Получатель Stars не указан. Начните покупку заново.", show_alert=True)
        return
    await state.clear()

    try:
        quantity = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректное количество Stars.",
            show_alert=True,
        )
        return

    if quantity < STARS_MIN or quantity > STARS_MAX:
        await callback.answer(
            "❌ Некорректное количество Stars.",
            show_alert=True,
        )
        return

    await callback.answer(
        "⏳ Формируем заказ..."
    )

    user = await get_or_create_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )

    if not user:
        await callback.message.answer(
            "❌ Не удалось создать пользователя."
        )
        return

    original_amount = calculate_stars_rub(quantity)
    amount, discount = await get_discounted_price(callback.from_user.id, original_amount)

    try:
        order_id = await create_order(
            user_id=user[0],
            product_id=None,
            payment_method="RUB",
            amount=amount,
            stars_quantity=quantity,
            stars_recipient=recipient,
        )
    except Exception as e:
        print(f"Ошибка создания RUB Stars: {e}")

        await callback.message.answer(
            "❌ Не удалось создать заказ."
        )
        return

    card = await get_setting("rub_card")

    if not card:
        card = "Реквизиты пока не указаны."

    text = await _get_rendered_template("stars_order_rub", _ui_text_default("stars_order_rub"), {
        "order_id": order_id,
        "quantity": f"{quantity:,}",
        "recipient": html.escape(recipient),
        "original_amount": f"{original_amount:.2f}",
        "amount": f"{amount:.2f}",
        "discount": (f"\n🎁 Скидка рулетки: <b>{discount}%</b>\n" if discount else ""),
        "card": card,
    })

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_button_label("📸 Я оплатил — отправить чек", callback_data=f"receipt:{order_id}"),
                    style="success",
                    callback_data=f"receipt:{order_id}",
                    icon_custom_emoji_id=_BUTTON_ICONS.get(_button_key(callback_data=f"receipt:{order_id}", text="📸 Я оплатил — отправить чек")),
                )
            ],
            [
                InlineKeyboardButton(
                    text=_button_label("❌ Отменить", callback_data="back_main"),
                    style="danger",
                    callback_data="back_main",
                    icon_custom_emoji_id=_BUTTON_ICONS.get(_button_key(callback_data="back_main", text="❌ Отменить")),
                )
            ],
        ]
    )

    await show_text_or_photo(
        callback,
        text,
        keyboard,
        ui_key="stars_order_rub",
    )


# ============================================================
# STARS СБП — РУЧНАЯ ПРОВЕРКА
# ============================================================

@dp.callback_query(F.data.startswith(("stars_pay_yoomoney:", "stars_pay_sbp:")))
async def stars_pay_yoomoney(callback: CallbackQuery, state: FSMContext):
    if not await is_payment_enabled("sbp"):
        await callback.answer("⛔ Оплата через СБП отключена администратором.", show_alert=True)
        return
    data = await state.get_data()
    recipient = data.get("stars_recipient")
    if not recipient:
        await callback.answer("❌ Получатель Stars не указан. Начните покупку заново.", show_alert=True)
        return
    await state.clear()
    try:
        quantity = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректное количество Stars.", show_alert=True)
        return
    if quantity < STARS_MIN or quantity > STARS_MAX:
        await callback.answer("❌ Некорректное количество Stars.", show_alert=True)
        return
    wallet = await get_setting("yoomoney_wallet")
    if not wallet:
        await callback.answer("❌ ЮMoney пока не настроен администратором.", show_alert=True)
        return
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    if not user:
        await callback.answer("❌ Не удалось создать пользователя.", show_alert=True)
        return
    original_amount = calculate_stars_rub(quantity)
    amount, discount = await get_discounted_price(callback.from_user.id, original_amount)
    try:
        order_id = await create_order(user_id=user[0], product_id=None, payment_method="YOOMONEY", amount=amount, stars_quantity=quantity, stars_recipient=recipient)
    except Exception as e:
        print(f"Ошибка создания Stars YooMoney заказа: {e}")
        await callback.answer("❌ Не удалось создать заказ.", show_alert=True)
        return
    label = f"ORDER-{await get_order_code(order_id)}"
    pay_url = "https://yoomoney.ru/quickpay/confirm?" + urlencode({
        "receiver": wallet, "quickpay-form": "shop",
        "targets": f"Заказ #{await get_order_code(order_id)}", "paymentType": "AC",
        "sum": f"{amount:.2f}", "label": label,
    })
    text = await _get_rendered_template("stars_order_sbp", _ui_text_default("stars_order_sbp"), {
        "order_id": order_id,
        "quantity": f"{quantity:,}",
        "recipient": html.escape(recipient),
        "original_amount": f"{original_amount:.2f}",
        "amount": f"{amount:.2f}",
        "discount": (f"\n🎁 Скидка: <b>{int(discount)}%</b>" if discount else ""),
    })
    await callback.answer()
    await answer_text_or_photo(callback.message, text, keyboard=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_button_label("🏦 Оплатить СБП", callback_data="pay_yoomoney:button"), style="success", url=pay_url, icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_sbp"))],
        [InlineKeyboardButton(text=_button_label("🔎 Я оплатил", callback_data="sbp_check:button"), style="success", callback_data=f"yoomoney_check:{order_id}", icon_custom_emoji_id=_BUTTON_ICONS.get("label:sbp_check"))],
        [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
    ]), ui_key="stars_order_sbp")


@dp.callback_query(F.data.startswith("stars_pay_sbp:"))
async def stars_pay_sbp(callback: CallbackQuery, state: FSMContext):
    callback.data = "stars_pay_yoomoney:" + callback.data.split(":", 1)[1]
    return await stars_pay_yoomoney(callback, state)


# ============================================================
# STARS USDT ЧЕРЕЗ CRYPTO BOT
# ============================================================

@dp.callback_query(F.data.startswith("stars_pay_usdt:"))
async def stars_pay_usdt(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await is_payment_enabled("usdt"):
        await callback.answer("⛔ Оплата USDT отключена администратором.", show_alert=True)
        return
    data = await state.get_data()
    parts = (callback.data or "").split(":")
    # Для USDT получатель передаётся в callback, поэтому покупка не ломается,
    # даже если FSM-состояние было потеряно между экраном оплаты и нажатием кнопки.
    recipient = data.get("stars_recipient")
    if len(parts) >= 3 and parts[2].strip():
        recipient = "@" + parts[2].lstrip("@")
    if not recipient:
        await callback.answer("❌ Получатель Stars не указан. Начните покупку заново.", show_alert=True)
        return
    await state.clear()

    try:
        quantity = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректное количество Stars.",
            show_alert=True,
        )
        return

    if quantity < STARS_MIN or quantity > STARS_MAX:
        await callback.answer(
            "❌ Некорректное количество Stars.",
            show_alert=True,
        )
        return

    await callback.answer(
        "⏳ Создаём оплату..."
    )

    user = await get_or_create_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )

    if not user:
        await callback.message.answer(
            "❌ Не удалось создать пользователя."
        )
        return

    original_amount = calculate_stars_usdt(quantity)
    amount, discount = await get_discounted_price(callback.from_user.id, original_amount)

    try:
        order_id = await create_order(
            user_id=user[0],
            product_id=None,
            payment_method="USDT",
            amount=amount,
            stars_quantity=quantity,
            stars_recipient=recipient,
        )

        invoice = await create_crypto_invoice(
            amount=amount,
            order_id=order_id,
        )

    except Exception as e:
        print(f"Ошибка Crypto Pay Stars: {e}")

        await callback.message.answer(
            "❌ Не удалось создать оплату USDT.\n\n"
            "Попробуйте ещё раз."
        )
        return

    pay_url = invoice["bot_invoice_url"]

    text = await _get_rendered_template("stars_order_usdt", _ui_text_default("stars_order_usdt"), {
        "order_id": order_id,
        "quantity": f"{quantity:,}",
        "recipient": html.escape(recipient),
        "amount": f"{amount:.4f}",
        "discount": (f"\n🎁 Скидка: <b>{discount}%</b>" if discount else ""),
    })

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить USDT",
                    style="success",
                    url=pay_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Проверить оплату",
                    style="success",
                    callback_data=(
                        f"crypto_check:"
                        f"{invoice['invoice_id']}:"
                        f"{order_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    style="danger",
                    callback_data="back_main",
                )
            ],
        ]
    )

    await show_text_or_photo(
        callback,
        text,
        keyboard,
        ui_key="stars_order_usdt",
    )


# ============================================================
# ПОЛЬЗОВАТЕЛЬСКИЕ КАТАЛОГИ
# ============================================================



# ============================================================
# ПОЛЬЗОВАТЕЛЬСКИЙ ТОВАР
# ============================================================

@dp.callback_query(F.data.startswith("user_product:"))
async def user_product(callback: CallbackQuery):
    """Open a product card without losing the keyboard or image."""
    await callback.answer()
    try:
        product_id = int((callback.data or "").split(":", 1)[1])
        product = await get_product(product_id)
        if not product or len(product) < 9 or product[7] != 1:
            await callback.answer("❌ Товар недоступен.", show_alert=True)
            return

        (
            product_id, catalog_id, name, description, image_file_id,
            price_rub, price_usdt, is_active, catalog_name, *rest
        ) = product
        quantity = int(rest[0] or 0) if rest else 0

        name_entities = await _get_text_entities("products", "name_entities", product_id)
        description_entities = await _get_text_entities("products", "description_entities", product_id)
        name_html = _render_custom_emoji_html(name, name_entities)
        description_html = _render_custom_emoji_html(description, description_entities)
        catalog_entities = await _get_text_entities("catalogs", "name_entities", catalog_id)
        catalog_name_html = _render_custom_emoji_html(str(catalog_name or ""), catalog_entities)
        quantity_line = "" if quantity <= 0 else f"\n📦 Количество: <b>{quantity}</b> шт."
        text = await _get_rendered_template("product", _ui_text_default("product"), {
            "product_name": name_html, "catalog_name": catalog_name_html, "description": description_html,
            "description_html": description_html, "price_rub": f"{float(price_rub):g}",
            "price_usdt": f"{float(price_usdt):g}", "quantity": quantity, "quantity_line": quantity_line,
        })
        if quantity <= 0:
            # Remove the legacy quantity row from templates saved before the unlimited mode.
            import re as _re
            text = _re.sub(r"(?:<br\s*/?>|\n|^)[^<\n]*📦\s*Количество:[^\n<]*(?:\n|$)", "\n", text)
            text = text.replace("📦 Количество: <b>0</b> шт.", "")

        catalog_l = str(catalog_name or "").lower()
        name_l = str(name or "").lower()
        is_robux = "robux" in catalog_l or "roblox" in catalog_l or "robux" in name_l
        if is_robux:
            buy_buttons = await product_payment_buttons(product_id)
            if buy_buttons:
                keyboard_rows = _chunk_buttons(buy_buttons, 2)
            else:
                keyboard_rows = [[InlineKeyboardButton(text="⛔ Оплата временно отключена", style="danger", callback_data="payments_disabled")]]
        else:
            keyboard_rows = [[InlineKeyboardButton(text="💳 Купить", style="success", callback_data=f"buy:{product_id}")]]

        keyboard_rows.append([InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=f"user_catalog:{catalog_id}")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        if image_file_id:
            try:
                if callback.message.photo:
                    await callback.message.edit_media(
                        media=InputMediaPhoto(media=image_file_id, caption=text, parse_mode="HTML"),
                        reply_markup=keyboard,
                    )
                else:
                    sent = await callback.message.answer_photo(
                        photo=image_file_id, caption=text, reply_markup=keyboard, parse_mode="HTML"
                    )
                    try:
                        await callback.message.delete()
                    except Exception:
                        pass
                return
            except Exception as e:
                print(f"[USER PRODUCT IMAGE] {e}")

        await show_text_or_photo(callback, text, keyboard, photo=image_file_id, ui_key="product")

    except Exception as e:
        print(f"[USER PRODUCT ERROR] {e}")
        try:
            await callback.answer("❌ Не удалось открыть товар. Проверьте данные товара в админ-панели.", show_alert=True)
        except Exception:
            pass


# ============================================================
# ПОКУПКА ТОВАРА
# ============================================================

@dp.callback_query(F.data.startswith("buy:"))
async def buy_product(
    callback: CallbackQuery,
    state: FSMContext,
):
    await callback.answer()
    await state.clear()

    try:
        product_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный товар.",
            show_alert=True,
        )
        return

    product = await get_product(product_id)

    if not product or product[7] != 1:
        await callback.answer(
            "❌ Товар недоступен.",
            show_alert=True,
        )
        return

    rub_price, discount = await get_discounted_price(callback.from_user.id, float(product[5]))
    usdt_price, _ = await get_discounted_price(callback.from_user.id, float(product[6]))
    discount_line = f"\n🎁 Скидка: <b>{discount}%</b>" if discount else ""
    product_name_html = _render_custom_emoji_html(
        str(product[2] or ""),
        await _get_text_entities("products", "name_entities", product_id),
    )
    text = await _get_rendered_template("payment", _ui_text_default("payment"), {
        "product_name": product_name_html, "rub_price": f"{rub_price:g}", "usdt_price": f"{usdt_price:g}",
        "discount": discount_line,
    })

    is_robux = (
        "robux" in str(product[8]).lower()
        or "roblox" in str(product[8]).lower()
        or "robux" in str(product[2]).lower()
    )

    payment_buttons = await product_payment_buttons(product_id)
    if not payment_buttons:
        text += "\n\n⛔ <b>Все способы оплаты временно отключены.</b>"

    keyboard_rows = _chunk_buttons(payment_buttons, 2)
    keyboard_rows.append([InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=f"user_product:{product_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    await show_text_or_photo(
        callback,
        text,
        keyboard,
        ui_key="payment",
    )


# ============================================================
# СБП ОПЛАТА ТОВАРА — РУЧНАЯ ПРОВЕРКА
# ============================================================

@dp.callback_query(F.data == "payments_disabled")
async def payments_disabled(callback: CallbackQuery):
    await callback.answer("⛔ Все способы оплаты временно отключены администратором.", show_alert=True)


@dp.callback_query(F.data.startswith(("pay_sbp:", "roblox_pay_sbp:")))
async def pay_product_sbp(callback: CallbackQuery, state: FSMContext):
    callback.data = "pay_yoomoney:" + callback.data.split(":", 1)[1]
    return await pay_yoomoney_special(callback, state)


# ============================================================
# RUB ОПЛАТА ТОВАРА
# ============================================================
# RUB ОПЛАТА ТОВАРА
# ============================================================

@dp.callback_query(F.data.startswith(("pay_yoomoney:", "pay_sbp:", "roblox_pay_sbp:")))
async def pay_yoomoney_special(callback: CallbackQuery, state: FSMContext):
    if not await is_payment_enabled("sbp"):
        await callback.answer("⛔ Оплата через СБП отключена администратором.", show_alert=True)
        return
    await state.clear()
    try:
        product_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный товар.", show_alert=True)
        return
    product = await get_product(product_id)
    if not product or product[7] != 1:
        await callback.answer("❌ Товар недоступен.", show_alert=True)
        return
    wallet = await get_setting("yoomoney_wallet")
    if not wallet:
        await callback.answer("❌ ЮMoney пока не настроен администратором.", show_alert=True)
        return
    user = await get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    if not user:
        await callback.answer("❌ Не удалось создать пользователя.", show_alert=True)
        return
    original_amount = float(product[5])
    amount, discount = await get_discounted_price(callback.from_user.id, original_amount)
    base_data = {"product_id": product_id, "product_name": product[2], "payment_method": "YOOMONEY", "amount": amount, "original_amount": original_amount, "roulette_discount": discount}
    catalog_name = str(product[8]).lower() if len(product) > 8 else ""
    product_name_lower = str(product[2]).lower()
    await state.update_data(**base_data)
    await callback.answer()
    if "robux" in catalog_name or "roblox" in catalog_name or "robux" in product_name_lower:
        await state.set_state(RobloxState.waiting_nickname)
        await show_text_or_photo(callback, await _get_rendered_ui_text("roblox", _ui_text_default("roblox")), None, ui_key="roblox")
        return
    if await is_brawl_product(product):
        is_pass = is_brawl_pass_product(product)
        base_data["brawl_id_type"] = "player_id" if is_pass else "player_tag"
        await state.update_data(brawl_id_type=base_data["brawl_id_type"])
        await state.set_state(BrawlState.waiting_id)
        if is_pass:
            await callback.message.answer("🎫 <b>Brawl Pass</b>\n\nВведите ваш <b>Supercell ID</b>.\n\nПример: <code>BraveBarbarian</code>", parse_mode="HTML")
        else:
            await show_text_or_photo(callback, await _get_rendered_ui_text("brawl", _ui_text_default("brawl")), None, ui_key="brawl")
        return
    try:
        order_id = await create_order(user_id=user[0], product_id=product_id, payment_method="YOOMONEY", amount=amount, stars_quantity=None)
    except Exception as e:
        print(f"Ошибка создания YooMoney заказа: {e}")
        await callback.message.answer("❌ Не удалось создать заказ.")
        return
    label = f"ORDER-{await get_order_code(order_id)}"
    pay_url = "https://yoomoney.ru/quickpay/confirm?" + urlencode({"receiver": wallet, "quickpay-form": "shop", "targets": f"Заказ #{await get_order_code(order_id)}", "paymentType": "AC", "sum": f"{amount:.2f}", "label": label})
    payment_text = await _get_rendered_template("sbp_order", _ui_text_default("sbp_order"), {
        "order_id": order_id,
        "product_name": html.escape(str(product[2])),
        "original_amount": f"{original_amount:.2f}",
        "amount": f"{amount:.2f}",
        "discount": (f"\n🎁 Скидка рулетки: <b>{int(discount)}%</b>\n" if discount else ""),
    })
    await callback.message.answer(
        payment_text,
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_button_label("🏦 Оплатить СБП", callback_data="pay_yoomoney:button"), style="success", url=pay_url, icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_sbp"))],
            [InlineKeyboardButton(text=_button_label("🔎 Я оплатил", callback_data="sbp_check:button"), style="success", callback_data=f"yoomoney_check:{order_id}", icon_custom_emoji_id=_BUTTON_ICONS.get("label:sbp_check"))],
            [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
        ])
    )


@dp.callback_query(F.data.startswith("pay_stars_owner:"))
async def pay_product_stars_owner(callback: CallbackQuery, state: FSMContext):
    if not await is_payment_enabled("stars_owner"):
        await callback.answer("⛔ Оплата Stars через владельца отключена администратором.", show_alert=True)
        return
    await state.clear()
    try:
        product_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный товар.", show_alert=True)
        return
    text = await _get_rendered_ui_text("stars_owner", _ui_text_default("stars_owner"))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=_button_label("⭐ Оплатить Stars", callback_data=f"pay_stars_owner:{product_id}"),
            style="success",
            url="https://t.me/" + RUB_OWNER_USERNAME + "?" + urlencode({"text": STARS_OWNER_MESSAGE}),
            icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_stars_owner"),
        )],
        [InlineKeyboardButton(text=_button_label("⬅️ Назад", callback_data=f"buy:{product_id}"), style="danger", callback_data=f"buy:{product_id}", icon_custom_emoji_id=_BUTTON_ICONS.get("label:back"))],
    ])
    await callback.answer()
    await show_text_or_photo(callback, text, keyboard, ui_key="stars_owner")


@dp.callback_query(F.data.startswith("pay_rub_owner:"))
async def pay_product_rub_owner(callback: CallbackQuery, state: FSMContext):
    if not await is_payment_enabled("rub_owner"):
        await callback.answer("⛔ Оплата рублями через владельца отключена администратором.", show_alert=True)
        return
    await state.clear()
    try:
        product_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный товар.", show_alert=True)
        return

    text = await _get_rendered_ui_text(
        "rub_owner",
        _ui_text_default("rub_owner"),
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=_button_label("💵 Оплатить рублями", callback_data="stars_pay_rub_owner:button"),
            style="success",
            icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_rub_owner"),
            url="https://t.me/" + RUB_OWNER_USERNAME + "?" + urlencode({"text": RUB_OWNER_MESSAGE}),
        )],
        [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data=f"buy:{product_id}")],
    ])
    await callback.answer()
    await show_text_or_photo(callback, text, keyboard, ui_key="rub_owner")


@dp.callback_query(F.data.startswith("pay_balance:"))
async def pay_product_balance(callback: CallbackQuery, state: FSMContext):
    """Оплата товара внутренним RUB-балансом пользователя."""
    await state.clear()
    try:
        product_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный товар.", show_alert=True)
        return

    product = await get_product(product_id)
    if not product or product[7] != 1:
        await callback.answer("❌ Товар недоступен.", show_alert=True)
        return

    user = await get_or_create_user(
        callback.from_user.id, callback.from_user.username, callback.from_user.first_name
    )
    if not user:
        await callback.answer("❌ Не удалось создать пользователя.", show_alert=True)
        return

    amount, discount = await get_discounted_price(callback.from_user.id, float(product[5]))
    balance = await get_balance_rub(callback.from_user.id)
    if balance + 1e-9 < amount:
        missing = max(0.0, amount - balance)
        insufficient_text = await _get_rendered_template("balance_payment_insufficient", _ui_text_default("balance_payment_insufficient"), {"amount": f"{amount:.2f}", "balance": f"{balance:.2f}", "missing": f"{missing:.2f}"})
        await callback.answer("❌ Недостаточно средств.", show_alert=True)
        await answer_text_or_photo(callback.message, insufficient_text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_button_label("💳 Пополнить баланс", callback_data="balance_topup"), style="success", callback_data="balance_topup")],[InlineKeyboardButton(text=_button_label("⬅️ Назад", callback_data="back_main"), style="danger", callback_data="back_main")]]), ui_key="balance_payment_insufficient")
        return

    catalog_name = str(product[8]).lower() if len(product) > 8 else ""
    product_name_lower = str(product[2]).lower()
    is_robux = "robux" in catalog_name or "roblox" in catalog_name or "robux" in product_name_lower

    if is_robux:
        await state.update_data(
            product_id=product_id, product_name=product[2], payment_method="BALANCE",
            amount=amount, original_amount=float(product[5]), roulette_discount=discount,
        )
        await state.set_state(RobloxState.waiting_nickname)
        await callback.answer()
        await callback.message.answer(
            await _get_rendered_ui_text("roblox", _ui_text_default("roblox")), parse_mode="HTML"
        )
        return

    if await is_brawl_product(product):
        is_pass = is_brawl_pass_product(product)
        await state.update_data(
            product_id=product_id, product_name=product[2], payment_method="BALANCE",
            amount=amount, original_amount=float(product[5]), roulette_discount=discount,
            brawl_id_type="player_id" if is_pass else "player_tag",
        )
        await state.set_state(BrawlState.waiting_id)
        await callback.answer()
        if is_pass:
            await callback.message.answer(
                await _get_rendered_ui_text("brawl_pass", _ui_text_default("brawl_pass")), parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                await _get_rendered_ui_text("brawl", _ui_text_default("brawl")), parse_mode="HTML"
            )
        return

    # Обычный товар: списываем деньги до создания заказа. При ошибке создания
    # заказа сразу возвращаем сумму на баланс.
    if not await debit_balance_rub(callback.from_user.id, amount):
        await callback.answer("❌ Средств на балансе уже недостаточно.", show_alert=True)
        return

    try:
        order_id = await create_order(
            user_id=user[0], product_id=product_id, payment_method="BALANCE",
            amount=amount, stars_quantity=None,
        )
        await update_order_status(order_id, "paid")
        if discount:
            await consume_roulette_discount(callback.from_user.id)
    except Exception as e:
        print(f"Ошибка создания заказа с баланса: {e}")
        await credit_balance_rub(callback.from_user.id, amount)
        await callback.answer("❌ Не удалось создать заказ. Средства возвращены на баланс.", show_alert=True)
        return

    new_balance = await get_balance_rub(callback.from_user.id)
    await callback.answer("✅ Оплата прошла успешно!", show_alert=True)
    success_text = await _get_rendered_template("balance_payment_success", _ui_text_default("balance_payment_success"), {"order_id": order_id, "product_name": html.escape(str(product[2])), "amount": f"{amount:.2f}", "balance": f"{new_balance:.2f}", "details": ""})
    await answer_text_or_photo(callback.message, success_text, ui_key="balance_payment_success")


@dp.callback_query(F.data.startswith("pay_rub:"))
async def pay_product_rub(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await is_payment_enabled("rub"):
        await callback.answer("⛔ Оплата RUB отключена администратором.", show_alert=True)
        return
    await state.clear()

    try:
        product_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный товар.",
            show_alert=True,
        )
        return

    product = await get_product(product_id)

    if not product or product[7] != 1:
        await callback.answer(
            "❌ Товар недоступен.",
            show_alert=True,
        )
        return

    await callback.answer(
        "⏳ Формируем заказ..."
    )

    user = await get_or_create_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )

    if not user:
        await callback.message.answer(
            "❌ Не удалось создать пользователя."
        )
        return

    original_amount = float(product[5])
    amount, discount = await get_discounted_price(callback.from_user.id, original_amount)

    catalog_name = str(product[8]).lower() if len(product) > 8 else ""
    product_name_lower = str(product[2]).lower()
    if "robux" in catalog_name or "roblox" in catalog_name or "robux" in product_name_lower:
        await state.update_data(
            product_id=product_id,
            product_name=product[2],
            payment_method="RUB",
            amount=amount,
            original_amount=original_amount,
            roulette_discount=discount,
        )
        await state.set_state(RobloxState.waiting_nickname)
        await show_text_or_photo(callback, await _get_rendered_ui_text("roblox", _ui_text_default("roblox")), None, ui_key="roblox")
        return

    if await is_brawl_product(product):
        is_pass = is_brawl_pass_product(product)
        await state.update_data(
            product_id=product_id,
            product_name=product[2],
            payment_method="RUB",
            amount=amount,
            original_amount=original_amount,
            roulette_discount=discount,
            brawl_id_type="player_id" if is_pass else "player_tag",
        )
        await state.set_state(BrawlState.waiting_id)
        if is_pass:
            await answer_text_or_photo(
                callback.message,
                await _get_rendered_ui_text("brawl_pass", _ui_text_default("brawl_pass")),
                ui_key="brawl_pass",
            )
        else:
            await show_text_or_photo(callback, await _get_rendered_ui_text("brawl", _ui_text_default("brawl")), None, ui_key="brawl")
        return

    try:
        order_id = await create_order(
            user_id=user[0],
            product_id=product_id,
            payment_method="RUB",
            amount=amount,
            stars_quantity=None,
        )
        if discount:
            await consume_roulette_discount(callback.from_user.id)
    except Exception as e:
        print(f"Ошибка создания RUB заказа: {e}")

        await callback.message.answer(
            "❌ Не удалось создать заказ."
        )
        return

    card = await get_setting("rub_card")

    if not card:
        card = "Реквизиты пока не указаны."

    product_name_html = _render_custom_emoji_html(
        str(product[2] or ""),
        await _get_text_entities("products", "name_entities", product_id),
    )
    text = await _get_rendered_template("order_rub", _ui_text_default("order_rub"), {
        "order_id": order_id, "product_name": product_name_html, "original_amount": f"{original_amount:.2f}",
        "amount": f"{amount:.2f}", "discount": (f"\n🎁 Скидка рулетки: <b>{discount}%</b>\n" if discount else ""), "card": card,
    })

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📸 Я оплатил — отправить чек",
                    style="success",
                    callback_data=f"receipt:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    style="danger",
                    callback_data="back_main",
                )
            ],
        ]
    )

    await show_text_or_photo(
        callback,
        text,
        keyboard,
        ui_key="order_rub",
    )


# ============================================================
# USDT ОПЛАТА ТОВАРА ЧЕРЕЗ CRYPTO BOT
# ============================================================

@dp.callback_query(F.data.startswith("pay_usdt:"))
async def pay_product_usdt(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not await is_payment_enabled("usdt"):
        await callback.answer("⛔ Оплата USDT отключена администратором.", show_alert=True)
        return
    await state.clear()

    try:
        product_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный товар.",
            show_alert=True,
        )
        return

    product = await get_product(product_id)

    if not product or product[7] != 1:
        await callback.answer(
            "❌ Товар недоступен.",
            show_alert=True,
        )
        return

    await callback.answer(
        "⏳ Создаём оплату..."
    )

    user = await get_or_create_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.first_name,
    )

    if not user:
        await callback.message.answer(
            "❌ Не удалось создать пользователя."
        )
        return

    original_amount = float(product[6])
    amount, discount = await get_discounted_price(callback.from_user.id, original_amount)

    catalog_name = str(product[8]).lower() if len(product) > 8 else ""
    product_name_lower = str(product[2]).lower()
    if "robux" in catalog_name or "roblox" in catalog_name or "robux" in product_name_lower:
        await state.update_data(
            product_id=product_id,
            product_name=product[2],
            payment_method="USDT",
            amount=amount,
            roulette_discount=discount,
        )
        await state.set_state(RobloxState.waiting_nickname)
        await show_text_or_photo(callback, await _get_rendered_ui_text("roblox", _ui_text_default("roblox")), None, ui_key="roblox")
        return

    if await is_brawl_product(product):
        is_pass = is_brawl_pass_product(product)
        await state.update_data(
            product_id=product_id,
            product_name=product[2],
            payment_method="USDT",
            amount=amount,
            brawl_id_type="player_id" if is_pass else "player_tag",
        )
        await state.set_state(BrawlState.waiting_id)
        if is_pass:
            await answer_text_or_photo(
                callback.message,
                await _get_rendered_ui_text("brawl_pass", _ui_text_default("brawl_pass")),
                ui_key="brawl_pass",
            )
        else:
            await show_text_or_photo(callback, await _get_rendered_ui_text("brawl", _ui_text_default("brawl")), None, ui_key="brawl")
        return

    try:
        order_id = await create_order(
            user_id=user[0],
            product_id=product_id,
            payment_method="USDT",
            amount=amount,
            stars_quantity=None,
        )
        if discount:
            await consume_roulette_discount(callback.from_user.id)

        invoice = await create_crypto_invoice(
            amount=amount,
            order_id=order_id,
        )

    except Exception as e:
        print(f"Ошибка Crypto Pay товара: {e}")

        await callback.message.answer(
            "❌ Не удалось создать оплату USDT.\n\n"
            "Попробуйте ещё раз."
        )
        return

    pay_url = invoice["bot_invoice_url"]

    product_name_html = _render_custom_emoji_html(
        str(product[2] or ""),
        await _get_text_entities("products", "name_entities", product_id),
    )
    text = await _get_rendered_template("order_usdt", _ui_text_default("order_usdt"), {
        "order_id": order_id, "product_name": product_name_html, "amount": f"{amount:.4f}",
    })

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить USDT",
                    style="success",
                    url=pay_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Проверить оплату",
                    style="success",
                    callback_data=(
                        f"crypto_check:"
                        f"{invoice['invoice_id']}:"
                        f"{order_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    style="danger",
                    callback_data="back_main",
                )
            ],
        ]
    )

    await show_text_or_photo(
        callback,
        text,
        keyboard,
        ui_key="order_usdt",
    )


# ============================================================
# ПРОВЕРКА CRYPTO PAY
# ============================================================

@dp.callback_query(F.data.startswith("crypto_check:"))
async def crypto_check(
    callback: CallbackQuery,
    bot: Bot,
):
    try:
        _, invoice_id, order_id = callback.data.split(
            ":",
            2,
        )

        invoice_id = int(invoice_id)
        order_id = int(order_id)

    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный платёж.",
            show_alert=True,
        )
        return

    await callback.answer(
        "⏳ Проверяем оплату..."
    )

    try:
        invoice = await get_crypto_invoice(
            invoice_id
        )
    except Exception as e:
        print(f"Ошибка проверки Crypto Pay: {e}")

        await callback.message.answer(
            "❌ Не удалось проверить оплату.\n"
            "Попробуйте ещё раз."
        )
        return

    if not invoice:
        await callback.message.answer(
            "❌ Счёт не найден."
        )
        return

    if invoice["status"] != "paid":
        await callback.message.answer(
            "⏳ Оплата ещё не поступила."
        )
        return

    order = await get_order(order_id)

    if not order:
        await callback.message.answer(
            "❌ Заказ не найден."
        )
        return

    if order[5] == "paid":
        await callback.message.answer(
            "✅ Этот заказ уже оплачен."
        )
        return

    if order[5] != "waiting_payment":
        await callback.message.answer(
            "❌ Заказ находится в другом статусе."
        )
        return

    await update_order_status(
        order_id,
        "paid",
    )

    # Списываем скидку рулетки только после подтверждённой оплаты.
    if order[8] == callback.from_user.id:
        discount, _ = await get_roulette_data(callback.from_user.id)
        if discount:
            await consume_roulette_discount(callback.from_user.id)

    if order[12]:
        product_text = (
            "⭐ Telegram Stars\n"
            f"👤 Получатель: <b>{html.escape(order[14] or 'не указан')}</b>\n"
            f"⭐ Количество: <b>{order[12]:,}</b>"
        )
    else:
        product_text = (
            f"📦 {order[11]}"
        )

    user_text = (
        "✅ <b>Оплата получена!</b>\n\n"
        f"🧾 Заказ: <b>#{await get_order_code(order_id)}</b>\n"
        f"{product_text}\n"
        "💳 Оплата: <b>USDT / Crypto Bot</b>\n\n"
        "Ожидайте выдачи товара."
    )

    try:
        await bot.send_message(
            chat_id=order[8],
            text=user_text,
            parse_mode="HTML",
        )
    except Exception as e:
        print(
            f"Ошибка уведомления пользователя: {e}"
        )

    admin_text = (
        "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА</b>\n\n"
        f"🧾 Заказ: <b>#{await get_order_code(order_id)}</b>\n"
        f"{product_text}\n"
        f"💰 {float(order[4]):.4f} USDT\n"
        "💳 Crypto Bot"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Мои заказы",
                    style="success",
                    callback_data="orders",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="back_main",
                )
            ],
        ]
    )

    await show_text_or_photo(
        callback,
        admin_text,
        keyboard,
    )


# ============================================================
# RUB ЧЕК
# ============================================================

@dp.callback_query(F.data.startswith("yoomoney_check:"))
async def yoomoney_check_payment(callback: CallbackQuery, bot: Bot):
    try:
        order_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный номер заказа.", show_alert=True)
        return
    order = await get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return
    if order[8] != callback.from_user.id:
        await callback.answer("⛔ Этот заказ вам не принадлежит.", show_alert=True)
        return
    if order[3] != "YOOMONEY":
        await callback.answer("❌ Этот заказ не оплачивается через ЮMoney.", show_alert=True)
        return
    if order[5] != "waiting_payment":
        await callback.answer("ℹ️ Этот заказ уже обработан.", show_alert=True)
        return
    username = f"@{order[9]}" if order[9] else "не указан"
    product_text = f"⭐ Telegram Stars\n👤 Получатель: <b>{html.escape(order[14] or 'не указан')}</b>\n⭐ Количество: <b>{order[12]:,} Stars</b>" if order[12] else f"📦 Товар: <b>{order[11]}</b>"
    admin_text = (
        "🔔 <b>Пользователь сообщил об оплате ЮMoney</b>\n\n"
        f"🧾 Заказ: <b>#{await get_order_code(order_id)}</b>\n👤 Пользователь: {username}\n🆔 ID: <code>{order[8]}</code>\n\n"
        f"{product_text}\n💰 Сумма: <b>{float(order[4]):.2f} ₽</b>\n🏦 Оплата: <b>СБП</b>\n\n"
        "Проверьте поступление в ЮMoney и выберите действие."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve:{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{order_id}")],
    ])
    try:
        await update_order_status(order_id, "waiting_review")
        for _admin_id in ADMIN_IDS:
            try:
                await bot.send_message(_admin_id, admin_text, parse_mode="HTML", reply_markup=keyboard)
            except Exception as _admin_exc:
                print(f"Ошибка отправки уведомления админу {_admin_id}: {_admin_exc}")
    except Exception as e:
        print(f"Ошибка уведомления администратора о YooMoney: {e}")
        await callback.answer("❌ Не удалось уведомить администратора.", show_alert=True)
        return
    await callback.answer("✅ Запрос на проверку отправлен.")
    try:
        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Оплата на проверке", style="primary", callback_data=f"yoomoney_check:{order_id}")],
            [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
        ]))
    except Exception:
        pass


@dp.callback_query(F.data.startswith("sbp_check:"))
async def sbp_check_payment(callback: CallbackQuery, bot: Bot):
    """Ручная проверка СБП: уведомляет администратора без отправки чека."""
    try:
        order_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный номер заказа.", show_alert=True)
        return

    order = await get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    if order[8] != callback.from_user.id:
        await callback.answer("⛔ Этот заказ вам не принадлежит.", show_alert=True)
        return

    if order[3] != "SBP":
        await callback.answer("❌ Этот заказ не оплачивается через СБП.", show_alert=True)
        return

    if order[5] != "waiting_payment":
        await callback.answer("ℹ️ Этот заказ уже обработан.", show_alert=True)
        return

    username = f"@{order[9]}" if order[9] else "не указан"
    if order[12]:
        product_text = f"⭐ Telegram Stars\n⭐ Количество: <b>{order[12]:,}</b> Stars"
    else:
        product_text = f"📦 Товар: <b>{order[11]}</b>"

    admin_text = (
        "🔔 <b>Пользователь сообщил об оплате СБП</b>\n\n"
        f"🧾 Заказ: <b>#{await get_order_code(order_id)}</b>\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: <code>{order[8]}</code>\n\n"
        f"{product_text}\n"
        f"💰 Сумма: <b>{float(order[4]):.2f} ₽</b>\n"
        "🏦 Оплата: <b>СБП</b>\n\n"
        "Проверьте поступление в банковском приложении и выберите действие."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve:{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{order_id}")],
    ])

    try:
        for _admin_id in ADMIN_IDS:
            try:
                await bot.send_message(_admin_id, admin_text, parse_mode="HTML", reply_markup=keyboard)
            except Exception as _admin_exc:
                print(f"Ошибка отправки уведомления админу {_admin_id}: {_admin_exc}")
    except Exception as e:
        print(f"Ошибка уведомления администратора о СБП: {e}")
        await callback.answer("❌ Не удалось уведомить администратора.", show_alert=True)
        return

    # После нажатия «Проверить оплату» переводим заказ в waiting_review.
    # Именно этот статус ожидают кнопки «Подтвердить» и «Отклонить».
    # Раньше заказ оставался в waiting_payment, из-за чего админ получал
    # сообщение, но кнопки approve/reject отказывались обрабатывать заказ.
    try:
        await update_order_status(order_id, "waiting_review")
    except Exception as e:
        print(f"Ошибка смены статуса СБП-заказа #{order_id}: {e}")
        await callback.answer("⚠️ Уведомление отправлено, но статус заказа не обновился.", show_alert=True)
        return

    await callback.answer("✅ Запрос на проверку отправлен.")
    try:
        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Оплата на проверке", style="primary", callback_data=f"sbp_check:{order_id}")],
            [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
        ]))
    except Exception:
        pass


@dp.callback_query(F.data.startswith("receipt:"))
async def receipt_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()

    try:
        order_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный заказ.",
            show_alert=True,
        )
        return

    order = await get_order(order_id)

    if not order:
        await callback.answer(
            "Заказ не найден.",
            show_alert=True,
        )
        return

    if order[8] != callback.from_user.id:
        await callback.answer(
            "⛔ Этот заказ вам не принадлежит.",
            show_alert=True,
        )
        return

    if order[5] != "waiting_payment":
        await callback.answer(
            "Для этого заказа чек уже отправлен.",
            show_alert=True,
        )
        return

    await state.set_state(
        ReceiptState.waiting_receipt
    )

    await state.update_data(
        order_id=order_id
    )

    await callback.answer()

    receipt_text = await _get_rendered_ui_text(
        "receipt",
        _ui_text_default("receipt"),
    )
    # Всегда показываем публичный ID заказа, тот же самый, который был
    # показан на экране оплаты. Внутренний numeric order_id наружу не выводим.
    receipt_text = receipt_text.replace("{order_id}", await get_order_code(order_id))

    await answer_text_or_photo(
        callback.message,
        receipt_text,
        ui_key="receipt",
    )


@dp.message(ReceiptState.waiting_receipt)
async def receipt_received(
    message: Message,
    state: FSMContext,
    bot: Bot,
):
    if not message.photo:
        await message.answer(
            "❌ Пожалуйста, отправьте именно фотографию чека."
        )
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await state.clear()
        await message.answer(
            "❌ Заказ не найден."
        )
        return

    order = await get_order(order_id)

    if not order:
        await state.clear()
        await message.answer(
            "❌ Заказ не найден."
        )
        return

    if order[8] != message.from_user.id:
        await state.clear()
        await message.answer(
            "⛔ Этот заказ вам не принадлежит."
        )
        return

    if order[5] != "waiting_payment":
        await state.clear()
        await message.answer(
            "❌ Для этого заказа чек уже отправлен."
        )
        return

    receipt_file_id = message.photo[-1].file_id

    try:
        await add_receipt(
            order_id,
            receipt_file_id,
        )
    except Exception as e:
        print(f"Ошибка сохранения чека: {e}")

        await message.answer(
            "❌ Не удалось сохранить чек."
        )
        return

    await state.clear()

    username = (
        f"@{order[9]}"
        if order[9]
        else "не указан"
    )

    if order[12]:
        product_text = (
            "⭐ Telegram Stars\n"
            f"👤 Получатель: <b>{html.escape(order[14] or 'не указан')}</b>\n"
            f"⭐ Количество: <b>{order[12]:,}</b> Stars"
        )
    else:
        product_text = (
            f"📦 Товар: <b>{order[11]}</b>"
        )

    admin_text = (
        "🔔 <b>Новая оплата!</b>\n\n"
        f"🧾 Заказ: <b>#{await get_order_code(order_id)}</b>\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: <code>{order[8]}</code>\n\n"
        f"{product_text}\n"
        f"💰 Сумма: <b>{float(order[4]):.4f}</b>\n"
        f"💳 Оплата: <b>{order[3]}</b>\n\n"
        "Проверьте чек и выберите действие."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"approve:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{order_id}",
                )
            ],
        ]
    )

    try:
        for _admin_id in ADMIN_IDS:
            try:
                await bot.send_photo(
                    chat_id=_admin_id,
                    photo=receipt_file_id,
                    caption=admin_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except Exception as _admin_exc:
                print(f"Ошибка отправки чека админу {_admin_id}: {_admin_exc}")
    except Exception as e:
        print(
            f"Ошибка отправки чека админу: {e}"
        )

        await message.answer(
            "❌ Не удалось отправить чек на проверку."
        )
        return

    await message.answer(
        f"✅ Чек по заказу <b>#{order_id}</b> отправлен "
        "на проверку.\n\n"
        "Ожидайте подтверждения оплаты.",
        parse_mode="HTML",
    )


# ============================================================
# ПОДТВЕРЖДЕНИЕ RUB
# ============================================================

@dp.callback_query(F.data.startswith("approve:"))
async def approve_order(
    callback: CallbackQuery,
    bot: Bot,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    try:
        order_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный заказ.",
            show_alert=True,
        )
        return

    order = await get_order(order_id)

    if not order:
        await callback.answer(
            "Заказ не найден.",
            show_alert=True,
        )
        return

    if order[5] == "paid":
        await callback.answer(
            "Заказ уже подтверждён.",
            show_alert=True,
        )
        return

    if order[5] != "waiting_review":
        await callback.answer(
            "Этот заказ нельзя подтвердить в текущем статусе.",
            show_alert=True,
        )
        return

    await update_order_status(
        order_id,
        "paid",
    )

    if order[3] == "YOOMONEY":
        discount, _ = await get_roulette_data(order[8])
        if discount:
            await consume_roulette_discount(order[8])

    await callback.answer(
        "Оплата подтверждена.",
        show_alert=True,
    )

    if order[12]:
        product_text = (
            "⭐ Telegram Stars\n"
            f"👤 Получатель: <b>{html.escape(order[14] or 'не указан')}</b>\n"
            f"⭐ Количество: <b>{order[12]:,}</b> Stars"
        )
    else:
        product_text = (
            f"📦 {order[11]}"
        )

    try:
        await bot.send_message(
            chat_id=order[8],
            text=(
                "✅ <b>Оплата подтверждена!</b>\n\n"
                f"🧾 Заказ: <b>#{await get_order_code(order_id)}</b>\n"
                f"{product_text}\n\n"
                "Ожидайте выдачи товара."
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    admin_result = (
        "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА</b>\n\n"
        f"🧾 Заказ: #{await get_order_code(order_id)}\n"
        f"{product_text}\n"
        f"💰 {float(order[4]):.4f} {order[3]}\n\n"
        f"👤 ID: {order[8]}"
    )

    try:
        await callback.message.edit_caption(
            caption=admin_result,
            reply_markup=None,
            parse_mode="HTML",
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=admin_result,
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            pass


# ============================================================
# ОТКЛОНЕНИЕ RUB
# ============================================================

@dp.callback_query(F.data.startswith("reject:"))
async def reject_order(
    callback: CallbackQuery,
    bot: Bot,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    try:
        order_id = int(
            callback.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный заказ.",
            show_alert=True,
        )
        return

    order = await get_order(order_id)

    if not order:
        await callback.answer(
            "Заказ не найден.",
            show_alert=True,
        )
        return

    if order[5] == "rejected":
        await callback.answer(
            "Заказ уже отклонён.",
            show_alert=True,
        )
        return

    if order[5] != "waiting_review":
        await callback.answer(
            "Этот заказ нельзя отклонить в текущем статусе.",
            show_alert=True,
        )
        return

    await update_order_status(
        order_id,
        "rejected",
    )

    await callback.answer(
        "Оплата отклонена.",
        show_alert=True,
    )

    if order[12]:
        product_text = (
            "⭐ Telegram Stars\n"
            f"👤 Получатель: <b>{html.escape(order[14] or 'не указан')}</b>\n"
            f"⭐ Количество: <b>{order[12]:,}</b> Stars"
        )
    else:
        product_text = (
            f"📦 {order[11]}"
        )

    try:
        await bot.send_message(
            chat_id=order[8],
            text=(
                "❌ <b>Оплата отклонена</b>\n\n"
                f"🧾 Заказ: <b>#{await get_order_code(order_id)}</b>\n"
                f"{product_text}\n\n"
                "Пожалуйста, проверьте оплату "
                "и обратитесь в поддержку."
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    admin_result = (
        "❌ <b>ОПЛАТА ОТКЛОНЕНА</b>\n\n"
        f"🧾 Заказ: #{await get_order_code(order_id)}\n"
        f"{product_text}\n"
        f"💰 {float(order[4]):.4f} {order[3]}\n\n"
        f"👤 ID: {order[8]}"
    )

    try:
        await callback.message.edit_caption(
            caption=admin_result,
            reply_markup=None,
            parse_mode="HTML",
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=admin_result,
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            pass


# ============================================================
# МОИ ЗАКАЗЫ
# ============================================================

@dp.callback_query(F.data == "orders")
async def orders_handler(callback: CallbackQuery):
    """Показывает историю заказов пользователя.

    Важно: этот экран не должен зависеть от того, был ли пользователь
    зарегистрирован именно через /start. Если человек уже взаимодействует
    с ботом, гарантируем наличие записи в users и только после этого читаем
    заказы.
    """
    await callback.answer()

    try:
        tg_user = callback.from_user

        # Гарантируем запись пользователя в БД. Это устраняет ситуацию,
        # когда кнопка «Мои заказы» нажимается, но users ещё не содержит ID.
        await add_user(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )

        user = await get_user_by_telegram_id(tg_user.id)
        if not user:
            raise RuntimeError("Пользователь не найден после регистрации")

        orders = await get_user_orders(user[0])

        if not orders:
            orders_text = "У вас пока нет заказов."
        else:
            status_names = {
                "waiting_payment": "⏳ Ожидает оплаты",
                "waiting_review": "🔍 Проверяется",
                "paid": "✅ Оплачен",
                "rejected": "❌ Отклонён",
            }

            parts = []
            for order in orders:
                # get_user_orders:
                # id, product_name, payment_method, amount, status,
                # created_at, stars_quantity, brawl_id
                order_id = order[0]
                order_code = order[8] or str(order_id) if len(order) > 8 else str(order_id)
                product_name = order[1] or "Товар"
                payment_method = order[2] or "RUB"
                amount = order[3] or 0
                status = status_names.get(order[4], order[4] or "Неизвестно")

                if order[6]:
                    product_line = f"⭐ Telegram Stars — {int(order[6]):,} Stars"
                else:
                    product_line = str(product_name)

                # Название товара может содержать HTML/Premium Emoji. Оставляем
                # только безопасный текст здесь, чтобы один повреждённый товар
                # не ломал весь экран «Мои заказы».
                if "<tg-emoji" in product_line or "</tg-emoji>" in product_line:
                    product_line = re.sub(r"</?tg-emoji[^>]*>", "", product_line)
                product_line = html.escape(product_line)

                try:
                    amount_text = f"{float(amount):.4f}".rstrip("0").rstrip(".")
                except (TypeError, ValueError):
                    amount_text = str(amount)

                parts.append(
                    f"🧾 <b>#{await get_order_code(order_id)}</b>\n"
                    f"📦 {product_line}\n"
                    f"💰 {amount_text} {html.escape(str(payment_method))}\n"
                    f"{status}"
                )

            orders_text = "\n\n".join(parts)

        # Используем редактируемый шаблон интерфейса «Мои заказы».
        # {orders_text} вставляется уже как безопасный HTML.
        template, entities = await _get_ui_text(
            "orders",
            _ui_text_default("orders"),
        )
        if entities:
            template = _render_custom_emoji_html(template, entities)
        text = template.replace("{orders_text}", orders_text)

        await show_text_or_photo(
            callback,
            text,
            back_main_keyboard(),
            ui_key="orders",
        )

    except Exception as e:
        print(f"[ORDERS] Ошибка открытия «Мои заказы»: {e}")
        try:
            await show_text_or_photo(
                callback,
                "📦 <b>Мои заказы</b>\n\n"
                "Не удалось загрузить заказы. Попробуйте ещё раз.",
                back_main_keyboard(),
            )
        except Exception as display_error:
            print(f"[ORDERS DISPLAY] {display_error}")


# ============================================================
# АДМИН ЗАКАЗЫ
# ============================================================

@dp.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    orders = await get_orders()

    await callback.answer()

    if not orders:
        text = (
            "🧾 <b>Заказы</b>\n\n"
            "Заказов пока нет."
        )
    else:
        text = "🧾 <b>Последние заказы</b>\n\n"

        status_names = {
            "waiting_payment": "⏳ Ожидает оплаты",
            "waiting_review": "🔍 Проверяется",
            "paid": "✅ Оплачен",
            "rejected": "❌ Отклонён",
        }

        for order in orders[:20]:
            status = status_names.get(
                order[6],
                order[6],
            )

            username = (
                f"@{order[2]}"
                if order[2]
                else str(order[1])
            )

            if order[8]:
                product_name = (
                    f"⭐ Stars — {order[8]:,}"
                )
            else:
                product_name = order[3]

            text += (
                f"🧾 <b>#{order[0]}</b>\n"
                f"👤 {username}\n"
                f" {product_name}\n"
                f"💰 {float(order[5]):.4f} {order[4]}\n"
                f"{status}\n\n"
            )

    text = await _get_admin_ui_text(
        "admin_orders",
        _ui_text_default("admin_orders"),
        {"orders_text": text},
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить",
                        callback_data="admin_orders",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                    style="danger",
                        callback_data="admin_back",
                    )
                ],
            ]
        ),
        parse_mode="HTML",
    )


# ============================================================
# НАСТРОЙКИ
# ============================================================

@dp.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    card = await get_setting("rub_card") or "Не указана"
    network = await get_setting("usdt_network") or "Crypto Bot"
    wallet = await get_setting("usdt_wallet") or "Используется Crypto Bot"
    yoomoney_wallet = await get_setting("yoomoney_wallet")
    rub_enabled = await is_payment_enabled("rub")
    rub_owner_enabled = await is_payment_enabled("rub_owner")
    stars_owner_enabled = await is_payment_enabled("stars_owner")
    sbp_enabled = await is_payment_enabled("sbp")
    usdt_enabled = await is_payment_enabled("usdt")
    yoomoney_status = "Настроен ✅" if yoomoney_wallet else "Не настроен ❌"

    await callback.answer()
    await callback.message.edit_text(await _get_admin_ui_text(
        "admin_settings",
        _ui_text_default("admin_settings") + "\n\n💳 <b>СПОСОБЫ ОПЛАТЫ</b>\n₽ RUB / Карта: <b>{rub}</b>\n💵 RUB через владельца: <b>{rub_owner}</b>\n⭐ Stars через владельца: <b>{stars_owner}</b>\n🏦 СБП: <b>{sbp}</b>\n₮ USDT: <b>{usdt}</b>\n\n💳 <b>RUB</b>\nКарта: <code>{card}</code>\n\n🏦 <b>СБП</b>\nОплата через ЮMoney: {yoomoney_status}\n\n₮ <b>USDT</b>\nОплата: <b>Telegram Crypto Bot</b>\nСеть: <code>{network}</code>\nКошелёк: <code>{wallet}</code>",
        {
            "rub": _payment_status(rub_enabled),
            "rub_owner": _payment_status(rub_owner_enabled),
            "stars_owner": _payment_status(stars_owner_enabled),
            "sbp": _payment_status(sbp_enabled),
            "usdt": _payment_status(usdt_enabled),
            "card": html.escape(card),
            "yoomoney_status": yoomoney_status,
            "network": html.escape(network),
            "wallet": html.escape(wallet),
        },
    ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"₽ RUB / Карта — {_payment_status(rub_enabled)}", callback_data="payment_toggle:rub")],
            [InlineKeyboardButton(text=f"💵 RUB через владельца — {_payment_status(rub_owner_enabled)}", callback_data="payment_toggle:rub_owner")],
            [InlineKeyboardButton(text=f"⭐ Stars через владельца — {_payment_status(stars_owner_enabled)}", callback_data="payment_toggle:stars_owner")],
            [InlineKeyboardButton(text=f"🏦 СБП — {_payment_status(sbp_enabled)}", callback_data="payment_toggle:sbp")],
            [InlineKeyboardButton(text=f"₮ USDT — {_payment_status(usdt_enabled)}", callback_data="payment_toggle:usdt")],
            [InlineKeyboardButton(text="🔴 Отключить все оплаты", style="danger", callback_data="payment_toggle_all:off")],
            [InlineKeyboardButton(text="🟢 Включить все оплаты", style="success", callback_data="payment_toggle_all:on")],
            [InlineKeyboardButton(text="💳 Изменить RUB", callback_data="settings_rub")],
            [InlineKeyboardButton(text="🏦 Настроить СБП", callback_data="settings_yoomoney")],
            [InlineKeyboardButton(text="₮ USDT", style="primary", callback_data="settings_usdt")],
            [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="admin_back")],
        ]),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("payment_toggle:"))
async def payment_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    method = (callback.data or "").split(":", 1)[1].strip().lower()
    if method not in {"rub", "rub_owner", "stars_owner", "sbp", "usdt"}:
        await callback.answer("❌ Неизвестный способ оплаты", show_alert=True)
        return
    enabled = await is_payment_enabled(method)
    await set_setting(f"payment_{method}_enabled", "0" if enabled else "1")
    await admin_settings(callback)


@dp.callback_query(F.data.startswith("payment_toggle_all:"))
async def payment_toggle_all(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    action = (callback.data or "").split(":", 1)[1].strip().lower()
    if action not in {"on", "off"}:
        await callback.answer("❌ Некорректная команда", show_alert=True)
        return
    value = "1" if action == "on" else "0"
    for method in ("rub", "rub_owner", "stars_owner", "sbp", "usdt"):
        await set_setting(f"payment_{method}_enabled", value)
    await admin_settings(callback)


@dp.callback_query(F.data == "settings_rub")
async def settings_rub(
    callback: CallbackQuery,
    state: FSMContext,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    await state.clear()

    await state.set_state(
        PaymentSettingsState.waiting_rub_card
    )

    await callback.answer()

    await callback.message.answer(
        "💳 Введите новый номер карты RUB:"
    )


@dp.message(PaymentSettingsState.waiting_rub_card)
async def settings_rub_save(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    if not message.text:
        await message.answer(
            "❌ Введите реквизиты текстом."
        )
        return

    await set_setting(
        "rub_card",
        message.text.strip(),
    )

    await state.clear()

    await message.answer(
        "✅ Реквизиты RUB обновлены."
    )


@dp.callback_query(F.data == "settings_sbp_link")
async def settings_sbp_link(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await state.set_state(PaymentSettingsState.waiting_sbp_link)
    await callback.answer()
    await callback.message.answer(
        "🏦 <b>Настройка СБП</b>\n\n"
        "Отправьте <b>ссылку на страницу оплаты/перевода СБП</b> одним сообщением.\n\n"
        "После сохранения во всех товарах кнопка СБП будет открывать эту ссылку.\n"
        "Например: ссылка из вашего банка или платёжного сервиса, ведущая на перевод на ваш счёт.",
        parse_mode="HTML",
    )


@dp.message(PaymentSettingsState.waiting_sbp_link)
async def settings_sbp_link_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    link = (message.text or "").strip()
    if not re.match(r"^https?://\S+$", link):
        await message.answer("❌ Отправьте корректную ссылку, начинающуюся с http:// или https://")
        return
    await set_setting("sbp_payment_url", link)
    await state.clear()
    await message.answer("✅ Ссылка СБП сохранена. Теперь она используется для оплаты во всех товарах, включая товары, созданные через админ-панель.")


@dp.callback_query(F.data == "settings_yoomoney")
async def settings_yoomoney(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await state.set_state(PaymentSettingsState.waiting_yoomoney_wallet)
    await callback.answer()
    await callback.message.answer(
        "🏦 <b>Настройка СБП</b>\n\n"
        "Отправьте номер вашего кошелька ЮMoney, например:\n<code>41001XXXXXXXXXXXX</code>\n\n"
        "После сохранения бот будет автоматически создавать отдельную ссылку ЮMoney с точной суммой и номером заказа для каждого товара.",
        parse_mode="HTML",
    )


@dp.message(PaymentSettingsState.waiting_yoomoney_wallet)
async def settings_yoomoney_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    wallet = (message.text or "").strip()
    if not re.fullmatch(r"\d{10,25}", wallet):
        await message.answer("❌ Неверный номер кошелька ЮMoney. Отправьте только цифры.")
        return
    await set_setting("yoomoney_wallet", wallet)
    await state.clear()
    await message.answer("✅ Кошелёк ЮMoney сохранён. Теперь для каждого заказа будет формироваться отдельная ссылка с точной суммой.")


@dp.callback_query(F.data == "settings_usdt")
async def settings_usdt(
    callback: CallbackQuery,
):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    await callback.answer()

    await callback.message.answer(
        "₮ <b>USDT</b>\n\n"
        "Оплата работает автоматически через "
        "<b>Telegram Crypto Bot</b>.\n\n"
        "Для работы необходимо указать "
        "<code>CRYPTO_PAY_TOKEN</code> в config.py.",
        parse_mode="HTML",
    )


@dp.message(PaymentSettingsState.waiting_usdt_network)
async def settings_usdt_network(
    message: Message,
    state: FSMContext,
):
    await state.clear()


@dp.message(PaymentSettingsState.waiting_usdt_wallet)
async def settings_usdt_wallet(
    message: Message,
    state: FSMContext,
):
    await state.clear()



# ============================================================
# РАССЫЛКА
# ============================================================

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    await callback.answer()
    await state.clear()
    await state.set_state(BroadcastState.waiting_message)

    broadcast_text = await _get_admin_ui_text(
        "admin_broadcast",
        _ui_text_default("admin_broadcast") + "\n\nПоддерживаются текст, фото, видео, документы и другие сообщения Telegram.\n\n❌ Для отмены отправьте: <code>отмена</code>",
    )
    await callback.message.answer(
        broadcast_text,
        parse_mode="HTML",
    )


@dp.message(BroadcastState.waiting_message)
async def broadcast_preview(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip().lower() == "отмена":
        await state.clear()
        await message.answer(
            "❌ Рассылка отменена."
        )
        return

    await state.update_data(
        broadcast_chat_id=message.chat.id,
        broadcast_message_id=message.message_id,
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟢 Отправить всем",
                    callback_data="broadcast_confirm",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    style="danger",
                    callback_data="broadcast_cancel",
                ),
            ],
        ]
    )

    await message.answer(
        "📢 <b>Предпросмотр рассылки</b>\n\n"
        "Сообщение выше будет отправлено пользователям.\n\n"
        "Подтвердить отправку?",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    await state.clear()
    await callback.answer("Рассылка отменена.")
    await callback.message.edit_text(
        "❌ <b>Рассылка отменена.</b>",
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    data = await state.get_data()
    source_chat_id = data.get("broadcast_chat_id")
    source_message_id = data.get("broadcast_message_id")

    if not source_chat_id or not source_message_id:
        await state.clear()
        await callback.answer(
            "❌ Сообщение для рассылки не найдено.",
            show_alert=True,
        )
        return

    await callback.answer()
    await callback.message.edit_text(
        "📢 <b>Рассылка выполняется...</b>\n\n"
        "Пожалуйста, подождите.",
        parse_mode="HTML",
    )

    # Получаем пользователей напрямую через базу данных.
    try:
        # DB_NAME уже используется проектом через config/database.
        # Если в проекте есть готовая функция получения пользователей,
        # используем её; иначе читаем таблицу users через DB_NAME.
        try:
            from config import DB_NAME
        except ImportError:
            DB_NAME = None

        if not DB_NAME:
            # Попытка получить путь из database-модуля.
            import database
            DB_NAME = getattr(database, "DB_NAME", None)

        if not DB_NAME:
            raise RuntimeError("Не удалось определить DB_NAME.")

        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(
                "SELECT telegram_id FROM users"
            )
            rows = await cursor.fetchall()

        sent = 0
        failed = 0

        for row in rows:
            telegram_id = row[0]
            try:
                await callback.bot.copy_message(
                    chat_id=telegram_id,
                    from_chat_id=source_chat_id,
                    message_id=source_message_id,
                )
                sent += 1
            except Exception as e:
                failed += 1
                print(
                    f"[BROADCAST] Не удалось отправить "
                    f"{telegram_id}: {e}"
                )

        await state.clear()

        await callback.message.edit_text(
            "✅ <b>Рассылка завершена!</b>\n\n"
            f"📨 Отправлено: <b>{sent}</b>\n"
            f"❌ Не доставлено: <b>{failed}</b>",
            parse_mode="HTML",
        )

    except Exception as e:
        await state.clear()
        print(f"[BROADCAST ERROR] {e}")

        await callback.message.edit_text(
            "❌ <b>Не удалось выполнить рассылку.</b>\n\n"
            f"<code>{e}</code>",
            parse_mode="HTML",
        )


# ============================================================
# СТАТИСТИКА
# ============================================================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа",
            show_alert=True,
        )
        return

    total_users, total_starts, today_users, today_starts = (
        await get_bot_stats()
    )

    orders = await get_orders()

    total_orders = len(orders)

    paid = sum(
        1
        for order in orders
        if order[6] == "paid"
    )

    waiting = sum(
        1
        for order in orders
        if order[6] == "waiting_review"
    )

    rejected = sum(
        1
        for order in orders
        if order[6] == "rejected"
    )

    await callback.answer()

    stats_text = await _get_admin_ui_text(
        "admin_stats",
        _ui_text_default("admin_stats"),
        {"stats_text": (
            "📊 <b>Статистика магазина</b>\n\n"
            "👥 <b>Пользователи</b>\n"
            f"👤 Всего в боте: <b>{total_users}</b>\n"
            f"🚀 Всего нажатий /start: <b>{total_starts}</b>\n\n"
            "📅 <b>За сегодня</b>\n"
            f"👤 Всего в боте за день: <b>{today_users}</b>\n"
            f"🚀 Нажали /start за день: <b>{today_starts}</b>\n\n"
            "🧾 <b>Заказы</b>\n"
            f"🧾 Всего заказов: <b>{total_orders}</b>\n"
            f"⏳ На проверке: <b>{waiting}</b>\n"
            f"✅ Оплачено: <b>{paid}</b>\n"
            f"❌ Отклонено: <b>{rejected}</b>"
        )},
    )
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
                [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="admin_back")],
            ]
        ),
        parse_mode="HTML",
    )


# ============================================================
# ПРОФИЛЬ
# ============================================================


@dp.callback_query(F.data == "profile")
async def profile_handler(
    callback: CallbackQuery,
):
    await callback.answer()

    user = callback.from_user
    balance = await get_balance_rub(user.id)
    profile_text = await _get_rendered_template(
        "profile",
        _ui_text_default("profile"),
        {
            "user_id": user.id,
            "username": html.escape(f"@{user.username}" if user.username else "не указан"),
            "first_name": html.escape(user.first_name or "не указано"),
            "shop_name": html.escape(SHOP_NAME),
            "balance": f"{balance:.2f}",
        },
    )
    if "Баланс:" not in profile_text:
        profile_text += f"\n\n💰 Баланс: <b>{balance:.2f} ₽</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_button_label("💳 Пополнить баланс", callback_data="balance_topup"), style="success", callback_data="balance_topup", icon_custom_emoji_id=_BUTTON_ICONS.get("label:balance_topup"))],
        [InlineKeyboardButton(text="🤝 Рефералка", callback_data="referral_menu")],
        [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="back_main")],
    ])
    await show_text_or_photo(callback, profile_text, kb, ui_key="profile")


@dp.callback_query(F.data == "balance_topup")
async def balance_topup_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    text = await _get_rendered_ui_text("balance_topup", _ui_text_default("balance_topup"))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_button_label("🇷🇺 Рубли на карту", callback_data="topup_card"), style="success", callback_data="topup_card", icon_custom_emoji_id=_BUTTON_ICONS.get("label:topup_card"))],
        [InlineKeyboardButton(text=_button_label("💵 USDT • Crypto Pay", callback_data="topup_crypto:USDT"), style="success", callback_data="topup_crypto:USDT", icon_custom_emoji_id=_BUTTON_ICONS.get("label:topup_usdt"))],
        [InlineKeyboardButton(text=_button_label("💎 TON • Crypto Pay", callback_data="topup_crypto:TON"), style="success", callback_data="topup_crypto:TON", icon_custom_emoji_id=_BUTTON_ICONS.get("label:topup_ton"))],
        [InlineKeyboardButton(text=_button_label("⬅️ Профиль", callback_data="profile"), style="danger", callback_data="profile")],
    ])
    await show_text_or_photo(callback, text, kb, ui_key="balance_topup")


@dp.callback_query(F.data == "topup_card")
async def topup_card_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(TopupState.waiting_amount)
    await state.update_data(topup_method="CARD")
    text = await _get_rendered_ui_text("topup_card", _ui_text_default("topup_card"))
    await show_text_or_photo(
        callback, text,
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_button_label("⬅️ Назад", callback_data="balance_topup"), style="danger", callback_data="balance_topup")]
        ]),
        ui_key="topup_card",
    )


@dp.callback_query(F.data.startswith("topup_crypto:"))
async def topup_crypto_start(callback: CallbackQuery, state: FSMContext):
    asset = (callback.data or "").split(":", 1)[1].upper()
    if asset not in {"USDT", "TON"}:
        await callback.answer("❌ Неизвестная валюта.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(TopupState.waiting_amount)
    await state.update_data(topup_method=asset)
    text = (await _get_rendered_ui_text("topup_crypto", _ui_text_default("topup_crypto"))).replace("{asset}", html.escape(asset))
    await show_text_or_photo(
        callback, text,
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_button_label("⬅️ Назад", callback_data="balance_topup"), style="danger", callback_data="balance_topup")]
        ]),
        ui_key="topup_crypto",
    )


@dp.message(TopupState.waiting_amount)
async def topup_amount_received(message: Message, state: FSMContext):
    raw = (message.text or "").replace(",", ".").strip()
    try:
        amount = float(raw)
    except ValueError:
        await message.answer("❌ Введите сумму числом, например <code>1000</code>.", parse_mode="HTML")
        return
    if amount < 10 or amount > 500000:
        await message.answer("❌ Сумма должна быть от 10 до 500 000 ₽.")
        return

    data = await state.get_data()
    method = data.get("topup_method", "CARD")
    await state.clear()
    telegram_id = message.from_user.id

    if method == "CARD":
        topup_id = await create_topup(telegram_id, amount, "CARD")
        card = await get_setting("rub_card") or "Реквизиты пока не указаны."
        await state.set_state(TopupState.waiting_card_receipt)
        await state.update_data(topup_id=topup_id)
        topup_text = await _get_rendered_template("topup_card_payment", _ui_text_default("topup_card_payment"), {
            "topup_id": topup_id, "amount": f"{amount:.2f}", "card": str(card),
        })
        await answer_text_or_photo(
            message, topup_text,
            keyboard=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_button_label("📸 Я оплатил", callback_data=f"topup_card_paid:{topup_id}"), style="success", callback_data=f"topup_card_paid:{topup_id}", icon_custom_emoji_id=_BUTTON_ICONS.get("label:topup_paid"))],
                [InlineKeyboardButton(text=_button_label("❌ Отмена", callback_data="profile"), style="danger", callback_data="profile")],
            ]),
            ui_key="topup_card_payment",
        )
        return

    topup_id = await create_topup(telegram_id, amount, method)
    try:
        invoice = await create_crypto_topup_invoice(amount, telegram_id, topup_id, method)

        # Crypto Pay создаёт счёт в RUB и уже при оплате пересчитывает его
        # в выбранную криптовалюту. Показываем пользователю ориентировочную
        # сумму в криптовалюте по актуальному курсу Crypto Pay на момент создания счёта.
        rate = await get_crypto_rub_rate(method)
        crypto_amount = amount / rate
        decimals = 6 if method in {"USDT", "TON"} else 4

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE balance_topups SET invoice_id = ? WHERE id = ?", (invoice["invoice_id"], topup_id))
            await db.commit()

        crypto_text = await _get_rendered_template("topup_crypto_payment", _ui_text_default("topup_crypto_payment"), {
            "topup_id": topup_id, "amount": f"{amount:.2f}", "crypto_amount": f"{crypto_amount:.{decimals}f}",
            "asset": method, "rate": f"{rate:.2f}",
        })
        await answer_text_or_photo(
            message, crypto_text,
            keyboard=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_button_label(f"💳 Оплатить {method}", callback_data="topup_pay:button"), style="success", url=invoice["bot_invoice_url"], icon_custom_emoji_id=_BUTTON_ICONS.get("label:topup_pay"))],
                [InlineKeyboardButton(text=_button_label("🔄 Проверить оплату", callback_data=f"topup_crypto_check:{invoice['invoice_id']}:{topup_id}"), style="success", callback_data=f"topup_crypto_check:{invoice['invoice_id']}:{topup_id}", icon_custom_emoji_id=_BUTTON_ICONS.get("label:topup_check"))],
                [InlineKeyboardButton(text=_button_label("⬅️ Профиль", callback_data="profile"), style="danger", callback_data="profile")],
            ]),
            ui_key="topup_crypto_payment",
        )
    except Exception as e:
        print(f"Ошибка создания пополнения {method}: {e}")
        await finish_topup(topup_id, "rejected")
        await message.answer("❌ Не удалось создать Crypto Pay счёт. Попробуйте ещё раз.")


@dp.callback_query(F.data.startswith("topup_card_paid:"))
async def topup_card_paid(callback: CallbackQuery, state: FSMContext):
    try:
        topup_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректное пополнение.", show_alert=True)
        return
    topup = await get_topup(topup_id)
    if not topup or topup[1] != callback.from_user.id or topup[4] != "pending":
        await callback.answer("❌ Пополнение не найдено или уже обработано.", show_alert=True)
        return
    await state.set_state(TopupState.waiting_card_receipt)
    await state.update_data(topup_id=topup_id)
    await callback.answer()
    await callback.message.answer("📸 Отправьте фотографию чека одним сообщением.")


@dp.message(TopupState.waiting_card_receipt, F.photo)
async def topup_card_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    topup_id = data.get("topup_id")
    if not topup_id:
        await state.clear()
        await message.answer("❌ Пополнение не найдено.")
        return
    topup = await get_topup(int(topup_id))
    if not topup or topup[1] != message.from_user.id:
        await state.clear()
        await message.answer("❌ Пополнение не найдено.")
        return
    file_id = message.photo[-1].file_id
    await set_topup_receipt(int(topup_id), file_id)
    await state.clear()
    receipt_text = await _get_rendered_template("topup_receipt_sent", _ui_text_default("topup_receipt_sent"), {"topup_id": topup_id, "amount": f"{float(topup[2]):.2f}"})
    await answer_text_or_photo(message, receipt_text, ui_key="topup_receipt_sent")
    admin_text = (
        "💳 <b>НОВОЕ ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
        f"🧾 Заявка: <b>#{await get_topup_code(topup_id)}</b>\n"
        f"💰 Сумма: <b>{float(topup[2]):.2f} ₽</b>\n"
        f"👤 ID: <code>{message.from_user.id}</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Зачислить", style="success", callback_data=f"topup_approve:{topup_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", style="danger", callback_data=f"topup_reject:{topup_id}")],
    ])
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_photo(admin_id, file_id, caption=admin_text, parse_mode="HTML", reply_markup=kb)
        except Exception as e:
            print(f"Ошибка уведомления админа о пополнении: {e}")


@dp.callback_query(F.data.startswith("topup_approve:"))
async def topup_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    topup_id = int((callback.data or "").split(":", 1)[1])
    topup = await get_topup(topup_id)
    if not topup or topup[4] != "waiting_review":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return
    await finish_topup(topup_id, "paid")
    await callback.answer("Баланс зачислен.", show_alert=True)
    try:
        await callback.bot.send_message(topup[1], f"✅ Пополнение #{await get_topup_code(topup_id)} подтверждено. На баланс зачислено <b>{float(topup[2]):.2f} ₽</b>.", parse_mode="HTML")
    except Exception:
        pass
    try:
        await callback.message.edit_caption(caption=f"✅ <b>ПОПОЛНЕНИЕ #{await get_topup_code(topup_id)} ЗАЧИСЛЕНО</b>\n\n💰 {float(topup[2]):.2f} ₽\n👤 ID: <code>{topup[1]}</code>", parse_mode="HTML", reply_markup=None)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("topup_reject:"))
async def topup_reject(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    topup_id = int((callback.data or "").split(":", 1)[1])
    topup = await get_topup(topup_id)
    if not topup or topup[4] != "waiting_review":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return
    await finish_topup(topup_id, "rejected")
    await callback.answer("Пополнение отклонено.", show_alert=True)
    try:
        await callback.bot.send_message(topup[1], f"❌ Пополнение #{await get_topup_code(topup_id)} отклонено. Если это ошибка, обратитесь в поддержку.")
    except Exception:
        pass
    try:
        await callback.message.edit_caption(caption=f"❌ <b>ПОПОЛНЕНИЕ #{await get_topup_code(topup_id)} ОТКЛОНЕНО</b>\n\n💰 {float(topup[2]):.2f} ₽\n👤 ID: <code>{topup[1]}</code>", parse_mode="HTML", reply_markup=None)
    except Exception:
        pass


@dp.callback_query(F.data.startswith("topup_crypto_check:"))
async def topup_crypto_check(callback: CallbackQuery):
    try:
        _, invoice_id, topup_id = (callback.data or "").split(":", 2)
        invoice_id, topup_id = int(invoice_id), int(topup_id)
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный платёж.", show_alert=True)
        return
    topup = await get_topup(topup_id)
    if not topup or topup[1] != callback.from_user.id:
        await callback.answer("❌ Пополнение не найдено.", show_alert=True)
        return
    if topup[4] == "paid":
        await callback.answer("✅ Баланс уже пополнен.", show_alert=True)
        return
    try:
        invoice = await get_crypto_invoice(invoice_id)
    except Exception as e:
        print(f"Ошибка проверки пополнения Crypto Pay: {e}")
        await callback.answer("❌ Не удалось проверить оплату.", show_alert=True)
        return
    if not invoice or invoice.get("status") != "paid":
        await callback.answer("⏳ Оплата ещё не подтверждена.", show_alert=True)
        return
    await finish_topup(topup_id, "paid")
    paid_asset = invoice.get("paid_asset") or topup[3]
    await callback.answer("✅ Оплата подтверждена!", show_alert=True)
    await callback.message.edit_text(
        f"✅ <b>Баланс пополнен</b>\n\n💰 Зачислено: <b>{float(topup[2]):.2f} ₽</b>\n💳 Оплата: <b>{html.escape(str(paid_asset))} / Crypto Pay</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Профиль", style="success", callback_data="profile")]
        ]),
    )


@dp.callback_query(F.data == "referral_menu")
async def referral_menu(callback: CallbackQuery, state: FSMContext | None = None):
    if state is not None:
        try:
            await state.clear()
        except Exception:
            pass
    await callback.answer()
    user_id = callback.from_user.id
    balance = await get_referral_balance(user_id)
    total_refs, premium_refs = await get_referral_stats(user_id)
    payout = await get_payout_details(user_id)
    me = await callback.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"

    # Ровно тот текст, что в редакторе (переменные подставляются 1 в 1)
    text_msg = await _get_rendered_template(
        "referral",
        _ui_text_default("referral"),
        {
            "reward": str(int(REF_REWARD_RUB)),
            "min_withdraw": str(int(REF_MIN_WITHDRAW_RUB)),
            "balance": f"{balance:.0f}",
            "total_refs": str(total_refs),
            "premium_refs": str(premium_refs),
            "payout": payout if payout else "не указаны",
            "ref_link": ref_link,
        },
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_button_label("💳 Добавить реквизиты", "referral_set_card"), callback_data="referral_set_card")],
        [InlineKeyboardButton(text=_button_label("🏧 Вывести", "referral_withdraw"), callback_data="referral_withdraw")],
        [InlineKeyboardButton(text=_button_label("⬅️ Главное меню", "back"), style="danger", callback_data="back_main")],
    ])
    await show_text_or_photo(callback, text_msg, kb, ui_key="referral")


@dp.callback_query(F.data == "referral_set_card")
async def referral_set_card(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(WithdrawState.waiting_card)
    card_text = await _get_rendered_ui_text("referral_card", _ui_text_default("referral_card"))
    await answer_text_or_photo(callback.message, card_text, ui_key="referral_card")


@dp.message(WithdrawState.waiting_card)
async def referral_save_card(message: Message, state: FSMContext):
    if (message.text or "").strip().lower() in {"/cancel", "отмена"}:
        await state.clear()
        await message.answer("Отменено.")
        return

    raw = (message.text or "").strip().replace(" ", "").replace("-", "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 13 or len(digits) > 19:
        await message.answer(
            "❌ Некорректный номер карты.\n"
            "Введите от 13 до 19 цифр или /cancel."
        )
        return

    await set_payout_details(message.from_user.id, digits)
    await state.clear()
    await message.answer(
        f"✅ Реквизиты сохранены:\n<code>{digits}</code>\n\n"
        "Они будут показаны в разделе «Рефералка».",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤝 Открыть рефералку", callback_data="referral_menu")],
            [InlineKeyboardButton(text="⬅️ Главное меню", style="danger", callback_data="back_main")],
        ]),
    )


@dp.callback_query(F.data == "referral_withdraw")
async def referral_withdraw_start(callback: CallbackQuery, state: FSMContext):
    # Сначала проверяем, что пользователь сделал хотя бы одну подтверждённую покупку
    if not await user_has_paid_order(callback.from_user.id):
        await callback.answer(
            "Для вывода нужен хотя бы один успешный заказ (подтверждённый администратором).",
            show_alert=True,
        )
        return

    balance = await get_referral_balance(callback.from_user.id)
    if balance < REF_MIN_WITHDRAW_RUB:
        await callback.answer(
            f"Минимум {int(REF_MIN_WITHDRAW_RUB)} ₽. Сейчас: {balance:.0f} ₽",
            show_alert=True,
        )
        return

    payout = await get_payout_details(callback.from_user.id)
    if not payout:
        await callback.answer(
            "Сначала добавьте реквизиты (номер карты)",
            show_alert=True,
        )
        return

    await callback.answer()
    ok, err, req_id = await create_withdrawal_request(
        callback.from_user.id, balance, payout
    )
    if not ok:
        await callback.message.answer(f"❌ {err}")
        return

    await callback.message.answer(
        f"✅ Заявка <b>#{req_id}</b> на вывод <b>{balance:.0f} ₽</b> создана.\n"
        f"Карта: <code>{html.escape(payout)}</code>\n"
        "Ожидайте обработки администратором.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Главное меню", style="danger", callback_data="back_main")],
        ]),
    )
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🏧 <b>Заявка на вывод #{req_id}</b>\n\n"
                f"User: <code>{callback.from_user.id}</code> "
                f"@{callback.from_user.username or '—'}\n"
                f"Сумма: <b>{balance:.0f} ₽</b>\n"
                f"Карта: <code>{html.escape(payout)}</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Выплачено", callback_data=f"wd_ok:{req_id}")],
                    [InlineKeyboardButton(text="❌ Отклонить (вернуть)", callback_data=f"wd_no:{req_id}")],
                ]),
            )
        except Exception as e:
            print(f"[REF] admin notify failed: {e}")


@dp.callback_query(F.data.startswith("wd_ok:"))
async def withdrawal_ok(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    req_id = int(callback.data.split(":")[1])
    ok = await set_withdrawal_status(req_id, "paid")
    if not ok:
        await callback.answer("Уже обработано", show_alert=True)
        return
    await callback.answer("Отмечено как выплачено")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("✅ Выплачено")
    except Exception:
        pass


@dp.callback_query(F.data.startswith("wd_no:"))
async def withdrawal_no(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    req_id = int(callback.data.split(":")[1])
    ok = await refund_withdrawal(req_id)
    if not ok:
        await callback.answer("Уже обработано", show_alert=True)
        return
    await callback.answer("Отклонено, сумма возвращена")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("❌ Отклонено, баланс возвращён пользователю")
    except Exception:
        pass


# ============================================================
# ПОДДЕРЖКА
# ============================================================
# ============================================================
# ПОДДЕРЖКА
# ============================================================


@dp.callback_query(F.data == "reviews")
async def reviews_handler(callback: CallbackQuery):
    await callback.answer()
    text_msg = await _get_rendered_ui_text("reviews", _ui_text_default("reviews"))
    channel_btn = _button_label("📢 Перейти в канал с отзывами", url="https://t.me/sentyrep")
    # label key via url alias
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=channel_btn,
            url="https://t.me/sentyrep",
            style="success",
        )],
        [InlineKeyboardButton(
            text=_button_label("⬅️ Главное меню", "back"),
            style="danger",
            callback_data="back_main",
        )],
    ])
    await show_text_or_photo(callback, text_msg, kb, ui_key="reviews")


@dp.callback_query(F.data == "support")
async def support_handler(
    callback: CallbackQuery,
):
    await callback.answer()

    support_text = await _get_rendered_ui_text("support", _ui_text_default("support"))
    await show_text_or_photo(
        callback,
        support_text,
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}")],
                [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="back_main")],
            ]
        ),
        ui_key="support",
    )


# ============================================================
# РУЛЕТКА
# ============================================================

def roulette_keyboard(can_spin: bool = True) -> InlineKeyboardMarkup:
    # Кнопка запуска всегда остаётся на экране. Если попытка уже
    # использована сегодня, roulette_spin_handler сам покажет уведомление.
    # Это не даёт интерфейсу рулетки "пропадать" из-за даты последнего спина.
    rows = [
        [InlineKeyboardButton(text="🎰 Крутить рулетку", style="success", callback_data="roulette_spin")],
        [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "roulette")
async def roulette_handler(callback: CallbackQuery):
    await callback.answer()
    discount, last_spin = await get_roulette_data(callback.from_user.id)
    today = date.today().isoformat()
    can_spin = last_spin != today
    extra = ""
    if discount:
        extra = f"\n\n🎟 <b>Ваша скидка: {discount}%</b> — она будет применена к следующей покупке."
    if not can_spin:
        extra += "\n\n⏰ Вы уже крутили рулетку сегодня. Новая попытка будет доступна завтра."
    roulette_text = await _get_rendered_ui_text("roulette", _ui_text_default("roulette"))
    if "50 ₽" not in roulette_text:
        roulette_text += (
            "\n\n🎁 <b>Возможные награды:</b> 5%, 10%, 15% скидка "
            "или <b>1 ₽, 3 ₽, 5 ₽, 10 ₽, 20 ₽, 50 ₽</b> на баланс.\n"
            "💰 Денежная награда зачисляется автоматически."
        )
    roulette_text += extra

    # Главное меню — фотография, а рулетка — текстовый экран.
    # Telegram не умеет превратить photo-message в text-message через edit_text,
    # поэтому удаляем старое сообщение и создаём ровно ОДНО новое.
    await show_text_or_photo(
        callback,
        roulette_text,
        roulette_keyboard(can_spin),
        ui_key="roulette",
    )


@dp.callback_query(F.data == "roulette_spin")
async def roulette_spin_handler(callback: CallbackQuery):
    import random

    today = date.today().isoformat()
    discount, last_spin = await get_roulette_data(callback.from_user.id)
    if last_spin == today:
        await callback.answer("⏰ Рулетку можно крутить только раз в день.", show_alert=True)
        return

    await callback.answer("🎰 Рулетка запускается...")
    frames = [
        "🎰 <b>РУЛЕТКА</b>\n\n🔄 Крутим...\n\n❌ Ничего • 5% • 1 ₽ • 10 ₽",
        "🎰 <b>РУЛЕТКА</b>\n\n🔄 Крутим...\n\n3 ₽ • 10% • 20 ₽ • 15%",
        "🎰 <b>РУЛЕТКА</b>\n\n🔄 Крутим...\n\n5 ₽ • 50 ₽ • 5% • 10%",
        "🎰 <b>РУЛЕТКА</b>\n\n🔄 Крутим...\n\n15% • 1 ₽ • 3 ₽ • 20 ₽",
        "🎰 <b>РУЛЕТКА</b>\n\n⏳ Останавливаемся...",
    ]
    for frame in frames:
        try:
            # После входа в рулетку сообщение уже текстовое, поэтому просто редактируем его.
            await callback.message.edit_text(
                frame,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🎰 Рулетка крутится...", callback_data="roulette_wait")]]
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await asyncio.sleep(0.35)

    # Призы рулетки. Денежные награды сразу зачисляются на внутренний
    # баланс пользователя в рублях. Шанс 50 ₽ — ровно 2%.
    prizes = [
        ("nothing", 0, 35),
        ("discount", 5, 25),
        ("discount", 10, 15),
        ("discount", 15, 8),
        ("rub", 1, 7),
        ("rub", 3, 4),
        ("rub", 5, 2),
        ("rub", 10, 1),
        ("rub", 20, 1),
        ("rub", 50, 2),
    ]
    prize_kind, prize_value, _weight = random.choices(
        prizes, weights=[item[2] for item in prizes], k=1
    )[0]

    # Для денежного приза сохраняем 0% скидки и зачисляем сумму отдельно.
    roulette_result = prize_value if prize_kind == "discount" else 0
    await set_roulette_result(callback.from_user.id, roulette_result, today)

    if prize_kind == "discount":
        result_text = (
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"🎁 Вам выпала скидка <b>{prize_value}%</b>!\n\n"
            "Она автоматически применится к <b>следующей покупке</b>."
        )
    elif prize_kind == "rub":
        await credit_balance_rub(callback.from_user.id, prize_value)
        new_balance = await get_balance_rub(callback.from_user.id)
        result_text = (
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"💰 Вам выпало <b>{prize_value} ₽</b> на баланс!\n\n"
            f"💳 Новый баланс: <b>{new_balance:.2f} ₽</b>"
        )
    else:
        result_text = "😔 <b>В этот раз ничего не выпало.</b>\n\nПопробуйте завтра!"
    await callback.message.edit_text(
        "🎁 <b>РУЛЕТКА</b>\n\n" + result_text,
        reply_markup=roulette_keyboard(False),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "roulette_wait")
async def roulette_wait_handler(callback: CallbackQuery):
    await callback.answer("🎰 Рулетка ещё крутится...", show_alert=False)


# ============================================================
# FAQ
# ============================================================

@dp.callback_query(F.data == "faq")
async def faq_handler(callback: CallbackQuery):
    await callback.answer()

    faq_text = await _get_rendered_ui_text("faq", _ui_text_default("faq"))

    await show_text_or_photo(
        callback,
        faq_text,
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="back_main")]
            ]
        ),
        ui_key="faq",
    )


# ============================================================
# ПРАВИЛА / СОГЛАШЕНИЯ
# ============================================================

@dp.callback_query(F.data == "rules_menu")
async def rules_handler(callback: CallbackQuery):
    await callback.answer()

    rules_text = await _get_rendered_ui_text("rules", _ui_text_default("rules"))

    await show_text_or_photo(
        callback,
        rules_text,
        InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", style="danger", callback_data="back_main")]]
        ),
        ui_key="rules",
    )


# ============================================================
# НАЗАД
# ============================================================

@dp.callback_query(F.data == "back_main")
async def back_main_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    # Универсальный и отказоустойчивый возврат в главное меню.
    # Сначала отвечаем на callback, чтобы Telegram не оставлял кнопку
    # в состоянии загрузки, затем пробуем редактирование текущего сообщения.
    try:
        await callback.answer()
    except Exception:
        pass

    try:
        if isinstance(callback.message, Message):
            await send_main_menu_from_callback(callback, state)
            return
    except Exception as e:
        print(f"[BACK_MAIN] edit failed: {e}")

    # Сначала отправляем рабочее меню, и только после этого удаляем старое.
    try:
        if isinstance(callback.message, Message):
            new_message = await callback.message.answer(
                "👋 <b>Добро пожаловать в {shop_name}!</b>\n\nВыберите нужный раздел ниже:",
                reply_markup=main_menu(),
                parse_mode="HTML",
            )
            try:
                await callback.message.delete()
            except Exception:
                pass
            if new_message.photo:
                cache_asset_id("main_menu", new_message.photo[-1].file_id)
            return
    except Exception as e:
        print(f"[BACK_MAIN] fallback send failed: {e}")



# ============================================================
# DEFAULT ROBLOX / ROBUX CATALOG
# ============================================================

async def create_default_roblox_catalog():
    """Создаёт системный Roblox → Robux без размножения каталогов и товаров.

    Важно: стандартные товары идентифицируются по количеству Robux в названии,
    а не только по точному названию. Поэтому переименование товара через
    админ-панель больше не приводит к созданию его копии при перезапуске.
    """
    import re

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row

        # ---------- Roblox root ----------
        cursor = await db.execute(
            """SELECT id, name, image_file_id FROM catalogs
               WHERE parent_id IS NULL
               AND lower(trim(name)) IN ('roblox', '❇️ roblox')
               ORDER BY id ASC"""
        )
        roots = await cursor.fetchall()

        if roots:
            roblox_id = roots[0]["id"]
            image_id = roots[0]["image_file_id"]
            for row in roots[1:]:
                duplicate_id = row["id"]
                if not image_id and row["image_file_id"]:
                    image_id = row["image_file_id"]
                await db.execute(
                    "UPDATE products SET catalog_id = ? WHERE catalog_id = ?",
                    (roblox_id, duplicate_id),
                )
                await db.execute(
                    "UPDATE catalogs SET parent_id = ? WHERE parent_id = ?",
                    (roblox_id, duplicate_id),
                )
                await db.execute("DELETE FROM catalogs WHERE id = ?", (duplicate_id,))
            await db.execute(
                "UPDATE catalogs SET name = ?, image_file_id = COALESCE(image_file_id, ?) WHERE id = ?",
                ("❇️ Roblox", image_id, roblox_id),
            )
        else:
            cur = await db.execute(
                "INSERT INTO catalogs (name, parent_id, is_active, image_file_id) VALUES (?, NULL, 1, NULL)",
                ("❇️ Roblox",),
            )
            roblox_id = cur.lastrowid

        # ---------- Robux subcatalog ----------
        cursor = await db.execute(
            """SELECT id, name, image_file_id FROM catalogs
               WHERE parent_id = ?
               AND lower(trim(name)) IN ('robux', '💰 robux')
               ORDER BY id ASC""",
            (roblox_id,),
        )
        robux_rows = await cursor.fetchall()

        if robux_rows:
            robux_id = robux_rows[0]["id"]
            image_id = robux_rows[0]["image_file_id"]
            for row in robux_rows[1:]:
                duplicate_id = row["id"]
                if not image_id and row["image_file_id"]:
                    image_id = row["image_file_id"]
                await db.execute(
                    "UPDATE products SET catalog_id = ? WHERE catalog_id = ?",
                    (robux_id, duplicate_id),
                )
                await db.execute(
                    "UPDATE catalogs SET parent_id = ? WHERE parent_id = ?",
                    (robux_id, duplicate_id),
                )
                await db.execute("DELETE FROM catalogs WHERE id = ?", (duplicate_id,))
            await db.execute(
                "UPDATE catalogs SET name = ?, image_file_id = COALESCE(image_file_id, ?) WHERE id = ?",
                ("💰 Robux", image_id, robux_id),
            )
        else:
            cur = await db.execute(
                "INSERT INTO catalogs (name, parent_id, is_active, image_file_id) VALUES (?, ?, 1, NULL)",
                ("💰 Robux", roblox_id),
            )
            robux_id = cur.lastrowid

        await db.commit()

    # ---------- Standard Robux products ----------
    amounts = [100, 300, 500, 1000, 2000, 5000, 10000]

    def amount_from_name(name: str):
        """Возвращает количество Robux, если название похоже на Robux-товар."""
        text = str(name or "").lower().replace("\u00a0", " ")
        if "robux" not in text:
            return None
        numbers = re.findall(r"(?<!\d)(\d[\d\s,._]*)(?!\d)", text)
        for raw in numbers:
            digits = re.sub(r"\D", "", raw)
            if digits:
                value = int(digits)
                if value in amounts:
                    return value
        return None

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, name, description, image_file_id, price_rub, price_usdt, is_active
               FROM products WHERE catalog_id = ? ORDER BY id ASC""",
            (robux_id,),
        )
        rows = await cursor.fetchall()

        # Собираем существующие товары по количеству Robux. Это переживает
        # переименование товара и поэтому не создаёт копию после перезапуска.
        by_amount = {amount: [] for amount in amounts}
        for row in rows:
            amount = amount_from_name(row["name"])
            if amount is not None:
                by_amount[amount].append(row)

        for amount in amounts:
            candidates = by_amount[amount]

            if candidates:
                # Оставляем самый старый товар. Удаляем только его дубли,
                # сохраняя остальные пользовательские товары нетронутыми.
                keeper = candidates[0]
                duplicate_ids = [row["id"] for row in candidates[1:]]
                if duplicate_ids:
                    placeholders = ",".join("?" for _ in duplicate_ids)
                    await db.execute(
                        f"DELETE FROM products WHERE id IN ({placeholders})",
                        duplicate_ids,
                    )

                # Обновляем только системные поля цены/активности.
                # Название, описание и картинка, изменённые админом, сохраняются.
                price_usdt = round(amount * 1.2 / 100, 2)
                await db.execute(
                    "UPDATE products SET price_rub = ?, price_usdt = ?, is_active = 1 WHERE id = ?",
                    (amount, price_usdt, keeper["id"]),
                )
            else:
                name = f"💰 {amount:,} Robux".replace(",", " ")
                price_usdt = round(amount * 1.2 / 100, 2)
                await db.execute(
                    """INSERT INTO products
                    (catalog_id, name, description, image_file_id, price_rub, price_usdt, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (
                        robux_id,
                        name,
                        f"🎮 Пополнение Roblox на {amount:,} Robux.\n"
                        "👤 Выдача по нику Roblox.\n"
                        "⚡ После оплаты товар выдается на указанный ник.".replace(",", " "),
                        None,
                        amount,
                        price_usdt,
                    ),
                )

        await db.commit()

    print("✅ Каталог Roblox → Robux: каталоги и товары синхронизированы без дублей")


# ============================================================
# DEFAULT BRAWL STARS CATALOG
# ============================================================


async def create_default_funpay_accounts_catalog():
    """Каталог: Аккаунты Funpay → «с отзывами» → Funpay 494 отзыва.

    Без дублей при каждом запуске. Сравнение имён в Python (SQLite lower()
    не умеет кириллицу).
    """
    ROOT_NAME = "Аккаунты Funpay"
    SUB_NAME = "с отзывами"
    PRODUCT_NAME = "Funpay 494 отзыва"
    DESCRIPTION = (
        "👤 Аккаунт FunPay с 494 отзывами.\n"
        "📦 Выдача данных после подтверждения оплаты.\n"
        "⚡ Проверьте описание перед покупкой."
    )
    PRICE_RUB = 6500.0
    PRICE_USDT = 0.0

    def _norm(s: str) -> str:
        return " ".join(str(s or "").casefold().split())

    def _is_funpay_root(name: str) -> bool:
        n = _norm(name)
        return (
            n == _norm(ROOT_NAME)
            or ("аккаунт" in n and "funpay" in n)
            or ("funpay" in n and "аккаунт" in n)
        )

    def _is_reviews_sub(name: str) -> bool:
        n = _norm(name)
        return n == _norm(SUB_NAME) or "с отзывами" in n

    def _is_target_product(name: str) -> bool:
        n = _norm(name)
        return "494" in n and "отзыв" in n or n == _norm(PRODUCT_NAME)

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row

        # ---- корневые каталоги ----
        cursor = await db.execute(
            "SELECT id, name FROM catalogs WHERE parent_id IS NULL ORDER BY id ASC"
        )
        all_roots = await cursor.fetchall()
        funpay_roots = [r for r in all_roots if _is_funpay_root(r["name"])]

        if funpay_roots:
            root_id = funpay_roots[0]["id"]
            # Сливаем дубликаты корня
            for row in funpay_roots[1:]:
                dup = row["id"]
                await db.execute(
                    "UPDATE products SET catalog_id = ? WHERE catalog_id = ?",
                    (root_id, dup),
                )
                await db.execute(
                    "UPDATE catalogs SET parent_id = ? WHERE parent_id = ?",
                    (root_id, dup),
                )
                await db.execute("DELETE FROM catalogs WHERE id = ?", (dup,))
            await db.execute(
                "UPDATE catalogs SET name = ?, is_active = 1 WHERE id = ?",
                (ROOT_NAME, root_id),
            )
        else:
            cur = await db.execute(
                "INSERT INTO catalogs (name, parent_id, is_active) VALUES (?, NULL, 1)",
                (ROOT_NAME,),
            )
            root_id = cur.lastrowid

        # ---- подкаталог ----
        cursor = await db.execute(
            "SELECT id, name FROM catalogs WHERE parent_id = ? ORDER BY id ASC",
            (root_id,),
        )
        children = await cursor.fetchall()
        subs = [r for r in children if _is_reviews_sub(r["name"])]

        if subs:
            sub_id = subs[0]["id"]
            for row in subs[1:]:
                dup = row["id"]
                await db.execute(
                    "UPDATE products SET catalog_id = ? WHERE catalog_id = ?",
                    (sub_id, dup),
                )
                await db.execute(
                    "UPDATE catalogs SET parent_id = ? WHERE parent_id = ?",
                    (sub_id, dup),
                )
                await db.execute("DELETE FROM catalogs WHERE id = ?", (dup,))
            await db.execute(
                "UPDATE catalogs SET name = ?, is_active = 1 WHERE id = ?",
                (SUB_NAME, sub_id),
            )
        else:
            cur = await db.execute(
                "INSERT INTO catalogs (name, parent_id, is_active) VALUES (?, ?, 1)",
                (SUB_NAME, root_id),
            )
            sub_id = cur.lastrowid

        await db.commit()

        # ---- товар ----
        cursor = await db.execute(
            "SELECT id, name FROM products WHERE catalog_id = ? ORDER BY id ASC",
            (sub_id,),
        )
        all_products = await cursor.fetchall()
        targets = [p for p in all_products if _is_target_product(p["name"])]

        if targets:
            pid = targets[0]["id"]
            await db.execute(
                """UPDATE products
                   SET name = ?, description = ?, price_rub = ?, price_usdt = ?,
                       is_active = 1, quantity = COALESCE(NULLIF(quantity, 0), 1)
                   WHERE id = ?""",
                (PRODUCT_NAME, DESCRIPTION, PRICE_RUB, PRICE_USDT, pid),
            )
            for row in targets[1:]:
                await db.execute("DELETE FROM products WHERE id = ?", (row["id"],))
        else:
            await db.execute(
                """INSERT INTO products
                   (catalog_id, name, description, image_file_id, price_rub, price_usdt, quantity, is_active)
                   VALUES (?, ?, ?, NULL, ?, ?, 1, 1)""",
                (sub_id, PRODUCT_NAME, DESCRIPTION, PRICE_RUB, PRICE_USDT),
            )

        await db.commit()

    print("✅ Каталог Аккаунты Funpay → с отзывами → Funpay 494 отзыва: без дублей")


async def create_default_brawl_pass_catalog():
    """Пустой каталог Brawl Pass: товары добавляет админ.
    При покупке любого товара из него бот просит Supercell ID.
    """
    ROOT_NAME = "Brawl Pass"

    def _norm(s: str) -> str:
        return " ".join(str(s or "").casefold().split())

    def _is_root(name: str) -> bool:
        n = _norm(name)
        return n == _norm(ROOT_NAME) or n.replace(" ", "") == "brawlpass"

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name FROM catalogs WHERE parent_id IS NULL ORDER BY id ASC"
        )
        roots = [r for r in await cursor.fetchall() if _is_root(r["name"])]

        if roots:
            root_id = roots[0]["id"]
            for row in roots[1:]:
                dup = row["id"]
                await db.execute(
                    "UPDATE products SET catalog_id = ? WHERE catalog_id = ?",
                    (root_id, dup),
                )
                await db.execute(
                    "UPDATE catalogs SET parent_id = ? WHERE parent_id = ?",
                    (root_id, dup),
                )
                await db.execute("DELETE FROM catalogs WHERE id = ?", (dup,))
            await db.execute(
                "UPDATE catalogs SET name = ?, is_active = 1 WHERE id = ?",
                (ROOT_NAME, root_id),
            )
        else:
            await db.execute(
                "INSERT INTO catalogs (name, parent_id, is_active) VALUES (?, NULL, 1)",
                (ROOT_NAME,),
            )

        await db.commit()

    print("✅ Каталог Brawl Pass готов (товары добавляй через админку)")


async def create_default_brawl_stars_catalog():
    catalogs = await get_catalogs()

    for catalog in catalogs:
        if catalog[1] == "Brawl Stars":
            return

    catalog_id = await create_catalog(
        name="Brawl Stars",
        parent_id=None,
    )

    products = [
        (
            "🎮 Brawl Stars аккаунт",
            "Прокачанные аккаунты Brawl Stars.",
            499,
            5.99,
        ),
        (
            "⭐ Brawl Pass Brawl Stars",
            "Покупка Brawl Pass для вашего аккаунта по Supercell ID.",
            799,
            9.99,
        ),
        (
            "💎 Гемы Brawl Stars",
            "Пополнение гемов Brawl Stars.",
            299,
            3.99,
        ),
    ]

    for name, description, price_rub, price_usdt in products:
        await create_product(
            catalog_id=catalog_id,
            name=name,
            description=description,
            image_file_id=None,
            price_rub=price_rub,
            price_usdt=price_usdt,
        )

    print("✅ Каталог Brawl Stars создан")


# ============================================================
# ЗАПУСК БОТА
# ============================================================



@dp.message(RobloxState.waiting_nickname)
async def roblox_nickname_received(message: Message, state: FSMContext):
    nickname = message.text.strip() if message.text else ""

    if not is_valid_roblox_nickname(nickname):
        await message.answer(
            "❌ Некорректный ник Roblox.\n\n"
            "Используйте от 3 до 20 символов: латинские буквы, цифры и _.\n"
            "Пример: <code>Builderman</code>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    if not user:
        await state.clear()
        await message.answer("❌ Не удалось создать пользователя.")
        return

    payment_method = data.get("payment_method", "")
    method_key = "sbp" if payment_method in ("SBP", "YOOMONEY") else str(payment_method).lower()
    if payment_method == "BALANCE":
        method_key = "balance"
    if method_key not in {"rub", "sbp", "usdt", "balance"} or (method_key != "balance" and not await is_payment_enabled(method_key)):
        await state.clear()
        await message.answer("⛔ Этот способ оплаты был отключён администратором. Вернитесь к товару и выберите доступный способ оплаты.")
        return

    try:
        order_id = await create_order(
            user_id=user[0],
            product_id=data["product_id"],
            payment_method=data["payment_method"],
            amount=data["amount"],
            brawl_id=nickname,
        )
    except Exception as e:
        print(f"Ошибка создания Roblox заказа: {e}")
        await state.clear()
        await message.answer("❌ Не удалось создать заказ.")
        return

    payment_method = data["payment_method"]

    if payment_method == "BALANCE":
        amount = float(data["amount"])
        if not await debit_balance_rub(message.from_user.id, amount):
            balance_now = await get_balance_rub(message.from_user.id)
            missing = max(0.0, amount - balance_now)
            insufficient_text = await _get_rendered_template("balance_payment_insufficient", _ui_text_default("balance_payment_insufficient"), {"amount": f"{amount:.2f}", "balance": f"{balance_now:.2f}", "missing": f"{missing:.2f}"})
            await state.clear()
            await answer_text_or_photo(message, insufficient_text, ui_key="balance_payment_insufficient")
            return
        await update_order_status(order_id, "paid")
        if data.get("roulette_discount"):
            await consume_roulette_discount(message.from_user.id)
        new_balance = await get_balance_rub(message.from_user.id)
        await state.clear()
        success_text = await _get_rendered_template("balance_payment_success", _ui_text_default("balance_payment_success"), {
            "order_id": order_id, "product_name": "Roblox", "amount": f"{amount:.2f}", "balance": f"{new_balance:.2f}",
            "details": f"🎮 Roblox: <code>{html.escape(nickname)}</code>",
        })
        await answer_text_or_photo(message, success_text, ui_key="balance_payment_success")
        return

    await state.clear()

    if payment_method in ("RUB", "SBP"):
        if payment_method == "SBP":
            sbp_link = await get_setting("sbp_payment_url")
            if not sbp_link:
                await message.answer("❌ СБП сейчас не настроен. Обратитесь в поддержку.")
                return
            roblox_text = await _get_rendered_template("roblox_order_sbp", _ui_text_default("roblox_order_sbp"), {
                "order_id": order_id,
                "product_name": html.escape(str(data.get("product_name", "Robux"))),
                "nickname": html.escape(nickname),
                "original_amount": f"{float(data.get('original_amount', data['amount'])):.2f}",
                "amount": f"{float(data['amount']):.2f}",
                "discount": (f"\n🎁 Скидка рулетки: <b>{int(data.get('roulette_discount', 0))}%</b>\n" if data.get('roulette_discount') else ""),
            })
            await answer_text_or_photo(message, roblox_text, keyboard=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏦 Перейти к оплате СБП", style="success", url=sbp_link)],
                [InlineKeyboardButton(text="🔎 Проверить оплату", style="success", callback_data=f"sbp_check:{order_id}")],
                [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
            ]), ui_key="roblox_order_sbp")
        else:
            await state.update_data(order_id=order_id)
            await state.set_state(ReceiptState.waiting_receipt)
            card = await get_setting("rub_card") or "Реквизиты пока не указаны."
            roblox_text = await _get_rendered_template("roblox_order_rub", _ui_text_default("roblox_order_rub"), {
                "order_id": order_id, "product_name": html.escape(str(data.get("product_name", "Robux"))), "nickname": html.escape(nickname),
                "original_amount": f"{float(data.get('original_amount', data['amount'])):.2f}", "amount": f"{float(data['amount']):.2f}",
                "discount": (f"\n🎁 Скидка рулетки: <b>{int(data.get('roulette_discount', 0))}%</b>\n" if data.get('roulette_discount') else ""), "card": card,
            })
            await answer_text_or_photo(message, roblox_text, keyboard=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📸 Я оплатил — отправить чек", style="success", callback_data=f"receipt:{order_id}")],
                [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
            ]), ui_key="roblox_order_rub")
        return

    if payment_method == "YOOMONEY":
        wallet = await get_setting("yoomoney_wallet")
        if not wallet:
            await message.answer("❌ ЮMoney сейчас не настроен. Обратитесь в поддержку.")
            return
        label = f"ORDER-{await get_order_code(order_id)}"
        pay_url = "https://yoomoney.ru/quickpay/confirm?" + urlencode({
            "receiver": wallet, "quickpay-form": "shop",
            "targets": f"Заказ #{await get_order_code(order_id)}",
            "paymentType": "AC", "sum": f"{float(data['amount']):.2f}", "label": label,
        })
        roblox_text = await _get_rendered_template("sbp_order", _ui_text_default("sbp_order"), {
            "order_id": order_id,
            "product_name": html.escape(str(data.get("product_name", "Robux"))) + f"\n👤 Roblox: <code>{html.escape(nickname)}</code>",
            "original_amount": f"{float(data.get('original_amount', data['amount'])):.2f}",
            "amount": f"{float(data['amount']):.2f}",
            "discount": (f"\n🎁 Скидка рулетки: <b>{int(data.get('roulette_discount', 0))}%</b>\n" if data.get('roulette_discount') else ""),
        })
        await message.answer(roblox_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_button_label("🏦 Оплатить СБП", callback_data="pay_yoomoney:button"), style="success", url=pay_url, icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_sbp"))],
            [InlineKeyboardButton(text=_button_label("🔎 Я оплатил", callback_data="sbp_check:button"), style="success", callback_data=f"yoomoney_check:{order_id}", icon_custom_emoji_id=_BUTTON_ICONS.get("label:sbp_check"))],
            [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
        ]))
        return

    try:
        invoice = await create_crypto_invoice(
            amount=float(data["amount"]),
            order_id=order_id,
        )
        roblox_text = await _get_rendered_template("roblox_order_usdt", _ui_text_default("roblox_order_usdt"), {
            "order_id": order_id,
            "product_name": html.escape(str(data.get("product_name", "Robux"))),
            "nickname": html.escape(nickname),
            "amount": f"{float(data['amount']):.4f}",
        })
        await answer_text_or_photo(
            message,
            roblox_text,
            keyboard=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить USDT", style="success", url=invoice["bot_invoice_url"])],
                [InlineKeyboardButton(text="🔄 Проверить оплату", style="success", callback_data=f"crypto_check:{invoice['invoice_id']}:{order_id}")],
            ]),
            ui_key="roblox_order_usdt",
        )
    except Exception as e:
        print(f"Ошибка создания USDT Roblox заказа: {e}")
        await message.answer("❌ Не удалось создать оплату USDT. Попробуйте ещё раз.")


@dp.message(BrawlState.waiting_id)
async def brawl_id_received(message: Message, state: FSMContext):
    raw_id = message.text.strip() if message.text else ""
    data = await state.get_data()
    id_type = data.get("brawl_id_type", "player_tag")

    if id_type == "player_id":
        player_id = raw_id
        if not is_valid_player_id(player_id):
            await message.answer(
                "❌ Неверный Supercell Player ID.\n\n"
                "Пример: <code>BraveBarbarian</code>\n\n"
                "Введите Player ID ещё раз.\n"
                "Не используйте старый формат с <code>#</code>.",
                parse_mode="HTML",
            )
            return
        brawl_id = player_id
        id_label = "🎫 Supercell Player ID сохранён."
    else:
        brawl_id = raw_id.upper()
        if not is_valid_brawl_id(brawl_id):
            await message.answer(
                "❌ Неверный Brawl Stars ID.\n\n"
                "Пример правильного ID:\n"
                "#2PP0L9QJ\n\n"
                "Введите ID ещё раз:"
            )
            return
        id_label = "🎮 Brawl ID сохранён."
    user = await get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )

    if not user:
        await state.clear()
        return

    payment_method = data.get("payment_method", "")
    method_key = "sbp" if payment_method in ("SBP", "YOOMONEY") else str(payment_method).lower()
    if payment_method == "BALANCE":
        method_key = "balance"
    if method_key not in {"rub", "sbp", "usdt", "balance"} or (method_key != "balance" and not await is_payment_enabled(method_key)):
        await state.clear()
        await message.answer("⛔ Этот способ оплаты был отключён администратором. Вернитесь к товару и выберите доступный способ оплаты.")
        return

    order_id = await create_order(
        user_id=user[0],
        product_id=data["product_id"],
        payment_method=data["payment_method"],
        amount=data["amount"],
        brawl_id=brawl_id,
    )
    payment_method = data["payment_method"]

    if payment_method == "BALANCE":
        amount = float(data["amount"])
        if not await debit_balance_rub(message.from_user.id, amount):
            balance_now = await get_balance_rub(message.from_user.id)
            missing = max(0.0, amount - balance_now)
            insufficient_text = await _get_rendered_template("balance_payment_insufficient", _ui_text_default("balance_payment_insufficient"), {"amount": f"{amount:.2f}", "balance": f"{balance_now:.2f}", "missing": f"{missing:.2f}"})
            await state.clear()
            await answer_text_or_photo(message, insufficient_text, ui_key="balance_payment_insufficient")
            return
        await update_order_status(order_id, "paid")
        if data.get("roulette_discount"):
            await consume_roulette_discount(message.from_user.id)
        new_balance = await get_balance_rub(message.from_user.id)
        await state.clear()
        success_text = await _get_rendered_template("balance_payment_success", _ui_text_default("balance_payment_success"), {
            "order_id": order_id, "product_name": data.get("product_name", "Brawl Stars"), "amount": f"{amount:.2f}", "balance": f"{new_balance:.2f}",
            "details": html.escape(id_label),
        })
        await answer_text_or_photo(message, success_text, ui_key="balance_payment_success")
        return

    await state.clear()

    # RUB — показываем реквизиты и ждём чек
    if payment_method in ("RUB", "SBP"):
        if payment_method == "SBP":
            sbp_link = await get_setting("sbp_payment_url")
            if not sbp_link:
                await message.answer("❌ СБП сейчас не настроен. Обратитесь в поддержку.")
                return
            brawl_text = await _get_rendered_template("sbp_order", _ui_text_default("sbp_order"), {
                "order_id": order_id,
                "product_name": html.escape(str(data.get("product_name", "Brawl Stars"))),
                "original_amount": f"{float(data.get('original_amount', data['amount'])):.2f}",
                "amount": f"{float(data['amount']):.2f}",
                "discount": (f"\n🎁 Скидка рулетки: <b>{int(data.get('roulette_discount', 0))}%</b>\n" if data.get('roulette_discount') else ""),
            })
            await answer_text_or_photo(message, brawl_text, keyboard=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏦 Перейти к оплате СБП", style="success", url=sbp_link)],
                [InlineKeyboardButton(text="🔎 Проверить оплату", style="success", callback_data=f"sbp_check:{order_id}")],
                [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
            ]), ui_key="sbp_order")
        else:
            await state.update_data(order_id=order_id)
            await state.set_state(ReceiptState.waiting_receipt)
            card = await get_setting("rub_card") or "Реквизиты пока не указаны."
            brawl_template_key = "brawl_pass_order_rub" if id_type == "player_id" else "brawl_order_rub"
            brawl_text = await _get_rendered_template(brawl_template_key, _ui_text_default(brawl_template_key), {
                "order_id": order_id, "product_name": html.escape(str(data.get("product_name", "Brawl Stars"))), "id_label": html.escape(id_label),
                "original_amount": f"{float(data.get('original_amount', data['amount'])):.2f}", "amount": f"{float(data['amount']):.2f}",
                "discount": (f"\n🎁 Скидка рулетки: <b>{int(data.get('roulette_discount', 0))}%</b>\n" if data.get('roulette_discount') else ""), "card": card,
            })
            await answer_text_or_photo(message, brawl_text, ui_key=brawl_template_key)
        return

    if payment_method == "YOOMONEY":
        wallet = await get_setting("yoomoney_wallet")
        if not wallet:
            await message.answer("❌ ЮMoney сейчас не настроен. Обратитесь в поддержку.")
            return
        label = f"ORDER-{await get_order_code(order_id)}"
        pay_url = "https://yoomoney.ru/quickpay/confirm?" + urlencode({
            "receiver": wallet, "quickpay-form": "shop",
            "targets": f"Заказ #{await get_order_code(order_id)}",
            "paymentType": "AC", "sum": f"{float(data['amount']):.2f}", "label": label,
        })
        brawl_text = await _get_rendered_template("sbp_order", _ui_text_default("sbp_order"), {
            "order_id": order_id,
            "product_name": html.escape(str(data.get("product_name", "Brawl Stars"))) + f"\n🎮 ID: <code>{html.escape(brawl_id)}</code>",
            "original_amount": f"{float(data.get('original_amount', data['amount'])):.2f}",
            "amount": f"{float(data['amount']):.2f}",
            "discount": (f"\n🎁 Скидка рулетки: <b>{int(data.get('roulette_discount', 0))}%</b>\n" if data.get('roulette_discount') else ""),
        })
        await answer_text_or_photo(message, brawl_text, keyboard=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_button_label("🏦 Оплатить СБП", callback_data="pay_yoomoney:button"), style="success", url=pay_url, icon_custom_emoji_id=_BUTTON_ICONS.get("label:pay_sbp"))],
            [InlineKeyboardButton(text=_button_label("🔎 Я оплатил", callback_data="sbp_check:button"), style="success", callback_data=f"yoomoney_check:{order_id}", icon_custom_emoji_id=_BUTTON_ICONS.get("label:sbp_check"))],
            [InlineKeyboardButton(text="❌ Отменить", style="danger", callback_data="back_main")],
        ]), ui_key="sbp_order")
        return

    # USDT — создаём оплату после получения Brawl ID
    if payment_method == "USDT":
        try:
            invoice = await create_crypto_invoice(
                amount=float(data["amount"]),
                order_id=order_id,
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💳 Оплатить USDT",
                    style="success",
                                    url=invoice["bot_invoice_url"],
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔄 Проверить оплату",
                            callback_data=(
                                f"crypto_check:"
                                f"{invoice['invoice_id']}:"
                                f"{order_id}"
                            ),
                        )
                    ],
                ]
            )

            brawl_text = await _get_rendered_template("brawl_order_usdt", _ui_text_default("brawl_order_usdt"), {
                "order_id": order_id,
                "id_label": html.escape(id_label),
                "amount": f"{float(data['amount']):.2f}",
            })
            await answer_text_or_photo(
                message,
                brawl_text,
                keyboard=keyboard,
                ui_key="brawl_order_usdt",
            )

        except Exception as e:
            print(f"Ошибка создания USDT после Brawl ID: {e}")
            await message.answer(
                "❌ Не удалось создать оплату USDT. Попробуйте ещё раз."
            )


async def main():
    await init_db()
    await ensure_balance_tables()
    await _load_button_texts()
    await _load_name_emoji_cache()
    await ensure_product_quantity_db()
    await ensure_catalog_images_db()
    await init_start_stats_db()
    await create_default_roblox_catalog()
    await create_default_funpay_accounts_catalog()
    await create_default_brawl_pass_catalog()

    # Прокси используется только если задан PROXY_URL.
    # По умолчанию Telegram API вызывается напрямую.
    session = AiohttpSession(proxy=PROXY_URL or None)
    bot = Bot(token=BOT_TOKEN, session=session)

    try:
        print("========================================")
        print("🚀 Бот запускается...")
        print("========================================")

        # Telegram API может отвечать медленно/временно быть недоступен на хостинге.
        # Пробуем удалить webhook несколько раз, но не даём одному таймауту
        # завершить процесс без понятного сообщения.
        webhook_ok = False
        for attempt in range(1, 4):
            try:
                print(f"📡 Подключение к Telegram API: попытка {attempt}/3...")
                await bot.delete_webhook(drop_pending_updates=True, request_timeout=15)
                webhook_ok = True
                print("✅ Связь с Telegram API установлена.")
                break
            except Exception as e:
                print(f"⚠️ Telegram API недоступен (попытка {attempt}/3): {type(e).__name__}: {e}")
                if attempt < 3:
                    await asyncio.sleep(3)

        if CRYPTO_PAY_TOKEN:
            try:
                crypto_app = await crypto_api("getMe")
                print(
                    "✅ Crypto Pay API: подключение успешно "
                    f"(app_id={crypto_app.get('app_id')}, name={crypto_app.get('name')!r})."
                )
            except Exception as e:
                print(f"❌ Crypto Pay API: проверка не пройдена: {type(e).__name__}: {e}")
                print("💡 Проверьте переменную CRYPTO_PAY_TOKEN на Deploy-F. Это должен быть API Token приложения Crypto Bot, а не BOT_TOKEN.")
        else:
            print("⚠️ Crypto Pay API: CRYPTO_PAY_TOKEN не задан.")

        if not webhook_ok:
            if PROXY_URL:
                print("❌ Не удалось подключиться к Telegram даже через указанный PROXY_URL.")
            else:
                print("❌ Не удалось подключиться к Telegram напрямую.")
                print("💡 Если хостинг блокирует Telegram API, добавьте рабочий PROXY_URL в переменные окружения.")
            return

        print("✅ Бот успешно запущен!")
        print("⏳ Ожидание сообщений...")

        await dp.start_polling(bot, polling_timeout=30)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
