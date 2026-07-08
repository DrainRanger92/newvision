/**
 * # @module: ArticleRenderer
 *
 * Renders article blocks, routing translatable blocks
 * (heading h2-h6, paragraph, list, quote) through CurtainBlock
 * and non-translatable blocks (code, image) directly.
 * Triggers batch prefetch on article load.
 */

import type { Article, Block, HeadingBlock } from "../services/api";
import { isTranslatable } from "../services/api";
import CurtainBlock from "./CurtainBlock";
import { useTranslation } from "../hooks/useTranslation";
import { useBatchPrefetch } from "../hooks/useTranslation";
import { usePreload } from "../hooks/usePreload";

interface Props {
  article: Article;
}

function isTitleBlock(block: Block): boolean {
  return block.type === "heading" && (block as HeadingBlock).level === 1;
}

export default function ArticleRenderer({ article }: Props) {
  const { preloadTranslations } = useTranslation();

  useBatchPrefetch(article.id, article.blocks);

  const { sentinelRef } = usePreload(
    article.id,
    article.blocks,
    preloadTranslations,
    isTranslatable
  );

  return (
    <article className="article">
      <h1 className="article-title">{article.title}</h1>
      <div className="article-blocks">
        {article.blocks.map((block, index) => {
          if (isTitleBlock(block)) {
            return null;
          }

          if (isTranslatable(block)) {
            return (
              <CurtainBlock
                key={index}
                articleId={article.id}
                blockIndex={index}
                block={block}
              />
            );
          }

          return <DirectBlockRenderer key={index} block={block} />;
        })}
        <div ref={sentinelRef} style={{ height: 1 }} aria-hidden="true" />
      </div>
    </article>
  );
}

function DirectBlockRenderer({ block }: { block: Block }) {
  switch (block.type) {
    case "code":
      return renderCode(block.content, block.language);
    case "image":
      return renderImage(block.src, block.alt);
    default:
      return null;
  }
}

function renderCode(content: string, language: string | null) {
  return (
    <div className="code-block-wrapper">
      {language && <span className="code-lang">{language}</span>}
      <pre className="code-block">
        <code>{content}</code>
      </pre>
    </div>
  );
}

function renderImage(src: string, alt: string) {
  return (
    <div className="image-block">
      <img src={src} alt={alt} loading="lazy" />
      {alt && <span className="image-alt">{alt}</span>}
    </div>
  );
}
