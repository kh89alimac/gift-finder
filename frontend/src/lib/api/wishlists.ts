import apiClient from './client';
import type {
  CreateWishlistRequest,
  UpdateWishlistRequest,
  Wishlist,
  WishlistDetail,
} from '../types/api';

export async function listWishlists(): Promise<Wishlist[]> {
  const response = await apiClient.get<Wishlist[]>('/wishlists');
  return response.data;
}

export async function getWishlist(id: string): Promise<WishlistDetail> {
  const response = await apiClient.get<WishlistDetail>(`/wishlists/${id}`);
  return response.data;
}

export async function createWishlist(data: CreateWishlistRequest): Promise<Wishlist> {
  const response = await apiClient.post<Wishlist>('/wishlists', data);
  return response.data;
}

export async function updateWishlist(id: string, data: UpdateWishlistRequest): Promise<Wishlist> {
  const response = await apiClient.patch<Wishlist>(`/wishlists/${id}`, data);
  return response.data;
}

export async function deleteWishlist(id: string): Promise<void> {
  await apiClient.delete(`/wishlists/${id}`);
}

export async function addItem(wishlistId: string, itemId: string): Promise<void> {
  await apiClient.post(`/wishlists/${wishlistId}/items`, { itemId });
}

export async function removeItem(wishlistId: string, itemId: string): Promise<void> {
  await apiClient.delete(`/wishlists/${wishlistId}/items/${itemId}`);
}

export async function generateShareToken(id: string): Promise<{ shareToken: string }> {
  const response = await apiClient.post<{ shareToken: string }>(`/wishlists/${id}/share`);
  return response.data;
}

export async function getByShareToken(token: string): Promise<WishlistDetail> {
  const response = await apiClient.get<WishlistDetail>(`/wishlists/shared/${token}`);
  return response.data;
}
