import DOMPurify from 'dompurify';

/**
 * Sanitize markdown content for safe rendering
 * Uses DOMPurify with a strict configuration
 */
export function sanitizeMarkdown(markdown: string): string {
  // DOMPurify requires HTML input, so we need to convert markdown to HTML first
  // For now, we'll do a simple markdown-to-HTML conversion then sanitize
  const html = markdownToHtml(markdown);
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr',
      'strong', 'em', 'u', 's', 'code', 'pre',
      'ul', 'ol', 'li',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'blockquote', 'a', 'span', 'div'
    ],
    ALLOWED_ATTR: ['href', 'class', 'id', 'style'],
    ALLOW_DATA_ATTR: false,
    FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button'],
    FORBID_ATTR: ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus', 'onblur'],
    KEEP_CONTENT: true,
  });
}

/**
 * Simple markdown to HTML converter for basic markdown elements
 * In production, consider using a proper markdown parser like marked or markdown-it
 */
function markdownToHtml(markdown: string): string {
  return markdown
    // Headers
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Code blocks
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Horizontal rules
    .replace(/^---$/gim, '<hr>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    // Tables - basic conversion
    .replace(/^\|(.*)\|$/gim, (match) => {
      const cells = match.split('|').slice(1, -1).map(c => c.trim());
      const isHeader = match.includes('---');
      if (isHeader) return '';
      return `<tr>${cells.map(c => `<td>${c}</td>`).join('')}</tr>`;
    })
    // Newlines to paragraphs
    .split('\n\n')
    .map(block => block.trim())
    .filter(block => block.length > 0)
    .map(block => {
      if (block.startsWith('<')) return block;
      return `<p>${block.replace(/\n/g, '<br>')}</p>`;
    })
    .join('\n');
}

/**
 * Sanitize any HTML string
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'p', 'br', 'hr',
      'strong', 'em', 'u', 's', 'code', 'pre',
      'ul', 'ol', 'li',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'blockquote', 'a', 'span', 'div'
    ],
    ALLOWED_ATTR: ['href', 'class', 'id', 'style'],
    FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button'],
    FORBID_ATTR: ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus', 'onblur'],
  });
}