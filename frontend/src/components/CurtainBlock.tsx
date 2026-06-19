/**
 * # @module: CurtainBlock
 *
 * Visual curtain component for translatable article blocks.
 * Two-layer structure: original (slides up) + translation (fades in).
 * Uses useCurtain for gesture handling and useTranslation for cache.
 */

import React, { useRef, useState, useEffect, useCallback } from "react";
import DOMPurify from "dompurify";
import type { Block, HeadingBlock, ListBlock, QuoteBlock } from "../services/api";
import { isTranslatable } from "../services/api";
import { useCurtain, SNAP_DURATION_MS } from "../hooks/useCurtain";
import { useTranslation } from "../hooks/useTranslation";

interface CurtainBlockProps {
  articleId: string;
  blockIndex: number;
  block: Block;
}

function sanitizeHtml(text: string): string {
  return DOMPurify.sanitize(text, { ADD_ATTR: ["target"] });
}

function renderBlockContent(block: Block): React.ReactNode {
  switch (block.type) {
    case "heading": {
      const h = block as HeadingBlock;
      const Tag = `h${h.level}` as keyof React.JSX.IntrinsicElements;
      return React.createElement(Tag, {
        className: `heading heading-${h.level}`,
        dangerouslySetInnerHTML: { __html: sanitizeHtml(h.content) },
      });
    }
    case "paragraph":
      return React.createElement("p", {
        className: "paragraph",
        dangerouslySetInnerHTML: { __html: sanitizeHtml(block.content) },
      });
    case "list": {
      const l = block as ListBlock;
      const Tag = l.ordered ? "ol" : "ul";
      return React.createElement(
        Tag,
        { className: `list ${l.ordered ? "list-ordered" : "list-unordered"}` },
        l.items.map((item, i) =>
          React.createElement("li", {
            key: i,
            dangerouslySetInnerHTML: { __html: sanitizeHtml(item) },
          })
        )
      );
    }
    case "quote":
      return React.createElement("blockquote", {
        className: "quote",
        dangerouslySetInnerHTML: { __html: sanitizeHtml(block.content) },
      });
    default:
      return null;
  }
}

export default function CurtainBlock({
  articleId,
  blockIndex,
  block,
}: CurtainBlockProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [blockHeight, setBlockHeight] = useState(100);
  const [translationText, setTranslationText] = useState<string | null>(null);
  const { getTranslation } = useTranslation();

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const h = entry.contentRect.height;
        if (h > 0) setBlockHeight(h);
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const handleOpen = useCallback(async () => {
    const text = await getTranslation(articleId, blockIndex);
    setTranslationText(text);
  }, [articleId, blockIndex, getTranslation]);

  const handleClose = useCallback(() => {
    // Cached translation stays; just close visual
  }, []);

  const { curtainProps, state, offset, isOpen } = useCurtain(
    blockHeight,
    handleOpen,
    handleClose
  );

  const showTranslation = state === "loaded" && translationText !== null;
  const showSpinner = state === "loading";
  const showError = state === "error";

  if (!isTranslatable(block)) {
    return <>{renderBlockContent(block)}</>;
  }

  return (
    <div
      ref={containerRef}
      className="curtain-container"
      data-curtain-block=""
      data-block-index={blockIndex}
      {...curtainProps}
    >
      <div
        className="curtain-original"
        style={{
          transform: `translateY(-${offset}px) translateZ(0)`,
          transition:
            offset === 0 || isOpen
              ? `transform ${SNAP_DURATION_MS}ms ease-out`
              : "none",
        }}
      >
        {renderBlockContent(block)}
      </div>
      <div
        className={`curtain-translation ${isOpen ? "visible" : ""}`}
        aria-hidden={!isOpen}
      >
        {showSpinner && <div className="curtain-spinner" />}
        {showError && (
          <p className="curtain-error">[CurtainBlock] Translation unavailable</p>
        )}
        {showTranslation && <p>{translationText}</p>}
      </div>
    </div>
  );
}
