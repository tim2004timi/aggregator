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
    const accessToken = params.get("access");
    const refreshToken = params.get("refresh");

    console.log('🔍 Проверка токенов в URL:', {
      accessToken: accessToken ? `${accessToken.substring(0, 20)}...` : null,
      refreshToken: refreshToken ? `${refreshToken.substring(0, 20)}...` : null,
      hasAccessToken: !!accessToken,
      hasRefreshToken: !!refreshToken
    });

    if (accessToken && refreshToken) {
      console.log('💾 Сохранение токенов в localStorage...');
      
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("refresh_token", refreshToken);
      
      // Проверяем, что токены действительно сохранились
      const savedAccessToken = localStorage.getItem("access_token");
      const savedRefreshToken = localStorage.getItem("refresh_token");
      
      console.log('✅ Токены сохранены в localStorage:', {
        accessTokenSaved: !!savedAccessToken,
        refreshTokenSaved: !!savedRefreshToken,
        accessTokenLength: savedAccessToken?.length,
        refreshTokenLength: savedRefreshToken?.length
      });

      // Удалить токены из URL
      params.delete("access");
      params.delete("refresh");
      const newUrl =
        window.location.pathname +
        (params.toString() ? "?" + params.toString() : "");
      window.history.replaceState({}, document.title, newUrl);
      
      console.log('🧹 Токены удалены из URL, новый URL:', newUrl);
    } else {
      console.log('⚠️ Токены не найдены в URL или отсутствуют');
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
