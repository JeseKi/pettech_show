import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Typography, theme } from 'antd'
import { Children, cloneElement, isValidElement, type MouseEvent, type ReactElement, type ReactNode } from 'react'
import type { AiwikiWikiEntry } from '../../lib/aiwiki'
import { highlight } from './helpers'

interface MarkdownContentProps {
  markdown: string
  entriesBySlug: Map<string, AiwikiWikiEntry>
  highlightTerms: string[]
  onOpenEntry: (slug: string) => void
}

export default function MarkdownContent({
  markdown,
  entriesBySlug,
  highlightTerms,
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
            {renderHighlightedChildren(children, highlightTerms)}
          </Typography.Link>
        )
      }
      return (
        <Typography.Link href={href} target="_blank" rel="noreferrer">
          {renderHighlightedChildren(children, highlightTerms)}
        </Typography.Link>
      )
    },
    h1: ({ children }) => (
      <Typography.Title id={nextHeadingId()} level={3} style={{ marginTop: 0 }}>
        {renderHighlightedChildren(children, highlightTerms)}
      </Typography.Title>
    ),
    h2: ({ children }) => (
      <Typography.Title id={nextHeadingId()} level={4} style={{ marginTop: 22 }}>
        {renderHighlightedChildren(children, highlightTerms)}
      </Typography.Title>
    ),
    h3: ({ children }) => (
      <Typography.Title id={nextHeadingId()} level={5} style={{ marginTop: 18 }}>
        {renderHighlightedChildren(children, highlightTerms)}
      </Typography.Title>
    ),
    p: ({ children }) => (
      <Typography.Paragraph style={{ lineHeight: 1.8 }}>
        {renderHighlightedChildren(children, highlightTerms)}
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
        {renderHighlightedChildren(children, highlightTerms)}
      </th>
    ),
    td: ({ children }) => (
      <td style={{ border: `1px solid ${token.colorBorderSecondary}`, padding: 8, verticalAlign: 'top' }}>
        {renderHighlightedChildren(children, highlightTerms)}
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

function renderHighlightedChildren(children: ReactNode, terms: string[]): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child === 'string') return highlight(child, terms)
    if (!isValidElement(child)) return child
    const element = child as ReactElement<{ children?: ReactNode }>
    return cloneElement(element, {
      children: renderHighlightedChildren(element.props.children, terms),
    })
  })
}
