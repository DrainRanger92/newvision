/**
 * # @module: usePreload
 * IntersectionObserver-based translation preloader.
 * Returns a sentinelRef to attach at the end of the block list.
 * When sentinel enters viewport (200px margin), preloads next 3 uncached blocks.
 * Tracks progress via a cursor ref to avoid re-preloading blocks.
 */

import { useEffect, useRef, useCallback } from "react";
import type { Block } from "../services/api";

const DEBOUNCE_MS = 300;
const LOOK_AHEAD = 3;
const ROOT_MARGIN = "200px";

export function usePreload(
  articleId: string,
  blocks: Block[],
  preloadFn: (articleId: string, indices: number[]) => Promise<void>,
  isTranslatableFn: (block: Block) => boolean
) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cursorRef = useRef(0);
  const preloadedSetRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    cursorRef.current = 0;
    preloadedSetRef.current = new Set();
  }, [articleId]);

  const schedulePreload = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = setTimeout(() => {
      const candidates: number[] = [];
      let i = cursorRef.current;

      while (i < blocks.length && candidates.length < LOOK_AHEAD) {
        if (isTranslatableFn(blocks[i]) && !preloadedSetRef.current.has(i)) {
          candidates.push(i);
          preloadedSetRef.current.add(i);
        }
        i++;
      }

      cursorRef.current = i;

      if (candidates.length > 0) {
        preloadFn(articleId, candidates).catch(() => {
          /* fire-and-forget: errors handled by useTranslation cache */
        });
      }
    }, DEBOUNCE_MS);
  }, [articleId, blocks, preloadFn, isTranslatableFn]);

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
