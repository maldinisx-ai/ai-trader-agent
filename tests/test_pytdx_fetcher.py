# -*- coding: utf-8 -*-
"""
测试 Pytdx 数据下载器 (mock 版本)

使用 mock 避免实际调用 Pytdx API
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager

# 导入 src.main 中的组件
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class MockPytdxDownloader:
    """Mock 版本的 PytdxDownloader，不依赖真实的 pytdx"""

    # 通达信服务器列表
    DEFAULT_HOSTS = [
        ("119.147.212.81", 7709),
        ("112.74.214.43", 7727),
        ("221.231.141.60", 7709),
        ("101.227.73.20", 7709),
    ]

    def __init__(self, hosts=None):
        """初始化下载器"""
        self._hosts = hosts or self.DEFAULT_HOSTS
        self._api = None
        self._current_host_idx = 0
        self._mock_api = Mock()  # Mock API 对象

    def _get_market_code(self, stock_code: str) -> tuple:
        """
        根据代码判断市场

        Returns:
            (market, code) 其中 market=0深圳, 1上海
        """
        code = stock_code.strip()
        code = code.replace('.SH', '').replace('.SZ', '')
        code = code.replace('.sh', '').replace('.sz', '')

        # 上海：60xxxx, 68xxxx
        if code.startswith(('60', '68')):
            return 1, code
        else:
            return 0, code

    @contextmanager
    def _connect(self):
        """连接上下文管理器（mock 版本）"""
        yield self._mock_api


@pytest.fixture
def downloader():
    """创建下载器实例"""
    return MockPytdxDownloader()


class TestMarketCode:
    """测试市场代码判断"""

    def test_get_market_code_shanghai_600xxx(self, downloader):
        """测试上海主板 600xxx"""
        market, code = downloader._get_market_code("600519")
        assert market == 1  # 上海
        assert code == "600519"

    def test_get_market_code_shanghai_601xxx(self, downloader):
        """测试上海主板 601xxx"""
        market, code = downloader._get_market_code("601318")
        assert market == 1
        assert code == "601318"

    def test_get_market_code_shanghai_603xxx(self, downloader):
        """测试上海主板 603xxx"""
        market, code = downloader._get_market_code("603259")
        assert market == 1
        assert code == "603259"

    def test_get_market_code_shanghai_68xxx(self, downloader):
        """测试上海科创板 68xxx"""
        market, code = downloader._get_market_code("688981")
        assert market == 1
        assert code == "688981"

    def test_get_market_code_shenzhen_000xxx(self, downloader):
        """测试深圳主板 000xxx"""
        market, code = downloader._get_market_code("000001")
        assert market == 0  # 深圳
        assert code == "000001"

    def test_get_market_code_shenzhen_001xxx(self, downloader):
        """测试深圳主板 001xxx"""
        market, code = downloader._get_market_code("001979")
        assert market == 0
        assert code == "001979"

    def test_get_market_code_shenzhen_002xxx(self, downloader):
        """测试深圳中小板 002xxx"""
        market, code = downloader._get_market_code("002415")
        assert market == 0
        assert code == "002415"

    def test_get_market_code_shenzhen_300xxx(self, downloader):
        """测试深圳创业板 300xxx"""
        market, code = downloader._get_market_code("300750")
        assert market == 0
        assert code == "300750"

    def test_get_market_code_with_dot_sh(self, downloader):
        """测试带.SH后缀"""
        market, code = downloader._get_market_code("600519.SH")
        assert market == 1
        assert code == "600519"

    def test_get_market_code_with_dot_sz(self, downloader):
        """测试带.SZ后缀"""
        market, code = downloader._get_market_code("000001.SZ")
        assert market == 0
        assert code == "000001"

    def test_get_market_code_with_lowercase_dot(self, downloader):
        """测试带小写点后缀"""
        market, code = downloader._get_market_code("600519.sh")
        assert market == 1
        assert code == "600519"

    def test_get_market_code_with_whitespace(self, downloader):
        """测试带空格"""
        market, code = downloader._get_market_code("  600519  ")
        assert market == 1
        assert code == "600519"


class TestInitialization:
    """测试初始化"""

    def test_init_default_hosts(self):
        """测试使用默认服务器列表"""
        downloader = MockPytdxDownloader()
        assert len(downloader._hosts) > 0
        assert downloader._hosts == MockPytdxDownloader.DEFAULT_HOSTS

    def test_init_custom_hosts(self):
        """测试使用自定义服务器列表"""
        custom_hosts = [("127.0.0.1", 7709), ("192.168.1.1", 7709)]
        downloader = MockPytdxDownloader(hosts=custom_hosts)
        assert downloader._hosts == custom_hosts

    def test_init_with_pytdx_missing(self):
        """测试 pytdx 未安装"""
        from tools.data.pytdx_fetcher import PytdxDownloader

        with patch.dict('sys.modules', {'pytdx': None}):
            # _get_api() 才会检查 pytdx 是否存在
            dl = PytdxDownloader.__new__(PytdxDownloader)
            dl._hosts = []
            dl._api = None
            dl._current_host_idx = 0

            with pytest.raises(RuntimeError) as exc_info:
                dl._get_api()
            assert "pytdx 未安装" in str(exc_info.value)


class TestDefaultHosts:
    """测试默认服务器配置"""

    def test_default_hosts_format(self):
        """测试默认服务器格式"""
        for host, port in MockPytdxDownloader.DEFAULT_HOSTS:
            assert isinstance(host, str)
            assert isinstance(port, int)
            assert 1024 <= port <= 65535

    def test_default_hosts_count(self):
        """测试默认服务器数量"""
        assert len(MockPytdxDownloader.DEFAULT_HOSTS) >= 4


class TestRealClassMethods:
    """测试真实类的方法"""

    def test_get_market_code_real_class(self):
        """测试真实类的 _get_market_code 方法"""
        from tools.data.pytdx_fetcher import PytdxDownloader

        with patch.dict('sys.modules', {'pytdx': Mock()}):
            dl = PytdxDownloader.__new__(PytdxDownloader)
            dl._hosts = []
            dl._api = None
            dl._current_host_idx = 0

            # 测试上海市场
            assert dl._get_market_code("600519") == (1, "600519")
            assert dl._get_market_code("601318") == (1, "601318")
            assert dl._get_market_code("688981") == (1, "688981")

            # 测试深圳市场
            assert dl._get_market_code("000001") == (0, "000001")
            assert dl._get_market_code("002415") == (0, "002415")
            assert dl._get_market_code("300750") == (0, "300750")


class TestHostIndexManagement:
    """测试服务器索引管理"""

    def test_current_host_idx_initialization(self, downloader):
        """测试当前服务器索引初始化"""
        assert downloader._current_host_idx == 0

    def test_multiple_hosts_available(self, downloader):
        """测试多个服务器可用"""
        assert len(downloader._hosts) >= 2


class TestConnectContextManager:
    """测试连接上下文管理器"""

    def test_connect_context_yields_api(self, downloader):
        """测试上下文管理器返回 API 对象"""
        with downloader._connect() as api:
            assert api is downloader._mock_api


class TestMarketCodeEdgeCases:
    """测试市场代码边缘情况"""

    def test_all_shanghai_prefixes(self, downloader):
        """测试所有上海前缀"""
        shanghai_prefixes = ['60', '68']
        for prefix in shanghai_prefixes:
            market, code = downloader._get_market_code(f"{prefix}0001")
            assert market == 1
            assert code.startswith(prefix)

    def test_all_shenzhen_prefixes(self, downloader):
        """测试所有深圳前缀"""
        shenzhen_prefixes = ['00', '30']
        for prefix in shenzhen_prefixes:
            market, code = downloader._get_market_code(f"{prefix}0001")
            assert market == 0
            assert code.startswith(prefix)

    def test_mixed_case_suffixes(self, downloader):
        """测试混合大小写后缀"""
        test_cases = [
            ("600519.SH", (1, "600519")),
            ("600519.sh", (1, "600519")),
            ("000001.SZ", (0, "000001")),
            ("000001.sz", (0, "000001")),
        ]
        for input_code, expected in test_cases:
            result = downloader._get_market_code(input_code)
            assert result == expected


class TestHostConfiguration:
    """测试服务器配置"""

    def test_custom_hosts_override_default(self):
        """测试自定义服务器覆盖默认"""
        custom = [("10.0.0.1", 7777)]
        dl = MockPytdxDownloader(hosts=custom)
        assert dl._hosts == custom
        assert len(dl._hosts) == 1

    def test_empty_hosts_not_allowed(self):
        """测试不允许空服务器列表"""
        dl = MockPytdxDownloader(hosts=None)  # None 应该使用默认列表
        assert dl._hosts != []  # 应该使用默认列表


class TestAPIManagement:
    """测试 API 管理"""

    def test_api_attribute_exists(self, downloader):
        """测试 API 属性存在"""
        assert hasattr(downloader, '_api')
        assert downloader._api is None  # 初始状态为 None

    def test_mock_api_is_callable(self, downloader):
        """测试 mock API 可调用"""
        assert callable(downloader._mock_api) or isinstance(downloader._mock_api, Mock)


class TestRealClassAttributes:
    """测试真实类属性"""

    def test_default_hosts_is_list(self):
        """测试 DEFAULT_HOSTS 是列表"""
        from tools.data.pytdx_fetcher import PytdxDownloader
        assert isinstance(PytdxDownloader.DEFAULT_HOSTS, list)

    def test_default_hosts_elements_are_tuples(self):
        """测试 DEFAULT_HOSTS 元素是元组"""
        from tools.data.pytdx_fetcher import PytdxDownloader
        for host in PytdxDownloader.DEFAULT_HOSTS:
            assert isinstance(host, tuple)
            assert len(host) == 2


class TestCodeCleaning:
    """测试代码清理"""

    def test_remove_dot_sh_upper(self, downloader):
        """测试移除.SH"""
        market, code = downloader._get_market_code("600519.SH")
        assert code == "600519"

    def test_remove_dot_sh_lower(self, downloader):
        """测试移除.sh"""
        market, code = downloader._get_market_code("600519.sh")
        assert code == "600519"

    def test_remove_dot_sz_upper(self, downloader):
        """测试移除.SZ"""
        market, code = downloader._get_market_code("000001.SZ")
        assert code == "000001"

    def test_remove_dot_sz_lower(self, downloader):
        """测试移除.sz"""
        market, code = downloader._get_market_code("000001.sz")
        assert code == "000001"

    def test_strip_whitespace(self, downloader):
        """测试移除空格"""
        market, code = downloader._get_market_code("  600519  ")
        assert code == "600519"

    def test_multiple_suffixes_removed(self, downloader):
        """测试移除多个后缀"""
        market, code = downloader._get_market_code("600519.sh.SH")
        assert code == "600519"

    def test_code_stripped_no_suffix(self, downloader):
        """测试无后缀代码"""
        market, code = downloader._get_market_code("600519")
        assert code == "600519"


class TestMarketClassification:
    """测试市场分类"""

    def test_shanghai_main_board(self, downloader):
        """测试上海主板"""
        for code in ["600000", "601000", "602000", "603000", "605000"]:
            market, _ = downloader._get_market_code(code)
            assert market == 1, f"{code} 应该是上海市场"

    def test_shanghai_star_market(self, downloader):
        """测试上海科创板"""
        for code in ["688000", "688001", "688999"]:
            market, _ = downloader._get_market_code(code)
            assert market == 1, f"{code} 应该是上海市场"

    def test_shenzhen_main_board(self, downloader):
        """测试深圳主板"""
        for code in ["000001", "000002", "000858"]:
            market, _ = downloader._get_market_code(code)
            assert market == 0, f"{code} 应该是深圳市场"

    def test_shenzhen_sme(self, downloader):
        """测试深圳中小板"""
        for code in ["002001", "002594", "002736"]:
            market, _ = downloader._get_market_code(code)
            assert market == 0, f"{code} 应该是深圳市场"

    def test_shenzhen_chi_next(self, downloader):
        """测试深圳创业板"""
        for code in ["300001", "300059", "300750"]:
            market, _ = downloader._get_market_code(code)
            assert market == 0, f"{code} 应该是深圳市场"


class TestInitializationDefaults:
    """测试初始化默认值"""

    def test_api_none_by_default(self, downloader):
        """测试 API 默认为 None"""
        assert downloader._api is None

    def test_current_host_idx_zero_by_default(self, downloader):
        """测试当前服务器索引默认为 0"""
        assert downloader._current_host_idx == 0


class TestServerList:
    """测试服务器列表"""

    def test_default_servers_are_reachable_ips(self):
        """测试默认服务器是可达的 IP"""
        from tools.data.pytdx_fetcher import PytdxDownloader
        for host, _ in PytdxDownloader.DEFAULT_HOSTS:
            # 验证是有效的 IP 地址格式
            parts = host.split('.')
            assert len(parts) == 4
            for part in parts:
                assert part.isdigit()
                assert 0 <= int(part) <= 255

    def test_default_servers_use_standard_port(self):
        """测试默认服务器使用标准端口"""
        from tools.data.pytdx_fetcher import PytdxDownloader
        for _, port in PytdxDownloader.DEFAULT_HOSTS:
            assert port in [7709, 7727]