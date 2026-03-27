/**
 * 分析相关 API
 */

export interface AnalysisRequest {
  stock_code: string
  strategies?: string[]
}

export interface StrategySignal {
  strategy_name: string
  display_name: string
  signal: 'buy' | 'sell' | 'hold'
  confidence: number
  score: number
  reasoning: string
  entry_price?: number
  stop_loss?: number
  take_profit?: number
}

export interface AnalysisResult {
  stock_code: string
  stock_name: string
  current_price?: number
  change_pct?: number
  overall_signal: 'buy' | 'sell' | 'hold'
  overall_score: number
  signals: StrategySignal[]
  active_strategies: string[]
  analysis_time: string
  market_data?: {
    close?: number
    change_pct?: number
    ma5?: number
    ma10?: number
    ma20?: number
    volume_ratio?: number
    n20_gain_pct?: number
    bias_ma5?: number
  }
}

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const analysisApi = {
  /**
   * 分析股票
   */
  async analyze(request: AnalysisRequest): Promise<AnalysisResult> {
    const response = await fetch(`${BASE_URL}/analysis/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    if (!response.ok) throw new Error('分析失败')
    return response.json()
  },

  /**
   * 获取历史记录
   */
  async getHistory(stockCode?: string, limit = 20): Promise<{ records: any[]; total: number }> {
    const params = new URLSearchParams()
    if (stockCode) params.append('stock_code', stockCode)
    params.append('limit', limit.toString())

    const response = await fetch(`${BASE_URL}/analysis/history?${params}`)
    if (!response.ok) throw new Error('获取历史记录失败')
    return response.json()
  },
}
