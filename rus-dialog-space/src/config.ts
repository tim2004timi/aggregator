export const config = {
  apiUrl: import.meta.env.VITE_API_URL || `http://${window.location.hostname}:3001/api`,
  wsUrl: import.meta.env.VITE_WS_URL || `ws://${window.location.hostname}:3001/ws`,
  authUrl: 'http://109.172.36.219:8000/api/auth',
};
