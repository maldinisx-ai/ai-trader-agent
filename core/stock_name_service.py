# -*- coding: utf-8 -*-
"""
股票名称映射服务

提供股票代码到名称的映射功能，支持从 AkShare 获取和本地缓存。
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
import pandas as pd

logger = logging.getLogger(__name__)


class StockNameService:
    """股票名称映射服务"""

    def __init__(self, data_dir: str = "data", cache_days: int = 7):
        """
        初始化服务

        Args:
            data_dir: 数据目录
            cache_days: 缓存有效期（天）
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.data_dir / "stock_names.json"
        self.cache_days = cache_days

        # 内存缓存
        self._name_map: Dict[str, str] = {}
        self._code_map: Dict[str, str] = {}  # 名称到代码的映射

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
                    if datetime.now() - last_update_dt < timedelta(days=self.cache_days):
                        self._name_map = data.get("names", {})
                        self._code_map = data.get("name_to_code", {})
                        logger.info(f"加载股票名称缓存: {len(self._name_map)} 只")
                        return

            except Exception as e:
                logger.warning(f"加载缓存失败: {e}")

    def _save_cache(self):
        """保存本地缓存"""
        try:
            data = {
                "last_update": datetime.now().isoformat(),
                "names": self._name_map,
                "name_to_code": self._code_map,
                "total": len(self._name_map),
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"保存股票名称缓存: {len(self._name_map)} 只")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")

    def _normalize_code(self, code: str) -> str:
        """
        标准化股票代码格式

        将 600519.SH 或 sh600519 转换为 600519.SH
        """
        code = code.strip().upper()

        # 如果已经是标准格式 (000001.SZ 或 600000.SH)
        if '.' in code and code.split('.')[-1] in ['SZ', 'SH']:
            return code

        # 去除前缀
        code = code.replace('SZ', '').replace('SH', '')
        code = code.replace('sz', '').replace('sh', '')

        # 添加后缀
        if code.startswith(('60', '68', '51')):
            return f"{code}.SH"  # 上海
        else:
            return f"{code}.SZ"  # 深圳

    def fetch_from_akshare(self) -> int:
        """
        从 AkShare 获取股票列表

        Returns:
            获取的股票数量
        """
        try:
            import akshare as ak
        except ImportError:
            logger.error("akshare 未安装")
            return 0

        logger.info("从 AkShare 获取股票列表...")
        new_count = 0

        # 获取 A 股列表
        try:
            df = ak.stock_info_a_code_name()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    code = str(row.get('code', ''))
                    name = str(row.get('name', ''))

                    if code and name:
                        # 标准化代码
                        norm_code = self._normalize_code(code)
                        self._name_map[norm_code] = name
                        self._code_map[name] = norm_code
                        new_count += 1

                logger.info(f"从 AkShare 获取 {new_count} 只股票")
                self._save_cache()
                return new_count

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")

        return 0

    def get_name(self, code: str) -> str:
        """
        获取股票名称

        Args:
            code: 股票代码（支持多种格式）

        Returns:
            股票名称，如果找不到返回代码本身
        """
        norm_code = self._normalize_code(code)

        # 从内存缓存获取
        if norm_code in self._name_map:
            return self._name_map[norm_code]

        # 如果缓存为空，尝试从 AkShare 获取
        if not self._name_map:
            self.fetch_from_akshare()
            if norm_code in self._name_map:
                return self._name_map[norm_code]

        # 找不到，返回代码
        return code

    def get_code(self, name: str) -> Optional[str]:
        """
        根据名称获取股票代码

        Args:
            name: 股票名称

        Returns:
            股票代码，如果找不到返回 None
        """
        # 如果缓存为空，先加载
        if not self._code_map:
            self.fetch_from_akshare()

        return self._code_map.get(name)

    def search(self, keyword: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        搜索股票

        Args:
            keyword: 搜索关键词（代码或名称）
            limit: 返回数量限制

        Returns:
            匹配的股票列表
        """
        # 确保缓存已加载
        if not self._name_map:
            self.fetch_from_akshare()

        keyword = keyword.upper()
        results = []

        # 按代码搜索
        for code, name in self._name_map.items():
            if keyword in code or keyword in name:
                results.append({"code": code, "name": name})
                if len(results) >= limit:
                    break

        return results

    def get_all_names(self) -> Dict[str, str]:
        """
        获取所有股票名称映射

        Returns:
            代码到名称的映射字典
        """
        # 确保缓存已加载
        if not self._name_map:
            self.fetch_from_akshare()

        return self._name_map.copy()

    def batch_get_names(self, codes: List[str]) -> Dict[str, str]:
        """
        批量获取股票名称

        Args:
            codes: 股票代码列表

        Returns:
            代码到名称的映射字典
        """
        return {code: self.get_name(code) for code in codes}

    def refresh(self):
        """刷新缓存（从 AkShare 重新获取）"""
        logger.info("刷新股票名称缓存...")
        self._name_map.clear()
        self._code_map.clear()
        return self.fetch_from_akshare()

    def add_custom(self, code: str, name: str):
        """
        添加自定义股票名称映射

        Args:
            code: 股票代码
            name: 股票名称
        """
        norm_code = self._normalize_code(code)
        self._name_map[norm_code] = name
        self._code_map[name] = norm_code
        logger.debug(f"添加自定义映射: {norm_code} -> {name}")

    def remove_custom(self, code: str):
        """
        移除自定义股票名称映射

        Args:
            code: 股票代码
        """
        norm_code = self._normalize_code(code)
        if norm_code in self._name_map:
            name = self._name_map[norm_code]
            del self._name_map[norm_code]
            if name in self._code_map:
                del self._code_map[name]
            logger.debug(f"移除映射: {norm_code}")


# 全局单例
_instance: Optional[StockNameService] = None


def get_stock_name_service(data_dir: str = "data") -> StockNameService:
    """
    获取股票名称服务单例

    Args:
        data_dir: 数据目录

    Returns:
        StockNameService 实例
    """
    global _instance
    if _instance is None:
        _instance = StockNameService(data_dir=data_dir)
    return _instance


if __name__ == "__main__":
    # 测试
    service = StockNameService()

    # 获取股票名称
    print("测试获取名称:")
    print(f"600519.SH -> {service.get_name('600519.SH')}")
    print(f"000001.SZ -> {service.get_name('000001.SZ')}")
    print(f"平安银行 -> {service.get_code('平安银行')}")

    # 搜索
    print("\n搜索 '银行':")
    results = service.search("银行", limit=5)
    for r in results:
        print(f"  {r['code']}: {r['name']}")

    # 刷新
    print(f"\n总股票数: {len(service.get_all_names())}")
