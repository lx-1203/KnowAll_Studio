import { Component, ReactNode } from 'react'
import { Button, Result } from 'antd'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log error for debugging and monitoring
    console.error(
      '[ErrorBoundary]',
      `Message: ${error.message}`,
      `Stack: ${error.stack?.slice(0, 500)}`,
      `Component: ${info.componentStack?.slice(0, 500)}`,
    )
    // In production, send to error tracking service (e.g., Sentry, Datadog)
    if (import.meta.env.PROD) {
      try {
        const payload = {
          error: error.message,
          stack: error.stack?.slice(0, 1000),
          componentStack: info.componentStack?.slice(0, 1000),
          url: window.location.href,
          timestamp: new Date().toISOString(),
        }
        // Fire-and-forget to avoid blocking
        navigator.sendBeacon?.('/api/v1/admin/error-report', JSON.stringify(payload))
      } catch {
        // Silent - don't break error boundary for reporting failures
      }
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <Result
          status="error"
          title="页面出错了"
          subTitle={this.state.error?.message || '未知错误'}
          extra={[
            <Button type="primary" key="retry" onClick={this.handleReset}>
              重试
            </Button>,
            <Button key="reload" onClick={() => window.location.reload()}>
              刷新页面
            </Button>,
          ]}
        />
      )
    }
    return this.props.children
  }
}
