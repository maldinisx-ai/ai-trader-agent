# -*- coding: utf-8 -*-
"""
本地数据加载器

从本地 CSV 文件加载完整的市场数据，包括：
- K线数据（OHLCV）
- 指数数据
- 行业资金流向
- 股票行业映射
"""

import os
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class LocalDataLoader:
    """
    本地数据加载器

    从本地 data/ 目录加载所有可用的市场数据。
    """

    def __init__(self, data_dir: str = "data"):
        """
        初始化数据加载器

        Args:
            data_dir: 数据目录路径
        """
        self.data_dir = Path(data_dir)
        self._cache: Dict[str, Any] = {}

    def load_all_data(self, symbol: str) -> Dict[str, Any]:
        """
        加载指定股票的所有相关数据

        Args:
            symbol: 股票代码

        Returns:
            dict: 包含所有市场数据的字典
        """
        result = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
        }

        # 1. 加载K线数据
        klines = self._load_klines(symbol)
        if klines is not None:
            result["klines"] = self._format_klines_for_ai(klines)

        # 2. 加载指数数据
        indices = self._load_indices()
        if indices:
            result["indices"] = self._format_indices_for_ai(indices)

        # 3. 加载行业资金流向
        industry_flow = self._load_industry_flow()
        if industry_flow is not None:
            result["industry_flow"] = self._format_industry_flow_for_ai(industry_flow)

        # 4. 获取股票所属行业
        stock_industry = self._get_stock_industry(symbol)
        if stock_industry:
            result["industry"] = stock_industry

        return result

    def _load_klines(self, symbol: str) -> Optional[pd.DataFrame]:
        """加载K线数据"""
        cache_key = f"klines_{symbol}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 尝试多种路径格式
        csv_path = None

        # 1. 新格式：data/klines/000001_SZ.csv 或 data/klines/600519_SH.csv
        klines_dir = self.data_dir / "klines"
        if klines_dir.exists():
            # 先尝试查找该股票的任何市场后缀文件
            for csv_path_candidate in klines_dir.glob(f"{symbol}_*.csv"):
                csv_path = csv_path_candidate
                break

        # 2. 旧格式：data/klines_000001.csv
        if csv_path is None:
            old_path = self.data_dir / f"klines_{symbol}.csv"
            if old_path.exists():
                csv_path = old_path

        if csv_path is None or not csv_path.exists():
            logger.warning(f"K线数据不存在: {symbol}")
            return None

        try:
            df = pd.read_csv(csv_path)

            # 兼容不同的列名格式
            # 新格式：trade_date, open_price, close_price, high_price, low_price
            # 旧格式：date, open, close, high, low
            if 'trade_date' in df.columns:
                df = df.rename(columns={
                    'trade_date': 'date',
                    'open_price': 'open',
                    'close_price': 'close',
                    'high_price': 'high',
                    'low_price': 'low',
                })

            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

            # 计算技术指标
            df = self._add_technical_indicators(df)

            self._cache[cache_key] = df
            return df
        except Exception as e:
            logger.error(f"加载K线数据失败: {symbol}, {e}")
            return None

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加技术指标"""
        # 移动平均线
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()

        # 价格变化
        df['change'] = df['close'].pct_change() * 100
        df['change_abs'] = df['close'].diff()

        # 振幅
        df['amplitude'] = ((df['high'] - df['low']) / df['close'].shift(1) * 100)

        # 成交量变化
        df['volume_ma5'] = df['volume'].rolling(window=5).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma5']

        return df

    def _format_klines_for_ai(self, df: pd.DataFrame) -> Dict[str, Any]:
        """格式化K线数据供AI分析"""
        if df.empty:
            return {}

        # 最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # 最近30天数据
        recent = df.tail(30)

        return {
            "latest": {
                "date": latest['date'].strftime('%Y-%m-%d'),
                "open": float(latest['open']),
                "close": float(latest['close']),
                "high": float(latest['high']),
                "low": float(latest['low']),
                "volume": int(latest['volume']),
                "amount": float(latest['amount']),
                "change": float(latest['change']) if not pd.isna(latest['change']) else 0.0,
                "amplitude": float(latest['amplitude']) if not pd.isna(latest['amplitude']) else 0.0,
            },
            "technical": {
                "ma5": float(latest['ma5']) if not pd.isna(latest['ma5']) else None,
                "ma10": float(latest['ma10']) if not pd.isna(latest['ma10']) else None,
                "ma20": float(latest['ma20']) if not pd.isna(latest['ma20']) else None,
                "ma60": float(latest['ma60']) if not pd.isna(latest['ma60']) else None,
                "volume_ratio": float(latest['volume_ratio']) if not pd.isna(latest['volume_ratio']) else 1.0,
            },
            "trend": self._analyze_trend(recent),
            "support_resistance": self._calculate_support_resistance(recent),
            "statistics": {
                "avg_volume_30": float(recent['volume'].mean()),
                "max_high_30": float(recent['high'].max()),
                "min_low_30": float(recent['low'].min()),
                "volatility": float(recent['change'].std()),
            }
        }

    def _analyze_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析趋势"""
        if len(df) < 5:
            return {"direction": "unknown", "strength": 0}

        latest = df.iloc[-1]
        prev_5 = df.iloc[-5]['close'] if len(df) >= 5 else df.iloc[0]['close']

        # 5日涨跌幅
        change_5d = (latest['close'] - prev_5) / prev_5 * 100

        # 均线排列
        ma_trend = "neutral"
        if not pd.isna(latest['ma5']) and not pd.isna(latest['ma10']) and not pd.isna(latest['ma20']):
            if latest['ma5'] > latest['ma10'] > latest['ma20']:
                ma_trend = "bullish"
            elif latest['ma5'] < latest['ma10'] < latest['ma20']:
                ma_trend = "bearish"

        # 趋势判断
        direction = "neutral"
        if change_5d > 2 and ma_trend == "bullish":
            direction = "strong_up"
        elif change_5d > 1:
            direction = "up"
        elif change_5d < -2 and ma_trend == "bearish":
            direction = "strong_down"
        elif change_5d < -1:
            direction = "down"

        return {
            "direction": direction,
            "change_5d": float(change_5d),
            "ma_alignment": ma_trend,
        }

    def _calculate_support_resistance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """计算支撑和阻力位"""
        if len(df) < 10:
            return {"support": None, "resistance": None}

        recent = df.tail(20)

        # 简单支撑阻力：最近20天的低点和高点
        support_levels = recent['low'].nsmallest(3).tolist()
        resistance_levels = recent['high'].nlargest(3).tolist()

        return {
            "support": [float(x) for x in support_levels],
            "resistance": [float(x) for x in resistance_levels],
            "current_price": float(df.iloc[-1]['close']),
        }

    def _load_indices(self) -> Dict[str, pd.DataFrame]:
        """加载所有指数数据"""
        indices = {}
        for csv_path in self.data_dir.glob("index_*.csv"):
            try:
                index_name = csv_path.stem.replace("index_", "")
                df = pd.read_csv(csv_path)
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')

                # 计算涨跌幅
                df['change'] = df['close'].pct_change() * 100

                indices[index_name] = df.tail(5)  # 只保留最近5天
            except Exception as e:
                logger.warning(f"加载指数数据失败 {csv_path}: {e}")

        return indices

    def _format_indices_for_ai(self, indices: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """格式化指数数据供AI分析"""
        result = []
        for name, df in indices.items():
            if df.empty:
                continue

            latest = df.iloc[-1]
            result.append({
                "name": name,
                "date": latest['date'].strftime('%Y-%m-%d'),
                "close": float(latest['close']),
                "change": float(latest['change']) if not pd.isna(latest['change']) else 0.0,
                "volume": int(latest['volume']),
            })

        return result

    def _load_industry_flow(self) -> Optional[pd.DataFrame]:
        """加载行业资金流向数据"""
        cache_key = "industry_flow"
        if cache_key in self._cache:
            return self._cache[cache_key]

        csv_path = self.data_dir / "industry_fund_flow.csv"
        if not csv_path.exists():
            return None

        try:
            df = pd.read_csv(csv_path)
            self._cache[cache_key] = df
            return df
        except Exception as e:
            logger.warning(f"加载行业资金流向失败: {e}")
            return None

    def _format_industry_flow_for_ai(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """格式化行业资金流向供AI分析"""
        result = []

        # 按净额排序，取前10
        df_sorted = df.sort_values('净额', ascending=False).head(10)

        for _, row in df_sorted.iterrows():
            result.append({
                "industry": row['行业'],
                "net_flow": float(row['净额']),
                "inflow": float(row['流入资金']),
                "outflow": float(row['流出资金']),
                "change_pct": float(row['行业-涨跌幅']),
                "leading_stock": row['领涨股'],
                "leading_change": float(row['领涨股-涨跌幅']),
            })

        return result

    def _get_stock_industry(self, symbol: str) -> Optional[Dict[str, str]]:
        """获取股票所属行业"""
        csv_path = self.data_dir / "stock_industry_mapping.csv"
        if not csv_path.exists():
            return None

        try:
            df = pd.read_csv(csv_path)
            row = df[df['股票代码'] == symbol]

            if not row.empty:
                return {
                    "industry": row['行业名称'].iloc[0],
                    "industry_code": row['行业代码'].iloc[0] if '行业代码' in row else None,
                }
        except Exception as e:
            logger.warning(f"获取股票行业失败: {e}")

        return None

    def get_available_symbols(self) -> List[str]:
        """获取所有可用的股票代码"""
        symbols = []

        # 优先从 klines/ 目录读取（新格式：000001_SZ.csv）
        klines_dir = self.data_dir / "klines"
        if klines_dir.exists():
            for csv_path in klines_dir.glob("*.csv"):
                # 文件名格式：000001_SZ.csv 或 600519_SH.csv
                # 提取股票代码（下划线前的部分）
                name = csv_path.stem  # 去掉 .csv
                if "_" in name:
                    symbol = name.split("_")[0]
                else:
                    symbol = name
                symbols.append(symbol)
        else:
            # 兼容旧格式：klines_000001.csv
            for csv_path in self.data_dir.glob("klines_*.csv"):
                symbol = csv_path.stem.replace("klines_", "")
                symbols.append(symbol)

        return sorted(symbols)

    def load_all_stocks(self, full_data: bool = False, limit: int = 50) -> Dict[str, Any]:
        """
        加载所有本地股票的数据

        Args:
            full_data: 是否返回完整数据（True=本地模型用，False=API模型用）
            limit: 最多加载的股票数量（避免token过多）

        Returns:
            dict: 包含所有股票数据的字典
        """
        symbols = self.get_available_symbols()

        # 限制数量
        if limit and limit > 0:
            symbols = symbols[:limit]

        result = {
            "type": "multi_stock",
            "timestamp": datetime.now().isoformat(),
            "total_count": len(symbols),
            "full_data": full_data,  # 标记数据类型
            "stocks": [],
        }

        # 加载每个股票的数据
        for symbol in symbols:
            if full_data:
                # 本地模型：加载完整K线数据
                stock_data = self._load_stock_full(symbol)
            else:
                # API模型：加载摘要数据
                stock_data = self._load_stock_summary(symbol)

            if stock_data:
                result["stocks"].append(stock_data)

        # 加载指数数据（共享）
        indices = self._load_indices()
        if indices:
            result["indices"] = self._format_indices_for_ai(indices)

        # 加载行业资金流向（共享）
        industry_flow = self._load_industry_flow()
        if industry_flow is not None:
            result["industry_flow"] = self._format_industry_flow_for_ai(industry_flow)

        return result

    def _load_stock_full(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        加载单个股票的完整数据（本地模型使用）

        Args:
            symbol: 股票代码

        Returns:
            dict: 股票完整数据
        """
        klines = self._load_klines(symbol)
        if klines is None or klines.empty:
            return None

        latest = klines.iloc[-1]
        recent = klines.tail(30)

        # 获取股票所属行业
        industry_info = self._get_stock_industry(symbol)

        return {
            "symbol": symbol,
            "industry": industry_info.get("industry") if industry_info else None,
            "latest": {
                "date": latest['date'].strftime('%Y-%m-%d'),
                "open": float(latest['open']),
                "close": float(latest['close']),
                "high": float(latest['high']),
                "low": float(latest['low']),
                "volume": int(latest['volume']),
                "amount": float(latest['amount']),
                "change": float(latest['change']) if not pd.isna(latest['change']) else 0.0,
                "amplitude": float(latest['amplitude']) if not pd.isna(latest['amplitude']) else 0.0,
            },
            "technical": {
                "ma5": float(latest['ma5']) if not pd.isna(latest['ma5']) else None,
                "ma10": float(latest['ma10']) if not pd.isna(latest['ma10']) else None,
                "ma20": float(latest['ma20']) if not pd.isna(latest['ma20']) else None,
                "ma60": float(latest['ma60']) if not pd.isna(latest['ma60']) else None,
                "volume_ratio": float(latest['volume_ratio']) if not pd.isna(latest['volume_ratio']) else 1.0,
            },
            "trend": self._analyze_trend(recent),
            "support_resistance": self._calculate_support_resistance(recent),
            "statistics": {
                "avg_volume_30": float(recent['volume'].mean()),
                "max_high_30": float(recent['high'].max()),
                "min_low_30": float(recent['low'].min()),
                "volatility": float(recent['change'].std()),
            },
            # 完整数据额外包含：最近10天K线数据
            "recent_klines": [
                {
                    "date": row['date'].strftime('%Y-%m-%d'),
                    "open": float(row['open']),
                    "close": float(row['close']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "volume": int(row['volume']),
                    "change": float(row['change']) if not pd.isna(row['change']) else 0.0,
                }
                for _, row in recent.tail(10).iterrows()
            ],
            # 保留原始K线数据用于评分计算
            "klines_df": klines
        }

    def _load_stock_summary(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        加载单个股票的摘要数据

        Args:
            symbol: 股票代码

        Returns:
            dict: 股票摘要数据
        """
        klines = self._load_klines(symbol)
        if klines is None or klines.empty:
            return None

        latest = klines.iloc[-1]
        recent = klines.tail(30)

        # 获取股票所属行业
        industry_info = self._get_stock_industry(symbol)

        return {
            "symbol": symbol,
            "industry": industry_info.get("industry") if industry_info else None,
            "latest": {
                "date": latest['date'].strftime('%Y-%m-%d'),
                "close": float(latest['close']),
                "change": float(latest['change']) if not pd.isna(latest['change']) else 0.0,
                "volume": int(latest['volume']),
                "amount": float(latest['amount']),
            },
            "technical": {
                "ma5": float(latest['ma5']) if not pd.isna(latest['ma5']) else None,
                "ma10": float(latest['ma10']) if not pd.isna(latest['ma10']) else None,
                "ma20": float(latest['ma20']) if not pd.isna(latest['ma20']) else None,
                "ma60": float(latest['ma60']) if not pd.isna(latest['ma60']) else None,
                "volume_ratio": float(latest['volume_ratio']) if not pd.isna(latest['volume_ratio']) else 1.0,
            },
            "trend": self._analyze_trend(recent),
            "support_resistance": self._calculate_support_resistance(recent),
            "statistics": {
                "avg_volume_30": float(recent['volume'].mean()),
                "max_high_30": float(recent['high'].max()),
                "min_low_30": float(recent['low'].min()),
                "volatility": float(recent['change'].std()),
            },
            # 保留原始K线数据用于评分计算
            "klines_df": klines
        }


def format_market_data_for_ai(data: Dict[str, Any], full_data: bool = False) -> str:
    """
    将市场数据格式化为AI可读的文本

    Args:
        data: LocalDataLoader 加载的数据
        full_data: 是否输出完整数据（True=本地模型，False=API模型）

    Returns:
        str: 格式化的文本
    """
    lines = []

    # 多股票数据
    if data.get("type") == "multi_stock" and "stocks" in data:
        is_full = data.get("full_data", False)
        lines.append(f"\n## 市场扫描 ({data['total_count']} 只股票)")
        lines.append(f"\n扫描时间: {data.get('timestamp', 'N/A')}")

        for stock in data["stocks"]:
            symbol = stock["symbol"]
            industry = stock.get("industry", "未知")

            # 基本信息
            latest = stock["latest"]
            lines.append(f"\n### {symbol} ({industry})")
            lines.append(f"日期: {latest['date']}")
            lines.append(f"价格: {latest['close']:.2f}  涨跌: {latest['change']:+.2f}%")
            lines.append(f"成交量: {latest['volume']:,} 手")

            # 技术指标
            tech = stock["technical"]
            ma5_str = f"{tech['ma5']:.2f}" if tech.get('ma5') else "N/A"
            ma10_str = f"{tech['ma10']:.2f}" if tech.get('ma10') else "N/A"
            lines.append(f"技术: MA5={ma5_str} MA10={ma10_str} 量比={tech['volume_ratio']:.2f}")

            # 趋势
            trend = stock["trend"]
            lines.append(f"趋势: {trend['direction']} (5日: {trend['change_5d']:+.2f}%)")

            # 支撑阻力
            sr = stock["support_resistance"]
            if sr.get("support") and sr.get("resistance"):
                lines.append(f"支撑: {sr['support'][0]:.2f}  阻力: {sr['resistance'][0]:.2f}")

            # 评分信息 (新增)
            if "score" in stock:
                score = stock["score"]
                lines.append(f"评分: {score['total_score']}/100 信号:{score['buy_signal']}")
                lines.append(f"  技术:{score['technical_score']}/100 基本:{score['fundamental_score']}/100 资金:{score['money_flow_score']}/100")
                if score.get("reasons"):
                    lines.append(f"  理由: {', '.join(score['reasons'])}")
                if score.get("risk_factors"):
                    lines.append(f"  风险: {', '.join(score['risk_factors'])}")

            # 完整数据模式：显示最近K线
            if is_full and "recent_klines" in stock:
                lines.append(f"\n最近10天K线:")
                for kline in stock["recent_klines"]:
                    lines.append(f"  {kline['date']}: {kline['close']:.2f} ({kline['change']:+.2f}%) "
                                f"量:{kline['volume']:,}")

        # 指数数据
        if "indices" in data and data["indices"]:
            lines.append(f"\n## 主要指数")
            for idx in data["indices"]:
                lines.append(f"  {idx['name']}: {idx['close']:.2f} ({idx['change']:+.2f}%)")

        # 行业资金流向
        if "industry_flow" in data and data["industry_flow"]:
            lines.append(f"\n## 行业资金流向 (TOP 10)")
            for idx, ind in enumerate(data["industry_flow"][:5], 1):
                lines.append(f"  {idx}. {ind['industry']}: 净流入 {ind['net_flow']:.2f}亿, 涨跌 {ind['change_pct']:+.2f}%")

        return "\n".join(lines)

    # 单股票K线数据
    if "klines" in data:
        k = data["klines"]
        lines.append(f"\n## {data['symbol']} K线数据")

        # 最新行情
        if "latest" in k:
            l = k["latest"]
            lines.append(f"\n最新行情 ({l['date']}):")
            lines.append(f"  开盘: {l['open']:.2f}")
            lines.append(f"  收盘: {l['close']:.2f}")
            lines.append(f"  最高: {l['high']:.2f}")
            lines.append(f"  最低: {l['low']:.2f}")
            lines.append(f"  成交量: {l['volume']:,} 手")
            lines.append(f"  涨跌幅: {l['change']:+.2f}%")
            lines.append(f"  振幅: {l['amplitude']:.2f}%")

        # 技术指标
        if "technical" in k:
            t = k["technical"]
            lines.append(f"\n技术指标:")
            if t.get("ma5"):
                lines.append(f"  MA5: {t['ma5']:.2f}")
            if t.get("ma10"):
                lines.append(f"  MA10: {t['ma10']:.2f}")
            if t.get("ma20"):
                lines.append(f"  MA20: {t['ma20']:.2f}")
            if t.get("ma60"):
                lines.append(f"  MA60: {t['ma60']:.2f}")
            lines.append(f"  量比: {t['volume_ratio']:.2f}")

        # 趋势分析
        if "trend" in k:
            tr = k["trend"]
            lines.append(f"\n趋势分析:")
            lines.append(f"  方向: {tr['direction']}")
            lines.append(f"  5日涨跌: {tr['change_5d']:+.2f}%")
            lines.append(f"  均线排列: {tr['ma_alignment']}")

        # 支撑阻力
        if "support_resistance" in k:
            sr = k["support_resistance"]
            lines.append(f"\n支撑阻力:")
            if sr.get("support"):
                lines.append(f"  支撑位: {', '.join([f'{x:.2f}' for x in sr['support'][:3]])}")
            if sr.get("resistance"):
                lines.append(f"  阻力位: {', '.join([f'{x:.2f}' for x in sr['resistance'][:3]])}")

        # 统计数据
        if "statistics" in k:
            s = k["statistics"]
            lines.append(f"\n30日统计:")
            lines.append(f"  平均成交量: {s['avg_volume_30']:,.0f} 手")
            lines.append(f"  最高价: {s['max_high_30']:.2f}")
            lines.append(f"  最低价: {s['min_low_30']:.2f}")
            lines.append(f"  波动率: {s['volatility']:.2f}%")

    # 指数数据
    if "indices" in data and data["indices"]:
        lines.append(f"\n## 主要指数")
        for idx in data["indices"]:
            lines.append(f"  {idx['name']}: {idx['close']:.2f} ({idx['change']:+.2f}%)")

    # 行业资金流向
    if "industry_flow" in data and data["industry_flow"]:
        lines.append(f"\n## 行业资金流向 (TOP 10)")
        for idx, ind in enumerate(data["industry_flow"][:5], 1):
            lines.append(f"  {idx}. {ind['industry']}: 净流入 {ind['net_flow']:.2f}亿, 涨跌 {ind['change_pct']:+.2f}%")

    # 股票所属行业
    if "industry" in data:
        ind = data["industry"]
        lines.append(f"\n## 所属行业")
        lines.append(f"  {ind['industry']}")

    return "\n".join(lines)
