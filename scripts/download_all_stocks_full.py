# -*- coding: utf-8 -*-
"""
下载所有A股历史K线数据 - 支持断点续传

功能：
1. 获取完整A股列表
2. 分批下载，支持断点续传
3. 自动重试失败的股票
4. 进度保存和恢复
"""

import os
import sys
import io
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

# 设置UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 禁用所有代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import requests
requests.Session.trust_env = False

import akshare as ak
import pandas as pd


# 进度文件路径
PROGRESS_FILE = PROJECT_ROOT / 'data' / 'download_progress.json'
STOCK_LIST_FILE = PROJECT_ROOT / 'data' / 'stock_list.json'


def load_progress():
    """加载下载进度"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'downloaded': [], 'failed': {}, 'last_update': None}


def save_progress(progress):
    """保存下载进度"""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def load_stock_list():
    """加载股票列表"""
    if STOCK_LIST_FILE.exists():
        with open(STOCK_LIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_stock_list(stocks):
    """保存股票列表"""
    with open(STOCK_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)


def get_all_a_stocks():
    """获取所有A股列表"""
    print("正在获取A股股票列表...")

    try:
        # 方法1: 使用东方财富A股列表
        print("尝试方法1: 东方财富A股列表...")
        df = ak.stock_zh_a_spot_em()

        if df is not None and len(df) > 0:
            stocks = []
            for _, row in df.iterrows():
                code = str(row['代码'])
                name = row['名称']

                # 过滤A股
                is_sh_a = (code.startswith('60') and not code.startswith('609'))
                is_sz_a = (code.startswith('00') or code.startswith('30'))
                is_star = code.startswith('688')

                if is_sh_a or is_sz_a or is_star:
                    stocks.append({
                        'code': code,
                        'name': name,
                    })

            print(f"成功获取 {len(stocks)} 只A股股票")
            save_stock_list(stocks)
            return stocks

    except Exception as e:
        print(f"方法1失败: {e}")

    # 方法2: 使用硬编码的主要股票列表
    print("使用内置股票列表...")
    stocks = get_major_stocks()
    save_stock_list(stocks)
    return stocks


def get_major_stocks():
    """获取主要股票列表（备用）"""
    # 这里包含主要的A股
    stocks = []

    # 上证50成分
    sh50 = [
        '600519', '600036', '601318', '601166', '600000', '601328', '601398',
        '601939', '601288', '601988', '601088', '600030', '601601', '601888',
        '600276', '600900', '601012', '600016', '600104', '601888', '601668',
        '601390', '601857', '600887', '601658', '601211', '600050', '601888',
        '601066', '601628', '600585', '601888', '600089', '601766', '601788',
        '601818', '601857', '601888', '601939', '600104', '600000', '601398',
        '601328', '600016', '600030', '601318', '600519', '600036', '601166',
        '600276', '600887', '601888', '601012', '600900', '600438', '601012',
    ]

    # 深证成指成分
    sz_components = [
        '000001', '000002', '000333', '000651', '000858', '002594', '300059',
        '300015', '300750', '002475', '300760', '002841', '300274', '000568',
        '002304', '603259', '600438', '688981', '688111', '688599', '600809',
        '000725', '002415', '300014', '300003', '000063', '002475', '300124',
        '002271', '000100', '002008', '300033', '300142', '002049', '300433',
        '300122', '002601', '002475', '300059', '300017', '300274', '300347',
        '002607', '300474', '300676', '300760', '300750', '002821', '300036',
    ]

    # 中证500成分（部分）
    zz500 = [
        '600809', '000568', '002304', '600438', '000768', '600566', '600570',
        '600582', '600594', '600660', '600741', '600761', '600783', '600789',
        '600820', '600869', '600875', '600880', '600903', '600958', '600963',
        '600985', '600998', '601000', '601015', '601077', '601098', '601117',
        '601127', '601138', '601155', '601163', '601198', '601218', '601225',
        '601231', '601233', '601288', '601319', '601333', '601369', '601388',
        '601515', '601555', '601566', '601577', '601588', '601598', '601600',
        '601606', '601608', '601611', '601615', '601618', '601628', '601633',
        '601666', '601668', '601669', '601678', '601688', '601696', '601699',
        '601700', '601717', '601718', '601727', '601766', '601768', '601777',
        '601788', '601798', '601800', '601801', '601808', '601816', '601818',
        '601828', '601838', '601857', '601865', '601868', '601869', '601872',
        '601877', '601878', '601880', '601881', '601883', '601886', '601888',
        '601890', '601898', '601899', '601901', '601919', '601928', '601933',
        '601939', '601949', '601958', '601963', '601969', '601985', '601988',
        '601989', '601995', '601997', '601998',
    ]

    # 合并去重
    all_codes = list(set(sh50 + sz_components + zz500))

    # 获取股票名称
    for code in all_codes:
        try:
            info = ak.stock_individual_info_em(symbol=code)
            name = info.iloc[1]['item'] if len(info) > 1 else ''
            stocks.append({'code': code, 'name': name})
            time.sleep(0.5)
        except:
            stocks.append({'code': code, 'name': ''})

    print(f"使用内置列表，共 {len(stocks)} 只股票")
    return stocks


def download_stock_kline(code, name, data_dir, days=365, max_retries=5):
    """下载单只股票K线数据"""
    for attempt in range(max_retries):
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq"
            )

            if df.empty:
                return {'success': False, 'error': '无数据'}

            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount'
            })

            df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df = df.tail(days)

            output_file = data_dir / f'stock_{code}.csv'
            df.to_csv(output_file, index=False, encoding='utf-8-sig')

            return {
                'success': True,
                'count': len(df),
                'start': str(df['date'].min()),
                'end': str(df['date'].max())
            }

        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)
                time.sleep(wait_time)
                continue
            return {'success': False, 'error': str(e)}


def main():
    """主函数"""
    print("=" * 70)
    print(" " * 20 + "A股全市场数据下载工具")
    print("=" * 70)
    print()

    # 配置
    DAYS = 365
    BATCH_SIZE = 20
    DELAY = 3  # 每批之间延迟3秒
    RETRY_DELAY = 5  # 失败重试延迟

    # 创建数据目录
    data_dir = PROJECT_ROOT / 'data' / 'stocks'
    data_dir.mkdir(parents=True, exist_ok=True)

    # 加载进度
    progress = load_progress()
    downloaded_set = set(progress['downloaded'])

    # 获取股票列表
    stocks = load_stock_list()
    if stocks is None:
        stocks = get_all_a_stocks()

    if not stocks:
        print("无法获取股票列表")
        return

    print(f"\n股票总数: {len(stocks)}")
    print(f"已下载: {len(downloaded_set)}")
    print(f"待下载: {len(stocks) - len(downloaded_set)}")
    print(f"数据目录: {data_dir}")
    print(f"时间范围: 最近 {DAYS} 天")
    print()

    # 过滤已下载的股票
    pending = [s for s in stocks if s['code'] not in downloaded_set]

    if not pending:
        print("所有股票已下载完成！")
        return

    print(f"开始下载 {len(pending)} 只股票...")
    print()

    # 分批下载
    total_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    success_count = 0
    fail_count = 0

    for batch_idx in range(total_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min((batch_idx + 1) * BATCH_SIZE, len(pending))
        batch = pending[start_idx:end_idx]

        print(f"\n--- 批次 {batch_idx + 1}/{total_batches} (股票 {start_idx + 1}-{end_idx}) ---")

        for i, stock in enumerate(batch):
            code = stock['code']
            name = stock['name']
            idx = start_idx + i + 1
            total_done = len(downloaded_set) + success_count

            print(f"[{total_done + 1}/{len(stocks)}] {code} {name}...", end=' ', flush=True)

            result = download_stock_kline(code, name, data_dir, DAYS)

            if result['success']:
                print(f"OK ({result['count']}条)")
                success_count += 1
                progress['downloaded'].append(code)
                # 每10个保存一次进度
                if (success_count % 10) == 0:
                    save_progress(progress)
            else:
                print(f"FAIL ({result['error'][:50]}...)")
                fail_count += 1
                progress['failed'][code] = result['error']

            time.sleep(DELAY)

        # 每批完成后保存进度
        save_progress(progress)
        print(f"\n本批进度: 成功 {success_count}, 失败 {fail_count}")
        print(f"总进度: {len(downloaded_set) + success_count}/{len(stocks)}")

        # 批次间延迟
        if batch_idx < total_batches - 1:
            print(f"等待 {RETRY_DELAY} 秒后继续...")
            time.sleep(RETRY_DELAY)

    # 最终统计
    progress['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_progress(progress)

    print("\n" + "=" * 70)
    print("下载完成！")
    print("=" * 70)
    print(f"股票总数: {len(stocks)}")
    print(f"本次成功: {success_count}")
    print(f"本次失败: {fail_count}")
    print(f"已下载总数: {len(progress['downloaded'])}")
    print(f"成功率: {len(progress['downloaded'])/len(stocks)*100:.1f}%")

    if progress['failed']:
        print(f"\n失败股票: {len(progress['failed'])}")
        print("可以重新运行脚本继续下载失败的股票")

    # 显示目录大小
    stock_files = list(data_dir.glob('stock_*.csv'))
    total_size = sum(f.stat().st_size for f in stock_files)
    print(f"\n数据目录: {len(stock_files)} 个文件")
    print(f"总大小: {total_size / 1024 / 1024:.2f} MB")


if __name__ == '__main__':
    main()
