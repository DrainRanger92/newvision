/**
 * # @module: ArticleRenderer
 *
 * Renders article blocks, routing translatable blocks
 * (heading h2-h6, paragraph, list, quote) through CurtainBlock
 * and non-translatable blocks (code, image, h1) directly.
 */

import DOMPurify from "dompurify";
import type { Article, Block, HeadingBlock } from "../services/api";
import { isTranslatable } from "../services/api";
import CurtainBlock from "./CurtainBlock";

interface Props {
  article: Article;
}

function sanitizeHtml(text: string): string {
  return DOMPurify.sanitize(text, { ADD_ATTR: ["target"] });
}

export default function ArticleRenderer({ article }: Props) {
  const isTitle = (block: Block, index: number): boolean => {
    if (block.type === "heading" && (block as HeadingBlock).level === 1) {
      return true;
    }
    return index === 0 && block.type === "heading";
  };

  return (
    <article className="article">
      <h1 className="article-title">{article.title}</h1>
      <div className="article-blocks">
        {article.blocks.map((block, index) => {
          if (isTitle(block, index)) {
            return (
              <h1 key={index} className="article-title">
                {block.content}
              </h1>
            );
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
