import '../wechatAutomationFlow/style.css'

export default function WecomMomentsPublishPage() {
  return (
    <div className="wechat-automation-flow-page">
      <iframe
        className="wechat-automation-flow-frame"
        src="/tools/wecom_moments_api_flow.html"
        title="企业微信朋友圈发布流程演示"
      />
    </div>
  )
}
