import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { Article } from "../services/api";
import { fetchArticle } from "../services/api";
import ArticleRenderer from "../components/ArticleRenderer";

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

    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchArticle(id!);
        if (!cancelled) {
          setArticle(data);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load article");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="reader-status">
        <div className="spinner" />
        <p>Loading article...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="reader-status reader-error">
        <p>{error}</p>
      </div>
    );
  }

  if (!article) {
    return (
      <div className="reader-status reader-error">
        <p>Article not found</p>
      </div>
    );
  }

  return <ArticleRenderer article={article} />;
}
