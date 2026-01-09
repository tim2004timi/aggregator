export const config = {
  apiUrl: import.meta.env.VITE_API_URL || `${window.location.origin}/api`,
  wsUrl: import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws`,
  authUrl: 'http://109.172.36.219:8000/api/auth',
};