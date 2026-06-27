import './style.css'

export default function WechatAutomationFlowPage() {
  return (
    <div className="wechat-automation-flow-page">
      <iframe
        className="wechat-automation-flow-frame"
        src="/tools/wechat_automation_flow_preview.html"
        title="微信生态自动化流程演示"
      />
    </div>
  )
}
