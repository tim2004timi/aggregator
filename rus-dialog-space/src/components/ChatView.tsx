import { useState, useEffect, useRef, useCallback } from 'react';
import { Message, Chat, getChatMessages, sendMessage as apiSendMessage, toggleAiChat, markChatAsRead, deleteChat, API_URL, fetchWithTokenRefresh, syncVkChat } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Send, Trash2, Paperclip, ArrowDown, RotateCw } from 'lucide-react';
import { toast } from '@/components/ui/sonner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useWebSocket } from '@/contexts/WebSocketContext';
import { useChat } from '@/contexts/ChatContext';
import { ChatTags } from '@/components/ChatTags';
import {
  Dialog,
  DialogTrigger,
  DialogContent
} from "@/components/ui/dialog";

interface ChatViewProps {
  chatId: number | null;
  onChatDeleted?: () => void;
}

const ChatView = ({ chatId, onChatDeleted }: ChatViewProps) => {
  const [newMessage, setNewMessage] = useState('');
  const [aiEnabled, setAiEnabled] = useState(false);
  const [chatInfo, setChatInfo] = useState<Chat | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { sendMessage: wsSendMessage } = useWebSocket();
  const { 
    messages, 
    loading: chatContextLoading, 
    selectedChat, 
    markChatAsRead: markChatAsReadFromContext, 
    refreshChats, 
    sendMessage,
    shouldAutoScroll,
    setShouldAutoScroll,
    selectChat: selectChatFromContext
  } = useChat();

  // Track the last message timestamp we've seen
  const lastSeenMessageRef = useRef<string>('');

  // Format timestamp for display
  const formatMessageTime = (timestamp: string) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleDateString('ru-RU', { 
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).replace(',', '');
  };

  const fetchChatInfo = useCallback(async () => {
    if (!chatId) return;
    setError(null);
    try {
      // Fetch chat info directly if chatId is available
      const response = await fetchWithTokenRefresh(`${API_URL}/chats/${chatId}`);
      if (!response.ok) {
        const errorData = await response.json();
        setError(errorData.detail || 'Чат не найден или недоступен.');
          setChatInfo(null);
          return;
        }
      const chatData = await response.json();
      setAiEnabled(chatData.ai);
      setChatInfo(chatData);

      // Fetch all messages for the chat when chat info is loaded
      const messagesData = await getChatMessages(chatData.id); // Fetch all messages
      // Note: messages are added to context state via selectChat, not here directly

    } catch (error) {
      setError('Ошибка при загрузке чата.');
      setChatInfo(null);
      console.error('Failed to fetch chat info:', error, 'chatId:', chatId);
    }
  }, [chatId]);

  useEffect(() => {
    // When chatId changes, fetch chat info and messages
    if (chatId) {
      fetchChatInfo();
      // Messages are now loaded by ChatContext when selectChat is called.
      // Ensure selectChat is called in the parent component when chatId changes.

    } else {
      setChatInfo(null);
    }
  }, [chatId, fetchChatInfo]);

  // Send waiting=false periodically when chat is open
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;

    if (chatId) {
      // Send immediately on chat open
      markChatAsReadFromContext(chatId);

      // Set interval for subsequent calls
      intervalId = setInterval(() => {
        markChatAsReadFromContext(chatId);
      }, 3000); // Send every 3 seconds
    }

    // Cleanup function to clear interval
    return () => {
      if (intervalId !== null) {
        clearInterval(intervalId);
      }
    };
  }, [chatId, markChatAsReadFromContext]); // Re-run effect if chatId or markChatAsReadFromContext changes

  // Check if user is near bottom of chat
  const checkScrollPosition = useCallback(() => {
    if (!messagesContainerRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const isNear = distanceFromBottom < 100; // Consider "near bottom" if within 100px
    setIsNearBottom(isNear);
    
    // If user manually scrolls to bottom, clear unread count and update last seen
    if (isNear && messages.length > 0) {
      setUnreadCount(0);
      setShouldAutoScroll(true);
      lastSeenMessageRef.current = messages[messages.length - 1].created_at;
    } else {
      setShouldAutoScroll(false);
    }
  }, [setShouldAutoScroll, messages]);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (shouldAutoScroll && isNearBottom) {
      scrollToBottom();
      // Update last seen message when auto-scrolling
      if (messages.length > 0) {
        lastSeenMessageRef.current = messages[messages.length - 1].created_at;
      }
    } else if (!isNearBottom && messages.length > 0) {
      // Only increment unread count for messages newer than the last seen message
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.created_at > lastSeenMessageRef.current) {
        setUnreadCount(prev => prev + 1);
        lastSeenMessageRef.current = lastMessage.created_at;
      }
    }
  }, [messages, shouldAutoScroll, isNearBottom]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setUnreadCount(0);
    setShouldAutoScroll(true);
    // Update last seen message when manually scrolling to bottom
    if (messages.length > 0) {
      lastSeenMessageRef.current = messages[messages.length - 1].created_at;
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedChat) return;
    try {
      await sendMessage(newMessage);
      setNewMessage('');
    } catch (error) {
      console.error('Failed to send message:', error);
      toast.error('Не удалось отправить сообщение');
    }
  };

  const handleAiToggle = async (checked: boolean) => {
    if (!chatId) return;
    
    try {
      console.log('Toggling AI status:', { chatId, checked });
      const updatedChat = await toggleAiChat(chatId, checked);
      console.log('AI status updated:', updatedChat);
      setAiEnabled(updatedChat.ai);
      toast.success(checked ? 'ИИ включен для этого чата' : 'ИИ отключен для этого чата');
    } catch (error) {
      console.error('Failed to toggle AI status:', error);
      fetchChatInfo();
    }
  };

  const handleDeleteChat = async () => {
    if (!chatId) return;
    
    try {
      await deleteChat(chatId);
      toast.success('Чат успешно удален');
      if (onChatDeleted) {
        onChatDeleted();
      }
    } catch (error) {
      console.error('Failed to delete chat:', error);
    }
  };

  const handleSyncVk = async () => {
    if (!chatId || !chatInfo || chatInfo.messager !== 'vk') return;
    
    setIsSyncing(true);
    try {
      const result = await syncVkChat(chatId);
      if (result.success) {
        toast.success(result.message || 'Чат успешно синхронизирован');
        // Обновляем информацию о чате
        await fetchChatInfo();
        // Обновляем сообщения через selectChat из контекста
        await selectChatFromContext(chatId);
      } else {
        toast.error(result.message || 'Ошибка синхронизации');
      }
    } catch (error) {
      console.error('Failed to sync VK chat:', error);
      toast.error('Не удалось синхронизировать чат');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedChat) return;

    // Check if file is an image
    if (!file.type.startsWith('image/')) {
      toast.error('Пожалуйста, выберите изображение');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('chat_id', selectedChat.id.toString());

      console.log('📤 Отправка изображения:', {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
        chatId: selectedChat.id,
        formDataEntries: Array.from(formData.entries())
      });

      const response = await fetchWithTokenRefresh(`${API_URL}/messages/image`, {
        method: 'POST',
        body: formData,
      });

      console.log('📥 Ответ сервера:', response.status, response.statusText);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Ошибка загрузки изображения:', errorText);
        throw new Error(`Failed to upload image: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      console.log('✅ Изображение успешно загружено:', data);
      setNewMessage('');
      toast.success('Изображение отправлено');
    } catch (error) {
      console.error('Error uploading image:', error);
      toast.error('Не удалось отправить изображение');
    }
  };

  useEffect(() => {
    if (selectedChat && selectedChat.id === chatId) {
      setChatInfo(selectedChat);
      setAiEnabled(selectedChat.ai);
    }
  }, [selectedChat, chatId]);

  if (!chatId) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center p-6">
          <h3 className="text-xl font-medium text-gray-600 mb-2">Выберите чат</h3>
          <p className="text-gray-500">Выберите чат из списка слева чтобы начать общение</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center p-6">
          <h3 className="text-xl font-medium text-red-600 mb-2">{error}</h3>
          <p className="text-gray-500">Попробуйте выбрать другой чат или обновить страницу.</p>
        </div>
      </div>
    );
  }

  const displayLoading = chatContextLoading && messages.length === 0;

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Chat Header */}
      <div className="border-b border-gray-300 py-2 px-4 flex items-center justify-between h-14">
        <div className="flex items-center gap-2 flex-grow min-w-0">
          <h2 className="text-lg font-medium text-gray-800 truncate">
            {chatInfo?.name || `Чат #${chatId}`}
          </h2>
          {chatInfo && (
            <ChatTags
              chatId={chatInfo.id}
              tags={chatInfo.tags || []}
              onTagsUpdate={(newTags) => {
                setChatInfo(prev => prev ? { ...prev, tags: newTags } : null);
              }}
            />
          )}
        </div>
        <div className="flex items-center space-x-2 flex-shrink-0">
          {chatInfo?.messager === 'vk' && (
            <Button
              variant="ghost"
              size="icon"
              className="text-gray-500 hover:text-gray-700 hover:bg-gray-100"
              onClick={handleSyncVk}
              disabled={isSyncing}
            >
              <RotateCw 
                size={18} 
                className={isSyncing ? 'animate-spin' : ''}
              />
            </Button>
          )}
          <div className="flex items-center space-x-1">
            <span className="text-sm text-gray-600 hidden sm:inline">ИИ</span>
            <Switch checked={aiEnabled} onCheckedChange={handleAiToggle} />
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="text-red-500 hover:text-red-600 hover:bg-red-50"
            onClick={() => setShowDeleteDialog(true)}
          >
            <Trash2 size={18} />
          </Button>
        </div>
      </div>
      
      {/* Messages Area */}
      <div 
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
        onScroll={checkScrollPosition}
      >
        {displayLoading ? (
          <div className="flex justify-center p-4">
            <p className="text-gray-500">Загрузка сообщений...</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex justify-center p-4">
            <p className="text-gray-500">Нет сообщений</p>
          </div>
        ) : (
          <>
            {[...messages]
              .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
              .map((message, index) => (
            <MessageBubble 
                  key={`${message.id}-${index}`}
              message={message} 
              formatTime={formatMessageTime}
            />
              ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input Area */}
      <div className="border-t border-gray-200 p-2 bg-white">
        <form onSubmit={handleSendMessage} className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="flex-shrink-0"
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip size={20} />
          </Button>
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept="image/*"
            onChange={handleFileSelect}
          />
          <Input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Введите сообщение..."
            className="flex-1"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!newMessage.trim()}
            className="flex-shrink-0"
          >
            <Send size={20} />
          </Button>
        </form>
      </div>

      {/* Scroll to Bottom Button */}
      {!isNearBottom && (
        <div className="fixed bottom-20 right-4">
          <Button
            variant="secondary"
            size="icon"
            className="rounded-full shadow-lg relative"
            onClick={scrollToBottom}
          >
            <ArrowDown size={20} />
            {unreadCount > 0 && (
              <div className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {unreadCount}
              </div>
            )}
          </Button>
        </div>
      )}

      {/* Delete Chat Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить чат?</AlertDialogTitle>
            <AlertDialogDescription>
              Это действие нельзя отменить. Это навсегда удалит чат и все его сообщения.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteChat}
              className="bg-red-500 hover:bg-red-600"
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

interface MessageBubbleProps {
  message: Message;
  formatTime: (timestamp: string) => string;
}

const MessageBubble = ({ message, formatTime }: MessageBubbleProps) => {
  const isQuestion = message.message_type === 'question';
  const imageRef = useRef<HTMLImageElement>(null);
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (message.is_image && imageRef.current) {
      imageRef.current.onload = () => {
        // Scroll to bottom after image loads
        const messagesContainer = document.querySelector('.messages-container');
        if (messagesContainer) {
          messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
      };
    }
  }, [message.is_image]);

  // Handlers for zoom and pan
  const handleWheel = (e: React.WheelEvent<HTMLImageElement>) => {
    e.preventDefault();
    setZoom((z) => Math.max(0.5, Math.min(5, z - e.deltaY * 0.001)));
  };
  const handleMouseDown = (e: React.MouseEvent<HTMLImageElement>) => {
    setDragging(true);
    setStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };
  const handleMouseMove = (e: React.MouseEvent<HTMLImageElement>) => {
    if (!dragging || !start) return;
    setOffset({ x: e.clientX - start.x, y: e.clientY - start.y });
  };
  const handleMouseUp = () => setDragging(false);
  const handleDialogOpenChange = (o: boolean) => {
    setOpen(o);
    if (!o) {
      setZoom(1);
      setOffset({ x: 0, y: 0 });
      setDragging(false);
      setStart(null);
    }
  };

  return (
    <div className={`mb-4 flex ${isQuestion ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-[80%] rounded-lg px-4 py-2 ${
        isQuestion ? 'bg-gray-300 text-gray-800' : 'bg-[#1F1F1F] text-white'
      }`}>
        <div className="mb-1 flex items-center">
          {message.ai && (
            <div className="mr-1 text-xs px-1 py-0.5 bg-white/20 rounded">
              ИИ
            </div>
          )}
        </div>
        {message.is_image ? (
          <Dialog open={open} onOpenChange={handleDialogOpenChange}>
            <DialogTrigger asChild>
              <img
                ref={imageRef}
                src={message.message}
                alt="Uploaded image"
                className="max-w-full rounded-lg cursor-zoom-in"
                style={{ maxHeight: '300px' }}
                onClick={() => setOpen(true)}
              />
            </DialogTrigger>
            <DialogContent className="flex items-center justify-center bg-black">
              <div
                style={{
                  overflow: 'hidden',
                  width: '100%',
                  height: '80vh',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'black',
                  cursor: dragging ? 'grabbing' : 'grab',
                }}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              >
                <img
                  src={message.message}
                  alt="Zoomed image"
                  style={{
                    transform: `scale(${zoom}) translate(${offset.x / zoom}px, ${offset.y / zoom}px)`,
                    transition: dragging ? 'none' : 'transform 0.2s',
                    maxWidth: '100%',
                    maxHeight: '80vh',
                    userSelect: 'none',
                    pointerEvents: 'auto',
                  }}
                  onWheel={handleWheel}
                  onMouseDown={handleMouseDown}
                  draggable={false}
                />
              </div>
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 bg-black/60 rounded px-3 py-1">
                <button
                  className="text-white text-lg px-2"
                  onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))}
                  type="button"
                >
                  -
                </button>
                <span className="text-white">{Math.round(zoom * 100)}%</span>
                <button
                  className="text-white text-lg px-2"
                  onClick={() => setZoom((z) => Math.min(5, z + 0.2))}
                  type="button"
                >
                  +
                </button>
              </div>
            </DialogContent>
          </Dialog>
        ) : (
          <p className="whitespace-pre-wrap break-words">{message.message}</p>
        )}
        <div className="text-right mt-1">
          <span className={`text-xs ${isQuestion ? 'text-gray-500' : 'text-gray-300'}`}>
            {formatTime(message.created_at)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ChatView;
