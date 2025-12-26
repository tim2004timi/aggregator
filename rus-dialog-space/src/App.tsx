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
    const params = new URLSearchParams(window.location.search);
    // Проверяем оба варианта параметра для обратной совместимости
    const accessToken = params.get("access_token") || params.get("access");

    console.log('🔍 Проверка токена в URL:', {
      accessToken: accessToken ? `${accessToken.substring(0, 20)}...` : null,
      hasAccessToken: !!accessToken
    });

    if (accessToken) {
      console.log('💾 Сохранение токена в localStorage...');
      
      localStorage.setItem("access_token", accessToken);
      
      // Проверяем, что токен действительно сохранился
      const savedAccessToken = localStorage.getItem("access_token");
      
      console.log('✅ Токен сохранен в localStorage:', {
        accessTokenSaved: !!savedAccessToken,
        accessTokenLength: savedAccessToken?.length
      });

      // Удалить токен из URL
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
