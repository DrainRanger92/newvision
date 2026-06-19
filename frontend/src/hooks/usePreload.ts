/**
 * # @module: usePreload
 * IntersectionObserver-based translation preloader.
 * When the last visible CurtainBlock enters viewport,
 * debounced 300ms → preload next 3 untranslated blocks.
 */

import { useEffect, useRef, useCallback } from "react";
import type { Block } from "../services/api";

const DEBOUNCE_MS = 300;
const LOOK_AHEAD = 3;

export function usePreload(
  articleId: string,
  blocks: Block[],
  currentIndex: number,
  preloadFn: (articleId: string, indices: number[]) => Promise<void>,
  isTranslatableFn: (block: Block) => boolean
) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const preloadedRef = useRef<Set<number>>(new Set());

  const schedulePreload = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(() => {
      const start = currentIndex + 1;
      const candidates: number[] = [];

      for (let i = start; i < blocks.length && candidates.length < LOOK_AHEAD; i++) {
        if (
          isTranslatableFn(blocks[i]) &&
          !preloadedRef.current.has(i)
        ) {
          candidates.push(i);
          preloadedRef.current.add(i);
        }
      }

      if (candidates.length > 0) {
        preloadFn(articleId, candidates);
      }
    }, DEBOUNCE_MS);
  }, [articleId, blocks, currentIndex, preloadFn, isTranslatableFn]);

  useEffect(() => {
    preloadedRef.current = new Set();
  }, [articleId]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  return { schedulePreload };
}
