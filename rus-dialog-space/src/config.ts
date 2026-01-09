const origin = window.location.origin;
const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const defaultWsUrl = `${wsProtocol}://${window.location.host}/ws`;

// В продакшн-сборке намеренно НЕ доверяем VITE_API_URL/VITE_WS_URL, потому что
// их часто оставляют как localhost и “вшивают” в билд, ломая прод.
const isProdBuild = import.meta.env.PROD;

export const config = {
  apiUrl: isProdBuild ? `${origin}/api` : (import.meta.env.VITE_API_URL || `${origin}/api`),
  wsUrl: isProdBuild ? defaultWsUrl : (import.meta.env.VITE_WS_URL || defaultWsUrl),
  authUrl: import.meta.env.VITE_AUTH_URL || `${origin}/api/auth`,
};