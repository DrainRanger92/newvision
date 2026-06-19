import DOMPurify from "dompurify";
import type { Article, Block } from "../services/api";

interface Props {
  article: Article;
}

function sanitizeHtml(text: string): string {
  return DOMPurify.sanitize(text, { ADD_ATTR: ["target"] });
}

export default function ArticleRenderer({ article }: Props) {
  return (
    <article className="article">
      <h1 className="article-title">{article.title}</h1>
      <div className="article-blocks">
        {article.blocks.map((block, index) => (
          <BlockRenderer key={index} block={block} />
        ))}
      </div>
    </article>
  );
}

function BlockRenderer({ block }: { block: Block }) {
  switch (block.type) {
    case "heading":
      return renderHeading(block.level, block.content);
    case "paragraph":
      return <p className="paragraph" dangerouslySetInnerHTML={{ __html: sanitizeHtml(block.content) }} />;
    case "code":
      return renderCode(block.content, block.language);
    case "image":
      return renderImage(block.src, block.alt);
    case "list":
      return renderList(block.items, block.ordered);
    case "quote":
      return <blockquote className="quote" dangerouslySetInnerHTML={{ __html: sanitizeHtml(block.content) }} />;
    default:
      return null;
  }
}

function renderHeading(level: number, content: string) {
  const Tag = `h${level}` as keyof JSX.IntrinsicElements;
  return <Tag className={`heading heading-${level}`} dangerouslySetInnerHTML={{ __html: sanitizeHtml(content) }} />;
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

function renderList(items: string[], ordered: boolean) {
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className={`list ${ordered ? "list-ordered" : "list-unordered"}`}>
      {items.map((item, i) => (
        <li key={i} dangerouslySetInnerHTML={{ __html: sanitizeHtml(item) }} />
      ))}
    </Tag>
  );
}
