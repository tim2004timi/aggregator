import React, { createContext, useContext, useEffect, useState } from 'react';
import { Message } from '../types';
import { config } from '../config';

interface WebSocketContextType {
  sendMessage: (message: Message) => void;
  lastMessage: Message | null;
  isConnected: boolean;
  lastUpdate: any;
}

const WebSocketContext = createContext<WebSocketContextType>({
  sendMessage: () => {},
  lastMessage: null,
  isConnected: false,
  lastUpdate: null,
});

export const useWebSocket = () => useContext(WebSocketContext);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [updatesWs, setUpdatesWs] = useState<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<Message | null>(null);
  const [lastUpdate, setLastUpdate] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const socket = new WebSocket(`${config.wsUrl}/messages`);
    socket.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };
    socket.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      // Attempt to reconnect after 5 seconds
      setTimeout(() => {
        setWs(null);
      }, 5000);
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('Received WebSocket message:', message);
        setLastMessage(message);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };
    setWs(socket);

    return () => {
      socket.close();
    };
  }, []);

  useEffect(() => {
    const socket = new WebSocket(`${config.wsUrl}/updates`);
    socket.onopen = () => {};
    socket.onclose = () => {
      console.log('Updates WebSocket disconnected');
      setTimeout(() => setUpdatesWs(null), 5000);
    };
    socket.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data);
        console.log('Received Updates WebSocket message:', update);
        setLastUpdate(update);
      } catch (error) {
        console.error('Error parsing Updates WebSocket message:', error);
      }
    };
    setUpdatesWs(socket);

    return () => {
      socket.close();
    };
  }, []);

  const sendMessage = (message: Message) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    } else {
      console.error('WebSocket is not connected');
    }
  };

  return (
    <WebSocketContext.Provider value={{ sendMessage, lastMessage, isConnected, lastUpdate }}>
      {children}
    </WebSocketContext.Provider>
  );
}; 