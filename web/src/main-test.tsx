import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'

const App = () => {
  return React.createElement('div', {
    style: {
      padding: '20px',
      minHeight: '100vh',
      background: '#0f172a',
      color: '#fff'
    }
  }, [
    React.createElement('h1', null, 'AI Trader Agent - 测试'),
    React.createElement('p', null, '如果你能看到这个页面，说明 React 基础渲染正常工作。'),
    React.createElement('button', {
      onClick: () => alert('点击工作正常！'),
      style: {
        padding: '10px 20px',
        background: '#06b6d4',
        color: 'white',
        border: 'none',
        borderRadius: '6px',
        cursor: 'pointer'
      }
    }, '测试按钮')
  ])
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  React.createElement(App)
)
