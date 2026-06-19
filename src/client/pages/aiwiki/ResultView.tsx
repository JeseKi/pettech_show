import { Button, Col, Divider, Flex, List, Row, Segmented, Space, Statistic, Table, Tag, Typography, theme } from 'antd'
import { FileTextOutlined, FilterOutlined, LinkOutlined, SearchOutlined } from '@ant-design/icons'
import type { AiwikiResult, AiwikiWikiEntry } from '../../lib/aiwiki'
import { descriptionOf, highlight, priorityColor, textOf, titleOf, entryTypeLabel } from './helpers'

interface ResultViewProps {
  result: AiwikiResult
  selectedTerm: string | null
  entryFilter: string
  filteredSearchIntents: Array<Record<string, unknown>>
  filteredEntries: AiwikiWikiEntry[]
  onOpenKeywordModal: () => void
  onClearTerm: () => void
  onEntryFilterChange: (value: string) => void
}

export default function ResultView({
  result,
  selectedTerm,
  entryFilter,
  filteredSearchIntents,
  filteredEntries,
  onOpenKeywordModal,
  onClearTerm,
  onEntryFilterChange,
}: ResultViewProps) {
  const { token } = theme.useToken()
  const sectionStyle = {
    background: token.colorBgContainer,
    border: `1px solid ${token.colorBorderSecondary}`,
    borderRadius: 8,
    padding: 18,
  }

  return (
    <Flex vertical gap={16}>
      <section id="materials" style={sectionStyle}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
          <Typography.Title level={3} style={{ margin: 0 }}>AI Wiki 资产</Typography.Title>
          <Space wrap>
            {selectedTerm && <Tag closable onClose={onClearTerm}>筛选：{selectedTerm}</Tag>}
            <Button icon={<FilterOutlined />} onClick={onOpenKeywordModal}>
              关键词高亮筛选
            </Button>
          </Space>
        </Flex>
        <Divider />
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}><Statistic title="素材" value={Number(result.summary.material_count ?? 0)} /></Col>
          <Col xs={12} md={6}><Statistic title="词条" value={Number(result.summary.wiki_entry_count ?? 0)} /></Col>
          <Col xs={12} md={6}><Statistic title="关键词" value={Number(result.summary.search_intent_count ?? 0)} /></Col>
          <Col xs={12} md={6}><Statistic title="选题" value={Number(result.summary.topic_count ?? 0)} /></Col>
        </Row>
      </section>

      <AssetSection id="hotspot" title="热点" items={result.hotspots} selectedTerm={selectedTerm} />
      <AssetSection id="pain_point" title="痛点" items={result.pain_points} selectedTerm={selectedTerm} />
      <AssetSection id="solution" title="解决方案" items={result.solutions} selectedTerm={selectedTerm} />

      <section id="topic" style={sectionStyle}>
        <Typography.Title level={4} style={{ marginTop: 0 }}>选题矩阵</Typography.Title>
        <Row gutter={[12, 12]}>
          {result.topics.map((topic, index) => (
            <Col key={`${titleOf(topic)}-${index}`} xs={24} md={12}>
              <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 14, height: '100%' }}>
                <Space direction="vertical" size={8}>
                  <Tag color="purple">{textOf(topic.status) || 'idea'}</Tag>
                  <Typography.Text strong>{highlight(titleOf(topic), selectedTerm)}</Typography.Text>
                  {descriptionOf(topic) && <Typography.Paragraph type="secondary" style={{ margin: 0 }}>{highlight(descriptionOf(topic), selectedTerm)}</Typography.Paragraph>}
                </Space>
              </div>
            </Col>
          ))}
        </Row>
      </section>

      <section id="search_intent" style={sectionStyle}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
          <Typography.Title level={4} style={{ margin: 0 }}>搜索入口与关键词池</Typography.Title>
          <Tag icon={<SearchOutlined />}>{filteredSearchIntents.length} 条</Tag>
        </Flex>
        <Table
          size="small"
          rowKey={(record, index) => `${record['关键词']}-${index}`}
          dataSource={filteredSearchIntents}
          pagination={{ pageSize: 8 }}
          scroll={{ x: 900 }}
          columns={[
            {
              title: '意图',
              dataIndex: '意图类型',
              width: 110,
              render: (value) => <Tag>{String(value ?? '-')}</Tag>,
            },
            {
              title: '关键词',
              dataIndex: '关键词',
              width: 220,
              render: (value) => <Typography.Text strong>{highlight(String(value ?? ''), selectedTerm)}</Typography.Text>,
            },
            {
              title: '搜索意图',
              dataIndex: '搜索意图',
              render: (value) => highlight(String(value ?? ''), selectedTerm),
            },
            {
              title: '优先级',
              dataIndex: '优先级',
              width: 90,
              render: (value) => <Tag color={priorityColor(value)}>{String(value ?? '-')}</Tag>,
            },
          ]}
        />
      </section>

      <section style={sectionStyle}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={12}>
          <Typography.Title level={4} style={{ margin: 0 }}>Wiki 词条</Typography.Title>
          <Segmented
            value={entryFilter}
            onChange={(value) => onEntryFilterChange(String(value))}
            options={['全部', '热点', '痛点', '解决方案', '选题', '搜索入口']}
          />
        </Flex>
        <List
          dataSource={filteredEntries}
          locale={{ emptyText: '暂无词条' }}
          renderItem={(entry) => (
            <List.Item id={entry.slug}>
              <Flex vertical gap={8} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color="blue">{entryTypeLabel(entry.type)}</Tag>
                  <Typography.Text strong>{highlight(entry.title, selectedTerm)}</Typography.Text>
                  <Typography.Text type="secondary"><FileTextOutlined /> {entry.path}</Typography.Text>
                </Space>
                {entry.sections.slice(0, 2).map((section) => (
                  <div key={section.title}>
                    <Typography.Text type="secondary">{section.title}</Typography.Text>
                    <Typography.Paragraph style={{ margin: '4px 0 0' }}>
                      {highlight(section.content, selectedTerm)}
                    </Typography.Paragraph>
                  </div>
                ))}
                {entry.references.length > 0 && (
                  <Space wrap>
                    {entry.references.slice(0, 8).map((ref) => (
                      <Tag key={ref} icon={<LinkOutlined />}>{ref}</Tag>
                    ))}
                  </Space>
                )}
              </Flex>
            </List.Item>
          )}
        />
      </section>
    </Flex>
  )
}

function AssetSection({ id, title, items, selectedTerm }: { id: string; title: string; items: Array<Record<string, unknown>>; selectedTerm: string | null }) {
  const { token } = theme.useToken()
  return (
    <section id={id} style={{ background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 18 }}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>{title}</Typography.Title>
      <Row gutter={[12, 12]}>
        {items.map((item, index) => (
          <Col key={`${titleOf(item)}-${index}`} xs={24} md={12} xl={8}>
            <div style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, padding: 14, height: '100%' }}>
              <Typography.Text strong>{highlight(titleOf(item), selectedTerm)}</Typography.Text>
              {descriptionOf(item) && (
                <Typography.Paragraph type="secondary" style={{ margin: '8px 0 0' }}>
                  {highlight(descriptionOf(item), selectedTerm)}
                </Typography.Paragraph>
              )}
            </div>
          </Col>
        ))}
      </Row>
    </section>
  )
}
