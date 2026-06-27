import { Button, Empty, Flex, Modal, Space, Tag, Typography } from 'antd'
import { CheckCircleOutlined, CloudUploadOutlined, LinkOutlined, PoweroffOutlined } from '@ant-design/icons'
import { formatDateTime } from '../interactiveMovieCanvas'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

export function PublishModal() {
  const {
    activeProject,
    activeProjectHasUnsavedChanges,
    activeProjectPublicUrl,
    closePublishedProject,
    publishCurrentDraft,
    publishModalOpen,
    publishing,
    refreshReleaseHistory,
    releaseHistory,
    releaseLoading,
    saving,
    setPublishModalOpen,
    setReleaseOnline,
  } = useInteractiveMoviePageContext()

  return (
    <Modal
      title="发表与正式版"
      open={publishModalOpen}
      onCancel={() => setPublishModalOpen(false)}
      footer={null}
      width={760}
      className="movie-publish-modal"
    >
      <Flex vertical gap={16}>
        <section className="movie-publish-status">
          <Flex align="center" justify="space-between" gap={12} wrap>
            <div>
              <Typography.Text className="movie-panel-kicker">公开地址</Typography.Text>
              <Typography.Title level={5} className="movie-publish-title">
                {activeProject.isPublished ? `已发表 v${activeProject.publishedVersionNo}` : '未发表'}
              </Typography.Title>
            </div>
            <Space wrap>
              {activeProject.isPublished && (
                <Button danger icon={<PoweroffOutlined />} loading={publishing} onClick={() => void closePublishedProject()}>
                  关闭发表
                </Button>
              )}
              <Button
                type="primary"
                icon={<CloudUploadOutlined />}
                loading={publishing}
                disabled={saving || activeProjectHasUnsavedChanges}
                onClick={() => void publishCurrentDraft()}
              >
                发表当前草稿
              </Button>
            </Space>
          </Flex>
          <div className="movie-public-url">
            <LinkOutlined />
            <Typography.Text copyable={{ text: activeProjectPublicUrl }} className="movie-public-url-text">
              {activeProjectPublicUrl}
            </Typography.Text>
          </div>
          {activeProjectHasUnsavedChanges && (
            <div className="movie-publish-warning">请先保存当前草稿后再发表。</div>
          )}
        </section>

        <section className="movie-panel-section">
          <Flex align="center" justify="space-between">
            <Typography.Text className="movie-panel-label">正式版历史</Typography.Text>
            <Button size="small" loading={releaseLoading} onClick={() => void refreshReleaseHistory(activeProject.id)}>
              刷新
            </Button>
          </Flex>
          {releaseHistory.length > 0 ? (
            <div className="movie-release-list">
              {releaseHistory.map((release) => (
                <div key={release.id} className={release.is_current ? 'movie-release-row is-current' : 'movie-release-row'}>
                  <div className="movie-release-main">
                    <span className="movie-release-version">v{release.version_no}</span>
                    <span className="movie-release-title">{release.title}</span>
                    <span className="movie-release-time">{formatDateTime(release.created_at)}</span>
                  </div>
                  {release.is_current ? (
                    <Tag color="green" icon={<CheckCircleOutlined />}>线上版</Tag>
                  ) : (
                    <Button size="small" loading={publishing} onClick={() => void setReleaseOnline(release)}>
                      设为线上版
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={releaseLoading ? '加载正式版历史中' : '暂无正式版'} />
          )}
        </section>
      </Flex>
    </Modal>
  )
}
