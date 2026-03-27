# -*- coding: utf-8 -*-
"""
综合金融数据下载脚本

支持下载多种类型数据：
- 股票K线数据
- 财务报表（利润表、资产负债表、现金流量表）
- 财务指标
- 资金流向
- 融资融券
- 龙虎榜
- 行业数据
- 指数数据
- 基金数据
- 期货数据
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
import argparse

try:
    import finshare as fs
    import pandas as pd
except ImportError as e:
    print("错误: 需要安装 finshare 和 pandas")
    print("安装命令: pip install finshare pandas")
    sys.exit(1)


class ComprehensiveDataDownloader:
    """综合金融数据下载器"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 子目录
        self.klines_dir = self.base_dir / "klines"
        self.financial_dir = self.base_dir / "financial"
        self.fundamentals_dir = self.base_dir / "fundamentals"
        self.money_flow_dir = self.base_dir / "money_flow"
        self.margin_dir = self.base_dir / "margin"
        self.lhb_dir = self.base_dir / "lhb"
        self.industry_dir = self.base_dir / "industry"
        self.index_dir = self.base_dir / "index"
        self.fund_dir = self.base_dir / "fund"
        self.future_dir = self.base_dir / "future"

        for d in [
            self.klines_dir, self.financial_dir, self.fundamentals_dir,
            self.money_flow_dir, self.margin_dir, self.lhb_dir,
            self.industry_dir, self.index_dir, self.fund_dir, self.future_dir
        ]:
            d.mkdir(exist_ok=True)

        self.stats = {
            "success": 0,
            "fail": 0,
            "skip": 0
        }

    def _save_df(self, df: pd.DataFrame, filepath: Path):
        """保存DataFrame到文件"""
        if df is not None and not df.empty:
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            return True
        return False

    # ==================== 股票K线数据 ====================

    def download_stock_klines(
        self,
        symbol: str,
        days: int = 365,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        """下载股票K线数据"""
        try:
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            df = fs.get_historical_data(symbol, start=start_date, end=end_date)
            if df is not None and not df.empty:
                filename = symbol.replace('.', '_') + '.csv'
                filepath = self.klines_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] K线: {symbol} ({len(df)}条)")
                self.stats["success"] += 1
            else:
                print(f"  [SKIP] K线: {symbol} (无数据)")
                self.stats["skip"] += 1
        except Exception as e:
            print(f"  [ERROR] K线: {symbol} - {e}")
            self.stats["fail"] += 1

    # ==================== 财务报表 ====================

    def download_income_statement(self, symbol: str):
        """下载利润表"""
        try:
            df = fs.get_income(symbol)
            if df is not None and not df.empty:
                filename = f"income_{symbol.replace('.', '_')}.csv"
                filepath = self.financial_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 利润表: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 利润表: {symbol} - {e}")
            self.stats["fail"] += 1

    def download_balance_sheet(self, symbol: str):
        """下载资产负债表"""
        try:
            df = fs.get_balance(symbol)
            if df is not None and not df.empty:
                filename = f"balance_{symbol.replace('.', '_')}.csv"
                filepath = self.financial_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 资产负债表: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 资产负债表: {symbol} - {e}")
            self.stats["fail"] += 1

    def download_cash_flow(self, symbol: str):
        """下载现金流量表"""
        try:
            df = fs.get_cashflow(symbol)
            if df is not None and not df.empty:
                filename = f"cashflow_{symbol.replace('.', '_')}.csv"
                filepath = self.financial_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 现金流量表: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 现金流量表: {symbol} - {e}")
            self.stats["fail"] += 1

    def download_financial_indicator(self, symbol: str):
        """下载财务指标"""
        try:
            df = fs.get_financial_indicator(symbol)
            if df is not None and not df.empty:
                filename = f"indicator_{symbol.replace('.', '_')}.csv"
                filepath = self.fundamentals_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 财务指标: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 财务指标: {symbol} - {e}")
            self.stats["fail"] += 1

    def download_dividend(self, symbol: str):
        """下载分红数据"""
        try:
            df = fs.get_dividend(symbol)
            if df is not None and not df.empty:
                filename = f"dividend_{symbol.replace('.', '_')}.csv"
                filepath = self.fundamentals_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 分红数据: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 分红数据: {symbol} - {e}")
            self.stats["fail"] += 1

    def download_all_financial_data(self, symbol: str):
        """下载所有财务相关数据"""
        print(f"\n[财务数据] {symbol}:")
        self.download_income_statement(symbol)
        self.download_balance_sheet(symbol)
        self.download_cash_flow(symbol)
        self.download_financial_indicator(symbol)
        self.download_dividend(symbol)

    # ==================== 资金流向 ====================

    def download_money_flow(self, symbol: str):
        """下载个股资金流向"""
        try:
            df = fs.get_money_flow(symbol)
            if df is not None and not df.empty:
                filename = f"money_flow_{symbol.replace('.', '_')}.csv"
                filepath = self.money_flow_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 资金流向: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 资金流向: {symbol} - {e}")
            self.stats["fail"] += 1

    def download_margin(self, symbol: str = None):
        """下载融资融券数据"""
        try:
            df = fs.get_margin(code=symbol)
            if df is not None and not df.empty:
                if symbol:
                    filename = f"margin_{symbol.replace('.', '_')}.csv"
                else:
                    filename = "margin_all.csv"
                filepath = self.margin_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 融资融券: {symbol if symbol else '全部'}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 融资融券: {e}")
            self.stats["fail"] += 1

    def download_margin_detail(self, symbol: str):
        """下载融资融券详情"""
        try:
            df = fs.get_margin_detail(symbol)
            if df is not None and not df.empty:
                filename = f"margin_detail_{symbol.replace('.', '_')}.csv"
                filepath = self.margin_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 融资融券详情: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 融资融券详情: {symbol} - {e}")
            self.stats["fail"] += 1

    # ==================== 龙虎榜 ====================

    def download_lhb(self, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """下载龙虎榜数据"""
        try:
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            df = fs.get_lhb(start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                filename = f"lhb_{start_date}_{end_date}.csv"
                filepath = self.lhb_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 龙虎榜: {len(df)}条记录")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 龙虎榜: {e}")
            self.stats["fail"] += 1

    def download_lhb_detail(self, symbol: str, trade_date: Optional[str] = None):
        """下载龙虎榜个股详情"""
        try:
            df = fs.get_lhb_detail(symbol, trade_date=trade_date)
            if df is not None and not df.empty:
                filename = f"lhb_detail_{symbol.replace('.', '_')}.csv"
                filepath = self.lhb_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 龙虎榜详情: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 龙虎榜详情: {symbol} - {e}")
            self.stats["fail"] += 1

    # ==================== 行业数据 ====================

    def download_sw_industry_list(self, level: int = 3):
        """下载申万行业列表"""
        try:
            df = fs.get_sw_industry_list(level=level)
            if df is not None and not df.empty:
                filename = f"sw_industry_level{level}.csv"
                filepath = self.industry_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 申万行业列表 (L{level}): {len(df)}个行业")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 申万行业列表: {e}")
            self.stats["fail"] += 1

    def download_sw_industry_analysis(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        level: int = 1
    ):
        """下载申万行业分析"""
        try:
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            df = fs.get_sw_industry_analysis(start_date=start_date, end_date=end_date, level=level)
            if df is not None and not df.empty:
                filename = f"sw_industry_analysis_{start_date}_{end_date}.csv"
                filepath = self.industry_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 申万行业分析: {len(df)}条记录")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 申万行业分析: {e}")
            self.stats["fail"] += 1

    def download_money_flow_industry(self):
        """下载行业资金流向"""
        try:
            df = fs.get_money_flow_industry()
            if df is not None and not df.empty:
                filename = "money_flow_industry.csv"
                filepath = self.industry_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 行业资金流向: {len(df)}个行业")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 行业资金流向: {e}")
            self.stats["fail"] += 1

    # ==================== 指数数据 ====================

    def download_index_pe(self, symbol: str = "sh000001"):
        """下载指数市盈率"""
        try:
            df = fs.get_index_pe(symbol)
            if df is not None and not df.empty:
                filename = f"index_pe_{symbol}.csv"
                filepath = self.index_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 指数市盈率: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 指数市盈率: {symbol} - {e}")
            self.stats["fail"] += 1

    def download_index_pb(self, symbol: str = "sh000001"):
        """下载指数市净率"""
        try:
            df = fs.get_index_pb(symbol)
            if df is not None and not df.empty:
                filename = f"index_pb_{symbol}.csv"
                filepath = self.index_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 指数市净率: {symbol}")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 指数市净率: {symbol} - {e}")
            self.stats["fail"] += 1

    def download_market_pb(self):
        """下载市场市净率"""
        try:
            df = fs.get_market_pb()
            if df is not None and not df.empty:
                filename = "market_pb.csv"
                filepath = self.index_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 市场市净率: {len(df)}条记录")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 市场市净率: {e}")
            self.stats["fail"] += 1

    # ==================== 基金数据 ====================

    def download_fund_list(self, market: str = 'all'):
        """下载基金列表"""
        try:
            df = fs.get_fund_list(market=market)
            if df is not None and not df.empty:
                filename = f"fund_list_{market}.csv"
                filepath = self.fund_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 基金列表 ({market}): {len(df)}只基金")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 基金列表: {e}")
            self.stats["fail"] += 1

    def download_fund_nav(self, code: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """下载基金净值"""
        try:
            df = fs.get_fund_nav(code, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                filename = f"fund_nav_{code}.csv"
                filepath = self.fund_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 基金净值: {code} ({len(df)}条记录)")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 基金净值: {code} - {e}")
            self.stats["fail"] += 1

    def download_etf_list(self):
        """下载ETF列表"""
        try:
            df = fs.get_etf_list()
            if df is not None and not df.empty:
                filename = "etf_list.csv"
                filepath = self.fund_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] ETF列表: {len(df)}只ETF")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] ETF列表: {e}")
            self.stats["fail"] += 1

    # ==================== 期货数据 ====================

    def download_future_list(self):
        """下载期货列表"""
        try:
            df = fs.get_future_list()
            if df is not None and not df.empty:
                filename = "future_list.csv"
                filepath = self.future_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 期货列表: {len(df)}个合约")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 期货列表: {e}")
            self.stats["fail"] += 1

    def download_future_kline(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        """下载期货K线"""
        try:
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            df = fs.get_future_kline(code, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                filename = f"future_{code}.csv"
                filepath = self.future_dir / filename
                self._save_df(df, filepath)
                print(f"  [OK] 期货K线: {code} ({len(df)}条记录)")
                self.stats["success"] += 1
        except Exception as e:
            print(f"  [ERROR] 期货K线: {code} - {e}")
            self.stats["fail"] += 1

    # ==================== 批量下载 ====================

    def download_all_for_stock(self, symbol: str, download_klines: bool = True):
        """下载单个股票的所有数据"""
        print(f"\n{'='*60}")
        print(f"下载股票完整数据: {symbol}")
        print(f"{'='*60}")

        # K线
        if download_klines:
            self.download_stock_klines(symbol)

        # 财务
        self.download_all_financial_data(symbol)

        # 资金流向
        print(f"\n[资金数据] {symbol}:")
        self.download_money_flow(symbol)
        self.download_margin_detail(symbol)

    def download_market_overview(self):
        """下载市场概览数据"""
        print(f"\n{'='*60}")
        print("下载市场概览数据")
        print(f"{'='*60}")

        # 龙虎榜
        print("\n[龙虎榜]:")
        self.download_lhb()

        # 行业数据
        print("\n[行业数据]:")
        self.download_sw_industry_list(level=1)
        self.download_sw_industry_list(level=2)
        self.download_sw_industry_list(level=3)
        self.download_sw_industry_analysis(level=1)
        self.download_money_flow_industry()

        # 指数数据
        print("\n[指数数据]:")
        self.download_index_pe("sh000001")  # 上证指数
        self.download_index_pb("sh000001")
        self.download_market_pb()

        # 融资融券
        print("\n[融资融券]:")
        self.download_margin()

        # 基金
        print("\n[基金数据]:")
        self.download_fund_list()
        self.download_etf_list()

        # 期货
        print("\n[期货数据]:")
        self.download_future_list()

    def print_summary(self):
        """打印下载摘要"""
        print(f"\n{'='*60}")
        print("下载摘要")
        print(f"{'='*60}")
        print(f"成功: {self.stats['success']}")
        print(f"失败: {self.stats['fail']}")
        print(f"跳过: {self.stats['skip']}")
        print(f"{'='*60}")

        # 保存摘要
        summary_file = self.base_dir / "download_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "data_source": "finshare"
            }, f, indent=2, ensure_ascii=False)
        print(f"\n摘要已保存: {summary_file}")


    # ==================== 批量下载 ====================

    def download_all_stocks(
        self,
        symbols: List[str],
        skip_existing: bool = True,
        save_interval: int = 50
    ):
        """批量下载所有股票数据"""
        print(f"\n{'='*60}")
        print(f"批量下载 {len(symbols)} 只股票")
        print(f"{'='*60}")

        progress_file = self.base_dir / "batch_progress.json"
        progress = self._load_progress(progress_file)

        downloaded = progress.get("downloaded", [])
        failed = progress.get("failed", [])

        for i, symbol in enumerate(symbols, 1):
            # 跳过已下载
            if skip_existing and symbol in downloaded:
                continue

            print(f"\n[{i}/{len(symbols)}] 处理 {symbol}...")

            try:
                self.download_all_for_stock(symbol, download_klines=True)
                downloaded.append(symbol)
            except Exception as e:
                print(f"  [ERROR] {symbol} 失败: {e}")
                if symbol not in failed:
                    failed.append(symbol)

            # 定期保存进度
            if i % save_interval == 0:
                self._save_progress(progress_file, downloaded, failed)
                print(f"\n--- 进度保存: 成功 {len(downloaded)}, 失败 {len(failed)} ---")

        # 最终保存
        self._save_progress(progress_file, downloaded, failed)

    def _load_progress(self, progress_file: Path) -> dict:
        """加载进度"""
        if progress_file.exists():
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"downloaded": [], "failed": []}

    def _save_progress(self, progress_file: Path, downloaded: List[str], failed: List[str]):
        """保存进度"""
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump({
                "downloaded": downloaded,
                "failed": failed,
                "last_update": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="综合金融数据下载器 - 基于 finshare",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 下载股票完整数据
  python scripts/download_comprehensive.py --stock 000001.SZ

  # 下载多只股票
  python scripts/download_comprehensive.py --stocks 000001.SZ 600519.SH

  # 下载所有股票（从 all_stocks.json）
  python scripts/download_comprehensive.py --all

  # 下载所有股票，限制数量
  python scripts/download_comprehensive.py --all --limit 500

  # 下载市场概览
  python scripts/download_comprehensive.py --overview

  # 下载特定数据类型
  python scripts/download_comprehensive.py --financial 000001.SZ
  python scripts/download_comprehensive.py --money-flow 000001.SZ
  python scripts/download_comprehensive.py --lhb

  # 下载指数估值
  python scripts/download_comprehensive.py --index-valuation
        """
    )

    parser.add_argument("--stock", type=str, help="下载单只股票完整数据")
    parser.add_argument("--stocks", type=str, nargs="+", help="下载多只股票")
    parser.add_argument("--all", action="store_true", help="下载所有股票（从 all_stocks.json 读取）")
    parser.add_argument("--limit", type=int, help="限制下载数量")
    parser.add_argument("--force", action="store_true", help="强制重新下载（跳过已存在检查）")
    parser.add_argument("--overview", action="store_true", help="下载市场概览数据")
    parser.add_argument("--financial", action="store_true", help="只下载财务数据")
    parser.add_argument("--money-flow", action="store_true", help="只下载资金流向数据")
    parser.add_argument("--lhb", action="store_true", help="只下载龙虎榜数据")
    parser.add_argument("--index-valuation", action="store_true", help="只下载指数估值数据")
    parser.add_argument("--no-klines", action="store_true", help="不下载K线数据")
    parser.add_argument("--days", type=int, default=365, help="K线下载数据天数")
    parser.add_argument("--output", type=str, default="data", help="输出目录")

    args = parser.parse_args()

    downloader = ComprehensiveDataDownloader(base_dir=args.output)

    # 下载所有股票
    if args.all:
        stock_list_file = Path(args.output) / "all_stocks.json"
        if not stock_list_file.exists():
            print(f"错误: 找不到股票列表文件 {stock_list_file}")
            print("请先运行 python scripts/get_stock_list.py 生成股票列表")
            return 1

        with open(stock_list_file, 'r', encoding='utf-8') as f:
            stock_data = json.load(f)

        symbols = stock_data.get("codes", [])
        if args.limit:
            symbols = symbols[:args.limit]

        downloader.download_all_stocks(
            symbols,
            skip_existing=not args.force
        )

    # 单只股票
    elif args.stock:
        downloader.download_all_for_stock(args.stock, download_klines=not args.no_klines)
    # 多只股票
    elif args.stocks:
        for stock in args.stocks:
            downloader.download_all_for_stock(stock, download_klines=not args.no_klines)
    # 市场概览
    elif args.overview:
        downloader.download_market_overview()
    # 单独功能
    elif args.financial and args.stock:
        downloader.download_all_financial_data(args.stock)
    elif args.money_flow and args.stock:
        downloader.download_money_flow(args.stock)
        downloader.download_margin_detail(args.stock)
    elif args.lhb:
        downloader.download_lhb()
    elif args.index_valuation:
        downloader.download_index_pe("sh000001")
        downloader.download_index_pb("sh000001")
        downloader.download_market_pb()
    else:
        parser.print_help()
        return 1

    downloader.print_summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())