import { useCallback, useEffect, useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import { Alert, Button, Card, Col, DatePicker, Empty, Flex, Row, Segmented, Space, Statistic, Table, Tabs, Tag, Typography } from 'antd'
import type { TableColumnsType, TabsProps } from 'antd'
import { BarChartOutlined, ReloadOutlined } from '@ant-design/icons'
import { Column, Line, Pie } from '@ant-design/charts'
import dayjs, { type Dayjs } from 'dayjs'
import {
  getMonitoringDetail,
  getMonitoringOverview,
  type BreakdownItem,
  type MetricCard,
  type MonitoringDetail,
  type MonitoringModule,
  type MonitoringOverview,
  type MonitoringQuery,
  type TrendPoint,
} from '../../lib/adminMonitoring'
import { resolveErrorMessage } from '../../lib/errorMessage'

const { RangePicker } = DatePicker

type RangeValue = [Dayjs, Dayjs]
type RangeKind = 'today' | 'last7' | null

const DETAIL_MODULES = [
  { key: 'aiwiki', label: '数据资产' },
  { key: 'seed-matrix', label: '选题生成' },
  { key: 'daily-writer', label: '长文生成' },
  { key: 'scripts', label: '脚本创作' },
  { key: 'capabilities', label: '能力任务' },
  { key: 'agent-skills', label: 'Skill' },
  { key: 'interactive-movie', label: '互动电影' },
  { key: 'users', label: '用户' },
  { key: 'chat', label: '智能体聊天' },
]

const DEFAULT_RANGE: RangeValue = [dayjs().subtract(7, 'day').startOf('day'), dayjs().endOf('day')]

const metricTagStyle: CSSProperties = {
  maxWidth: '100%',
  whiteSpace: 'normal',
  wordBreak: 'break-word',
  lineHeight: 1.45,
}

function queryFromRange(range: RangeValue): MonitoringQuery {
  return {
    startAt: range[0].startOf('day').toISOString(),
    endAt: range[1].endOf('day').toISOString(),
    tz: 'Asia/Shanghai',
  }
}

function formatNumber(value: number | null | undefined): number {
  return Number(value ?? 0)
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function formatMetricTagValue(value: number | null | undefined, unit: string): string {
  const normalizedUnit = unit ? ` ${unit}` : ''
  return `${formatNumber(value)}${normalizedUnit}`
}

function normalizeRange(range: RangeValue): RangeValue {
  return [range[0].startOf('day'), range[1].endOf('day')]
}

function formatRangeLabel(range: RangeValue): string {
  const [start, end] = normalizeRange(range)
  const today = dayjs()
  if (end.isSame(today, 'day')) {
    if (start.isSame(end, 'day')) {
      return '今天新增'
    }
    const days = Math.max(1, end.startOf('day').diff(start.startOf('day'), 'day'))
    return `近${days}天新增`
  }
  const dateFormat = start.year() === end.year() ? 'M.D' : 'YYYY.M.D'
  if (start.isSame(end, 'day')) {
    return `${start.format(dateFormat)} 新增`
  }
  return `${start.format(dateFormat)} 至 ${end.format(dateFormat)} 新增`
}

function rangeKind(range: RangeValue): RangeKind {
  const [start, end] = normalizeRange(range)
  const today = dayjs()
  if (!end.isSame(today, 'day')) {
    return null
  }
  if (start.isSame(end, 'day')) {
    return 'today'
  }
  if (end.startOf('day').diff(start.startOf('day'), 'day') === 7) {
    return 'last7'
  }
  return null
}

export default function AdminMonitoringPage() {
  const [range, setRange] = useState<RangeValue>(DEFAULT_RANGE)
  const [overview, setOverview] = useState<MonitoringOverview | null>(null)
  const [detail, setDetail] = useState<MonitoringDetail | null>(null)
  const [activeKey, setActiveKey] = useState('overview')
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const query = useMemo(() => queryFromRange(range), [range])
  const rangeLabel = useMemo(() => formatRangeLabel(range), [range])
  const selectedRangeKind = useMemo(() => rangeKind(range), [range])

  const loadOverview = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getMonitoringOverview(query)
      setOverview(data)
      setError(null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [query])

  const loadDetail = useCallback(async (moduleKey: string) => {
    if (moduleKey === 'overview') return
    setDetailLoading(true)
    try {
      const data = await getMonitoringDetail(moduleKey, query)
      setDetail(data)
      setError(null)
    } catch (err) {
      setError(resolveErrorMessage(err))
    } finally {
      setDetailLoading(false)
    }
  }, [query])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  useEffect(() => {
    if (activeKey !== 'overview') {
      void loadDetail(activeKey)
    }
  }, [activeKey, loadDetail])

  const tabItems = useMemo<TabsProps['items']>(() => [
    {
      key: 'overview',
      label: '总览',
      children: (
        <OverviewContent
          loading={loading}
          overview={overview}
          rangeLabel={rangeLabel}
          rangeKind={selectedRangeKind}
          onOpenModule={setActiveKey}
        />
      ),
    },
    ...DETAIL_MODULES.map((item) => ({
      key: item.key,
      label: item.label,
      children: (
        <ModuleDetail
          loading={detailLoading}
          module={activeKey === item.key ? detail : overview?.modules.find((module) => module.key === item.key) ?? null}
          rangeLabel={rangeLabel}
          rangeKind={selectedRangeKind}
        />
      ),
    })),
  ], [activeKey, detail, detailLoading, loading, overview, rangeLabel, selectedRangeKind])

  return (
    <Flex vertical gap={16}>
      <Flex align="center" justify="space-between" gap={12} wrap="wrap">
        <Space direction="vertical" size={0}>
          <Typography.Title level={4} style={{ margin: 0 }}>监控概览</Typography.Title>
          <Typography.Text type="secondary">企业数据资产、内容生产、脚本、Skill 和智能体使用情况。</Typography.Text>
        </Space>
        <Space wrap>
          <RangePicker
            allowClear={false}
            value={range}
            format="YYYY-MM-DD"
            presets={[
              { label: '今天', value: [dayjs().startOf('day'), dayjs().endOf('day')] },
              { label: '近 7 天', value: [dayjs().subtract(7, 'day').startOf('day'), dayjs().endOf('day')] },
              { label: '近 30 日', value: [dayjs().subtract(30, 'day').startOf('day'), dayjs().endOf('day')] },
              { label: '近 90 日', value: [dayjs().subtract(90, 'day').startOf('day'), dayjs().endOf('day')] },
            ]}
            onChange={(next) => {
              if (next?.[0] && next?.[1]) {
                setRange(normalizeRange([next[0], next[1]]))
              }
            }}
          />
          <Button icon={<ReloadOutlined />} onClick={() => activeKey === 'overview' ? void loadOverview() : void loadDetail(activeKey)}>
            刷新
          </Button>
        </Space>
      </Flex>
      {error && <Alert type="error" showIcon closable message={error} onClose={() => setError(null)} />}
      <Tabs activeKey={activeKey} items={tabItems} onChange={setActiveKey} />
    </Flex>
  )
}

function OverviewContent({
  loading,
  overview,
  rangeLabel,
  rangeKind,
  onOpenModule,
}: {
  loading: boolean
  overview: MonitoringOverview | null
  rangeLabel: string
  rangeKind: RangeKind
  onOpenModule: (key: string) => void
}) {
  if (!overview && !loading) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无监控数据" />
  }

  return (
    <Flex vertical gap={16}>
      <MetricGrid cards={overview?.cards ?? []} loading={loading} rangeLabel={rangeLabel} rangeKind={rangeKind} />
      <TrendPanel title="企业总趋势" data={overview?.trends ?? []} loading={loading} />
      <Row gutter={[16, 16]}>
        {loading && !overview ? Array.from({ length: 6 }).map((_, index) => (
          <Col key={`module-loading-${index}`} xs={24} lg={12} xl={8}>
            <Card title="加载中" loading styles={{ body: { minHeight: 260 } }} />
          </Col>
        )) : (overview?.modules ?? []).map((module) => (
          <Col key={module.key} xs={24} lg={12} xl={8}>
            <Card
              title={module.title}
              loading={loading}
              extra={loading ? null : <Button type="link" onClick={() => onOpenModule(module.key)}>详情</Button>}
              styles={{ body: { minHeight: 260 } }}
            >
              <Flex vertical gap={12}>
                <MetricGrid cards={module.cards.slice(0, 2)} compact />
                <MiniBreakdown module={module} />
              </Flex>
            </Card>
          </Col>
        ))}
      </Row>
    </Flex>
  )
}

function ModuleDetail({
  loading,
  module,
  rangeLabel,
  rangeKind,
}: {
  loading: boolean
  module: MonitoringModule | null
  rangeLabel: string
  rangeKind: RangeKind
}) {
  const [breakdownKey, setBreakdownKey] = useState<string | null>(null)
  const breakdownKeys = Object.keys(module?.breakdowns ?? {})
  const selectedBreakdownKey = breakdownKey && breakdownKeys.includes(breakdownKey)
    ? breakdownKey
    : breakdownKeys[0]

  useEffect(() => {
    setBreakdownKey(null)
  }, [module?.key])

  if (!module && !loading) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模块数据" />
  }

  const breakdown = selectedBreakdownKey ? module?.breakdowns[selectedBreakdownKey] ?? [] : []

  return (
    <Flex vertical gap={16}>
      <MetricGrid cards={module?.cards ?? []} loading={loading} rangeLabel={rangeLabel} rangeKind={rangeKind} />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <TrendPanel title={`${module?.title ?? ''}趋势`} data={module?.trends ?? []} loading={loading} />
        </Col>
        <Col xs={24} xl={10}>
          <BreakdownPanel
            activeKey={selectedBreakdownKey}
            data={breakdown}
            keys={breakdownKeys}
            loading={loading}
            onChange={setBreakdownKey}
          />
        </Col>
      </Row>
      <RowsTable rows={module?.rows ?? []} loading={loading} />
    </Flex>
  )
}

function MetricGrid({
  cards,
  loading = false,
  compact = false,
  rangeLabel,
  rangeKind,
}: {
  cards: MetricCard[]
  loading?: boolean
  compact?: boolean
  rangeLabel?: string
  rangeKind?: RangeKind
}) {
  if (!cards.length && !loading) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无指标" />
  }
  return (
    <Row gutter={[12, 12]}>
      {(loading ? Array.from({ length: compact ? 2 : 4 }).map((_, index) => ({
        key: `loading-${index}`,
        title: '加载中',
        value: 0,
        total: null,
        range_value: null,
        today_value: null,
        last_7_days_value: null,
        unit: '',
        description: null,
        extra: {},
      })) : cards).map((card) => (
        <Col key={card.key} xs={24} sm={compact ? 24 : 12} xl={compact ? 12 : 6}>
          <Card size={compact ? 'small' : 'default'} loading={loading}>
            <Statistic title={card.title} value={formatNumber(card.value)} suffix={card.unit} />
            {!compact && (
              <Space size={[6, 4]} wrap style={{ marginTop: 10, maxWidth: '100%' }}>
                {card.range_value !== null && (
                  <Tag color="blue" style={metricTagStyle}>
                    {rangeLabel ? `${rangeLabel} ` : '新增 '}
                    {formatMetricTagValue(card.range_value, card.unit)}
                  </Tag>
                )}
                {card.today_value !== null && rangeKind !== 'today' && (
                  <Tag color="green" style={metricTagStyle}>
                    今日新增 {formatMetricTagValue(card.today_value, card.unit)}
                  </Tag>
                )}
                {card.last_7_days_value !== null && rangeKind !== 'last7' && (
                  <Tag style={metricTagStyle}>
                    近7天新增 {formatMetricTagValue(card.last_7_days_value, card.unit)}
                  </Tag>
                )}
              </Space>
            )}
          </Card>
        </Col>
      ))}
    </Row>
  )
}

function TrendPanel({ title, data, loading = false }: { title: string; data: TrendPoint[]; loading?: boolean }) {
  return (
    <Card title={title || '趋势'} loading={loading} styles={{ body: { height: 340 } }}>
      {data.length ? (
        <Line
          data={data}
          xField="date"
          yField="value"
          colorField="metric"
          height={280}
          point
          legend={{ color: { position: 'bottom' } }}
          tooltip={{
            title: (datum: TrendPoint) => datum.date,
            items: [
              (datum: TrendPoint) => ({
                name: datum.metric,
                value: datum.value,
              }),
            ],
          }}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无趋势" />
      )}
    </Card>
  )
}

function BreakdownPanel({
  activeKey,
  data,
  keys,
  loading = false,
  onChange,
}: {
  activeKey: string | undefined
  data: BreakdownItem[]
  keys: string[]
  loading?: boolean
  onChange: (key: string) => void
}) {
  return (
    <Card
      title="结构分布"
      loading={loading}
      extra={!loading && keys.length > 1 ? (
        <Segmented
          size="small"
          value={activeKey}
          options={keys.map((key) => ({ label: key, value: key }))}
          onChange={(value) => onChange(String(value))}
        />
      ) : null}
      styles={{ body: { height: 340 } }}
    >
      {data.length ? (
        <Pie
          data={data}
          angleField="value"
          colorField="label"
          height={280}
          innerRadius={0.58}
          legend={{ color: { position: 'bottom' } }}
          tooltip={{
            title: (datum: BreakdownItem) => datum.label,
            items: [
              (datum: BreakdownItem) => ({
                name: datum.label,
                value: datum.value,
              }),
            ],
          }}
        />
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无分布" />
      )}
    </Card>
  )
}

function MiniBreakdown({ module }: { module: MonitoringModule }) {
  const firstKey = Object.keys(module.breakdowns)[0]
  const data = firstKey ? module.breakdowns[firstKey] ?? [] : []
  if (!data.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无分布" />
  }
  return (
    <Column
      data={data.slice(0, 6)}
      xField="label"
      yField="value"
      height={160}
      axis={{ x: { labelTransform: 'rotate(0)' } }}
      tooltip={{
        title: (datum: BreakdownItem) => datum.label,
        items: [
          (datum: BreakdownItem) => ({
            name: datum.label,
            value: datum.value,
          }),
        ],
      }}
    />
  )
}

function RowsTable({ rows, loading }: { rows: Array<Record<string, unknown>>; loading: boolean }) {
  const columns = useMemo<TableColumnsType<Record<string, unknown>>>(() => {
    const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, 10)
    return keys.map((key) => ({
      dataIndex: key,
      title: key,
      ellipsis: true,
      render: (value: unknown) => (
        key === 'status'
          ? <Tag color={value === 'completed' ? 'green' : value === 'failed' ? 'red' : 'blue'}>{formatCell(value)}</Tag>
          : <Typography.Text>{formatCell(value)}</Typography.Text>
      ),
    }))
  }, [rows])

  return (
    <Card title={<Space><BarChartOutlined />明细</Space>}>
      <Table
        columns={columns}
        dataSource={rows}
        loading={loading}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无明细" /> }}
        pagination={{ pageSize: 10 }}
        rowKey={(record, index) => String(record.id ?? record.key ?? index)}
        scroll={{ x: true }}
      />
    </Card>
  )
}
