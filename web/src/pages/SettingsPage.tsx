export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">系统设置</h1>

      <div className="card">
        <h2 className="text-lg font-semibold mb-4">API 配置</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">AI 模型 API Key</label>
            <input
              type="password"
              placeholder="输入你的 API Key"
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">数据源 Token (可选)</label>
            <input
              type="password"
              placeholder="Tushare / AkShare Token"
              className="input"
            />
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-4">分析设置</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">自动分析</div>
              <div className="text-sm text-gray-400">每日自动执行分析</div>
            </div>
            <input type="checkbox" className="toggle" />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">启用通知</div>
              <div className="text-sm text-gray-400">分析完成后发送通知</div>
            </div>
            <input type="checkbox" className="toggle" />
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <button className="btn">取消</button>
        <button className="btn btn-primary">保存设置</button>
      </div>
    </div>
  )
}
