# -*- coding: utf-8 -*-
"""
数据覆盖率检查和补充下载脚本

检查当前数据覆盖情况，并下载缺失的数据类型。
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Set
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import finshare as fs
    import pandas as pd
except ImportError as e:
    print("错误: 需要安装 finshare 和 pandas")
    print("安装命令: pip install finshare pandas")
    sys.exit(1)


class DataCoverageChecker:
    """数据覆盖率检查器"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)

        # 数据目录
        self.klines_dir = self.base_dir / "stocks"
        self.financial_dir = self.base_dir / "financial"
        self.fundamentals_dir = self.base_dir / "fundamentals"
        self.money_flow_dir = self.base_dir / "money_flow"
        self.margin_dir = self.base_dir / "margin"

        # 数据类型文件模式
        self.patterns = {
            "klines": "_SH.csv",  # K线
            "income": "income_",   # 利润表
            "balance": "balance_", # 资产负债表
            "cashflow": "cashflow_", # 现金流量表
            "indicator": "indicator_", # 财务指标
            "dividend": "dividend_",   # 分红
            "money_flow": "money_flow_", # 资金流向
            "margin_detail": "margin_detail_", # 融资融券详情
        }

    def get_stock_list(self) -> List[str]:
        """从K线目录获取股票列表"""
        stocks = set()
        if self.klines_dir.exists():
            for f in self.klines_dir.glob("*.csv"):
                # 从文件名提取股票代码: 000001_SZ.csv -> 000001.SZ
                name = f.stem
                if '_' in name:
                    code, market = name.split('_', 1)
                    stocks.add(f"{code}.{market}")
        return sorted(stocks)

    def check_coverage(self, symbol: str) -> Dict[str, bool]:
        """检查单只股票的数据覆盖情况"""
        filename_base = symbol.replace('.', '_')
        coverage = {}

        # K线数据
        coverage["klines"] = (self.klines_dir / f"{filename_base}.csv").exists()

        # 财务数据
        coverage["income"] = (self.financial_dir / f"income_{filename_base}.csv").exists()
        coverage["balance"] = (self.financial_dir / f"balance_{filename_base}.csv").exists()
        coverage["cashflow"] = (self.financial_dir / f"cashflow_{filename_base}.csv").exists()

        # 财务指标
        coverage["indicator"] = (self.fundamentals_dir / f"indicator_{filename_base}.csv").exists()
        coverage["dividend"] = (self.fundamentals_dir / f"dividend_{filename_base}.csv").exists()

        # 资金流向
        coverage["money_flow"] = (self.money_flow_dir / f"money_flow_{filename_base}.csv").exists()

        # 融资融券
        coverage["margin_detail"] = (self.margin_dir / f"margin_detail_{filename_base}.csv").exists()

        return coverage

    def generate_report(self) -> Dict:
        """生成数据覆盖率报告"""
        stocks = self.get_stock_list()
        print(f"发现 {len(stocks)} 只股票")

        report = {
            "total_stocks": len(stocks),
            "data_types": {},
            "stocks_missing_data": {},
            "summary": {}
        }

        # 统计每种数据类型的覆盖率
        type_counts = {k: 0 for k in self.patterns.keys()}

        # 统计缺失数据的股票
        missing_any = []

        for stock in stocks:
            coverage = self.check_coverage(stock)
            missing = [k for k, v in coverage.items() if not v]

            if missing:
                missing_any.append({
                    "symbol": stock,
                    "missing": missing
                })

            for data_type, has_data in coverage.items():
                if has_data:
                    type_counts[data_type] = type_counts.get(data_type, 0) + 1

        report["data_types"] = {
            k: {
                "count": v,
                "coverage": f"{v * 100 / len(stocks):.1f}%" if stocks else "0%"
            }
            for k, v in type_counts.items()
        }

        report["stocks_missing_data"] = missing_any
        report["summary"] = {
            "stocks_with_all_data": len(stocks) - len(missing_any),
            "stocks_missing_any": len(missing_any),
            "completion_rate": f"{(len(stocks) - len(missing_any)) * 100 / len(stocks):.1f}%" if stocks else "0%"
        }

        return report

    def print_report(self, report: Dict = None):
        """打印报告"""
        if report is None:
            report = self.generate_report()

        print("\n" + "=" * 60)
        print("数据覆盖率报告")
        print("=" * 60)

        print(f"\n总股票数: {report['total_stocks']}")
        print(f"\n数据类型覆盖:")
        for data_type, stats in report["data_types"].items():
            print(f"  {data_type:15s}: {stats['count']:4d} ({stats['coverage']})")

        print(f"\n完成度统计:")
        print(f"  完整数据股票: {report['summary']['stocks_with_all_data']}")
        print(f"  缺失数据股票: {report['summary']['stocks_missing_any']}")
        print(f"  完成率: {report['summary']['completion_rate']}")

        # 显示缺失数据的股票（最多20个）
        missing = report["stocks_missing_data"]
        if missing:
            print(f"\n缺失数据股票示例 (共{len(missing)}只):")
            for item in missing[:20]:
                missing_str = ", ".join(item["missing"])
                print(f"  {item['symbol']:12s}: {missing_str}")
            if len(missing) > 20:
                print(f"  ... 还有 {len(missing) - 20} 只")

        print("=" * 60)

    def save_report(self, report: Dict = None, output_file: str = None):
        """保存报告到文件"""
        if report is None:
            report = self.generate_report()
        if output_file is None:
            output_file = self.base_dir / "coverage_report.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n报告已保存: {output_file}")

    def get_missing_downloads(self, report: Dict) -> Dict[str, List[str]]:
        """获取需要下载的数据类型和股票列表"""
        missing = {
            "income": [],
            "balance": [],
            "cashflow": [],
            "indicator": [],
            "dividend": [],
            "money_flow": [],
            "margin_detail": [],
        }

        for item in report["stocks_missing_data"]:
            symbol = item["symbol"]
            for data_type in item["missing"]:
                if data_type in missing:
                    missing[data_type].append(symbol)

        return missing


class DataSupplementDownloader:
    """数据补充下载器"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.financial_dir = self.base_dir / "financial"
        self.fundamentals_dir = self.base_dir / "fundamentals"
        self.money_flow_dir = self.base_dir / "money_flow"
        self.margin_dir = self.base_dir / "margin"

        self.stats = {"success": 0, "fail": 0, "skip": 0}

    def _save_df(self, df: pd.DataFrame, filepath: Path) -> bool:
        """保存DataFrame到文件"""
        if df is not None and not df.empty:
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            return True
        return False

    def download_income(self, symbols: List[str]):
        """批量下载利润表"""
        print(f"\n[下载利润表] {len(symbols)} 只股票")
        for symbol in symbols:
            try:
                df = fs.get_income(symbol)
                if df is not None and not df.empty:
                    filename = f"income_{symbol.replace('.', '_')}.csv"
                    filepath = self.financial_dir / filename
                    if self._save_df(df, filepath):
                        print(f"  [OK] {symbol}")
                        self.stats["success"] += 1
                    else:
                        print(f"  [SKIP] {symbol} (空数据)")
                        self.stats["skip"] += 1
            except Exception as e:
                print(f"  [ERROR] {symbol} - {e}")
                self.stats["fail"] += 1

    def download_balance(self, symbols: List[str]):
        """批量下载资产负债表"""
        print(f"\n[下载资产负债表] {len(symbols)} 只股票")
        for symbol in symbols:
            try:
                df = fs.get_balance(symbol)
                if df is not None and not df.empty:
                    filename = f"balance_{symbol.replace('.', '_')}.csv"
                    filepath = self.financial_dir / filename
                    if self._save_df(df, filepath):
                        print(f"  [OK] {symbol}")
                        self.stats["success"] += 1
            except Exception as e:
                print(f"  [ERROR] {symbol} - {e}")
                self.stats["fail"] += 1

    def download_cashflow(self, symbols: List[str]):
        """批量下载现金流量表"""
        print(f"\n[下载现金流量表] {len(symbols)} 只股票")
        for symbol in symbols:
            try:
                df = fs.get_cashflow(symbol)
                if df is not None and not df.empty:
                    filename = f"cashflow_{symbol.replace('.', '_')}.csv"
                    filepath = self.financial_dir / filename
                    if self._save_df(df, filepath):
                        print(f"  [OK] {symbol}")
                        self.stats["success"] += 1
            except Exception as e:
                print(f"  [ERROR] {symbol} - {e}")
                self.stats["fail"] += 1

    def download_indicator(self, symbols: List[str]):
        """批量下载财务指标"""
        print(f"\n[下载财务指标] {len(symbols)} 只股票")
        for symbol in symbols:
            try:
                df = fs.get_financial_indicator(symbol)
                if df is not None and not df.empty:
                    filename = f"indicator_{symbol.replace('.', '_')}.csv"
                    filepath = self.fundamentals_dir / filename
                    if self._save_df(df, filepath):
                        print(f"  [OK] {symbol}")
                        self.stats["success"] += 1
            except Exception as e:
                print(f"  [ERROR] {symbol} - {e}")
                self.stats["fail"] += 1

    def download_dividend(self, symbols: List[str]):
        """批量下载分红数据"""
        print(f"\n[下载分红数据] {len(symbols)} 只股票")
        for symbol in symbols:
            try:
                df = fs.get_dividend(symbol)
                if df is not None and not df.empty:
                    filename = f"dividend_{symbol.replace('.', '_')}.csv"
                    filepath = self.fundamentals_dir / filename
                    if self._save_df(df, filepath):
                        print(f"  [OK] {symbol}")
                        self.stats["success"] += 1
            except Exception as e:
                print(f"  [ERROR] {symbol} - {e}")
                self.stats["fail"] += 1

    def download_money_flow(self, symbols: List[str]):
        """批量下载资金流向"""
        print(f"\n[下载资金流向] {len(symbols)} 只股票")
        for symbol in symbols:
            try:
                df = fs.get_money_flow(symbol)
                if df is not None and not df.empty:
                    filename = f"money_flow_{symbol.replace('.', '_')}.csv"
                    filepath = self.money_flow_dir / filename
                    if self._save_df(df, filepath):
                        print(f"  [OK] {symbol}")
                        self.stats["success"] += 1
            except Exception as e:
                print(f"  [ERROR] {symbol} - {e}")
                self.stats["fail"] += 1

    def download_margin_detail(self, symbols: List[str]):
        """批量下载融资融券详情"""
        print(f"\n[下载融资融券详情] {len(symbols)} 只股票")
        for symbol in symbols:
            try:
                df = fs.get_margin_detail(symbol)
                if df is not None and not df.empty:
                    filename = f"margin_detail_{symbol.replace('.', '_')}.csv"
                    filepath = self.margin_dir / filename
                    if self._save_df(df, filepath):
                        print(f"  [OK] {symbol}")
                        self.stats["success"] += 1
            except Exception as e:
                print(f"  [ERROR] {symbol} - {e}")
                self.stats["fail"] += 1

    def print_summary(self):
        """打印摘要"""
        print(f"\n{'='*60}")
        print("下载摘要")
        print(f"{'='*60}")
        print(f"成功: {self.stats['success']}")
        print(f"失败: {self.stats['fail']}")
        print(f"跳过: {self.stats['skip']}")
        print(f"{'='*60}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据覆盖率检查和补充下载")
    parser.add_argument("--check-only", action="store_true", help="仅检查覆盖率，不下载")
    parser.add_argument("--download", action="store_true", help="下载缺失的数据")
    parser.add_argument("--types", type=str, nargs="+",
                        choices=["income", "balance", "cashflow", "indicator", "dividend", "money_flow", "margin_detail", "all"],
                        help="指定下载的数据类型")
    parser.add_argument("--output", type=str, default="data", help="数据目录")

    args = parser.parse_args()

    # 1. 检查覆盖率
    print("步骤 1: 检查数据覆盖率...")
    checker = DataCoverageChecker(base_dir=args.output)
    report = checker.generate_report()
    checker.print_report()
    checker.save_report(report)

    # 如果只检查，直接退出
    if args.check_only:
        return 0

    # 2. 下载缺失数据
    if args.download:
        missing = checker.get_missing_downloads(report)

        # 统计需要下载的数量
        total_to_download = sum(len(v) for v in missing.values())
        print(f"\n步骤 2: 需要下载 {total_to_download} 个文件")

        downloader = DataSupplementDownloader(base_dir=args.output)

        # 确定要下载的类型
        types_to_download = args.types if args.types and "all" not in args.types else list(missing.keys())

        for data_type in types_to_download:
            symbols = missing.get(data_type, [])
            if not symbols:
                continue

            if data_type == "income":
                downloader.download_income(symbols)
            elif data_type == "balance":
                downloader.download_balance(symbols)
            elif data_type == "cashflow":
                downloader.download_cashflow(symbols)
            elif data_type == "indicator":
                downloader.download_indicator(symbols)
            elif data_type == "dividend":
                downloader.download_dividend(symbols)
            elif data_type == "money_flow":
                downloader.download_money_flow(symbols)
            elif data_type == "margin_detail":
                downloader.download_margin_detail(symbols)

        downloader.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
