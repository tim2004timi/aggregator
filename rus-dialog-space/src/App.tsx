import React, { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { WebSocketProvider } from './contexts/WebSocketContext';
import { ChatProvider } from './contexts/ChatContext';
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import MessageBox from "./pages/MessageBox";

console.log('App module loaded');

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

const App = () => {
  console.log('App component rendering');

  useEffect(() => {
    // Логируем полный URL для отладки
    const fullUrl = window.location.href;
    const searchString = window.location.search;
    const hashString = window.location.hash;
    
    console.log('🔍 Полный URL:', fullUrl);
    console.log('🔍 Search строка:', searchString);
    console.log('🔍 Hash:', hashString);
    
    // Пробуем получить токен из query string
    let accessToken: string | null = null;
    
    if (searchString) {
      const params = new URLSearchParams(searchString);
      
      // Логируем все параметры для отладки
      const allParams = Array.from(params.entries());
      console.log('🔍 Все параметры из query string:', allParams);
      
      // Проверяем оба варианта параметра для обратной совместимости
      accessToken = params.get("access_token") || params.get("access");
    }
    
    // Если токен не найден в query string, пробуем извлечь из hash (на случай если он там)
    if (!accessToken && hashString) {
      const hashParams = new URLSearchParams(hashString.substring(1));
      console.log('🔍 Параметры из hash:', Array.from(hashParams.entries()));
      accessToken = hashParams.get("access_token") || hashParams.get("access");
    }
    
    // Альтернативный способ: парсим URL напрямую через регулярное выражение
    if (!accessToken) {
      const match = fullUrl.match(/[?&]access_token=([^&?#]+)/);
      if (match && match[1]) {
        accessToken = decodeURIComponent(match[1]);
        console.log('🔍 Токен найден через regex из полного URL');
      }
    }

    console.log('🔍 Проверка токена в URL:', {
      accessToken: accessToken ? `${accessToken.substring(0, 20)}...` : null,
      hasAccessToken: !!accessToken,
      accessTokenLength: accessToken?.length
    });

    if (accessToken) {
      console.log('💾 Сохранение токена в localStorage...');
      
      // Проверяем срок действия токена (JWT)
      try {
        const tokenParts = accessToken.split('.');
        if (tokenParts.length === 3) {
          const payload = JSON.parse(atob(tokenParts[1]));
          const exp = payload.exp;
          const now = Math.floor(Date.now() / 1000);
          const isExpired = exp < now;
          const expiresIn = exp - now;
          
          console.log('🔍 Информация о токене:', {
            exp: exp,
            now: now,
            expiresIn: expiresIn,
            expiresInMinutes: Math.floor(expiresIn / 60),
            isExpired: isExpired,
            expiresAt: new Date(exp * 1000).toLocaleString()
          });
          
          if (isExpired) {
            console.warn('⚠️ Токен уже истек!');
          }
        }
      } catch (e) {
        console.log('⚠️ Не удалось декодировать токен:', e);
      }
      
      localStorage.setItem("access_token", accessToken);
      
      // Проверяем, что токен действительно сохранился
      const savedAccessToken = localStorage.getItem("access_token");
      
      console.log('✅ Токен сохранен в localStorage:', {
        accessTokenSaved: !!savedAccessToken,
        accessTokenLength: savedAccessToken?.length,
        tokensMatch: savedAccessToken === accessToken
      });

      // Удалить токен из URL
      const params = new URLSearchParams(window.location.search);
      params.delete("access_token");
      params.delete("access"); // Удаляем и старый параметр для обратной совместимости
      const newUrl =
        window.location.pathname +
        (params.toString() ? "?" + params.toString() : "");
      window.history.replaceState({}, document.title, newUrl);
      
      console.log('🧹 Токен удален из URL, новый URL:', newUrl);
    } else {
      console.log('⚠️ Токен не найден в URL');
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <WebSocketProvider>
          <ChatProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<Index />} />
                <Route path="/message-box" element={<MessageBox />} />
                {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
                <Route path="*" element={<NotFound />} />
              </Routes>
            </BrowserRouter>
          </ChatProvider>
        </WebSocketProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
};

export default App;
