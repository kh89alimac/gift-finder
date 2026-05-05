import apiClient from './client';
import type { AuthTokens, LoginRequest, RegisterRequest, User } from '../types/api';

export async function register(data: RegisterRequest): Promise<{ user: User; tokens: AuthTokens }> {
  const response = await apiClient.post<{ user: User; tokens: AuthTokens }>('/auth/register', data);
  return response.data;
}

export async function login(email: string, password: string): Promise<{ user: User; tokens: AuthTokens }> {
  const data: LoginRequest = { email, password };
  const response = await apiClient.post<{ user: User; tokens: AuthTokens }>('/auth/login', data);
  return response.data;
}

// The refresh token lives in an httpOnly cookie — `withCredentials: true` on
// the axios instance ensures it is sent automatically, no body needed.
export async function refreshToken(): Promise<AuthTokens> {
  const response = await apiClient.post<AuthTokens>('/auth/refresh');
  return response.data;
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post('/auth/logout');
  } catch {
    // Ignore errors on logout
  }
}

export async function getMe(): Promise<User> {
  const response = await apiClient.get<User>('/auth/me');
  return response.data;
}
