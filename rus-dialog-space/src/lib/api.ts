import { toast } from '@/components/ui/sonner';
import { config } from '@/config';

export const API_URL = config.apiUrl;

// Функция для выполнения запроса с токеном
export const fetchWithTokenRefresh = async (
  url: string, 
  options: RequestInit = {}
): Promise<Response> => {
  // Добавляем токен к запросу
  const accessToken = localStorage.getItem('access_token');
  
  if (!accessToken) {
    return new Response(JSON.stringify({ detail: 'Authorization token missing' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  const headers: Record<string, string> = {};
  
  // Не устанавливаем Content-Type для FormData, браузер сам установит правильный
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  
  // Добавляем остальные заголовки из options
  if (options.headers) {
    Object.assign(headers, options.headers);
  }
  
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  const requestOptions = {
    ...options,
    headers,
  };

  // Выполняем запрос
  const response = await fetch(url, requestOptions);

  // Если получили 401, токен истек - просим пользователя авторизоваться заново
  if (response.status === 401) {
    // Удаляем токен из localStorage
    localStorage.removeItem('access_token');
    
    // Показываем сообщение пользователю
    toast.error('Сессия истекла. Пожалуйста, авторизуйтесь заново.');
  }

  return response;
};

// Функция для получения заголовков с токеном
const getAuthHeaders = () => {
  const accessToken = localStorage.getItem('access_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  
  return headers;
};

// Функция для входа
export const login = async (email: string, password: string): Promise<string> => {
  try {
    const response = await fetch(`${config.authUrl}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Ошибка при входе');
    }

    const data = await response.json();
    const token = data.access_token || data.token || data.access;
    
    if (token) {
      localStorage.setItem('access_token', token);
      return token;
    } else {
      throw new Error('Токен не получен');
    }
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
};

// Types
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

export interface Message {
  id: number;
  chat_id: number;
  created_at: string;
  message: string;
  message_type: 'question' | 'answer';
  ai: boolean;
  is_image: boolean;
}

// Get all chats
export const getChats = async (): Promise<Chat[]> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/chats`);
    
    if (!response.ok) {
      return [];
    }
    
    const chats = await response.json();
    
    return chats.map((chat: any) => ({
          id: chat.id,
          uuid: chat.uuid,
          waiting: chat.waiting,
          ai: chat.ai,
      name: chat.name,
      tags: chat.tags,
      messager: chat.messager,
      lastMessage: chat.last_message?.content || '',
      lastMessageTime: chat.last_message?.timestamp || '',
          unread: false // This should be implemented based on your business logic
    }));
  } catch (error) {
    console.error('Error fetching chats:', error);
    toast.error('Не удалось загрузить список чатов');
    return [];
  }
};

// Get messages for a specific chat
export const getChatMessages = async (chatId: number | string): Promise<Message[]> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}/messages`);
    if (!response.ok) {
      throw new Error('Failed to fetch messages');
    }
    const messages = await response.json();
    return messages.map((msg: any) => ({
      id: msg.id,
      chat_id: Number(msg.chatId || msg.chat_id),
      created_at: msg.created_at || msg.timestamp || '',
      message: msg.message || msg.content || '',
      message_type: msg.message_type || 'text',
      ai: typeof msg.ai === 'boolean' ? msg.ai : false,
      is_image: msg.is_image || false,
    }));
  } catch (error) {
    console.error('Error fetching messages:', error);
    toast.error('Не удалось загрузить сообщения');
    return [];
  }
};

// Send a new message
export const sendMessage = async (chatId: number, message: string, isAi: boolean): Promise<Message> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/messages`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        chat_id: chatId,
        message,
        message_type: 'answer',
        ai: isAi
      }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    
    const newMessage = await response.json();
    
    // Update chat waiting status
    await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}/waiting`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify({ waiting: false }),
    });
    
    return {
      id: newMessage.id,
      chat_id: newMessage.chat_id,
      created_at: newMessage.created_at,
      message: newMessage.message,
      message_type: newMessage.message_type,
      ai: newMessage.ai,
      is_image: newMessage.is_image || false,
    };
  } catch (error) {
    console.error('Error sending message:', error);
    toast.error('Не удалось отправить сообщение');
    throw error;
  }
};

// Toggle AI status for a chat
export const toggleAiChat = async (chatId: number, aiEnabled: boolean): Promise<Chat> => {
  try {
    console.log('Toggling AI status:', { chatId, aiEnabled });
    
    const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}/ai`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify({ ai: aiEnabled }),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      console.error('Failed to update chat AI status:', errorData);
      throw new Error('Failed to update chat');
    }
    
    const chat = await response.json();
    console.log('Chat AI status updated successfully:', chat);
    
    return {
      id: chat.id,
      uuid: chat.uuid,
      waiting: chat.waiting,
      ai: chat.ai,
      name: chat.name,
      tags: chat.tags,
      messager: chat.messager
    };
  } catch (error) {
    console.error('Error toggling AI status:', error);
    toast.error('Не удалось обновить статус ИИ');
    throw error;
  }
};

// Mark chat as read
export const markChatAsRead = async (chatId: number): Promise<void> => {
  try {
    console.log('Marking chat as read:', chatId);
    
    const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}/waiting`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify({ waiting: false }),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      console.error('Failed to update chat waiting status:', errorData);
      throw new Error('Failed to update chat waiting status');
    }
    
    const result = await response.json();
    console.log('Chat marked as read successfully:', result);
  } catch (error) {
    console.error('Error marking chat as read:', error);
  }
};

// Get chat statistics
export const getChatStats = async (): Promise<{ total: number, pending: number, ai: number }> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/stats`);
    
    if (!response.ok) {
      return { total: 0, pending: 0, ai: 0 };
    }
    
    const stats = await response.json();
    
    return stats;
  } catch (error) {
    console.error('Error fetching chat statistics:', error);
    return { total: 0, pending: 0, ai: 0 };
  }
};

// Delete a chat
export const deleteChat = async (chatId: number | string): Promise<void> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      console.error('Failed to delete chat:', errorData);
      throw new Error('Failed to delete chat');
    }
  } catch (error) {
    console.error('Error deleting chat:', error);
    toast.error('Не удалось удалить чат');
    throw error;
  }
};

// Add tag to chat
export const addChatTag = async (chatId: number, tag: string): Promise<{ success: boolean; tags: string[] }> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}/tags`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ tag }),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to add tag');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error adding tag:', error);
    toast.error('Не удалось добавить тег');
    throw error;
  }
};

// Remove tag from chat
export const removeChatTag = async (chatId: number, tag: string): Promise<{ success: boolean; tags: string[] }> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}/tags/${tag}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to remove tag');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error removing tag:', error);
    toast.error('Не удалось удалить тег');
    throw error;
  }
};

// Get AI context
export const getAiContext = async (): Promise<{ system_message: string, faqs: string }> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/ai/context`);
    if (!response.ok) {
      throw new Error('Failed to fetch AI context');
    }
    const data = await response.json();
    return {
      system_message: data["system_message"] || '',
      faqs: data.faqs || ''
    };
  } catch (error) {
    console.error('Error fetching AI context:', error);
    toast.error('Не удалось загрузить контекст ИИ');
    return { system_message: '', faqs: '' };
  }
};

// Put AI context
export const putAiContext = async (system_message: string, faqs: string): Promise<{ system_message: string, faqs: string }> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/ai/context`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify({ 
        system_message,
        faqs
      }),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to update AI context');
    }
    
    const data = await response.json();
    toast.success('Контекст ИИ успешно обновлен');
    return data;
  } catch (error) {
    console.error('Error updating AI context:', error);
    toast.error('Не удалось обновить контекст ИИ');
    throw error;
  }
};

// Sync VK chat
export const syncVkChat = async (chatId: number): Promise<{ success: boolean; message: string; vk_count?: number; db_count_before?: number; db_count_after?: number }> => {
  try {
    const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}/sync-vk`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to sync VK chat');
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error syncing VK chat:', error);
    toast.error('Не удалось синхронизировать чат');
    throw error;
  }
};
