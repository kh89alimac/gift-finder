import axios, { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

// We import the store lazily to avoid circular dependencies
let getAccessToken: (() => string | null) | null = null;
let setAuthTokens: ((accessToken: string) => void) | null = null;
let clearAuth: (() => void) | null = null;

export function injectAuthStore(
  tokenGetter: () => string | null,
  tokenSetter: (token: string) => void,
  authClearer: () => void
) {
  getAccessToken = tokenGetter;
  setAuthTokens = tokenSetter;
  clearAuth = authClearer;
}

// `withCredentials: true` — required so the browser sends the httpOnly
// refresh-token cookie alongside requests to /api/v1/auth/refresh and
// /api/v1/auth/logout. The refresh token is no longer in localStorage.
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Request interceptor — attach Bearer token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (getAccessToken) {
      const token = getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

let isRefreshing = false;
let refreshQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else if (token) {
      resolve(token);
    }
  });
  refreshQueue = [];
}

// Response interceptor — 401 → refresh → retry
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest: AxiosRequestConfig & { _retry?: boolean } = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve, reject });
        }).then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Dynamically import to avoid circular dependency at module load time.
        // The refresh cookie is sent automatically because of `withCredentials`.
        const { refreshToken } = await import('./auth');
        const tokens = await refreshToken();

        if (setAuthTokens) {
          setAuthTokens(tokens.accessToken);
        }

        processQueue(null, tokens.accessToken);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${tokens.accessToken}`;
        }

        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        if (clearAuth) {
          clearAuth();
        }
        if (typeof window !== 'undefined') {
          window.location.href = '/auth/login';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
