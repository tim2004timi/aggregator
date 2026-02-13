-- Миграция: добавление topic_id для форум-группы Telegram
-- Запустить вручную или через docker exec:
--   docker exec -i postgres psql -U postgres -d mydb < /path/to/add_topic_id.sql

ALTER TABLE chats ADD COLUMN IF NOT EXISTS topic_id INTEGER;

