import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchArticle, type Article } from "../services/api";

function sanitizeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export default function Reader() {
  const { id } = useParams<{ id: string }>();
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError("No article ID provided");
      setLoading(false);
      return;
    }
    fetchArticle(id)
      .then(setArticle)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="app"><p>Loading...</p></div>;
  }

  if (error) {
    return <div className="app"><p>Error: {error}</p></div>;
  }

  if (!article) return null;

  return (
    <div className="app">
      <h1>{article.title}</h1>
      {article.blocks.map((block, i) => (
        <BlockRenderer key={i} block={block} />
      ))}
    </div>
  );
}

function BlockRenderer({ block }: { block: Article["blocks"][number] }) {
  switch (block.type) {
    case "heading": {
      const level = Math.min(Math.max(block.level, 1), 6);
      const Tag = `h${level}` as keyof JSX.IntrinsicElements;
      const html = sanitizeHtml(block.content);
      return <Tag dangerouslySetInnerHTML={{ __html: html }} />;
    }
    case "paragraph": {
      const html = sanitizeHtml(block.content);
      return <p dangerouslySetInnerHTML={{ __html: html }} />;
    }
    case "code":
      return (
        <pre>
          <code>{block.content}</code>
        </pre>
      );
    case "image":
      return <img src={block.src} alt={block.alt} style={{ maxWidth: "100%" }} />;
    case "list":
      if (block.ordered) {
        return (
          <ol>
            {block.items.map((item, i) => (
              <li key={i} dangerouslySetInnerHTML={{ __html: sanitizeHtml(item) }} />
            ))}
          </ol>
        );
      }
      return (
        <ul>
          {block.items.map((item, i) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: sanitizeHtml(item) }} />
          ))}
        </ul>
      );
    case "quote": {
      const html = sanitizeHtml(block.content);
      return <blockquote dangerouslySetInnerHTML={{ __html: html }} />;
    }
    default:
      return null;
  }
}
