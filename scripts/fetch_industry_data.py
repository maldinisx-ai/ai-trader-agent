# -*- coding: utf-8 -*-
"""
获取行业分类和板块数据

提供以下功能：
1. 获取股票行业分类
2. 获取行业板块指数
3. 获取概念板块数据
4. 分析行业资金流向
"""

import os
import sys
import io
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


def get_industry_classification():
    """获取行业分类"""
    print("=" * 60)
    print("获取行业分类")
    print("=" * 60)

    try:
        # 获取行业板块名称
        df = ak.stock_board_industry_name_em()
        print(f"\n行业板块 ({len(df)} 个):")
        print(df.to_string())

        # 保存
        data_dir = PROJECT_ROOT / 'data'
        data_dir.mkdir(exist_ok=True)
        output_file = data_dir / 'industry_classification.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n已保存到: {output_file}")

        return df
    except Exception as e:
        print(f"获取行业分类失败: {e}")
        return None


def get_industry_stocks(industry_name):
    """获取指定行业的股票列表"""
    try:
        # 获取申万行业成分股
        df = ak.sw_index_cons(index_code=industry_name)
        return df
    except Exception as e:
        print(f"获取 {industry_name} 成分股失败: {e}")
        return None


def get_sector_index_data():
    """获取主要板块指数数据"""
    print("\n" + "=" * 60)
    print("获取主要板块指数")
    print("=" * 60)

    sectors = [
        ('银行', 'bank'),
        ('医药', 'medicine'),
        ('食品饮料', 'food'),
        ('新能源', 'new_energy'),
        ('半导体', 'semiconductor'),
        ('军工', 'military'),
        ('房地产', 'real_estate'),
    ]

    data_dir = PROJECT_ROOT / 'data' / 'sectors'
    data_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for name_cn, name_en in sectors:
        try:
            # 这里使用东方财富的行业指数
            # 实际应用中需要查找对应的指数代码
            print(f"获取 {name_cn} 指数数据...")
            # TODO: 实现具体的指数获取逻辑
            results[name_cn] = {'status': 'pending'}
        except Exception as e:
            print(f"  失败: {e}")
            results[name_cn] = {'status': 'failed', 'error': str(e)}

    return results


def get_concept_sectors():
    """获取概念板块数据"""
    print("\n" + "=" * 60)
    print("获取概念板块")
    print("=" * 60)

    try:
        # 获取概念板块列表
        df = ak.stock_board_concept_name_em()
        print(f"\n共 {len(df)} 个概念板块")
        print("\n热门概念板块 (前20):")
        print(df.head(20).to_string())

        # 保存
        data_dir = PROJECT_ROOT / 'data'
        data_dir.mkdir(exist_ok=True)
        output_file = data_dir / 'concept_sectors.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n已保存到: {output_file}")

        return df
    except Exception as e:
        print(f"获取概念板块失败: {e}")
        return None


def get_stock_industry_info(stock_code):
    """获取单只股票的行业信息"""
    try:
        # 获取个股信息
        df = ak.stock_individual_info_em(symbol=stock_code)
        return df
    except Exception as e:
        print(f"获取 {stock_code} 行业信息失败: {e}")
        return None


def analyze_industry_performance():
    """分析行业表现"""
    print("\n" + "=" * 60)
    print("分析行业板块表现")
    print("=" * 60)

    try:
        # 获取行业板块实时行情
        df = ak.stock_board_industry_spot_em()

        print("\n行业板块涨跌幅排名:")
        if '涨跌幅' in df.columns:
            df_sorted = df.sort_values('涨跌幅', ascending=False)
        else:
            df_sorted = df
        print(df_sorted.to_string())

        # 保存
        data_dir = PROJECT_ROOT / 'data'
        output_file = data_dir / 'industry_performance.csv'
        df_sorted.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n已保存到: {output_file}")

        return df_sorted
    except Exception as e:
        print(f"分析行业表现失败: {e}")
        return None


def get_industry_fund_flow():
    """获取行业资金流向"""
    print("\n" + "=" * 60)
    print("获取行业资金流向")
    print("=" * 60)

    try:
        # 获取行业资金流向
        df = ak.stock_fund_flow_industry()

        print("\n行业资金流向排名:")
        print(df.head(20).to_string())

        # 保存
        data_dir = PROJECT_ROOT / 'data'
        output_file = data_dir / 'industry_fund_flow.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n已保存到: {output_file}")

        return df
    except Exception as e:
        print(f"获取行业资金流向失败: {e}")
        return None


def main():
    """主函数"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "行业分类与板块数据工具" + " " * 24 + "║")
    print("╚" + "═" * 58 + "╝")

    # 1. 获取申万行业分类
    sw1 = get_industry_classification()

    # 2. 获取概念板块
    concepts = get_concept_sectors()

    # 3. 分析行业表现
    performance = analyze_industry_performance()

    # 4. 获取行业资金流向
    fund_flow = get_industry_fund_flow()

    print("\n" + "=" * 60)
    print("数据获取完成！")
    print("=" * 60)

    # 显示已下载的文件
    data_dir = PROJECT_ROOT / 'data'
    files = [
        'industry_classification.csv',
        'concept_sectors.csv',
        'industry_performance.csv',
        'industry_fund_flow.csv'
    ]

    print("\n已下载的数据文件:")
    for f in files:
        file_path = data_dir / f
        if file_path.exists():
            df = pd.read_csv(file_path)
            print(f"  ✓ {f}: {len(df)} 条记录")
        else:
            print(f"  ✗ {f}: 未下载")

    print("\n" + "=" * 60)
    print("行业数据可用于:")
    print("  1. 行业轮动策略")
    print("  2. 行业配置优化")
    print("  3. 行业资金流向分析")
    print("  4. 个股行业归类")
    print("=" * 60)


if __name__ == '__main__':
    main()
