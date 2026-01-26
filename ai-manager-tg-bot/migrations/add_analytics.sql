-- Миграция для добавления аналитики диалогов
-- Выполнить один раз на существующей базе данных

-- 1. Добавляем новые колонки в таблицу chats
ALTER TABLE chats ADD COLUMN IF NOT EXISTS assigned_manager_id INTEGER;
ALTER TABLE chats ADD COLUMN IF NOT EXISTS assigned_manager_name VARCHAR(100);
ALTER TABLE chats ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE chats ADD COLUMN IF NOT EXISTS dialog_status VARCHAR(20) DEFAULT 'new';

-- 2. Создаем таблицу для аналитики диалогов
CREATE TABLE IF NOT EXISTS dialog_analytics (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL UNIQUE REFERENCES chats(id),
    
    -- Основная информация
    manager_id INTEGER,
    manager_name VARCHAR(100),
    channel VARCHAR(20),
    
    -- Результаты AI-анализа
    summary TEXT,
    customer_problem TEXT,
    customer_intent VARCHAR(50),
    refund_reason TEXT,
    manager_quality_score INTEGER,
    manager_quality_notes TEXT,
    customer_sentiment VARCHAR(20),
    resolution_status VARCHAR(30),
    key_topics TEXT[],
    recommendations TEXT,
    
    -- Метаданные
    messages_count INTEGER DEFAULT 0,
    dialog_duration_minutes INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
    raw_ai_response JSONB
);

-- 3. Индексы
CREATE INDEX IF NOT EXISTS idx_dialog_analytics_chat_id ON dialog_analytics(chat_id);
CREATE INDEX IF NOT EXISTS idx_dialog_analytics_created_at ON dialog_analytics(created_at);
CREATE INDEX IF NOT EXISTS idx_chats_dialog_status ON chats(dialog_status);
CREATE INDEX IF NOT EXISTS idx_chats_assigned_manager_id ON chats(assigned_manager_id);

