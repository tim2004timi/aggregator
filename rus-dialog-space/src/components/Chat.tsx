import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useWebSocket } from '../contexts/WebSocketContext';
import { Message } from '../types';
import { API_URL, fetchWithTokenRefresh } from '../lib/api';

interface ChatProps {
  chatId: string;
}

export const Chat: React.FC<ChatProps> = ({ chatId }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const { sendMessage, lastMessage, isConnected } = useWebSocket();

  const loadMessages = useCallback(async (pageNum: number) => {
    if (!chatId) return;
    
    try {
      setIsLoading(true);
      const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}/messages?page=${pageNum}&limit=50`);
      if (!response.ok) {
        throw new Error('Failed to load messages');
      }
      const data = await response.json();
      console.log('Loaded messages:', data);
      
      if (pageNum === 1) {
        setMessages(data);
      } else {
        setMessages(prev => [...prev, ...data]);
      }
      setHasMore(data.length === 50);
    } catch (error) {
      console.error('Error loading messages:', error);
    } finally {
      setIsLoading(false);
    }
  }, [chatId]);

  useEffect(() => {
    if (chatId) {
      setPage(1);
      loadMessages(1);
    }
  }, [chatId, loadMessages]);

  useEffect(() => {
    if (lastMessage && lastMessage.chatId === chatId) {
      console.log('Received new message:', lastMessage);
      setMessages(prev => {
        // Check if message already exists
        const exists = prev.some(msg => 
          msg.content === lastMessage.content && 
          msg.timestamp === lastMessage.timestamp
        );
        if (!exists) {
          return [...prev, lastMessage];
        }
        return prev;
      });
    }
  }, [lastMessage, chatId]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleScroll = useCallback(() => {
    if (!chatContainerRef.current) return;
    
    const { scrollTop } = chatContainerRef.current;
    if (scrollTop === 0 && hasMore && !isLoading) {
      setPage(prev => {
        const nextPage = prev + 1;
        loadMessages(nextPage);
        return nextPage;
      });
    }
  }, [hasMore, isLoading, loadMessages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || !isConnected) return;

    const message: Message = {
      chatId,
      content: inputMessage,
      message_type: 'text',
      ai: false,
      timestamp: new Date().toISOString()
    };

    sendMessage(message);
    setInputMessage('');
  };

  return (
    <div className="flex flex-col h-full">
      <div 
        ref={chatContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
        onScroll={handleScroll}
      >
        {isLoading && (
          <div className="flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
          </div>
        )}
        {messages.map((message, index) => (
          <div
            key={`${message.timestamp}-${index}`}
            className={`flex ${message.ai ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={`max-w-[70%] rounded-lg p-3 ${
                message.ai
                  ? 'bg-gray-100 text-gray-900'
                  : 'bg-blue-500 text-white'
              }`}
            >
              <p className="text-sm">{message.content}</p>
              <p className="text-xs mt-1 opacity-70">
                {new Date(message.timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSubmit} className="p-4 border-t">
        <div className="flex space-x-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder={isConnected ? "Type a message..." : "Connecting..."}
            disabled={!isConnected}
            className="flex-1 p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={!isConnected || !inputMessage.trim()}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}; 