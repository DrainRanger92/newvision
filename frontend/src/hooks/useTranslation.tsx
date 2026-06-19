import React, { createContext, useContext, useCallback, useRef } from "react";
import {
  fetchBlockTranslation,
  fetchBlockTranslationBatch,
} from "../services/api";

/**
 * # @module: useTranslation
 * React Context providing a shared translation cache.
 * Uses Map<string, string> keyed by `articleId:blockIndex`.
 * Deduplicates in-flight requests via pending Promise map.
 * Error responses are cached as "[translation error]" (not retried).
 */

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
          cache.current.set(`${articleId}:${uncached[j]}`, text);
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
