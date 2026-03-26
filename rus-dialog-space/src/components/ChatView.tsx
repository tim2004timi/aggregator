import { useState, useEffect, useRef, useCallback } from 'react';
import { Message, Chat, getChatMessages, sendMessage as apiSendMessage, toggleAiChat, markChatAsRead, deleteChat, API_URL, fetchWithTokenRefresh, syncVkChat, analyzeChat, getChatAnalytics, DialogAnalytics, assignChat, getCurrentUser, User, deleteMessage as apiDeleteMessage, editMessage as apiEditMessage } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Send, Trash2, Paperclip, ArrowDown, RotateCw, BarChart3, TrendingUp, MessageSquare, Target, Lightbulb, MoreVertical, FileText, StickyNote, Smile, Star, Pencil, X, Check, Mic, Video, Square, Play, Pause, Download } from 'lucide-react';
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
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import data from '@emoji-mart/data';
import Picker from '@emoji-mart/react';

interface ChatViewProps {
  chatId: number | null;
  onChatDeleted?: () => void;
}

const ChatView = ({ chatId, onChatDeleted }: ChatViewProps) => {
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
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser).catch(console.error);
  }, []);

  const [isRecordingVoice, setIsRecordingVoice] = useState(false);
  const [voiceRecordingTime, setVoiceRecordingTime] = useState(0);
  const [isRecordingVideo, setIsRecordingVideo] = useState(false);
  const [videoRecordingTime, setVideoRecordingTime] = useState(0);
  const [showVideoRecorder, setShowVideoRecorder] = useState(false);
  const voiceRecorderRef = useRef<MediaRecorder | null>(null);
  const voiceChunksRef = useRef<Blob[]>([]);
  const voiceTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const voiceTimeRef = useRef(0);
  const videoRecorderRef = useRef<MediaRecorder | null>(null);
  const videoChunksRef = useRef<Blob[]>([]);
  const videoTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const videoTimeRef = useRef(0);
  const videoPreviewRef = useRef<HTMLVideoElement>(null);
  const videoStreamRef = useRef<MediaStream | null>(null);

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
  } = useChat();

  const handleDeleteMessage = useCallback(async (messageId: number) => {
    try {
      await apiDeleteMessage(messageId);
      toast.success('Сообщение удалено');
    } catch {
      toast.error('Не удалось удалить сообщение');
    }
  }, []);

  const handleEditMessage = useCallback(async (messageId: number, newText: string) => {
    try {
      await apiEditMessage(messageId, newText);
      toast.success('Сообщение изменено');
    } catch {
      toast.error('Не удалось изменить сообщение');
    }
  }, []);

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

  useEffect(() => {
    if (chatId) {
      markChatAsReadFromContext(chatId);
    }
  }, [chatId, markChatAsReadFromContext]);

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
    } catch (error) {
      console.error('Failed to analyze chat:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleTakeChat = async () => {
    if (!chatId || !currentUser) return;
    try {
      const managerName = currentUser.name || currentUser.email;
      await assignChat(chatId, currentUser.id, managerName);
      
      // Disable AI when taking chat
      if (aiEnabled) {
        await toggleAiChat(chatId, false);
        setAiEnabled(false);
      }
      
      await fetchChatInfo();
      toast.success('Вы взяли чат в работу');
    } catch (error) {
      console.error('Failed to take chat:', error);
    }
  };

  const isAssignedToMe = currentUser && chatInfo?.assigned_manager_id === currentUser.id;
  const isUnassigned = !chatInfo?.assigned_manager_id;
  // const canWrite = isAssignedToMe;
  const canWrite = true; // Allow writing for everyone for now as "Take Chat" is disabled

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

  const uploadImage = useCallback(async (file: File) => {
    if (!selectedChat) return;
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
        const errorText = await response.text();
        console.error('Image upload error:', errorText);
        throw new Error(`Failed to upload image: ${response.status} ${response.statusText}`);
      }

      await response.json();
      setNewMessage('');
      toast.success('Изображение отправлено');
    } catch (error) {
      console.error('Error uploading image:', error);
      toast.error('Не удалось отправить изображение');
    }
  }, [selectedChat]);

  const uploadFile = useCallback(async (file: File) => {
    if (!selectedChat) return;
    if (file.size > 20 * 1024 * 1024) {
      toast.error('Файл слишком большой (макс. 20 МБ)');
      return;
    }
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('chat_id', selectedChat.id.toString());

      const response = await fetchWithTokenRefresh(`${API_URL}/messages/file`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const detail = errorData?.detail || 'Не удалось отправить файл';
        toast.error(detail);
        return;
      }

      await response.json();
      toast.success('Файл отправлен');
    } catch (error) {
      console.error('Error uploading file:', error);
      toast.error('Не удалось отправить файл');
    }
  }, [selectedChat]);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.type.startsWith('image/')) {
      await uploadImage(file);
    } else {
      await uploadFile(file);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) uploadImage(file);
        return;
      }
    }
  }, [uploadImage]);

  const uploadVoice = useCallback(async (blob: Blob, duration: number) => {
    if (!selectedChat) return;
    try {
      const formData = new FormData();
      formData.append('voice', blob, 'voice.webm');
      formData.append('chat_id', selectedChat.id.toString());
      formData.append('duration', Math.round(duration).toString());

      const response = await fetchWithTokenRefresh(`${API_URL}/messages/voice`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Failed to upload voice');
      toast.success('Голосовое сообщение отправлено');
    } catch (error) {
      console.error('Error uploading voice:', error);
      toast.error('Не удалось отправить голосовое сообщение');
    }
  }, [selectedChat]);

  const uploadVideoNote = useCallback(async (blob: Blob, duration: number) => {
    if (!selectedChat) return;
    try {
      const formData = new FormData();
      formData.append('video', blob, 'video.webm');
      formData.append('chat_id', selectedChat.id.toString());
      formData.append('duration', Math.round(duration).toString());

      const response = await fetchWithTokenRefresh(`${API_URL}/messages/video_note`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Failed to upload video note');
      toast.success('Видеосообщение отправлено');
    } catch (error) {
      console.error('Error uploading video note:', error);
      toast.error('Не удалось отправить видеосообщение');
    }
  }, [selectedChat]);

  const startVoiceRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm'
      });
      voiceChunksRef.current = [];
      voiceTimeRef.current = 0;
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) voiceChunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(voiceChunksRef.current, { type: 'audio/webm' });
        if (blob.size > 0) {
          uploadVoice(blob, voiceTimeRef.current);
        }
        setVoiceRecordingTime(0);
        voiceTimeRef.current = 0;
      };
      recorder.start(100);
      voiceRecorderRef.current = recorder;
      setIsRecordingVoice(true);
      setVoiceRecordingTime(0);
      voiceTimerRef.current = setInterval(() => {
        voiceTimeRef.current += 1;
        setVoiceRecordingTime(prev => prev + 1);
      }, 1000);
    } catch {
      toast.error('Нет доступа к микрофону');
    }
  }, [uploadVoice]);

  const stopVoiceRecording = useCallback(() => {
    if (voiceRecorderRef.current && voiceRecorderRef.current.state !== 'inactive') {
      voiceRecorderRef.current.stop();
    }
    if (voiceTimerRef.current) {
      clearInterval(voiceTimerRef.current);
      voiceTimerRef.current = null;
    }
    setIsRecordingVoice(false);
  }, []);

  const cancelVoiceRecording = useCallback(() => {
    if (voiceRecorderRef.current && voiceRecorderRef.current.state !== 'inactive') {
      voiceRecorderRef.current.ondataavailable = null;
      voiceRecorderRef.current.onstop = () => {
        voiceRecorderRef.current?.stream.getTracks().forEach(t => t.stop());
      };
      voiceRecorderRef.current.stop();
    }
    if (voiceTimerRef.current) {
      clearInterval(voiceTimerRef.current);
      voiceTimerRef.current = null;
    }
    voiceChunksRef.current = [];
    setIsRecordingVoice(false);
    setVoiceRecordingTime(0);
  }, []);

  const startVideoRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 384, height: 384, facingMode: 'user' },
        audio: true
      });
      videoStreamRef.current = stream;
      setShowVideoRecorder(true);

      setTimeout(() => {
        if (videoPreviewRef.current) {
          videoPreviewRef.current.srcObject = stream;
        }
      }, 100);
    } catch {
      toast.error('Нет доступа к камере');
    }
  }, []);

  const beginVideoCapture = useCallback(() => {
    if (!videoStreamRef.current) return;
    const recorder = new MediaRecorder(videoStreamRef.current, {
      mimeType: MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')
        ? 'video/webm;codecs=vp9,opus'
        : 'video/webm'
    });
    videoChunksRef.current = [];
    videoTimeRef.current = 0;
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) videoChunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(videoChunksRef.current, { type: 'video/webm' });
      if (blob.size > 0) {
        uploadVideoNote(blob, videoTimeRef.current);
      }
      stopVideoStream();
    };
    recorder.start(100);
    videoRecorderRef.current = recorder;
    setIsRecordingVideo(true);
    setVideoRecordingTime(0);
    videoTimerRef.current = setInterval(() => {
      videoTimeRef.current += 1;
      setVideoRecordingTime(prev => prev + 1);
    }, 1000);
  }, [uploadVideoNote, stopVideoStream]);

  const stopVideoRecording = useCallback(() => {
    if (videoRecorderRef.current && videoRecorderRef.current.state !== 'inactive') {
      videoRecorderRef.current.stop();
    }
    if (videoTimerRef.current) {
      clearInterval(videoTimerRef.current);
      videoTimerRef.current = null;
    }
    setIsRecordingVideo(false);
  }, []);

  const stopVideoStream = useCallback(() => {
    videoStreamRef.current?.getTracks().forEach(t => t.stop());
    videoStreamRef.current = null;
    setShowVideoRecorder(false);
    setIsRecordingVideo(false);
    setVideoRecordingTime(0);
    if (videoTimerRef.current) {
      clearInterval(videoTimerRef.current);
      videoTimerRef.current = null;
    }
  }, []);

  const cancelVideoRecording = useCallback(() => {
    if (videoRecorderRef.current && videoRecorderRef.current.state !== 'inactive') {
      videoRecorderRef.current.ondataavailable = null;
      videoRecorderRef.current.onstop = () => {};
      videoRecorderRef.current.stop();
    }
    videoChunksRef.current = [];
    stopVideoStream();
  }, [stopVideoStream]);

  useEffect(() => {
    return () => {
      if (voiceTimerRef.current) clearInterval(voiceTimerRef.current);
      if (videoTimerRef.current) clearInterval(videoTimerRef.current);
      videoStreamRef.current?.getTracks().forEach(t => t.stop());
    };
  }, []);

  const formatRecordingTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
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
    <div className="h-full flex flex-col bg-white overflow-hidden relative">
      {/* Chat Header */}
      <div className="border-b border-gray-300 py-2 px-4 flex items-center justify-between h-14 flex-shrink-0 bg-white z-10">
        <div className="flex items-center gap-2 flex-grow min-w-0">
          <h2 className="text-base sm:text-lg font-medium text-gray-800 truncate">
            {chatInfo?.name || 'Чат'}
          </h2>
          <span className="text-[10px] sm:text-xs text-gray-400 flex-shrink-0">
            №{chatInfo?.id ?? chatId}
          </span>
          {!isMobile && chatInfo && (
            <ChatTags
              chatId={chatInfo.id}
              tags={chatInfo.tags || []}
              onTagsUpdate={(newTags) => {
                setChatInfo(prev => prev ? { ...prev, tags: newTags } : null);
              }}
            />
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
                  <RotateCw 
                    size={16} 
                    className={isSyncing ? 'animate-spin' : ''}
                  />
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="text-gray-700 border-gray-200 hover:bg-gray-50 h-8"
                onClick={handleEndDialog}
                disabled={isAnalyzing}
              >
                Закончить диалог
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className={`hover:bg-blue-50 h-8 w-8 ${analytics ? 'text-blue-500' : 'text-gray-400 cursor-not-allowed'}`}
                onClick={analytics ? () => setShowAnalyticsDialog(true) : undefined}
                disabled={!analytics}
                title={analytics ? 'Посмотреть анализ' : 'Анализ появится после завершения диалога'}
              >
                <BarChart3 
                  size={16} 
                  className={isAnalyzing ? 'animate-pulse' : ''}
                />
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
                  <DropdownMenuItem onClick={handleEndDialog} disabled={isAnalyzing}>
                    <TrendingUp size={16} className="mr-2" />
                    Закончить диалог
                  </DropdownMenuItem>
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
      
      {/* Messages Area */}
      <div 
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4 scrolling-touch relative"
        onScroll={checkScrollPosition}
      >
        {/* Take Chat Overlay */}
        {/* {!canWrite && isUnassigned && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/50 backdrop-blur-[1px]">
            <Button 
              onClick={handleTakeChat}
              className="bg-black text-white hover:bg-gray-800 text-sm font-bold uppercase tracking-wider px-8 py-6 rounded-2xl shadow-xl transform transition-all hover:scale-105"
            >
              Взять чат
            </Button>
          </div>
        )} */}

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
                  onDelete={handleDeleteMessage}
                  onEdit={handleEditMessage}
                />
              ))}
            <div ref={messagesEndRef} className="h-1" />
          </div>
        )}
      </div>

      {/* Video Recorder Overlay */}
      {showVideoRecorder && (
        <div className="absolute inset-0 z-30 bg-black/80 flex flex-col items-center justify-center">
          <div className="relative">
            <video
              ref={videoPreviewRef}
              autoPlay
              muted
              playsInline
              className="w-64 h-64 sm:w-80 sm:h-80 rounded-full object-cover border-4 border-white/20"
              style={{ transform: 'scaleX(-1)' }}
            />
            {isRecordingVideo && (
              <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-red-500 text-white text-sm font-mono px-3 py-1 rounded-full flex items-center gap-2">
                <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                {formatRecordingTime(videoRecordingTime)}
              </div>
            )}
          </div>
          <div className="mt-6 flex items-center gap-4">
            <button
              type="button"
              className="h-12 w-12 rounded-full bg-white/20 text-white hover:bg-white/30 flex items-center justify-center transition-colors"
              onClick={cancelVideoRecording}
            >
              <X size={24} />
            </button>
            {!isRecordingVideo ? (
              <button
                type="button"
                className="h-16 w-16 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors border-4 border-white/30"
                onClick={beginVideoCapture}
              >
                <div className="w-6 h-6 rounded-full bg-white" />
              </button>
            ) : (
              <button
                type="button"
                className="h-16 w-16 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors border-4 border-white/30"
                onClick={stopVideoRecording}
              >
                <Square size={24} fill="white" />
              </button>
            )}
            <div className="h-12 w-12" />
          </div>
        </div>
      )}

      {/* Message Input Area */}
      <div className="border-t border-gray-200 bg-white flex-shrink-0 pb-[safe-area-inset-bottom]">
        <div className="p-3 sm:p-4">
          {isRecordingVoice ? (
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="text-red-500 hover:text-red-600 transition-colors p-2 h-10 w-10 flex items-center justify-center"
                onClick={cancelVoiceRecording}
              >
                <X size={20} />
              </button>
              <div className="flex-1 flex items-center gap-3 bg-red-50 rounded-xl px-4 py-2">
                <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                <span className="text-red-600 font-mono text-sm">
                  {formatRecordingTime(voiceRecordingTime)}
                </span>
                <div className="flex-1 flex items-center gap-0.5">
                  {Array.from({ length: 20 }).map((_, i) => (
                    <div
                      key={i}
                      className="w-1 bg-red-300 rounded-full animate-pulse"
                      style={{
                        height: `${8 + Math.random() * 16}px`,
                        animationDelay: `${i * 0.05}s`
                      }}
                    />
                  ))}
                </div>
              </div>
              <Button
                type="button"
                size="icon"
                className="h-10 w-10 bg-red-500 text-white rounded-full hover:bg-red-600 flex-shrink-0"
                onClick={stopVoiceRecording}
              >
                <Send size={18} />
              </Button>
            </div>
          ) : (
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
                    accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.rtf,.odt,.ods,.odp,.zip,.rar,.7z,.tar,.gz,.mp3,.wav,.ogg,.flac,.aac,.mp4,.mov,.avi,.mkv,.webm,.json,.xml,.html,.css,.md"
                    onChange={handleFileSelect}
                />
                
                <div className="relative flex-1">
                    <Input
                        type="text"
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        onPaste={handlePaste}
                        placeholder="Написать сообщение..."
                        className="w-full min-h-[40px] py-2 pl-4 pr-4 bg-gray-50 border-gray-200 rounded-xl focus:bg-white transition-colors"
                        disabled={!canWrite}
                    />
                </div>

                <Popover open={showEmojiPicker} onOpenChange={setShowEmojiPicker}>
                    <PopoverTrigger asChild>
                        <button
                            type="button"
                            className="text-gray-400 hover:text-gray-600 transition-colors p-2 h-10 w-10 flex items-center justify-center"
                            disabled={!canWrite}
                        >
                            <Smile size={20} />
                        </button>
                    </PopoverTrigger>
                    <PopoverContent side="top" align="end" className="w-auto p-0 border-none shadow-xl">
                        <Picker
                            data={data}
                            onEmojiSelect={(emoji: { native: string }) => {
                                setNewMessage(prev => prev + emoji.native);
                                setShowEmojiPicker(false);
                            }}
                            locale="ru"
                            theme="light"
                            previewPosition="none"
                            skinTonePosition="none"
                        />
                    </PopoverContent>
                </Popover>

                {!newMessage.trim() ? (
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      className="text-gray-400 hover:text-gray-600 transition-colors p-2 h-10 w-10 flex items-center justify-center"
                      onClick={startVoiceRecording}
                      disabled={!canWrite}
                      title="Голосовое сообщение"
                    >
                      <Mic size={20} />
                    </button>
                    <button
                      type="button"
                      className="text-gray-400 hover:text-gray-600 transition-colors p-2 h-10 w-10 flex items-center justify-center"
                      onClick={startVideoRecording}
                      disabled={!canWrite}
                      title="Видеосообщение (кружок)"
                    >
                      <Video size={20} />
                    </button>
                  </div>
                ) : (
                  <Button
                      type="submit"
                      size="icon"
                      disabled={!newMessage.trim() || !canWrite}
                      className="h-10 w-10 bg-black text-white rounded-full hover:bg-gray-800 flex-shrink-0"
                  >
                      <Send size={18} />
                  </Button>
                )}
            </form>
          )}
        </div>
        
        {/* Navigation Island */}
        {/* <div className="border-t border-gray-100 py-3 flex justify-center gap-8">
            {[1, 2, 3, 4, 5].map((i) => (
                <button key={i} className="text-gray-300 hover:text-gray-500 transition-colors">
                    <Star size={20} />
                </button>
            ))}
        </div> */}
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
            <AlertDialogAction
              onClick={handleDeleteChat}
              className="bg-red-500 hover:bg-red-600"
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Analytics Dialog */}
      <Dialog open={showAnalyticsDialog} onOpenChange={setShowAnalyticsDialog}>
        <DialogContent className="max-w-2xl w-[calc(100%-32px)] sm:w-full max-h-[85vh] overflow-y-auto p-0 border-none shadow-2xl rounded-2xl">
          {/* Header */}
          <div className="sticky top-0 z-10 bg-white border-b border-gray-100 px-4 sm:px-6 py-4 sm:py-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3 sm:gap-4">
                <div className="h-10 w-10 sm:h-12 sm:w-12 bg-blue-50 rounded-xl sm:rounded-2xl flex items-center justify-center text-blue-600 shadow-sm flex-shrink-0">
                  <BarChart3 size={20} className="sm:size-24" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-lg sm:text-xl font-bold text-gray-900 leading-tight truncate">Анализ диалога</h2>
                  <p className="text-gray-500 text-[10px] font-medium uppercase tracking-wider mt-0.5">
                    {analytics && !isNaN(new Date(analytics.created_at).getTime()) ? (
                      new Date(analytics.created_at).toLocaleString('ru-RU', {
                        day: 'numeric',
                        month: 'long',
                        hour: '2-digit',
                        minute: '2-digit'
                      })
                    ) : 'Дата не определена'}
                  </p>
                </div>
              </div>
              {analytics?.manager_quality_score !== undefined && (
                <div className="flex items-center gap-3 bg-gray-50 px-3 py-1.5 sm:px-4 sm:py-2 rounded-xl sm:rounded-2xl border border-gray-100 self-start sm:self-auto">
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
                    <TrendingUp size={16} className="sm:size-20" />
                  </div>
                </div>
              )}
            </div>
          </div>
          
          <div className="p-4 sm:p-6 space-y-6 bg-gray-50/30">
            {analytics ? (
              <div className="grid gap-6">
                {/* Fact Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {analytics.customer_sentiment && (
                    <div className="bg-white p-4 rounded-xl sm:rounded-2xl border border-gray-100 shadow-sm">
                      <div className="flex items-center gap-2 mb-3">
                        <MessageSquare size={14} className="text-gray-400" />
                        <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Тональность</h3>
                      </div>
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg sm:rounded-xl text-xs sm:text-sm font-bold ${
                        analytics.customer_sentiment === 'positive' ? 'bg-emerald-50 text-emerald-700' :
                        analytics.customer_sentiment === 'negative' ? 'bg-red-50 text-red-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {analytics.customer_sentiment === 'positive' ? '😊 Позитивная' :
                         analytics.customer_sentiment === 'negative' ? '😞 Негативная' : '😐 Нейтральная'}
                      </div>
                    </div>
                  )}

                  {analytics.resolution_status && (
                    <div className="bg-white p-4 rounded-xl sm:rounded-2xl border border-gray-100 shadow-sm">
                      <div className="flex items-center gap-2 mb-3">
                        <Target size={14} className="text-gray-400" />
                        <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Статус решения</h3>
                      </div>
                      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg sm:rounded-xl text-xs sm:text-sm font-bold ${
                        analytics.resolution_status === 'resolved' ? 'bg-emerald-50 text-emerald-700' :
                        analytics.resolution_status === 'pending' ? 'bg-amber-50 text-amber-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {analytics.resolution_status === 'resolved' ? '✓ Проблема решена' :
                         analytics.resolution_status === 'pending' ? '⏳ В процессе' : analytics.resolution_status}
                      </div>
                    </div>
                  )}
                </div>

                {/* Content Blocks */}
                <div className="space-y-4">
                  {analytics.summary && (
                    <div className="bg-white p-4 sm:p-5 rounded-xl sm:rounded-2xl border border-gray-100 shadow-sm">
                      <h3 className="text-[10px] sm:text-xs font-bold text-gray-900 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <div className="w-1 h-3 sm:w-1.5 sm:h-4 bg-blue-500 rounded-full"></div>
                        Суть диалога
                      </h3>
                      <p className="text-gray-600 text-xs sm:text-sm leading-relaxed">{analytics.summary}</p>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {analytics.customer_problem && (
                      <div className="bg-white p-4 sm:p-5 rounded-xl sm:rounded-2xl border border-red-50 shadow-sm">
                        <h3 className="text-[10px] sm:text-xs font-bold text-red-600 uppercase tracking-wider mb-3">Проблема</h3>
                        <p className="text-gray-600 text-xs sm:text-sm leading-relaxed">{analytics.customer_problem}</p>
                      </div>
                    )}

                    {analytics.customer_intent && (
                      <div className="bg-white p-4 sm:p-5 rounded-xl sm:rounded-2xl border border-blue-50 shadow-sm">
                        <h3 className="text-[10px] sm:text-xs font-bold text-blue-600 uppercase tracking-wider mb-3">Намерение</h3>
                        <p className="text-gray-600 text-xs sm:text-sm leading-relaxed">{analytics.customer_intent}</p>
                      </div>
                    )}
                  </div>

                  {analytics.manager_quality_notes && (
                    <div className="bg-white p-4 sm:p-5 rounded-xl sm:rounded-2xl border border-gray-100 shadow-sm">
                      <h3 className="text-[10px] sm:text-xs font-bold text-gray-900 uppercase tracking-wider mb-3">Работа менеджера</h3>
                      <p className="text-gray-600 text-xs sm:text-sm leading-relaxed italic">"{analytics.manager_quality_notes}"</p>
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
                          <span 
                            key={i} 
                            className="px-2 py-1 bg-white border border-gray-200 text-gray-600 rounded-lg text-[10px] font-bold shadow-sm"
                          >
                            #{topic}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="py-12 sm:py-16 text-center">
                <div className="w-16 h-16 sm:w-20 sm:h-20 mx-auto mb-6 bg-gray-100 rounded-2xl sm:rounded-3xl flex items-center justify-center text-gray-300">
                  <BarChart3 size={28} className="sm:size-32" />
                </div>
                <h3 className="text-base sm:text-lg font-bold text-gray-900 mb-2">Анализ не найден</h3>
                <p className="text-gray-500 text-xs sm:text-sm max-w-xs mx-auto">Нажмите «Закончить диалог» в шапке чата, чтобы ИИ подготовил отчет по этому диалогу.</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const VoicePlayer = ({ src, duration, isQuestion }: { src: string; duration?: number | null; isQuestion: boolean }) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [totalDuration, setTotalDuration] = useState(duration || 0);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setPlaying(!playing);
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current && audioRef.current.duration && isFinite(audioRef.current.duration)) {
      setTotalDuration(audioRef.current.duration);
    }
  };

  const handleEnded = () => setPlaying(false);

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current || !totalDuration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    audioRef.current.currentTime = ratio * totalDuration;
  };

  const progress = totalDuration > 0 ? (currentTime / totalDuration) * 100 : 0;

  return (
    <div className="flex items-center gap-2 min-w-[200px]">
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        preload="metadata"
      />
      <button
        type="button"
        onClick={togglePlay}
        className={`h-9 w-9 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
          isQuestion ? 'bg-gray-400 hover:bg-gray-500 text-white' : 'bg-white/20 hover:bg-white/30 text-white'
        }`}
      >
        {playing ? <Pause size={16} /> : <Play size={16} className="ml-0.5" />}
      </button>
      <div className="flex-1 flex flex-col gap-1">
        <div
          className="h-1.5 rounded-full cursor-pointer relative overflow-hidden"
          style={{ backgroundColor: isQuestion ? 'rgba(0,0,0,0.15)' : 'rgba(255,255,255,0.2)' }}
          onClick={handleSeek}
        >
          <div
            className="absolute inset-y-0 left-0 rounded-full transition-[width]"
            style={{
              width: `${progress}%`,
              backgroundColor: isQuestion ? '#374151' : '#ffffff'
            }}
          />
        </div>
        <span className={`text-[10px] font-mono ${isQuestion ? 'text-gray-500' : 'text-gray-300'}`}>
          {formatTime(currentTime)} / {formatTime(totalDuration)}
        </span>
      </div>
    </div>
  );
};

const VideoNotePlayer = ({ src }: { src: string }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (playing) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setPlaying(!playing);
  };

  return (
    <div className="relative cursor-pointer group/video" onClick={togglePlay}>
      <video
        ref={videoRef}
        src={src}
        className="w-48 h-48 sm:w-56 sm:h-56 rounded-full object-cover"
        playsInline
        onEnded={() => setPlaying(false)}
        preload="metadata"
      />
      {!playing && (
        <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/20 group-hover/video:bg-black/30 transition-colors">
          <div className="h-12 w-12 rounded-full bg-white/80 flex items-center justify-center">
            <Play size={24} className="text-gray-800 ml-1" />
          </div>
        </div>
      )}
    </div>
  );
};

const FILE_ICON_COLORS: Record<string, string> = {
  pdf: 'bg-red-100 text-red-600',
  doc: 'bg-blue-100 text-blue-600',
  docx: 'bg-blue-100 text-blue-600',
  xls: 'bg-green-100 text-green-600',
  xlsx: 'bg-green-100 text-green-600',
  ppt: 'bg-orange-100 text-orange-600',
  pptx: 'bg-orange-100 text-orange-600',
  zip: 'bg-yellow-100 text-yellow-700',
  rar: 'bg-yellow-100 text-yellow-700',
  '7z': 'bg-yellow-100 text-yellow-700',
  txt: 'bg-gray-100 text-gray-600',
  csv: 'bg-green-100 text-green-700',
};

const FileAttachment = ({
  src,
  fileName,
  fileSize,
  isQuestion,
}: {
  src: string;
  fileName?: string | null;
  fileSize?: number | null;
  isQuestion: boolean;
}) => {
  const name = fileName || 'Файл';
  const ext = name.split('.').pop()?.toLowerCase() || '';
  const iconColor = FILE_ICON_COLORS[ext] || 'bg-gray-100 text-gray-500';

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  };

  return (
    <a
      href={src}
      target="_blank"
      rel="noopener noreferrer"
      download={name}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors min-w-[200px] ${
        isQuestion
          ? 'bg-gray-200/60 hover:bg-gray-200'
          : 'bg-white/10 hover:bg-white/20'
      }`}
    >
      <div className={`h-10 w-10 rounded-lg flex items-center justify-center flex-shrink-0 ${iconColor}`}>
        <FileText size={20} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium truncate ${isQuestion ? 'text-gray-800' : 'text-white'}`}>
          {name}
        </p>
        <div className="flex items-center gap-2">
          {fileSize != null && (
            <span className={`text-xs ${isQuestion ? 'text-gray-500' : 'text-gray-300'}`}>
              {formatSize(fileSize)}
            </span>
          )}
          <span className={`text-xs uppercase ${isQuestion ? 'text-gray-400' : 'text-gray-400'}`}>
            {ext}
          </span>
        </div>
      </div>
      <Download size={16} className={`flex-shrink-0 ${isQuestion ? 'text-gray-400' : 'text-gray-300'}`} />
    </a>
  );
};

interface MessageBubbleProps {
  message: Message;
  formatTime: (timestamp: string) => string;
  onDelete?: (messageId: number) => void;
  onEdit?: (messageId: number, newText: string) => void;
}

const MessageBubble = ({ message, formatTime, onDelete, onEdit }: MessageBubbleProps) => {
  const isQuestion = message.message_type === 'question';
  const isAnswer = message.message_type === 'answer';
  const imageRef = useRef<HTMLImageElement>(null);
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(message.message);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    if (message.is_image && imageRef.current) {
      imageRef.current.onload = () => {
        const messagesContainer = document.querySelector('.messages-container');
        if (messagesContainer) {
          messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
      };
    }
  }, [message.is_image]);

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

  const handleSaveEdit = () => {
    if (editText.trim() && editText !== message.message && onEdit) {
      onEdit(message.id, editText.trim());
    }
    setIsEditing(false);
  };

  const handleCancelEdit = () => {
    setEditText(message.message);
    setIsEditing(false);
  };

  const handleDeleteConfirm = () => {
    if (onDelete) onDelete(message.id);
    setShowDeleteConfirm(false);
  };

  return (
    <div className={`mb-4 flex ${isQuestion ? 'justify-start' : 'justify-end'} group`}>
      {/* Edit/delete buttons for answer text messages (on hover, left side) */}
      {isAnswer && !message.is_image && !message.media_type && !isEditing && (
        <div className="flex items-center gap-1 mr-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600"
            onClick={() => { setEditText(message.message); setIsEditing(true); }}
            title="Редактировать"
          >
            <Pencil size={14} />
          </button>
          <button
            type="button"
            className="p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500"
            onClick={() => setShowDeleteConfirm(true)}
            title="Удалить"
          >
            <Trash2 size={14} />
          </button>
        </div>
      )}
      {/* Delete-only button for answer media (images, voice, video, files) */}
      {isAnswer && (message.is_image || message.media_type) && (
        <div className="flex items-center gap-1 mr-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            className="p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500"
            onClick={() => setShowDeleteConfirm(true)}
            title="Удалить"
          >
            <Trash2 size={14} />
          </button>
        </div>
      )}

      <div className={`max-w-[80%] rounded-lg px-4 py-2 relative ${
        isQuestion ? 'bg-gray-300 text-gray-800' : 'bg-[#1F1F1F] text-white'
      }`}>
        <div className="mb-1 flex items-center">
          {message.ai && (
            <div className="mr-1 text-xs px-1 py-0.5 bg-white/20 rounded">
              ИИ
            </div>
          )}
        </div>
        {isEditing ? (
          <div className="flex flex-col gap-2">
            <textarea
              className="w-full p-2 rounded bg-white/10 text-white border border-white/20 text-sm resize-none focus:outline-none focus:border-white/40"
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSaveEdit(); }
                if (e.key === 'Escape') handleCancelEdit();
              }}
              rows={3}
              autoFocus
            />
            <div className="flex gap-1 justify-end">
              <button
                type="button"
                className="p-1 rounded hover:bg-white/20 text-gray-300 hover:text-white"
                onClick={handleCancelEdit}
              >
                <X size={16} />
              </button>
              <button
                type="button"
                className="p-1 rounded hover:bg-white/20 text-green-400 hover:text-green-300"
                onClick={handleSaveEdit}
              >
                <Check size={16} />
              </button>
            </div>
          </div>
        ) : message.media_type === 'voice' ? (
          <VoicePlayer src={message.message} duration={message.media_duration} isQuestion={isQuestion} />
        ) : message.media_type === 'video_note' ? (
          <VideoNotePlayer src={message.message} />
        ) : message.media_type === 'file' ? (
          <FileAttachment
            src={message.message}
            fileName={message.file_name}
            fileSize={message.file_size}
            isQuestion={isQuestion}
          />
        ) : message.is_image ? (
          <div className="flex flex-col gap-2">
            <Dialog open={open} onOpenChange={handleDialogOpenChange}>
              <DialogTrigger asChild>
                <img
                  ref={imageRef}
                  src={message.message.split('|')[0]}
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
                    src={message.message.split('|')[0]}
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
            {message.message.includes('|') && (
              <p className="whitespace-pre-wrap break-words text-sm">
                {message.message.split('|')[1]}
              </p>
            )}
          </div>
        ) : (
          <p className="whitespace-pre-wrap break-words">{message.message}</p>
        )}
        <div className="text-right mt-1 flex items-center justify-end gap-1">
          {message.edited_at && (
            <span className={`text-xs italic ${isQuestion ? 'text-gray-500' : 'text-gray-400'}`}>
              ред.
            </span>
          )}
          <span className={`text-xs ${isQuestion ? 'text-gray-500' : 'text-gray-300'}`}>
            {formatTime(message.created_at)}
          </span>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <AlertDialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <AlertDialogContent className="w-[calc(100%-32px)] sm:max-w-[360px] rounded-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить сообщение?</AlertDialogTitle>
            <AlertDialogDescription>
              Сообщение будет удалено из агрегатора и мессенджера (если возможно).
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-col sm:flex-row gap-2">
            <AlertDialogCancel className="mt-0">Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-red-500 hover:bg-red-600">
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ChatView;
