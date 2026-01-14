/**
 * SafeMarkdown Component
 *
 * Renders Markdown content with XSS sanitization.
 * Uses react-markdown for parsing and DOMPurify for HTML sanitization.
 */

import ReactMarkdown from 'react-markdown';
import DOMPurify from 'dompurify';
import { cn } from '@/lib/utils';

// =============================================================================
// DOMPurify Configuration
// =============================================================================

/**
 * Configure DOMPurify to strip dangerous content while preserving safe formatting.
 */
const DOMPURIFY_CONFIG = {
  // Allow safe HTML tags
  ALLOWED_TAGS: [
    'p', 'br', 'strong', 'em', 'u', 's', 'code', 'pre',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li',
    'blockquote',
    'a',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
  ],
  // Allow safe attributes
  ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
  // Force all links to open in new tab with security attributes
  ADD_ATTR: ['target', 'rel'],
  // Forbid dangerous protocols
  ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
  // Return string instead of TrustedHTML
  RETURN_TRUSTED_TYPE: false as const,
};

/**
 * Sanitize raw HTML/text content
 */
function sanitizeContent(content: string): string {
  return DOMPurify.sanitize(content, DOMPURIFY_CONFIG) as string;
}

// =============================================================================
// Component Props
// =============================================================================

interface SafeMarkdownProps {
  /** The markdown content to render */
  content: string;
  /** Additional CSS classes */
  className?: string;
}

// =============================================================================
// Component
// =============================================================================

/**
 * Renders markdown content safely with XSS protection.
 *
 * Features:
 * - Sanitizes all HTML using DOMPurify
 * - Renders code blocks with syntax highlighting styles
 * - Opens links in new tabs with rel="noopener noreferrer"
 * - Strips script tags and event handlers
 *
 * @example
 * ```tsx
 * <SafeMarkdown content="**Bold** and `code`" />
 * ```
 */
export function SafeMarkdown({ content, className }: SafeMarkdownProps) {
  // Pre-sanitize content to remove any dangerous HTML before markdown parsing
  const sanitizedContent = sanitizeContent(content);

  return (
    <div className={cn('prose prose-sm dark:prose-invert max-w-none', className)}>
      <ReactMarkdown
        components={{
          // Custom code block rendering
          code({ className: codeClassName, children, ...props }) {
            const isInline = !codeClassName;

            if (isInline) {
              return (
                <code
                  className="rounded bg-muted px-1.5 py-0.5 text-sm font-mono"
                  {...props}
                >
                  {children}
                </code>
              );
            }

            return (
              <pre className="overflow-x-auto rounded-lg bg-muted p-3">
                <code className={cn('text-sm font-mono', codeClassName)} {...props}>
                  {children}
                </code>
              </pre>
            );
          },
          // Secure link rendering
          a({ href, children, ...props }) {
            // Sanitize href to prevent javascript: URLs
            const safeHref = href && !href.toLowerCase().startsWith('javascript:')
              ? href
              : '#';

            return (
              <a
                href={safeHref}
                target="_blank"
                rel="noopener noreferrer"
                className="text-aurora-400 hover:underline"
                {...props}
              >
                {children}
              </a>
            );
          },
          // Paragraph styling
          p({ children, ...props }) {
            return (
              <p className="mb-2 last:mb-0" {...props}>
                {children}
              </p>
            );
          },
          // List styling
          ul({ children, ...props }) {
            return (
              <ul className="mb-2 list-disc pl-4" {...props}>
                {children}
              </ul>
            );
          },
          ol({ children, ...props }) {
            return (
              <ol className="mb-2 list-decimal pl-4" {...props}>
                {children}
              </ol>
            );
          },
        }}
      >
        {sanitizedContent}
      </ReactMarkdown>
    </div>
  );
}

export default SafeMarkdown;
