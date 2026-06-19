const API_BASE = import.meta.env.VITE_API_URL ?? "/api";

export interface HeadingBlock {
  type: "heading";
  level: number;
  content: string;
}

export interface ParagraphBlock {
  type: "paragraph";
  content: string;
}

export interface CodeBlock {
  type: "code";
  content: string;
  language: string | null;
}

export interface ImageBlock {
  type: "image";
  src: string;
  alt: string;
}

export interface ListBlock {
  type: "list";
  items: string[];
  ordered: boolean;
}

export interface QuoteBlock {
  type: "quote";
  content: string;
}

export type Block = HeadingBlock | ParagraphBlock | CodeBlock | ImageBlock | ListBlock | QuoteBlock;

export interface Article {
  id: string;
  url: string;
  title: string;
  blocks: Block[];
  fetched_at: string;
}

export async function fetchArticle(id: string): Promise<Article> {
  const response = await fetch(`${API_BASE}/articles/${id}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error("Article not found");
    }
    throw new Error(`Failed to fetch article: ${response.statusText}`);
  }
  return response.json() as Promise<Article>;
}
