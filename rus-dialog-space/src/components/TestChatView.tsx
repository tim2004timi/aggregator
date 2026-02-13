import { useState, useEffect, useRef, useCallback } from 'react';
import { Message, Chat, getChatMessages, toggleAiChat, deleteChat, API_URL, fetchWithTokenRefresh, syncVkChat, analyzeChat, getChatAnalytics, DialogAnalytics, assignChat, getCurrentUser, User } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Send, Trash2, Paperclip, ArrowDown, RotateCw, BarChart3, TrendingUp, MessageSquare, Target, Lightbulb, MoreVertical, X } from 'lucide-react';
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
import { useIsMobile } from '@/hooks/use-mobile';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface TestChatViewProps {
  chatId: number | null;
  onChatDeleted?: () => void;
}

const TestChatView = ({ chatId, onChatDeleted }: TestChatViewProps) => {
  const isMobile = useIsMobile();
  const [newMessage, setNewMessage] = useState('');
  const [aiEnabled, setAiEnabled] = useState(false);
  const [chatInfo, setChatInfo] = useState<Chat | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analytics, setAnalytics] = useState<DialogAnalytics | null>(null);
  const [showAnalyticsDialog, setShowAnalyticsDialog] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(console.error);
  }, []);

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
    selectChat: selectChatFromContext,
    deleteMessage: deleteMessageFromContext
  } = useChat();

  const lastSeenMessageRef = useRef<string>('');

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
    } catch (err) {
      setError('Ошибка при загрузке чата.');
      setChatInfo(null);
      console.error('Failed to fetch chat info:', err, 'chatId:', chatId);
    }
  }, [chatId]);

  useEffect(() => {
    if (chatId) {
      fetchChatInfo();
    } else {
      setChatInfo(null);
    }
  }, [chatId, fetchChatInfo]);

  useEffect(() => {
    if (chatId) {
      markChatAsReadFromContext(chatId);
    }
  }, [chatId, markChatAsReadFromContext]);

  const checkScrollPosition = useCallback(() => {
    if (!messagesContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const isNear = distanceFromBottom < 100;
    setIsNearBottom(isNear);
    if (isNear && messages.length > 0) {
      setUnreadCount(0);
      setShouldAutoScroll(true);
      lastSeenMessageRef.current = messages[messages.length - 1].created_at;
    } else {
      setShouldAutoScroll(false);
    }
  }, [setShouldAutoScroll, messages]);

  useEffect(() => {
    if (shouldAutoScroll && isNearBottom) {
      scrollToBottom();
      if (messages.length > 0) {
        lastSeenMessageRef.current = messages[messages.length - 1].created_at;
      }
    } else if (!isNearBottom && messages.length > 0) {
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
    } catch (err) {
      console.error('Failed to send message:', err);
      toast.error('Не удалось отправить сообщение');
    }
  };

  const handleAiToggle = async (checked: boolean) => {
    if (!chatId) return;
    try {
      const updatedChat = await toggleAiChat(chatId, checked);
      setAiEnabled(updatedChat.ai);
      toast.success(checked ? 'ИИ включен для этого чата' : 'ИИ отключен для этого чата');
    } catch (err) {
      console.error('Failed to toggle AI status:', err);
      fetchChatInfo();
    }
  };

  const handleDeleteChat = async () => {
    if (!chatId) return;
    try {
      await deleteChat(chatId);
      toast.success('Чат успешно удален');
      if (onChatDeleted) onChatDeleted();
    } catch (err) {
      console.error('Failed to delete chat:', err);
    }
  };

  const handleSyncVk = async () => {
    if (!chatId || !chatInfo || chatInfo.messager !== 'vk') return;
    setIsSyncing(true);
    try {
      const result = await syncVkChat(chatId);
      if (result.success) {
        toast.success(result.message || 'Чат успешно синхронизирован');
        await fetchChatInfo();
        await selectChatFromContext(chatId);
      } else {
        toast.error(result.message || 'Ошибка синхронизации');
      }
    } catch (err) {
      console.error('Failed to sync VK chat:', err);
      toast.error('Не удалось синхронизировать чат');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleEndDialog = async () => {
    if (!chatId) return;
    setIsAnalyzing(true);
    try {
      const result = await analyzeChat(chatId);
      setAnalytics(result);
      setShowAnalyticsDialog(true);
      setAiEnabled(true);
      await fetchChatInfo();
      await refreshChats();
    } catch (err) {
      console.error('Failed to analyze chat:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleTakeChat = async () => {
    if (!chatId || !currentUser) return;
    try {
      const managerName = currentUser.name || currentUser.email;
      await assignChat(chatId, currentUser.id, managerName);
      
      if (aiEnabled) {
        await toggleAiChat(chatId, false);
        setAiEnabled(false);
      }
      
      await fetchChatInfo();
      await refreshChats();
      toast.success('Вы взяли чат в работу');
    } catch (err) {
      console.error('Failed to take chat:', err);
    }
  };

  const isAssignedToMe = currentUser && chatInfo?.assigned_manager_id === currentUser.id;
  const isUnassigned = !chatInfo?.assigned_manager_id;
  const canWrite = isAssignedToMe || false;

  const loadExistingAnalytics = useCallback(async () => {
    if (!chatId) return;
    const existing = await getChatAnalytics(chatId);
    setAnalytics(existing);
  }, [chatId]);

  useEffect(() => {
    if (chatId) {
      loadExistingAnalytics();
    }
  }, [chatId, loadExistingAnalytics]);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedChat) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Пожалуйста, выберите изображение');
      return;
    }
    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('chat_id', selectedChat.id.toString());
      const response = await fetchWithTokenRefresh(`${API_URL}/messages/image`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Failed to upload image: ${response.status}`);
      }
      setNewMessage('');
      toast.success('Изображение отправлено');
    } catch (err) {
      console.error('Error uploading image:', err);
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
          <h3 className="text-lg font-semibold text-gray-600 mb-2">Выберите чат</h3>
          <p className="text-sm text-gray-400">Выберите чат из списка слева чтобы начать общение</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center p-6">
          <h3 className="text-lg font-medium text-red-600 mb-2">{error}</h3>
          <p className="text-sm text-gray-500">Попробуйте выбрать другой чат или обновить страницу.</p>
        </div>
      </div>
    );
  }

  const displayLoading = chatContextLoading && messages.length === 0;

  return (
    <div className="h-full flex flex-col bg-white overflow-hidden relative">
      {/* Chat Header */}
      <div className="border-b border-gray-200 py-2 px-4 flex items-center justify-between h-14 flex-shrink-0 bg-white z-10">
        <div className="flex items-center gap-3 flex-grow min-w-0">
          {/* Messenger badge */}
          <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
            {chatInfo?.messager === 'telegram' ? (
              <Send size={16} className="text-blue-500" />
            ) : chatInfo?.messager === 'vk' ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <rect width="24" height="24" rx="6" fill="#2787F5"/>
                <path d="M17.5 8.5C17.7 7.9 17.5 7.5 16.7 7.5H15.5C15 7.5 14.8 7.8 14.6 8.2C14.6 8.2 13.7 10.1 13.1 10.9C12.9 11.1 12.8 11.2 12.7 11.2C12.6 11.2 12.5 11.1 12.5 10.8V8.5C12.5 8 12.4 7.5 11.6 7.5H9.1C8.7 7.5 8.5 7.7 8.5 8C8.5 8.5 9.2 8.6 9.3 10.1V12.1C9.2 12.4 9 12.5 8.8 12.5C8.5 12.5 7.7 11.5 7.2 10.3C7 9.8 6.8 9.5 6.3 9.5H5.5C5.1 9.5 5 9.7 5 10C5 10.5 5.5 11.7 6.6 13.2C7.7 14.7 9.1 15.5 10.3 15.5C10.7 15.5 10.9 15.3 10.9 14.9V14.1C10.9 13.7 11 13.6 11.3 13.6C11.5 13.6 12 13.7 12.6 14.3C13.4 15.1 13.7 15.5 14.3 15.5H15.5C15.9 15.5 16 15.3 16 15C16 14.5 15.3 14.4 14.7 13.7C14.5 13.5 14.5 13.4 14.7 13.1C14.7 13.1 17.1 10.2 17.5 8.5Z" fill="white"/>
              </svg>
            ) : (
              <MessageSquare size={16} className="text-gray-400" />
            )}
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-gray-900 truncate">
              {chatInfo?.name || 'Никнейм'}
            </h2>
            <p className="text-[10px] text-gray-400">
              Номер чата {chatInfo?.id ?? chatId}
            </p>
          </div>
          {!isMobile && chatInfo && (
            <div className="ml-2">
              <ChatTags
                chatId={chatInfo.id}
                tags={chatInfo.tags || []}
                onTagsUpdate={(newTags) => {
                  setChatInfo(prev => prev ? { ...prev, tags: newTags } : null);
                }}
              />
            </div>
          )}
        </div>
        <div className="flex items-center space-x-1 sm:space-x-2 flex-shrink-0 ml-2">
          {!isMobile ? (
            <>
              {chatInfo?.messager === 'vk' && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-gray-500 hover:text-gray-700 hover:bg-gray-100 h-8 w-8"
                  onClick={handleSyncVk}
                  disabled={isSyncing}
                >
                  <RotateCw size={16} className={isSyncing ? 'animate-spin' : ''} />
                </Button>
              )}
              {isAssignedToMe && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-gray-700 border-gray-200 hover:bg-gray-50 h-8 text-xs"
                  onClick={handleEndDialog}
                  disabled={isAnalyzing}
                >
                  Закончить диалог
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                className={`hover:bg-blue-50 h-8 w-8 ${analytics ? 'text-blue-500' : 'text-gray-400 cursor-not-allowed'}`}
                onClick={analytics ? () => setShowAnalyticsDialog(true) : undefined}
                disabled={!analytics}
              >
                <BarChart3 size={16} className={isAnalyzing ? 'animate-pulse' : ''} />
              </Button>
              <div className="flex items-center space-x-1 ml-1">
                <span className="text-xs text-gray-600">ИИ</span>
                <Switch checked={aiEnabled} onCheckedChange={handleAiToggle} />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="text-red-500 hover:text-red-600 hover:bg-red-50 h-8 w-8"
                onClick={() => setShowDeleteDialog(true)}
              >
                <Trash2 size={16} />
              </Button>
            </>
          ) : (
            <>
              <div className="flex items-center space-x-1 mr-1">
                <span className="text-[10px] text-gray-600 font-medium">ИИ</span>
                <Switch checked={aiEnabled} onCheckedChange={handleAiToggle} className="scale-75 origin-right" />
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <MoreVertical size={18} />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  {chatInfo?.messager === 'vk' && (
                    <DropdownMenuItem onClick={handleSyncVk} disabled={isSyncing}>
                      <RotateCw size={16} className={`mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
                      Синхронизировать VK
                    </DropdownMenuItem>
                  )}
                  {isAssignedToMe && (
                    <DropdownMenuItem onClick={handleEndDialog} disabled={isAnalyzing}>
                      <TrendingUp size={16} className="mr-2" />
                      Закончить диалог
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem 
                    onClick={analytics ? () => setShowAnalyticsDialog(true) : undefined}
                    disabled={!analytics}
                  >
                    <BarChart3 size={16} className="mr-2" />
                    Посмотреть анализ
                  </DropdownMenuItem>
                  <DropdownMenuItem 
                    onClick={() => setShowDeleteDialog(true)}
                    className="text-red-600 focus:text-red-600"
                  >
                    <Trash2 size={16} className="mr-2" />
                    Удалить чат
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
        </div>
      </div>
      
      {/* Messages Area - wrapper for overlay positioning */}
      <div className="flex-1 relative overflow-hidden">
        <div 
          ref={messagesContainerRef}
          className="h-full overflow-y-auto p-4 space-y-4 scrolling-touch"
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
          <div className="flex flex-col space-y-4">
            {[...messages]
              .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
              .map((message, index) => (
                <MessageBubble 
                  key={`${message.id}-${index}`}
                  message={message} 
                  formatTime={formatMessageTime}
                  onDelete={async (messageId) => {
                    try {
                      await deleteMessageFromContext(messageId);
                      toast.success('Сообщение удалено');
                    } catch {
                      toast.error('Не удалось удалить сообщение');
                    }
                  }}
                />
              ))}
            <div ref={messagesEndRef} className="h-1" />
          </div>
        )}
        </div>

        {/* Take Chat Overlay - floats over messages area */}
        {!isAssignedToMe && !displayLoading && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/50 backdrop-blur-[1px]">
            <Button 
              onClick={handleTakeChat}
              className="bg-[#1F1F1F] text-white hover:bg-black text-sm font-bold uppercase tracking-wider px-10 py-7 rounded-2xl shadow-2xl transform transition-all hover:scale-105 active:scale-95"
            >
              ВЗЯТЬ ЧАТ
            </Button>
          </div>
        )}
      </div>

      {/* Message Input Area */}
      <div className="border-t border-gray-200 bg-white flex-shrink-0 pb-[safe-area-inset-bottom]">
        <div className="p-3 sm:p-4">
          <form onSubmit={handleSendMessage} className="flex items-end gap-2">
            <button 
              type="button" 
              className="text-gray-400 hover:text-gray-600 transition-colors p-2 h-10 w-10 flex items-center justify-center" 
              onClick={() => fileInputRef.current?.click()} 
              disabled={!canWrite}
            >
              <Paperclip size={20} />
            </button>
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              accept="image/*"
              onChange={handleFileSelect}
            />
            <div className="relative flex-1">
              <Input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Написать сообщение..."
                className="w-full min-h-[40px] py-2 pl-4 pr-4 bg-gray-50 border-gray-200 rounded-xl focus:bg-white transition-colors"
                disabled={!canWrite}
              />
            </div>
            <Button
              type="submit"
              size="icon"
              disabled={!newMessage.trim() || !canWrite}
              className="h-10 w-10 bg-black text-white rounded-full hover:bg-gray-800 flex-shrink-0"
            >
              <Send size={18} />
            </Button>
          </form>
        </div>
      </div>

      {/* Scroll to Bottom Button */}
      {!isNearBottom && (
        <div className="absolute bottom-20 right-4 z-20">
          <Button
            variant="secondary"
            size="icon"
            className="rounded-full shadow-lg relative h-10 w-10 sm:h-12 sm:w-12"
            onClick={scrollToBottom}
          >
            <ArrowDown size={20} />
            {unreadCount > 0 && (
              <div className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] rounded-full w-5 h-5 flex items-center justify-center font-bold">
                {unreadCount}
              </div>
            )}
          </Button>
        </div>
      )}

      {/* Delete Chat Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="w-[calc(100%-32px)] sm:max-w-[425px] rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить чат?</AlertDialogTitle>
            <AlertDialogDescription>
              Это действие нельзя отменить. Это навсегда удалит чат и все его сообщения.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-col sm:flex-row gap-2">
            <AlertDialogCancel className="mt-0">Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteChat} className="bg-red-500 hover:bg-red-600">
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Analytics Dialog */}
      <Dialog open={showAnalyticsDialog} onOpenChange={setShowAnalyticsDialog}>
        <DialogContent className="max-w-2xl w-[calc(100%-32px)] sm:w-full max-h-[85vh] overflow-y-auto p-0 border-none shadow-2xl rounded-2xl">
          <div className="sticky top-0 z-10 bg-white border-b border-gray-100 px-4 sm:px-6 py-4 sm:py-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3 sm:gap-4">
                <div className="h-10 w-10 sm:h-12 sm:w-12 bg-blue-50 rounded-xl sm:rounded-2xl flex items-center justify-center text-blue-600 shadow-sm flex-shrink-0">
                  <BarChart3 size={20} />
                </div>
                <div className="min-w-0">
                  <h2 className="text-lg sm:text-xl font-bold text-gray-900 leading-tight truncate">Анализ диалога</h2>
                  <p className="text-gray-500 text-[10px] font-medium uppercase tracking-wider mt-0.5">
                    {analytics && !isNaN(new Date(analytics.created_at).getTime()) ? (
                      new Date(analytics.created_at).toLocaleString('ru-RU', {
                        day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit'
                      })
                    ) : 'Дата не определена'}
                  </p>
                </div>
              </div>
              {analytics?.manager_quality_score !== undefined && (
                <div className="flex items-center gap-3 bg-gray-50 px-3 py-1.5 sm:px-4 sm:py-2 rounded-xl sm:rounded-2xl border border-gray-100">
                  <div className="text-right">
                    <p className="text-[8px] sm:text-[10px] text-gray-400 uppercase font-bold leading-none mb-1">Качество</p>
                    <p className="text-xl sm:text-2xl font-black text-gray-900 leading-none">
                      {analytics.manager_quality_score}<span className="text-xs sm:text-sm font-normal text-gray-400 ml-0.5">/10</span>
                    </p>
                  </div>
                  <div className={`h-8 w-8 sm:h-10 sm:w-10 rounded-lg sm:rounded-xl flex items-center justify-center ${
                    analytics.manager_quality_score >= 7 ? 'bg-emerald-100 text-emerald-600' :
                    analytics.manager_quality_score >= 4 ? 'bg-amber-100 text-amber-600' : 'bg-red-100 text-red-600'
                  }`}>
                    <TrendingUp size={16} />
                  </div>
                </div>
              )}
            </div>
          </div>
          
          <div className="p-4 sm:p-6 space-y-6 bg-gray-50/30">
            {analytics ? (
              <div className="grid gap-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {analytics.customer_sentiment && (
                    <div className="bg-white p-4 rounded-xl sm:rounded-2xl border border-gray-100 shadow-sm">
                      <div className="flex items-center gap-2 mb-3">
                        <MessageSquare size={14} className="text-gray-400" />
                        <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Тональность</h3>
                      </div>
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold ${
                        analytics.customer_sentiment === 'positive' ? 'bg-emerald-50 text-emerald-700' :
                        analytics.customer_sentiment === 'negative' ? 'bg-red-50 text-red-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {analytics.customer_sentiment === 'positive' ? 'Позитивная' :
                         analytics.customer_sentiment === 'negative' ? 'Негативная' : 'Нейтральная'}
                      </div>
                    </div>
                  )}
                  {analytics.resolution_status && (
                    <div className="bg-white p-4 rounded-xl sm:rounded-2xl border border-gray-100 shadow-sm">
                      <div className="flex items-center gap-2 mb-3">
                        <Target size={14} className="text-gray-400" />
                        <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Статус решения</h3>
                      </div>
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold ${
                        analytics.resolution_status === 'resolved' ? 'bg-emerald-50 text-emerald-700' :
                        analytics.resolution_status === 'pending' ? 'bg-amber-50 text-amber-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {analytics.resolution_status === 'resolved' ? 'Проблема решена' :
                         analytics.resolution_status === 'pending' ? 'В процессе' : analytics.resolution_status}
                      </div>
                    </div>
                  )}
                </div>
                <div className="space-y-4">
                  {analytics.summary && (
                    <div className="bg-white p-4 sm:p-5 rounded-xl sm:rounded-2xl border border-gray-100 shadow-sm">
                      <h3 className="text-[10px] sm:text-xs font-bold text-gray-900 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <div className="w-1 h-3 bg-blue-500 rounded-full"></div>
                        Суть диалога
                      </h3>
                      <p className="text-gray-600 text-xs sm:text-sm leading-relaxed">{analytics.summary}</p>
                    </div>
                  )}
                  {analytics.recommendations && (
                    <div className="bg-emerald-50/50 p-4 sm:p-5 rounded-xl sm:rounded-2xl border border-emerald-100 shadow-sm">
                      <h3 className="text-[10px] sm:text-xs font-bold text-emerald-700 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <Lightbulb size={14} />
                        Рекомендации
                      </h3>
                      <p className="text-gray-700 text-xs sm:text-sm leading-relaxed font-medium">{analytics.recommendations}</p>
                    </div>
                  )}
                  {analytics.key_topics && analytics.key_topics.length > 0 && (
                    <div className="pt-2">
                      <div className="flex flex-wrap gap-2">
                        {analytics.key_topics.map((topic, i) => (
                          <span key={i} className="px-2 py-1 bg-white border border-gray-200 text-gray-600 rounded-lg text-[10px] font-bold shadow-sm">
                            #{topic}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="py-12 text-center">
                <div className="w-16 h-16 mx-auto mb-6 bg-gray-100 rounded-2xl flex items-center justify-center text-gray-300">
                  <BarChart3 size={28} />
                </div>
                <h3 className="text-base font-bold text-gray-900 mb-2">Анализ не найден</h3>
                <p className="text-gray-500 text-xs max-w-xs mx-auto">Нажмите «Закончить диалог» чтобы ИИ подготовил отчет.</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

interface MessageBubbleProps {
  message: Message;
  formatTime: (timestamp: string) => string;
  onDelete: (messageId: number) => void;
}

const MessageBubble = ({ message, formatTime, onDelete }: MessageBubbleProps) => {
  const isQuestion = message.message_type === 'question';
  const imageRef = useRef<HTMLImageElement>(null);
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleWheel = (e: React.WheelEvent<HTMLImageElement>) => {
    e.preventDefault();
    setZoom((z) => Math.max(0.5, Math.min(5, z - e.deltaY * 0.001)));
  };
  const handleMouseDown = (e: React.MouseEvent<HTMLImageElement>) => {
    setDragging(true);
    setStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!dragging || !start) return;
    setOffset({ x: e.clientX - start.x, y: e.clientY - start.y });
  };
  const handleMouseUp = () => setDragging(false);
  const handleDialogOpenChange = (o: boolean) => {
    setOpen(o);
    if (!o) { setZoom(1); setOffset({ x: 0, y: 0 }); setDragging(false); setStart(null); }
  };

  return (
    <div className={`mb-4 flex ${isQuestion ? 'justify-start' : 'justify-end'} group`}>
      <div className={`max-w-[80%] rounded-lg px-4 py-2 relative ${
        isQuestion ? 'bg-gray-200 text-gray-800' : 'bg-[#1F1F1F] text-white'
      }`}>
        <button
          onClick={() => setShowDeleteConfirm(true)}
          className={`absolute -top-2 ${isQuestion ? '-right-2' : '-left-2'} w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600 shadow-md z-10`}
        >
          <X size={12} />
        </button>
        <div className="mb-1 flex items-center">
          {message.ai && (
            <div className="mr-1 text-xs px-1 py-0.5 bg-white/20 rounded">ИИ</div>
          )}
        </div>
        {message.is_image ? (
          <div className="flex flex-col gap-2">
            <Dialog open={open} onOpenChange={handleDialogOpenChange}>
              <DialogTrigger asChild>
                <img
                  ref={imageRef}
                  src={message.message.split('|')[0]}
                  alt="Image"
                  className="max-w-full rounded-lg cursor-zoom-in"
                  style={{ maxHeight: '300px' }}
                  onClick={() => setOpen(true)}
                />
              </DialogTrigger>
              <DialogContent className="flex items-center justify-center bg-black">
                <div
                  style={{
                    overflow: 'hidden', width: '100%', height: '80vh',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: 'black', cursor: dragging ? 'grabbing' : 'grab',
                  }}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                >
                  <img
                    src={message.message.split('|')[0]}
                    alt="Zoomed image"
                    style={{
                      transform: `scale(${zoom}) translate(${offset.x / zoom}px, ${offset.y / zoom}px)`,
                      transition: dragging ? 'none' : 'transform 0.2s',
                      maxWidth: '100%', maxHeight: '80vh', userSelect: 'none', pointerEvents: 'auto',
                    }}
                    onWheel={handleWheel}
                    onMouseDown={handleMouseDown}
                    draggable={false}
                  />
                </div>
              </DialogContent>
            </Dialog>
            {message.message.includes('|') && (
              <p className="whitespace-pre-wrap break-words text-sm">{message.message.split('|')[1]}</p>
            )}
          </div>
        ) : (
          <p className="whitespace-pre-wrap break-words">{message.message}</p>
        )}
        <div className="text-right mt-1">
          <span className={`text-xs ${isQuestion ? 'text-gray-500' : 'text-gray-300'}`}>
            {formatTime(message.created_at)}
          </span>
        </div>
      </div>

      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent className="w-[calc(100%-32px)] sm:max-w-[425px] rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить сообщение?</AlertDialogTitle>
            <AlertDialogDescription>Это действие нельзя отменить.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-col sm:flex-row gap-2">
            <AlertDialogCancel className="mt-0">Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={() => onDelete(message.id)} className="bg-red-500 hover:bg-red-600">Удалить</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default TestChatView;
