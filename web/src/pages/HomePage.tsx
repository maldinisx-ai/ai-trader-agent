import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, TrendingUp, TrendingDown, Lightbulb, Cog } from 'lucide-react'
import { clsx } from 'clsx'

export default function HomePage() {
  const [stockInput, setStockInput] = useState('')

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="text-center py-12">
        <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
          AI 智能交易系统
        </h1>
        <p className="text-gray-400 text-lg max-w-2xl mx-auto">
          基于多策略的智能股票分析，帮你捕捉市场机会，控制投资风险
        </p>
      </div>

      {/* 快速分析 */}
      <div className="card max-w-2xl mx-auto">
        <h2 className="text-lg font-semibold mb-4">快速分析</h2>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="输入股票代码或名称 (如: 600519, 贵州茅台)"
            value={stockInput}
            onChange={(e) => setStockInput(e.target.value)}
            className="input flex-1"
            onKeyPress={(e) => {
              if (e.key === 'Enter' && stockInput.trim()) {
                window.location.href = `/analysis?code=${stockInput.trim()}`
              }
            }}
          />
          <Link
            to={stockInput.trim() ? `/analysis?code=${stockInput.trim()}` : '#'}
            className={clsx(
              'btn btn-primary flex items-center gap-2',
              !stockInput.trim() && 'opacity-50 pointer-events-none'
            )}
          >
            分析
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {/* 功能卡片 */}
      <div className="grid md:grid-cols-3 gap-6">
        <Link to="/analysis" className="card hover:border-primary transition-colors cursor-pointer">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-primary" />
            </div>
            <h3 className="font-semibold">智能分析</h3>
          </div>
          <p className="text-gray-400 text-sm">
            使用 AI 分析股票走势，获取买卖建议和目标价位
          </p>
        </Link>

        <Link to="/strategy" className="card hover:border-secondary transition-colors cursor-pointer">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-10 w-10 rounded-lg bg-secondary/20 flex items-center justify-center">
              <Lightbulb className="h-5 w-5 text-secondary" />
            </div>
            <h3 className="font-semibold">策略管理</h3>
          </div>
          <p className="text-gray-400 text-sm">
            管理交易策略，灵活切换不同分析策略
          </p>
        </Link>

        <Link to="/settings" className="card hover:border-success transition-colors cursor-pointer">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-10 w-10 rounded-lg bg-success/20 flex items-center justify-center">
              <Cog className="h-5 w-5 text-success" />
            </div>
            <h3 className="font-semibold">系统设置</h3>
          </div>
          <p className="text-gray-400 text-sm">
            配置 API 密钥和数据源，自定义系统行为
          </p>
        </Link>
      </div>

      {/* 市场概览 */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">市场概览</h2>
        <div className="grid md:grid-cols-4 gap-4">
          <div className="bg-surface rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">上证指数</div>
            <div className="flex items-center justify-between">
              <span className="text-xl font-bold">3,245.67</span>
              <span className="text-success text-sm flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />
                +0.85%
              </span>
            </div>
          </div>
          <div className="bg-surface rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">深证成指</div>
            <div className="flex items-center justify-between">
              <span className="text-xl font-bold">10,234.56</span>
              <span className="text-success text-sm flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />
                +1.02%
              </span>
            </div>
          </div>
          <div className="bg-surface rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">创业板指</div>
            <div className="flex items-center justify-between">
              <span className="text-xl font-bold">2,045.32</span>
              <span className="text-danger text-sm flex items-center gap-1">
                <TrendingDown className="h-3 w-3" />
                -0.23%
              </span>
            </div>
          </div>
          <div className="bg-surface rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">北向资金</div>
            <div className="flex items-center justify-between">
              <span className="text-xl font-bold">+45.6亿</span>
              <span className="text-success text-sm flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />
                净流入
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
