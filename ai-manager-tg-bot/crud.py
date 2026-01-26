import os
import re
import asyncio
import io
import aiohttp
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, selectinload
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func, select, desc, ARRAY, delete, JSON, Float
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict, Any
from datetime import datetime
import vk_api
from minio import Minio

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# MinIO configuration
APP_HOST = os.getenv("APP_HOST", "localhost")
MINIO_LOGIN = os.getenv("MINIO_LOGIN")
MINIO_PWD = os.getenv("MINIO_PWD")
BUCKET_NAME = "psih-photo"

# SQLAlchemy engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

# Models
class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, nullable=False)
    ai = Column(Boolean, default=False)
    waiting = Column(Boolean, default=False)
    tags = Column(ARRAY(String), default=[])
    name = Column(String(30), default="Не известно")
    messager = Column(String(16), nullable=False, default="telegram")
    # Поля для аналитики и назначения менеджера
    assigned_manager_id = Column(Integer, nullable=True)
    assigned_manager_name = Column(String(100), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    dialog_status = Column(String(20), default="new")  # new, assigned, closed
    messages = relationship("Message", back_populates="chat")
    analytics = relationship("DialogAnalytics", back_populates="chat", uselist=False)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False, index=True)
    message = Column(String, nullable=False)
    message_type = Column(String, nullable=False)
    ai = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.timezone('UTC', func.now()))
    is_image = Column(Boolean, default=False)
    chat = relationship("Chat", back_populates="messages")

class AiSettings(Base):
    __tablename__ = "ai_settings"
    id = Column(Integer, primary_key=True, index=True)
    system_message = Column(String, default="")
    faqs = Column(String, default="")
    rules = Column(String, default="")
    tone = Column(String, default="")
    handoff_phrases = Column(String, default="")
    min_score = Column(Float, default=0.2)
    site_pages = Column(String, default="")
    auto_refresh_minutes = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.timezone('UTC', func.now()), onupdate=func.timezone('UTC', func.now()))

class AiKnowledge(Base):
    __tablename__ = "ai_knowledge"
    id = Column(Integer, primary_key=True, index=True)
    data = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.timezone('UTC', func.now()), onupdate=func.timezone('UTC', func.now()))


class DialogAnalytics(Base):
    """Модель для хранения AI-аналитики диалогов"""
    __tablename__ = "dialog_analytics"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False, unique=True, index=True)
    
    # Основная информация
    manager_id = Column(Integer, nullable=True)
    manager_name = Column(String(100), nullable=True)
    channel = Column(String(20), nullable=True)  # telegram, vk, whatsapp
    
    # Результаты AI-анализа
    summary = Column(String, nullable=True)  # Краткое резюме диалога
    customer_problem = Column(String, nullable=True)  # Проблема клиента
    customer_intent = Column(String, nullable=True)  # Намерение клиента (покупка, возврат, вопрос)
    refund_reason = Column(String, nullable=True)  # Причина возврата если есть
    manager_quality_score = Column(Integer, nullable=True)  # Оценка качества работы менеджера 1-10
    manager_quality_notes = Column(String, nullable=True)  # Комментарии к оценке
    customer_sentiment = Column(String, nullable=True)  # Настроение клиента (positive, neutral, negative)
    resolution_status = Column(String, nullable=True)  # Статус решения (resolved, pending, escalated)
    key_topics = Column(ARRAY(String), default=[])  # Ключевые темы диалога
    recommendations = Column(String, nullable=True)  # Рекомендации для бизнеса
    
    # Метаданные
    messages_count = Column(Integer, default=0)
    dialog_duration_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.timezone('UTC', func.now()))
    raw_ai_response = Column(JSON, nullable=True)  # Полный ответ AI для отладки
    
    chat = relationship("Chat", back_populates="analytics")


# CRUD operations
async def get_chats(db: AsyncSession):
    result = await db.execute(select(Chat).order_by(Chat.id.desc()))
    return result.scalars().all()

async def get_chat(db: AsyncSession, chat_id: int):
    result = await db.execute(select(Chat).filter(Chat.id == chat_id))
    return result.scalar_one_or_none()

async def get_chat_by_uuid(db: AsyncSession, uuid: str):
    if not uuid or not uuid.strip() or not uuid.replace('-', '').isalnum():
        return None
    result = await db.execute(select(Chat).filter(Chat.uuid == uuid))
    return result.scalar_one_or_none()

async def get_messages(db: AsyncSession, chat_id: int):
    result = await db.execute(
        select(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()

async def create_chat(db: AsyncSession, uuid: str, ai: bool = True, name: str = "Не известно", tags: List[str] = None, messager: str = "telegram"):
    new_chat = Chat(
        uuid=uuid,
        ai=ai,
        name=name,
        tags=tags or [],
        messager=messager
    )
    db.add(new_chat)
    try:
        await db.commit()
        await db.refresh(new_chat)
        return new_chat
    except SQLAlchemyError:
        await db.rollback()
        raise

async def create_message(db: AsyncSession, chat_id: int, message: str, message_type: str, ai: bool = False):
    new_message = Message(chat_id=chat_id, message=message, message_type=message_type, ai=ai, created_at=datetime.utcnow())
    db.add(new_message)
    try:
        await db.commit()
        await db.refresh(new_message)
        return new_message
    except SQLAlchemyError:
        await db.rollback()
        raise

async def update_chat_waiting(db: AsyncSession, chat_id: int, waiting: bool):
    chat = await get_chat(db, chat_id)
    if chat:
        chat.waiting = waiting
        await db.commit()
        await db.refresh(chat)
    return chat

async def update_chat_ai(db: AsyncSession, chat_id: int, ai: bool):
    chat = await get_chat(db, chat_id)
    if chat:
        chat.ai = ai
        await db.commit()
        await db.refresh(chat)
    return chat

async def get_ai_settings(db: AsyncSession) -> Optional[AiSettings]:
    result = await db.execute(select(AiSettings).limit(1))
    return result.scalar_one_or_none()

async def upsert_ai_settings(db: AsyncSession, payload: Dict[str, Any]) -> AiSettings:
    settings = await get_ai_settings(db)
    if not settings:
        settings = AiSettings(**payload)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        return settings

    for key, value in payload.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    await db.commit()
    await db.refresh(settings)
    return settings

async def get_ai_knowledge(db: AsyncSession) -> Optional[AiKnowledge]:
    result = await db.execute(select(AiKnowledge).limit(1))
    return result.scalar_one_or_none()

async def save_ai_knowledge(db: AsyncSession, data: Any) -> AiKnowledge:
    knowledge = await get_ai_knowledge(db)
    if not knowledge:
        knowledge = AiKnowledge(data=data)
        db.add(knowledge)
        await db.commit()
        await db.refresh(knowledge)
        return knowledge

    knowledge.data = data
    await db.commit()
    await db.refresh(knowledge)
    return knowledge

async def get_stats(db: AsyncSession):
    total = await db.scalar(select(func.count(Chat.id)))
    pending = await db.scalar(select(func.count(Chat.id)).filter(Chat.waiting == True))
    ai_count = await db.scalar(select(func.count(Chat.id)).filter(Chat.ai == True))
    return {"total": total, "pending": pending, "ai": ai_count}

async def get_chats_with_last_messages(db: AsyncSession, limit: int = 10000) -> List[Dict[str, Any]]:
    # Подзапрос: последняя запись Message.id для каждого чата
    last_msg_ids = (
        select(
            Message.chat_id.label("chat_id"),
            func.max(Message.id).label("last_id"),
        )
        .group_by(Message.chat_id)
        .subquery()
    )

    # Важно: сначала джойним по chat_id, потом подтягиваем конкретное последнее сообщение
    query = (
        select(Chat, Message)
        .outerjoin(last_msg_ids, last_msg_ids.c.chat_id == Chat.id)
        .outerjoin(Message, Message.id == last_msg_ids.c.last_id)
        .order_by(desc(Chat.id))
    )
    
    if limit:
        query = query.limit(limit)
        
    result = await db.execute(query)
    rows = result.all()
    
    chats_with_messages = []
    for chat, last_message in rows:
        chat_dict = {
            "id": chat.id,
            "uuid": chat.uuid,
            "ai": chat.ai,
            "waiting": chat.waiting,
            "name": chat.name,
            "tags": chat.tags,
            "messager": chat.messager,
            "assigned_manager_id": chat.assigned_manager_id,
            "assigned_manager_name": chat.assigned_manager_name,
            "assigned_at": chat.assigned_at.isoformat() if chat.assigned_at else None,
            "dialog_status": chat.dialog_status,
            "last_message": None
        }
        
        if last_message:
            chat_dict["last_message"] = {
                "id": last_message.id,
                "content": last_message.message,
                "message_type": last_message.message_type,
                "ai": last_message.ai,
                "timestamp": last_message.created_at.isoformat() if last_message.created_at else None
            }
        
        chats_with_messages.append(chat_dict)
    
    return chats_with_messages

async def get_chat_messages(db: AsyncSession, chat_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    query = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(desc(Message.id)) 
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    messages.reverse()
    
    return [
        {
            "id": msg.id,
            "content": msg.message,
            "message_type": msg.message_type,
            "ai": msg.ai,
            "timestamp": msg.created_at.isoformat() if msg.created_at else None,
            "chatId": str(chat_id),
            "is_image": msg.is_image
        }
        for msg in messages
    ]

async def add_chat_tag(db: AsyncSession, chat_id: int, tag: str) -> dict:
    chat = await get_chat(db, chat_id)
    if not chat:
        return {"message": "error"}
    
    try:
        if chat.tags is None:
            chat.tags = []
        
        if tag not in chat.tags:
            chat.tags = chat.tags + [tag]
        
        await db.commit()
        await db.refresh(chat)
        return {"success": True, "tags": chat.tags}
    except Exception as e:
        await db.rollback()
        return {"message": "error"}

async def remove_chat_tag(db: AsyncSession, chat_id: int, tag: str) -> dict:
    chat = await get_chat(db, chat_id)
    if not chat:
        return {"message": "error"}
    
    try:
        if chat.tags is None:
            chat.tags = []
        
        if tag in chat.tags:
            chat.tags = [t for t in chat.tags if t != tag]
        
        await db.commit()
        await db.refresh(chat)
        return {"success": True, "tags": chat.tags}
    except Exception as e:
        await db.rollback()
        return {"message": "error"}

async def sync_vk(db: AsyncSession, chat_id: int) -> dict:
    """
    Синхронизирует VK чат с базой данных.
    Проверяет количество сообщений в VK и БД, и если они не совпадают,
    удаляет все сообщения из БД и добавляет все из VK.
    """
    # Получаем чат из БД
    chat = await get_chat(db, chat_id)
    if not chat:
        return {"success": False, "message": "Chat not found"}
    
    # Проверяем, что это VK чат
    if chat.messager != "vk":
        return {"success": False, "message": "Chat is not a VK chat"}
    
    try:
        # Инициализируем VK API
        VK_TOKEN = os.getenv("VK_TOKEN")
        VK_GROUP_ID = int(re.sub(r"\D", "", os.getenv("VK_GROUP_ID", "0")))
        
        if not VK_TOKEN:
            return {"success": False, "message": "VK_TOKEN not found"}
        
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        
        # Создаем клиент MinIO (если есть настройки)
        minio_client = None
        if MINIO_LOGIN and MINIO_PWD:
            try:
                minio_client = Minio(
                    endpoint="minio:9000",
                    access_key=MINIO_LOGIN,
                    secret_key=MINIO_PWD,
                    secure=False
                )
            except Exception as e:
                # Если не удалось создать клиент, продолжаем без MinIO
                minio_client = None
        
        # Получаем peer_id из uuid чата
        peer_id = int(chat.uuid)
        
        # Получаем все сообщения из VK
        # Используем asyncio.to_thread для синхронного вызова VK API
        all_vk_messages = []
        offset = 0
        count = 200  # Максимум за один запрос
        
        while True:
            history = await asyncio.to_thread(
                vk.messages.getHistory,
                peer_id=peer_id,
                count=count,
                offset=offset
            )
            
            items = history.get("items", [])
            if not items:
                break
            
            all_vk_messages.extend(items)
            
            # Если получили меньше count, значит это последняя страница
            if len(items) < count:
                break
            
            offset += count
        
        # Фильтруем только текстовые сообщения и фото
        vk_messages_filtered = []
        for msg in all_vk_messages:
            # Проверяем наличие текста или фото
            has_text = bool(msg.get("text"))
            has_photo = bool(msg.get("attachments") and any(
                att.get("type") == "photo" for att in msg.get("attachments", [])
            ))
            
            if has_text or has_photo:
                vk_messages_filtered.append(msg)
        
        vk_count = len(vk_messages_filtered)
        
        # Получаем количество сообщений в БД
        db_count = await db.scalar(
            select(func.count(Message.id)).where(Message.chat_id == chat_id)
        )
        
        # Если количество совпадает, ничего не делаем
        if vk_count == db_count:
            return {
                "success": True,
                "message": "Messages are already synchronized",
                "vk_count": vk_count,
                "db_count": db_count
            }
        
        # Удаляем все сообщения из БД для этого чата
        await db.execute(delete(Message).where(Message.chat_id == chat_id))
        await db.commit()
        
        # Добавляем все сообщения из VK в БД
        # Сортируем по дате (от старых к новым)
        vk_messages_filtered.sort(key=lambda x: x.get("date", 0))
        
        for vk_msg in vk_messages_filtered:
            from_id = vk_msg.get("from_id", 0)
            text = vk_msg.get("text", "")
            attachments = vk_msg.get("attachments", [])
            msg_date = vk_msg.get("date", 0)
            
            # Определяем тип сообщения
            # Если from_id отрицательный (от группы) или from_id == VK_GROUP_ID, это ответ от админа/менеджера
            # Иначе - вопрос от пользователя
            if from_id < 0 or from_id == VK_GROUP_ID:
                message_type = "answer"
            else:
                message_type = "question"
            
            # Обрабатываем текстовые сообщения
            if text:
                db_message = Message(
                    chat_id=chat_id,
                    message=text,
                    message_type=message_type,
                    ai=False,
                    created_at=datetime.fromtimestamp(msg_date) if msg_date else datetime.utcnow(),
                    is_image=False
                )
                db.add(db_message)
            
            # Обрабатываем фото
            for att in attachments:
                if att.get("type") == "photo":
                    photo = att.get("photo", {})
                    # Получаем URL фотографии (берем самый большой размер)
                    photo_url = None
                    for size in ['photo_1280', 'photo_807', 'photo_604', 'photo_130', 'photo_75']:
                        if size in photo:
                            photo_url = photo[size]
                            break
                    
                    # Если не нашли прямые URL, пробуем получить из sizes
                    if not photo_url and "sizes" in photo:
                        sizes = photo["sizes"]
                        if sizes:
                            max_size = max(sizes, key=lambda s: s.get("height", 0))
                            photo_url = max_size.get("url")
                    
                    if photo_url:
                        # Скачиваем фото из VK
                        try:
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                                'Accept-Language': 'en-US,en;q=0.9',
                                'Referer': 'https://vk.com/'
                            }
                            async with aiohttp.ClientSession() as http_sess:
                                resp = await http_sess.get(photo_url, headers=headers)
                                if resp.status != 200:
                                    # Если не удалось скачать, сохраняем оригинальный URL
                                    img_url = photo_url
                                else:
                                    content = await resp.read()
                                    if not content:
                                        # Если контент пустой, сохраняем оригинальный URL
                                        img_url = photo_url
                                    else:
                                        # Загружаем в MinIO, если клиент доступен
                                        if minio_client:
                                            try:
                                                file_ext = os.path.splitext(photo_url.split('?')[0])[1] or ".jpg"
                                                file_name = f"{peer_id}-{int(msg_date) if msg_date else int(datetime.utcnow().timestamp())}{file_ext}"
                                                
                                                # Создаем BytesIO объект
                                                file_data = io.BytesIO(content)
                                                file_data.seek(0, 2)  # Перемещаемся в конец файла
                                                file_size = file_data.tell()  # Получаем размер
                                                file_data.seek(0)  # Возвращаемся в начало
                                                
                                                # Загружаем в MinIO
                                                await asyncio.to_thread(
                                                    minio_client.put_object,
                                                    BUCKET_NAME,
                                                    file_name,
                                                    file_data,
                                                    file_size,
                                                    content_type="image/jpeg"
                                                )
                                                # Не отдаём прямой :9000 наружу — отдаём через nginx /minio/...
                                                img_url = f"/minio/{BUCKET_NAME}/{file_name}"
                                            except Exception as minio_error:
                                                # Если ошибка при загрузке в MinIO, используем оригинальный URL
                                                img_url = photo_url
                                        else:
                                            # Если MinIO не настроен, используем оригинальный URL
                                            img_url = photo_url
                        except Exception as e:
                            # В случае ошибки сохраняем оригинальный URL из VK
                            img_url = photo_url
                        
                        db_message = Message(
                            chat_id=chat_id,
                            message=img_url,
                            message_type=message_type,
                            ai=False,
                            created_at=datetime.fromtimestamp(msg_date) if msg_date else datetime.utcnow(),
                            is_image=True
                        )
                        db.add(db_message)
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Messages synchronized successfully",
            "vk_count": vk_count,
            "db_count_before": db_count,
            "db_count_after": vk_count
        }
        
    except Exception as e:
        await db.rollback()
        return {"success": False, "message": f"Error during synchronization: {str(e)}"}


# ================== Аналитика диалогов ==================

async def assign_chat_to_manager(db: AsyncSession, chat_id: int, manager_id: int, manager_name: str) -> Optional[Dict[str, Any]]:
    """Назначает диалог менеджеру (кнопка 'Взять диалог')"""
    chat = await get_chat(db, chat_id)
    if not chat:
        return None
    
    # Если диалог уже назначен другому менеджеру
    if chat.assigned_manager_id and chat.assigned_manager_id != manager_id:
        return {"error": "already_assigned", "assigned_to": chat.assigned_manager_name}
    
    chat.assigned_manager_id = manager_id
    chat.assigned_manager_name = manager_name
    chat.assigned_at = datetime.utcnow()
    chat.dialog_status = "assigned"
    
    await db.commit()
    await db.refresh(chat)
    
    return {
        "success": True,
        "chat_id": chat.id,
        "manager_id": manager_id,
        "manager_name": manager_name,
        "assigned_at": chat.assigned_at.isoformat() if chat.assigned_at else None
    }


async def close_chat_dialog(db: AsyncSession, chat_id: int) -> Optional[Dict[str, Any]]:
    """Закрывает диалог (меняет статус на closed)"""
    chat = await get_chat(db, chat_id)
    if not chat:
        return None
    
    chat.dialog_status = "closed"
    await db.commit()
    await db.refresh(chat)
    
    return {"success": True, "chat_id": chat.id, "status": "closed"}


async def create_dialog_analytics(db: AsyncSession, analytics_data: Dict[str, Any]) -> DialogAnalytics:
    """Создает запись аналитики для диалога"""
    analytics = DialogAnalytics(**analytics_data)
    db.add(analytics)
    try:
        await db.commit()
        await db.refresh(analytics)
        return analytics
    except SQLAlchemyError:
        await db.rollback()
        raise


async def get_dialog_analytics(db: AsyncSession, chat_id: int) -> Optional[DialogAnalytics]:
    """Получает аналитику для конкретного диалога"""
    result = await db.execute(
        select(DialogAnalytics).filter(DialogAnalytics.chat_id == chat_id)
    )
    return result.scalar_one_or_none()


async def get_all_analytics(db: AsyncSession, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Получает список всех аналитик с пагинацией"""
    query = (
        select(DialogAnalytics, Chat)
        .join(Chat, DialogAnalytics.chat_id == Chat.id)
        .order_by(desc(DialogAnalytics.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    analytics_list = []
    for analytics, chat in rows:
        analytics_list.append({
            "id": analytics.id,
            "chat_id": analytics.chat_id,
            "chat_name": chat.name,
            "channel": analytics.channel,
            "manager_name": analytics.manager_name,
            "summary": analytics.summary,
            "customer_problem": analytics.customer_problem,
            "customer_intent": analytics.customer_intent,
            "refund_reason": analytics.refund_reason,
            "manager_quality_score": analytics.manager_quality_score,
            "customer_sentiment": analytics.customer_sentiment,
            "resolution_status": analytics.resolution_status,
            "key_topics": analytics.key_topics,
            "messages_count": analytics.messages_count,
            "created_at": analytics.created_at.isoformat() if analytics.created_at else None
        })
    
    return analytics_list


async def get_analytics_stats(db: AsyncSession) -> Dict[str, Any]:
    """Получает общую статистику по аналитике"""
    total = await db.scalar(select(func.count(DialogAnalytics.id)))
    avg_score = await db.scalar(select(func.avg(DialogAnalytics.manager_quality_score)))
    
    # Подсчет по настроению клиентов
    positive = await db.scalar(
        select(func.count(DialogAnalytics.id)).filter(DialogAnalytics.customer_sentiment == "positive")
    )
    negative = await db.scalar(
        select(func.count(DialogAnalytics.id)).filter(DialogAnalytics.customer_sentiment == "negative")
    )
    neutral = await db.scalar(
        select(func.count(DialogAnalytics.id)).filter(DialogAnalytics.customer_sentiment == "neutral")
    )
    
    # Подсчет возвратов
    refunds = await db.scalar(
        select(func.count(DialogAnalytics.id)).filter(DialogAnalytics.refund_reason.isnot(None))
    )
    
    return {
        "total_analyzed": total or 0,
        "avg_manager_score": round(float(avg_score), 2) if avg_score else None,
        "sentiment": {
            "positive": positive or 0,
            "neutral": neutral or 0,
            "negative": negative or 0
        },
        "refunds_count": refunds or 0
    }