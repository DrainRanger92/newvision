/**
 * # @module: useCurtain
 * Touch gesture engine for CurtainBlock.
 * Captures touchstart/move/end, calculates drag offset,
 * evaluates threshold + flick velocity, triggers snap open/close.
 * Supports both open→close (swipe down) and close→open (swipe up) gestures.
 */

import React, { useRef, useState, useEffect, useCallback } from "react";

export type CurtainState = "idle" | "dragging" | "loading" | "loaded" | "error";

export interface CurtainGesture {
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchMove: (e: React.TouchEvent) => void;
  onTouchEnd: (e: React.TouchEvent) => void;
}

export interface UseCurtainResult {
  curtainProps: CurtainGesture;
  state: CurtainState;
  offset: number;
  isOpen: boolean;
}

const OPEN_THRESHOLD = 0.3;
const FLICK_VELOCITY = 0.3;
const DEAD_ZONE = 10;
const MAX_OPEN = 400;
const HORIZONTAL_GATE_DEG = 30;
const VELOCITY_WINDOW_MS = 150;

export const SNAP_DURATION_MS = 250;

function horizontalGate(dx: number, dy: number): boolean {
  if (Math.abs(dy) < 1) return true;
  const angle = Math.abs(Math.atan2(Math.abs(dx), Math.abs(dy)) * (180 / Math.PI));
  return angle > HORIZONTAL_GATE_DEG;
}

export function useCurtain(
  blockHeight: number,
  onOpen: () => Promise<void>,
  onClose: () => void
): UseCurtainResult {
  const [state, setState] = useState<CurtainState>("idle");
  const [offset, setOffset] = useState(0);

  const startY = useRef(0);
  const startX = useRef(0);
  const startOffset = useRef(0);
  const offsetRef = useRef(0);
  const positions = useRef<Array<{ t: number; y: number }>>([]);
  const maxOpen = useRef(Math.min(blockHeight, MAX_OPEN));
  const rafRef = useRef(0);

  useEffect(() => {
    maxOpen.current = Math.min(blockHeight, MAX_OPEN);
  }, [blockHeight]);

  useEffect(() => {
    offsetRef.current = offset;
  }, [offset]);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    const touch = e.touches[0];
    if (!touch) return;
    startY.current = touch.clientY;
    startX.current = touch.clientX;
    startOffset.current = offsetRef.current;
    positions.current = [{ t: Date.now(), y: touch.clientY }];
    setState("dragging");
  }, []);

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      const touch = e.touches[0];
      if (!touch) return;

      const dy = startY.current - touch.clientY;
      if (Math.abs(dy) <= DEAD_ZONE) return;

      const dx = Math.abs(startX.current - touch.clientX);
      if (horizontalGate(dx, dy)) return;

      e.preventDefault();

      const rawOffset = startOffset.current + dy;
      const clamped = Math.max(0, Math.min(rawOffset, maxOpen.current));

      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        setOffset(clamped);
      });

      positions.current.push({ t: Date.now(), y: touch.clientY });
      if (positions.current.length > 20) {
        positions.current = positions.current.slice(-20);
      }
    },
    []
  );

  const handleTouchEnd = useCallback(() => {
    const currentOffset = offsetRef.current;
    const wasOpen = startOffset.current > maxOpen.current * OPEN_THRESHOLD;

    const now = Date.now();
    const velocityPoints = positions.current.filter(
      (p) => now - p.t <= VELOCITY_WINDOW_MS
    );

    let signedVelocity = 0;
    if (velocityPoints.length >= 2) {
      const first = velocityPoints[0];
      const last = velocityPoints[velocityPoints.length - 1];
      if (first && last) {
        const dt = last.t - first.t;
        if (dt > 0) {
          signedVelocity = (first.y - last.y) / dt;
        }
      }
    }

    const threshold = maxOpen.current * OPEN_THRESHOLD;
    const absVelocity = Math.abs(signedVelocity);
    const deltaFromStart = Math.abs(currentOffset - startOffset.current);
    const shouldOpen =
      currentOffset > threshold || (absVelocity > FLICK_VELOCITY && deltaFromStart > DEAD_ZONE);
    const isFlickDown = signedVelocity < -FLICK_VELOCITY;

    if (wasOpen && isFlickDown) {
      setOffset(0);
      setState("idle");
      onClose();
    } else if (wasOpen && !shouldOpen) {
      setOffset(0);
      setState("idle");
      onClose();
    } else if (shouldOpen) {
      setOffset(maxOpen.current);
      setState("loading");
      onOpen()
        .then(() => setState("loaded"))
        .catch(() => setState("error"));
    } else {
      setOffset(wasOpen ? maxOpen.current : 0);
      setState(wasOpen ? "loaded" : "idle");
    }
  }, [onOpen, onClose]);

  useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const isOpen = state === "loading" || state === "loaded" || state === "error";

  return {
    curtainProps: {
      onTouchStart: handleTouchStart,
      onTouchMove: handleTouchMove,
      onTouchEnd: handleTouchEnd,
    },
    state,
    offset,
    isOpen,
  };
}
