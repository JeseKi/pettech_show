import { useEffect, useMemo, useState } from 'react'
import { Button, Empty, Flex, Input, Modal, Space, Tag, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'

export default function KeywordModal({
  open,
  terms,
  selectedTerms,
  keywordSearch,
  onSearch,
  onApply,
  onClose,
}: {
  open: boolean
  terms: string[]
  selectedTerms: string[]
  keywordSearch: string
  onSearch: (value: string) => void
  onApply: (terms: string[]) => void
  onClose: () => void
}) {
  const [draftTerms, setDraftTerms] = useState<string[]>([])
  const draftSet = useMemo(() => new Set(draftTerms), [draftTerms])
  const visibleTerms = useMemo(() => {
    const keyword = keywordSearch.trim()
    return keyword ? terms.filter((term) => term.includes(keyword)) : terms
  }, [keywordSearch, terms])

  useEffect(() => {
    if (open) setDraftTerms(selectedTerms)
  }, [open, selectedTerms])

  const toggleTerm = (term: string) => {
    setDraftTerms((current) => (
      current.includes(term)
        ? current.filter((item) => item !== term)
        : [...current, term]
    ))
  }

  return (
    <Modal
      title="关键词高亮筛选"
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="clear" onClick={() => setDraftTerms([])}>清空</Button>,
        <Button key="all" onClick={() => setDraftTerms(terms)}>全选</Button>,
        <Button key="apply" type="primary" onClick={() => onApply(draftTerms)}>确定</Button>,
      ]}
    >
      <Flex vertical gap={14}>
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索关键词"
          value={keywordSearch}
          onChange={(event) => onSearch(event.target.value)}
        />
        <Typography.Text type="secondary">
          已选择 {draftTerms.length} / {terms.length} 个关键词
        </Typography.Text>
        <Space wrap>
          {visibleTerms.map((term) => (
            <Tag
              key={term}
              color={draftSet.has(term) ? 'blue' : 'default'}
              style={{ cursor: 'pointer', padding: '4px 8px' }}
              onClick={() => toggleTerm(term)}
            >
              {term}
            </Tag>
          ))}
        </Space>
        {!visibleTerms.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无匹配关键词" />}
      </Flex>
    </Modal>
  )
}
