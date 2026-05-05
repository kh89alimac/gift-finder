'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  addItem,
  createWishlist,
  deleteWishlist,
  generateShareToken,
  getWishlist,
  listWishlists,
  removeItem,
  updateWishlist,
} from '../api/wishlists';
import useWishlistStore from '../store/wishlistStore';
import type { CreateWishlistRequest, UpdateWishlistRequest } from '../types/api';

export function useWishlists() {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: ['wishlists'],
    queryFn: listWishlists,
    staleTime: 1000 * 60 * 2,
  });
}

export function useWishlistDetail(id: string) {
  return useQuery({
    queryKey: ['wishlists', id],
    queryFn: () => getWishlist(id),
    enabled: Boolean(id),
    staleTime: 1000 * 60 * 2,
  });
}

export function useCreateWishlist() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateWishlistRequest) => createWishlist(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlists'] });
      toast.success('Wishlist created');
    },
    onError: () => {
      toast.error('Failed to create wishlist');
    },
  });
}

export function useUpdateWishlist(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateWishlistRequest) => updateWishlist(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlists'] });
      queryClient.invalidateQueries({ queryKey: ['wishlists', id] });
      toast.success('Wishlist updated');
    },
    onError: () => {
      toast.error('Failed to update wishlist');
    },
  });
}

export function useDeleteWishlist() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteWishlist(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlists'] });
      toast.success('Wishlist deleted');
    },
    onError: () => {
      toast.error('Failed to delete wishlist');
    },
  });
}

export function useAddToWishlist(wishlistId: string) {
  const queryClient = useQueryClient();
  const { addOptimistic, confirmAdd, rollback } = useWishlistStore();

  return useMutation({
    mutationFn: (itemId: string) => {
      addOptimistic(itemId);
      return addItem(wishlistId, itemId);
    },
    onSuccess: (_, itemId) => {
      confirmAdd(itemId);
      queryClient.invalidateQueries({ queryKey: ['wishlists', wishlistId] });
      toast.success('Added to wishlist');
    },
    onError: (_, itemId) => {
      rollback(itemId);
      toast.error('Failed to add item');
    },
  });
}

export function useRemoveFromWishlist(wishlistId: string) {
  const queryClient = useQueryClient();
  const { removeOptimistic, confirmRemove, rollback } = useWishlistStore();

  return useMutation({
    mutationFn: (itemId: string) => {
      removeOptimistic(itemId);
      return removeItem(wishlistId, itemId);
    },
    onSuccess: (_, itemId) => {
      confirmRemove(itemId);
      queryClient.invalidateQueries({ queryKey: ['wishlists', wishlistId] });
      toast.success('Removed from wishlist');
    },
    onError: (_, itemId) => {
      rollback(itemId);
      toast.error('Failed to remove item');
    },
  });
}

export function useGenerateShareToken(wishlistId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => generateShareToken(wishlistId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlists', wishlistId] });
    },
    onError: () => {
      toast.error('Failed to generate share link');
    },
  });
}
