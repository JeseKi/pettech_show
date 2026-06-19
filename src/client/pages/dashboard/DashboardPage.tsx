import { Button, Card, Col, Flex, Row, Typography } from 'antd'
import { FileSearchOutlined, RightOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'

export default function DashboardPage() {
  return (
    <Flex vertical gap={20}>
      <Typography.Title level={2} style={{ margin: 0 }}>
        工作台
      </Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12} xl={8}>
          <Card
            title={(
              <Flex align="center" gap={8}>
                <FileSearchOutlined />
                <span>AI Wiki</span>
              </Flex>
            )}
            extra={<Button type="link" icon={<RightOutlined />} iconPosition="end"><Link to="/aiwiki">进入</Link></Button>}
          >
            <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
              上传 DOCX、Markdown 或 TXT，生成热点、痛点、解决方案、关键词池、选题和可跳转的内容资产。
            </Typography.Paragraph>
            <Button type="primary" icon={<FileSearchOutlined />}>
              <Link to="/aiwiki">创建 AI Wiki</Link>
            </Button>
          </Card>
        </Col>
      </Row>
    </Flex>
  )
}
