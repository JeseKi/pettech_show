import { Drawer, Flex, Space, Tag, Typography } from 'antd'
import { LinkOutlined } from '@ant-design/icons'
import type { AiwikiWikiEntry } from '../../lib/aiwiki'
import { entryTypeLabel } from './helpers'
import MarkdownContent from './MarkdownContent'

interface EntryDrawerProps {
  entry: AiwikiWikiEntry | null
  entriesBySlug: Map<string, AiwikiWikiEntry>
  onClose: () => void
  onOpenEntry: (slug: string) => void
}

export default function EntryDrawer({
  entry,
  entriesBySlug,
  onClose,
  onOpenEntry,
}: EntryDrawerProps) {
  const tags = entry?.frontmatter.tags
  const tagList = Array.isArray(tags) ? tags.filter((item) => typeof item === 'string') : []

  return (
    <Drawer
      width={720}
      open={Boolean(entry)}
      onClose={onClose}
      title={entry?.title ?? 'Wiki 词条'}
    >
      {entry && (
        <Flex vertical gap={16}>
          <Space wrap>
            <Tag color="blue">{entryTypeLabel(entry.type)}</Tag>
            {entry.created && <Tag>创建：{entry.created}</Tag>}
            {entry.updated && <Tag>更新：{entry.updated}</Tag>}
            <Typography.Text type="secondary">{entry.path}</Typography.Text>
          </Space>

          {tagList.length > 0 && (
            <Space wrap>
              {tagList.map((tag) => <Tag key={tag}>{tag}</Tag>)}
            </Space>
          )}

          <MarkdownContent
            markdown={entry.body_markdown}
            entriesBySlug={entriesBySlug}
            onOpenEntry={onOpenEntry}
          />

          {entry.reference_links.length > 0 && (
            <Flex vertical gap={8}>
              <Typography.Text type="secondary">引用词条</Typography.Text>
              <Space wrap>
                {entry.reference_links.map((ref) => (
                  <Tag
                    key={ref.slug}
                    icon={<LinkOutlined />}
                    style={{ cursor: 'pointer' }}
                    onClick={() => onOpenEntry(ref.slug)}
                  >
                    {ref.title}
                  </Tag>
                ))}
              </Space>
            </Flex>
          )}
        </Flex>
      )}
    </Drawer>
  )
}
