import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchArticle, type Article } from "../services/api";

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
      const Tag = `h${block.level}` as keyof JSX.IntrinsicElements;
      return <Tag dangerouslySetInnerHTML={{ __html: block.content }} />;
    }
    case "paragraph":
      return <p dangerouslySetInnerHTML={{ __html: block.content }} />;
    case "code":
      return (
        <pre>
          <code>{block.content}</code>
        </pre>
      );
    case "list":
      if (block.ordered) {
        return (
          <ol>
            {block.items.map((item, i) => (
              <li key={i} dangerouslySetInnerHTML={{ __html: item }} />
            ))}
          </ol>
        );
      }
      return (
        <ul>
          {block.items.map((item, i) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: item }} />
          ))}
        </ul>
      );
    case "quote":
      return <blockquote dangerouslySetInnerHTML={{ __html: block.content }} />;
    default:
      return null;
  }
}
