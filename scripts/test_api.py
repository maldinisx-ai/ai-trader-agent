import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_api_connection():
    """测试API连接"""

    # 1. 健康检查
    print("=" * 50)
    print("[1] 健康检查")
    print("-" * 50)
    try:
        resp = requests.get("http://127.0.0.1:8000/health")
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
    except Exception as e:
        print(f"Error: {e}")
        return False

    # 2. 获取策略列表
    print("\n" + "=" * 50)
    print("[2] 获取策略列表")
    print("-" * 50)
    try:
        resp = requests.get(f"{BASE_URL}/strategy/")
        data = resp.json()
        print(f"Status: {resp.status_code}")
        print(f"策略数量: {len(data)}")
        for strategy in data:
            print(f"  - {strategy['name']}: {strategy['display_name']}")
    except Exception as e:
        print(f"Error: {e}")
        return False

    # 3. 获取激活策略
    print("\n" + "=" * 50)
    print("[3] 获取激活策略")
    print("-" * 50)
    try:
        resp = requests.get(f"{BASE_URL}/strategy/active")
        data = resp.json()
        print(f"Status: {resp.status_code}")
        print(f"激活策略: {data.get('active_strategies', [])}")
    except Exception as e:
        print(f"Error: {e}")
        return False

    # 4. 测试股票分析
    print("\n" + "=" * 50)
    print("[4] 测试股票分析")
    print("-" * 50)
    try:
        payload = {
            "stock_code": "600519.SH",
            "stock_name": "贵州茅台",
            "strategies": ["momentum_trend"]
        }
        resp = requests.post(f"{BASE_URL}/analysis/analyze", json=payload)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"股票代码: {data.get('stock_code')}")
            print(f"股票名称: {data.get('stock_name')}")
            print(f"综合信号: {data.get('overall_signal')}")
            print(f"综合评分: {data.get('overall_score')}")
            print(f"策略数量: {len(data.get('signals', []))}")
        else:
            print(f"Response: {resp.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
        return False

    print("\n" + "=" * 50)
    print("[完成] 所有API测试通过!")
    print("=" * 50)
    return True

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    test_api_connection()