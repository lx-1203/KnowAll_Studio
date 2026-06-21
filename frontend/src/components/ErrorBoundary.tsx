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
