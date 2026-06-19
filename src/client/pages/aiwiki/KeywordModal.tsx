import { Button, Empty, Input, Modal, Space, Tag } from 'antd'
import { SearchOutlined } from '@ant-design/icons'

export default function KeywordModal({
  open,
  terms,
  selectedTerm,
  keywordSearch,
  onSearch,
  onSelect,
  onClear,
  onClose,
}: {
  open: boolean
  terms: string[]
  selectedTerm: string | null
  keywordSearch: string
  onSearch: (value: string) => void
  onSelect: (term: string) => void
  onClear: () => void
  onClose: () => void
}) {
  return (
    <Modal
      title="关键词高亮筛选"
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="clear" onClick={onClear}>清除筛选</Button>,
        <Button key="close" type="primary" onClick={onClose}>完成</Button>,
      ]}
    >
      <Input
        allowClear
        prefix={<SearchOutlined />}
        placeholder="搜索关键词"
        value={keywordSearch}
        onChange={(event) => onSearch(event.target.value)}
        style={{ marginBottom: 16 }}
      />
      <Space wrap>
        {terms.map((term) => (
          <Tag
            key={term}
            color={selectedTerm === term ? 'blue' : 'default'}
            style={{ cursor: 'pointer', padding: '4px 8px' }}
            onClick={() => onSelect(term)}
          >
            {term}
          </Tag>
        ))}
      </Space>
      {!terms.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无匹配关键词" />}
    </Modal>
  )
}
