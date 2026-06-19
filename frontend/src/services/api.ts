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

export type Block =
  | HeadingBlock
  | ParagraphBlock
  | CodeBlock
  | ImageBlock
  | ListBlock
  | QuoteBlock;

export type TranslatableBlock =
  | HeadingBlock
  | ParagraphBlock
  | ListBlock
  | QuoteBlock;

export function isTranslatable(block: Block): block is TranslatableBlock {
  return block.type !== "code" && block.type !== "image";
}

export interface Article {
  id: string;
  url: string;
  title: string;
  blocks: Block[];
  fetched_at: string;
}

export interface TranslateResponse {
  article_id: string;
  block_index: number;
  block_type: string;
  translated_text: string;
  cached: boolean;
  error: boolean;
}

export interface BatchTranslateResponse {
  translations: TranslateResponse[];
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

export async function fetchBlockTranslation(
  articleId: string,
  blockIndex: number
): Promise<string> {
  const response = await fetch(`${API_BASE}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ article_id: articleId, block_index: blockIndex }),
  });

  if (!response.ok) {
    throw new Error(`Translation failed: ${response.statusText}`);
  }

  const data = (await response.json()) as TranslateResponse;
  return data.translated_text;
}

export async function fetchBlockTranslationBatch(
  articleId: string,
  blockIndices: number[]
): Promise<string[]> {
  const response = await fetch(`${API_BASE}/translate/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      article_id: articleId,
      block_indices: blockIndices,
    }),
  });

  if (!response.ok) {
    throw new Error(`Batch translation failed: ${response.statusText}`);
  }

  const data = (await response.json()) as BatchTranslateResponse;
  return data.translations.map((t) => t.translated_text);
}
