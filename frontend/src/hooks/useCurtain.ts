import React from "react";

/**
 * # @module: useCurtain
 * Touch gesture engine for CurtainBlock.
 * Captures touchstart/move/end, calculates drag offset,
 * evaluates threshold + flick velocity, triggers snap open/close.
 * Supports both open→close (swipe down) and close→open (swipe up) gestures.
 */

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
  return angle > 90 - HORIZONTAL_GATE_DEG;
}

export function useCurtain(
  blockHeight: number,
  isCurrentlyOpen: boolean,
  onOpen: () => Promise<void>,
  onClose: () => void
): UseCurtainResult {
  const [state, setState] = React.useState<CurtainState>("idle");
  const [offset, setOffset] = React.useState(0);

  const startY = React.useRef(0);
  const startX = React.useRef(0);
  const startOffset = React.useRef(0);
  const startTime = React.useRef(0);
  const positions = React.useRef<Array<{ t: number; y: number }>>([]);
  const maxOpen = React.useRef(Math.min(blockHeight, MAX_OPEN));

  React.useEffect(() => {
    maxOpen.current = Math.min(blockHeight, MAX_OPEN);
  }, [blockHeight]);

  React.useEffect(() => {
    if (isCurrentlyOpen) {
      setOffset(maxOpen.current);
      setState("loaded");
    } else {
      setOffset(0);
      setState("idle");
    }
  }, [isCurrentlyOpen]);

  const handleTouchStart = React.useCallback((e: React.TouchEvent) => {
    const touch = e.touches[0];
    startY.current = touch.clientY;
    startX.current = touch.clientX;
    startOffset.current = offset;
    startTime.current = Date.now();
    positions.current = [{ t: Date.now(), y: touch.clientY }];
    setState("dragging");
  }, [offset]);

  const handleTouchMove = React.useCallback(
    (e: React.TouchEvent) => {
      const touch = e.touches[0];
      const dy = startY.current - touch.clientY;

      if (Math.abs(dy) <= DEAD_ZONE) return;

      const dx = Math.abs(startX.current - touch.clientX);
      if (horizontalGate(dx, dy)) return;

      e.preventDefault();

      const rawOffset = startOffset.current + dy;
      const clamped = Math.max(0, Math.min(rawOffset, maxOpen.current));
      setOffset(clamped);
      positions.current.push({ t: Date.now(), y: touch.clientY });

      if (positions.current.length > 20) {
        positions.current = positions.current.slice(-20);
      }
    },
    []
  );

  const handleTouchEnd = React.useCallback(() => {
    const now = Date.now();
    const velocityPoints = positions.current.filter(
      (p) => now - p.t <= VELOCITY_WINDOW_MS
    );

    let velocity = 0;
    if (velocityPoints.length >= 2) {
      const first = velocityPoints[0];
      const last = velocityPoints[velocityPoints.length - 1];
      const dt = last.t - first.t;
      if (dt > 0) {
        velocity = Math.abs(first.y - last.y) / dt;
      }
    }

    const threshold = maxOpen.current * OPEN_THRESHOLD;
    const deltaFromStart = Math.abs(offset - startOffset.current);
    const shouldOpen =
      offset > threshold || (velocity > FLICK_VELOCITY && deltaFromStart > DEAD_ZONE);
    const wasOpen = startOffset.current > threshold;

    if (wasOpen && !shouldOpen) {
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
      setOffset(startOffset.current > 0 ? maxOpen.current : 0);
      setState(startOffset.current > 0 ? "loaded" : "idle");
    }
  }, [offset, onOpen, onClose]);

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
