import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { Chat, Message, getChats, getChatMessages, sendMessage as apiSendMessage, markChatAsRead as apiMarkChatAsRead, getChatStats } from '@/lib/api';
import { useWebSocket } from './WebSocketContext';
import type { WebSocketMessage } from '@/types';

interface ChatContextType {
  chats: Chat[];
  selectedChat: Chat | null;
  messages: Message[];
  loading: boolean;
  unreadCount: number;
  shouldAutoScroll: boolean;
  setShouldAutoScroll: (value: boolean) => void;
  selectChat: (chatId: number | null) => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  refreshChats: () => Promise<void>;
  markChatAsRead: (chatId: number) => Promise<void>;
}

const ChatContext = createContext<ChatContextType | null>(null);

interface IncomingMessageWebSocket {
    type: 'message';
    chatId: string;
    content: string;
    message_type: 'question' | 'answer' | 'text';
    ai: boolean;
    timestamp: string;
    id: number;
    is_image?: boolean;
}

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [chats, setChats] = useState<Chat[]>([]);
  const [selectedChat, setSelectedChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const { lastMessage, sendMessage: wsSendMessage, lastUpdate } = useWebSocket();
  const isSelectingChat = useRef(false);
  const selectedChatRef = useRef<Chat | null>(null);
  const [stats, setStats] = useState<{ total: number; pending: number; ai: number }>({ total: 0, pending: 0, ai: 0 });
  const lastStatsUpdate = useRef<number>(0);

  useEffect(() => {
    selectedChatRef.current = selectedChat;
  }, [selectedChat]);

  const refreshChats = useCallback(async () => {
    try {
      setLoading(true);
      const chatData = await getChats();
      setChats(prevChats => {
        // Preserve selected chat state
        return chatData.map(newChat => {
          const prevChat = prevChats.find(c => c.id === newChat.id);
          return prevChat ? { ...newChat, ...prevChat } : newChat;
        });
      });
      
      // Calculate unread count
      const unread = chatData.filter(chat => chat.waiting).length;
      setUnreadCount(unread);
    } catch (error) {
      console.error('Failed to fetch chats:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refreshChats();
  }, [refreshChats]);

  // Получение статистики
  const fetchStats = useCallback(async () => {
    const now = Date.now();
    // Обновляем статистику не чаще чем раз в 2 секунды
    if (now - lastStatsUpdate.current < 2000) {
      return;
    }
    try {
      const statsData = await getChatStats();
      setStats(statsData);
      lastStatsUpdate.current = now;
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  }, []);

  // Handle WebSocket messages from lastMessage stream
  useEffect(() => {
    if (!lastMessage) return;

    try {
      const data = typeof lastMessage === 'string' ? JSON.parse(lastMessage) : lastMessage;

      if (data.type === 'message') {
        const wsMsgTyped = data as IncomingMessageWebSocket;
        
        const currentSelectedChat = selectedChatRef.current;
        
        if (currentSelectedChat && currentSelectedChat.id === Number(wsMsgTyped.chatId)) {
          const newMessage: Message = {
            id: wsMsgTyped.id,
            chat_id: Number(wsMsgTyped.chatId),
            created_at: wsMsgTyped.timestamp,
            message: wsMsgTyped.content,
            message_type: wsMsgTyped.message_type === 'question' ? 'question' : 'answer',
            ai: wsMsgTyped.ai,
            is_image: wsMsgTyped.is_image || false,
          };

          setMessages(prevMessages => [...prevMessages, newMessage]);
          }

        setChats(prevChats => {
          const updatedChats = prevChats.map(chat =>
            chat.id === Number(wsMsgTyped.chatId) ?
            {
              ...chat,
              lastMessage: wsMsgTyped.content,
              lastMessageTime: wsMsgTyped.timestamp,
            } : chat
          );
          return updatedChats;
        });

      }
    } catch (error) {
      console.error('WS error processing lastMessage:', error);
    }
  }, [lastMessage, selectedChatRef, setMessages, setChats]);

  useEffect(() => {
    if (!lastUpdate) return;
    
    try {
      const data = typeof lastUpdate === 'string' ? JSON.parse(lastUpdate) : lastUpdate;

      if (data.type === 'chat_deleted' && data.chatId) {
        setChats(prevChats => prevChats.filter(chat => String(chat.id) !== String(data.chatId)));
        setSelectedChat(prev => (prev && String(prev.id) === String(data.chatId) ? null : prev));
        fetchStats();
      } else if (data.type === 'chat_ai_updated' && data.chatId) {
        setChats(prevChats => prevChats.map(chat => 
          String(chat.id) === String(data.chatId) 
            ? { ...chat, ai: data.ai } 
            : chat
        ));
        fetchStats();
      } else if (data.type === 'chat_created' && data.chat) {
        const newChat = data.chat;

        setChats(prevChats => [
          newChat,
          ...prevChats,
        ]);

        fetchStats();
      } else if (data.type === 'chat_update') {
        setChats(prevChats => prevChats.map(chat => 
          String(chat.id) === String(data.chat_id) 
            ? { 
                ...chat, 
                waiting: data.waiting,
                ai: data.ai
              } 
            : chat
        ));
        fetchStats();
      } else if (data.type === 'chat_tags_updated' && data.chatId && data.tags) {
        setChats(prevChats => {
          const updatedChats = prevChats.map(chat =>
            chat.id === data.chatId
              ? { ...chat, tags: data.tags }
              : chat
          );
          const newChatsArray = [...updatedChats];
          return newChatsArray;
           });
      }
    } catch (error) {
      console.error('WS error processing lastUpdate:', error);
    }
  }, [lastUpdate, fetchStats, selectedChatRef, setChats, setSelectedChat]);

  // Начальная загрузка статистики
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const selectChat = useCallback(async (chatId: number | null) => {
    if (isSelectingChat.current) return;
    
    try {
      isSelectingChat.current = true;
      
      if (chatId === null) {
        // Clear the selected chat and messages
        setSelectedChat(null);
        setMessages([]);
        return;
      }
      
      // First, find the chat in our current list
      let chat = chats.find(c => c.id === chatId);
      
      // If chat not found, refresh the list
      if (!chat) {
        await refreshChats();
        chat = chats.find(c => c.id === chatId);
        if (!chat) {
          console.error('Chat not found after refresh:', chatId);
          return;
        }
      }
      
      // Then fetch messages
      const messagesData = await getChatMessages(chatId);
      setMessages(messagesData);
      
      // Set selected chat AFTER messages are loaded
      setSelectedChat(chat);
      
      // Mark as read if it was unread
      if (chat.waiting) {
        await apiMarkChatAsRead(chatId);
        setChats(prevChats => 
          prevChats.map(c => 
            c.id === chatId 
              ? { ...c, waiting: false }
              : c
          )
        );
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error('Failed to select chat:', error);
      // If there's an error, clear the selection
      setSelectedChat(null);
      setMessages([]);
    } finally {
      isSelectingChat.current = false;
    }
  }, [chats, refreshChats]);

  const sendMessage = useCallback(async (message: string) => {
    if (!selectedChat) return;

    try {
      const newMessage = await apiSendMessage(selectedChat.id, message, false);
      // При отправке используем selectedChat.id (ID из БД) для chat_id
      wsSendMessage({
        id: newMessage.id, // Используем id созданного сообщения
        chat_id: selectedChat.id, // ID чата из БД
        created_at: newMessage.created_at, // Используем timestamp созданного сообщения
        message: message, // Содержимое сообщения
        message_type: 'text', // Тип сообщения
        ai: false, // Это сообщение пользователя, не AI
        is_image: false, // Default value, as the original code didn't include is_image
      });
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  }, [selectedChat, wsSendMessage]);

  const markChatAsRead = useCallback(async (chatId: number) => {
    try {
      await apiMarkChatAsRead(chatId);
      setChats(prevChats => 
        prevChats.map(chat => 
          chat.id === chatId 
            ? { ...chat, waiting: false }
            : chat
        )
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Failed to mark chat as read:', error);
    }
  }, []);

  const value = {
    chats,
    selectedChat,
    messages,
    loading,
    unreadCount,
    shouldAutoScroll,
    setShouldAutoScroll,
    selectChat,
    sendMessage,
    refreshChats,
    markChatAsRead,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}; 