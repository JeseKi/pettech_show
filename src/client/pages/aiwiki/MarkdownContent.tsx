import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Typography, theme } from 'antd'
import type { MouseEvent } from 'react'
import type { AiwikiWikiEntry } from '../../lib/aiwiki'

interface MarkdownContentProps {
  markdown: string
  entriesBySlug: Map<string, AiwikiWikiEntry>
  onOpenEntry: (slug: string) => void
}

export default function MarkdownContent({
  markdown,
  entriesBySlug,
  onOpenEntry,
}: MarkdownContentProps) {
  const { token } = theme.useToken()
  let headingIndex = 0
  const nextHeadingId = () => `heading-${++headingIndex}`
  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith('#wiki-entry-')) {
        const slug = decodeURIComponent(href.slice('#wiki-entry-'.length))
        const handleClick = (event: MouseEvent<HTMLElement>) => {
          event.preventDefault()
          event.stopPropagation()
          onOpenEntry(slug)
        }
        return (
          <Typography.Link href={href} onClick={handleClick}>
            {children}
          </Typography.Link>
        )
      }
      return (
        <Typography.Link href={href} target="_blank" rel="noreferrer">
          {children}
        </Typography.Link>
      )
    },
    h1: ({ children }) => (
      <Typography.Title id={nextHeadingId()} level={3} style={{ marginTop: 0 }}>
        {children}
      </Typography.Title>
    ),
    h2: ({ children }) => (
      <Typography.Title id={nextHeadingId()} level={4} style={{ marginTop: 22 }}>
        {children}
      </Typography.Title>
    ),
    h3: ({ children }) => (
      <Typography.Title id={nextHeadingId()} level={5} style={{ marginTop: 18 }}>
        {children}
      </Typography.Title>
    ),
    p: ({ children }) => (
      <Typography.Paragraph style={{ lineHeight: 1.8 }}>
        {children}
      </Typography.Paragraph>
    ),
    table: ({ children }) => (
      <div style={{ overflowX: 'auto', margin: '12px 0' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 560 }}>
          {children}
        </table>
      </div>
    ),
    th: ({ children }) => (
      <th style={{ border: `1px solid ${token.colorBorderSecondary}`, padding: 8, background: token.colorFillAlter, textAlign: 'left' }}>
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td style={{ border: `1px solid ${token.colorBorderSecondary}`, padding: 8, verticalAlign: 'top' }}>
        {children}
      </td>
    ),
  }

  return (
    <div style={{ color: token.colorText }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {renderWikiLinks(markdown, entriesBySlug)}
      </ReactMarkdown>
    </div>
  )
}

function renderWikiLinks(markdown: string, entriesBySlug: Map<string, AiwikiWikiEntry>) {
  return markdown.replace(/\[\[([^\]]+)\]\]/g, (_, raw: string) => {
    const [slug, explicitLabel] = splitWikiLink(raw)
    const label = explicitLabel || entriesBySlug.get(slug)?.title || slug
    return `[${escapeMarkdownLabel(label)}](#wiki-entry-${encodeURIComponent(slug)})`
  })
}

function splitWikiLink(raw: string): [string, string | null] {
  const normalized = raw.replace(/\\\|/g, '|')
  const index = normalized.indexOf('|')
  if (index < 0) return [normalized.trim(), null]
  return [normalized.slice(0, index).trim(), normalized.slice(index + 1).trim() || null]
}

function escapeMarkdownLabel(label: string) {
  return label.replaceAll('[', '\\[').replaceAll(']', '\\]')
}
