# -*- coding: utf-8 -*-
"""
money_flow_scoring.py 模块的单元测试
"""

# 必须先导入模块以确保覆盖率收集
import core.money_flow_scoring

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from pathlib import Path

from core.money_flow_scoring import (
    MoneyFlowScore,
    MoneyFlowScorer,
)


class TestMoneyFlowScore:
    """测试 MoneyFlowScore 数据类"""

    def test_initialization(self):
        """测试初始化"""
        score = MoneyFlowScore(
            total_score=80,
            main_flow_score=35,
            net_flow_score=25,
            margin_score=20,
            reasons=["主力流入", "净流入"],
            risk_factors=["融资下降"],
        )

        assert score.total_score == 80
        assert score.main_flow_score == 35
        assert score.net_flow_score == 25
        assert score.margin_score == 20
        assert len(score.reasons) == 2
        assert len(score.risk_factors) == 1

    def test_default_lists(self):
        """测试默认空列表"""
        score = MoneyFlowScore(
            total_score=50,
            main_flow_score=15,
            net_flow_score=15,
            margin_score=20,
        )

        assert score.reasons == []
        assert score.risk_factors == []

    def test_to_dict(self):
        """测试转换为字典"""
        score = MoneyFlowScore(
            total_score=80,
            main_flow_score=35,
            net_flow_score=25,
            margin_score=20,
            reasons=["主力流入"],
            risk_factors=["融资下降"],
        )

        result = score.to_dict()

        assert result['total_score'] == 80
        assert result['main_flow_score'] == 35
        assert result['net_flow_score'] == 25
        assert result['margin_score'] == 20
        assert result['reasons'] == ["主力流入"]
        assert result['risk_factors'] == ["融资下降"]


class TestMoneyFlowScorer:
    """测试 MoneyFlowScorer 类"""

    def test_weights_constants(self):
        """测试权重常量"""
        scorer = MoneyFlowScorer()
        assert scorer.WEIGHTS['main_flow'] == 40
        assert scorer.WEIGHTS['net_flow'] == 30
        assert scorer.WEIGHTS['margin'] == 30
        assert sum(scorer.WEIGHTS.values()) == 100

    def test_initialization_default(self):
        """测试默认初始化"""
        scorer = MoneyFlowScorer()

        assert scorer.data_dir == Path("data")
        assert scorer.money_flow_dir == Path("data") / "money_flow"
        assert scorer.margin_dir == Path("data") / "margin"

    def test_initialization_custom(self):
        """测试自定义数据目录"""
        scorer = MoneyFlowScorer(data_dir="custom_data")

        assert scorer.data_dir == Path("custom_data")
        assert scorer.money_flow_dir == Path("custom_data") / "money_flow"
        assert scorer.margin_dir == Path("custom_data") / "margin"


class TestLoadMoneyFlow:
    """测试加载资金流向数据"""

    @patch('core.money_flow_scoring.pd.read_csv')
    @patch('core.money_flow_scoring.Path.exists')
    def test_load_success(self, mock_exists, mock_read_csv):
        """测试成功加载数据"""
        mock_exists.return_value = True
        mock_df = pd.DataFrame({'mainNetInflow': [100000000]})
        mock_read_csv.return_value = mock_df

        scorer = MoneyFlowScorer()
        result = scorer._load_money_flow("000001")

        assert result is not None
        assert len(result) == 1

    @patch('core.money_flow_scoring.Path.exists')
    def test_load_file_not_exists(self, mock_exists):
        """测试文件不存在"""
        mock_exists.return_value = False

        scorer = MoneyFlowScorer()
        result = scorer._load_money_flow("000001")

        assert result is None

    @patch('core.money_flow_scoring.pd.read_csv')
    @patch('core.money_flow_scoring.Path.exists')
    def test_load_exception(self, mock_exists, mock_read_csv):
        """测试加载异常"""
        mock_exists.return_value = True
        mock_read_csv.side_effect = Exception("Read error")

        scorer = MoneyFlowScorer()
        result = scorer._load_money_flow("000001")

        assert result is None

    def test_symbol_to_filename(self):
        """测试股票代码转换文件名"""
        with patch('core.money_flow_scoring.pd.read_csv') as mock_read_csv, \
             patch('core.money_flow_scoring.Path.exists') as mock_exists:
            mock_exists.return_value = True
            mock_read_csv.return_value = pd.DataFrame()

            scorer = MoneyFlowScorer()
            scorer._load_money_flow("600519.SH")
            scorer._load_money_flow("000001.SZ")

            # 验证文件名格式
            call_args = [call[0][0] for call in mock_read_csv.call_args_list]
            assert "money_flow_600519_SH.csv" in str(call_args)
            assert "money_flow_000001_SZ.csv" in str(call_args)


class TestLoadMarginDetail:
    """测试加载融资融券详情"""

    @patch('core.money_flow_scoring.pd.read_csv')
    @patch('core.money_flow_scoring.Path.exists')
    def test_load_success(self, mock_exists, mock_read_csv):
        """测试成功加载数据"""
        mock_exists.return_value = True
        mock_df = pd.DataFrame({'financingBalance': [1000000]})
        mock_read_csv.return_value = mock_df

        scorer = MoneyFlowScorer()
        result = scorer._load_margin_detail("000001")

        assert result is not None
        assert len(result) == 1

    @patch('core.money_flow_scoring.Path.exists')
    def test_load_file_not_exists(self, mock_exists):
        """测试文件不存在"""
        mock_exists.return_value = False

        scorer = MoneyFlowScorer()
        result = scorer._load_margin_detail("000001")

        assert result is None

    @patch('core.money_flow_scoring.pd.read_csv')
    @patch('core.money_flow_scoring.Path.exists')
    def test_load_exception(self, mock_exists, mock_read_csv):
        """测试加载异常"""
        mock_exists.return_value = True
        mock_read_csv.side_effect = Exception("Read error")

        scorer = MoneyFlowScorer()
        result = scorer._load_margin_detail("000001")

        assert result is None


class TestScoreMainFlow:
    """测试主力资金流入评分"""

    def test_score_main_flow_none(self):
        """测试空数据"""
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_main_flow(None)

        assert score == 15
        assert "资金流向数据缺失" in reasons

    def test_score_main_flow_empty(self):
        """测试空 DataFrame"""
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_main_flow(pd.DataFrame())

        assert score == 15
        assert "资金流向数据缺失" in reasons

    def test_score_main_flow_very_large_inflow(self):
        """测试大幅流入 (>1亿)"""
        df = pd.DataFrame({'mainNetInflow': [150000000]})
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_main_flow(df)

        assert score == 40
        assert "主力大幅流入" in reasons

    def test_score_main_flow_large_inflow(self):
        """测试明显流入 (>5000万)"""
        test_cases = [60000000, 75000000, 99000000]
        scorer = MoneyFlowScorer()

        for flow in test_cases:
            df = pd.DataFrame({'mainNetInflow': [flow]})
            score, reasons = scorer.score_main_flow(df)
            assert score == 35
            assert "主力明显流入" in reasons

    def test_score_main_flow_medium_inflow(self):
        """测试小幅流入 (>1000万)"""
        test_cases = [15000000, 30000000, 49000000]
        scorer = MoneyFlowScorer()

        for flow in test_cases:
            df = pd.DataFrame({'mainNetInflow': [flow]})
            score, reasons = scorer.score_main_flow(df)
            assert score == 25
            assert "主力小幅流入" in reasons

    def test_score_main_flow_small_inflow(self):
        """测试微幅流入 (>0)"""
        test_cases = [1000000, 5000000, 9000000]
        scorer = MoneyFlowScorer()

        for flow in test_cases:
            df = pd.DataFrame({'mainNetInflow': [flow]})
            score, reasons = scorer.score_main_flow(df)
            assert score == 15
            assert "主力微幅流入" in reasons

    def test_score_main_flow_outflow(self):
        """测试净流出 (<0)"""
        test_cases = [-1000000, -50000000, -100000000]
        scorer = MoneyFlowScorer()

        for flow in test_cases:
            df = pd.DataFrame({'mainNetInflow': [flow]})
            score, reasons = scorer.score_main_flow(df)
            assert score == 5
            assert "主力净流出" in reasons

    def test_score_main_flow_zero(self):
        """测试零流入"""
        df = pd.DataFrame({'mainNetInflow': [0]})
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_main_flow(df)

        assert score == 5
        assert "主力净流出" in reasons

    def test_score_main_flow_boundary_values(self):
        """测试边界值"""
        scorer = MoneyFlowScorer()

        # 1亿边界
        df = pd.DataFrame({'mainNetInflow': [100000000]})
        score, _ = scorer.score_main_flow(df)
        assert score == 35  # 不是40

        df = pd.DataFrame({'mainNetInflow': [100000001]})
        score, _ = scorer.score_main_flow(df)
        assert score == 40

        # 5000万边界
        df = pd.DataFrame({'mainNetInflow': [50000000]})
        score, _ = scorer.score_main_flow(df)
        assert score == 25  # 不是35

        df = pd.DataFrame({'mainNetInflow': [50000001]})
        score, _ = scorer.score_main_flow(df)
        assert score == 35

        # 1000万边界
        df = pd.DataFrame({'mainNetInflow': [10000000]})
        score, _ = scorer.score_main_flow(df)
        assert score == 15  # 不是25

        df = pd.DataFrame({'mainNetInflow': [10000001]})
        score, _ = scorer.score_main_flow(df)
        assert score == 25

    def test_score_main_flow_different_columns(self):
        """测试不同的列名"""
        test_columns = ['mainNetInflow', '主力净流入', 'big_net_in', '超级大单净额']
        scorer = MoneyFlowScorer()

        for col in test_columns:
            df = pd.DataFrame({col: [120000000]})
            score, reasons = scorer.score_main_flow(df)
            assert score == 40

    def test_score_main_flow_column_not_found(self):
        """测试未找到列"""
        df = pd.DataFrame({'other_col': [10000000]})
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_main_flow(df)

        assert score == 15
        assert "主力资金列未找到" in reasons

    def test_score_main_flow_nan_value(self):
        """测试 NaN 值"""
        df = pd.DataFrame({'mainNetInflow': [None]})
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_main_flow(df)

        assert score == 15
        assert "主力资金数据无效" in reasons


class TestScoreNetFlow:
    """测试净流入评分"""

    def test_score_net_flow_none(self):
        """测试空数据"""
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(None)

        assert score == 15
        assert "净流入数据不足" in reasons

    def test_score_net_flow_empty(self):
        """测试空 DataFrame"""
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(pd.DataFrame())

        assert score == 15
        assert "净流入数据不足" in reasons

    def test_score_net_flow_insufficient_rows(self):
        """测试数据行数不足"""
        df = pd.DataFrame({'netInflow': [1000]})
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(df)

        assert score == 15
        assert "净流入数据不足" in reasons

    def test_score_net_flow_3_days_inflow(self):
        """测试连续3天净流入"""
        df = pd.DataFrame({
            'netInflow': [1000, 800, 600],
            'date': ['2024-01-03', '2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(df)

        assert score == 30
        assert "连续净流入" in reasons

    def test_score_net_flow_2_days_inflow(self):
        """测试连续2天净流入"""
        df = pd.DataFrame({
            'netInflow': [1000, 800, -500],
            'date': ['2024-01-03', '2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(df)

        assert score == 25
        assert "连续2天净流入" in reasons

    def test_score_net_flow_1_day_inflow(self):
        """测试当日净流入"""
        df = pd.DataFrame({
            'netInflow': [1000, -800, -600],
            'date': ['2024-01-03', '2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(df)

        assert score == 20
        assert "当日净流入" in reasons

    def test_score_net_flow_zero(self):
        """测试资金震荡 (全部为0)"""
        df = pd.DataFrame({
            'netInflow': [0, 0, 0],
            'date': ['2024-01-03', '2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(df)

        assert score == 15
        assert "资金震荡" in reasons

    def test_score_net_flow_outflow(self):
        """测试资金净流出"""
        df = pd.DataFrame({
            'netInflow': [-1000, -800, -600],
            'date': ['2024-01-03', '2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(df)

        assert score == 5
        assert "资金净流出" in reasons

    def test_score_net_flow_different_columns(self):
        """测试不同的列名"""
        test_columns = ['netInflow', '净流入', 'net_amount']

        scorer = MoneyFlowScorer()
        for col in test_columns:
            df = pd.DataFrame({
                col: [1000, 800, 600],
                'date': ['2024-01-03', '2024-01-02', '2024-01-01'],
            })
            score, reasons = scorer.score_net_flow(df)
            assert score == 30

    def test_score_net_flow_column_not_found(self):
        """测试未找到列"""
        df = pd.DataFrame({
            'other_col': [1000, 800, 600],
            'date': ['2024-01-03', '2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_net_flow(df)

        assert score == 15
        assert "净流入列未找到" in reasons


class TestScoreMargin:
    """测试融资融券评分"""

    def test_score_margin_none(self):
        """测试空数据"""
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_margin(None)

        assert score == 15
        assert "融资融券数据不足" in reasons

    def test_score_margin_empty(self):
        """测试空 DataFrame"""
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_margin(pd.DataFrame())

        assert score == 15
        assert "融资融券数据不足" in reasons

    def test_score_margin_insufficient_rows(self):
        """测试数据行数不足"""
        df = pd.DataFrame({'financingBalance': [1000000]})
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_margin(df)

        assert score == 15
        assert "融资融券数据不足" in reasons

    def test_score_margin_large_increase(self):
        """测试融资余额大增 (>10%)"""
        df = pd.DataFrame({
            'financingBalance': [1100001, 1000000],  # 10.0001% 增长 (>10%)
            'date': ['2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_margin(df)

        assert score == 30
        assert "融资余额大增" in reasons

    def test_score_margin_increase(self):
        """测试融资余额增加 (>5%)"""
        test_cases = [1060000, 1080000, 1090000]
        scorer = MoneyFlowScorer()

        for balance in test_cases:
            df = pd.DataFrame({
                'financingBalance': [balance, 1000000],
                'date': ['2024-01-02', '2024-01-01'],
            })
            score, reasons = scorer.score_margin(df)
            assert score == 25
            assert "融资余额增加" in reasons

    def test_score_margin_small_increase(self):
        """测试融资余额微增 (>0%)"""
        test_cases = [1010000, 1030000, 1040000]
        scorer = MoneyFlowScorer()

        for balance in test_cases:
            df = pd.DataFrame({
                'financingBalance': [balance, 1000000],
                'date': ['2024-01-02', '2024-01-01'],
            })
            score, reasons = scorer.score_margin(df)
            assert score == 20
            assert "融资余额微增" in reasons

    def test_score_margin_decrease(self):
        """测试融资余额下降"""
        df = pd.DataFrame({
            'financingBalance': [900000, 1000000],
            'date': ['2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_margin(df)

        assert score == 10
        assert "融资余额下降" in reasons

    def test_score_margin_zero_growth(self):
        """测试零增长"""
        df = pd.DataFrame({
            'financingBalance': [1000000, 1000000],
            'date': ['2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_margin(df)

        assert score == 10
        assert "融资余额下降" in reasons

    def test_score_margin_boundary_values(self):
        """测试边界值"""
        scorer = MoneyFlowScorer()

        # 10% 边界
        df = pd.DataFrame({
            'financingBalance': [1100000, 1000000],
        })
        score, _ = scorer.score_margin(df)
        assert score == 25  # 不是30

        df = pd.DataFrame({
            'financingBalance': [1100001, 1000000],
        })
        score, _ = scorer.score_margin(df)
        assert score == 30

        # 5% 边界
        df = pd.DataFrame({
            'financingBalance': [1050000, 1000000],
        })
        score, _ = scorer.score_margin(df)
        assert score == 20  # 不是25

        df = pd.DataFrame({
            'financingBalance': [1050001, 1000000],
        })
        score, _ = scorer.score_margin(df)
        assert score == 25

    def test_score_margin_different_columns(self):
        """测试不同的列名"""
        test_columns = ['financingBalance', '融资余额', 'fin_sum']

        scorer = MoneyFlowScorer()
        for col in test_columns:
            df = pd.DataFrame({
                col: [1100001, 1000000],  # 10.0001% 增长 (>10%)
                'date': ['2024-01-02', '2024-01-01'],
            })
            score, reasons = scorer.score_margin(df)
            assert score == 30  # 大增

    def test_score_margin_column_not_found(self):
        """测试未找到列"""
        df = pd.DataFrame({
            'other_col': [1100000, 1000000],
            'date': ['2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_margin(df)

        assert score == 15
        assert "融资余额列未找到" in reasons

    def test_score_margin_nan_values(self):
        """测试 NaN 值"""
        df = pd.DataFrame({
            'financingBalance': [None, 1000000],
            'date': ['2024-01-02', '2024-01-01'],
        })
        scorer = MoneyFlowScorer()
        score, reasons = scorer.score_margin(df)

        assert score == 15
        assert "融资余额数据无效" in reasons


class TestScore:
    """测试完整评分流程"""

    @patch('core.money_flow_scoring.MoneyFlowScorer.score_margin')
    @patch('core.money_flow_scoring.MoneyFlowScorer.score_net_flow')
    @patch('core.money_flow_scoring.MoneyFlowScorer.score_main_flow')
    @patch('core.money_flow_scoring.MoneyFlowScorer._load_margin_detail')
    @patch('core.money_flow_scoring.MoneyFlowScorer._load_money_flow')
    def test_score_complete(self, mock_load_money, mock_load_margin, mock_score_main,
                            mock_score_net, mock_score_margin):
        """测试完整评分流程"""
        mock_load_money.return_value = pd.DataFrame()
        mock_load_margin.return_value = pd.DataFrame()

        mock_score_main.return_value = (35, ["主力流入"])
        mock_score_net.return_value = (25, ["净流入"])
        mock_score_margin.return_value = (20, ["融资增加"])

        scorer = MoneyFlowScorer()
        result = scorer.score("000001")

        assert result.total_score == 80  # 35 + 25 + 20
        assert result.main_flow_score == 35
        assert result.net_flow_score == 25
        assert result.margin_score == 20
        assert len(result.reasons) == 3
        assert len(result.risk_factors) == 0

    @patch('core.money_flow_scoring.MoneyFlowScorer.score_margin')
    @patch('core.money_flow_scoring.MoneyFlowScorer.score_net_flow')
    @patch('core.money_flow_scoring.MoneyFlowScorer.score_main_flow')
    @patch('core.money_flow_scoring.MoneyFlowScorer._load_margin_detail')
    @patch('core.money_flow_scoring.MoneyFlowScorer._load_money_flow')
    def test_score_with_risks(self, mock_load_money, mock_load_margin, mock_score_main,
                                mock_score_net, mock_score_margin):
        """测试包含风险因素"""
        mock_load_money.return_value = pd.DataFrame()
        mock_load_margin.return_value = pd.DataFrame()

        mock_score_main.return_value = (5, ["主力流出"])
        mock_score_net.return_value = (5, ["净流出"])
        mock_score_margin.return_value = (10, ["融资下降"])

        scorer = MoneyFlowScorer()
        result = scorer.score("000001")

        assert result.main_flow_score == 5
        assert result.net_flow_score == 5
        assert result.margin_score == 10
        assert "主力资金流出" in result.risk_factors
        assert "资金净流出" in result.risk_factors
        assert "融资余额下降" in result.risk_factors

    @patch('core.money_flow_scoring.MoneyFlowScorer.score_margin')
    @patch('core.money_flow_scoring.MoneyFlowScorer.score_net_flow')
    @patch('core.money_flow_scoring.MoneyFlowScorer.score_main_flow')
    @patch('core.money_flow_scoring.MoneyFlowScorer._load_margin_detail')
    @patch('core.money_flow_scoring.MoneyFlowScorer._load_money_flow')
    def test_score_partial_risks(self, mock_load_money, mock_load_margin, mock_score_main,
                                   mock_score_net, mock_score_margin):
        """测试部分风险因素"""
        mock_load_money.return_value = pd.DataFrame()
        mock_load_margin.return_value = pd.DataFrame()

        mock_score_main.return_value = (35, ["主力流入"])
        mock_score_net.return_value = (5, ["净流出"])
        mock_score_margin.return_value = (20, ["融资增加"])

        scorer = MoneyFlowScorer()
        result = scorer.score("000001")

        assert "主力资金流出" not in result.risk_factors
        assert "资金净流出" in result.risk_factors
        assert "融资余额下降" not in result.risk_factors

    @patch('core.money_flow_scoring.MoneyFlowScorer._load_margin_detail')
    @patch('core.money_flow_scoring.MoneyFlowScorer._load_money_flow')
    def test_score_loads_data(self, mock_load_money, mock_load_margin):
        """测试数据加载调用"""
        mock_load_money.return_value = pd.DataFrame()
        mock_load_margin.return_value = pd.DataFrame()

        scorer = MoneyFlowScorer()
        result = scorer.score("000001")

        mock_load_money.assert_called_once_with("000001")
        mock_load_margin.assert_called_once_with("000001")

    @patch('core.money_flow_scoring.MoneyFlowScorer._load_margin_detail')
    @patch('core.money_flow_scoring.MoneyFlowScorer._load_money_flow')
    def test_score_different_symbols(self, mock_load_money, mock_load_margin):
        """测试不同股票代码"""
        mock_load_money.return_value = pd.DataFrame()
        mock_load_margin.return_value = pd.DataFrame()

        scorer = MoneyFlowScorer()

        for symbol in ["000001", "000002", "600000", "600519"]:
            result = scorer.score(symbol)
            # 验证使用了正确的股票代码
            call_args = mock_load_money.call_args
            assert call_args[0][0] == symbol
            mock_load_money.reset_mock()
            mock_load_margin.reset_mock()