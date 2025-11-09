export interface Message {
  id: number;
  chat_id: number;
  created_at: string;
  message: string;
  message_type: 'question' | 'answer' | 'text';
  ai: boolean;
  is_image?: boolean;
}

export interface Chat {
  id: number;
  uuid: string;
  waiting: boolean;
  ai: boolean;
  name: string;
  tags: string[];
  messager: string;
  lastMessage?: string;
  lastMessageTime?: string;
  unread?: boolean;
}

export interface WebSocketMessage {
  type: 'message' | 'update' | 'status_update' | 'chat_deleted' | 'chat_ai_updated';
  chatId: number;
  content?: string;
  message_type?: string;
  ai?: boolean;
  timestamp?: string;
  id?: number;
  chat?: {
    id: number;
    uuid: string;
    waiting: boolean;
  };
} 