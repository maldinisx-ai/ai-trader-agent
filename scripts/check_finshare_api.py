import finshare as fs

print('=== finshare 主要 API ===')
methods = [m for m in dir(fs) if not m.startswith('_') and callable(getattr(fs, m))]

categories = {
    '股票行情': [],
    '财务数据': [],
    '资金流向': [],
    '市场数据': [],
    '其他': []
}

for m in sorted(methods):
    name_lower = m.lower()
    if any(x in name_lower for x in ['stock', 'kline', 'hist', 'quote', 'price']):
        categories['股票行情'].append(m)
    elif any(x in name_lower for x in ['financial', 'income', 'balance', 'cash', 'dividend', 'indicator']):
        categories['财务数据'].append(m)
    elif any(x in name_lower for x in ['money', 'flow', 'margin']):
        categories['资金流向'].append(m)
    elif any(x in name_lower for x in ['index', 'market', 'industry', 'lhb', 'future', 'fund']):
        categories['市场数据'].append(m)
    else:
        categories['其他'].append(m)

for cat, methods in categories.items():
    if methods:
        print(f'\n[{cat}]:')
        for m in methods:
            print(f'  - {m}')
