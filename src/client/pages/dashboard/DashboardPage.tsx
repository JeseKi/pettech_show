import { Button, Card, Col, Flex, Row, Typography } from 'antd'
import { FileSearchOutlined, FileTextOutlined, RightOutlined, TableOutlined } from '@ant-design/icons'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  AIWIKI_MODES,
  CAPABILITY_GROUP_META,
  DAILY_WRITER_MODES,
  SEED_MATRIX_MODES,
  VISIBLE_CAPABILITY_ENTRIES,
  type CapabilityGroupId,
} from '../../lib/workflowModes'

const capabilityGroupIcons: Record<CapabilityGroupId, ReactNode> = {
  'competitor-insights': <FileSearchOutlined />,
  'topic-planning': <TableOutlined />,
  'script-creation': <FileTextOutlined />,
}

const entryGroups = [
  {
    title: 'AI Wiki',
    icon: <FileSearchOutlined />,
    entries: Object.values(AIWIKI_MODES),
  },
  {
    title: '选题矩阵',
    icon: <TableOutlined />,
    entries: Object.values(SEED_MATRIX_MODES),
  },
  {
    title: '长文生成',
    icon: <FileTextOutlined />,
    entries: Object.values(DAILY_WRITER_MODES),
  },
  ...Object.entries(CAPABILITY_GROUP_META).map(([groupId, meta]) => ({
    title: meta.title,
    icon: capabilityGroupIcons[groupId as CapabilityGroupId],
    entries: VISIBLE_CAPABILITY_ENTRIES.filter((entry) => entry.group === groupId),
  })).filter((group) => group.entries.length > 0),
]

export default function DashboardPage() {
  return (
    <Flex vertical gap={24}>
      <Typography.Title level={2} style={{ margin: 0 }}>
        首页
      </Typography.Title>
      {entryGroups.map((group) => (
        <Flex key={group.title} vertical gap={12}>
          <Flex align="center" gap={8}>
            {group.icon}
            <Typography.Title level={4} style={{ margin: 0 }}>
              {group.title}
            </Typography.Title>
          </Flex>
          <Row gutter={[16, 16]}>
            {group.entries.map((entry) => (
              <Col key={entry.key} xs={24} md={12} xl={8}>
                <Card
                  hoverable
                  title={(
                    <Flex align="center" gap={8}>
                      {group.icon}
                      <span>{entry.navLabel}</span>
                    </Flex>
                  )}
                  extra={(
                    <Button type="link" icon={<RightOutlined />} iconPosition="end">
                      <Link to={entry.path}>进入</Link>
                    </Button>
                  )}
                  style={{ height: '100%' }}
                  styles={{ body: { minHeight: 152 } }}
                >
                  <Flex vertical justify="space-between" gap={16} style={{ height: '100%' }}>
                    <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                      {entry.description}
                    </Typography.Paragraph>
                    <Button type="primary" icon={group.icon} style={{ alignSelf: 'flex-start' }}>
                      <Link to={entry.path}>{entry.buttonText}</Link>
                    </Button>
                  </Flex>
                </Card>
              </Col>
            ))}
          </Row>
        </Flex>
      ))}
    </Flex>
  )
}
