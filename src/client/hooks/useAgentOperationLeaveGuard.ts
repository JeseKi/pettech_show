import { useEffect, useRef } from 'react'

const AGENT_OPERATION_LEAVE_MESSAGE = '智能体仍在处理，离开页面可能会中断前端工具操作。确定离开吗？'

const samePageUrl = (href: string) => {
  try {
    const target = new URL(href, window.location.href)
    return target.href === window.location.href
  } catch {
    return false
  }
}

const closestAnchor = (target: EventTarget | null) => (
  target instanceof Element ? target.closest<HTMLAnchorElement>('a[href]') : null
)

export function confirmAgentOperationLeave() {
  return window.confirm(AGENT_OPERATION_LEAVE_MESSAGE)
}

export function useAgentOperationLeaveGuard(active: boolean) {
  const activeRef = useRef(active)
  activeRef.current = active

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!activeRef.current) return
      event.preventDefault()
      event.returnValue = ''
    }

    const handleDocumentClick = (event: MouseEvent) => {
      if (!activeRef.current || event.defaultPrevented) return
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const anchor = closestAnchor(event.target)
      if (!anchor || samePageUrl(anchor.href)) return
      if (anchor.target && anchor.target !== '_self') return
      if (anchor.hasAttribute('download')) return

      if (!confirmAgentOperationLeave()) {
        event.preventDefault()
        event.stopPropagation()
        event.stopImmediatePropagation()
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    document.addEventListener('click', handleDocumentClick, true)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
      document.removeEventListener('click', handleDocumentClick, true)
    }
  }, [])
}
