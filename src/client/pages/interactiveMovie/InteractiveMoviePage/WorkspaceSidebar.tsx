import { Button, Typography } from 'antd'
import { DeleteOutlined, DoubleLeftOutlined, DoubleRightOutlined, EditOutlined, PlusOutlined, VideoCameraOutlined } from '@ant-design/icons'
import WorkbenchHomeButton from '../../../components/brand/WorkbenchHomeButton'
import { useInteractiveMoviePageContext } from './useInteractiveMoviePageContext'

export function WorkspaceSidebar() {
  const { activeProject, confirmDeleteProject, confirmRenameProject, createProject, setWorkspaceCollapsed, switchProject, workspace, workspaceCollapsed } = useInteractiveMoviePageContext()

  return (
    <aside className="movie-workspace-sidebar">
      <div className="movie-sidebar-chrome">
        <WorkbenchHomeButton className="movie-workbench-home" />
      </div>
      <button
        type="button"
        className="movie-sidebar-collapse"
        onClick={() => setWorkspaceCollapsed((value) => !value)}
        aria-label={workspaceCollapsed ? '展开工作区' : '折叠工作区'}
      >
        {workspaceCollapsed ? <DoubleRightOutlined /> : <DoubleLeftOutlined />}
      </button>
      <div className="movie-sidebar-brand">
        <span className="movie-logo-mark"><VideoCameraOutlined /></span>
        <div className="movie-sidebar-brand-text">
          <Typography.Text className="movie-kicker">互动电影生成</Typography.Text>
          <Typography.Title level={5} className="movie-sidebar-title">工作区</Typography.Title>
        </div>
      </div>
      <Button block type="primary" icon={<PlusOutlined />} onClick={createProject} className="movie-new-project-button">
        新建项目
      </Button>
      <div className="movie-project-list">
        {workspace.projects.map((project) => (
          <div
            key={project.id}
            role="button"
            tabIndex={0}
            className={project.id === activeProject.id ? 'movie-project-item is-active' : 'movie-project-item'}
            onClick={() => switchProject(project.id)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                switchProject(project.id)
              }
            }}
          >
            <button
              type="button"
              className="movie-project-rename"
              aria-label={`重命名项目 ${project.title}`}
              onClick={(event) => {
                event.stopPropagation()
                confirmRenameProject(project)
              }}
            >
              <EditOutlined />
            </button>
            <button
              type="button"
              className="movie-project-delete"
              aria-label={`删除项目 ${project.title}`}
              onClick={(event) => {
                event.stopPropagation()
                confirmDeleteProject(project)
              }}
            >
              <DeleteOutlined />
            </button>
            <span className="movie-project-name">{project.title}</span>
            <span className="movie-project-meta">{project.scenes.length} 场景 · {project.choices.length} 选择 · {project.assetNodes.length} 素材</span>
          </div>
        ))}
      </div>
    </aside>
  )
}
