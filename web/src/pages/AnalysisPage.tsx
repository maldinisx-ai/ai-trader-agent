import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { analysisApi, type AnalysisResult } from '../api/analysis'

export default function AnalysisPage() {
  const [searchParams] = useSearchParams()
  const [stockCode, setStockCode] = useState(searchParams.get('code') || '')
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const analyze = async () => {
    if (!stockCode.trim()) return

    setAnalyzing(true)
    setError(null)
    try {
      const data = await analysisApi.analyze({ stock_code: stockCode.trim() })
      setResult(data)
    } catch (err: any) {
      setError(err?.message || '分析失败，请稍后重试')
      setResult(null)
    } finally {
      setAnalyzing(false)
    }
  }

  useEffect(() => {
    if (stockCode) {
      analyze()
    }
  }, [stockCode])

  const getSignalText = (signal: string) => {
    switch (signal) {
      case 'buy':
        return '建议买入'
      case 'sell':
        return '建议卖出'
      default:
        return '建议观望'
    }
  }

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'buy':
        return 'bg-success/20 text-success'
      case 'sell':
        return 'bg-danger/20 text-danger'
      default:
        return 'bg-warning/20 text-warning'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="输入股票代码 (如: 600519.SH)"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value.toUpperCase())}
            className="input pl-10"
            onKeyPress={(e) => e.key === 'Enter' && analyze()}
          />
        </div>
        <button onClick={analyze} disabled={analyzing || !stockCode} className="btn btn-primary">
          {analyzing ? '分析中...' : '分析'}
        </button>
      </div>

      {error && (
        <div className="card bg-danger/10 border-danger">
          <div className="flex items-center gap-2 text-danger">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* 股票信息 */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-2xl font-bold">{result.stock_name}</h2>
                <p className="text-gray-400">{result.stock_code}</p>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold">
                  ¥{result.current_price?.toFixed(2) || '--'}
                </div>
                <div className={clsx(
                  'text-sm flex items-center gap-1',
                  (result.change_pct || 0) >= 0 ? 'text-success' : 'text-danger'
                )}>
                  {(result.change_pct || 0) >= 0 ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {(result.change_pct || 0) >= 0 ? '+' : ''}{(result.change_pct || 0).toFixed(2)}%
                </div>
              </div>
            </div>

            {/* 综合评分 */}
            <div className="bg-surface rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-gray-400 mb-1">综合评分</div>
                  <div className="text-3xl font-bold">{result.overall_score}/100</div>
                </div>
                <div className={clsx(
                  'px-4 py-2 rounded-lg text-lg font-semibold',
                  getSignalColor(result.overall_signal)
                )}>
                  {getSignalText(result.overall_signal)}
                </div>
              </div>
            </div>

            {/* 市场数据摘要 */}
            {result.market_data && (
              <div className="mt-4 grid grid-cols-4 gap-4 text-center">
                <div>
                  <div className="text-xs text-gray-400">MA5</div>
                  <div className="font-semibold">{result.market_data.ma5?.toFixed(2) || '--'}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">MA20</div>
                  <div className="font-semibold">{result.market_data.ma20?.toFixed(2) || '--'}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">量比</div>
                  <div className="font-semibold">{result.market_data.volume_ratio?.toFixed(2) || '--'}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-400">20日涨幅</div>
                  <div className={clsx('font-semibold',
                    (result.market_data.n20_gain_pct || 0) >= 0 ? 'text-success' : 'text-danger'
                  )}>
                    {(result.market_data.n20_gain_pct || 0) >= 0 ? '+' : ''}{(result.market_data.n20_gain_pct || 0).toFixed(2)}%
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 策略信号 */}
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">策略分析</h3>
            <div className="space-y-4">
              {result.signals?.map((signal, idx) => (
                <div key={idx} className="bg-surface rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{signal.display_name}</span>
                      <span className={clsx(
                        'text-sm px-2 py-0.5 rounded',
                        getSignalColor(signal.signal)
                      )}>
                        {getSignalText(signal.signal)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-400">置信度</span>
                      <span className="font-semibold">{(signal.confidence * 100).toFixed(0)}%</span>
                      <span className="text-xl font-bold">{signal.score}</span>
                    </div>
                  </div>
                  {signal.reasoning && (
                    <div className="text-gray-400 text-sm whitespace-pre-line">
                      {signal.reasoning}
                    </div>
                  )}

                  {/* 价格建议 */}
                  {(signal.entry_price || signal.stop_loss || signal.take_profit) && (
                    <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
                      {signal.entry_price && (
                        <div>
                          <span className="text-gray-400">买入价: </span>
                          <span className="font-semibold">¥{signal.entry_price.toFixed(2)}</span>
                        </div>
                      )}
                      {signal.stop_loss && (
                        <div>
                          <span className="text-gray-400">止损: </span>
                          <span className="font-semibold text-warning">¥{signal.stop_loss.toFixed(2)}</span>
                        </div>
                      )}
                      {signal.take_profit && (
                        <div>
                          <span className="text-gray-400">目标: </span>
                          <span className="font-semibold text-success">¥{signal.take_profit.toFixed(2)}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 激活的策略 */}
          <div className="text-sm text-gray-400">
            使用策略: {result.active_strategies?.join(', ') || '无'}
          </div>
        </div>
      )}
    </div>
  )
}
