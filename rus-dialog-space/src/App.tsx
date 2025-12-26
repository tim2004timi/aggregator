import React from "react";
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

// Функция для извлечения токена из URL (выполняется синхронно до рендеринга)
const extractTokenFromUrl = (): void => {
  const searchString = window.location.search;
  const hashString = window.location.hash;
  const fullUrl = window.location.href;
  
  // Пробуем получить токен из query string
  let accessToken: string | null = null;
  
  if (searchString) {
    const params = new URLSearchParams(searchString);
    accessToken = params.get("access_token") || params.get("access");
  }
  
  // Если токен не найден в query string, пробуем извлечь из hash
  if (!accessToken && hashString) {
    const hashParams = new URLSearchParams(hashString.substring(1));
    accessToken = hashParams.get("access_token") || hashParams.get("access");
  }
  
  // Альтернативный способ: парсим URL напрямую через регулярное выражение
  if (!accessToken) {
    const match = fullUrl.match(/[?&]access_token=([^&?#]+)/);
    if (match && match[1]) {
      accessToken = decodeURIComponent(match[1]);
    }
  }

  if (accessToken) {
    localStorage.setItem("access_token", accessToken);

    // Удалить токен из URL
    const params = new URLSearchParams(window.location.search);
    params.delete("access_token");
    params.delete("access");
    const newUrl =
      window.location.pathname +
      (params.toString() ? "?" + params.toString() : "");
    window.history.replaceState({}, document.title, newUrl);
  }
};

// Извлекаем токен СИНХРОННО до рендеринга компонентов
extractTokenFromUrl();

const App = () => {
  console.log('App component rendering');

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
