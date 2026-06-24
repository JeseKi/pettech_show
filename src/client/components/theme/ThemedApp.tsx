import { App as AntdApp, ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from '../../App'

export default function ThemedApp() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#b8ff67',
          colorInfo: '#6ee7f9',
          colorSuccess: '#2dd4bf',
          colorWarning: '#facc15',
          colorError: '#fb7185',
          borderRadius: 8,
          colorBgBase: '#050706',
          colorBgLayout: '#050706',
          colorBgContainer: '#0d120f',
          colorBgElevated: '#111712',
          colorBorder: 'rgba(213, 255, 169, 0.16)',
          colorBorderSecondary: 'rgba(255, 255, 255, 0.09)',
          colorFillAlter: 'rgba(255, 255, 255, 0.055)',
          colorFillSecondary: 'rgba(184, 255, 103, 0.12)',
          colorFillQuaternary: 'rgba(255, 255, 255, 0.045)',
          colorTextBase: '#f5f7f1',
          colorTextSecondary: 'rgba(245, 247, 241, 0.68)',
          colorTextTertiary: 'rgba(245, 247, 241, 0.46)',
          boxShadow: '0 22px 56px rgba(0, 0, 0, 0.36)',
          boxShadowSecondary: '0 16px 40px rgba(0, 0, 0, 0.3)',
          fontFamily:
            "'Inter', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, -apple-system, sans-serif",
        },
        components: {
          Button: {
            controlHeight: 40,
            fontWeight: 600,
            paddingInline: 16,
            primaryColor: '#091008',
          },
          Layout: {
            headerBg: '#080d0a',
            siderBg: '#080d0a',
            bodyBg: 'transparent',
          },
          Card: {
            borderRadiusLG: 8,
            colorBgContainer: '#0d120f',
            colorBorderSecondary: 'rgba(255, 255, 255, 0.09)',
          },
          Menu: {
            darkItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(184, 255, 103, 0.14)',
            darkItemSelectedColor: '#f5f7f1',
          },
        },
      }}
    >
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  )
}
