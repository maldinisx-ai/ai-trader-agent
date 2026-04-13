import { useState, useEffect } from 'react'
import { Switch } from '@/components/ui/switch'
import { clsx } from 'clsx'
import { strategyApi, type Strategy } from '../api/strategy'

export default function StrategyPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStrategies()
  }, [])

  const loadStrategies = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await strategyApi.listStrategies()
      setStrategies(data)
    } catch (err: any) {
      setError(err?.message || '加载策略失败')
    } finally {
      setLoading(false)
    }
  }

  const toggleStrategy = async (name: string, currentEnabled: boolean) => {
    // 乐观更新 UI
    setStrategies((prev) =>
      prev.map((s) =>
        s.name === name ? { ...s, enabled: !currentEnabled } : s
      )
    )

    try {
      await strategyApi.updateStrategy(name, { enabled: !currentEnabled })
      // 重新加载以获取最新状态
      await loadStrategies()
    } catch (err: any) {
      // 恢复原状态
      setStrategies((prev) =>
        prev.map((s) =>
          s.name === name ? { ...s, enabled: currentEnabled } : s
        )
      )
      setError(err?.message || '更新策略失败')
    }
  }

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      trend: '趋势',
      reversal: '反转',
      pattern: '形态',
    }
    return labels[category] || category
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      trend: 'bg-primary/20 text-primary',
      reversal: 'bg-secondary/20 text-secondary',
      pattern: 'bg-warning/20 text-warning',
    }
    return colors[category] || 'bg-gray-500/20 text-gray-400'
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card bg-danger/10 border-danger">
        <div className="text-center">
          <p className="text-danger mb-4">{error}</p>
          <button onClick={loadStrategies} className="btn btn-primary">
            重试
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">交易策略</h1>
        <span className="text-gray-400 text-sm">
          已激活: {strategies.filter((s) => s.enabled).length} / {strategies.length}
        </span>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {strategies.map((strategy) => (
          <div
            key={strategy.name}
            className={clsx(
              'card transition-all',
              strategy.enabled && 'ring-2 ring-primary/50'
            )}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold">{strategy.display_name}</h3>
                  <span
                    className={clsx(
                      'text-xs px-2 py-0.5 rounded',
                      getCategoryColor(strategy.category)
                    )}
                  >
                    {getCategoryLabel(strategy.category)}
                  </span>
                </div>
                <p className="text-gray-400 text-sm">{strategy.description}</p>
              </div>
              <Switch
                checked={strategy.enabled}
                onCheckedChange={() => toggleStrategy(strategy.name, strategy.enabled)}
              />
            </div>

            {strategy.enabled && (
              <div className="mt-4 pt-4 border-t border-surface">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-400">状态</span>
                  <span className="text-success">已激活</span>
                </div>
                <div className="flex items-center justify-between text-sm mt-1">
                  <span className="text-gray-400">优先级</span>
                  <span>{strategy.default_priority}</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="card">
        <h3 className="font-semibold mb-3">策略说明</h3>
        <div className="space-y-2 text-sm text-gray-400">
          <p>- <strong>趋势策略</strong>: 适合上涨趋势，追涨杀跌</p>
          <p>- <strong>反转策略</strong>: 适合底部区域，左侧布局</p>
          <p>- <strong>形态策略</strong>: 捕捉特定形态，精准出击</p>
        </div>
      </div>
    </div>
  )
}
