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
from crud import async_session, engine, Base, get_chats, get_chat, get_messages, create_chat, create_message, update_chat_waiting, update_chat_ai, get_stats, get_chats_with_last_messages, get_chat_messages, get_chat_by_uuid, add_chat_tag, remove_chat_tag, sync_vk
import requests
from pydantic import BaseModel, validator
from shared import get_bot
import json
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, insert
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
from aiogram.types import FSInputFile
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

FAQ_INLINE_RAW = """
Q: Delivery Time? (Когда ожидать доставку?)
A: **Срок зависит** от того, в наличии ли вещь или на предзаказе. Если в наличии — отправка на следующий день. Если предзаказ — сроки производства и отправки устанавливаются брендом. **Точные сроки** по предзаказу подскажет менеджер. Хотите, чтобы я связал вас с ним?

Q: Tell me the status of order XXXXX (Подскажи статус заказа XXXXX?)
A: В данный момент я не могу называть статусы заказов, но могу перевести вас на менеджера. Подключить вас?

Q: What is Pre-order? (Что такое предзаказ?)
A: Предзаказ — это резервирование вещи до ее производства. Вы заранее предоставляете средства на пошив и получаете товар одним из первых.

Q: How long is Pre-order? (Как долго ожидать вещи с предзаказа?)
A: Обычно от 2 до 4 недель, но срок может сдвигаться. Лучше уточните у менеджера — хотите, чтобы я вас с ним связал?

Q: Return Policy? (Как отменить/вернуть заказ?)
A: Возврат согласуется с менеджером. Товар должен быть надлежащего качества и возвратным. Возврат платный (по тарифу доставки). В посылке должно быть заявление (бланк у менеджера). **Отмена заказа** возможна только в первые 30 минут после оформления.

Q: Size Guide? (Где находится таблица размеров?)
A: Таблицы размещены на сайте — в описании товара или на изображениях. Если её нет — значит таблицы для этой вещи не существует. Можно уточнить у менеджера.

Q: Why is shipping delayed? (Почему отправка так затянулась?)
A: Скорее всего, вы заказали товар на предзаказе, либо заказ в статусе «на утверждении».

Q: Is it a Pre-order? (Как определить, на предзаказе ли вещь?)
A: Если перед названием товара на сайте стоит «+» — вещь в наличии. Если нет знака — это предзаказ. Можно уточнить у менеджера. Хотите, свяжу вас с менеджером?

Q: What if my order has both pre-order and in-stock items? (Когда будет отправка, если в заказе и то и другое?)
A: Заказ отправляется, когда все позиции готовы. Но можно разделить заказ — вас связать с менеджером?

Q: International Shipping? (Доставляете ли вы вещи за границы РФ?)
A: Да, доставляем. Для оформления вам нужно связаться с менеджером. Перевести вас на менеджера?

Q: Which carriers do you use? (Какими службами доставки отправляете?)
A: Почта России и СДЭК.

Q: How do I choose a size? (Как подобрать размер?)
A: Ориентируйтесь на таблицу размеров на странице товара. Если таблицы нет — уточните у менеджера, он подскажет по меркам.

Q: Which items are non-returnable? (Какие товары не подлежат возврату?)
A: Бельевые изделия (швейные и трикотажные) и чулочно-носочные изделия (согласно Пост. Правительства РФ №55).

Q: How should I care for PSIH items? (Как ухаживать за вещами PSIH?)
A: Ручная или деликатная стирка 15–30°С, вывернуть наизнанку, без отбеливателя. Кастом — стирать отдельно, места с росписью не тереть, сушить горизонтально, без прямого солнца. Гладить щадяще с изнанки; рисунок — только через ткань; без отпаривателя.

Q: What if my item is defective? (Что делать, если брак?)
A: Брак подтверждается экспертизой; при подтверждении возможен возврат/обмен. Продавец может согласовать возврат/обмен без экспертизы — по ситуации.

--- Brand Information & Details ---
🧠 **Общая информация о бренде ПСИХ**
• **Название:** ПСИХ (PSIH)
• **Официальный сайт:** https://psihclothes.com/
• **VK:** https://vk.com/psihclothes

🎭 **Концепция и философия бренда**
ПСИХ — это не просто одежда, это способ самовыражения, отражающий внутренние переживания и эмоции.

🛍️ **Покупка и доставка**
Оформление заказов: через сайт psihclothes.com. Доставка: по России и в другие страны.
--- End Brand Information & Details ---
""".strip()

CATALOG_API_URL = os.getenv("CATALOG_API_URL")
CATALOG_AUTH_TOKEN = os.getenv("CATALOG_AUTH_TOKEN")
CATALOG_AUTH_USERNAME = os.getenv("CATALOG_AUTH_USERNAME") or os.getenv("CATALOG_USERNAME") or os.getenv("CATALOG_USER")
CATALOG_AUTH_PASSWORD = os.getenv("CATALOG_AUTH_PASSWORD") or os.getenv("CATALOG_PASSWORD") or os.getenv("CATALOG_PASS")
CATALOG_TOKEN_TTL_SECONDS = int(os.getenv("CATALOG_TOKEN_TTL_SECONDS", "3300"))
CATALOG_CACHE_TTL_SECONDS = int(os.getenv("CATALOG_CACHE_TTL_SECONDS", "60"))
_catalog_cache: Dict[str, Any] = {"ts": 0.0, "categories": None, "products": {}, "product": {}, "color_images": {}}
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

def _tg_faq_text() -> str:
    ensure_faq_loaded()
    if not FAQ_ORDER:
        return "<b>FAQ</b>\n<blockquote>Пока пусто: раздел ещё не настроен</blockquote>"
    return "<b>FAQ</b>\n<blockquote>Выберите тему</blockquote>"

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
    for item_id in FAQ_ORDER[start:end]:
        title = FAQ_ITEMS.get(item_id, {}).get("title", item_id)
        ru = title.split("(")[-1].rstrip(")") if "(" in title and ")" in title else title
        label = ru[:28]
        row.append({"text": label, "data": f"m:faq:item:{item_id}:{page}"})
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

def _vk_faq_text() -> str:
    ensure_faq_loaded()
    if not FAQ_ORDER:
        return "FAQ\n\nПока пусто: раздел ещё не настроен"
    return "FAQ\n\nВыберите тему:"

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
        cid = str(c.get("slug") or "")
        name = str(c.get("name") or "Категория")[:38]
        if not cid:
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
    kb.add_button("👤 Менеджер", color=VkKeyboardColor.NEGATIVE, payload={"cmd": "manager"})
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
        return
    payload: Dict[str, Any] = {"peer_id": peer_id, "message": message, "random_id": 0}
    if keyboard:
        payload["keyboard"] = keyboard
    if attachment:
        payload["attachment"] = attachment
    await asyncio.to_thread(vk.messages.send, **payload)

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
        for k in ("url", "image_url", "src", "path", "link"):
            v = obj.get(k)
            if isinstance(v, str) and v:
                return _catalog_abs_url(v) if not v.startswith("http") else v
    return None

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
    name = str(raw.get("name") or raw.get("title") or raw.get("product_name") or "").strip() or str(pid)
    description = str(raw.get("description") or raw.get("desc") or "").strip()
    url = str(raw.get("url") or raw.get("link") or "").strip()
    price = raw.get("price") or raw.get("cost")

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
        "name": name,
        "description": description,
        "url": url,
        "price": price,
        "images": images,
        "colors": colors,
        "images_by_color": images_by_color,
    }

async def catalog_get_products(category_id: str, page: int = 1, limit: int = 8) -> Optional[List[Dict[str, Any]]]:
    key = f"{category_id}:{page}:{limit}"
    cached = _catalog_cache["products"].get(key)
    if cached and _catalog_is_fresh(cached["ts"]):
        return cached["data"]

    offset = max(0, (int(page or 1) - 1) * int(limit or 0))
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
    data: Any = None
    for params in params_variants:
        data = await _catalog_get_json("/api/products", params=params)
        if data is not None:
            break

    used_products_endpoint = data is not None
    if data is None:
        data = await _catalog_get_json(f"/api/categories/{category_id}")
    items: Any = None
    if isinstance(data, dict):
        items = data.get("products") or data.get("items") or data.get("data") or data.get("results")
    if items is None:
        items = data
    if not isinstance(items, list):
        return None

    all_products: List[Dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        pid = raw.get("id") or raw.get("product_id") or raw.get("base_product_id") or raw.get("uuid")
        if pid is None:
            continue
        name = str(raw.get("name") or raw.get("title") or raw.get("product_name") or "").strip() or str(pid)
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
        all_products.append({
            "id": str(pid),
            "name": name,
            "description": description,
            "url": url,
            "price": price,
            "images": images,
            "colors": [],
            "color_entries": [],
            "images_by_color": {},
        })

    if used_products_endpoint:
        normalized = all_products[:limit]
    else:
        start = max(0, (page - 1) * limit)
        normalized = all_products[start:start + limit]
    _catalog_cache["products"][key] = {"ts": datetime.utcnow().timestamp(), "data": normalized}
    return normalized

async def catalog_get_product(product_id: str) -> Optional[Dict[str, Any]]:
    cached = _catalog_cache["product"].get(product_id)
    if cached and _catalog_is_fresh(cached["ts"]):
        return cached["data"]
    base = await _catalog_get_json(f"/api/products/{product_id}")
    if base is None:
        base = await _catalog_get_json(f"/api/products/slug/{product_id}")
    if not isinstance(base, dict):
        return None
    pid = base.get("id") or base.get("product_id") or base.get("uuid") or product_id
    name = str(base.get("name") or base.get("title") or base.get("product_name") or "").strip() or str(pid)
    description = str(base.get("description") or base.get("desc") or "").strip()
    url = str(base.get("url") or base.get("link") or "").strip()
    price = base.get("price") or base.get("cost")

    images: List[str] = []
    for k in ("primary_image", "image", "cover"):
        u = _extract_image_url(base.get(k))
        if u:
            images = [u]
            break
    if not images and isinstance(base.get("images"), list):
        imgs = [_extract_image_url(x) for x in base.get("images")]
        images = [x for x in imgs if x]

    colors_data = await _catalog_get_json(f"/api/products/{product_id}/colors")
    color_entries: List[Dict[str, Any]] = []
    if isinstance(colors_data, list):
        for c in colors_data:
            if not isinstance(c, dict):
                continue
            cid = c.get("id") or c.get("product_color_id") or c.get("color_id")
            cname = str(c.get("name") or c.get("title") or c.get("color") or c.get("value") or c.get("color_name") or "").strip()
            if cid is None or not cname:
                continue
            color_entries.append({"id": str(cid), "name": cname})

    product: Dict[str, Any] = {
        "id": str(pid),
        "name": name,
        "description": description,
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

def tg_product_caption(p: Dict[str, Any], color: Optional[str] = None) -> str:
    name = _tg_to_html(str(p.get("name") or "Товар"))
    desc = _tg_to_html(str(p.get("description") or ""))
    url = str(p.get("url") or "")
    price = p.get("price")
    parts = [f"<b>{name}</b>"]
    if price is not None and str(price).strip():
        parts.append(f"<b>Цена:</b> {html.escape(str(price))}")
    if color:
        parts.append(f"<b>Цвет:</b> {html.escape(color)}")
    if desc:
        parts.append(f"\n<blockquote>{desc}</blockquote>")
    if url:
        parts.append(f'\n<a href="{html.escape(url)}">Открыть на сайте</a>')
    return "\n".join(parts).strip()


# VK config (делаем опциональным: отсутствие VK_* не должно валить весь API)
VK_TOKEN = os.getenv("VK_TOKEN")  # токен сообщества
VK_GROUP_ID_RAW = os.getenv("VK_GROUP_ID")  # ID сообщества (строкой)
VK_GROUP_ID: Optional[int] = None
if VK_GROUP_ID_RAW:
    try:
        VK_GROUP_ID = int(VK_GROUP_ID_RAW)
    except ValueError:
        logging.error("Invalid VK_GROUP_ID=%r (expected integer). VK integration will be disabled.", VK_GROUP_ID_RAW)

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
                logging.info(f"🟢 VK event received: {event.type}")
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
    if event.type != VkBotEventType.MESSAGE_NEW:
        return

    msg = event.object['message']
    peer_id = msg['peer_id']
    user_id = msg['from_id']
    text = msg.get('text', "")
    attachments = msg.get("attachments", [])

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
            if cmd == "home":
                await vk_send_message(peer_id, _vk_main_text(), keyboard=vk_kb_main())
                return
            if cmd == "faq":
                await vk_send_message(peer_id, _vk_faq_text(), keyboard=vk_kb_faq_menu(1))
                return
            if cmd == "faq_page":
                page = int(payload_data.get("page") or 1)
                await vk_send_message(peer_id, _vk_faq_text(), keyboard=vk_kb_faq_menu(page))
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
                items = await catalog_get_products(category_id, page=page, limit=limit)
                if not items:
                    reason = str(_catalog_cache.get("last_error") or "").strip()
                    text_out = "Каталог пустой или API недоступен."
                    if reason:
                        text_out += f"\nПричина: {reason}"
                    await vk_send_message(peer_id, text_out, keyboard=vk_kb_main())
                    return
                await vk_send_message(peer_id, f"Каталог\n\nСтраница {page}", keyboard=vk_kb_products(category_id, page, items, has_next=len(items) >= limit))
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
                    "name": product.get("name"),
                    "description": product.get("description"),
                    "colors": product.get("colors", []),
                    "url": product.get("url"),
                }
                await vk_send_message(peer_id, "Напишите вопрос по этому товару — я отвечу с учётом описания и цветов.", keyboard=vk_kb_main())
                return
            if cmd == "manager":
                await request_manager(session, chat.id, str(peer_id), user_name, "vk")
                await vk_send_message(peer_id, "Я позвал менеджера. Напишите, что нужно — он подключится.", keyboard=vk_kb_main())
                return

        text_norm = _normalize(text)
        if text_norm in {"меню", "menu", "/menu", "старт", "start"}:
            await vk_send_message(peer_id, _vk_main_text(), keyboard=vk_kb_main())
            return
        if text_norm in {"faq", "/faq"}:
            await vk_send_message(peer_id, _vk_faq_text(), keyboard=vk_kb_faq_menu(1))
            return
        if text_norm in {"каталог", "товары", "товар"}:
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
        if "позови менеджера" in text_norm or text_norm == "менеджер":
            await request_manager(session, chat.id, str(peer_id), user_name, "vk")
            await vk_send_message(peer_id, "Я позвал менеджера. Напишите, что нужно — он подключится.", keyboard=vk_kb_main())
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

            # Если AI выключен — обновляем waiting и выходим
            if not chat.ai:
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
            else:
                state = _get_state("vk", str(peer_id))
                ai_question = text
                if state.get("mode") == "ask_ai_product" and state.get("product"):
                    p = state["product"]
                    context = f"Контекст товара:\nНазвание: {p.get('name','')}\nОписание: {p.get('description','')}\nЦвета: {', '.join(p.get('colors', []))}\nСсылка: {p.get('url','')}"
                    ai_question = f"{context}\n\nВопрос пользователя: {text}"
                    _clear_state("vk", str(peer_id))
                current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
                try:
                    async with current_session.post(
                        API_URL,
                        json={"question": ai_question, "chat_id": chat.id}
                    ) as resp:
                        data = await resp.json()
                    
                    if data.get("answer"):
                        answer = data["answer"]
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

                    if data.get("manager") == "true":
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
                                chat_id=peer_id,
                                chat_name=user_name,
                                messager="vk"
                            )
                except Exception as e:
                    logging.error(f"AI request error: {e}")
                finally:
                    if current_session != http_session:
                        await current_session.close()

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

# API endpoint for sending questions
API_URL = os.getenv("API_URL", "http://pavel")
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

    return {"message": db_img, "delivered": delivered, "delivery_error": delivery_error}

@app.get("/api/ai/context")
async def get_ai_context(_: bool = Depends(auth.require_auth)):
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        async with current_session.get(API_URL) as response:
            data = await response.json()
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке на API {e}")
    finally:
        if current_session != http_session: await current_session.close()

class PutAIContext(BaseModel):
    system_message: str
    faqs: str

@app.put("/api/ai/context")
async def put_ai_context(new_ai_context: PutAIContext, _: bool = Depends(auth.require_auth)):
    current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
    try:
        async with current_session.post(
            API_URL,
            json={
                "system_message": new_ai_context.system_message,
                "faqs": new_ai_context.faqs
            }
        ) as response:
            data = await response.json()
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при отправке на API {e}")
    finally:
        if current_session != http_session: await current_session.close()

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
    await message.answer(_tg_faq_text(), reply_markup=tg_kb_faq_menu(1), parse_mode="HTML")

@dp.callback_query(F.data.startswith("m:"))
async def handle_menu_callback(callback: types.CallbackQuery):
    parts = (callback.data or "").split(":")
    if len(parts) < 2:
        await callback.answer()
        return
    action = parts[1]
    await callback.answer()

    if action == "home":
        await callback.message.edit_text(_tg_main_text(), reply_markup=tg_kb_main(), parse_mode="HTML")
        return
    if action == "faq":
        if len(parts) == 2:
            await callback.message.edit_text(_tg_faq_text(), reply_markup=tg_kb_faq_menu(1), parse_mode="HTML")
            return
        if len(parts) >= 4 and parts[2] == "page" and str(parts[3]).isdigit():
            page = int(parts[3])
            await callback.message.edit_text(_tg_faq_text(), reply_markup=tg_kb_faq_menu(page), parse_mode="HTML")
            return
        if len(parts) >= 5 and parts[2] == "item":
            item_id = parts[3]
            page = int(parts[4]) if str(parts[4]).isdigit() else 1
            await callback.message.edit_text(_tg_faq_item_text(item_id), reply_markup=tg_kb_faq_item(item_id, page), parse_mode="HTML")
            return
        item_id = parts[2]
        await callback.message.edit_text(_tg_faq_item_text(item_id), reply_markup=tg_kb_faq_item(item_id, 1), parse_mode="HTML")
        return
    if action == "cat":
        if len(parts) == 2:
            categories = await catalog_get_categories()
            if not categories:
                reason = str(_catalog_cache.get("last_error") or "").strip()
                details = f"\n<blockquote>{html.escape(reason)}</blockquote>" if reason else "\n<blockquote>Пока недоступен</blockquote>"
                await callback.message.edit_text(f"<b>Каталог</b>{details}", reply_markup=_tg_kb([[{"text": "⬅️ Назад", "data": "m:home"}]]), parse_mode="HTML")
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
            await callback.message.edit_text("<b>Каталог</b>\n<blockquote>Выберите категорию</blockquote>", reply_markup=_tg_kb(rows), parse_mode="HTML")
            return

        category_id = parts[2]
        page = 1
        if len(parts) >= 4 and str(parts[3]).isdigit():
            page = int(parts[3])
        limit = 8
        items = await catalog_get_products(category_id, page=page, limit=limit)
        if not items:
            reason = str(_catalog_cache.get("last_error") or "").strip()
            details = f"\n<blockquote>{html.escape(reason)}</blockquote>" if reason else "\n<blockquote>Пусто или API недоступен</blockquote>"
            await callback.message.edit_text(f"<b>Каталог</b>{details}", reply_markup=_tg_kb([[{"text": "⬅️ Назад", "data": "m:cat"}], [{"text": "🏠 Меню", "data": "m:home"}]]), parse_mode="HTML")
            return

        state = _get_state("tg", str(callback.message.chat.id))
        state["last_category"] = category_id
        state["last_page"] = page

        rows: List[List[Dict[str, str]]] = []
        row: List[Dict[str, str]] = []
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
        if len(items) >= limit:
            nav_row.append({"text": "➡️", "data": f"m:cat:{category_id}:{page+1}"})
        if nav_row:
            rows.append(nav_row)
        rows.append([{"text": "⬅️ Категории", "data": "m:cat"}])
        rows.append([{"text": "🏠 Меню", "data": "m:home"}])
        await callback.message.edit_text(f"<b>Каталог</b>\n<blockquote>Страница {page}</blockquote>", reply_markup=_tg_kb(rows), parse_mode="HTML")
        return

    if action == "prod" and len(parts) >= 3:
        product_id = parts[2]
        product = await catalog_get_product(product_id)
        if not product:
            await callback.message.answer("Товар не найден.")
            return
        state = _get_state("tg", str(callback.message.chat.id))
        color_entries: List[Dict[str, Any]] = product.get("color_entries", [])
        colors: List[str] = product.get("colors", [])
        selected_entry = color_entries[0] if color_entries else None
        selected_color = selected_entry["name"] if selected_entry else (colors[0] if colors else None)
        image_url = None
        if selected_entry:
            imgs = await catalog_get_color_images(selected_entry["id"])
            image_url = imgs[0] if imgs else None
            if imgs:
                product["images_by_color"][selected_entry["name"]] = imgs
        if not image_url and product.get("images"):
            image_url = product["images"][0]

        kb_rows: List[List[Dict[str, str]]] = []
        if colors:
            color_row: List[Dict[str, str]] = []
            for idx, c in enumerate(colors[:6]):
                color_row.append({"text": c[:16], "data": f"m:color:{product_id}:{idx}"})
                if len(color_row) == 2:
                    kb_rows.append(color_row)
                    color_row = []
            if color_row:
                kb_rows.append(color_row)
        kb_rows.append([{"text": "🧠 Спросить ИИ", "data": f"m:ask:{product_id}"}])
        kb_rows.append([{"text": "👤 Менеджер", "data": "m:manager"}])
        if state.get("last_category"):
            kb_rows.append([{"text": "⬅️ Назад", "data": f"m:cat:{state['last_category']}:{state.get('last_page', 1)}"}])
        else:
            kb_rows.append([{"text": "⬅️ Назад", "data": "m:cat"}])

        caption = tg_product_caption(product, color=selected_color)
        if image_url:
            await callback.message.answer_photo(photo=image_url, caption=caption, parse_mode="HTML", reply_markup=_tg_kb(kb_rows))
        else:
            await callback.message.answer(caption, parse_mode="HTML", reply_markup=_tg_kb(kb_rows))
        return

    if action == "color" and len(parts) >= 4:
        product_id = parts[2]
        idx = int(parts[3]) if str(parts[3]).isdigit() else 0
        product = await catalog_get_product(product_id)
        if not product:
            return
        color_entries: List[Dict[str, Any]] = product.get("color_entries", [])
        colors: List[str] = product.get("colors", [])
        if not colors:
            return
        color = colors[idx] if 0 <= idx < len(colors) else colors[0]
        image_url = None
        if 0 <= idx < len(color_entries):
            imgs = await catalog_get_color_images(color_entries[idx]["id"])
            if imgs:
                product["images_by_color"][color] = imgs
        if product.get("images_by_color", {}).get(color):
            image_url = product["images_by_color"][color][0]
        if not image_url and product.get("images"):
            image_url = product["images"][0]

        kb_rows: List[List[Dict[str, str]]] = []
        color_row: List[Dict[str, str]] = []
        for j, c in enumerate(colors[:6]):
            label = ("✅ " if c == color else "") + c
            color_row.append({"text": label[:18], "data": f"m:color:{product_id}:{j}"})
            if len(color_row) == 2:
                kb_rows.append(color_row)
                color_row = []
        if color_row:
            kb_rows.append(color_row)
        kb_rows.append([{"text": "🧠 Спросить ИИ", "data": f"m:ask:{product_id}"}])
        kb_rows.append([{"text": "👤 Менеджер", "data": "m:manager"}])
        kb_rows.append([{"text": "🏠 Меню", "data": "m:home"}])

        caption = tg_product_caption(product, color=color)
        if image_url:
            try:
                await callback.message.edit_media(
                    types.InputMediaPhoto(media=image_url, caption=caption, parse_mode="HTML"),
                    reply_markup=_tg_kb(kb_rows),
                )
            except Exception:
                await callback.message.answer_photo(photo=image_url, caption=caption, parse_mode="HTML", reply_markup=_tg_kb(kb_rows))
        else:
            await callback.message.edit_text(caption, parse_mode="HTML", reply_markup=_tg_kb(kb_rows))
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
            "name": product.get("name"),
            "description": product.get("description"),
            "colors": product.get("colors", []),
            "url": product.get("url"),
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
        await callback.message.answer("Я позвал менеджера. Напишите, что нужно — он подключится.", reply_markup=tg_kb_main())
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
        if text_norm in {"меню", "/menu", "menu"}:
            await message.answer(_tg_main_text(), reply_markup=tg_kb_main(), parse_mode="HTML")
            return
        if text_norm in {"faq", "/faq"}:
            await message.answer(_tg_faq_text(), reply_markup=tg_kb_faq_menu(1), parse_mode="HTML")
            return
        if text_norm in {"каталог", "товары", "товар"}:
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

        force_manager = "позови менеджера" in text_norm or text_norm == "менеджер"
        state = _get_state("tg", str(message.chat.id))
        ai_question = message.text
        if state.get("mode") == "ask_ai_product" and state.get("product"):
            p = state["product"]
            context = f"Контекст товара:\nНазвание: {p.get('name','')}\nОписание: {p.get('description','')}\nЦвета: {', '.join(p.get('colors', []))}\nСсылка: {p.get('url','')}"
            ai_question = f"{context}\n\nВопрос пользователя: {message.text}"
            _clear_state("tg", str(message.chat.id))

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
            await message.answer("Я позвал менеджера. Напишите, что нужно — он подключится.", reply_markup=tg_kb_main())
            return

        if not chat.ai:
            await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
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
            return
        
        current_session = http_session if http_session and not http_session.closed else aiohttp.ClientSession()
        try:
            async with current_session.post(
                API_URL,
                json={
                    "question": ai_question,
                    "chat_id": chat.id
                }
            ) as response:
                if response.status != 200:
                    await message.answer("Извините, произошла ошибка при обработке запроса")
                data = await response.json()
                if not data:
                    await message.answer("Извините, произошла ошибка при обработке запроса")
                if "answer" in data:
                    answer = data["answer"]
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
                if "manager" in data and data["manager"] == "true":
                    await update_chat_waiting(db=session, chat_id=chat.id, waiting=True)
                    await update_chat_ai(db=session, chat_id=chat.id, ai=False)
                    update_message = {
                        "type": "chat_update",
                        "chat_id": chat.id,
                        "waiting": True,
                        "ai": False
                    }
                    await updates_manager.broadcast(json.dumps(update_message))
                    
                    notification_manager = notifications.get_notification_manager()
                    if notification_manager:
                        await notification_manager.send_waiting_notification(
                            chat_id=message.chat.id,
                            chat_name=message.chat.first_name or str(message.chat.id),
                            messager="telegram"
                        )
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            await message.answer("Извините, произошла ошибка при обработке запроса")
        finally:
            if current_session != http_session:
                await current_session.close()


@dp.message(F.photo)
async def handle_photos(message: types.Message):
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
            new_message = Message(
                chat_id=chat.id,
                message=build_public_minio_url(file_name),
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
