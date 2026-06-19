export type TranslatableBlock =
  | HeadingBlock
  | ParagraphBlock
  | ListBlock
  | QuoteBlock;

const TRANSLATABLE_TYPES = new Set<string>([
  "heading",
  "paragraph",
  "list",
  "quote",
]);

export function isTranslatable(block: Block): block is TranslatableBlock {
  return TRANSLATABLE_TYPES.has(block.type);
}
