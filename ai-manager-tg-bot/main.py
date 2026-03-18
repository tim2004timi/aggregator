import asyncio
import logging
from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import aiohttp
from dotenv import load_dotenv
import os
import re
import html
from pathlib import Path
from urllib.parse import urljoin
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from crud import async_session, engine, Base, get_chats, get_chat, get_messages, create_chat, create_message, update_chat_waiting, update_chat_ai, get_stats, get_chats_with_last_messages, get_chat_messages, get_chat_by_uuid, add_chat_tag, remove_chat_tag, sync_vk, get_ai_settings, upsert_ai_settings, get_ai_knowledge, save_ai_knowledge, assign_chat_to_manager, close_chat_dialog, create_dialog_analytics, get_dialog_analytics, get_all_analytics, get_analytics_stats, DialogAnalytics, get_chat_by_topic_id, update_chat_topic_id
import requests
from pydantic import BaseModel, validator
from shared import get_bot
import json
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, insert, text as sa_text
from crud import Message
import crud
from aiogram import F
from minio import Minio
import io
import tempfile
import threading
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from aiogram.types import FSInputFile, BufferedInputFile
import auth
import notifications

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

FAQ_ITEMS: Dict[str, Dict[str, str]] = {}
FAQ_ORDER: List[str] = []
TG_FAQ_PAGE_SIZE = 12
VK_FAQ_PAGE_SIZE = 10

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "30"))

# XAI (Grok) configuration
XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4-latest")
XAI_BASE_URL = "https://api.x.ai/v1/chat/completions"
XAI_PROXY = os.getenv("XAI_PROXY")

# Chats using /test mode (xai model)
_xai_test_chats: set = set()

AI_TOP_K = int(os.getenv("AI_TOP_K", "6"))
AI_MAX_PRODUCTS = int(os.getenv("AI_MAX_PRODUCTS", "300"))
AI_PRODUCTS_PAGE = int(os.getenv("AI_PRODUCTS_PAGE", "50"))
AI_SETTINGS_TTL_SECONDS = int(os.getenv("AI_SETTINGS_TTL_SECONDS", "30"))
AI_KNOWLEDGE_TTL_SECONDS = int(os.getenv("AI_KNOWLEDGE_TTL_SECONDS", "300"))

DEFAULT_AI_SETTINGS = {
    "system_message": "",
    "faqs": "",
    "rules": "",
    "tone": "",
    "handoff_phrases": "",
    "min_score": 0.2,
    "site_pages": "",
    "auto_refresh_minutes": 0,
}

AI_SETTINGS_CACHE: Dict[str, Any] = {"data": None, "ts": 0.0}
AI_KNOWLEDGE_CACHE: Dict[str, Any] = {"data": [], "tokens": [], "ts": 0.0}
AI_STATUS: Dict[str, Any] = {"last_indexed": None, "last_error": None, "chunks": 0}

# Промт для обычного чата поддержки (когда пользователь просто пишет боту)
AI_SUPPORT_PROMPT = (
    "AI Support Assistant — PSIH (psihclothes.com)\n\n"
    "Ассистент работает как цифровая справка магазина PSIH.\n"
    "Он отвечает на вопросы клиентов, используя только фактическую информацию о бренде, товарах, доставке, оплате, возврате и уходе за изделиями.\n\n"
    "Стиль ответа — спокойный, человеческий, без канцелярита и без заученных фраз.\n"
    "Каждый ответ формулируется по смыслу вопроса, без одинаковых конструкций.\n"
    "Ассистент не ведёт диалог ради диалога — он даёт информацию, которую запросили.\n\n"
    "Если информации достаточно — отвечает сразу и по делу.\n"
    "Если информации нет или она неизвестна — прямо сообщает об этом и уточняет, хочет ли клиент, чтобы подключился менеджер.\n\n"
    "Ассистент не делает предположений и не дополняет ответы догадками.\n"
    "Основа ответа — только реальные данные магазина.\n\n"
    "Язык ответа всегда совпадает с языком сообщения клиента.\n\n"
    "---\n\n"
    "О БРЕНДЕ\n\n"
    "PSIH — бренд одежды, существующий с 1 августа 2018 года.\n"
    "Это одежда и аксессуары российского производства.\n\n"
    "Философия бренда:\n"
    "ПСИХ — это визуализация самых далёких уголков разума, эстетика человеческих переживаний, выраженная в дизайне вещей.\n\n"
    "Сайт: https://psihclothes.com\n\n"
    "Связь:\n"
    "VK — vk.com/psihclothes\n"
    "Telegram — t.me/psihclothes\n"
    "Сотрудничество — cooperation@psihclothes.com\n\n"
    "Продавец:\n"
    "ИП Дарков Владислав Игоревич\n"
    "ОГРНИП 320435000030462\n\n"
    "---\n\n"
    "ТОВАРЫ\n\n"
    "Товары — одежда и аксессуары, представленные на сайте.\n"
    "Описание, фото и цена указаны на странице товара.\n"
    "Фотографии являются иллюстрациями и могут немного отличаться от фактического вида.\n\n"
    "---\n\n"
    "ЗАКАЗ\n\n"
    "Заказ оформляется покупателем самостоятельно через сайт.\n"
    "После оформления необходимо оплатить заказ в течение 30 минут, иначе он отменяется автоматически.\n\n"
    "Изготовление заказа занимает от 14 до 45 календарных дней с момента оплаты.\n"
    "В отдельных случаях срок может быть увеличен — об этом покупателя уведомляют.\n\n"
    "---\n\n"
    "ПРЕДЗАКАЗ\n\n"
    "Метка «Предзаказ» означает, что товара нет в наличии и он изготавливается под клиента.\n"
    "Отправка такого товара осуществляется не ранее чем через 21 день после оплаты.\n"
    "Сроки могут уточняться дополнительно через уведомления.\n\n"
    "---\n\n"
    "ОПЛАТА\n\n"
    "Оплата производится банковской картой на сайте.\n"
    "Продажа осуществляется по 100% предоплате.\n\n"
    "Цена фиксируется в момент оформления заказа и не изменяется.\n\n"
    "---\n\n"
    "ДОСТАВКА\n\n"
    "Доставка выполняется через:\n"
    "Почту России\n"
    "СДЭК\n\n"
    "Минимальный срок доставки — от 7 дней после оплаты.\n"
    "Срок зависит от региона и рассчитывается индивидуально.\n"
    "Стоимость доставки оплачивается покупателем.\n\n"
    "Доставка возможна по России, странам СНГ и по миру.\n"
    "Международная доставка — стоимость товара + 1000 рублей.\n\n"
    "Срок хранения заказа в пункте выдачи — 7 дней.\n\n"
    "---\n\n"
    "ВОЗВРАТ\n\n"
    "Если обнаружен производственный брак — товар можно вернуть.\n"
    "Если не подошёл размер, фасон или внешний вид — возврат возможен при сохранении товарного состояния.\n\n"
    "Условия возврата:\n"
    "— без следов носки\n"
    "— сохранена упаковка\n"
    "— сохранена бирка\n"
    "— товарный вид не нарушен\n\n"
    "Срок обращения:\n"
    "— при браке — в течение 3 дней после получения\n"
    "— если не подошёл — в течение 7 дней после получения\n\n"
    "Доставка при возврате оплачивается покупателем.\n"
    "Стоимость первоначальной доставки не возвращается.\n\n"
    "Возврат денежных средств производится после получения товара магазином:\n"
    "обычно до 10 дней, в отдельных случаях — до 30 рабочих дней (зависит от банка).\n\n"
    "---\n\n"
    "УХОД ЗА ОДЕЖДОЙ\n\n"
    "Рекомендуется:\n"
    "— ручная или деликатная стирка при 15–30°C\n"
    "— стирать изделие вывернутым наизнанку\n"
    "— использовать умеренное количество моющих средств\n"
    "— не использовать отбеливатели\n"
    "— не замачивать\n"
    "— не тереть места с нанесённым рисунком\n"
    "— не выжимать скручиванием\n"
    "— стирать отдельно от других вещей\n\n"
    "Сушить горизонтально, без прямого солнца.\n"
    "Гладить с изнаночной стороны, при необходимости — через ткань.\n\n"
    "---\n\n"
    "Если ассистент не располагает нужной информацией, он сообщает об этом и предлагает подключить менеджера для уточнения.\n"
)

# Промт для "Спросить у ИИ" (когда пользователь нажимает кнопку в товаре)
AI_PRODUCT_PROMPT = (
    "AI Product Assistant — PSIH\n\n"
    "Ассистент отвечает на вопросы о конкретном товаре, используя данные, полученные из бэкенда.\n"
    "Контекст содержит фактическую информацию о товаре: название, описание, цену, доступные цвета, размеры, состав, особенности, рекомендации по уходу и другие характеристики.\n\n"
    "Ответ формируется на основе этих данных.\n"
    "Никакая информация не добавляется от себя.\n\n"
    "Ассистент объясняет характеристики товара, помогает понять различия, свойства, детали изделия и условия использования.\n"
    "Ответ даётся по сути вопроса, без рекламных формулировок и без попытки «продать».\n\n"
    "Фразы не повторяются шаблонно — формулировка каждый раз естественная, но смысл остаётся точным.\n"
    "Ответ не выходит за пределы переданного контекста.\n\n"
    "Если нужной информации в данных нет, ассистент прямо сообщает, что в доступной информации этого нет, и уточняет, хочет ли клиент, чтобы подключился менеджер для уточнения.\n\n"
    "Язык ответа всегда совпадает с языком вопроса клиента.\n\n"
    "Ассистент может:\n"
    "— пояснять описание товара простыми словами\n"
    "— называть цену и характеристики\n"
    "— перечислять доступные варианты (цвет, размер и т.д.), если они есть в данных\n"
    "— объяснять рекомендации по уходу\n"
    "— уточнять различия между вариантами товара\n"
    "— отвечать только на то, о чём спросили\n\n"
    "Ассистент не делает предположений о наличии, сроках доставки, изменениях заказа или любых данных, которых нет в контексте.\n"
    "Он работает как интерпретатор карточки товара, а не как менеджер магазина.\n"
)

FAQ_INLINE_RAW = ""

CATALOG_API_URL = os.getenv("CATALOG_API_URL")
CATALOG_AUTH_TOKEN = os.getenv("CATALOG_AUTH_TOKEN")
CATALOG_AUTH_USERNAME = os.getenv("CATALOG_AUTH_USERNAME") or os.getenv("CATALOG_USERNAME") or os.getenv("CATALOG_USER")
CATALOG_AUTH_PASSWORD = os.getenv("CATALOG_AUTH_PASSWORD") or os.getenv("CATALOG_PASSWORD") or os.getenv("CATALOG_PASS")
CATALOG_TOKEN_TTL_SECONDS = int(os.getenv("CATALOG_TOKEN_TTL_SECONDS", "3300"))
CATALOG_CACHE_TTL_SECONDS = int(os.getenv("CATALOG_CACHE_TTL_SECONDS", "60"))
_catalog_cache: Dict[str, Any] = {"ts": 0.0, "categories": None, "products": {}, "product": {}, "product_variants": {}, "color_images": {}}
_catalog_token_cache: Dict[str, Any] = {"ts": 0.0, "token": None}

_user_state: Dict[str, Dict[str, Any]] = {}

def _state_key(platform: str, peer_id: str) -> str:
    return f"{platform}:{peer_id}"

def _get_state(platform: str, peer_id: str) -> Dict[str, Any]:
    return _user_state.setdefault(_state_key(platform, peer_id), {})

def _clear_state(platform: str, peer_id: str) -> None:
    _user_state.pop(_state_key(platform, peer_id), None)

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())

def _format_price(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    try:
        dec_value = Decimal(str(value))
    except Exception:
        return str(value)
    if dec_value == dec_value.to_integral():
        return str(dec_value.quantize(Decimal("1")))
    text = format(dec_value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text

def _normalize_price_text(text: str) -> str:
    if not text:
        return text
    def _repl(match: re.Match) -> str:
        whole = match.group(0)
        int_part = match.group(1)
        frac = match.group(2) or ""
        if frac == "00":
            return int_part
        return whole.replace(",", ".")
    return re.sub(r"\b(\d+)(?:[.,](\d{2}))\b", _repl, text)

def _faq_slug(text: str) -> str:
    base = _normalize(text)
    base = re.sub(r"[^a-z0-9]+", "_", base)
    return base.strip("_") or "faq"

def _find_faq_file() -> Optional[Path]:
    candidates: List[Optional[str]] = [
        os.getenv("FAQ_FILE"),
        "/app/faq.md",
        str(Path(__file__).resolve().parent / "faq.md"),
        str(Path.cwd() / "faq.md"),
        str(Path(__file__).resolve().parent.parent / "faq.md"),
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(c)
        if p.exists() and p.is_file():
            return p
    return None

def _parse_faq_markdown(raw: str) -> Dict[str, Dict[str, str]]:
    items: Dict[str, Dict[str, str]] = {}
    lines = (raw or "").splitlines()
    current_q: Optional[str] = None
    current_a: List[str] = []
    in_brand_block = False
    brand_lines: List[str] = []

    def flush() -> None:
        nonlocal current_q, current_a
        if not current_q:
            return
        answer = "\n".join([l.rstrip() for l in current_a if l.strip()])
        if answer:
            slug = _faq_slug(current_q.split("(")[0].replace("Q:", "").strip().rstrip("?"))
            if slug not in items:
                items[slug] = {"title": current_q.strip(), "answer": answer.strip()}
        current_q = None
        current_a = []

    for line in lines:
        s = line.lstrip()
        if s.strip().startswith("--- Brand Information"):
            flush()
            in_brand_block = True
            continue
        if in_brand_block:
            if s.strip().startswith("--- End Brand"):
                in_brand_block = False
                continue
            brand_lines.append(line)
            continue

        if s.startswith("Q:"):
            flush()
            current_q = s.replace("Q:", "").strip()
            continue
        if s.startswith("A:"):
            current_a.append(s.replace("A:", "").strip())
            continue
        if s.startswith("EN:"):
            continue
        if current_q and s.strip() and not s.strip().startswith("---"):
            current_a.append(line.rstrip())

    flush()

    brand_text = "\n".join([l.rstrip() for l in brand_lines if l.strip()]).strip()
    if brand_text:
        items["brand_info"] = {"title": "О бренде ПСИХ", "answer": brand_text}

    return items

def load_faq() -> None:
    global FAQ_ITEMS, FAQ_ORDER
    p = _find_faq_file()
    faq_mode = str(os.getenv("FAQ_MODE") or "inline").strip().lower()
    raw = None
    if faq_mode == "file" and p:
        raw = p.read_text(encoding="utf-8", errors="ignore")
    if raw is None:
        raw = FAQ_INLINE_RAW
    items = _parse_faq_markdown(raw)
    preferred_order = [
        "delivery_time",
        "tell_me_the_status_of_order_xxxxx",
        "what_is_pre_order",
        "how_long_is_pre_order",
        "return_policy",
        "size_guide",
        "why_is_shipping_delayed",
        "is_it_a_pre_order",
        "what_if_my_order_has_both_pre_order_and_in_stock_items",
        "international_shipping",
        "which_carriers_do_you_use",
        "how_do_i_choose_a_size",
        "which_items_are_non_returnable",
        "how_should_i_care_for_psih_items",
        "what_if_my_item_is_defective",
        "brand_info",
    ]
    ordered: List[str] = []
    for key in preferred_order:
        if key in items:
            ordered.append(key)
    for key in items.keys():
        if key not in ordered:
            ordered.append(key)
    FAQ_ITEMS = items
    FAQ_ORDER = ordered
    src = str(p) if (faq_mode == "file" and p) else "inline"
    logging.info("FAQ loaded: %s items from %s", len(FAQ_ITEMS), src)

def ensure_faq_loaded() -> None:
    if not FAQ_ITEMS:
        load_faq()

def _tg_to_html(text: str) -> str:
    escaped = html.escape(text or "")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped

def _tg_main_text() -> str:
    return "<b>PSIH</b>\n<blockquote>Выберите раздел ниже или просто напишите вопрос</blockquote>"

def _tg_faq_text(page: int = 1) -> str:
    ensure_faq_loaded()
    if not FAQ_ORDER:
        return "<b>FAQ</b>\n<blockquote>Пока пусто: раздел ещё не настроен</blockquote>"
    total = len(FAQ_ORDER)
    page_size = TG_FAQ_PAGE_SIZE
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), total_pages))
    return (
        "<b>FAQ</b>\n"
        f"<blockquote>Тем: {total}. Страница {page}/{total_pages}.\n"
        "Выберите тему ниже.</blockquote>"
    )

def _tg_faq_item_text(item_id: str) -> str:
    ensure_faq_loaded()
    item = FAQ_ITEMS.get(item_id)
    if not item:
        return "<b>FAQ</b>\n<blockquote>Не нашёл эту тему</blockquote>"
    title = _tg_to_html(item["title"])
    answer = _tg_to_html(item["answer"])
    return f"<b>{title}</b>\n\n<blockquote>{answer}</blockquote>"

def _tg_kb(rows: List[List[Dict[str, str]]]) -> types.InlineKeyboardMarkup:
    inline_keyboard: List[List[types.InlineKeyboardButton]] = []
    for row in rows:
        inline_keyboard.append([
            types.InlineKeyboardButton(text=b["text"], callback_data=b["data"])
            for b in row
        ])
    return types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

def tg_kb_main() -> types.InlineKeyboardMarkup:
    return _tg_kb([
        [{"text": "🛍️ Товары", "data": "m:cat"}],
        [{"text": "📌 FAQ", "data": "m:faq"}],
        [{"text": "👤 Позвать менеджера", "data": "m:manager"}],
    ])

def tg_kb_faq_menu(page: int = 1) -> types.InlineKeyboardMarkup:
    ensure_faq_loaded()
    total = len(FAQ_ORDER)
    page_size = TG_FAQ_PAGE_SIZE
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    buttons: List[List[Dict[str, str]]] = []
    row: List[Dict[str, str]] = []
    for idx, item_id in enumerate(FAQ_ORDER[start:end], start=start):
        title = FAQ_ITEMS.get(item_id, {}).get("title", item_id)
        ru = title.split("(")[-1].rstrip(")") if "(" in title and ")" in title else title
        label = ru[:28]
        row.append({"text": label, "data": f"m:faq:item:{idx}:{page}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if total_pages > 1:
        nav: List[Dict[str, str]] = []
        if page > 1:
            nav.append({"text": "◀️", "data": f"m:faq:page:{page - 1}"})
        if page < total_pages:
            nav.append({"text": "▶️", "data": f"m:faq:page:{page + 1}"})
        if nav:
            buttons.append(nav)
    if not buttons:
        buttons.append([{"text": "👤 Позвать менеджера", "data": "m:manager"}])
    buttons.append([{"text": "⬅️ Назад", "data": "m:home"}])
    return _tg_kb(buttons)

def tg_kb_faq_item(item_id: str, page: int = 1) -> types.InlineKeyboardMarkup:
    return _tg_kb([
        [{"text": "⬅️ Назад", "data": f"m:faq:page:{max(1, int(page or 1))}"}],
        [{"text": "👤 Позвать менеджера", "data": "m:manager"}],
        [{"text": "🏠 Меню", "data": "m:home"}],
    ])

def _vk_main_text() -> str:
    return "PSIH\n\nВыберите раздел ниже или просто напишите вопрос."

def _vk_faq_text(page: int = 1) -> str:
    ensure_faq_loaded()
    if not FAQ_ORDER:
        return "FAQ\n\nПока пусто: раздел ещё не настроен"
    total = len(FAQ_ORDER)
    page_size = VK_FAQ_PAGE_SIZE
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), total_pages))
    return f"FAQ\n\nТем: {total}. Страница {page}/{total_pages}.\nВыберите тему:"

def _vk_faq_item_text(item_id: str) -> str:
    ensure_faq_loaded()
    item = FAQ_ITEMS.get(item_id)
    if not item:
        return "FAQ\n\nТема не найдена."
    title = item["title"]
    answer = re.sub(r"\*\*(.+?)\*\*", r"\1", item["answer"])
    return f"{title}\n\n«{answer}»"

def vk_kb_main() -> Optional[str]:
    kb = VkKeyboard(one_time=False, inline=True)
    kb.add_button("🛍️ Товары", color=VkKeyboardColor.PRIMARY, payload={"cmd": "cat"})
    kb.add_line()
    kb.add_button("📌 FAQ", color=VkKeyboardColor.SECONDARY, payload={"cmd": "faq"})
    kb.add_line()
    kb.add_button("👤 Менеджер", color=VkKeyboardColor.NEGATIVE, payload={"cmd": "manager"})
    return kb.get_keyboard()

def vk_kb_faq_menu(page: int = 1) -> Optional[str]:
    ensure_faq_loaded()
    total = len(FAQ_ORDER)
    page_size = VK_FAQ_PAGE_SIZE
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    kb = VkKeyboard(one_time=False, inline=True)
    for item_id in FAQ_ORDER[start:end]:
        title = FAQ_ITEMS.get(item_id, {}).get("title", item_id)
        ru = title.split("(")[-1].rstrip(")") if "(" in title and ")" in title else title
        kb.add_button(ru[:38], color=VkKeyboardColor.SECONDARY, payload={"cmd": "faq_item", "id": item_id, "page": page})
        kb.add_line()
    if total_pages > 1:
        if page > 1:
            kb.add_button("◀️", color=VkKeyboardColor.PRIMARY, payload={"cmd": "faq_page", "page": page - 1})
        if page < total_pages:
            kb.add_button("▶️", color=VkKeyboardColor.PRIMARY, payload={"cmd": "faq_page", "page": page + 1})
        kb.add_line()
    kb.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY, payload={"cmd": "home"})
    return kb.get_keyboard()

def vk_kb_faq_item(item_id: str, page: int = 1) -> Optional[str]:
    kb = VkKeyboard(one_time=False, inline=True)
    kb.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY, payload={"cmd": "faq_page", "page": max(1, int(page or 1))})
    kb.add_line()
    kb.add_button("👤 Менеджер", color=VkKeyboardColor.NEGATIVE, payload={"cmd": "manager"})
    kb.add_line()
    kb.add_button("🏠 Меню", color=VkKeyboardColor.SECONDARY, payload={"cmd": "home"})
    return kb.get_keyboard()

def vk_kb_categories(categories: List[Dict[str, Any]]) -> Optional[str]:
    kb = VkKeyboard(one_time=False, inline=True)
    for c in categories[:6]:
        # Пытаемся получить slug, если нет - используем id
        cid = str(c.get("slug") or c.get("id") or "")
        name = str(c.get("name") or "Категория")[:38]
        if not cid:
            logging.warning(f"Category without ID/slug: {c}")
            continue
        kb.add_button(name, color=VkKeyboardColor.PRIMARY, payload={"cmd": "cat_open", "id": cid, "page": 1})
        kb.add_line()
    kb.add_button("🏠 Меню", color=VkKeyboardColor.SECONDARY, payload={"cmd": "home"})
    return kb.get_keyboard()

def vk_kb_products(category_id: str, page: int, products: List[Dict[str, Any]], has_next: bool) -> Optional[str]:
    kb = VkKeyboard(one_time=False, inline=True)
    for p in products[:6]:
        kb.add_button(str(p.get("name") or "Товар")[:38], color=VkKeyboardColor.SECONDARY, payload={"cmd": "prod", "id": p.get("id"), "cat": category_id, "page": page})
        kb.add_line()
    nav_added = False
    if page > 1:
        kb.add_button("⬅️", color=VkKeyboardColor.PRIMARY, payload={"cmd": "cat_open", "id": category_id, "page": page - 1})
        nav_added = True
    if has_next:
        if nav_added:
            kb.add_button("➡️", color=VkKeyboardColor.PRIMARY, payload={"cmd": "cat_open", "id": category_id, "page": page + 1})
        else:
            kb.add_button("➡️", color=VkKeyboardColor.PRIMARY, payload={"cmd": "cat_open", "id": category_id, "page": page + 1})
        nav_added = True
    if nav_added:
        kb.add_line()
    kb.add_button("⬅️ Категории", color=VkKeyboardColor.PRIMARY, payload={"cmd": "cat"})
    kb.add_line()
    kb.add_button("🏠 Меню", color=VkKeyboardColor.SECONDARY, payload={"cmd": "home"})
    return kb.get_keyboard()

def vk_kb_product(product_id: str, category_id: Optional[str] = None, page: Optional[int] = None, colors: Optional[List[str]] = None) -> Optional[str]:
    kb = VkKeyboard(one_time=False, inline=True)
    if colors:
        for idx, c in enumerate(colors[:6]):
            kb.add_button(c[:38], color=VkKeyboardColor.SECONDARY, payload={"cmd": "color", "id": product_id, "ci": idx, "cat": category_id, "page": page})
            kb.add_line()
    kb.add_button("🧠 Спросить ИИ", color=VkKeyboardColor.PRIMARY, payload={"cmd": "ask_ai", "id": product_id})
    kb.add_line()
    if category_id and page:
        kb.add_button("⬅️ Назад", color=VkKeyboardColor.PRIMARY, payload={"cmd": "cat_open", "id": category_id, "page": page})
    else:
        kb.add_button("⬅️ Каталог", color=VkKeyboardColor.PRIMARY, payload={"cmd": "cat"})
    kb.add_line()
    kb.add_button("🏠 Меню", color=VkKeyboardColor.SECONDARY, payload={"cmd": "home"})
    return kb.get_keyboard()

async def vk_send_message(peer_id: int, message: str, keyboard: Optional[str] = None, attachment: Optional[str] = None) -> None:
    if not vk:
        logging.warning("VK send skipped: VK is not initialized (check VK_TOKEN/VK_GROUP_ID).")
        return
    payload: Dict[str, Any] = {"peer_id": peer_id, "message": message, "random_id": 0}
    if keyboard:
        payload["keyboard"] = keyboard
    if attachment:
        payload["attachment"] = attachment
    try:
        await asyncio.to_thread(vk.messages.send, **payload)
    except Exception as e:
        error_msg = str(e)
        if "912" in error_msg or "chat bot feature" in error_msg.lower():
            logging.error("❌ VK send failed: Необходимо включить 'Возможности ботов' в настройках сообщества VK!")
            logging.error("   Инструкция: Настройки → Сообщения → Настройки для бота → Включить 'Возможности ботов'")
        else:
            logging.error("❌ VK send failed: %s", error_msg)

_vk_photo_cache: Dict[str, Dict[str, Any]] = {}

async def vk_upload_photo_from_url(url: str) -> Optional[str]:
    if not vk or not url:
        return None
    cached = _vk_photo_cache.get(url)
    if cached and _catalog_is_fresh(cached.get("ts", 0.0)):
        return cached.get("attachment")

    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    content: Optional[bytes] = None
    try:
        async with current_session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None
            content = await resp.read()
    except Exception:
        return None
    finally:
        if current_session != http_session:
            await current_session.close()

    try:
        upload_url = await asyncio.to_thread(vk.photos.getMessagesUploadServer)
        upload_url = upload_url["upload_url"]
        current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
        try:
            form = aiohttp.FormData()
            form.add_field("photo", content, filename="photo.jpg", content_type="image/jpeg")
            async with current_session.post(upload_url, data=form, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                upload_result = await resp.json()
        finally:
            if current_session != http_session:
                await current_session.close()

        photo_data = await asyncio.to_thread(
            vk.photos.saveMessagesPhoto,
            photo=upload_result["photo"],
            server=upload_result["server"],
            hash=upload_result["hash"],
        )
        att = f"photo{photo_data[0]['owner_id']}_{photo_data[0]['id']}"
        _vk_photo_cache[url] = {"ts": datetime.utcnow().timestamp(), "attachment": att}
        return att
    except Exception:
        return None

async def request_manager(db: AsyncSession, chat_id: int, peer_id: str, chat_name: str, messager: str) -> None:
    await update_chat_waiting(db=db, chat_id=chat_id, waiting=True)
    await update_chat_ai(db=db, chat_id=chat_id, ai=False)
    await updates_manager.broadcast(json.dumps({
        "type": "chat_update",
        "chat_id": chat_id,
        "waiting": True,
        "ai": False
    }))
    notification_manager = notifications.get_notification_manager()
    if notification_manager:
        await notification_manager.send_waiting_notification(
            chat_id=int(peer_id) if str(peer_id).isdigit() else peer_id,
            chat_name=chat_name,
            messager=messager
        )

def _catalog_is_fresh(ts: float) -> bool:
    return (datetime.utcnow().timestamp() - ts) < CATALOG_CACHE_TTL_SECONDS

def _catalog_token_is_fresh(ts: float) -> bool:
    return (datetime.utcnow().timestamp() - ts) < CATALOG_TOKEN_TTL_SECONDS

async def _catalog_get_token() -> Optional[str]:
    base = (CATALOG_API_URL or "").rstrip("/")
    if not base or not CATALOG_AUTH_USERNAME or not CATALOG_AUTH_PASSWORD:
        return None

    cached = _catalog_token_cache.get("token")
    if cached and _catalog_token_is_fresh(float(_catalog_token_cache.get("ts") or 0.0)):
        return str(cached)

    url = f"{base}/api/auth/token"
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        async with current_session.post(
            url,
            data={"username": CATALOG_AUTH_USERNAME, "password": CATALOG_AUTH_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            content_type = resp.headers.get("content-type", "")
            if resp.status != 200:
                text = await resp.text()
                _catalog_cache["last_error"] = f"{resp.status} от /api/auth/token: {text[:200]}"
                return None
            if "application/json" in content_type:
                data = await resp.json()
            else:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except Exception:
                    data = None
            if not isinstance(data, dict):
                _catalog_cache["last_error"] = "Неожиданный ответ /api/auth/token"
                return None
            token = data.get("access_token") or data.get("token")
            if not token:
                _catalog_cache["last_error"] = "Токен не найден в ответе /api/auth/token"
                return None
            _catalog_token_cache["token"] = str(token)
            _catalog_token_cache["ts"] = datetime.utcnow().timestamp()
            return str(token)
    except Exception:
        _catalog_cache["last_error"] = "Ошибка запроса /api/auth/token"
        return None
    finally:
        if current_session != http_session:
            await current_session.close()

async def _catalog_get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    base = (CATALOG_API_URL or "").rstrip("/")
    if not base:
        _catalog_cache["last_error"] = "CATALOG_API_URL не задан"
        return None
    url = f"{base}{path}"
    headers: Dict[str, str] = {}
    token = CATALOG_AUTH_TOKEN
    if not token and CATALOG_AUTH_USERNAME and CATALOG_AUTH_PASSWORD:
        token = await _catalog_get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        async with current_session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                text = await resp.text()
                _catalog_cache["last_error"] = f"{resp.status} от {path}: {text[:200]}"
                return None
            _catalog_cache["last_error"] = None
            return await resp.json()
    except Exception:
        _catalog_cache["last_error"] = f"Ошибка запроса {path}"
        return None
    finally:
        if current_session != http_session:
            await current_session.close()

def _catalog_abs_url(raw_url: str) -> str:
    base = (CATALOG_API_URL or "").rstrip("/") + "/"
    return urljoin(base, raw_url)

def _extract_image_url(obj: Any) -> Optional[str]:
    if isinstance(obj, str) and obj:
        return _catalog_abs_url(obj) if not obj.startswith("http") else obj
    if isinstance(obj, dict):
        for k in ("url", "image_url", "src", "path", "link", "file"):
            v = obj.get(k)
            if isinstance(v, str) and v:
                return _catalog_abs_url(v) if not v.startswith("http") else v
    return None

def _normalize_sections(raw_sections: Any) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []
    if not isinstance(raw_sections, list):
        return sections
    for s in raw_sections:
        if isinstance(s, str):
            title = ""
            content = s.strip()
        elif isinstance(s, dict):
            title = str(s.get("title") or s.get("name") or s.get("label") or "").strip()
            content = str(s.get("content") or s.get("text") or s.get("body") or "").strip()
        else:
            continue
        if not content and not title:
            continue
        sections.append({"title": title, "content": content})
    return sections

def _flatten_categories(tree: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    stack: List[Any] = []
    if isinstance(tree, list):
        stack.extend(tree)
    elif isinstance(tree, dict):
        stack.append(tree)
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        slug = node.get("slug") or node.get("id")
        name = node.get("name") or node.get("title")
        if slug and name:
            out.append({"slug": str(slug), "name": str(name)})
        children = node.get("children") or node.get("items") or node.get("categories")
        if isinstance(children, list):
            stack.extend(children)
    uniq: Dict[str, Dict[str, Any]] = {}
    for c in reversed(out):
        uniq[c["slug"]] = c
    return list(uniq.values())

async def catalog_get_categories() -> Optional[List[Dict[str, Any]]]:
    if _catalog_cache.get("categories") and _catalog_is_fresh(_catalog_cache.get("ts", 0.0)):
        return _catalog_cache["categories"]
    data = await _catalog_get_json("/api/categories")
    categories = _flatten_categories(data)
    if categories:
        _catalog_cache["categories"] = categories
        _catalog_cache["ts"] = datetime.utcnow().timestamp()
        return categories
    return None

def _normalize_product(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    pid = raw.get("id") or raw.get("product_id") or raw.get("uuid") or raw.get("slug")
    if pid is None:
        return None
    slug = str(raw.get("slug") or raw.get("product_slug") or raw.get("base_slug") or "").strip()
    name = str(
        raw.get("name") or raw.get("title") or raw.get("product_name") or
        raw.get("base_title") or raw.get("productName") or raw.get("label") or
        raw.get("display_name") or raw.get("displayName") or ""
    ).strip()
    if not name or name.isdigit():
        name = slug if slug and not slug.isdigit() else ""
    if not name:
        name = f"Товар {pid}"
    description = str(raw.get("description") or raw.get("desc") or "").strip()
    composition = str(raw.get("composition") or "").strip()
    fit = str(raw.get("fit") or "").strip()
    meta_raw = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    meta = {
        "care": str(meta_raw.get("care") or raw.get("meta_care") or "").strip(),
        "shipping": str(meta_raw.get("shipping") or raw.get("meta_shipping") or "").strip(),
        "returns": str(meta_raw.get("returns") or raw.get("meta_returns") or "").strip(),
    }
    sections = _normalize_sections(raw.get("custom_sections") or raw.get("sections") or raw.get("accordions") or [])
    url = str(raw.get("url") or raw.get("link") or "").strip()
    price = raw.get("price") or raw.get("cost")
    base_id = raw.get("product_id") or raw.get("base_product_id") or raw.get("baseProductId")
    main_category = raw.get("main_category") if isinstance(raw.get("main_category"), dict) else {}
    category_names: List[str] = []
    main_name = str(main_category.get("name") or "").strip()
    if main_name:
        category_names.append(main_name)
    category_path = raw.get("categoryPath")
    if isinstance(category_path, list):
        for it in category_path:
            if isinstance(it, dict):
                cname = str(it.get("name") or it.get("title") or "").strip()
            else:
                cname = str(it).strip()
            if cname:
                category_names.append(cname)

    images: List[str] = []
    if isinstance(raw.get("images"), list):
        images = [str(x) for x in raw.get("images") if x]
    elif isinstance(raw.get("image"), str) and raw.get("image"):
        images = [raw.get("image")]

    colors: List[str] = []
    images_by_color: Dict[str, List[str]] = {}

    raw_colors = raw.get("colors")
    if isinstance(raw_colors, list):
        for c in raw_colors:
            if isinstance(c, str):
                colors.append(c)
            elif isinstance(c, dict):
                cname = str(c.get("name") or c.get("title") or c.get("color") or "").strip()
                if cname:
                    colors.append(cname)
                cimgs: List[str] = []
                if isinstance(c.get("images"), list):
                    cimgs = [str(x) for x in c.get("images") if x]
                if cname and cimgs:
                    images_by_color[cname] = cimgs

    raw_color_images = raw.get("color_images")
    if isinstance(raw_color_images, dict):
        for k, v in raw_color_images.items():
            if isinstance(v, list):
                images_by_color[str(k)] = [str(x) for x in v if x]

    return {
        "id": str(pid),
        "base_id": str(base_id) if base_id is not None else None,
        "name": name,
        "slug": slug,
        "description": description,
        "composition": composition,
        "fit": fit,
        "meta": meta,
        "sections": sections,
        "url": url,
        "price": price,
        "images": images,
        "colors": colors,
        "images_by_color": images_by_color,
        "categories": category_names,
    }

async def catalog_get_products(category_id: str, page: int = 1, limit: int = 8) -> Optional[Dict[str, Any]]:
    page = max(1, int(page or 1))
    limit = max(1, int(limit or 8))
    
    # Проверяем кеш всех товаров категории для локальной пагинации
    all_key = f"{category_id}:all"
    cached_all = _catalog_cache["products"].get(all_key)
    if cached_all and _catalog_is_fresh(cached_all["ts"]):
        all_products = cached_all["data"]
        start = (page - 1) * limit
        normalized = all_products[start:start + limit]
        has_next = (start + limit) < len(all_products)
        return {"items": normalized, "has_next": has_next}

    offset = (page - 1) * limit
    data = await _catalog_get_json(f"/api/categories/{category_id}")
    used_products_endpoint = False
    used_params: Optional[Dict[str, Any]] = None
    if data is None:
        params_variants: List[Dict[str, Any]] = [
            {"category": category_id, "page": page, "limit": limit},
            {"category_slug": category_id, "page": page, "limit": limit},
            {"categorySlug": category_id, "page": page, "limit": limit},
            {"category": category_id, "offset": offset, "limit": limit},
            {"category_slug": category_id, "offset": offset, "limit": limit},
            {"category": category_id, "skip": offset, "limit": limit},
            {"category_slug": category_id, "skip": offset, "limit": limit},
            {"category": category_id, "page": page, "size": limit},
            {"category_slug": category_id, "page": page, "size": limit},
        ]
        for params in params_variants:
            data = await _catalog_get_json("/api/products", params=params)
            if data is not None:
                used_params = params
                used_products_endpoint = True
                break
    items: Any = None
    if isinstance(data, dict):
        items = data.get("products") or data.get("items") or data.get("data") or data.get("results")
    if items is None:
        items = data
    if not isinstance(items, list):
        return None

    # Если нет данных о пагинации, пробуем собрать все страницы вручную
    if used_products_endpoint and used_params and isinstance(data, dict):
        total_from_api = data.get("total") or data.get("count") or data.get("totalCount")
        skip_from_api = data.get("skip") or data.get("offset")
        has_pagination_meta = isinstance(total_from_api, int) and isinstance(skip_from_api, int)
        if not has_pagination_meta:
            items = list(items)
            next_page = page
            next_offset = offset
            for _ in range(1, 20):
                next_params = dict(used_params)
                if "page" in next_params:
                    next_page += 1
                    next_params["page"] = next_page
                    if "offset" in next_params or "skip" in next_params:
                        next_offset += limit
                        if "offset" in next_params:
                            next_params["offset"] = next_offset
                        if "skip" in next_params:
                            next_params["skip"] = next_offset
                else:
                    next_offset += limit
                    if "offset" in next_params:
                        next_params["offset"] = next_offset
                    if "skip" in next_params:
                        next_params["skip"] = next_offset
                data_page = await _catalog_get_json("/api/products", params=next_params)
                if data_page is None:
                    break
                page_items: Any = None
                if isinstance(data_page, dict):
                    page_items = data_page.get("products") or data_page.get("items") or data_page.get("data") or data_page.get("results")
                if page_items is None:
                    page_items = data_page
                if not isinstance(page_items, list) or not page_items:
                    break
                items.extend(page_items)
                if len(page_items) < limit:
                    break

    uniq: Dict[str, Dict[str, Any]] = {}
    variants_by_product: Dict[str, Dict[str, Any]] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue
        base_pid = raw.get("product_id") or raw.get("base_product_id") or raw.get("baseProductId")
        pid = raw.get("id") or raw.get("product_id") or raw.get("base_product_id") or raw.get("uuid")
        if pid is None:
            continue
        slug = str(raw.get("slug") or raw.get("product_slug") or raw.get("base_slug") or "").strip()
        # Расширенный поиск имени товара
        name = str(
            raw.get("name") or raw.get("title") or raw.get("product_name") or 
            raw.get("base_title") or raw.get("productName") or raw.get("label") or 
            raw.get("display_name") or raw.get("displayName") or ""
        ).strip()
        if not name or name.isdigit():
            name = slug if slug and not slug.isdigit() else ""
        if not name:
            name = f"Товар {pid}"
        description = str(raw.get("description") or raw.get("desc") or "").strip()
        composition = str(raw.get("composition") or "").strip()
        fit = str(raw.get("fit") or "").strip()
        meta_raw = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        meta = {
            "care": str(meta_raw.get("care") or raw.get("meta_care") or "").strip(),
            "shipping": str(meta_raw.get("shipping") or raw.get("meta_shipping") or "").strip(),
            "returns": str(meta_raw.get("returns") or raw.get("meta_returns") or "").strip(),
        }
        sections = _normalize_sections(raw.get("custom_sections") or raw.get("sections") or raw.get("accordions") or [])
        composition = str(raw.get("composition") or "").strip()
        fit = str(raw.get("fit") or "").strip()
        meta_raw = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        meta = {
            "care": str(meta_raw.get("care") or raw.get("meta_care") or "").strip(),
            "shipping": str(meta_raw.get("shipping") or raw.get("meta_shipping") or "").strip(),
            "returns": str(meta_raw.get("returns") or raw.get("meta_returns") or "").strip(),
        }
        sections = _normalize_sections(raw.get("custom_sections") or raw.get("sections") or raw.get("accordions") or [])
        url = str(raw.get("url") or raw.get("link") or "").strip()
        price = raw.get("price") or raw.get("cost")
        main_category = raw.get("main_category") if isinstance(raw.get("main_category"), dict) else {}
        category_names: List[str] = []
        main_name = str(main_category.get("name") or "").strip()
        if main_name:
            category_names.append(main_name)
        category_path = raw.get("categoryPath")
        if isinstance(category_path, list):
            for it in category_path:
                if isinstance(it, dict):
                    cname = str(it.get("name") or it.get("title") or "").strip()
                else:
                    cname = str(it).strip()
                if cname:
                    category_names.append(cname)
        images: List[str] = []
        for k in ("primary_image", "image", "cover"):
            u = _extract_image_url(raw.get(k))
            if u:
                images = [u]
                break
        if not images and isinstance(raw.get("images"), list):
            imgs = [_extract_image_url(x) for x in raw.get("images")]
            images = [x for x in imgs if x]
        product_id = str(base_pid) if base_pid is not None else str(pid)
        color_id = raw.get("color_id") or raw.get("colorId") or raw.get("product_color_id") or raw.get("productColorId") or raw.get("id")
        color_name = str(
            raw.get("label") or raw.get("color") or raw.get("color_name") or raw.get("colorName") or ""
        ).strip()
        if product_id not in variants_by_product:
            variants_by_product[product_id] = {
                "id": product_id,
                "base_id": str(base_pid) if base_pid is not None else None,
                "name": name,
                "slug": slug,
                "description": description,
                "composition": composition,
                "fit": fit,
                "meta": meta,
                "sections": sections,
                "url": url,
                "price": price,
                "images": images,
                "colors": [],
                "color_entries": [],
                "images_by_color": {},
                "categories": category_names,
            }
        if color_name:
            if color_name not in variants_by_product[product_id]["colors"]:
                variants_by_product[product_id]["colors"].append(color_name)
        if color_id is not None:
            variants_by_product[product_id]["color_entries"].append({"id": str(color_id), "name": color_name or ""})
            if images:
                variants_by_product[product_id]["images_by_color"][color_name or str(color_id)] = images
                _catalog_cache["color_images"][str(color_id)] = {"ts": datetime.utcnow().timestamp(), "data": images}
        uniq_key = product_id
        if uniq_key not in uniq:
            uniq[uniq_key] = {
                "id": product_id,
                "base_id": str(base_pid) if base_pid is not None else None,
                "name": name,
                "slug": slug,
                "description": description,
                "composition": composition,
                "fit": fit,
                "meta": meta,
                "sections": sections,
                "url": url,
                "price": price,
                "images": images,
                "colors": [],
                "color_entries": [],
                "images_by_color": {},
                "categories": category_names,
            }

    all_products = list(uniq.values())
    if variants_by_product:
        _catalog_cache["product_variants"] = {
            "ts": datetime.utcnow().timestamp(),
            "data": variants_by_product,
        }
    
    # Определяем, поддерживает ли API пагинацию
    api_has_pagination = False
    total_from_api = None
    if used_products_endpoint and isinstance(data, dict):
        total_from_api = data.get("total") or data.get("count") or data.get("totalCount")
        skip_from_api = data.get("skip") or data.get("offset")
        if isinstance(total_from_api, int) and isinstance(skip_from_api, int):
            api_has_pagination = True
    
    if api_has_pagination and total_from_api is not None:
        # API поддерживает пагинацию
        has_next = (offset + limit) < total_from_api
        normalized = all_products[:limit]
    else:
        # API не поддерживает пагинацию - кешируем все товары и делаем локальную нарезку
        _catalog_cache["products"][all_key] = {"ts": datetime.utcnow().timestamp(), "data": all_products}
        start = (page - 1) * limit
        normalized = all_products[start:start + limit]
        has_next = (start + limit) < len(all_products)
    
    return {"items": normalized, "has_next": has_next}


async def catalog_search_products(query: str, limit: int = 12) -> List[Dict[str, Any]]:
    if not query:
        return []
    limit = max(1, min(int(limit or 12), 100))
    params_variants: List[Dict[str, Any]] = [
        {"search": query, "limit": limit, "page": 1},
        {"q": query, "limit": limit, "page": 1},
        {"query": query, "limit": limit, "page": 1},
    ]
    data: Any = None
    for params in params_variants:
        data = await _catalog_get_json("/api/products", params=params)
        if data is not None:
            break
    items: Any = None
    if isinstance(data, dict):
        items = data.get("products") or data.get("items") or data.get("data") or data.get("results")
    if items is None:
        items = data
    if not isinstance(items, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        base_pid = raw.get("product_id") or raw.get("base_product_id") or raw.get("baseProductId")
        pid = raw.get("id") or raw.get("product_id") or raw.get("base_product_id") or raw.get("uuid")
        if pid is None:
            continue
        slug = str(raw.get("slug") or raw.get("product_slug") or raw.get("base_slug") or "").strip()
        name = str(
            raw.get("name") or raw.get("title") or raw.get("product_name") or
            raw.get("base_title") or raw.get("productName") or raw.get("label") or
            raw.get("display_name") or raw.get("displayName") or ""
        ).strip()
        if not name or name.isdigit():
            name = slug if slug and not slug.isdigit() else ""
        if not name:
            name = f"Товар {pid}"
        description = str(raw.get("description") or raw.get("desc") or "").strip()
        url = str(raw.get("url") or raw.get("link") or "").strip()
        price = raw.get("price") or raw.get("cost")
        images: List[str] = []
        for k in ("primary_image", "image", "cover"):
            u = _extract_image_url(raw.get(k))
            if u:
                images = [u]
                break
        if not images and isinstance(raw.get("images"), list):
            imgs = [_extract_image_url(x) for x in raw.get("images")]
            images = [x for x in imgs if x]
        color_name = str(
            raw.get("label") or raw.get("color") or raw.get("color_name") or raw.get("colorName") or ""
        ).strip()
        product_id = str(base_pid) if base_pid is not None else str(pid)
        entry = {
            "id": product_id,
            "base_id": str(base_pid) if base_pid is not None else None,
            "name": name,
            "slug": slug,
            "description": description,
            "composition": composition,
            "fit": fit,
            "meta": meta,
            "sections": sections,
            "url": url,
            "price": price,
            "images": images,
            "colors": [color_name] if color_name else [],
            "color_entries": [{"id": str(raw.get("color_id") or raw.get("colorId") or raw.get("id")), "name": color_name}] if color_name else [],
            "categories": [],
        }
        normalized.append(entry)
    return normalized

async def catalog_get_product(product_id: str) -> Optional[Dict[str, Any]]:
    logging.info(f"🛒 catalog_get_product called with product_id={product_id}")
    cached_variants = _catalog_cache.get("product_variants") or {}
    if cached_variants.get("data") and _catalog_is_fresh(cached_variants.get("ts", 0.0)):
        pv = cached_variants["data"].get(str(product_id))
        if pv:
            logging.info(f"🛒 Returning from variants cache")
            return pv
    cached = _catalog_cache["product"].get(product_id)
    if cached and _catalog_is_fresh(cached["ts"]):
        logging.info(f"🛒 Returning from product cache")
        return cached["data"]
    logging.info(f"🛒 Fetching from API: /api/products/{product_id}")
    base = await _catalog_get_json(f"/api/products/{product_id}")
    logging.info(f"🛒 API response keys: {list(base.keys()) if isinstance(base, dict) else type(base)}")
    if base is None:
        base = await _catalog_get_json(f"/api/products/slug/{product_id}")
    if not isinstance(base, dict):
        return None
    pid = base.get("id") or base.get("product_id") or base.get("uuid") or product_id
    slug = str(base.get("slug") or base.get("product_slug") or base.get("base_slug") or "").strip()
    name = str(
        base.get("name") or base.get("title") or base.get("product_name") or
        base.get("base_title") or base.get("productName") or base.get("label") or
        base.get("display_name") or base.get("displayName") or ""
    ).strip()
    if not name or name.isdigit():
        name = slug if slug and not slug.isdigit() else ""
    if not name:
        name = f"Товар {pid}"
    description = str(base.get("description") or base.get("desc") or "").strip()
    composition = str(base.get("composition") or "").strip()
    fit = str(base.get("fit") or "").strip()
    url = str(base.get("url") or base.get("link") or "").strip()
    price = base.get("price") or base.get("cost")
    base_id = base.get("product_id") or base.get("base_product_id") or base.get("baseProductId")
    meta_raw = base.get("meta") if isinstance(base.get("meta"), dict) else {}
    meta = {
        "care": str(meta_raw.get("care") or base.get("meta_care") or "").strip(),
        "shipping": str(meta_raw.get("shipping") or base.get("meta_shipping") or "").strip(),
        "returns": str(meta_raw.get("returns") or base.get("meta_returns") or "").strip(),
    }
    sections = _normalize_sections(base.get("custom_sections") or base.get("sections") or base.get("accordions") or [])
    if not sections and base_id is not None:
        sections_data = await _catalog_get_json(f"/api/products/{base_id}/sections")
        sections = _normalize_sections(sections_data)

    images: List[str] = []
    for k in ("primary_image", "image", "cover"):
        u = _extract_image_url(base.get(k))
        if u:
            images = [u]
            break
    if not images and isinstance(base.get("images"), list):
        imgs = [_extract_image_url(x) for x in base.get("images")]
        images = [x for x in imgs if x]

    color_entries: List[Dict[str, Any]] = []
    colors_data = base.get("colors") if isinstance(base.get("colors"), list) else None
    logging.info(f"🎨 catalog_get_product colors_data from response: {len(colors_data) if colors_data else 0} items")
    if isinstance(colors_data, list) and colors_data:
        for c in colors_data:
            if not isinstance(c, dict):
                continue
            cid = c.get("id") or c.get("product_color_id") or c.get("color_id")
            cname = str(c.get("label") or c.get("name") or c.get("title") or c.get("color") or c.get("value") or c.get("color_name") or "").strip()
            if cid is None or not cname:
                continue
            sizes_raw = c.get("sizes") if isinstance(c.get("sizes"), list) else []
            sizes: List[Dict[str, Any]] = []
            for s in sizes_raw:
                if not isinstance(s, dict):
                    continue
                size_name = str(s.get("size") or s.get("name") or s.get("label") or s.get("title") or "").strip()
                if not size_name:
                    continue
                sizes.append({
                    "name": size_name,
                    "available": (s.get("quantity") or 0) > 0 if "quantity" in s else s.get("available"),
                    "qty": s.get("quantity"),
                })
            color_entries.append({"id": str(cid), "name": cname, "sizes": sizes})
    else:
        logging.info(f"🎨 No colors in response, fetching from /api/products/{product_id}/colors")
        colors_data = await _catalog_get_json(f"/api/products/{product_id}/colors")
        logging.info(f"🎨 Fetched colors_data: {colors_data}")
        if isinstance(colors_data, list):
            for c in colors_data:
                if not isinstance(c, dict):
                    continue
                cid = c.get("id") or c.get("product_color_id") or c.get("color_id")
                cname = str(c.get("label") or c.get("name") or c.get("title") or c.get("color") or c.get("value") or c.get("color_name") or "").strip()
                if cid is None or not cname:
                    continue
                color_entries.append({"id": str(cid), "name": cname})

    product: Dict[str, Any] = {
        "id": str(pid),
        "base_id": str(base_id) if base_id is not None else None,
        "name": name,
        "slug": slug,
        "description": description,
        "composition": composition,
        "fit": fit,
        "meta": meta,
        "sections": sections,
        "url": url,
        "price": price,
        "images": images,
        "colors": [c["name"] for c in color_entries],
        "color_entries": color_entries,
        "images_by_color": {},
    }
    _catalog_cache["product"][product_id] = {"ts": datetime.utcnow().timestamp(), "data": product}
    return product

async def catalog_get_color_images(product_color_id: str) -> List[str]:
    cached = _catalog_cache["color_images"].get(product_color_id)
    if cached and _catalog_is_fresh(cached["ts"]):
        return cached["data"]
    data = await _catalog_get_json(f"/api/products/colors/{product_color_id}/images")
    urls: List[str] = []
    if isinstance(data, list):
        for it in data:
            u = _extract_image_url(it)
            if u:
                urls.append(u)
    _catalog_cache["color_images"][product_color_id] = {"ts": datetime.utcnow().timestamp(), "data": urls}
    return urls

async def catalog_get_color_sizes(product_color_id: str) -> List[Dict[str, Any]]:
    logging.info(f"📦 catalog_get_color_sizes called with product_color_id={product_color_id}")
    data = await _catalog_get_json(f"/api/products/colors/{product_color_id}/sizes")
    logging.info(f"📦 Raw sizes response: {data}")
    if not isinstance(data, list):
        logging.info(f"📦 Response is not a list, returning empty")
        return []
    out: List[Dict[str, Any]] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        name = str(it.get("size") or it.get("name") or it.get("label") or it.get("title") or "").strip()
        logging.info(f"📦 Processing size item: {it}, extracted name: {name}")
        if not name:
            continue
        out.append({
            "name": name,
            "available": (it.get("quantity") or 0) > 0 if "quantity" in it else it.get("available") if "available" in it else it.get("in_stock"),
            "qty": it.get("qty") or it.get("stock") or it.get("quantity"),
        })
    logging.info(f"📦 Final sizes: {out}")
    return out

async def catalog_get_collections() -> List[Dict[str, Any]]:
    data = await _catalog_get_json("/api/collections")
    if not isinstance(data, list):
        if isinstance(data, dict):
            data = data.get("items") or data.get("data") or data.get("results") or []
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or it.get("title") or it.get("collection_name") or "").strip()
        if not name:
            continue
        out.append({
            "id": str(it.get("id") or it.get("collection_id") or name),
            "name": name,
            "description": str(it.get("description") or it.get("desc") or "").strip(),
        })
    return out

async def catalog_get_product_categories(product_id: str) -> List[str]:
    data = await _catalog_get_json(f"/api/products/base/{product_id}/categories")
    if isinstance(data, dict):
        data = data.get("items") or data.get("data") or data.get("results") or data.get("categories")
    if not isinstance(data, list):
        return []
    names: List[str] = []
    for it in data:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or it.get("title") or "").strip()
        if name:
            names.append(name)
    return names

def tg_product_caption(p: Dict[str, Any], color: Optional[str] = None) -> str:
    name = _tg_to_html(str(p.get("name") or "Товар"))
    desc = _tg_to_html(str(p.get("description") or ""))
    url = str(p.get("url") or "")
    price = p.get("price")
    price_text = _format_price(price)
    parts = [f"<b>{name}</b>"]
    if price_text:
        parts.append(f"<b>Цена:</b> {html.escape(price_text)}")
    if color:
        parts.append(f"<b>Цвет:</b> {html.escape(color)}")
    if desc:
        parts.append(f"\n<blockquote>{desc}</blockquote>")
    if url:
        parts.append(f'\n<a href="{html.escape(url)}">Открыть на сайте</a>')
    return "\n".join(parts).strip()

async def _tg_get_product_images(product: Dict[str, Any], product_id: str, color_idx: int) -> Dict[str, Any]:
    color_entries: List[Dict[str, Any]] = product.get("color_entries", []) or []
    colors: List[str] = product.get("colors", []) or []
    idx = int(color_idx or 0)
    if idx < 0:
        idx = 0
    if idx >= len(colors):
        idx = 0

    color_name = colors[idx] if colors else None
    images: List[str] = []
    if 0 <= idx < len(color_entries):
        imgs = await catalog_get_color_images(str(color_entries[idx]["id"]))
        if imgs:
            images = imgs
    if not images and isinstance(product.get("images"), list):
        images = [str(x) for x in product.get("images") if x]
    return {"color_idx": idx, "color": color_name, "images": images, "colors": colors}

def _tg_product_kb(product_id: str, colors: List[str], selected_color_idx: int, img_idx: int, img_total: int, back_data: str) -> types.InlineKeyboardMarkup:
    rows: List[List[Dict[str, str]]] = []
    if img_total > 1:
        prev_idx = (img_idx - 1) % img_total
        next_idx = (img_idx + 1) % img_total
        rows.append([
            {"text": "◀️", "data": f"m:img:{product_id}:{selected_color_idx}:{prev_idx}"},
            {"text": f"🖼 {img_idx + 1}/{img_total}", "data": "m:nop"},
            {"text": "▶️", "data": f"m:img:{product_id}:{selected_color_idx}:{next_idx}"},
        ])
    if colors:
        color_row: List[Dict[str, str]] = []
        for idx, c in enumerate(colors[:6]):
            label = ("✅ " if idx == selected_color_idx else "") + str(c)
            color_row.append({"text": label[:18], "data": f"m:color:{product_id}:{idx}:0"})
            if len(color_row) == 2:
                rows.append(color_row)
                color_row = []
        if color_row:
            rows.append(color_row)
    rows.append([{"text": "🧠 Спросить ИИ", "data": f"m:ask:{product_id}"}])
    rows.append([{"text": "⬅️ Назад", "data": back_data}])
    rows.append([{"text": "🏠 Меню", "data": "m:home"}])
    return _tg_kb(rows)

async def _tg_download_as_input_file(url: str) -> Optional[Dict[str, Any]]:
    if not url:
        return None
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        async with current_session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return None
            content_type = (resp.headers.get("content-type") or "").lower()
            data = await resp.read()
            if not data:
                return None
            base = (url.split("?")[0] or "").rstrip("/")
            ext = ""
            if "image/png" in content_type or content_type.endswith("+png"):
                ext = ".png"
            elif "image/jpeg" in content_type or "image/jpg" in content_type:
                ext = ".jpg"
            elif "image/webp" in content_type:
                ext = ".webp"
            if not ext:
                ext = Path(base).suffix.lower()
            if not ext:
                ext = ".jpg"
            filename = f"image{ext}"
            is_photo = ext in {".jpg", ".jpeg", ".png"} and content_type.startswith("image/")
            file = BufferedInputFile(data, filename=filename)
            return {"file": file, "is_photo": is_photo}
    except Exception:
        return None
    finally:
        if current_session != http_session:
            await current_session.close()

def _ai_strip_html(raw: str) -> str:
    if not raw:
        return ""
    cleaned = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def _ai_tokenize(text: str) -> List[str]:
    base = _normalize(text)
    return [t for t in re.split(r"[^a-zа-я0-9]+", base) if t]

def _ai_score(query_tokens: List[str], chunk_tokens: List[str]) -> float:
    if not query_tokens or not chunk_tokens:
        return 0.0
    query_set = set(query_tokens)
    chunk_set = set(chunk_tokens)
    overlap = len(query_set.intersection(chunk_set))
    return overlap / max(len(query_set), 1)

def _ai_parse_lines(raw: str) -> List[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]

def _ai_trim(text: str, max_len: int = 320) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"

def _ai_cleanup_answer(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "")
    cleaned = cleaned.replace("*", "").replace("_", "")
    return cleaned.strip()


def _ai_is_recommendation(text_norm: str) -> bool:
    keys = ["посовет", "рекоменд", "какой товар", "что купить", "что посовету"]
    return any(k in text_norm for k in keys)

def _ai_has_product_intent(text_norm: str) -> bool:
    keywords = [
        "футболк", "худи", "свитшот", "лонгслив", "толстовк", "куртк", "жилет",
        "штаны", "брюк", "шорт", "юбк", "плать", "кофт", "свитер", "кардиган",
        "кепк", "шапк", "шарф", "перчатк", "носк", "аксессуар", "сумк", "рюкзак",
        "джинс", "спортивн", "комплект",
    ]
    if _ai_is_recommendation(text_norm):
        return True
    return any(k in text_norm for k in keywords)

def _ai_build_history(messages: List[Dict[str, Any]], max_items: int = 6) -> str:
    if not messages:
        return ""
    trimmed = messages[-max_items:]
    lines: List[str] = []
    for m in trimmed:
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        role = "Ассистент" if m.get("ai") else "Пользователь"
        lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()

def _ai_get_previous_user_message(messages: List[Dict[str, Any]], current_text: str) -> Optional[str]:
    if not messages:
        return None
    current_norm = _normalize(current_text)
    for m in reversed(messages):
        if m.get("ai"):
            continue
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        if _normalize(content) == current_norm:
            continue
        return content
    return None




HANDOFF_MESSAGE = "Запрос передан менеджеру, он свяжется с вами."

def _ai_is_handoff_confirm(text_norm: str) -> bool:
    """Определяет согласие пользователя на связь с менеджером"""
    triggers = {
        "да", "давай", "дайте", "ок", "окей", "ага", "угу", "можно",
        "свяжи", "свяжите", "подключи", "подключите", "позови", "позовите",
        "менеджер", "оператор", "человек", "поддержка",
    }
    if not text_norm:
        return False
    tokens = set(_ai_tokenize(text_norm))
    for t in triggers:
        tt = _normalize(t)
        if " " in tt and tt in text_norm:
            return True
        if tt in tokens:
            return True
    return False




async def _ai_get_settings(db: AsyncSession) -> Dict[str, Any]:
    cached = AI_SETTINGS_CACHE.get("data")
    if cached and (datetime.utcnow().timestamp() - AI_SETTINGS_CACHE.get("ts", 0.0)) < AI_SETTINGS_TTL_SECONDS:
        return cached

    settings = await get_ai_settings(db)
    if not settings:
        settings = await upsert_ai_settings(db, DEFAULT_AI_SETTINGS.copy())
    data = {
        "system_message": settings.system_message or "",
        "faqs": settings.faqs or "",
        "rules": settings.rules or "",
        "tone": settings.tone or "",
        "handoff_phrases": settings.handoff_phrases or "",
        "min_score": float(settings.min_score) if settings.min_score is not None else 0.2,
        "site_pages": settings.site_pages or "",
        "auto_refresh_minutes": int(settings.auto_refresh_minutes or 0),
    }
    AI_SETTINGS_CACHE["data"] = data
    AI_SETTINGS_CACHE["ts"] = datetime.utcnow().timestamp()
    return data

async def _ai_fetch_page_text(url: str) -> str:
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        async with current_session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return ""
            text = await resp.text()
            return _ai_strip_html(text)
    except Exception:
        return ""
    finally:
        if current_session != http_session:
            await current_session.close()

async def _ai_collect_products(limit: int) -> List[Dict[str, Any]]:
    categories = await catalog_get_categories()
    if not categories:
        return []
    products: List[Dict[str, Any]] = []
    for c in categories:
        if len(products) >= limit:
            break
        category_id = str(c.get("slug") or "")
        if not category_id:
            continue
        page = 1
        while len(products) < limit:
            items_data = await catalog_get_products(category_id, page=page, limit=AI_PRODUCTS_PAGE)
            if not items_data:
                break
            items = items_data.get("items") or []
            products.extend(items)
            if not items_data.get("has_next"):
                break
            page += 1
            if page > 10:
                break
    return products[:limit]

async def _ai_build_knowledge(settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []

    categories = await catalog_get_categories()
    logging.info(f"📚 Building knowledge base: {len(categories) if categories else 0} categories")
    if categories:
        cat_names = ", ".join([str(c.get("name")) for c in categories if c.get("name")])
        if cat_names:
            chunks.append({
                "text": f"Категории: {cat_names}",
                "source": "categories",
                "tags": ["categories"],
            })

    collections = await catalog_get_collections()
    logging.info(f"📚 Loading {len(collections)} collections")
    for col in collections:
        text = f"Коллекция: {col.get('name')}"
        if col.get("description"):
            text += f". Описание: {col.get('description')}"
        chunks.append({
            "text": text,
            "source": f"collection:{col.get('id')}",
            "tags": ["collection"],
        })

    products = await _ai_collect_products(AI_MAX_PRODUCTS)
    logging.info(f"📚 Loading {len(products)} products")
    for p in products:
        text = f"Товар: {p.get('name')}"
        price_text = _format_price(p.get("price"))
        if price_text:
            text += f". Цена: {price_text}"
        if p.get("description"):
            text += f". Описание: {p.get('description')}"
        if p.get("composition"):
            text += f". Состав: {p.get('composition')}"
        if p.get("fit"):
            text += f". Посадка: {p.get('fit')}"
        meta = p.get("meta") if isinstance(p.get("meta"), dict) else {}
        if meta.get("care"):
            text += f". Уход: {_ai_trim(str(meta.get('care')))}"
        if meta.get("shipping"):
            text += f". Доставка: {_ai_trim(str(meta.get('shipping')))}"
        if meta.get("returns"):
            text += f". Возврат: {_ai_trim(str(meta.get('returns')))}"
        sections = p.get("sections") if isinstance(p.get("sections"), list) else []
        section_texts: List[str] = []
        for s in sections:
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or "").strip()
            content = str(s.get("content") or "").strip()
            if not content and not title:
                continue
            content = _ai_trim(_ai_strip_html(content), 280)
            if title:
                section_texts.append(f"{title}: {content}")
            else:
                section_texts.append(content)
            if len(section_texts) >= 3:
                break
        if section_texts:
            text += f". Дополнительно: {'; '.join(section_texts)}"
        if p.get("colors"):
            text += f". Цвета: {', '.join([str(x) for x in p.get('colors') if x])}"
        if p.get("url"):
            text += f". Ссылка: {p.get('url')}"
        chunks.append({
            "text": text,
            "source": f"product:{p.get('id')}",
            "tags": ["product"],
            "meta": {"product_id": str(p.get("id"))},
        })

    for url in _ai_parse_lines(settings.get("site_pages", "")):
        content = await _ai_fetch_page_text(url)
        if content:
            chunks.append({
                "text": content,
                "source": f"page:{url}",
                "tags": ["page"],
            })

    faqs_text = settings.get("faqs") or ""
    if faqs_text.strip():
        chunks.append({
            "text": faqs_text.strip(),
            "source": "admin_faqs",
            "tags": ["faq"],
        })
    else:
        inline_faq = FAQ_INLINE_RAW.strip()
        if inline_faq:
            chunks.append({
                "text": inline_faq,
                "source": "inline_faqs",
                "tags": ["faq"],
            })

    return chunks

async def _ai_load_knowledge(db: AsyncSession) -> List[Dict[str, Any]]:
    cached = AI_KNOWLEDGE_CACHE.get("data")
    if cached and (datetime.utcnow().timestamp() - AI_KNOWLEDGE_CACHE.get("ts", 0.0)) < AI_KNOWLEDGE_TTL_SECONDS:
        return cached

    knowledge = await get_ai_knowledge(db)
    if knowledge and isinstance(knowledge.data, list):
        chunks = knowledge.data
    else:
        settings = await _ai_get_settings(db)
        chunks = await _ai_build_knowledge(settings)
        await save_ai_knowledge(db, chunks)
    AI_KNOWLEDGE_CACHE["data"] = chunks
    AI_KNOWLEDGE_CACHE["tokens"] = [_ai_tokenize(c.get("text", "")) for c in chunks]
    AI_KNOWLEDGE_CACHE["ts"] = datetime.utcnow().timestamp()
    return chunks

async def _ai_reindex(db: AsyncSession) -> Dict[str, Any]:
    settings = await _ai_get_settings(db)
    try:
        chunks = await _ai_build_knowledge(settings)
        await save_ai_knowledge(db, chunks)
        AI_KNOWLEDGE_CACHE["data"] = chunks
        AI_KNOWLEDGE_CACHE["tokens"] = [_ai_tokenize(c.get("text", "")) for c in chunks]
        AI_KNOWLEDGE_CACHE["ts"] = datetime.utcnow().timestamp()
        AI_STATUS["last_indexed"] = datetime.utcnow().isoformat()
        AI_STATUS["last_error"] = None
        AI_STATUS["chunks"] = len(chunks)
        return {"ok": True, "chunks": len(chunks)}
    except Exception as e:
        AI_STATUS["last_error"] = str(e)
        return {"ok": False, "error": str(e)}

async def _ai_auto_refresh_loop() -> None:
    while True:
        try:
            async with async_session() as session:
                settings = await _ai_get_settings(session)
                minutes = int(settings.get("auto_refresh_minutes") or 0)
                if minutes > 0:
                    await _ai_reindex(session)
                    await asyncio.sleep(minutes * 60)
                else:
                    await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)

async def _ai_openrouter(messages: List[Dict[str, Any]], use_xai: bool = False) -> Optional[Dict[str, Any]]:
    if use_xai and XAI_API_KEY:
        api_key = XAI_API_KEY
        model = XAI_MODEL
        base_url = XAI_BASE_URL
        label = "XAI"
    else:
        api_key = OPENAI_API_KEY
        model = OPENAI_MODEL
        base_url = "https://api.openai.com/v1/chat/completions"
        label = "OpenAI"
    if not api_key:
        logging.error(f"❌ {label} API key not found")
        return None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 600,
    }
    proxy_url = XAI_PROXY if use_xai and XAI_PROXY else None
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        logging.info(f"🤖 Sending request to {label} API with model: {model}" + (f" via proxy" if proxy_url else ""))
        async with current_session.post(
            base_url,
            headers=headers,
            json=payload,
            proxy=proxy_url,
            timeout=aiohttp.ClientTimeout(total=OPENAI_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logging.error(f"❌ {label} API error {resp.status}: {error_text}")
                return None
            data = await resp.json()
            logging.info(f"✅ {label} API response received")
            return data
    except Exception as e:
        logging.error(f"❌ {label} API exception: {e}")
        return None
    finally:
        if current_session != http_session:
            await current_session.close()

def _ai_extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None

async def _ai_build_sizes_context(product_id: str, fallback_id: Optional[str] = None) -> str:
    logging.info(f"🔍 _ai_build_sizes_context called with product_id={product_id}, fallback_id={fallback_id}")
    product = await catalog_get_product(product_id)
    logging.info(f"🔍 Got product: {product.get('name') if product else 'None'}, color_entries: {len(product.get('color_entries', [])) if product else 0}")
    if (not product or not product.get("color_entries")) and fallback_id and fallback_id != product_id:
        logging.info(f"🔍 Trying fallback_id={fallback_id}")
        product = await catalog_get_product(fallback_id)
    if not product:
        logging.info("🔍 No product found, returning empty")
        return ""
    parts: List[str] = []
    for entry in product.get("color_entries", []):
        logging.info(f"🔍 Processing color entry: {entry}")
        sizes = entry.get("sizes") if isinstance(entry, dict) else None
        logging.info(f"🔍 Inline sizes: {sizes}")
        if not sizes:
            logging.info(f"🔍 Fetching sizes for color_id={entry.get('id')}")
            sizes = await catalog_get_color_sizes(str(entry.get("id")))
            logging.info(f"🔍 Fetched sizes: {sizes}")
        if not sizes:
            logging.info(f"🔍 No sizes for color {entry.get('name')}")
            continue
        label = entry.get("name") or "Цвет"
        sizes_text = []
        for s in sizes:
            if s.get("available") is False:
                sizes_text.append(f"{s.get('name')} (нет)")
            elif s.get("qty"):
                sizes_text.append(f"{s.get('name')} (в наличии: {s.get('qty')})")
            else:
                sizes_text.append(str(s.get("name")))
        if sizes_text:
            parts.append(f"{label}: {', '.join(sizes_text)}")
    if not parts:
        logging.info("🔍 No sizes found for any color")
        return ""
    result = "Размеры и наличие по цветам:\n" + "\n".join(parts)
    logging.info(f"🔍 Sizes context: {result}")
    return result

async def _ai_answer_question(db: AsyncSession, question: str, extra_context: Optional[str] = None, product_id: Optional[str] = None, product_base_id: Optional[str] = None, product_categories: Optional[List[str]] = None, conversation_history: Optional[str] = None, previous_user_message: Optional[str] = None, is_product_question: bool = False, use_xai: bool = False) -> Dict[str, Any]:
    settings = await _ai_get_settings(db)
    text_norm = _normalize(question)

    # Все вопросы отправляем в AI — без шаблонных ответов.


    context_parts: List[str] = []
    top_score = 0.0
    min_score = float(settings.get("min_score") or 0.2)
    context_text = ""

    if not extra_context and _ai_has_product_intent(text_norm):
        search_products = await catalog_search_products(question, limit=12)
        if search_products:
            lines: List[str] = []
            for p in search_products:
                price_text = _format_price(p.get("price"))
                colors = ", ".join(p.get("colors") or [])
                line = f"- {p.get('name')}"
                if price_text:
                    line += f" ({price_text} ₽)"
                if colors:
                    line += f", цвета: {colors}"
                if p.get("url"):
                    line += f", ссылка: {p.get('url')}"
                lines.append(line)
            context_text = "Подборка товаров по запросу пользователя:\n" + "\n".join(lines)

    if not context_text and extra_context:
        context_parts.append(extra_context.strip())
        if ("размер" in text_norm or "налич" in text_norm) and product_id:
            sizes_ctx = await _ai_build_sizes_context(str(product_id), fallback_id=str(product_base_id) if product_base_id else None)
            if sizes_ctx:
                context_parts.append(sizes_ctx)
        context_text = "\n\n".join([p for p in context_parts if p])
    elif not context_text:
        chunks = await _ai_load_knowledge(db)
        logging.info(f"🔍 Knowledge base loaded: {len(chunks)} chunks")
        tokens = _ai_tokenize(question)
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for idx, c in enumerate(chunks):
            chunk_tokens = AI_KNOWLEDGE_CACHE["tokens"][idx] if idx < len(AI_KNOWLEDGE_CACHE["tokens"]) else _ai_tokenize(c.get("text", ""))
            score = _ai_score(tokens, chunk_tokens)
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        top_score = scored[0][0] if scored else 0.0
        logging.info(f"🎯 Search scores - Top: {top_score:.3f}, Min required: {min_score:.3f}, Total matches: {len(scored)}")
        if top_score < min_score:
            context_text = "В базе знаний нет релевантной информации по этому запросу. Отвечай СТРОГО по системному промту. Не выдумывай факты."
        else:
            top_chunks = [c for _, c in scored[:AI_TOP_K]]
            if "размер" in text_norm or "налич" in text_norm:
                for c in top_chunks:
                    meta = c.get("meta") or {}
                    pid = meta.get("product_id")
                    if pid:
                        sizes_ctx = await _ai_build_sizes_context(str(pid), fallback_id=None)
                        if sizes_ctx:
                            context_parts.append(sizes_ctx)
                        break

            context_parts.extend([c.get("text", "") for c in top_chunks if c.get("text")])
            context_text = "\n\n".join([p for p in context_parts if p])
    if not context_text:
        context_text = "В базе знаний нет релевантной информации по этому запросу. Отвечай СТРОГО по системному промту. Не выдумывай факты."
 
    if conversation_history:
        context_text = f"История диалога:\n{conversation_history}\n\n{context_text}"

    logging.info(f"📝 Final context_text for AI:\n{context_text[:500]}...")
    
    json_format = (
        "\nФормат ответа — ТОЛЬКО JSON без markdown:\n"
        '{{"answer": "твой ответ", "handoff": false, "confidence": 0.8}}\n'
        "answer — текст ответа клиенту, handoff — true если нужен менеджер, "
        "confidence — уверенность 0.0-1.0."
    )

    if is_product_question:
        system_content = AI_PRODUCT_PROMPT + json_format
    else:
        system_content = AI_SUPPORT_PROMPT + json_format

    messages = [
        {
            "role": "system",
            "content": system_content
        },
        {
            "role": "user",
            "content": f"Контекст:\n{context_text}\n\nВопрос клиента: {question}"
        }
    ]
    data = await _ai_openrouter(messages, use_xai=use_xai)
    if not data:
        return {"handoff": True, "answer": "", "confidence": top_score, "reason": "llm_error"}

    content = ""
    try:
        content = data["choices"][0]["message"]["content"]
        logging.info(f"🤖 OpenAI raw response: {content[:300]}...")
    except Exception:
        content = ""
    
    parsed = _ai_extract_json(content)
    if not parsed and content.strip():
        logging.warning("⚠️ AI returned non-JSON answer, using raw text fallback.")
        return {
            "handoff": False,
            "answer": content.strip(),
            "confidence": top_score,
            "reason": "fallback_text",
        }
    parsed = parsed or {}
    answer = str(parsed.get("answer") or "").strip()
    handoff = bool(parsed.get("handoff"))
    
    # Если AI решил передать менеджеру - передаем ВСЕГДА
    if handoff:
        return {
            "handoff": True, 
            "answer": "", 
            "confidence": float(parsed.get("confidence") or top_score), 
            "reason": "ai_escalation"
        }
    
    # Если ответ пустой - тоже передаем менеджеру
    if not answer:
        return {
            "handoff": True, 
            "answer": "", 
            "confidence": top_score, 
            "reason": "empty_answer"
        }
    
    # Возвращаем нормальный ответ AI
    return {
        "handoff": False,
        "answer": answer,
        "confidence": float(parsed.get("confidence") or top_score),
        "reason": "ok",
    }


# ================== AI Аналитика диалогов ==================

DIALOG_ANALYTICS_PROMPT = """
Ты — AI-аналитик диалогов службы поддержки. Проанализируй переписку между клиентом и менеджером.

Верни JSON со следующими полями:
{
  "summary": "Краткое резюме диалога (2-3 предложения)",
  "customer_problem": "Описание проблемы/вопроса клиента",
  "customer_intent": "Намерение клиента: purchase (покупка), refund (возврат), question (вопрос), complaint (жалоба), other (другое)",
  "refund_reason": "Если клиент хочет возврат - укажи причину, иначе null",
  "manager_quality_score": число от 1 до 10 (оценка работы менеджера),
  "manager_quality_notes": "Комментарий к оценке менеджера",
  "customer_sentiment": "positive, neutral или negative (настроение клиента)",
  "resolution_status": "resolved (решено), pending (в процессе), escalated (требует внимания руководства)",
  "key_topics": ["список", "ключевых", "тем"],
  "recommendations": "Рекомендации для улучшения сервиса (если есть)"
}

Критерии оценки менеджера:
- Скорость и точность ответов
- Вежливость и профессионализм
- Решение проблемы клиента
- Знание продукта/услуг

Отвечай ТОЛЬКО JSON без дополнительного текста или markdown.
"""

async def _ai_analyze_dialog(messages: List[Dict[str, Any]], manager_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Анализирует диалог с помощью AI и возвращает структурированную аналитику.
    
    Args:
        messages: Список сообщений диалога
        manager_name: Имя менеджера (опционально)
    
    Returns:
        Dict с результатами анализа или None при ошибке
    """
    if not OPENAI_API_KEY:
        logging.error("❌ OpenAI API key not found for dialog analytics")
        return None
    
    if not messages:
        logging.warning("⚠️ No messages to analyze")
        return None
    
    # Форматируем диалог для AI
    dialog_text = []
    for msg in messages:
        role = "Клиент" if msg.get("message_type") == "question" else "Менеджер"
        if msg.get("ai"):
            role = "AI-бот"
        content = msg.get("content") or msg.get("message", "")
        timestamp = msg.get("timestamp") or msg.get("created_at", "")
        if isinstance(timestamp, datetime):
            timestamp = timestamp.isoformat()
        dialog_text.append(f"[{timestamp}] {role}: {content}")
    
    dialog_formatted = "\n".join(dialog_text)
    
    if manager_name:
        context_info = f"\nМенеджер диалога: {manager_name}\n"
    else:
        context_info = ""
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": DIALOG_ANALYTICS_PROMPT},
            {"role": "user", "content": f"{context_info}\nДиалог для анализа:\n\n{dialog_formatted}"}
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
    }
    
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        logging.info(f"🔍 Analyzing dialog with {len(messages)} messages")
        async with current_session.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logging.error(f"❌ OpenAI API error {resp.status}: {error_text}")
                return None
            data = await resp.json()
            
            content = ""
            try:
                content = data["choices"][0]["message"]["content"]
            except Exception:
                logging.error("❌ Failed to extract content from OpenAI response")
                return None
            
            parsed = _ai_extract_json(content)
            if not parsed:
                logging.error(f"❌ Failed to parse AI response as JSON: {content[:200]}")
                return None
            
            logging.info("✅ Dialog analysis completed successfully")
            return {
                "summary": parsed.get("summary"),
                "customer_problem": parsed.get("customer_problem"),
                "customer_intent": parsed.get("customer_intent"),
                "refund_reason": parsed.get("refund_reason"),
                "manager_quality_score": parsed.get("manager_quality_score"),
                "manager_quality_notes": parsed.get("manager_quality_notes"),
                "customer_sentiment": parsed.get("customer_sentiment"),
                "resolution_status": parsed.get("resolution_status"),
                "key_topics": parsed.get("key_topics", []),
                "recommendations": parsed.get("recommendations"),
                "raw_response": parsed
            }
            
    except Exception as e:
        logging.error(f"❌ Dialog analysis exception: {e}")
        return None
    finally:
        if current_session != http_session:
            await current_session.close()


# VK config (делаем опциональным: отсутствие VK_* не должно валить весь API)
VK_TOKEN = os.getenv("VK_TOKEN")  # токен сообщества
VK_GROUP_ID_RAW = os.getenv("VK_GROUP_ID")  # ID сообщества (строкой)
VK_GROUP_ID: Optional[int] = None
if VK_GROUP_ID_RAW:
    try:
        VK_GROUP_ID = int(re.sub(r"\D", "", VK_GROUP_ID_RAW))
    except ValueError:
        logging.error("Invalid VK_GROUP_ID=%r (expected integer). VK integration will be disabled.", VK_GROUP_ID_RAW)
else:
    logging.warning("VK_GROUP_ID is not set. VK integration will be disabled.")

if not VK_TOKEN:
    logging.warning("VK_TOKEN is not set. VK integration will be disabled.")

# Синхронные объекты vk_api (инициализируем только если есть корректная конфигурация)
vk_session = None
vk = None
longpoll = None
if VK_TOKEN and VK_GROUP_ID:
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)
    except Exception:
        logging.exception("Failed to initialize VK integration. VK bot will be disabled.")
        vk_session = None
        vk = None
        longpoll = None

# ====== Forum Group (Telegram Topics) ======
_bot_user_id: Optional[int] = None  # кэш bot user id

FORUM_GROUP_ID: Optional[int] = None
_forum_group_id_raw = os.getenv("FORUM_GROUP_ID")
if _forum_group_id_raw:
    try:
        FORUM_GROUP_ID = int(_forum_group_id_raw.strip())
        logging.info("Forum group enabled: %s", FORUM_GROUP_ID)
    except ValueError:
        logging.error("Invalid FORUM_GROUP_ID=%r", _forum_group_id_raw)
else:
    logging.warning("FORUM_GROUP_ID is not set. Forum topic replies will be disabled.")

# Emoji IDs для иконок топиков (Telegram custom emoji)
FORUM_EMOJI_TELEGRAM = 5330237710655306682  # 📱 Telegram
FORUM_EMOJI_VK = 5334853932915114338        # 📱 VK
FORUM_EMOJI_WEB = None                       # Для сайта (нет кастомного emoji)

def _forum_emoji_for_messager(messager: str) -> Optional[int]:
    """Возвращает custom emoji ID для иконки топика по типу мессенджера"""
    if messager == "telegram":
        return FORUM_EMOJI_TELEGRAM
    elif messager == "vk":
        return FORUM_EMOJI_VK
    return FORUM_EMOJI_WEB


async def forum_create_topic(chat_obj) -> Optional[int]:
    """
    Создаёт топик в форум-группе для данного чата.
    Возвращает message_thread_id (topic_id) или None при ошибке.
    """
    if not FORUM_GROUP_ID or not bot:
        return None
    if chat_obj.topic_id:
        return chat_obj.topic_id  # уже создан

    topic_name = (chat_obj.name or "Без имени")[:128]
    emoji_id = _forum_emoji_for_messager(chat_obj.messager)

    # Цвета для иконок топиков (fallback если нет Premium для кастомных эмодзи)
    # Telegram = синий, VK = фиолетовый, остальное = зелёный
    ICON_COLORS = {"telegram": 0x6FB9F0, "vk": 0xCB86DB}

    try:
        kwargs = {
            "chat_id": FORUM_GROUP_ID,
            "name": topic_name,
        }
        if emoji_id:
            kwargs["icon_custom_emoji_id"] = str(emoji_id)
        try:
            topic = await bot.create_forum_topic(**kwargs)
        except Exception as emoji_err:
            if "PREMIUM" in str(emoji_err).upper() and emoji_id:
                # Без Premium — используем цвет вместо кастомного эмодзи
                kwargs.pop("icon_custom_emoji_id", None)
                color = ICON_COLORS.get(chat_obj.messager)
                if color:
                    kwargs["icon_color"] = color
                topic = await bot.create_forum_topic(**kwargs)
            else:
                raise emoji_err
        topic_id = topic.message_thread_id

        # Сохраняем topic_id в БД
        async with async_session() as session:
            await update_chat_topic_id(session, chat_obj.id, topic_id)
        chat_obj.topic_id = topic_id

        logging.info("Forum topic created: %s (id=%s) for chat %s", topic_name, topic_id, chat_obj.id)
        return topic_id
    except Exception as e:
        logging.error("Failed to create forum topic for chat %s: %s", chat_obj.id, e)
        return None


async def forum_send_message(chat_obj, text: str, is_image: bool = False, image_caption: str = None):
    """
    Пересылает сообщение клиента в топик форум-группы.
    """
    if not FORUM_GROUP_ID or not bot:
        return
    topic_id = chat_obj.topic_id
    if not topic_id:
        topic_id = await forum_create_topic(chat_obj)
    if not topic_id:
        return

    try:
        source_label = chat_obj.messager.upper() if chat_obj.messager else "?"
        header = f"[{source_label}] {chat_obj.name or 'Клиент'}:\n"

        if is_image:
            # text содержит URL картинки, возможно с caption через |
            parts = text.split("|", 1)
            img_url = parts[0].strip()
            caption = parts[1].strip() if len(parts) > 1 else ""
            full_caption = header + caption if caption else header + "📷 Фото"

            # Пробуем отправить как фото по URL
            if img_url.startswith(("http://", "https://")):
                try:
                    await bot.send_photo(
                        chat_id=FORUM_GROUP_ID,
                        message_thread_id=topic_id,
                        photo=img_url,
                        caption=full_caption[:1024]
                    )
                    return
                except Exception:
                    pass  # fallback к текстовому сообщению

            # Если не удалось отправить как фото — отправляем текстом
            await bot.send_message(
                chat_id=FORUM_GROUP_ID,
                message_thread_id=topic_id,
                text=f"{header}{caption}\n🖼 {img_url}" if caption else f"{header}📷 Фото\n🖼 {img_url}"
            )
        else:
            await bot.send_message(
                chat_id=FORUM_GROUP_ID,
                message_thread_id=topic_id,
                text=header + text
            )
    except Exception as e:
        logging.error("Failed to send message to forum topic %s: %s", topic_id, e)


async def forum_send_photo_bytes(chat_obj, photo_data, caption: str = None):
    """
    Отправляет фото (bytes/BufferedInputFile) в топик форум-группы.
    """
    if not FORUM_GROUP_ID or not bot:
        return
    topic_id = chat_obj.topic_id
    if not topic_id:
        topic_id = await forum_create_topic(chat_obj)
    if not topic_id:
        return

    try:
        source_label = chat_obj.messager.upper() if chat_obj.messager else "?"
        header = f"[{source_label}] {chat_obj.name or 'Клиент'}"
        full_caption = f"{header}: {caption}" if caption else f"{header}: 📷 Фото"
        await bot.send_photo(
            chat_id=FORUM_GROUP_ID,
            message_thread_id=topic_id,
            photo=photo_data,
            caption=full_caption[:1024]
        )
    except Exception as e:
        logging.error("Failed to send photo to forum topic %s: %s", topic_id, e)


# Асинхронная очередь для передачи событий из потока
queue: asyncio.Queue = asyncio.Queue()

def start_poller(loop: asyncio.AbstractEventLoop):
    """Запускаем блокирующий longpoll.listen() в фоновом потоке
       и шлём события в asyncio.Queue."""
    logging.info("▶️ Запускаю VK-poller thread")
    def _poller():
        try:
            logging.info("🟢 VK bot started polling")
            for event in longpoll.listen():
                etype = getattr(event, "type", None)
                if etype is None and isinstance(event, dict):
                    etype = event.get("type")
                logging.info(f"🟢 VK event received: {etype}")
                # передаём событие в цикл
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as e:
            logging.error(f"❌ VK poller error: {e}")
            # Перезапускаем поллер при ошибке
            loop.call_soon_threadsafe(lambda: start_poller(loop))
    thread = threading.Thread(target=_poller, daemon=True)
    thread.start()

async def handle_events():
    """Асинхронно обрабатываем события из очереди."""
    logging.info("👂 Начинаю асинхронно обрабатывать VK-события")
    while True:
        event = await queue.get()
        logging.debug("⚪ Взял из очереди событие: %s", event)
        asyncio.create_task(handle_single_event(event))

async def handle_single_event(event):
    etype = getattr(event, "type", None)
    if etype is None and isinstance(event, dict):
        etype = event.get("type")
    etype_str = str(etype).lower()
    is_incoming = (etype == VkBotEventType.MESSAGE_NEW or "message_new" in etype_str)
    is_outgoing = (etype == VkBotEventType.MESSAGE_REPLY or "message_reply" in etype_str)
    if not (is_incoming or is_outgoing):
        return

    payload_obj = getattr(event, "object", None)
    if payload_obj is None and isinstance(event, dict):
        payload_obj = event.get("object") or event.get("message") or event
    if isinstance(payload_obj, dict):
        msg = payload_obj.get("message") or payload_obj.get("object") or payload_obj
    else:
        msg = getattr(payload_obj, "message", None) or payload_obj
    if not isinstance(msg, dict):
        return
    peer_id = msg['peer_id']
    user_id = msg['from_id']
    text = msg.get('text', "")
    attachments = msg.get("attachments", [])

    # Outgoing messages from VK community admin panel
    if is_outgoing or (VK_GROUP_ID and user_id == -VK_GROUP_ID):
        if not text and not attachments:
            return
        async with async_session() as session:
            chat = await get_chat_by_uuid(session, str(peer_id))
            if not chat:
                chat = await create_chat(session, str(peer_id), name=str(peer_id), messager="vk")
                await updates_manager.broadcast(json.dumps({
                    "type": "chat_created",
                    "chat": {
                        "id": chat.id, "uuid": chat.uuid, "name": chat.name,
                        "messager": chat.messager, "waiting": chat.waiting,
                        "ai": chat.ai, "tags": chat.tags,
                        "last_message_content": None, "last_message_timestamp": None
                    }
                }))
            if text:
                db_msg = crud.Message(
                    chat_id=chat.id, message=text,
                    message_type="answer", ai=False,
                    created_at=datetime.utcnow()
                )
                session.add(db_msg)
                await session.commit()
                await session.refresh(db_msg)
                await messages_manager.broadcast(json.dumps({
                    "type": "message",
                    "chatId": str(db_msg.chat_id),
                    "content": db_msg.message,
                    "message_type": db_msg.message_type,
                    "ai": False,
                    "timestamp": db_msg.created_at.isoformat(),
                    "id": db_msg.id
                }))
            for att in attachments:
                if att.get("type") != "photo":
                    continue
                photo = att["photo"]
                url = None
                for size_key in ['photo_1280', 'photo_807', 'photo_604', 'photo_130', 'photo_75']:
                    if size_key in photo:
                        url = photo[size_key]
                        break
                if not url and "sizes" in photo:
                    sizes = photo["sizes"]
                    max_size = max(sizes, key=lambda s: s["height"])
                    url = max_size["url"]
                if not url:
                    continue
                try:
                    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
                    try:
                        async with current_session.get(url) as resp:
                            if resp.status != 200:
                                continue
                            content = await resp.read()
                    finally:
                        if current_session != http_session:
                            await current_session.close()
                    if not content:
                        continue
                    file_ext = os.path.splitext(url.split('?')[0])[1] or ".jpg"
                    file_name = f"{peer_id}-{int(datetime.utcnow().timestamp())}{file_ext}"
                    file_data = io.BytesIO(content)
                    file_data.seek(0, 2)
                    file_size = file_data.tell()
                    file_data.seek(0)
                    await asyncio.to_thread(
                        minio_client.put_object, BUCKET_NAME, file_name,
                        file_data, file_size, content_type="image/jpeg"
                    )
                    img_url = build_public_minio_url(file_name)
                    db_img = Message(
                        chat_id=chat.id, message=img_url,
                        message_type="answer", ai=False,
                        created_at=datetime.utcnow(), is_image=True
                    )
                    session.add(db_img)
                    await session.commit()
                    await session.refresh(db_img)
                    await messages_manager.broadcast(json.dumps({
                        "type": "message",
                        "chatId": str(db_img.chat_id),
                        "content": db_img.message,
                        "message_type": "answer",
                        "ai": False,
                        "timestamp": db_img.created_at.isoformat(),
                        "id": db_img.id,
                        "is_image": True
                    }))
                except Exception as e:
                    logging.error(f"Error processing outgoing VK photo: {e}")
        return

    # Получаем информацию о пользователе
    try:
        user_info = await asyncio.to_thread(
            vk.users.get,
            user_ids=[user_id],
            fields=['first_name', 'last_name']
        )
        if user_info:
            user = user_info[0]
            user_name = f"{user['first_name']} {user['last_name']}"
        else:
            user_name = str(user_id)
    except Exception as e:
        logging.error(f"Error getting VK user info: {e}")
        user_name = str(user_id)

    # --- 1) Работа с чатом в БД, WebSocket-апдейты ---
    async with async_session() as session:
        # Получаем или создаём чат
        chat = await get_chat_by_uuid(session, str(peer_id))
        if not chat:
            chat = await create_chat(
                session,
                str(peer_id),
                name=user_name,
                messager="vk"
            )
            new_chat_message = {
                "type": "chat_created",
                "chat": {
                    "id": chat.id,
                    "uuid": chat.uuid,
                    "name": chat.name,
                    "messager": chat.messager,
                    "waiting": chat.waiting,
                    "ai": chat.ai,
                    "tags": chat.tags,
                    "last_message_content": None,
                    "last_message_timestamp": None
                }
            }
            await updates_manager.broadcast(json.dumps(new_chat_message))

        payload_raw = msg.get("payload")
        payload_data: Optional[Dict[str, Any]] = None
        if payload_raw:
            try:
                payload_data = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
            except Exception:
                payload_data = None

        if payload_data and isinstance(payload_data, dict) and payload_data.get("cmd"):
            cmd = str(payload_data.get("cmd"))
            if chat.waiting and cmd != "ask_ai":
                return
            if cmd == "home":
                await vk_send_message(peer_id, _vk_main_text(), keyboard=vk_kb_main())
                return
            if cmd == "faq":
                await vk_send_message(peer_id, _vk_faq_text(1), keyboard=vk_kb_faq_menu(1))
                return
            if cmd == "faq_page":
                page = int(payload_data.get("page") or 1)
                await vk_send_message(peer_id, _vk_faq_text(page), keyboard=vk_kb_faq_menu(page))
                return
            if cmd == "faq_item":
                item_id = str(payload_data.get("id") or "")
                page = int(payload_data.get("page") or 1)
                await vk_send_message(peer_id, _vk_faq_item_text(item_id), keyboard=vk_kb_faq_item(item_id, page))
                return
            if cmd == "cat":
                categories = await catalog_get_categories()
                if not categories:
                    reason = str(_catalog_cache.get("last_error") or "").strip()
                    text_out = "Каталог пока недоступен."
                    if reason:
                        text_out += f"\nПричина: {reason}"
                    await vk_send_message(peer_id, text_out, keyboard=vk_kb_main())
                    return
                await vk_send_message(peer_id, "Каталог\n\nВыберите категорию:", keyboard=vk_kb_categories(categories))
                return
            if cmd == "cat_open":
                category_id = str(payload_data.get("id") or "")
                page = int(payload_data.get("page") or 1)
                limit = 6
                logging.info(f"VK: Opening category {category_id}, page {page}")
                items_data = await catalog_get_products(category_id, page=page, limit=limit)
                if not items_data:
                    reason = str(_catalog_cache.get("last_error") or "").strip()
                    text_out = "Каталог пустой или API недоступен."
                    if reason:
                        text_out += f"\nПричина: {reason}"
                    logging.error(f"VK: Failed to get products for category {category_id}: {reason}")
                    await vk_send_message(peer_id, text_out, keyboard=vk_kb_main())
                    return
                items = items_data.get("items") or []
                has_next = bool(items_data.get("has_next"))
                logging.info(f"VK: Got {len(items)} products for category {category_id}")
                await vk_send_message(peer_id, f"Каталог\n\nСтраница {page}", keyboard=vk_kb_products(category_id, page, items, has_next=has_next))
                return
            if cmd == "prod":
                product_id = str(payload_data.get("id") or "")
                category_id = str(payload_data.get("cat") or "") or None
                page = int(payload_data.get("page") or 1) if payload_data.get("page") else None
                product = await catalog_get_product(product_id)
                if not product:
                    await vk_send_message(peer_id, "Товар не найден.", keyboard=vk_kb_main())
                    return
                colors = product.get("colors", [])
                color_entries: List[Dict[str, Any]] = product.get("color_entries", [])
                selected_color = colors[0] if colors else None
                image_url = None
                if color_entries:
                    imgs = await catalog_get_color_images(color_entries[0]["id"])
                    if imgs:
                        product["images_by_color"][color_entries[0]["name"]] = imgs
                        image_url = imgs[0]
                if not image_url and product.get("images"):
                    image_url = product["images"][0]
                attachment = await vk_upload_photo_from_url(image_url) if image_url else None
                text_out = f"{product.get('name','Товар')}\n\n{product.get('description','')}"
                if product.get("url"):
                    text_out += f"\n\nСсылка: {product.get('url')}"
                await vk_send_message(peer_id, text_out.strip(), keyboard=vk_kb_product(product_id, category_id=category_id, page=page, colors=colors), attachment=attachment)
                return
            if cmd == "color":
                product_id = str(payload_data.get("id") or "")
                idx = int(payload_data.get("ci") or 0)
                category_id = str(payload_data.get("cat") or "") or None
                page = int(payload_data.get("page") or 1) if payload_data.get("page") else None
                product = await catalog_get_product(product_id)
                if not product:
                    return
                colors = product.get("colors", [])
                color_entries: List[Dict[str, Any]] = product.get("color_entries", [])
                color = colors[idx] if colors and 0 <= idx < len(colors) else (colors[0] if colors else None)
                image_url = None
                if color and 0 <= idx < len(color_entries):
                    imgs = await catalog_get_color_images(color_entries[idx]["id"])
                    if imgs:
                        product["images_by_color"][color] = imgs
                        image_url = imgs[0]
                if not image_url and product.get("images"):
                    image_url = product["images"][0]
                attachment = await vk_upload_photo_from_url(image_url) if image_url else None
                text_out = f"{product.get('name','Товар')}"
                if color:
                    text_out += f"\nЦвет: {color}"
                if product.get("url"):
                    text_out += f"\n\nСсылка: {product.get('url')}"
                await vk_send_message(peer_id, text_out.strip(), keyboard=vk_kb_product(product_id, category_id=category_id, page=page, colors=colors), attachment=attachment)
                return
            if cmd == "ask_ai":
                product_id = str(payload_data.get("id") or "")
                product = await catalog_get_product(product_id)
                if not product:
                    await vk_send_message(peer_id, "Товар не найден.", keyboard=vk_kb_main())
                    return
                state = _get_state("vk", str(peer_id))
                state["mode"] = "ask_ai_product"
                state["product"] = {
                    "id": product.get("id"),
                    "base_id": product.get("base_id"),
                    "name": product.get("name"),
                    "description": product.get("description"),
                    "colors": product.get("colors", []),
                    "url": product.get("url"),
                    "price": product.get("price"),
                    "categories": product.get("categories", []),
                }
                await vk_send_message(peer_id, "Напишите вопрос по этому товару — я отвечу с учётом описания и цветов.", keyboard=vk_kb_main())
                return
            if cmd == "manager":
                await request_manager(session, chat.id, str(peer_id), user_name, "vk")
                await vk_send_message(peer_id, HANDOFF_MESSAGE, keyboard=vk_kb_main())
                return

        text_norm = _normalize(text)
        command = text_norm
        state = _get_state("vk", str(peer_id))
        allow_ai_during_waiting = bool(state.get("mode") == "ask_ai_product" and state.get("product"))
        force_ai = allow_ai_during_waiting
        suppress_ai = False
        if command.startswith("/"):
            command = command[1:]
        if "@" in command:
            command = command.split("@", 1)[0]
        if not suppress_ai and (command in {"меню", "menu", "старт", "start"} or text_norm in {"/menu", "/start"}):
            _clear_state("vk", str(peer_id))  # очищаем state при смене режима
            await vk_send_message(peer_id, _vk_main_text(), keyboard=vk_kb_main())
            return
        if not suppress_ai and (command == "faq" or "faq" in text_norm or "/faq" in text_norm):
            _clear_state("vk", str(peer_id))  # очищаем state при смене режима
            await vk_send_message(peer_id, _vk_faq_text(1), keyboard=vk_kb_faq_menu(1))
            return
        if not suppress_ai and any(k in text_norm for k in {"каталог", "товары", "товар"}):
            _clear_state("vk", str(peer_id))  # очищаем state при смене режима
            categories = await catalog_get_categories()
            if not categories:
                reason = str(_catalog_cache.get("last_error") or "").strip()
                text_out = "Каталог пока недоступен."
                if reason:
                    text_out += f"\nПричина: {reason}"
                await vk_send_message(peer_id, text_out, keyboard=vk_kb_main())
                return
            await vk_send_message(peer_id, "Каталог\n\nВыберите категорию:", keyboard=vk_kb_categories(categories))
            return
        if not suppress_ai and ("позови менеджера" in text_norm or text_norm == "менеджер"):
            await request_manager(session, chat.id, str(peer_id), user_name, "vk")
            await vk_send_message(peer_id, HANDOFF_MESSAGE, keyboard=vk_kb_main())
            return

        # --- 2) Текстовое сообщение ---
        if text:
            # Создаём запись вопроса
            db_msg = crud.Message(
                chat_id=chat.id,
                message=text,
                message_type="question",
                ai=False,
                created_at=datetime.utcnow()
            )
            session.add(db_msg)
            await session.commit()
            await session.refresh(db_msg)

            # Шлём фронту через WS
            message_for_frontend = {
                "type": "message",
                "chatId": str(db_msg.chat_id),
                "content": db_msg.message,
                "message_type": db_msg.message_type,
                "ai": db_msg.ai,
                "timestamp": db_msg.created_at.isoformat(),
                "id": db_msg.id
            }
            await messages_manager.broadcast(json.dumps(message_for_frontend))

            # Пересылаем в форум-группу
            await forum_send_message(chat, text)

        state = _get_state("vk", str(peer_id))
        text_norm = _normalize(text)

        if _ai_is_handoff_confirm(text_norm):
            await request_manager(session, chat.id, str(peer_id), user_name, "vk")
            await vk_send_message(peer_id, HANDOFF_MESSAGE, keyboard=vk_kb_main())
            return

        if suppress_ai:
            if text:
                await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
                await updates_manager.broadcast(json.dumps({
                    "type": "chat_update",
                    "chat_id": chat.id,
                    "waiting": True
                }))
            return
        
        # Проверяем, отключен ли AI для этого чата (кроме режима "спросить у ИИ" про товар)
        is_product_mode = bool(state.get("mode") == "ask_ai_product" and state.get("product"))
        if not is_product_mode and (not chat.ai or chat.waiting):
            logging.info(f"🔇 VK AI disabled for chat {chat.id}: ai={chat.ai}, waiting={chat.waiting}")
            if text and not chat.waiting:
                await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
                await updates_manager.broadcast(json.dumps({
                    "type": "chat_update",
                    "chat_id": chat.id,
                    "waiting": True
                }))
            return
        
        extra_context = None
        product_id = None
        base_id = None
        categories: List[str] = []
        logging.info(f"🔍 VK state for {peer_id}: mode={state.get('mode')}, has_product={bool(state.get('product'))}")
        if state.get("mode") == "ask_ai_product" and state.get("product"):
            p = state["product"]
            product_id = str(p.get("id") or p.get("base_id") or "")
            base_id = str(p.get("base_id") or p.get("id") or "")
            logging.info(f"📦 VK using product context: product_id={product_id}, base_id={base_id}, name={p.get('name')}")
            categories = p.get("categories") or []
            if not categories and base_id:
                categories = await catalog_get_product_categories(base_id)
            price_text = _format_price(p.get("price"))
            meta = p.get("meta") if isinstance(p.get("meta"), dict) else {}
            sections = p.get("sections") if isinstance(p.get("sections"), list) else []
            section_lines: List[str] = []
            for s in sections:
                if not isinstance(s, dict):
                    continue
                title = str(s.get("title") or "").strip()
                content = str(s.get("content") or "").strip()
                if not content and not title:
                    continue
                content = _ai_trim(_ai_strip_html(content), 280)
                if title:
                    section_lines.append(f"{title}: {content}")
                else:
                    section_lines.append(content)
                if len(section_lines) >= 3:
                    break
            ctx_lines = [
                f"Название: {p.get('name','')}",
                f"Описание: {p.get('description','')}",
            ]
            if p.get("composition"):
                ctx_lines.append(f"Состав: {p.get('composition','')}")
            if p.get("fit"):
                ctx_lines.append(f"Посадка: {p.get('fit','')}")
            if meta.get("care"):
                ctx_lines.append(f"Уход: {meta.get('care','')}")
            if meta.get("shipping"):
                ctx_lines.append(f"Доставка: {meta.get('shipping','')}")
            if meta.get("returns"):
                ctx_lines.append(f"Возврат: {meta.get('returns','')}")
            if section_lines:
                ctx_lines.append(f"Дополнительно: {'; '.join(section_lines)}")
            ctx_lines.extend([
                f"Цена: {price_text}",
                f"Цвета: {', '.join(p.get('colors', []))}",
                f"Категории: {', '.join(categories)}",
                f"Ссылка: {p.get('url','')}",
            ])
            extra_context = "Контекст товара:\n" + "\n".join(ctx_lines)
            # НЕ очищаем state — сохраняем контекст товара для продолжения диалога
            force_ai = True
        history = await get_chat_messages(session, chat.id, limit=6)
        history_text = _ai_build_history(history, max_items=6)
        previous_user_message = _ai_get_previous_user_message(history, text)
        is_product_q = bool(state.get("mode") == "ask_ai_product" and state.get("product"))
        ai_result = await _ai_answer_question(
            session,
            text,
            extra_context=extra_context,
            product_id=product_id,
            product_base_id=base_id,
            product_categories=categories or None,
            conversation_history=history_text,
            previous_user_message=previous_user_message,
            is_product_question=is_product_q,
        )
        
        # Если AI решил передать менеджеру - сразу передаём
        if ai_result.get("handoff"):
            await request_manager(session, chat.id, str(peer_id), user_name, "vk")
            await vk_send_message(peer_id, HANDOFF_MESSAGE, keyboard=vk_kb_main())
            return

        # Если ответ пустой - тоже передаем менеджеру
        answer = str(ai_result.get("answer") or "").strip()
        answer = _normalize_price_text(answer)
        answer = _ai_cleanup_answer(answer)
        if not answer:
            await request_manager(session, chat.id, str(peer_id), user_name, "vk")
            await vk_send_message(peer_id, HANDOFF_MESSAGE, keyboard=vk_kb_main())
            return

        await asyncio.to_thread(
            vk.messages.send,
            peer_id=peer_id,
            message=answer,
            random_id=0
        )

        db_ans = crud.Message(
            chat_id=chat.id,
            message=answer,
            message_type="answer",
            ai=True,
            created_at=datetime.utcnow()
        )
        session.add(db_ans)
        await session.commit()
        await session.refresh(db_ans)

        ans_for_frontend = {
            "type": "message",
            "chatId": str(db_ans.chat_id),
            "content": db_ans.message,
            "message_type": db_ans.message_type,
            "ai": db_ans.ai,
            "timestamp": db_ans.created_at.isoformat(),
            "id": db_ans.id
        }
        await messages_manager.broadcast(json.dumps(ans_for_frontend))

        # Дублируем AI-ответ в форум-топик
        if FORUM_GROUP_ID and bot and chat.topic_id:
            try:
                await bot.send_message(
                    chat_id=FORUM_GROUP_ID,
                    message_thread_id=chat.topic_id,
                    text=f"[AI]:\n{answer}"
                )
            except Exception:
                pass

        # AI ответил, но менеджер должен увидеть диалог как непрочитанный
        await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
        await updates_manager.broadcast(json.dumps({
            "type": "chat_update",
            "chat_id": chat.id,
            "waiting": True
        }))

        # --- 4) Обработка фото-вложений ---
        for att in attachments:
                if att["type"] != "photo":
                    continue
                
                # Получаем прямые URL фотографии
                photo = att["photo"]
                logging.info(f"VK photo data: {json.dumps(photo, indent=2)}")
                
                # Пробуем получить URL в порядке убывания размера
                url = None
                for size in ['photo_1280', 'photo_807', 'photo_604', 'photo_130', 'photo_75']:
                    if size in photo:
                        url = photo[size]
                        logging.info(f"Found photo URL for size {size}: {url}")
                        break
                
                if not url:
                    # Если не нашли прямые URL, пробуем получить из sizes
                    if "sizes" in photo:
                        sizes = photo["sizes"]
                        max_size = max(sizes, key=lambda s: s["height"])
                        url = max_size["url"]
                        logging.info(f"Using URL from sizes: {url}")
                    else:
                        logging.error("No suitable photo URL found")
                        continue
                
                logging.info(f"Selected VK photo URL: {url}")
                
                # Скачиваем картинку
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://vk.com/'
                    }
                    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
                    try:
                        async with current_session.get(url, headers=headers) as resp:
                            if resp.status != 200:
                                logging.error(f"Failed to download VK photo: {resp.status}")
                                continue
                            content = await resp.read()
                    finally:
                        if current_session != http_session: await current_session.close()

                    if not content:
                        logging.error("Empty photo content received")
                        continue
                    logging.info(f"Successfully downloaded VK photo, size: {len(content)} bytes")
                except Exception as e:
                    logging.error(f"VK photo download error: {e}")
                    continue

                # Загружаем в Minio
                file_ext = os.path.splitext(url.split('?')[0])[1] or ".jpg"
                file_name = f"{peer_id}-{int(datetime.utcnow().timestamp())}{file_ext}"
                logging.info(f"Attempting to upload to MinIO: {file_name}")
                
                try:
                    # Создаем BytesIO объект с правильным размером
                    file_data = io.BytesIO(content)
                    file_data.seek(0, 2)  # Перемещаемся в конец файла
                    file_size = file_data.tell()  # Получаем размер
                    file_data.seek(0)  # Возвращаемся в начало
                    
                    logging.info(f"Uploading to MinIO: {file_name}, size: {file_size} bytes")
                    
                    await asyncio.to_thread(
                        minio_client.put_object,
                        BUCKET_NAME,
                        file_name,
                        file_data,
                        file_size,
                        content_type="image/jpeg"
                    )
                    img_url = build_public_minio_url(file_name)
                    logging.info(f"Successfully uploaded to MinIO: {img_url}")
                except Exception as e:
                    logging.error(f"MinIO upload error: {e}")
                    continue

                # Сохраняем как сообщение
                try:
                    db_img = Message(
                        chat_id=chat.id,
                        message=img_url,
                        message_type="question",
                        ai=False,
                        created_at=datetime.utcnow(),
                        is_image=True
                    )
                    session.add(db_img)
                    await session.commit()
                    await session.refresh(db_img)
                    logging.info(f"Successfully saved message to database with image URL: {img_url}")
                except Exception as e:
                    logging.error(f"Database error while saving image message: {e}")
                    continue
                # Шлём на фронт
                await messages_manager.broadcast(json.dumps({
                    "type": "message",
                    "chatId": str(db_img.chat_id),
                    "content": db_img.message,
                    "message_type": db_img.message_type,
                    "ai": db_img.ai,
                    "timestamp": db_img.created_at.isoformat(),
                    "id": db_img.id,
                    "is_image": True
                }))

                # Пересылаем фото в форум-группу
                try:
                    photo_input = BufferedInputFile(content, filename=file_name)
                    await forum_send_photo_bytes(chat, photo_input, caption=text or None)
                except Exception as e:
                    logging.error("Failed to forward VK photo to forum: %s", e)

                # Обновление waiting
                await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
                await updates_manager.broadcast(json.dumps({
                    "type": "chat_update",
                    "chat_id": chat.id,
                    "waiting": True
                }))
                
                # Отправляем уведомление админам
                notification_manager = notifications.get_notification_manager()
                if notification_manager:
                    await notification_manager.send_waiting_notification(
                        chat_id=peer_id,
                        chat_name=user_name,
                        messager="vk"
                    )

async def start_vk_bot():
    loop = asyncio.get_running_loop()
    if not (VK_TOKEN and VK_GROUP_ID and vk_session and longpoll):
        logging.warning("VK integration disabled (missing/invalid VK_TOKEN or VK_GROUP_ID).")
        return

    start_poller(loop)
    print("Async VK-бот запущен. Ожидаем сообщений…")
    await handle_events()


# Initialize bot and dispatcher (TG делаем опциональным, чтобы API не падал без BOT_TOKEN)
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = None
if BOT_TOKEN:
    try:
        bot = get_bot()
    except Exception:
        logging.exception("Failed to initialize Telegram bot. TG polling will be disabled.")
        bot = None
else:
    logging.warning("BOT_TOKEN is not set. TG polling will be disabled.")

dp = Dispatcher()

APP_HOST = os.getenv("APP_HOST", "localhost")
MINIO_LOGIN = os.getenv("MINIO_LOGIN")
MINIO_PWD = os.getenv("MINIO_PWD")

http_session: Optional[aiohttp.ClientSession] = None

BUCKET_NAME = "psih-photo"
minio_client = Minio(
    endpoint=f"minio:9000",
    access_key=MINIO_LOGIN,
    secret_key=MINIO_PWD,
    secure=False  # True для HTTPS
)

def build_public_minio_url(file_name: str) -> str:
    """
    Не возвращаем прямой URL на :9000 (он обычно закрыт извне).
    Отдаём через nginx по /minio/{bucket}/{object} на текущем домене.
    """
    public_base = os.getenv("PUBLIC_MINIO_BASE_URL")
    if public_base:
        return f"{public_base.rstrip('/')}/{BUCKET_NAME}/{file_name}"
    return f"/minio/{BUCKET_NAME}/{file_name}"

# Create database tables
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Auto-миграции: добавляем колонки если их нет
        await conn.execute(sa_text("ALTER TABLE chats ADD COLUMN IF NOT EXISTS topic_id INTEGER"))
        await conn.execute(sa_text("ALTER TABLE chats ADD COLUMN IF NOT EXISTS mark VARCHAR(20) DEFAULT NULL"))
        await conn.execute(sa_text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ DEFAULT NULL"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_session
    await init_db()
    load_faq()
    
    http_session = aiohttp.ClientSession()
    
    if bot:
        notifications.init_notification_manager(bot)
    
    tg_task = None
    if bot:
        tg_task = asyncio.create_task(dp.start_polling(bot))
    
    vk_task = asyncio.create_task(start_vk_bot())
    ai_task = asyncio.create_task(_ai_auto_refresh_loop())
    
    yield
    
    if tg_task:
        tg_task.cancel()
        try:
            await tg_task
        except asyncio.CancelledError:
            pass

    vk_task.cancel()
    try:
        await vk_task
    except asyncio.CancelledError:
        pass

    ai_task.cancel()
    try:
        await ai_task
    except asyncio.CancelledError:
        pass

    if http_session:
        await http_session.close()

app = FastAPI(lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
async def get_db():
    async with async_session() as session:
        yield session

# WebSocket connection managers
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logging.error(f"Error broadcasting message: {e}")

# Create separate managers for messages and updates
messages_manager = ConnectionManager()
updates_manager = ConnectionManager()

@app.websocket("/ws/messages")
async def messages_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    
    try:
        is_authorized = await auth.check_permissions(token)
        if not is_authorized:
            await websocket.close(code=1008)
            return
    except Exception as e:
        logging.error(f"WS auth error: {e}")
        await websocket.close(code=1011)
        return

    await messages_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                if "chatId" in message_data and "content" in message_data:
                    try:
                        chat_id = int(message_data["chatId"])
                        await bot.send_message(chat_id=chat_id, text=message_data["content"])
                        chat = await get_chat(async_session(), chat_id)
                        if chat:
                            await create_message(
                                async_session(),
                                chat.id,
                                message_data["content"],
                                "text",
                                False
                            )
                            update_message = {
                                "type": "update",
                                "chatId": str(chat_id),
                                "content": message_data["content"],
                                "message_type": "text",
                                "ai": False,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            await updates_manager.broadcast(json.dumps(update_message))
                    except (ValueError, TypeError) as e:
                        logging.error(f"Invalid chat_id format: {e}")
                else:
                    await messages_manager.broadcast(data)
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing message: {e}")
    except WebSocketDisconnect:
        messages_manager.disconnect(websocket)

@app.websocket("/ws/updates")
async def updates_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    
    try:
        is_authorized = await auth.check_permissions(token)
        if not is_authorized:
            await websocket.close(code=1008)
            return
    except Exception as e:
        logging.error(f"WS auth error: {e}")
        await websocket.close(code=1011)
        return

    await updates_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                update_data = json.loads(data)
                await updates_manager.broadcast(data)
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing update: {e}")
    except WebSocketDisconnect:
        updates_manager.disconnect(websocket)

# Endpoints
class LoginRequest(BaseModel):
    email: str
    password: str

async def _proxy_auth_token(username: str, password: str):
    """
    Совместимость с "рабочим проектом": auth-service принимает
    POST /api/auth/token (application/x-www-form-urlencoded) с полями username/password.
    """
    url = f"{auth.AUTH_SERVICE_BASE_URL}/api/auth/token"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data={"username": username, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = await resp.json()
                    return JSONResponse(status_code=resp.status, content=data)
                text = await resp.text()
                return JSONResponse(status_code=resp.status, content={"detail": text})
    except Exception as e:
        logging.error(f"Auth token proxy error: {e}")
        raise HTTPException(status_code=502, detail="Auth service unavailable")

@app.post("/api/auth/login")
async def auth_login(payload: LoginRequest):
    # алиас под текущий фронт: email/password -> username/password
    return await _proxy_auth_token(username=payload.email, password=payload.password)

@app.post("/api/auth/token")
async def auth_token(username: str = Form(...), password: str = Form(...)):
    # точное совпадение с "рабочим проектом"
    return await _proxy_auth_token(username=username, password=password)


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


@app.post("/api/auth/register")
async def auth_register(payload: RegisterRequest):
    """
    Регистрация нового менеджера через внешний сервис аутентификации.
    """
    url = f"{auth.AUTH_SERVICE_BASE_URL}/api/auth/register"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    "email": payload.email,
                    "password": payload.password,
                    "name": payload.name,
                    "is_admin": True,
                },
                headers={"Content-Type": "application/json"},
            ) as resp:
                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = await resp.json()
                    return JSONResponse(status_code=resp.status, content=data)
                text = await resp.text()
                return JSONResponse(status_code=resp.status, content={"detail": text})
    except Exception as e:
        logging.error(f"Auth register proxy error: {e}")
        raise HTTPException(status_code=502, detail="Auth service unavailable")


@app.get("/api/auth/me")
async def auth_me(request: Request):
    """
    Получение информации о текущем пользователе через внешний сервис аутентификации.
    """
    token = await auth.get_token_from_header(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    url = f"{auth.AUTH_SERVICE_BASE_URL}/api/auth/me"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={
                    "accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            ) as resp:
                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    data = await resp.json()
                    return JSONResponse(status_code=resp.status, content=data)
                text = await resp.text()
                return JSONResponse(status_code=resp.status, content={"detail": text})
    except Exception as e:
        logging.error(f"Auth me proxy error: {e}")
        raise HTTPException(status_code=502, detail="Auth service unavailable")


@app.get("/api/chats")
@limiter.limit("60/minute")
async def read_chats(request: Request, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    chats_data = await get_chats_with_last_messages(db)
    return chats_data

@app.get("/api/chats/{chat_id}")
async def read_chat(chat_id: int, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    chat = await get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@app.get("/api/chats/{chat_id}/messages")
async def read_messages(
    chat_id: int,
    page: int = 1,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(auth.require_auth)
):
    offset = (page - 1) * limit
    return await get_chat_messages(db, chat_id, limit, offset)

# Schemas
class ChatCreate(BaseModel):
    uuid: str
    ai: bool = False

@app.post("/api/chats")
async def create_chat_endpoint(chat: ChatCreate, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    return await create_chat(db, chat.uuid, chat.ai)

class MessageCreate(BaseModel):
    chat_id: int
    message: str
    message_type: str
    ai: bool = False

    @validator('message')
    def message_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        if len(v) > 4000:
            raise ValueError('Message too long')
        return v

@app.post("/api/messages")
async def create_message_endpoint(msg: MessageCreate, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    # 1. Создаем сообщение в БД
    db_msg = await create_message(
        db=db,
        chat_id=msg.chat_id,
        message=msg.message,
        message_type=msg.message_type,
        ai=msg.ai
    )

    # 2. Получаем информацию о чате
    chat = await get_chat(db, msg.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # 3. Отправляем сообщение в соответствующий мессенджер (best-effort)
    delivered = True
    delivery_error: Optional[str] = None
    try:
        if chat.messager == "telegram":
            if not bot:
                delivered = False
                delivery_error = "Telegram bot is not configured (BOT_TOKEN missing)"
            else:
                tg_chat_id = int(chat.uuid) if str(chat.uuid).isdigit() else chat.uuid
                await bot.send_message(chat_id=tg_chat_id, text=msg.message)
        elif chat.messager == "vk":
            if not vk:
                delivered = False
                delivery_error = "VK bot is not configured (VK_TOKEN/VK_GROUP_ID missing)"
            else:
                await asyncio.to_thread(
                    vk.messages.send,
                    peer_id=int(chat.uuid),
                    message=msg.message,
                    random_id=0
                )
    except Exception as e:
        delivered = False
        delivery_error = str(e)
        logging.error(f"Error sending message to {chat.messager}: {e}")

    if msg.message_type == "answer":
        await update_chat_waiting(db, msg.chat_id, False)
        stats = await get_stats(db)
        await updates_manager.broadcast(json.dumps({
            "type": "chat_update",
            "chat_id": msg.chat_id,
            "waiting": False
        }))
        await updates_manager.broadcast(json.dumps({
            "type": "stats_update",
            "total": stats["total"], 
            "pending": stats["pending"], 
            "ai": stats["ai"]
        }))

    message_for_frontend = {
        "type": "message",
        "chatId": str(db_msg.chat_id),
        "content": db_msg.message,
        "message_type": db_msg.message_type,
        "ai": db_msg.ai,
        "timestamp": db_msg.created_at.isoformat(),
        "id": db_msg.id
    }
    await messages_manager.broadcast(json.dumps(message_for_frontend))

    # Если ответ менеджера — дублируем в форум-топик (чтобы видно было в группе)
    if msg.message_type == "answer" and FORUM_GROUP_ID and bot and chat.topic_id:
        try:
            await bot.send_message(
                chat_id=FORUM_GROUP_ID,
                message_thread_id=chat.topic_id,
                text=f"[Менеджер (веб)]:\n{msg.message}"
            )
        except Exception as e:
            logging.error("Failed to forward web-dashboard reply to forum: %s", e)

    return {"message": db_msg, "delivered": delivered, "delivery_error": delivery_error}

class WaitingUpdate(BaseModel):
    waiting: bool

@app.put("/api/chats/{chat_id}/waiting")
async def update_waiting(chat_id: int, data: WaitingUpdate, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    chat = await get_chat(db, chat_id)
    old_waiting = chat.waiting
    chat = await update_chat_waiting(db, chat_id, data.waiting)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.waiting != old_waiting:
        stats = await get_stats(db)
        await updates_manager.broadcast(json.dumps({
                    "type": "stats_update",
                    "total": stats["total"], 
                    "pending": stats["pending"], 
                    "ai": stats["ai"]
                }))
    return {"success": True, "chat": chat}

class AIUpdate(BaseModel):
    ai: bool

@app.put("/api/chats/{chat_id}/ai")
async def update_ai(chat_id: int, data: AIUpdate, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    chat = await update_chat_ai(db, chat_id, data.ai)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    # Отправляем обновление по WebSocket
    update_message = {
        "type": "chat_ai_updated",
        "chatId": str(chat_id),
        "ai": chat.ai
    }
    await updates_manager.broadcast(json.dumps(update_message))
    return chat

class MarkUpdate(BaseModel):
    mark: Optional[str] = None

@app.put("/api/chats/{chat_id}/mark")
async def update_mark(chat_id: int, data: MarkUpdate, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    if data.mark is not None and data.mark not in ("unread", "reply_later"):
        raise HTTPException(status_code=400, detail="mark must be 'unread', 'reply_later' or null")
    chat = await get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.mark = data.mark
    await db.commit()
    await db.refresh(chat)
    await updates_manager.broadcast(json.dumps({
        "type": "chat_mark_updated",
        "chat_id": chat_id,
        "mark": data.mark
    }))
    return {"success": True, "chat_id": chat_id, "mark": data.mark}

@app.get("/api/stats")
@limiter.limit("60/minute")
async def stats(request: Request, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    return await get_stats(db)

class TagCreate(BaseModel):
    tag: str

@app.post("/api/chats/{chat_id}/tags")
async def add_chat_tag_endpoint(chat_id: int, tag_data: TagCreate, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    result = await crud.add_chat_tag(db, chat_id, tag_data.tag)
    if result.get("success"):
        # Broadcast updated tags via WebSocket
        update_message = {
            "type": "chat_tags_updated",
            "chatId": chat_id,
            "tags": result["tags"]
        }
        await updates_manager.broadcast(json.dumps(update_message))
    return result

@app.delete("/api/chats/{chat_id}/tags/{tag}")
async def remove_chat_tag_endpoint(chat_id: int, tag: str, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    result = await crud.remove_chat_tag(db, chat_id, tag)
    if result.get("success"):
        # Broadcast updated tags via WebSocket
        update_message = {
            "type": "chat_tags_updated",
            "chatId": chat_id,
            "tags": result["tags"]
        }
        await updates_manager.broadcast(json.dumps(update_message))
    return result

@app.delete("/api/chats/{chat_id}")
async def delete_chat(chat_id: int, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    chat = await get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    # Удаляем все сообщения этого чата
    messages = await db.execute(select(Message).where(Message.chat_id == chat_id))
    for msg in messages.scalars().all():
        await db.delete(msg)
    await db.delete(chat)
    await db.commit()
    # Отправляем уведомление по WebSocket всем фронтендам
    update_message = {
        "type": "chat_deleted",
        "chatId": str(chat_id)
    }
    await updates_manager.broadcast(json.dumps(update_message))
    return {"success": True}

@app.delete("/api/messages/{message_id}")
async def delete_message_endpoint(message_id: int, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.message_type != "answer":
        raise HTTPException(status_code=403, detail="Can only delete own (answer) messages")
    chat = await get_chat(db, msg.chat_id)
    # Best-effort delete from messenger
    if chat:
        try:
            if chat.messager == "vk" and vk:
                await asyncio.to_thread(vk.messages.delete, message_ids=[message_id], delete_for_all=1)
            elif chat.messager == "telegram" and bot:
                tg_chat_id = int(chat.uuid) if str(chat.uuid).isdigit() else chat.uuid
                await bot.delete_message(chat_id=tg_chat_id, message_id=message_id)
        except Exception as e:
            logging.warning(f"Could not delete message from messenger: {e}")
    chat_id = msg.chat_id
    await db.delete(msg)
    await db.commit()
    await updates_manager.broadcast(json.dumps({
        "type": "message_deleted",
        "message_id": message_id,
        "chat_id": chat_id
    }))
    return {"success": True}

class MessageEdit(BaseModel):
    message: str

@app.put("/api/messages/{message_id}")
async def edit_message_endpoint(message_id: int, data: MessageEdit, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.message_type != "answer":
        raise HTTPException(status_code=403, detail="Can only edit own (answer) messages")
    chat = await get_chat(db, msg.chat_id)
    # Best-effort edit in messenger
    if chat:
        try:
            if chat.messager == "vk" and vk:
                await asyncio.to_thread(vk.messages.edit, peer_id=int(chat.uuid), message_id=message_id, message=data.message)
            elif chat.messager == "telegram" and bot:
                tg_chat_id = int(chat.uuid) if str(chat.uuid).isdigit() else chat.uuid
                await bot.edit_message_text(chat_id=tg_chat_id, message_id=message_id, text=data.message)
        except Exception as e:
            logging.warning(f"Could not edit message in messenger: {e}")
    msg.message = data.message
    msg.edited_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)
    await updates_manager.broadcast(json.dumps({
        "type": "message_edited",
        "message_id": message_id,
        "chat_id": msg.chat_id,
        "message": data.message,
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None
    }))
    return {"success": True, "message": msg.message, "edited_at": msg.edited_at.isoformat() if msg.edited_at else None}

@app.post("/api/chats/{chat_id}/sync-vk")
async def sync_vk_chat(chat_id: int, db: AsyncSession = Depends(get_db), _: bool = Depends(auth.require_auth)):
    """
    Синхронизирует VK чат с базой данных.
    Проверяет количество сообщений в VK и БД, и если они не совпадают,
    удаляет все сообщения из БД и добавляет все из VK.
    """
    result = await sync_vk(db, chat_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Sync failed"))
    
    # Отправляем обновление через WebSocket, чтобы фронтенд обновил сообщения
    update_message = {
        "type": "chat_synced",
        "chatId": str(chat_id),
        "vk_count": result.get("vk_count", 0),
        "db_count_before": result.get("db_count_before", 0),
        "db_count_after": result.get("db_count_after", 0)
    }
    await updates_manager.broadcast(json.dumps(update_message))
    
    # Также отправляем обновление сообщений
    messages_update = {
        "type": "messages_updated",
        "chatId": str(chat_id)
    }
    await messages_manager.broadcast(json.dumps(messages_update))
    
    return result


# ================== API Аналитики диалогов ==================

class AssignChatRequest(BaseModel):
    manager_id: int
    manager_name: str

@app.post("/api/chats/{chat_id}/assign")
async def assign_chat_endpoint(
    chat_id: int, 
    data: AssignChatRequest, 
    db: AsyncSession = Depends(get_db), 
    _: bool = Depends(auth.require_auth)
):
    """
    Назначает диалог менеджеру (кнопка 'Взять диалог').
    После назначения диалог готов к отслеживанию для аналитики.
    """
    result = await assign_chat_to_manager(db, chat_id, data.manager_id, data.manager_name)
    
    if not result:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if result.get("error") == "already_assigned":
        raise HTTPException(
            status_code=409, 
            detail=f"Dialog already assigned to {result.get('assigned_to')}"
        )
    
    # Отправляем обновление через WebSocket
    update_message = {
        "type": "chat_assigned",
        "chatId": str(chat_id),
        "manager_id": data.manager_id,
        "manager_name": data.manager_name,
        "assigned_at": result.get("assigned_at")
    }
    await updates_manager.broadcast(json.dumps(update_message))
    
    return result


@app.post("/api/chats/{chat_id}/close")
async def close_chat_endpoint(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(auth.require_auth)
):
    """
    Закрывает диалог и запускает AI-аналитику.
    Анализирует всю переписку и сохраняет результаты.
    """
    chat = await get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Получаем все сообщения диалога
    messages = await get_chat_messages(db, chat_id, limit=1000)
    
    if not messages:
        raise HTTPException(status_code=400, detail="No messages in dialog")
    
    # Запускаем AI-анализ
    analysis_result = await _ai_analyze_dialog(messages, chat.assigned_manager_name)
    
    # Закрываем диалог
    close_result = await close_chat_dialog(db, chat_id)
    await update_chat_waiting(db=db, chat_id=chat_id, waiting=False)
    updated_chat = await update_chat_ai(db=db, chat_id=chat_id, ai=True)
    if updated_chat:
        await updates_manager.broadcast(json.dumps({
            "type": "chat_update",
            "chat_id": chat_id,
            "waiting": updated_chat.waiting,
            "ai": updated_chat.ai,
            "dialog_status": updated_chat.dialog_status
        }))
    
    if analysis_result:
        # Вычисляем длительность диалога
        duration_minutes = None
        if len(messages) >= 2:
            try:
                first_ts = messages[0].get("timestamp")
                last_ts = messages[-1].get("timestamp")
                if first_ts and last_ts:
                    from datetime import datetime as dt
                    first_dt = dt.fromisoformat(first_ts.replace('Z', '+00:00')) if isinstance(first_ts, str) else first_ts
                    last_dt = dt.fromisoformat(last_ts.replace('Z', '+00:00')) if isinstance(last_ts, str) else last_ts
                    duration_minutes = int((last_dt - first_dt).total_seconds() / 60)
            except Exception:
                pass
        
        # Сохраняем аналитику в БД
        analytics_data = {
            "chat_id": chat_id,
            "manager_id": chat.assigned_manager_id,
            "manager_name": chat.assigned_manager_name,
            "channel": chat.messager,
            "summary": analysis_result.get("summary"),
            "customer_problem": analysis_result.get("customer_problem"),
            "customer_intent": analysis_result.get("customer_intent"),
            "refund_reason": analysis_result.get("refund_reason"),
            "manager_quality_score": analysis_result.get("manager_quality_score"),
            "manager_quality_notes": analysis_result.get("manager_quality_notes"),
            "customer_sentiment": analysis_result.get("customer_sentiment"),
            "resolution_status": analysis_result.get("resolution_status"),
            "key_topics": analysis_result.get("key_topics", []),
            "recommendations": analysis_result.get("recommendations"),
            "messages_count": len(messages),
            "dialog_duration_minutes": duration_minutes,
            "raw_ai_response": analysis_result.get("raw_response")
        }
        
        try:
            analytics = await create_dialog_analytics(db, analytics_data)
            
            # Отправляем обновление через WebSocket
            update_message = {
                "type": "dialog_closed",
                "chatId": str(chat_id),
                "analytics_id": analytics.id,
                "summary": analysis_result.get("summary"),
                "manager_quality_score": analysis_result.get("manager_quality_score")
            }
            await updates_manager.broadcast(json.dumps(update_message))
            
            return {
                "success": True,
                "chat_id": chat_id,
                "status": "closed",
                "analytics": {
                    "id": analytics.id,
                    "summary": analytics.summary,
                    "customer_problem": analytics.customer_problem,
                    "customer_intent": analytics.customer_intent,
                    "manager_quality_score": analytics.manager_quality_score,
                    "customer_sentiment": analytics.customer_sentiment
                }
            }
        except Exception as e:
            logging.error(f"Failed to save analytics: {e}")
            return {
                "success": True,
                "chat_id": chat_id,
                "status": "closed",
                "analytics": None,
                "error": "Failed to save analytics"
            }
    
    return {
        "success": True,
        "chat_id": chat_id,
        "status": "closed",
        "analytics": None,
        "error": "AI analysis failed"
    }


@app.get("/api/chats/{chat_id}/analytics")
async def get_chat_analytics_endpoint(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(auth.require_auth)
):
    """Получает аналитику для конкретного диалога"""
    analytics = await get_dialog_analytics(db, chat_id)
    
    if not analytics:
        raise HTTPException(status_code=404, detail="Analytics not found for this chat")
    
    return {
        "id": analytics.id,
        "chat_id": analytics.chat_id,
        "manager_name": analytics.manager_name,
        "channel": analytics.channel,
        "summary": analytics.summary,
        "customer_problem": analytics.customer_problem,
        "customer_intent": analytics.customer_intent,
        "refund_reason": analytics.refund_reason,
        "manager_quality_score": analytics.manager_quality_score,
        "manager_quality_notes": analytics.manager_quality_notes,
        "customer_sentiment": analytics.customer_sentiment,
        "resolution_status": analytics.resolution_status,
        "key_topics": analytics.key_topics,
        "recommendations": analytics.recommendations,
        "messages_count": analytics.messages_count,
        "dialog_duration_minutes": analytics.dialog_duration_minutes,
        "created_at": analytics.created_at.isoformat() if analytics.created_at else None
    }


@app.get("/api/analytics")
@limiter.limit("60/minute")
async def get_all_analytics_endpoint(
    request: Request,
    page: int = 1,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(auth.require_auth)
):
    """Получает список всех аналитик с пагинацией"""
    offset = (page - 1) * limit
    analytics_list = await get_all_analytics(db, limit, offset)
    return analytics_list


@app.get("/api/analytics/stats")
@limiter.limit("60/minute")
async def get_analytics_stats_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(auth.require_auth)
):
    """Получает общую статистику по аналитике"""
    return await get_analytics_stats(db)


@app.post("/api/messages/image")
async def upload_image(
    image: UploadFile = File(...),
    chat_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(auth.require_auth)
):
    # 1. Получаем информацию о чате
    chat = await get_chat(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # 2. Читаем содержимое файла
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # 3. Генерируем имя файла
    file_ext = os.path.splitext(image.filename)[1] or ".jpg"
    file_name = f"{chat.uuid}-{int(datetime.utcnow().timestamp())}{file_ext}"

    # 4. Загружаем в MinIO
    try:
        await asyncio.to_thread(
            minio_client.put_object,
            BUCKET_NAME,
            file_name,
            io.BytesIO(content),
            len(content),
            content_type="image/jpeg"
        )
        img_url = build_public_minio_url(file_name)
    except Exception as e:
        logging.error(f"MinIO upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image")

    # 5. Сохраняем сообщение в БД
    db_img = Message(
        chat_id=chat_id,
        message=img_url,
        message_type="answer",
        ai=False,
        created_at=datetime.utcnow(),
        is_image=True
    )
    db.add(db_img)
    await db.commit()
    await db.refresh(db_img)

    # 6. Отправляем фотографию в соответствующий мессенджер (best-effort)
    delivered = True
    delivery_error: Optional[str] = None
    try:
        if chat.messager == "telegram":
            if not bot:
                delivered = False
                delivery_error = "Telegram bot is not configured (BOT_TOKEN missing)"
                raise RuntimeError(delivery_error)
            # Создаем временный файл для отправки в Telegram
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                temp_file.write(content)
                temp_file.flush()
                # Отправка в Telegram
                tg_chat_id = int(chat.uuid) if str(chat.uuid).isdigit() else chat.uuid
                await bot.send_photo(chat_id=tg_chat_id, photo=FSInputFile(temp_file.name))
            # Удаляем временный файл
            os.unlink(temp_file.name)
        elif chat.messager == "vk":
            if not vk:
                delivered = False
                delivery_error = "VK bot is not configured (VK_TOKEN/VK_GROUP_ID missing)"
                raise RuntimeError(delivery_error)
            # Загружаем фото на сервер VK
            upload_url = await asyncio.to_thread(
                vk.photos.getMessagesUploadServer
            )
            upload_url = upload_url['upload_url']

            current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
            try:
                form = aiohttp.FormData()
                form.add_field('photo', content, filename='photo.jpg')
                async with current_session.post(upload_url, data=form) as resp:
                    if resp.status != 200:
                        raise Exception(f"Failed to upload photo to VK: {resp.status}")
                    upload_result = await resp.json()
            finally:
                if current_session != http_session: await current_session.close()

            # Сохраняем фото на сервере VK
            photo_data = await asyncio.to_thread(
                vk.photos.saveMessagesPhoto,
                photo=upload_result['photo'],
                server=upload_result['server'],
                hash=upload_result['hash']
            )

            # Отправляем сообщение с фото в VK
            await asyncio.to_thread(
                vk.messages.send,
                peer_id=int(chat.uuid),
                attachment=f"photo{photo_data[0]['owner_id']}_{photo_data[0]['id']}",
                random_id=0
            )
    except Exception as e:
        delivered = False
        delivery_error = str(e)
        logging.error(f"Error sending photo to {chat.messager}: {e}")

    # 7. Отправляем сообщение через WebSocket
    message_for_frontend = {
        "type": "message",
        "chatId": str(db_img.chat_id),
        "content": db_img.message,
        "message_type": db_img.message_type,
        "ai": db_img.ai,
        "timestamp": db_img.created_at.isoformat(),
        "id": db_img.id,
        "is_image": True
    }
    await messages_manager.broadcast(json.dumps(message_for_frontend))

    # 8. Дублируем фото в форум-топик (ответ менеджера с веб-дашборда)
    if FORUM_GROUP_ID and bot and chat.topic_id:
        try:
            photo_input = BufferedInputFile(content, filename=file_name)
            await bot.send_photo(
                chat_id=FORUM_GROUP_ID,
                message_thread_id=chat.topic_id,
                photo=photo_input,
                caption="[Менеджер (веб)]: 📷 Фото"
            )
        except Exception as e:
            logging.error("Failed to forward web-dashboard photo to forum: %s", e)

    return {"message": db_img, "delivered": delivered, "delivery_error": delivery_error}

def _is_forum_group(message: types.Message) -> bool:
    """Проверяет, что сообщение пришло из нашей форум-группы"""
    return bool(FORUM_GROUP_ID and message.chat and message.chat.id == FORUM_GROUP_ID)

@dp.message(lambda m: _is_forum_group(m) and m.text and m.message_thread_id)
async def handle_forum_text_reply(message: types.Message):
    """Менеджер ответил текстом в топике форум-группы → пересылаем клиенту"""
    global _bot_user_id
    if bot and not _bot_user_id:
        _bot_user_id = (await bot.get_me()).id
    if message.from_user and message.from_user.id == _bot_user_id:
        return

    topic_id = message.message_thread_id
    text = message.text

    async with async_session() as session:
        chat = await get_chat_by_topic_id(session, topic_id)
        if not chat:
            await message.reply("⚠️ Не найден клиент для этого топика.")
            return

        # Сохраняем сообщение менеджера в БД
        db_msg = await create_message(
            db=session,
            chat_id=chat.id,
            message=text,
            message_type="answer",
            ai=False
        )

        # Отправляем клиенту
        delivered = True
        delivery_error = None
        try:
            if chat.messager == "telegram":
                tg_chat_id = int(chat.uuid) if str(chat.uuid).isdigit() else chat.uuid
                await bot.send_message(chat_id=tg_chat_id, text=text)
            elif chat.messager == "vk":
                if vk:
                    await asyncio.to_thread(
                        vk.messages.send,
                        peer_id=int(chat.uuid),
                        message=text,
                        random_id=0
                    )
                else:
                    delivered = False
                    delivery_error = "VK not configured"
            else:
                delivered = False
                delivery_error = f"Unknown messager: {chat.messager}"
        except Exception as e:
            delivered = False
            delivery_error = str(e)
            logging.error("Forum reply delivery error (chat %s, %s): %s", chat.id, chat.messager, e)

        # Снимаем waiting, обновляем фронт
        await update_chat_waiting(session, chat.id, False)
        stats = await get_stats(session)

        await updates_manager.broadcast(json.dumps({
            "type": "chat_update",
            "chat_id": chat.id,
            "waiting": False
        }))
        await updates_manager.broadcast(json.dumps({
            "type": "stats_update",
            "total": stats["total"],
            "pending": stats["pending"],
            "ai": stats["ai"]
        }))

        message_for_frontend = {
            "type": "message",
            "chatId": str(db_msg.chat_id),
            "content": db_msg.message,
            "message_type": db_msg.message_type,
            "ai": db_msg.ai,
            "timestamp": db_msg.created_at.isoformat(),
            "id": db_msg.id
        }
        await messages_manager.broadcast(json.dumps(message_for_frontend))

        status_icon = "✅" if delivered else "⚠️"
        err_detail = f" ({delivery_error})" if delivery_error else ""
        await message.reply(f"{status_icon} Доставлено клиенту ({chat.messager.upper()}){err_detail}")


@dp.message(lambda m: _is_forum_group(m) and m.photo and m.message_thread_id)
async def handle_forum_photo_reply(message: types.Message):
    """Менеджер отправил фото в топике форум-группы → пересылаем клиенту"""
    global _bot_user_id
    if bot and not _bot_user_id:
        _bot_user_id = (await bot.get_me()).id
    if message.from_user and message.from_user.id == _bot_user_id:
        return

    topic_id = message.message_thread_id

    async with async_session() as session:
        chat = await get_chat_by_topic_id(session, topic_id)
        if not chat:
            await message.reply("⚠️ Не найден клиент для этого топика.")
            return

        # Скачиваем фото
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_data = await bot.download_file(file.file_path)
        content = file_data.read() if hasattr(file_data, 'read') else file_data

        # Сохраняем в MinIO
        file_ext = os.path.splitext(file.file_path)[1] or ".jpg"
        file_name = f"forum-{chat.id}-{int(datetime.utcnow().timestamp())}{file_ext}"
        try:
            minio_client.put_object(
                bucket_name=BUCKET_NAME,
                object_name=file_name,
                data=io.BytesIO(content),
                length=len(content),
                content_type="image/jpeg"
            )
            image_url = build_public_minio_url(file_name)
        except Exception as e:
            logging.error("MinIO upload error in forum photo: %s", e)
            await message.reply("⚠️ Не удалось загрузить фото.")
            return

        caption = message.caption or ""
        message_content = f"{image_url}|{caption}" if caption else image_url

        db_msg = crud.Message(
            chat_id=chat.id,
            message=message_content,
            message_type="answer",
            ai=False,
            created_at=datetime.utcnow(),
            is_image=True
        )
        session.add(db_msg)
        await session.commit()
        await session.refresh(db_msg)

        # Отправляем клиенту
        delivered = True
        delivery_error = None
        try:
            if chat.messager == "telegram":
                tg_chat_id = int(chat.uuid) if str(chat.uuid).isdigit() else chat.uuid
                photo_input = BufferedInputFile(content, filename=file_name)
                await bot.send_photo(chat_id=tg_chat_id, photo=photo_input, caption=caption or None)
            elif chat.messager == "vk":
                if vk:
                    upload_url_resp = await asyncio.to_thread(vk.photos.getMessagesUploadServer)
                    upload_url = upload_url_resp['upload_url']
                    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
                    try:
                        form = aiohttp.FormData()
                        form.add_field('photo', content, filename='photo.jpg')
                        async with current_session.post(upload_url, data=form) as resp:
                            upload_result = await resp.json()
                    finally:
                        if current_session != http_session:
                            await current_session.close()
                    photo_data = await asyncio.to_thread(
                        vk.photos.saveMessagesPhoto,
                        photo=upload_result['photo'],
                        server=upload_result['server'],
                        hash=upload_result['hash']
                    )
                    await asyncio.to_thread(
                        vk.messages.send,
                        peer_id=int(chat.uuid),
                        attachment=f"photo{photo_data[0]['owner_id']}_{photo_data[0]['id']}",
                        message=caption or "",
                        random_id=0
                    )
                else:
                    delivered = False
                    delivery_error = "VK not configured"
        except Exception as e:
            delivered = False
            delivery_error = str(e)
            logging.error("Forum photo delivery error (chat %s, %s): %s", chat.id, chat.messager, e)

        # Обновляем фронт
        await update_chat_waiting(session, chat.id, False)

        message_for_frontend = {
            "type": "message",
            "chatId": str(db_msg.chat_id),
            "content": db_msg.message,
            "message_type": db_msg.message_type,
            "ai": db_msg.ai,
            "timestamp": db_msg.created_at.isoformat(),
            "id": db_msg.id,
            "is_image": True
        }
        await messages_manager.broadcast(json.dumps(message_for_frontend))

        status_icon = "✅" if delivered else "⚠️"
        err_detail = f" ({delivery_error})" if delivery_error else ""
        await message.reply(f"{status_icon} Фото доставлено клиенту ({chat.messager.upper()}){err_detail}")


@dp.message(lambda m: _is_forum_group(m))
async def handle_forum_ignore(message: types.Message):
    """Все остальные сообщения в форум-группе — игнорируем (не обрабатываем как клиентские)"""
    return


# ===================== END FORUM GROUP HANDLERS =====================

@dp.message(Command("reindex"))
async def cmd_reindex(message: Message):
    """Команда для принудительной переиндексации базы знаний"""
    async with async_session() as session:
        await message.answer("🔄 Начинаю переиндексацию базы знаний...")
        result = await _ai_reindex(session)
        if result.get("ok"):
            await message.answer(f"✅ База знаний обновлена! Загружено {result.get('chunks', 0)} записей.")
        else:
            await message.answer(f"❌ Ошибка переиндексации: {result.get('error', 'Unknown error')}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Проверяем, является ли пользователь админом
    notification_manager = notifications.get_notification_manager()
    if notification_manager:
        user_username = message.from_user.username
        if user_username and user_username in notification_manager.admin_usernames:
            # Сохраняем chat_id админа
            await notification_manager.save_admin_chat_id(user_username, message.chat.id)
            
            # Отправляем приветствие с клавиатурой управления уведомлениями
            await message.answer(
                "👋 Добро пожаловать в панель администратора!\n\n"
                "Здесь вы можете управлять уведомлениями о новых сообщениях.",
                reply_markup=notification_manager.get_notification_keyboard(user_username)
            )
            return
    
    # Обычное приветствие для обычных пользователей
    await message.answer(_tg_main_text(), reply_markup=tg_kb_main(), parse_mode="HTML")

@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(_tg_main_text(), reply_markup=tg_kb_main(), parse_mode="HTML")

@dp.message(Command("faq"))
async def cmd_faq(message: Message):
    await message.answer(_tg_faq_text(1), reply_markup=tg_kb_faq_menu(1), parse_mode="HTML")

@dp.message(Command("test"))
async def cmd_test(message: Message):
    if not XAI_API_KEY:
        await message.answer("❌ XAI_API_KEY не настроен")
        return
    question = (message.text or "").split(maxsplit=1)[1] if len((message.text or "").split(maxsplit=1)) > 1 else ""
    if not question.strip():
        await message.answer("Использование: /test <вопрос>\nОтправит вопрос через XAI Grok")
        return
    json_format = (
        "\nФормат ответа — ТОЛЬКО JSON без markdown:\n"
        '{"answer": "твой ответ", "handoff": false, "confidence": 0.8}\n'
        "answer — текст ответа клиенту, handoff — true если нужен менеджер, "
        "confidence — уверенность 0.0-1.0."
    )
    msgs = [
        {"role": "system", "content": AI_SUPPORT_PROMPT + json_format},
        {"role": "user", "content": question},
    ]
    data = await _ai_openrouter(msgs, use_xai=True)
    if not data:
        await message.answer("❌ Ошибка вызова XAI API")
        return
    try:
        content = data["choices"][0]["message"]["content"].strip()
    except Exception:
        await message.answer("❌ Не удалось разобрать ответ XAI")
        return
    parsed = _ai_extract_json(content)
    if parsed and parsed.get("answer"):
        answer = str(parsed["answer"]).strip()
    elif content:
        answer = content
    else:
        await message.answer("XAI вернул пустой ответ")
        return
    await message.answer(f"🧪 [{XAI_MODEL}]\n{answer}")

@dp.callback_query(F.data.startswith("m:"))
async def handle_menu_callback(callback: types.CallbackQuery):
    parts = (callback.data or "").split(":")
    if len(parts) < 2:
        await callback.answer()
        return
    action = parts[1]
    async def _edit_or_send(text: str, reply_markup: Optional[types.InlineKeyboardMarkup] = None) -> None:
        msg = callback.message
        if not msg:
            return
        try:
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            await msg.answer(text, reply_markup=reply_markup, parse_mode="HTML")

    try:
        if action == "home":
            await _edit_or_send(_tg_main_text(), tg_kb_main())
            return
        if action == "faq":
            if len(parts) == 2:
                await _edit_or_send(_tg_faq_text(1), tg_kb_faq_menu(1))
                return
            if len(parts) >= 4 and parts[2] == "page" and str(parts[3]).isdigit():
                page = int(parts[3])
                await _edit_or_send(_tg_faq_text(page), tg_kb_faq_menu(page))
                return
            if len(parts) >= 5 and parts[2] == "item":
                item_id = parts[3]
                page = int(parts[4]) if str(parts[4]).isdigit() else 1
                if str(item_id).isdigit():
                    idx = int(item_id)
                    if 0 <= idx < len(FAQ_ORDER):
                        item_id = FAQ_ORDER[idx]
                await _edit_or_send(_tg_faq_item_text(item_id), tg_kb_faq_item(item_id, page))
                return
            item_id = parts[2]
            await _edit_or_send(_tg_faq_item_text(item_id), tg_kb_faq_item(item_id, 1))
            return
        if action == "cat":
            if len(parts) == 2:
                categories = await catalog_get_categories()
                if not categories:
                    reason = str(_catalog_cache.get("last_error") or "").strip()
                    details = f"\n<blockquote>{html.escape(reason)}</blockquote>" if reason else "\n<blockquote>Пока недоступен</blockquote>"
                    await _edit_or_send(f"<b>Каталог</b>{details}", _tg_kb([[{"text": "⬅️ Назад", "data": "m:home"}]]))
                    return
                rows: List[List[Dict[str, str]]] = []
                row: List[Dict[str, str]] = []
                for c in categories[:12]:
                    cid = str(c.get("slug") or "")
                    name = str(c.get("name") or "Категория")[:28]
                    if not cid:
                        continue
                    row.append({"text": name, "data": f"m:cat:{cid}:1"})
                    if len(row) == 2:
                        rows.append(row)
                        row = []
                if row:
                    rows.append(row)
                rows.append([{"text": "⬅️ Назад", "data": "m:home"}])
                await _edit_or_send("<b>Каталог</b>\n<blockquote>Выберите категорию</blockquote>", _tg_kb(rows))
                return
            if len(parts) < 3:
                await _edit_or_send("<b>Каталог</b>\n<blockquote>Не понял категорию</blockquote>", _tg_kb([[{"text": "⬅️ Назад", "data": "m:cat"}], [{"text": "🏠 Меню", "data": "m:home"}]]))
                return

            category_id = parts[2]
            page = 1
            if len(parts) >= 4 and str(parts[3]).isdigit():
                page = int(parts[3])
            limit = 8
            items_data = await catalog_get_products(category_id, page=page, limit=limit)
            if not items_data:
                reason = str(_catalog_cache.get("last_error") or "").strip()
                details = f"\n<blockquote>{html.escape(reason)}</blockquote>" if reason else "\n<blockquote>Пусто или API недоступен</blockquote>"
                await _edit_or_send(f"<b>Каталог</b>{details}", _tg_kb([[{"text": "⬅️ Назад", "data": "m:cat"}], [{"text": "🏠 Меню", "data": "m:home"}]]))
                return

            state = _get_state("tg", str(callback.message.chat.id))
            state["last_category"] = category_id
            state["last_page"] = page

            rows: List[List[Dict[str, str]]] = []
            row: List[Dict[str, str]] = []
            items = items_data.get("items") or []
            for p in items:
                row.append({"text": str(p.get("name") or "Товар")[:28], "data": f"m:prod:{p['id']}"})
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)

            nav_row: List[Dict[str, str]] = []
            if page > 1:
                nav_row.append({"text": "⬅️", "data": f"m:cat:{category_id}:{page-1}"})
            if items_data.get("has_next"):
                nav_row.append({"text": "➡️", "data": f"m:cat:{category_id}:{page+1}"})
            if nav_row:
                rows.append(nav_row)
            rows.append([{"text": "⬅️ Категории", "data": "m:cat"}])
            rows.append([{"text": "🏠 Меню", "data": "m:home"}])
            await _edit_or_send(f"<b>Каталог</b>\n<blockquote>Страница {page}</blockquote>", _tg_kb(rows))
            return
    except Exception:
        logging.exception("TG callback handler failed: %r", callback.data)
        if callback.message:
            try:
                await callback.message.answer("Что-то пошло не так. Напишите /menu", reply_markup=tg_kb_main())
            except Exception:
                pass
    finally:
        try:
            await callback.answer()
        except Exception:
            pass

    if action == "prod" and len(parts) >= 3:
        product_id = parts[2]
        product = await catalog_get_product(product_id)
        if not product:
            await callback.message.answer("Товар не найден.")
            return
        state = _get_state("tg", str(callback.message.chat.id))
        back_data = f"m:cat:{state['last_category']}:{state.get('last_page', 1)}" if state.get("last_category") else "m:cat"
        info = await _tg_get_product_images(product, product_id, 0)
        colors = info["colors"]
        color_idx = info["color_idx"]
        selected_color = info["color"]
        images: List[str] = info["images"]
        img_idx = 0
        image_url = images[img_idx] if images else None
        kb = _tg_product_kb(product_id, colors, color_idx, img_idx, len(images), back_data)
        caption = tg_product_caption(product, color=selected_color)
        if image_url:
            payload = await _tg_download_as_input_file(image_url)
            if payload and payload.get("is_photo"):
                await callback.message.answer_photo(photo=payload["file"], caption=caption, parse_mode="HTML", reply_markup=kb)
            elif payload:
                await callback.message.answer_document(document=payload["file"], caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                await callback.message.answer(caption, parse_mode="HTML", reply_markup=kb)
        else:
            await callback.message.answer(caption, parse_mode="HTML", reply_markup=kb)
        return

    if action == "color" and len(parts) >= 4:
        product_id = parts[2]
        idx = int(parts[3]) if str(parts[3]).isdigit() else 0
        img_idx = int(parts[4]) if len(parts) >= 5 and str(parts[4]).isdigit() else 0
        product = await catalog_get_product(product_id)
        if not product:
            return
        state = _get_state("tg", str(callback.message.chat.id))
        back_data = f"m:cat:{state['last_category']}:{state.get('last_page', 1)}" if state.get("last_category") else "m:cat"
        info = await _tg_get_product_images(product, product_id, idx)
        colors = info["colors"]
        color_idx = info["color_idx"]
        color = info["color"]
        images: List[str] = info["images"]
        if images:
            img_idx = max(0, min(int(img_idx or 0), len(images) - 1))
        else:
            img_idx = 0
        image_url = images[img_idx] if images else None
        kb = _tg_product_kb(product_id, colors, color_idx, img_idx, len(images), back_data)
        caption = tg_product_caption(product, color=color)
        if image_url:
            try:
                payload = await _tg_download_as_input_file(image_url)
                if payload and payload.get("is_photo"):
                    await callback.message.edit_media(
                        types.InputMediaPhoto(media=payload["file"], caption=caption, parse_mode="HTML"),
                        reply_markup=kb,
                    )
                elif payload:
                    await callback.message.answer_document(document=payload["file"], caption=caption, parse_mode="HTML", reply_markup=kb)
                else:
                    await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
            except Exception:
                payload = await _tg_download_as_input_file(image_url)
                if payload and payload.get("is_photo"):
                    await callback.message.answer_photo(photo=payload["file"], caption=caption, parse_mode="HTML", reply_markup=kb)
                elif payload:
                    await callback.message.answer_document(document=payload["file"], caption=caption, parse_mode="HTML", reply_markup=kb)
                else:
                    await callback.message.answer(caption, parse_mode="HTML", reply_markup=kb)
        else:
            await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
        return

    if action == "img" and len(parts) >= 5:
        product_id = parts[2]
        color_idx = int(parts[3]) if str(parts[3]).isdigit() else 0
        img_idx = int(parts[4]) if str(parts[4]).isdigit() else 0
        product = await catalog_get_product(product_id)
        if not product:
            return
        state = _get_state("tg", str(callback.message.chat.id))
        back_data = f"m:cat:{state['last_category']}:{state.get('last_page', 1)}" if state.get("last_category") else "m:cat"
        info = await _tg_get_product_images(product, product_id, color_idx)
        colors = info["colors"]
        color_idx = info["color_idx"]
        color = info["color"]
        images: List[str] = info["images"]
        if not images:
            await callback.message.edit_text(tg_product_caption(product, color=color), parse_mode="HTML", reply_markup=_tg_product_kb(product_id, colors, color_idx, 0, 0, back_data))
            return
        img_idx = max(0, min(int(img_idx or 0), len(images) - 1))
        image_url = images[img_idx]
        kb = _tg_product_kb(product_id, colors, color_idx, img_idx, len(images), back_data)
        caption = tg_product_caption(product, color=color)
        try:
            payload = await _tg_download_as_input_file(image_url)
            if payload and payload.get("is_photo"):
                await callback.message.edit_media(
                    types.InputMediaPhoto(media=payload["file"], caption=caption, parse_mode="HTML"),
                    reply_markup=kb,
                )
            elif payload:
                await callback.message.answer_document(document=payload["file"], caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=kb)
        except Exception:
            payload = await _tg_download_as_input_file(image_url)
            if payload and payload.get("is_photo"):
                await callback.message.answer_photo(photo=payload["file"], caption=caption, parse_mode="HTML", reply_markup=kb)
            elif payload:
                await callback.message.answer_document(document=payload["file"], caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                await callback.message.answer(caption, parse_mode="HTML", reply_markup=kb)
        return

    if action == "nop":
        return

    if action == "ask" and len(parts) >= 3:
        product_id = parts[2]
        product = await catalog_get_product(product_id)
        if not product:
            await callback.message.answer("Товар не найден.")
            return
        state = _get_state("tg", str(callback.message.chat.id))
        state["mode"] = "ask_ai_product"
        state["product"] = {
            "id": product.get("id"),
            "base_id": product.get("base_id"),
            "name": product.get("name"),
            "description": product.get("description"),
            "colors": product.get("colors", []),
            "url": product.get("url"),
            "price": product.get("price"),
            "categories": product.get("categories", []),
        }
        await callback.message.answer("Напишите вопрос по этому товару — я отвечу с учётом описания и цветов.", reply_markup=tg_kb_main())
        return
    if action == "manager":
        async with async_session() as session:
            chat = await get_chat_by_uuid(session, str(callback.message.chat.id))
            if not chat:
                chat = await create_chat(session, str(callback.message.chat.id), name=callback.from_user.first_name, messager="telegram")
                await updates_manager.broadcast(json.dumps({
                    "type": "chat_created",
                    "chat": {
                        "id": chat.id,
                        "uuid": chat.uuid,
                        "name": chat.name,
                        "messager": chat.messager,
                        "waiting": chat.waiting,
                        "ai": chat.ai,
                        "tags": chat.tags,
                        "last_message_content": None,
                        "last_message_timestamp": None
                    }
                }))
            await request_manager(session, chat.id, str(callback.message.chat.id), callback.from_user.first_name or str(callback.message.chat.id), "telegram")
        await callback.message.answer(HANDOFF_MESSAGE, reply_markup=tg_kb_main())
        return

@dp.callback_query(lambda c: c.data.startswith("notifications_"))
async def handle_notification_toggle(callback: types.CallbackQuery):
    """Обработчик переключения уведомлений"""
    notification_manager = notifications.get_notification_manager()
    if not notification_manager:
        await callback.answer("Ошибка: менеджер уведомлений не инициализирован")
        return
    
    # Извлекаем username из callback_data
    parts = callback.data.split("_")
    if len(parts) >= 3:
        action = parts[1]  # on или off
        username = "_".join(parts[2:])  # username может содержать подчеркивания
        
        if username in notification_manager.admin_usernames:
            await notification_manager.toggle_notifications(username, callback.message.chat.id)
            await callback.answer()
        else:
            await callback.answer("Ошибка: пользователь не найден в списке админов")
    else:
        await callback.answer("Ошибка: неверный формат callback данных")

@dp.message(Command("notifications"))
async def cmd_notifications(message: Message):
    """Команда для вызова панели управления уведомлениями"""
    notification_manager = notifications.get_notification_manager()
    if not notification_manager:
        await message.answer("Ошибка: менеджер уведомлений не инициализирован")
        return
    
    user_username = message.from_user.username
    if not user_username or user_username not in notification_manager.admin_usernames:
        await message.answer("⛔ У вас нет доступа к панели администратора.")
        return
    
    # Сохраняем chat_id админа
    await notification_manager.save_admin_chat_id(user_username, message.chat.id)
    
    # Отправляем панель управления уведомлениями
    await message.answer(
        "🔔 Панель управления уведомлениями\n\n"
        "Здесь вы можете управлять уведомлениями о новых сообщениях.",
        reply_markup=notification_manager.get_notification_keyboard(user_username)
    )

PROMO_ALLOWED_USERNAMES = {"psihpinki", "pshdarkk"}
_promo_state: Dict[int, Dict[str, Any]] = {}

async def _catalog_post_json(path: str, body: Dict[str, Any]) -> Optional[Any]:
    base = (CATALOG_API_URL or "").rstrip("/")
    if not base:
        return None
    url = f"{base}{path}"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    token = CATALOG_AUTH_TOKEN
    if not token and CATALOG_AUTH_USERNAME and CATALOG_AUTH_PASSWORD:
        token = await _catalog_get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        async with current_session.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                return {"error": text[:300]}
            return await resp.json()
    except Exception as e:
        return {"error": str(e)}
    finally:
        if current_session != http_session:
            await current_session.close()


@dp.message(Command("promo"))
async def cmd_promo(message: Message):
    username = message.from_user.username
    if not username or username not in PROMO_ALLOWED_USERNAMES:
        await message.answer("У вас нет доступа к управлению промокодами.")
        return
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Процент скидки (%)", callback_data="promo_type:percentage")],
        [types.InlineKeyboardButton(text="Фиксированная скидка (руб.)", callback_data="promo_type:fixed")],
        [types.InlineKeyboardButton(text="Список промокодов", callback_data="promo_list")],
    ])
    await message.answer("Управление промокодами.\nВыберите тип нового промокода:", reply_markup=kb)


@dp.callback_query(lambda c: c.data and c.data.startswith("promo_type:"))
async def promo_type_callback(callback: types.CallbackQuery):
    username = callback.from_user.username
    if not username or username not in PROMO_ALLOWED_USERNAMES:
        await callback.answer("Нет доступа")
        return
    dtype = callback.data.split(":")[1]
    _promo_state[callback.from_user.id] = {"step": "code", "discount_type": dtype}
    await callback.message.answer(f"Тип: {'Процент скидки' if dtype == 'percentage' else 'Фиксированная скидка'}\n\nВведите код промокода (например SALE20):")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "promo_list")
async def promo_list_callback(callback: types.CallbackQuery):
    username = callback.from_user.username
    if not username or username not in PROMO_ALLOWED_USERNAMES:
        await callback.answer("Нет доступа")
        return
    data = await _catalog_get_json("/api/promocodes")
    if not data or isinstance(data, dict) and data.get("error"):
        await callback.message.answer("Не удалось загрузить промокоды.")
        await callback.answer()
        return
    if not data:
        await callback.message.answer("Промокодов пока нет.")
        await callback.answer()
        return
    lines = []
    for p in data[:20]:
        status = "ON" if p.get("is_active") else "OFF"
        dtype = "%" if p.get("discount_type") == "percentage" else "руб."
        val = p.get("discount_value", "?")
        used = p.get("used_count", 0)
        mx = p.get("max_uses") or "~"
        lines.append(f"[{status}] {p['code']} — {val}{dtype} | {used}/{mx}")
    text = "Промокоды:\n\n" + "\n".join(lines)
    await callback.message.answer(text)
    await callback.answer()


@dp.message(lambda m: m.from_user and m.from_user.id in _promo_state and m.text and not m.text.startswith("/"))
async def promo_step_handler(message: Message):
    uid = message.from_user.id
    state = _promo_state.get(uid)
    if not state:
        return
    username = message.from_user.username
    if not username or username not in PROMO_ALLOWED_USERNAMES:
        _promo_state.pop(uid, None)
        return

    step = state.get("step")
    text = message.text.strip()

    if step == "code":
        state["code"] = text.upper()
        state["step"] = "value"
        label = "процент (число от 1 до 99)" if state["discount_type"] == "percentage" else "сумму скидки в рублях"
        await message.answer(f"Код: {state['code']}\n\nВведите {label}:")

    elif step == "value":
        try:
            val = float(text)
            if val <= 0:
                raise ValueError
        except ValueError:
            await message.answer("Введите положительное число:")
            return
        state["discount_value"] = val
        state["step"] = "max_uses"
        await message.answer("Введите лимит использований (число) или отправьте 0 для безлимита:")

    elif step == "max_uses":
        try:
            mx = int(text)
        except ValueError:
            await message.answer("Введите целое число:")
            return
        state["max_uses"] = mx if mx > 0 else None
        state["step"] = "expires"
        await message.answer("Введите срок действия в формате ДД.ММ.ГГГГ или отправьте 0 для бессрочного:")

    elif step == "expires":
        expires_at = None
        if text != "0":
            try:
                dt = datetime.strptime(text, "%d.%m.%Y")
                expires_at = dt.strftime("%Y-%m-%dT23:59:59")
            except ValueError:
                await message.answer("Неверный формат. Используйте ДД.ММ.ГГГГ или отправьте 0:")
                return
        state["expires_at"] = expires_at
        state["step"] = "description"
        await message.answer("Введите описание промокода (или отправьте 0 чтобы пропустить):")

    elif step == "description":
        description = "" if text == "0" else text
        body = {
            "code": state["code"],
            "discount_type": state["discount_type"],
            "discount_value": state["discount_value"],
            "description": description,
            "max_uses": state["max_uses"],
            "expires_at": state["expires_at"],
        }
        result = await _catalog_post_json("/api/promocodes", body)
        _promo_state.pop(uid, None)
        if result and not result.get("error"):
            dtype_label = "%" if state["discount_type"] == "percentage" else " руб."
            desc_line = f"Описание: {description}\n" if description else ""
            await message.answer(
                f"Промокод создан!\n\n"
                f"Код: {state['code']}\n"
                f"Скидка: {state['discount_value']}{dtype_label}\n"
                f"Лимит: {state['max_uses'] or 'Безлимитный'}\n"
                f"Срок: {'Бессрочный' if not state['expires_at'] else state['expires_at'][:10]}\n"
                f"{desc_line}"
            )
        else:
            err = result.get("error", "Неизвестная ошибка") if result else "Нет ответа от API"
            await message.answer(f"Ошибка создания промокода:\n{err}")


@dp.message(F.text)
async def handle_message(message: Message):
    async with async_session() as session:
        chat = await get_chat_by_uuid(session, str(message.chat.id))
        if not chat:
            chat = await create_chat(session, str(message.chat.id), name=message.chat.first_name, messager="telegram")
            new_chat_message = {
                "type": "chat_created",
                "chat": {
                    "id": chat.id,
                    "uuid": chat.uuid,
                    "name": chat.name,
                    "messager": chat.messager,
                    "waiting": chat.waiting,
                    "ai": chat.ai,
                    "tags": chat.tags,
                    "last_message_content": None,
                    "last_message_timestamp": None
                }
            }
            await updates_manager.broadcast(json.dumps(new_chat_message))

        text_norm = _normalize(message.text)
        state = _get_state("tg", str(message.chat.id))
        allow_ai_during_waiting = bool(state.get("mode") == "ask_ai_product" and state.get("product"))
        suppress_ai = False

        if not suppress_ai and text_norm in {"меню", "/menu", "menu"}:
            _clear_state("tg", str(message.chat.id))  # очищаем state при смене режима
            await message.answer(_tg_main_text(), reply_markup=tg_kb_main(), parse_mode="HTML")
            return
        if not suppress_ai and text_norm in {"faq", "/faq"}:
            _clear_state("tg", str(message.chat.id))  # очищаем state при смене режима
            await message.answer(_tg_faq_text(1), reply_markup=tg_kb_faq_menu(1), parse_mode="HTML")
            return
        if not suppress_ai and text_norm in {"каталог", "товары", "товар"}:
            _clear_state("tg", str(message.chat.id))  # очищаем state при смене режима
            categories = await catalog_get_categories()
            if not categories:
                await message.answer("<b>Каталог</b>\n<blockquote>Пока недоступен</blockquote>", parse_mode="HTML", reply_markup=tg_kb_main())
                return
            rows: List[List[Dict[str, str]]] = []
            row: List[Dict[str, str]] = []
            for c in categories[:12]:
                cid = str(c.get("slug") or "")
                name = str(c.get("name") or "Категория")[:28]
                if not cid:
                    continue
                row.append({"text": name, "data": f"m:cat:{cid}:1"})
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            rows.append([{"text": "🏠 Меню", "data": "m:home"}])
            await message.answer("<b>Каталог</b>\n<blockquote>Выберите категорию</blockquote>", parse_mode="HTML", reply_markup=_tg_kb(rows))
            return

        if _ai_is_handoff_confirm(text_norm):
            await request_manager(session, chat.id, str(message.chat.id), message.chat.first_name or str(message.chat.id), "telegram")
            await message.answer(HANDOFF_MESSAGE, reply_markup=tg_kb_main())
            return

        force_manager = not suppress_ai and ("позови менеджера" in text_norm or text_norm == "менеджер")
        extra_context = None
        product_id = None
        base_id = None
        categories: List[str] = []
        force_ai = False
        logging.info(f"🔍 TG state for {message.chat.id}: mode={state.get('mode')}, has_product={bool(state.get('product'))}")
        if state.get("mode") == "ask_ai_product" and state.get("product"):
            p = state["product"]
            product_id = str(p.get("id") or p.get("base_id") or "")
            base_id = str(p.get("base_id") or p.get("id") or "")
            logging.info(f"📦 TG using product context: product_id={product_id}, base_id={base_id}, name={p.get('name')}")
            categories = p.get("categories") or []
            if not categories and base_id:
                categories = await catalog_get_product_categories(base_id)
            price_text = _format_price(p.get("price"))
            meta = p.get("meta") if isinstance(p.get("meta"), dict) else {}
            sections = p.get("sections") if isinstance(p.get("sections"), list) else []
            section_lines: List[str] = []
            for s in sections:
                if not isinstance(s, dict):
                    continue
                title = str(s.get("title") or "").strip()
                content = str(s.get("content") or "").strip()
                if not content and not title:
                    continue
                content = _ai_trim(_ai_strip_html(content), 280)
                if title:
                    section_lines.append(f"{title}: {content}")
                else:
                    section_lines.append(content)
                if len(section_lines) >= 3:
                    break
            ctx_lines = [
                f"Название: {p.get('name','')}",
                f"Описание: {p.get('description','')}",
            ]
            if p.get("composition"):
                ctx_lines.append(f"Состав: {p.get('composition','')}")
            if p.get("fit"):
                ctx_lines.append(f"Посадка: {p.get('fit','')}")
            if meta.get("care"):
                ctx_lines.append(f"Уход: {meta.get('care','')}")
            if meta.get("shipping"):
                ctx_lines.append(f"Доставка: {meta.get('shipping','')}")
            if meta.get("returns"):
                ctx_lines.append(f"Возврат: {meta.get('returns','')}")
            if section_lines:
                ctx_lines.append(f"Дополнительно: {'; '.join(section_lines)}")
            ctx_lines.extend([
                f"Цена: {price_text}",
                f"Цвета: {', '.join(p.get('colors', []))}",
                f"Категории: {', '.join(categories)}",
                f"Ссылка: {p.get('url','')}",
            ])
            extra_context = "Контекст товара:\n" + "\n".join(ctx_lines)
            # НЕ очищаем state — сохраняем контекст товара для продолжения диалога
            force_ai = True

        new_message = Message(
            chat_id=chat.id,
            message=message.text,
            message_type="question",
            ai=False,
            created_at=datetime.utcnow()
        )
        session.add(new_message)
        await session.commit()
        await session.refresh(new_message)

        message_for_frontend = {
            "type": "message",
            "chatId": str(new_message.chat_id),
            "content": new_message.message,
            "message_type": new_message.message_type,
            "ai": new_message.ai,
            "timestamp": new_message.created_at.isoformat(),
            "id": new_message.id
        }
        await messages_manager.broadcast(json.dumps(message_for_frontend))

        # Пересылаем в форум-группу
        await forum_send_message(chat, message.text)

        if force_manager:
            await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
            await update_chat_ai(db=session, chat_id=chat.id, ai=False)
            await updates_manager.broadcast(json.dumps({
                "type": "chat_update",
                "chat_id": chat.id,
                "waiting": True,
                "ai": False
            }))
            notification_manager = notifications.get_notification_manager()
            if notification_manager:
                await notification_manager.send_waiting_notification(
                    chat_id=message.chat.id,
                    chat_name=message.chat.first_name or str(message.chat.id),
                    messager="telegram"
                )
            await message.answer(HANDOFF_MESSAGE, reply_markup=tg_kb_main())
            return

        if suppress_ai:
            await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
            await updates_manager.broadcast(json.dumps({
                "type": "chat_update",
                "chat_id": chat.id,
                "waiting": True
            }))
            return
        
        # Проверяем, отключен ли AI для этого чата (кроме режима "спросить у ИИ" про товар)
        is_product_mode = bool(state.get("mode") == "ask_ai_product" and state.get("product"))
        if not is_product_mode and (not chat.ai or chat.waiting):
            logging.info(f"🔇 TG AI disabled for chat {chat.id}: ai={chat.ai}, waiting={chat.waiting}")
            if not chat.waiting:
                await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
                await updates_manager.broadcast(json.dumps({
                    "type": "chat_update",
                    "chat_id": chat.id,
                    "waiting": True
                }))
            return
        
        try:
            history = await get_chat_messages(session, chat.id, limit=6)
            history_text = _ai_build_history(history, max_items=6)
            is_product_q = bool(state.get("mode") == "ask_ai_product" and state.get("product"))
            ai_result = await _ai_answer_question(
                session,
                message.text,
                extra_context=extra_context,
                product_id=product_id,
                product_base_id=base_id,
                product_categories=categories or None,
                conversation_history=history_text,
                previous_user_message=_ai_get_previous_user_message(history, message.text),
                is_product_question=is_product_q,
                use_xai=str(message.chat.id) in _xai_test_chats,
            )
            
            # Если AI решил передать менеджеру - сразу передаём
            if ai_result.get("handoff"):
                await request_manager(session, chat.id, str(message.chat.id), message.chat.first_name or str(message.chat.id), "telegram")
                await message.answer(HANDOFF_MESSAGE, reply_markup=tg_kb_main())
                return

            # Если ответ пустой - тоже передаем менеджеру
            answer = str(ai_result.get("answer") or "").strip()
            answer = _normalize_price_text(answer)
            answer = _ai_cleanup_answer(answer)
            if not answer:
                await request_manager(session, chat.id, str(message.chat.id), message.chat.first_name or str(message.chat.id), "telegram")
                await message.answer(HANDOFF_MESSAGE, reply_markup=tg_kb_main())
                return

            await message.answer(answer)
            new_answer = crud.Message(
                chat_id=chat.id,
                message=answer,
                message_type="answer",
                ai=True,
                created_at=datetime.utcnow()
            )
            session.add(new_answer)
            await session.commit()
            await session.refresh(new_answer)
            message_for_frontend = {
                "type": "message",
                "chatId": chat.id,
                "content": answer,
                "message_type": "answer",
                "ai": True,
                "timestamp": new_answer.created_at.isoformat(),
                "id": new_answer.id
            }
            await messages_manager.broadcast(json.dumps(message_for_frontend))

            # Дублируем AI-ответ в форум-топик
            if FORUM_GROUP_ID and bot and chat.topic_id:
                try:
                    await bot.send_message(
                        chat_id=FORUM_GROUP_ID,
                        message_thread_id=chat.topic_id,
                        text=f"[AI]:\n{answer}"
                    )
                except Exception:
                    pass

            # AI ответил, но менеджер должен увидеть диалог как непрочитанный
            await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
            await updates_manager.broadcast(json.dumps({
                "type": "chat_update",
                "chat_id": chat.id,
                "waiting": True
            }))
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            await message.answer("Извините, произошла ошибка при обработке запроса")


@dp.message(F.photo)
async def handle_photos(message: types.Message):
    # Игнорируем фото из форум-группы (обрабатываются отдельным хендлером)
    if _is_forum_group(message):
        return

    # Берем фото с самым высоким разрешением
    photo = message.photo[-1]
    
    # Скачиваем фото
    file = await bot.get_file(photo.file_id)
    file_data = await bot.download_file(file.file_path)
    
    # Генерируем уникальное имя файла
    file_extension = os.path.splitext(file.file_path)[1]
    file_name = f"{message.from_user.id}-{photo.file_id}{file_extension}"
    
    # Асинхронно загружаем в Minio
    success = minio_client.put_object(
                bucket_name=BUCKET_NAME,
                object_name=file_name,
                data=file_data,
                length=photo.file_size,
                content_type="image/jpeg"
            )
    
    if success:
        async with async_session() as session:
            # Создаем сообщение в базе данных
            chat = await get_chat_by_uuid(session, str(message.chat.id))
            if not chat:
                chat = await create_chat(session, str(message.chat.id), name=message.chat.first_name, messager="telegram")
            
            # Формируем контент: URL картинки и подпись через разделитель |
            image_url = build_public_minio_url(file_name)
            message_content = f"{image_url}|{message.caption}" if message.caption else image_url

            new_message = Message(
                chat_id=chat.id,
                message=message_content,
                message_type="question",
                ai=False,
                created_at=datetime.utcnow(),
                is_image=True
            )
            session.add(new_message)
            await session.commit()
            await session.refresh(new_message)
            message_for_frontend = {
                "type": "message",
                "chatId": str(new_message.chat_id),
                "content": new_message.message,
                "message_type": new_message.message_type,
                "ai": new_message.ai,
                "timestamp": new_message.created_at.isoformat(),
                "id": new_message.id,
                "is_image": new_message.is_image
            }
            await messages_manager.broadcast(json.dumps(message_for_frontend))

            # Пересылаем фото в форум-группу
            try:
                file_data_for_forum = await bot.download_file(file.file_path)
                content_bytes = file_data_for_forum.read() if hasattr(file_data_for_forum, 'read') else file_data_for_forum
                photo_input = BufferedInputFile(content_bytes, filename=file_name)
                await forum_send_photo_bytes(chat, photo_input, caption=message.caption)
            except Exception as e:
                logging.error("Failed to forward TG photo to forum: %s", e)

            update_message = {
                "type": "chat_update",
                "chat_id": chat.id,
                "waiting": True
            }
            await updates_manager.broadcast(json.dumps(update_message))
            
            notification_manager = notifications.get_notification_manager()
            if notification_manager:
                await notification_manager.send_waiting_notification(
                    chat_id=message.chat.id,
                    chat_name=message.chat.first_name or str(message.chat.id),
                    messager="telegram"
                )
    else:
        await message.reply("Произошла ошибка при загрузке фото")



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)
