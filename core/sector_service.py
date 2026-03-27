# -*- coding: utf-8 -*-
"""
行业板块数据服务

提供行业板块数据的获取、缓存和查询功能。
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class SectorData:
    """行业板块数据"""

    def __init__(
        self,
        code: str,
        name: str,
        current_price: float,
        change: float,
        change_pct: float,
        volume: float = 0,
        amount: float = 0,
    ):
        self.code = code
        self.name = name
        self.current_price = current_price
        self.change = change
        self.change_pct = change_pct
        self.volume = volume
        self.amount = amount

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "code": self.code,
            "name": self.name,
            "current_price": self.current_price,
            "change": self.change,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "amount": self.amount,
        }


class SectorService:
    """行业板块数据服务"""

    def __init__(self, data_dir: str = "data", cache_hours: int = 4):
        """
        初始化服务

        Args:
            data_dir: 数据目录
            cache_hours: 缓存有效期（小时）
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.data_dir / "sectors.json"
        self.cache_hours = cache_hours

        # 内存缓存
        self._sectors: List[SectorData] = []

        # 加载缓存
        self._load_cache()

    def _load_cache(self):
        """加载本地缓存"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 检查缓存是否过期
                last_update = data.get("last_update")
                if last_update:
                    last_update_dt = datetime.fromisoformat(last_update)
                    if datetime.now() - last_update_dt < timedelta(hours=self.cache_hours):
                        self._sectors = [
                            SectorData(**s) for s in data.get("sectors", [])
                        ]
                        logger.info(f"加载行业板块缓存: {len(self._sectors)} 个")
                        return

            except Exception as e:
                logger.warning(f"加载缓存失败: {e}")

    def _save_cache(self):
        """保存本地缓存"""
        try:
            data = {
                "last_update": datetime.now().isoformat(),
                "sectors": [s.to_dict() for s in self._sectors],
                "total": len(self._sectors),
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"保存行业板块缓存: {len(self._sectors)} 个")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")

    def fetch_from_akshare(self) -> int:
        """
        从 AkShare 获取行业板块数据

        Returns:
            获取的板块数量
        """
        try:
            import akshare as ak
        except ImportError:
            logger.error("akshare 未安装")
            return 0

        logger.info("从 AkShare 获取行业板块数据...")
        sectors = []

        # 获取行业板块列表
        try:
            # 获取申万行业板块
            df = ak.stock_board_industry_name_em()

            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    try:
                        code = str(row.get('板块代码', ''))
                        name = str(row.get('板块名称', ''))

                        if not code or not name:
                            continue

                        # 获取板块成分股行情
                        try:
                            detail_df = ak.stock_board_industry_cons_em(symbol=name)
                            if detail_df is not None and not detail_df.empty:
                                # 计算板块平均涨跌幅
                                detail_df['最新价'] = pd.to_numeric(detail_df.get('最新价', 0), errors='coerce')
                                detail_df['涨跌幅'] = pd.to_numeric(detail_df.get('涨跌幅', 0), errors='coerce')

                                avg_price = detail_df['最新价'].mean()
                                avg_change_pct = detail_df['涨跌幅'].mean()

                                # 估算涨跌额
                                change = avg_price * (avg_change_pct / 100)

                                sectors.append(SectorData(
                                    code=code,
                                    name=name,
                                    current_price=round(avg_price, 2),
                                    change=round(change, 2),
                                    change_pct=round(avg_change_pct, 2),
                                ))
                        except Exception as e:
                            logger.debug(f"获取 {name} 详情失败: {e}")
                            # 使用默认值
                            sectors.append(SectorData(
                                code=code,
                                name=name,
                                current_price=0,
                                change=0,
                                change_pct=0,
                            ))

                    except Exception as e:
                        logger.debug(f"处理板块数据失败: {e}")
                        continue

                self._sectors = sectors
                self._save_cache()
                logger.info(f"从 AkShare 获取 {len(sectors)} 个行业板块")
                return len(sectors)

        except Exception as e:
            logger.error(f"获取行业板块数据失败: {e}")

        return 0

    def get_all_sectors(self) -> List[SectorData]:
        """
        获取所有行业板块

        Returns:
            行业板块列表
        """
        # 如果缓存为空，尝试获取
        if not self._sectors:
            self.fetch_from_akshare()

        return self._sectors.copy()

    def get_sector(self, code: str) -> Optional[SectorData]:
        """
        获取单个行业板块

        Args:
            code: 板块代码

        Returns:
            行业板块数据，如果找不到返回 None
        """
        sectors = self.get_all_sectors()
        for sector in sectors:
            if sector.code == code or sector.name == code:
                return sector
        return None

    def search(self, keyword: str, limit: int = 10) -> List[SectorData]:
        """
        搜索行业板块

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制

        Returns:
            匹配的板块列表
        """
        sectors = self.get_all_sectors()
        results = []

        for sector in sectors:
            if keyword in sector.code or keyword in sector.name:
                results.append(sector)
                if len(results) >= limit:
                    break

        return results

    def get_top_gainers(self, limit: int = 5) -> List[SectorData]:
        """
        获取涨幅榜

        Args:
            limit: 返回数量限制

        Returns:
            涨幅最大的板块列表
        """
        sectors = self.get_all_sectors()
        return sorted(sectors, key=lambda x: x.change_pct, reverse=True)[:limit]

    def get_top_losers(self, limit: int = 5) -> List[SectorData]:
        """
        获取跌幅榜

        Args:
            limit: 返回数量限制

        Returns:
            跌幅最大的板块列表
        """
        sectors = self.get_all_sectors()
        return sorted(sectors, key=lambda x: x.change_pct)[:limit]

    def refresh(self):
        """刷新缓存（从 AkShare 重新获取）"""
        logger.info("刷新行业板块缓存...")
        self._sectors.clear()
        return self.fetch_from_akshare()

    def get_statistics(self) -> Dict:
        """
        获取统计信息

        Returns:
            统计数据
        """
        sectors = self.get_all_sectors()

        if not sectors:
            return {
                "total": 0,
                "rising": 0,
                "falling": 0,
                "flat": 0,
                "avg_change_pct": 0,
            }

        rising = sum(1 for s in sectors if s.change_pct > 0)
        falling = sum(1 for s in sectors if s.change_pct < 0)
        flat = sum(1 for s in sectors if s.change_pct == 0)
        avg_change_pct = sum(s.change_pct for s in sectors) / len(sectors)

        return {
            "total": len(sectors),
            "rising": rising,
            "falling": falling,
            "flat": flat,
            "avg_change_pct": round(avg_change_pct, 2),
            "top_gainer": sectors[0].to_dict() if sectors else None,
        }


# 全局单例
_instance: Optional[SectorService] = None


def get_sector_service(data_dir: str = "data") -> SectorService:
    """
    获取行业板块服务单例

    Args:
        data_dir: 数据目录

    Returns:
        SectorService 实例
    """
    global _instance
    if _instance is None:
        _instance = SectorService(data_dir=data_dir)
    return _instance
