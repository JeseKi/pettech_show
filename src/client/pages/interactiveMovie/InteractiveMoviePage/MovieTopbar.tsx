import { Button, Flex, Input, Space, Tag, Typography } from 'antd'
import { CloudUploadOutlined, GlobalOutlined, PlayCircleOutlined, SaveOutlined } from '@ant-design/icons'
import BrandNavPill from '../../../components/brand/BrandNavPill'
import WorkbenchHomeButton from '../../../components/brand/WorkbenchHomeButton'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

export function MovieTopbar() {
  const { activeProject, openPublishModal, renameProject, saveDraft, saving, startPreview, syncing, syncMessage } = useInteractiveMoviePageContext()

  return (
    <header className="movie-topbar">
      <WorkbenchHomeButton className="movie-mobile-workbench-home" />
      <Flex align="center" gap={12} className="movie-project-heading">
        <div>
          <Typography.Text className="movie-kicker">云端项目 / 互动电影创作平台 MVP</Typography.Text>
          <Input
            variant="borderless"
            value={activeProject.title}
            onChange={(event) => renameProject(event.target.value)}
            className="movie-title-input"
            aria-label="项目名"
          />
        </div>
      </Flex>
      <BrandNavPill activeKey="interactive-movie" className="movie-top-nav" />
      <Space wrap>
        <Tag className="movie-status-tag">{syncing ? '同步检查中' : syncMessage}</Tag>
        {activeProject.isPublished && (
          <Tag color="green" icon={<GlobalOutlined />}>线上 v{activeProject.publishedVersionNo}</Tag>
        )}
        <Button icon={<SaveOutlined />} loading={saving} onClick={() => void saveDraft()}>保存</Button>
        <Button icon={<CloudUploadOutlined />} onClick={openPublishModal}>
          {activeProject.isPublished ? '管理发表' : '发表'}
        </Button>
        <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => startPreview()}>预览</Button>
      </Space>
    </header>
  )
}
