/**
 * # @module: useTranslation
 * React Context providing a shared translation cache.
 * Uses Map<string, string> keyed by articleId:blockIndex.
 * Deduplicates in-flight requests. Error responses cached.
 */

import React, {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useRef,
} from "react";
import {
  fetchBlockTranslation,
  fetchBlockTranslationBatch,
  isTranslatable,
} from "../services/api";
import type { Block } from "../services/api";

interface TranslationContextValue {
  getTranslation: (articleId: string, blockIndex: number) => Promise<string>;
  isTranslating: (articleId: string, blockIndex: number) => boolean;
  preloadTranslations: (
    articleId: string,
    indices: number[]
  ) => Promise<void>;
}

const TranslationContext = createContext<TranslationContextValue | null>(null);

const ERROR_MARKER = "[translation error]";
const BATCH_SIZE = 10;

export function TranslationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const cache = useRef<Map<string, string>>(new Map());
  const pending = useRef<Map<string, Promise<string>>>(new Map());

  const getTranslation = useCallback(
    async (articleId: string, blockIndex: number): Promise<string> => {
      const key = `${articleId}:${blockIndex}`;

      const cached = cache.current.get(key);
      if (cached !== undefined) return cached;

      const inflight = pending.current.get(key);
      if (inflight) return inflight;

      const promise = fetchBlockTranslation(articleId, blockIndex)
        .then((text) => {
          cache.current.set(key, text);
          pending.current.delete(key);
          return text;
        })
        .catch(() => {
          cache.current.set(key, ERROR_MARKER);
          pending.current.delete(key);
          return ERROR_MARKER;
        });

      pending.current.set(key, promise);
      return promise;
    },
    []
  );

  const isTranslating = useCallback(
    (articleId: string, blockIndex: number): boolean => {
      const key = `${articleId}:${blockIndex}`;
      return pending.current.has(key);
    },
    []
  );

  const preloadTranslations = useCallback(
    async (articleId: string, indices: number[]): Promise<void> => {
      const uncached = indices.filter((i) => {
        const key = `${articleId}:${i}`;
        return !cache.current.has(key) && !pending.current.has(key);
      });

      if (uncached.length === 0) return;

      try {
        const texts = await fetchBlockTranslationBatch(articleId, uncached);
        texts.forEach((text, j) => {
          const blockIndex = uncached[j];
          if (blockIndex !== undefined) {
            cache.current.set(`${articleId}:${blockIndex}`, text);
          }
        });
      } catch {
        uncached.forEach((i) => {
          cache.current.set(`${articleId}:${i}`, ERROR_MARKER);
        });
      }
    },
    []
  );

  return React.createElement(
    TranslationContext.Provider,
    { value: { getTranslation, isTranslating, preloadTranslations } },
    children
  );
}

export function useTranslation(): TranslationContextValue {
  const ctx = useContext(TranslationContext);
  if (!ctx) {
    throw new Error("useTranslation must be used within TranslationProvider");
  }
  return ctx;
}

export function useBatchPrefetch(
  articleId: string,
  blocks: Block[]
): void {
  const { preloadTranslations } = useTranslation();

  useEffect(() => {
    const translatableIndices: number[] = [];
    blocks.forEach((block, index) => {
      if (isTranslatable(block)) {
        translatableIndices.push(index);
      }
    });

    if (translatableIndices.length === 0) return;

    for (let i = 0; i < translatableIndices.length; i += BATCH_SIZE) {
      const chunk: number[] = [];
      const end = Math.min(i + BATCH_SIZE, translatableIndices.length);
      for (let j = i; j < end; j++) {
        const idx = translatableIndices[j];
        if (idx !== undefined) chunk.push(idx);
      }
      if (chunk.length > 0) {
        preloadTranslations(articleId, chunk);
      }
    }
  }, [articleId, blocks, preloadTranslations]);
}
