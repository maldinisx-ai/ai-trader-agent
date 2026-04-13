/**
 * 策略相关 API
 */

export interface Strategy {
  name: string
  display_name: string
  description: string
  category: string
  default_active: boolean
  enabled: boolean
  default_priority: number
  aliases: string[]
  required_tools: string[]
}

export interface StrategyUpdate {
  enabled: boolean
}

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const strategyApi = {
  /**
   * 获取所有策略
   */
  async listStrategies(category?: string): Promise<Strategy[]> {
    const params = category ? `?category=${category}` : ''
    const response = await fetch(`${BASE_URL}/strategy${params}`)
    if (!response.ok) throw new Error('获取策略列表失败')
    return response.json()
  },

  /**
   * 获取单个策略
   */
  async getStrategy(name: string): Promise<Strategy> {
    const response = await fetch(`${BASE_URL}/strategy/${name}`)
    if (!response.ok) throw new Error('获取策略失败')
    return response.json()
  },

  /**
   * 更新策略状态
   */
  async updateStrategy(name: string, data: StrategyUpdate): Promise<Strategy> {
    const response = await fetch(`${BASE_URL}/strategy/${name}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!response.ok) throw new Error('更新策略失败')
    return response.json()
  },

  /**
   * 批量激活策略
   */
  async activateStrategies(names: string[]): Promise<{ activated: string[]; count: number }> {
    const response = await fetch(`${BASE_URL}/strategy/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(names),
    })
    if (!response.ok) throw new Error('激活策略失败')
    return response.json()
  },

  /**
   * 停用所有策略
   */
  async deactivateAll(): Promise<{ status: string; message: string }> {
    const response = await fetch(`${BASE_URL}/strategy/deactivate-all`, {
      method: 'POST',
    })
    if (!response.ok) throw new Error('停用策略失败')
    return response.json()
  },

  /**
   * 获取已激活的策略
   */
  async getActiveStrategies(): Promise<Strategy[]> {
    const response = await fetch(`${BASE_URL}/strategy/active`)
    if (!response.ok) throw new Error('获取已激活策略失败')
    return response.json()
  },
}
