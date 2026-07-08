/**
 * # @module: CurtainBlock
 *
 * Visual curtain component for translatable article blocks.
 * Icon-trigger (🌐) in left margin expands/collapses translation inline.
 * Uses useTranslation for cache and lazy fetch.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import DOMPurify from "dompurify";
import type { Block, HeadingBlock, ListBlock } from "../services/api";
import { isTranslatable } from "../services/api";
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
  const [expanded, setExpanded] = useState(false);
  const [translationText, setTranslationText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const [collapsing, setCollapsing] = useState(false);
  const { getTranslation } = useTranslation();

  const handleToggle = useCallback(async () => {
    if (expanded) {
      const el = contentRef.current;
      if (el) {
        el.style.maxHeight = `${el.scrollHeight}px`;
        setCollapsing(true);
        requestAnimationFrame(() => {
          if (el) el.style.maxHeight = "0";
        });
      }
      setTimeout(() => {
        setExpanded(false);
        setCollapsing(false);
      }, 300);
      return;
    }

    setExpanded(true);

    if (translationText !== null) return;

    setLoading(true);
    setError(false);
    try {
      const text = await getTranslation(articleId, blockIndex);
      setTranslationText(text);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [expanded, translationText, articleId, blockIndex, getTranslation]);

  useEffect(() => {
    if (!expanded || collapsing) return;
    const el = contentRef.current;
    if (!el) return;
    const frame = requestAnimationFrame(() => {
      if (el) {
        el.style.maxHeight = `${el.scrollHeight}px`;
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [expanded, collapsing, translationText, loading, error]);

  if (!isTranslatable(block)) {
    return <>{renderBlockContent(block)}</>;
  }

  const showContent = expanded || collapsing;

  return (
    <div className="translatable-block">
      <div className="translatable-row">
        <button
          className={`translate-icon ${expanded ? "active" : ""}`}
          onClick={handleToggle}
          aria-label={expanded ? "Hide translation" : "Show translation"}
          aria-expanded={expanded}
          type="button"
        >
          🌐
        </button>
        <div className="block-content">{renderBlockContent(block)}</div>
      </div>
      <div
        ref={contentRef}
        className="translation-content"
        aria-hidden={!expanded}
      >
        {showContent && (
          <div className="translation-inner">
            {loading && <div className="translation-spinner" />}
            {error && (
              <p className="translation-error">Translation unavailable</p>
            )}
            {translationText !== null && !loading && (
              <p>{translationText}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
