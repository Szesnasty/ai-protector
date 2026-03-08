import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Configure marked for chat-style rendering
marked.setOptions({
  breaks: true, // Convert \n to <br>
  gfm: true, // GitHub Flavored Markdown
})

/**
 * Render markdown string to sanitized HTML.
 * Used for chat message content that may contain **bold**, *italic*,
 * `code`, lists, headers, etc.
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  const raw = marked.parse(text, { async: false }) as string
  return DOMPurify.sanitize(raw, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'b', 'i', 'code', 'pre',
      'ul', 'ol', 'li', 'blockquote', 'h1', 'h2', 'h3', 'h4',
      'a', 'span', 'del', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
  })
}
