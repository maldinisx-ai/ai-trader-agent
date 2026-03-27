import { Link, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  HomeIcon,
  ChartBarIcon,
  LightBulbIcon,
  CogIcon,
} from '@heroicons/react/24/outline'

const navigation = [
  { name: '首页', href: '/', icon: HomeIcon },
  { name: '分析', href: '/analysis', icon: ChartBarIcon },
  { name: '策略', href: '/strategy', icon: LightBulbIcon },
  { name: '设置', href: '/settings', icon: CogIcon },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-base">
      {/* 顶部导航 */}
      <header className="border-b border-surface bg-surface/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-secondary" />
                <span className="text-xl font-bold">AI Trader</span>
              </Link>
              <nav className="hidden md:flex items-center gap-1">
                {navigation.map((item) => {
                  const isActive = location.pathname === item.href
                  return (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={clsx(
                        'flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-primary text-white'
                          : 'text-gray-400 hover:text-white hover:bg-surface'
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.name}
                    </Link>
                  )
                })}
              </nav>
            </div>
          </div>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
