import type { TranslatableBlock } from "../services/api";

/**
 * # @module: useCurtain
 * Touch gesture engine for CurtainBlock.
 * Captures touchstart/move/end, calculates drag offset,
 * evaluates threshold + flick velocity, triggers snap open/close.
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

const SNAP_DURATION = 250;
const OPEN_THRESHOLD = 0.3;
const FLICK_VELOCITY = 0.3;
const DEAD_ZONE = 10;
const MAX_OPEN = 400;
const HORIZONTAL_GATE_DEG = 30;
const VELOCITY_WINDOW_MS = 150;

function horizontalGate(dx: number, dy: number): boolean {
  const angle = Math.abs(Math.atan2(Math.abs(dx), Math.abs(dy)) * (180 / Math.PI));
  return angle > 90 - HORIZONTAL_GATE_DEG;
}

export function useCurtain(
  blockHeight: number,
  onOpen: () => Promise<void>,
  onClose: () => void
): UseCurtainResult {
  const [state, setState] = React.useState<CurtainState>("idle");
  const [offset, setOffset] = React.useState(0);

  const startY = React.useRef(0);
  const startTime = React.useRef(0);
  const positions = React.useRef<Array<{ t: number; y: number }>>([]);
  const isHorizontal = React.useRef(false);
  const maxOpen = React.useRef(Math.min(blockHeight, MAX_OPEN));

  React.useEffect(() => {
    maxOpen.current = Math.min(blockHeight, MAX_OPEN);
  }, [blockHeight]);

  const handleTouchStart = React.useCallback((e: React.TouchEvent) => {
    const touch = e.touches[0];
    startY.current = touch.clientY;
    startTime.current = Date.now();
    positions.current = [{ t: Date.now(), y: touch.clientY }];
    isHorizontal.current = false;
    setState("dragging");
  }, []);

  const handleTouchMove = React.useCallback(
    (e: React.TouchEvent) => {
      if (!isHorizontal.current) {
        const touch = e.touches[0];
        const dy = startY.current - touch.clientY;
        const dx = Math.abs(touch.clientX - (e.touches[0]?.clientX || 0));

        if (horizontalGate(dx, dy) && Math.abs(dy) > DEAD_ZONE) {
          isHorizontal.current = true;
          return;
        }

        if (isHorizontal.current) return;

        if (Math.abs(dy) > DEAD_ZONE) {
          e.preventDefault();
        }

        const clamped = Math.max(0, Math.min(dy, maxOpen.current));
        setOffset(clamped);
        positions.current.push({ t: Date.now(), y: touch.clientY });

        if (positions.current.length > 20) {
          positions.current = positions.current.slice(-20);
        }
      }
    },
    []
  );

  const handleTouchEnd = React.useCallback(() => {
    if (isHorizontal.current) {
      setState("idle");
      return;
    }

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
    const shouldOpen =
      offset > threshold || (velocity > FLICK_VELOCITY && offset > DEAD_ZONE);

    if (shouldOpen) {
      setOffset(maxOpen.current);
      setState("loading");
      onOpen()
        .then(() => setState("loaded"))
        .catch(() => setState("error"));
    } else {
      setOffset(0);
      setState("idle");
      onClose();
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
