/**
 * # @module: usePreload
 * IntersectionObserver-based translation preloader.
 * Returns a sentinelRef to attach to the last block.
 * When sentinel enters viewport (200px margin),
 * debounced 300ms → preload next 3 untranslated blocks.
 */

import { useEffect, useRef, useCallback } from "react";
import type { Block } from "../services/api";

const DEBOUNCE_MS = 300;
const LOOK_AHEAD = 3;
const ROOT_MARGIN = "200px";

export function usePreload(
  articleId: string,
  blocks: Block[],
  currentIndex: number,
  preloadFn: (articleId: string, indices: number[]) => Promise<void>,
  isTranslatableFn: (block: Block) => boolean
) {
  const sentinelRef = useRef<HTMLDivElement>(null);
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
    const el = sentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          schedulePreload();
        }
      },
      { rootMargin: ROOT_MARGIN }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [schedulePreload]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  return { sentinelRef };
}
