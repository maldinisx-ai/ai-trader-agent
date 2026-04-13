# -*- coding: utf-8 -*-
"""
检查已下载股票数据质量

验证数据完整性、异常值、缺失等问题
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd


class DataQualityChecker:
    """数据质量检查器"""

    def __init__(self, data_dir: str = "data/stocks"):
        self.data_dir = Path(data_dir)

    def check_file(self, file_path: Path) -> Dict:
        """
        检查单个文件的数据质量

        Returns:
            {
                'file': 文件名,
                'symbol': 股票代码,
                'status': 'ok' | 'warning' | 'error',
                'issues': 问题列表,
                'stats': 统计信息
            }
        """
        result = {
            'file': file_path.name,
            'symbol': file_path.stem.replace('_', '.'),
            'status': 'ok',
            'issues': [],
            'stats': {}
        }

        try:
            # 读取数据
            df = pd.read_csv(file_path)

            if df.empty:
                result['status'] = 'error'
                result['issues'].append('数据为空')
                return result

            # 统计信息
            result['stats'] = {
                'rows': len(df),
                'columns': len(df.columns),
                'columns_list': list(df.columns),
                'date_range': self._get_date_range(df)
            }

            # 检查必需列
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                result['status'] = 'error'
                result['issues'].append(f'缺少必需列: {missing_cols}')

            # 检查数据行数
            if len(df) < 50:
                result['status'] = 'error'
                result['issues'].append(f'数据过少: {len(df)} 行')
            elif len(df) < 200:
                result['status'] = 'warning'
                result['issues'].append(f'数据较少: {len(df)} 行')

            # 检查缺失值
            null_counts = df.isnull().sum()
            null_info = null_counts[null_counts > 0].to_dict()
            if null_info:
                result['status'] = 'error'
                result['issues'].append(f'存在缺失值: {null_info}')

            # 检查数值范围
            for col in ['open', 'high', 'low', 'close']:
                if col in df.columns:
                    if (df[col] <= 0).any():
                        result['status'] = 'error'
                        result['issues'].append(f'{col} 存在非正值')

            # 检查价格逻辑
            if all(c in df.columns for c in ['high', 'low', 'open', 'close']):
                # high 应该 >= max(open, close)
                invalid_high = df['high'] < df[['open', 'close']].max(axis=1)
                if invalid_high.any():
                    result['status'] = 'warning'
                    result['issues'].append(f'存在 {invalid_high.sum()} 行价格异常 (high < max(open,close))')

                # low 应该 <= min(open, close)
                invalid_low = df['low'] > df[['open', 'close']].min(axis=1)
                if invalid_low.any():
                    result['status'] = 'warning'
                    result['issues'].append(f'存在 {invalid_low.sum()} 行价格异常 (low > min(open,close))')

            # 检查成交量
            if 'volume' in df.columns:
                if (df['volume'] < 0).any():
                    result['status'] = 'error'
                    result['issues'].append('成交量存在负值')

            # 检查重复日期
            if 'date' in df.columns:
                duplicates = df['date'].duplicated().sum()
                if duplicates > 0:
                    result['status'] = 'warning'
                    result['issues'].append(f'存在 {duplicates} 个重复日期')

            # 检查日期顺序
            if 'date' in df.columns:
                df_sorted = df.sort_values('date')
                if not df.equals(df_sorted):
                    result['status'] = 'warning'
                    result['issues'].append('日期顺序不正确')

            # 添加价格统计
            if 'close' in df.columns:
                result['stats']['price'] = {
                    'min': float(df['close'].min()),
                    'max': float(df['close'].max()),
                    'latest': float(df['close'].iloc[-1])
                }

        except Exception as e:
            result['status'] = 'error'
            result['issues'].append(f'读取失败: {str(e)}')

        return result

    def _get_date_range(self, df: pd.DataFrame) -> Dict:
        """获取日期范围"""
        if 'date' not in df.columns:
            return {}

        try:
            df['date'] = pd.to_datetime(df['date'])
            return {
                'start': str(df['date'].min())[:10],
                'end': str(df['date'].max())[:10],
                'days': (df['date'].max() - df['date'].min()).days + 1
            }
        except:
            return {}

    def check_all(self) -> List[Dict]:
        """检查所有文件"""
        files = list(self.data_dir.glob('*.csv'))
        results = []

        for file_path in files:
            result = self.check_file(file_path)
            results.append(result)

        return results

    def generate_report(self, results: List[Dict]) -> str:
        """生成报告"""
        total = len(results)
        ok = sum(1 for r in results if r['status'] == 'ok')
        warning = sum(1 for r in results if r['status'] == 'warning')
        error = sum(1 for r in results if r['status'] == 'error')

        report = []
        report.append("=" * 70)
        report.append(" 📊 股票数据质量检查报告")
        report.append("=" * 70)
        report.append(f"\n检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"检查文件: {total} 个")
        report.append(f"\n统计结果:")
        report.append(f"  ✅ 正常: {ok} ({ok/total*100:.1f}%)")
        report.append(f"  ⚠️ 警告: {warning} ({warning/total*100:.1f}%)")
        report.append(f"  ❌ 错误: {error} ({error/total*100:.1f}%)")

        # 问题汇总
        issue_summary = {}
        for r in results:
            for issue in r['issues']:
                issue_summary[issue] = issue_summary.get(issue, 0) + 1

        if issue_summary:
            report.append(f"\n问题汇总:")
            for issue, count in sorted(issue_summary.items(), key=lambda x: -x[1]):
                report.append(f"  - {issue}: {count} 次")

        # 错误和警告详情
        if error > 0 or warning > 0:
            report.append(f"\n问题文件详情:")

            error_files = [r for r in results if r['status'] == 'error']
            if error_files:
                report.append(f"\n  ❌ 错误文件 ({len(error_files)} 个):")
                for r in error_files[:20]:  # 最多显示20个
                    report.append(f"    {r['symbol']}: {r['issues']}")
                if len(error_files) > 20:
                    report.append(f"    ... 还有 {len(error_files) - 20} 个")

            warning_files = [r for r in results if r['status'] == 'warning']
            if warning_files:
                report.append(f"\n  ⚠️ 警告文件 ({len(warning_files)} 个):")
                for r in warning_files[:20]:
                    report.append(f"    {r['symbol']}: {r['issues']}")
                if len(warning_files) > 20:
                    report.append(f"    ... 还有 {len(warning_files) - 20} 个")

        # 数据统计
        avg_rows = sum(r['stats'].get('rows', 0) for r in results) / total if total > 0 else 0
        report.append(f"\n数据统计:")
        report.append(f"  平均行数: {avg_rows:.0f} 行/文件")
        report.append(f"  总文件数: {total}")

        report.append("\n" + "=" * 70)

        return "\n".join(report)

    def export_report(self, results: List[Dict], output_file: str = "data_quality_report.json"):
        """导出报告到 JSON"""
        report_data = {
            'check_time': datetime.now().isoformat(),
            'summary': {
                'total': len(results),
                'ok': sum(1 for r in results if r['status'] == 'ok'),
                'warning': sum(1 for r in results if r['status'] == 'warning'),
                'error': sum(1 for r in results if r['status'] == 'error')
            },
            'results': results
        }

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"报告已导出: {output_path}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="检查股票数据质量")
    parser.add_argument("--data-dir", default="data/stocks",
                        help="数据目录路径")
    parser.add_argument("--export", action="store_true",
                        help="导出 JSON 报告")
    parser.add_argument("--output", default="data_quality_report.json",
                        help="导出文件路径")
    parser.add_argument("--detail", action="store_true",
                        help="显示详细的问题文件列表")

    args = parser.parse_args()

    checker = DataQualityChecker(data_dir=args.data_dir)
    results = checker.check_all()

    # 生成文本报告
    report = checker.generate_report(results)
    print(report)

    # 导出报告
    if args.export:
        checker.export_report(results, args.output)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())