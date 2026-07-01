import { useState } from 'react'
import { Button, Col, Divider, Empty, Flex, List, Row, Segmented, Space, Statistic, Tag, Typography, theme } from 'antd'
import { FileTextOutlined, FilterOutlined, LinkOutlined } from '@ant-design/icons'
import type { AiwikiResult, AiwikiWikiEntry } from '../../lib/aiwiki'
import EntryDrawer from './EntryDrawer'
import { entryTypeLabel, highlight } from './helpers'
import KnowledgeGraph from './KnowledgeGraph'
import MarkdownContent from './MarkdownContent'

interface ResultViewProps {
  result: AiwikiResult
  selectedTerms: string[]
  entryFilter: string
  entryFilterOptions?: string[]
  summaryItems?: Array<{ title: string; value: number }>
  filteredEntries: AiwikiWikiEntry[]
  entriesBySlug: Map<string, AiwikiWikiEntry>
  activeEntry: AiwikiWikiEntry | null
  onOpenKeywordModal: () => void
  onEntryFilterChange: (value: string) => void
  onOpenEntry: (slug: string) => void
  onCloseEntry: () => void
}

export default function ResultView({
  result,
  selectedTerms,
  entryFilter,
  entryFilterOptions = ['全部', '热点', '痛点', '解决方案', '选题', '搜索入口', '文章', '实体', '概念', '对比', '问答', '笔记'],
  summaryItems,
  filteredEntries,
  entriesBySlug,
  activeEntry,
  onOpenKeywordModal,
  onEntryFilterChange,
  onOpenEntry,
  onCloseEntry,
}: ResultViewProps) {
  const { token } = theme.useToken()
  const [mainView, setMainView] = useState<'index' | 'graph'>('graph')
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
              {result.wiki_home?.title ?? '内容资产库'}
            </Typography.Title>
            <Space wrap>
              <Tag>
                {selectedTerms.length === result.highlight_terms.length
                  ? '高亮：全部关键词'
                  : selectedTerms.length
                    ? `高亮：${selectedTerms.length} 个关键词`
                    : '高亮：未启用'}
              </Tag>
              <Button icon={<FilterOutlined />} onClick={onOpenKeywordModal}>
                关键词高亮筛选
              </Button>
              <Segmented
                value={mainView}
                onChange={(value) => setMainView(value as 'index' | 'graph')}
                options={[
                  { label: '索引', value: 'index' },
                  { label: '知识图谱', value: 'graph' },
                ]}
              />
            </Space>
          </Flex>
          <Divider />
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            {(summaryItems ?? [
              { title: '素材', value: Number(result.summary.material_count ?? 0) },
              { title: '词条', value: Number(result.summary.wiki_entry_count ?? 0) },
              { title: '关键词', value: Number(result.summary.search_intent_count ?? 0) },
              { title: '选题', value: Number(result.summary.topic_count ?? 0) },
            ]).map((item) => (
              <Col key={item.title} xs={12} md={6}><Statistic title={item.title} value={item.value} /></Col>
            ))}
          </Row>
          {mainView === 'graph' ? (
            <KnowledgeGraph result={result} onOpenEntry={onOpenEntry} />
          ) : result.wiki_home?.body_markdown ? (
            <MarkdownContent
              markdown={result.wiki_home.body_markdown}
              entriesBySlug={entriesBySlug}
              highlightTerms={selectedTerms}
              onOpenEntry={onOpenEntry}
            />
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无知识库首页" />
          )}
        </section>

        <section id="entries" style={sectionStyle}>
          <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
            <Typography.Title level={4} style={{ margin: 0 }}>词条预览</Typography.Title>
            <Segmented
              value={entryFilter}
              onChange={(value) => onEntryFilterChange(String(value))}
              options={entryFilterOptions}
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
                  selectedTerms={selectedTerms}
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
        highlightTerms={selectedTerms}
        onClose={onCloseEntry}
        onOpenEntry={onOpenEntry}
      />
    </>
  )
}

function EntryCard({
  entry,
  selectedTerms,
  onOpenEntry,
}: {
  entry: AiwikiWikiEntry
  selectedTerms: string[]
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
        <Typography.Text strong>{highlight(entry.title, selectedTerms)}</Typography.Text>
        <Typography.Paragraph type="secondary" ellipsis={{ rows: 3 }} style={{ margin: 0 }}>
          {highlight(entry.excerpt || entry.sections[0]?.content || '', selectedTerms)}
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
