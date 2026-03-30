# -*- coding: utf-8 -*-
"""
下载全部A股数据 - 基于 finshare

使用 finshare.get_stock_list() 获取完整股票列表，然后批量下载
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

try:
    import finshare as fs
    import pandas as pd
except ImportError as e:
    print("错误: 需要安装 finshare 和 pandas")
    print("安装命令: pip install finshare pandas")
    sys.exit(1)


class FullStockDownloader:
    """全A股下载器"""

    def __init__(self, output_dir: str = "data/stocks"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 进度文件
        self.progress_file = self.output_dir.parent / "download_progress.json"
        self.progress = self._load_progress()

        # 统计
        self.success_count = 0
        self.fail_count = 0
        self.skip_count = 0

    def _load_progress(self) -> dict:
        """加载下载进度"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "last_update": None,
            "downloaded_stocks": [],
            "financial_data": {},      # 财务数据进度 {symbol: [types]}
            "money_flow": [],           # 资金流向进度
            "margin": [],                # 融资融券进度
            "market_data": False,       # 市场数据
            "industry_data": False,     # 行业数据
            "funds": False,             # 基金数据
            "etfs": False,              # ETF数据
            "lhb": False,               # 龙虎榜
            "valuation": False,         # 估值数据
            "spot": False,              # 实时行情
            "futures": False,           # 期货数据
            "funds": {},                # 基金数据 {list: bool, detail_xxx: bool}
            "etfs": {},                 # ETF数据 {etf_list: bool, lof_list: bool}
            "industry": {},             # 行业数据 {eastmoney_xxx: bool, sw_xxx: bool}
            "failed_stocks": []
        }

    def _save_progress(self):
        """保存下载进度"""
        self.progress["last_update"] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, indent=2, ensure_ascii=False)

    def _is_downloaded(self, category: str, key: str = None) -> bool:
        """
        检查数据是否已下载且是最新的

        对于K线数据：
        - 如果文件不存在，返回False
        - 如果最新日期 < 今天-1天，返回False（需要更新）
        - 否则返回True
        """
        # K线数据：检查文件日期
        if category == "kline" and key:
            # 解析股票代码
            symbol = key

            # 构建文件路径
            filename = symbol.replace('.', '_') + '.csv'
            file_path = self.output_dir / filename

            if not file_path.exists():
                return False

            try:
                # 读取文件，检查最新日期
                df = pd.read_csv(file_path)
                if df.empty:
                    return False

                # 获取日期列（可能是 date 或 trade_date）
                date_col = 'date' if 'date' in df.columns else ('trade_date' if 'trade_date' in df.columns else None)
                if not date_col:
                    return False

                latest_date = pd.to_datetime(df[date_col].iloc[-1])
                today = datetime.now()

                # 如果最新数据超过1天，需要更新
                days_old = (today - latest_date).days
                return days_old <= 1

            except Exception:
                return False

        # 其他类型保持原逻辑
        elif category == "financial":
            fin_data = self.progress.get("financial_data", {})
            return key in fin_data
        elif category == "moneyflow":
            return key in self.progress.get("money_flow", [])
        elif category == "margin":
            return key in self.progress.get("margin", [])
        elif category == "industry":
            ind_data = self.progress.get("industry", {})
            return key in ind_data
        elif category in ["funds", "etfs"]:
            if key is None:
                cat_data = self.progress.get(category, {})
                return bool(cat_data)
            return key in self.progress.get(category, {})
        elif category in ["market_data", "industry_data", "lhb", "valuation", "spot", "futures"]:
            return self.progress.get(category, False)
        return False

    def _mark_downloaded(self, category: str, key: str = None):
        """标记数据为已下载"""
        if category == "kline":
            if "downloaded_stocks" not in self.progress:
                self.progress["downloaded_stocks"] = []
            if key not in self.progress["downloaded_stocks"]:
                self.progress["downloaded_stocks"].append(key)
        elif category == "financial":
            if "financial_data" not in self.progress:
                self.progress["financial_data"] = {}
            if key not in self.progress["financial_data"]:
                self.progress["financial_data"][key] = []
        elif category == "moneyflow":
            if "money_flow" not in self.progress:
                self.progress["money_flow"] = []
            if key not in self.progress["money_flow"]:
                self.progress["money_flow"].append(key)
        elif category == "margin":
            if "margin" not in self.progress:
                self.progress["margin"] = []
            if key not in self.progress["margin"]:
                self.progress["margin"].append(key)
        elif category == "industry":
            if "industry" not in self.progress:
                self.progress["industry"] = {}
            if key not in self.progress["industry"]:
                self.progress["industry"][key] = True
        elif category in ["funds", "etfs"]:
            if category not in self.progress:
                self.progress[category] = {}
            if key not in self.progress[category]:
                self.progress[category][key] = True
        elif category in ["market_data", "industry_data", "lhb", "valuation", "spot", "futures"]:
            self.progress[category] = True

        self._save_progress()

    def get_all_stocks(self) -> List[str]:
        """
        获取全部A股列表

        Returns:
            股票代码列表 [000001.SZ, 600000.SH, ...]
        """
        print("[INFO] 正在获取A股列表...")

        try:
            # 使用 finshare 获取股票列表
            stocks = fs.get_stock_list()

            if stocks is None or len(stocks) == 0:
                print("[WARN] 未能获取股票列表，使用备用方案")
                return self._get_backup_stock_list()

            # 提取股票代码
            symbols = []
            for stock in stocks:
                code = str(stock.get('code', ''))
                market = stock.get('market', 0)  # 0=深圳, 1=上海

                # 跳过非6位数字代码
                if len(code) != 6 or not code.isdigit():
                    continue

                # 格式化代码
                if market == 0:  # 深圳
                    symbol = f"{code}.SZ"
                elif market == 1:  # 上海
                    symbol = f"{code}.SH"
                else:
                    continue

                symbols.append(symbol)

            print(f"[INFO] 共获取 {len(symbols)} 只股票")
            return symbols

        except Exception as e:
            print(f"[WARN] 获取股票列表失败: {e}")
            print("[INFO] 使用备用方案...")
            return self._get_backup_stock_list()

    def _get_backup_stock_list(self) -> List[str]:
        """备用方案：生成常见股票代码"""
        symbols = []

        # 深圳主板 000xxx
        for i in range(1, 1000):
            symbols.append(f"{i:06d}.SZ")

        # 深圳中小板 002xxx
        for i in range(1, 1000):
            symbols.append(f"00{i:04d}.SZ")

        # 深圳创业板 300xxx
        for i in range(1, 1000):
            symbols.append(f"300{i:03d}.SZ")

        # 上海主板 60xxxx
        for i in range(0, 1000):
            symbols.append(f"60{i:04d}.SH")

        # 上海科创板 688xxx
        for i in range(1, 500):
            symbols.append(f"688{i:03d}.SH")

        print(f"[INFO] 备用方案生成 {len(symbols)} 只股票代码")
        return symbols

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化列名

        finshare 返回的列名: trade_date, open_price, high_price, low_price, close_price
        标准列名: date, open, high, low, close
        """
        column_map = {
            'trade_date': 'date',
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'close_price': 'close',
        }

        # 重命名列
        df = df.rename(columns=column_map)

        return df

    def _validate_data(
        self,
        df: pd.DataFrame,
        symbol: str,
        expected_days: int = 365
    ) -> tuple[bool, str]:
        """
        验证下载的数据是否完整

        Returns:
            (is_valid, reason)
        """
        # 检查是否为空
        if df is None or df.empty:
            return False, "数据为空"

        # 标准化列名（仅用于验证，不修改原数据）
        df_valid = self._normalize_columns(df.copy())

        # 检查必需列
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [c for c in required_cols if c not in df_valid.columns]
        if missing_cols:
            return False, f"缺少列: {missing_cols}"

        # 检查数据行数（至少有 100 行数据）
        # 对于新上市股票，可能数据较少，只要数据完整就接受
        min_rows = 100
        if len(df_valid) < min_rows:
            return False, f"数据过少: {len(df_valid)} 行 (期望至少 {min_rows} 行)"

        # 检查是否有缺失值
        null_counts = df_valid[required_cols].isnull().sum()
        if null_counts.sum() > 0:
            null_info = null_counts[null_counts > 0].to_dict()
            return False, f"存在缺失值: {null_info}"

        # 检查数值是否合理
        for col in ['open', 'high', 'low', 'close']:
            if (df_valid[col] <= 0).any():
                return False, f"{col} 存在非正值"

        # 检查价格逻辑（high >= close, low <= close）
        invalid_high = df_valid['high'] < df_valid[['open', 'close']].max(axis=1)
        invalid_low = df_valid['low'] > df_valid[['open', 'close']].min(axis=1)
        if invalid_high.any() or invalid_low.any():
            return False, "价格数据异常"

        # 检查成交量
        if (df_valid['volume'] < 0).any():
            return False, "成交量存在负值"

        return True, "数据完整"

    def download_stock_klines(
        self,
        symbol: str,
        days: int = 365,
        validate: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        下载单只股票K线数据

        Args:
            symbol: 股票代码
            days: 天数
            validate: 是否验证数据完整性
        """
        try:
            # 设置日期范围
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # 使用 finshare 下载
            df = fs.get_historical_data(symbol, start=start_date, end=end_date)

            if df is None or df.empty:
                return None

            # 标准化列名
            df = self._normalize_columns(df)

            # 验证数据
            if validate:
                is_valid, reason = self._validate_data(df, symbol, days)
                if not is_valid:
                    print(f"[WARN] {symbol} 数据验证失败: {reason}")
                    return None

            return df

        except Exception as e:
            # 打印错误信息用于调试
            print(f"[DEBUG] {symbol} K线下载失败: {e}")
            return None

    def download_financial_data(
        self,
        symbol: str,
        data_types: List[str] = None
    ) -> dict:
        """
        下载财务数据（带断点续传）

        Args:
            symbol: 股票代码
            data_types: 数据类型列表 ['income', 'balance', 'cashflow', 'indicator', 'dividend']
        """
        if data_types is None:
            data_types = ['income', 'balance', 'cashflow', 'indicator', 'dividend']

        results = {}
        skipped_count = 0

        for data_type in data_types:
            # 检查是否已下载
            if self._is_downloaded("financial", f"{symbol}_{data_type}"):
                skipped_count += 1
                continue

            try:
                if data_type == 'income':
                    df = fs.get_income(symbol)
                    file_prefix = 'income'
                elif data_type == 'balance':
                    df = fs.get_balance(symbol)
                    file_prefix = 'balance'
                elif data_type == 'cashflow':
                    df = fs.get_cashflow(symbol)
                    file_prefix = 'cashflow'
                elif data_type == 'indicator':
                    df = fs.get_financial_indicator(symbol)
                    file_prefix = 'indicator'
                elif data_type == 'dividend':
                    df = fs.get_dividend(symbol)
                    file_prefix = 'dividend'
                else:
                    continue

                if df is not None and not df.empty:
                    results[data_type] = df
                    output_file = self.output_dir / f"{symbol.replace('.', '_')}_{file_prefix}.csv"
                    df.to_csv(output_file, index=False, encoding='utf-8-sig')

                    # 标记已下载
                    self._mark_downloaded("financial", f"{symbol}_{data_type}")

            except Exception as e:
                pass

        if skipped_count > 0:
            print(f"        └─ 财务: 跳过 {skipped_count} 类")

        return results

    def download_money_flow(
        self,
        symbol: str
    ) -> Optional[pd.DataFrame]:
        """下载资金流向数据（带断点续传）"""
        # 检查是否已下载
        if self._is_downloaded("moneyflow", symbol):
            return None

        try:
            df = fs.get_money_flow(symbol)
            if df is not None and not df.empty:
                output_file = self.output_dir / f"{symbol.replace('.', '_')}_moneyflow.csv"
                df.to_csv(output_file, index=False, encoding='utf-8-sig')

                # 标记已下载
                self._mark_downloaded("moneyflow", symbol)

                return df
        except Exception:
            pass
        return None

    def download_margin_data(
        self,
        symbol: str
    ) -> Optional[pd.DataFrame]:
        """下载融资融券数据（带断点续传）"""
        # 检查是否已下载
        if self._is_downloaded("margin", symbol):
            return None

        try:
            df = fs.get_margin(symbol)
            if df is not None and not df.empty:
                output_file = self.output_dir / f"{symbol.replace('.', '_')}_margin.csv"
                df.to_csv(output_file, index=False, encoding='utf-8-sig')

                # 标记已下载
                self._mark_downloaded("margin", symbol)

                return df
        except Exception:
            pass
        return None

    def download_market_data(self):
        """下载市场指数数据（带断点续传）"""
        market_dir = self.output_dir.parent / "market"
        market_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已下载
        if self._is_downloaded("market_data"):
            print("[INFO] 市场指数数据已存在，跳过")
            return

        print("\n[INFO] 下载市场指数数据...")

        # 获取指数列表
        indices = ['000001.SH', '399001.SZ', '399006.SZ']  # 上证指数、深证成指、创业板指

        for idx in indices:
            try:
                df = fs.get_historical_data(idx, start='2011-01-01', end=datetime.now().strftime('%Y-%m-%d'))
                if df is not None and not df.empty:
                    output_file = market_dir / f"index_{idx.replace('.', '_')}.csv"
                    df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"[OK] 指数 {idx}: {len(df)} 条")
            except Exception as e:
                print(f"[FAIL] 指数 {idx}")

        # 下载指数市盈率、市净率
        try:
            pe_df = fs.get_index_pe()
            if pe_df is not None and not pe_df.empty:
                output_file = market_dir / "index_pe.csv"
                pe_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"[OK] 指数市盈率: {len(pe_df)} 条")
        except Exception:
            pass

        try:
            pb_df = fs.get_index_pb()
            if pb_df is not None and not pb_df.empty:
                output_file = market_dir / "index_pb.csv"
                pb_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"[OK] 指数市净率: {len(pb_df)} 条")
        except Exception:
            pass

        # 标记已下载
        self._mark_downloaded("market_data")

        # 下载行业分类（多种来源）
        print("\n[INFO] 下载行业数据...")

        # 检查是否已下载行业数据
        if self._is_downloaded("industry_data"):
            print("[SKIP] 行业数据已下载，跳过")
        else:
            # 东方财富行业分类
            try:
                industries = fs.get_industry_list()
                if industries is not None and not industries.empty:
                    output_file = market_dir / "industries.csv"
                    industries.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"[OK] 行业分类: {len(industries)} 个")

                    # 下载每个行业的成分股
                    industry_dir = market_dir / "industries"
                    industry_dir.mkdir(exist_ok=True)

                    if 'code' in industries.columns:
                        for _, row in industries.iterrows():
                            ind_code = row.get('code')
                            ind_name = row.get('name', '')

                            if not ind_code:
                                continue

                            # 检查是否已下载
                            if self._is_downloaded("industry", f"eastmoney_{ind_code}"):
                                continue

                            try:
                                constituents = fs.get_industry_constituents(ind_code)
                                if constituents is not None and not constituents.empty:
                                    output_file = industry_dir / f"industry_{ind_code}_constituents.csv"
                                    constituents.to_csv(output_file, index=False, encoding='utf-8-sig')
                                    print(f"   └─ {ind_name} ({ind_code}): {len(constituents)} 只")
                                    self._mark_downloaded("industry", f"eastmoney_{ind_code}")
                            except Exception:
                                pass
            except Exception:
                pass

            # 申万行业分析
            try:
                sw_industries = fs.get_sw_industry_list()
                if sw_industries is not None and not sw_industries.empty:
                    output_file = market_dir / "sw_industries.csv"
                    sw_industries.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"[OK] 申万行业分类: {len(sw_industries)} 个")

                    # 下载申万行业成分股
                    sw_dir = market_dir / "sw_industries"
                    sw_dir.mkdir(exist_ok=True)

                    if 'code' in sw_industries.columns:
                        for _, row in sw_industries.iterrows():
                            sw_code = row.get('code')
                            sw_name = row.get('name', '')

                            if not sw_code:
                                continue

                            # 检查是否已下载
                            if self._is_downloaded("industry", f"sw_{sw_code}"):
                                continue

                            try:
                                constituents = fs.get_sw_industry_constituents(sw_code)
                                if constituents is not None and not constituents.empty:
                                    output_file = sw_dir / f"sw_{sw_code}_constituents.csv"
                                    constituents.to_csv(output_file, index=False, encoding='utf-8-sig')
                                    self._mark_downloaded("industry", f"sw_{sw_code}")
                            except Exception:
                                pass

                    # 下载申万行业分析数据
                    if not self._is_downloaded("industry", "sw_analysis"):
                        try:
                            sw_analysis = fs.get_sw_industry_analysis()
                            if sw_analysis is not None and not sw_analysis.empty:
                                output_file = market_dir / "sw_industry_analysis.csv"
                                sw_analysis.to_csv(output_file, index=False, encoding='utf-8-sig')
                                print(f"[OK] 申万行业分析: {len(sw_analysis)} 条")
                                self._mark_downloaded("industry", "sw_analysis")
                        except Exception:
                            pass
            except Exception:
                pass

            # 行业资金流向
            if not self._is_downloaded("industry", "moneyflow"):
                try:
                    money_flow_industry = fs.get_money_flow_industry()
                    if money_flow_industry is not None and not money_flow_industry.empty:
                        output_file = market_dir / "industry_moneyflow.csv"
                        money_flow_industry.to_csv(output_file, index=False, encoding='utf-8-sig')
                        print(f"[OK] 行业资金流向: {len(money_flow_industry)} 条")
                        self._mark_downloaded("industry", "moneyflow")
                except Exception:
                    pass

            # 标记行业数据已下载
            self._mark_downloaded("industry_data")

    def download_lhb_data(self, days: int = 30):
        """下载龙虎榜数据"""
        lhb_dir = self.output_dir.parent / "lhb"
        lhb_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已下载
        if self._is_downloaded("lhb"):
            print("\n[SKIP] 龙虎榜数据已下载，跳过")
            return

        print("\n[INFO] 下载龙虎榜数据...")

        # 计算日期范围
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        try:
            lhb = fs.get_lhb(start_date=start_date, end_date=end_date)
            if lhb is not None and not lhb.empty:
                output_file = lhb_dir / f"lhb_{start_date}_{end_date}.csv"
                lhb.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"[OK] 龙虎榜: {len(lhb)} 条")
                self._mark_downloaded("lhb")
        except Exception:
            pass

    def download_market_valuation(self):
        """下载市场估值数据"""
        valuation_dir = self.output_dir.parent / "valuation"
        valuation_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已下载
        if self._is_downloaded("valuation"):
            print("\n[SKIP] 市场估值数据已下载，跳过")
            return

        print("\n[INFO] 下载市场估值数据...")

        # 市场PB
        try:
            market_pb = fs.get_market_pb()
            if market_pb is not None and not market_pb.empty:
                output_file = valuation_dir / "market_pb.csv"
                market_pb.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"[OK] 市场PB: {len(market_pb)} 条")
        except Exception:
            pass

        # 全球指数（主要美股、港股指数）
        global_indices = [
            'SPX',  # 标普500
            'DJX',  # 道琼斯
            'IXIC',  # 纳斯达克
            'NDX',  # 纳斯达克100
            'HSI',  # 恒生指数
            'HSCEI',  # 恒生中国企业指数
        ]

        for idx_code in global_indices:
            # 检查是否已下载该指数
            if self._is_downloaded("valuation", f"global_{idx_code}"):
                continue

            try:
                idx_data = fs.get_global_index_daily(idx_code)
                if idx_data is not None and not idx_data.empty:
                    output_file = valuation_dir / f"global_{idx_code.lower()}.csv"
                    idx_data.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"[OK] 全球指数 {idx_code}: {len(idx_data)} 条")
                    self._mark_downloaded("valuation", f"global_{idx_code}")
            except Exception:
                pass

        # 标记估值数据已下载
        self._mark_downloaded("valuation")

    def download_spot_data(self):
        """下载实时行情快照"""
        spot_dir = self.output_dir.parent / "spot"
        spot_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已下载
        if self._is_downloaded("spot"):
            print("\n[SKIP] 实时行情已下载，跳过")
            return

        print("\n[INFO] 下载实时行情...")

        try:
            spot = fs.get_stock_spot()
            if spot is not None and not spot.empty:
                output_file = spot_dir / "stock_spot.csv"
                spot.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"[OK] 实时行情: {len(spot)} 只股票")
                self._mark_downloaded("spot")
        except Exception:
            pass

    def download_futures(self):
        """下载期货数据"""
        futures_dir = self.output_dir.parent / "futures"
        futures_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已下载
        if self._is_downloaded("futures"):
            print("\n[SKIP] 期货数据已下载，跳过")
            return

        print("\n[INFO] 下载期货数据...")

        # 期货列表
        try:
            futures = fs.get_future_list()
            if futures is not None and not futures.empty:
                output_file = futures_dir / "future_list.csv"
                futures.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"[OK] 期货列表: {len(futures)} 个合约")

                # 下载主力期货的历史数据
                main_futures = ['IF0', 'IC0', 'IH0', 'IM0']  # 股指期货
                for fcode in main_futures:
                    # 检查是否已下载该期货
                    if self._is_downloaded("futures", fcode):
                        continue

                    try:
                        fdata = fs.get_future_kline(fcode, start_date='2019-01-01')
                        if fdata is not None and len(fdata) > 0:
                            # 转换为DataFrame
                            import pandas as pd
                            df = pd.DataFrame([vars(d) for d in fdata])
                            output_file = futures_dir / f"future_{fcode}.csv"
                            df.to_csv(output_file, index=False, encoding='utf-8-sig')
                            print(f"   └─ {fcode}: {len(fdata)} 条")
                            self._mark_downloaded("futures", fcode)
                    except Exception:
                        pass
        except Exception:
            pass

        # 标记期货数据已下载
        self._mark_downloaded("futures")

    def download_fund_data(self, limit: int = None):
        """下载基金数据"""
        fund_dir = self.output_dir.parent / "funds"
        fund_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已下载基金列表
        if self._is_downloaded("funds", "list"):
            print("\n[SKIP] 基金列表已下载，跳过")
            return

        print("\n[INFO] 下载基金数据...")

        try:
            funds = fs.get_fund_list()
            if funds is not None and not funds.empty:
                output_file = fund_dir / "fund_list.csv"
                funds.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"[OK] 基金列表: {len(funds)} 只")
                self._mark_downloaded("funds", "list")

                # 下载前几只基金的详细信息
                fund_codes = funds.get('code', []).tolist()[:limit] if limit else []
                for i, code in enumerate(fund_codes[:50], 1):  # 最多下载50只
                    # 检查是否已下载该基金详情
                    if self._is_downloaded("funds", f"detail_{code}"):
                        print(f"[{i}] 基金 {code} - 已跳过")
                        continue

                    try:
                        info = fs.get_fund_info(code)
                        if info is not None and not info.empty:
                            output_file = fund_dir / f"fund_{code}_info.csv"
                            info.to_csv(output_file, index=False, encoding='utf-8-sig')
                            self._mark_downloaded("funds", f"detail_{code}")
                        print(f"[{i}] 基金 {code}")
                    except Exception:
                        pass
        except Exception as e:
            print(f"[FAIL] 获取基金列表: {e}")

    def download_etf_data(self):
        """下载ETF数据"""
        etf_dir = self.output_dir.parent / "etfs"
        etf_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否已下载ETF数据
        if self._is_downloaded("etfs", "etf_list") and self._is_downloaded("etfs", "lof_list"):
            print("\n[SKIP] ETF数据已下载，跳过")
            return

        print("\n[INFO] 下载ETF数据...")

        # 下载ETF列表
        if not self._is_downloaded("etfs", "etf_list"):
            try:
                etfs = fs.get_etf_list()
                if etfs is not None and not etfs.empty:
                    output_file = etf_dir / "etf_list.csv"
                    etfs.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"[OK] ETF列表: {len(etfs)} 只")
                    self._mark_downloaded("etfs", "etf_list")
            except Exception as e:
                print(f"[FAIL] 获取ETF列表: {e}")

        # 下载LOF列表
        if not self._is_downloaded("etfs", "lof_list"):
            try:
                lofs = fs.get_lof_list()
                if lofs is not None and not lofs.empty:
                    output_file = etf_dir / "lof_list.csv"
                    lofs.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"[OK] LOF列表: {len(lofs)} 只")
                    self._mark_downloaded("etfs", "lof_list")
            except Exception:
                pass

    def download_all(
        self,
        symbols: List[str],
        days: int = 365,
        batch_size: int = 10,
        include_financial: bool = False,
        include_moneyflow: bool = False,
        include_margin: bool = False,
        include_market: bool = True,
        include_funds: bool = False,
        include_etfs: bool = False,
        include_lhb: bool = False,
        include_valuation: bool = False,
        include_spot: bool = False,
        include_futures: bool = False
    ):
        """
        批量下载

        Args:
            symbols: 股票代码列表
            days: 天数
            batch_size: 批次大小
            include_financial: 是否下载财务数据
            include_moneyflow: 是否下载资金流向
            include_margin: 是否下载融资融券
            include_market: 是否下载市场数据
            include_funds: 是否下载基金数据
            include_etfs: 是否下载ETF数据
            include_lhb: 是否下载龙虎榜
            include_valuation: 是否下载市场估值
            include_spot: 是否下载实时行情
            include_futures: 是否下载期货数据
        """
        # 先下载市场数据（不依赖股票列表）
        if include_market:
            self.download_market_data()

        # 下载其他市场数据
        if include_lhb:
            self.download_lhb_data(days=30)

        if include_valuation:
            self.download_market_valuation()

        if include_spot:
            self.download_spot_data()

        if include_futures:
            self.download_futures()

        # 下载基金和ETF数据
        if include_funds:
            self.download_fund_data(limit=50)

        if include_etfs:
            self.download_etf_data()

        # 下载股票K线数据
        total = len(symbols)
        print(f"\n[INFO] 开始下载 {total} 只股票数据...")
        print(f"[INFO] 数据范围: 最近 {days} 天")

        if include_financial:
            print(f"[INFO] 同时下载财务数据")
        if include_moneyflow:
            print(f"[INFO] 同时下载资金流向")
        if include_margin:
            print(f"[INFO] 同时下载融资融券")

        downloaded_stocks = self.progress.get("downloaded_stocks", [])

        for i, symbol in enumerate(symbols, 1):
            # 检查是否需要更新（数据是否超过1天）
            kline_downloaded = False
            if not self._is_downloaded("kline", symbol):
                # 判断是首次下载还是增量更新
                filename = symbol.replace('.', '_') + '.csv'
                output_file = self.output_dir / filename

                if output_file.exists():
                    # 文件存在但数据过旧：增量更新（下载最近7天）
                    update_days = 7
                else:
                    # 文件不存在：首次下载（使用完整天数）
                    update_days = days

                df = self.download_stock_klines(symbol, days=update_days)
                if df is not None:
                    kline_downloaded = True
                    # 检查是否有旧数据需要合并
                    old_df = None
                    if output_file.exists():
                        try:
                            old_df = pd.read_csv(output_file)
                            if not old_df.empty:
                                # 合并旧数据和新数据，去重
                                df = pd.concat([old_df, df], ignore_index=True)
                                # 按日期去重，保留最新的
                                date_col = 'date' if 'date' in df.columns else 'trade_date'
                                df = df.drop_duplicates(subset=[date_col], keep='last')
                                # 按日期排序
                                df = df.sort_values(by=date_col)
                        except:
                            pass

                    df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    self.success_count += 1
                    if symbol not in downloaded_stocks:
                        downloaded_stocks.append(symbol)
                    print(f"[{i}/{total}] [更新] {symbol}: {len(df)} 条记录")
                else:
                    self.fail_count += 1
                    if self.fail_count <= 10:
                        print(f"[{i}/{total}] [FAIL] {symbol}")
            else:
                # 数据是最新的，跳过
                self.skip_count += 1
                kline_downloaded = False
                if i % 50 == 0:
                    print(f"[{i}/{total}] 跳过 {symbol} (数据已是最新)")

            # 下载附加数据（只在成功下载K线数据时下载）
            if kline_downloaded:
                if include_financial:
                    fin_data = self.download_financial_data(symbol)
                    if fin_data:
                        print(f"        └─ 财务: {len(fin_data)} 类")

                if include_moneyflow:
                    self.download_money_flow(symbol)

                if include_margin:
                    self.download_margin_data(symbol)

            # 更新进度
            if i % batch_size == 0:
                self.progress["downloaded_stocks"] = downloaded_stocks
                self._save_progress()

            # 延迟避免请求过快
            time.sleep(0.15)

        # 保存最终进度
        self.progress["downloaded_stocks"] = downloaded_stocks
        self._save_progress()

        print(f"\n[SUCCESS] 下载完成!")
        print(f"  成功: {self.success_count}")
        print(f"  跳过: {self.skip_count}")
        print(f"  失败: {self.fail_count}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="下载全部A股数据 - 基于 finshare")
    parser.add_argument("--limit", type=int, default=None,
                        help="限制下载数量（None=全部）")
    parser.add_argument("--symbols", type=str, nargs="+",
                        help="指定股票代码列表")
    parser.add_argument("--days", type=int, default=5475,
                        help="下载天数（默认5475天=15年）")
    parser.add_argument("--output", type=str, default="data/stocks",
                        help="输出目录")
    parser.add_argument("--financial", action="store_true",
                        help="下载财务数据（利润表、资产负债表、现金流量表、指标、分红）")
    parser.add_argument("--moneyflow", action="store_true",
                        help="下载资金流向数据")
    parser.add_argument("--margin", action="store_true",
                        help="下载融资融券数据")
    parser.add_argument("--no-market", action="store_true",
                        help="不下载市场数据（指数、PE/PB、行业）")
    parser.add_argument("--funds", action="store_true",
                        help="下载基金数据")
    parser.add_argument("--etfs", action="store_true",
                        help="下载ETF数据")
    parser.add_argument("--all-data", action="store_true",
                        help="下载所有类型数据")

    args = parser.parse_args()

    downloader = FullStockDownloader(output_dir=args.output)

    # 确定下载列表
    if args.symbols:
        symbols = args.symbols
    else:
        # 获取全部股票
        symbols = downloader.get_all_stocks()

        if args.limit:
            symbols = symbols[:args.limit]

    if not symbols:
        print("[ERROR] 没有需要下载的股票")
        return 1

    print(f"\n[INFO] 准备下载 {len(symbols)} 只股票\n")

    # 解析下载选项
    include_financial = args.financial or args.all_data
    include_moneyflow = args.moneyflow or args.all_data
    include_margin = args.margin or args.all_data
    include_market = not args.no_market
    include_funds = args.funds or args.all_data
    include_etfs = args.etfs or args.all_data
    include_lhb = args.all_data
    include_valuation = args.all_data
    include_spot = args.all_data
    include_futures = args.all_data

    # 开始下载
    downloader.download_all(
        symbols,
        days=args.days,
        include_financial=include_financial,
        include_moneyflow=include_moneyflow,
        include_margin=include_margin,
        include_market=include_market,
        include_funds=include_funds,
        include_etfs=include_etfs,
        include_lhb=include_lhb,
        include_valuation=include_valuation,
        include_spot=include_spot,
        include_futures=include_futures
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())