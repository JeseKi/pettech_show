import { Button, Col, Divider, Empty, Flex, List, Row, Segmented, Space, Statistic, Tag, Typography, theme } from 'antd'
import { FileTextOutlined, FilterOutlined, LinkOutlined } from '@ant-design/icons'
import type { AiwikiResult, AiwikiWikiEntry } from '../../lib/aiwiki'
import EntryDrawer from './EntryDrawer'
import { entryTypeLabel, highlight } from './helpers'
import MarkdownContent from './MarkdownContent'

interface ResultViewProps {
  result: AiwikiResult
  selectedTerm: string | null
  entryFilter: string
  filteredEntries: AiwikiWikiEntry[]
  entriesBySlug: Map<string, AiwikiWikiEntry>
  activeEntry: AiwikiWikiEntry | null
  onOpenKeywordModal: () => void
  onClearTerm: () => void
  onEntryFilterChange: (value: string) => void
  onOpenEntry: (slug: string) => void
  onCloseEntry: () => void
}

export default function ResultView({
  result,
  selectedTerm,
  entryFilter,
  filteredEntries,
  entriesBySlug,
  activeEntry,
  onOpenKeywordModal,
  onClearTerm,
  onEntryFilterChange,
  onOpenEntry,
  onCloseEntry,
}: ResultViewProps) {
  const { token } = theme.useToken()
  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 18,
  }

  return (
    <>
      <Flex vertical gap={16}>
        <section id="overview" style={sectionStyle}>
          <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
            <Typography.Title level={3} style={{ margin: 0 }}>
              {result.wiki_home?.title ?? 'AI Wiki'}
            </Typography.Title>
            <Space wrap>
              {selectedTerm && <Tag closable onClose={onClearTerm}>筛选：{selectedTerm}</Tag>}
              <Button icon={<FilterOutlined />} onClick={onOpenKeywordModal}>
                关键词高亮筛选
              </Button>
            </Space>
          </Flex>
          <Divider />
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} md={6}><Statistic title="素材" value={Number(result.summary.material_count ?? 0)} /></Col>
            <Col xs={12} md={6}><Statistic title="词条" value={Number(result.summary.wiki_entry_count ?? 0)} /></Col>
            <Col xs={12} md={6}><Statistic title="关键词" value={Number(result.summary.search_intent_count ?? 0)} /></Col>
            <Col xs={12} md={6}><Statistic title="选题" value={Number(result.summary.topic_count ?? 0)} /></Col>
          </Row>
          {result.wiki_home?.body_markdown ? (
            <MarkdownContent
              markdown={result.wiki_home.body_markdown}
              entriesBySlug={entriesBySlug}
              onOpenEntry={onOpenEntry}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 Wiki 首页" />
          )}
        </section>

        <section id="entries" style={sectionStyle}>
          <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
            <Typography.Title level={4} style={{ margin: 0 }}>词条预览</Typography.Title>
            <Segmented
              value={entryFilter}
              onChange={(value) => onEntryFilterChange(String(value))}
              options={['全部', '热点', '痛点', '解决方案', '选题', '搜索入口', '文章']}
            />
          </Flex>
          <List
            grid={{ gutter: 12, xs: 1, md: 2 }}
            dataSource={filteredEntries}
            locale={{ emptyText: '暂无词条' }}
            style={{ marginTop: 14 }}
            renderItem={(entry) => (
              <List.Item>
                <EntryCard
                  entry={entry}
                  selectedTerm={selectedTerm}
                  onOpenEntry={onOpenEntry}
                />
              </List.Item>
            )}
          />
        </section>
      </Flex>

      <EntryDrawer
        entry={activeEntry}
        entriesBySlug={entriesBySlug}
        onClose={onCloseEntry}
        onOpenEntry={onOpenEntry}
      />
    </>
  )
}

function EntryCard({
  entry,
  selectedTerm,
  onOpenEntry,
}: {
  entry: AiwikiWikiEntry
  selectedTerm: string | null
  onOpenEntry: (slug: string) => void
}) {
  const { token } = theme.useToken()
  const tags = entry.frontmatter.tags
  const tagList = Array.isArray(tags) ? tags.filter((item) => typeof item === 'string') : []
  return (
    <button
      type="button"
      onClick={() => onOpenEntry(entry.slug)}
      style={{
        width: '100%',
        height: '100%',
        textAlign: 'left',
        background: token.colorBgElevated,
        border: `1px solid ${token.colorBorderSecondary}`,
        borderRadius: 8,
        padding: 14,
        cursor: 'pointer',
      }}
    >
      <Flex vertical gap={10}>
        <Space wrap>
          <Tag color="blue">{entryTypeLabel(entry.type)}</Tag>
          {entry.created && <Tag>创建：{entry.created}</Tag>}
          {entry.updated && <Tag>更新：{entry.updated}</Tag>}
        </Space>
        <Typography.Text strong>{highlight(entry.title, selectedTerm)}</Typography.Text>
        <Typography.Paragraph type="secondary" ellipsis={{ rows: 3 }} style={{ margin: 0 }}>
          {highlight(entry.excerpt || entry.sections[0]?.content || '', selectedTerm)}
        </Typography.Paragraph>
        <Space wrap>
          <Typography.Text type="secondary"><FileTextOutlined /> {entry.path}</Typography.Text>
          {tagList.slice(0, 4).map((tag) => <Tag key={tag}>{tag}</Tag>)}
        </Space>
        {entry.reference_links.length > 0 && (
          <Space wrap>
            {entry.reference_links.slice(0, 5).map((ref) => (
              <Tag key={ref.slug} icon={<LinkOutlined />}>{ref.title}</Tag>
            ))}
          </Space>
        )}
      </Flex>
    </button>
  )
}
