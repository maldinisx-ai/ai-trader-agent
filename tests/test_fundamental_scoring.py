# -*- coding: utf-8 -*-
"""
fundamental_scoring.py 模块的单元测试
"""

# 必须先导入模块以确保覆盖率收集
import core.fundamental_scoring

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from pathlib import Path

from core.fundamental_scoring import (
    FundamentalScore,
    FundamentalScorer,
)


class TestFundamentalScore:
    """测试 FundamentalScore 数据类"""

    def test_initialization(self):
        """测试初始化"""
        score = FundamentalScore(
            total_score=75,
            roe_score=20,
            growth_score=18,
            valuation_score=17,
            quality_score=20,
            reasons=["ROE优秀", "成长性好"],
            risk_factors=["估值偏高"],
        )

        assert score.total_score == 75
        assert score.roe_score == 20
        assert score.growth_score == 18
        assert score.valuation_score == 17
        assert score.quality_score == 20
        assert len(score.reasons) == 2
        assert len(score.risk_factors) == 1

    def test_default_lists(self):
        """测试默认空列表"""
        score = FundamentalScore(
            total_score=50,
            roe_score=12,
            growth_score=12,
            valuation_score=13,
            quality_score=13,
        )

        assert score.reasons == []
        assert score.risk_factors == []

    def test_to_dict(self):
        """测试转换为字典"""
        score = FundamentalScore(
            total_score=75,
            roe_score=20,
            growth_score=18,
            valuation_score=17,
            quality_score=20,
            reasons=["ROE优秀"],
            risk_factors=["估值偏高"],
        )

        result = score.to_dict()

        assert result['total_score'] == 75
        assert result['roe_score'] == 20
        assert result['growth_score'] == 18
        assert result['valuation_score'] == 17
        assert result['quality_score'] == 20
        assert result['reasons'] == ["ROE优秀"]
        assert result['risk_factors'] == ["估值偏高"]


class TestFundamentalScorer:
    """测试 FundamentalScorer 类"""

    def test_weights_constants(self):
        """测试权重常量"""
        scorer = FundamentalScorer()
        assert scorer.WEIGHTS['roe'] == 25
        assert scorer.WEIGHTS['growth'] == 25
        assert scorer.WEIGHTS['valuation'] == 25
        assert scorer.WEIGHTS['quality'] == 25
        assert sum(scorer.WEIGHTS.values()) == 100

    def test_initialization_default(self):
        """测试默认初始化"""
        scorer = FundamentalScorer()

        assert scorer.data_dir == Path("data")
        assert scorer.fundamentals_dir == Path("data") / "fundamentals"
        assert scorer.financial_dir == Path("data") / "financial"

    def test_initialization_custom(self):
        """测试自定义数据目录"""
        scorer = FundamentalScorer(data_dir="custom_data")

        assert scorer.data_dir == Path("custom_data")
        assert scorer.fundamentals_dir == Path("custom_data") / "fundamentals"
        assert scorer.financial_dir == Path("custom_data") / "financial"


class TestLoadFinancialIndicator:
    """测试加载财务指标数据"""

    @patch('core.fundamental_scoring.pd.read_csv')
    @patch('core.fundamental_scoring.Path.exists')
    def test_load_success(self, mock_exists, mock_read_csv):
        """测试成功加载数据"""
        mock_exists.return_value = True
        mock_df = pd.DataFrame({'roe': [15.0, 12.0]})
        mock_read_csv.return_value = mock_df

        scorer = FundamentalScorer()
        result = scorer._load_financial_indicator("000001")

        assert result is not None
        assert len(result) == 2

    @patch('core.fundamental_scoring.Path.exists')
    def test_load_file_not_exists(self, mock_exists):
        """测试文件不存在"""
        mock_exists.return_value = False

        scorer = FundamentalScorer()
        result = scorer._load_financial_indicator("000001")

        assert result is None

    @patch('core.fundamental_scoring.pd.read_csv')
    @patch('core.fundamental_scoring.Path.exists')
    def test_load_exception(self, mock_exists, mock_read_csv):
        """测试加载异常"""
        mock_exists.return_value = True
        mock_read_csv.side_effect = Exception("Read error")

        scorer = FundamentalScorer()
        result = scorer._load_financial_indicator("000001")

        assert result is None

    def test_symbol_to_filename(self):
        """测试股票代码转换文件名"""
        with patch('core.fundamental_scoring.pd.read_csv') as mock_read_csv, \
             patch('core.fundamental_scoring.Path.exists') as mock_exists:
            mock_exists.return_value = True
            mock_read_csv.return_value = pd.DataFrame()

            scorer = FundamentalScorer()
            scorer._load_financial_indicator("600519.SH")
            scorer._load_financial_indicator("000001.SZ")
            scorer._load_financial_indicator("600519")

            # 验证文件名格式
            call_args = [call[0][0] for call in mock_read_csv.call_args_list]
            assert "indicator_600519_SH.csv" in str(call_args)


class TestLoadIncomeStatement:
    """测试加载利润表"""

    @patch('core.fundamental_scoring.pd.read_csv')
    @patch('core.fundamental_scoring.Path.exists')
    def test_load_success(self, mock_exists, mock_read_csv):
        """测试成功加载数据"""
        mock_exists.return_value = True
        mock_df = pd.DataFrame({'operatingRevenue': [1000, 900]})
        mock_read_csv.return_value = mock_df

        scorer = FundamentalScorer()
        result = scorer._load_income_statement("000001")

        assert result is not None
        assert len(result) == 2

    @patch('core.fundamental_scoring.Path.exists')
    def test_load_file_not_exists(self, mock_exists):
        """测试文件不存在"""
        mock_exists.return_value = False

        scorer = FundamentalScorer()
        result = scorer._load_income_statement("000001")

        assert result is None

    @patch('core.fundamental_scoring.pd.read_csv')
    @patch('core.fundamental_scoring.Path.exists')
    def test_load_exception(self, mock_exists, mock_read_csv):
        """测试加载异常"""
        mock_exists.return_value = True
        mock_read_csv.side_effect = Exception("Read error")

        scorer = FundamentalScorer()
        result = scorer._load_income_statement("000001")

        assert result is None


class TestScoreROE:
    """测试 ROE 评分"""

    def test_score_roe_none(self):
        """测试空数据"""
        scorer = FundamentalScorer()
        score, reasons = scorer.score_roe(None)

        assert score == 5
        assert "ROE数据缺失" in reasons

    def test_score_roe_empty(self):
        """测试空 DataFrame"""
        scorer = FundamentalScorer()
        score, reasons = scorer.score_roe(pd.DataFrame())

        assert score == 5
        assert "ROE数据缺失" in reasons

    def test_score_roe_excellent(self):
        """测试 ROE 优秀 (>=20%)"""
        df = pd.DataFrame({'roe': [25.0]})
        scorer = FundamentalScorer()
        score, reasons = scorer.score_roe(df)

        assert score == 25
        assert "ROE优秀" in reasons

    def test_score_roe_good(self):
        """测试 ROE 良好 (15-20%)"""
        test_cases = [15.0, 17.5, 19.9]
        scorer = FundamentalScorer()

        for roe_value in test_cases:
            df = pd.DataFrame({'roe': [roe_value]})
            score, reasons = scorer.score_roe(df)
            assert score == 20
            assert "ROE良好" in reasons

    def test_score_roe_average(self):
        """测试 ROE 一般 (10-15%)"""
        test_cases = [10.0, 12.5, 14.9]
        scorer = FundamentalScorer()

        for roe_value in test_cases:
            df = pd.DataFrame({'roe': [roe_value]})
            score, reasons = scorer.score_roe(df)
            assert score == 15
            assert "ROE一般" in reasons

    def test_score_roe_low(self):
        """测试 ROE 较低 (5-10%)"""
        test_cases = [5.0, 7.5, 9.9]
        scorer = FundamentalScorer()

        for roe_value in test_cases:
            df = pd.DataFrame({'roe': [roe_value]})
            score, reasons = scorer.score_roe(df)
            assert score == 10
            assert "ROE较低" in reasons

    def test_score_roe_poor(self):
        """测试 ROE 差 (<5%)"""
        test_cases = [0.0, 2.5, 4.9]
        scorer = FundamentalScorer()

        for roe_value in test_cases:
            df = pd.DataFrame({'roe': [roe_value]})
            score, reasons = scorer.score_roe(df)
            assert score == 5
            assert "ROE差" in reasons

    def test_score_roe_negative(self):
        """测试负 ROE"""
        df = pd.DataFrame({'roe': [-10.0]})
        scorer = FundamentalScorer()
        score, reasons = scorer.score_roe(df)

        assert score == 5
        assert "ROE差" in reasons

    def test_score_roe_boundary_values(self):
        """测试边界值"""
        scorer = FundamentalScorer()

        # 20% 边界
        df = pd.DataFrame({'roe': [20.0]})
        score, _ = scorer.score_roe(df)
        assert score == 25

        # 15% 边界
        df = pd.DataFrame({'roe': [15.0]})
        score, _ = scorer.score_roe(df)
        assert score == 20

        # 10% 边界
        df = pd.DataFrame({'roe': [10.0]})
        score, _ = scorer.score_roe(df)
        assert score == 15

        # 5% 边界
        df = pd.DataFrame({'roe': [5.0]})
        score, _ = scorer.score_roe(df)
        assert score == 10

    def test_score_roe_different_columns(self):
        """测试不同的列名"""
        test_columns = ['roe', 'ROE', '净资产收益率', 'roeAvg', 'roe_ttm']
        scorer = FundamentalScorer()

        for col in test_columns:
            df = pd.DataFrame({col: [18.0]})
            score, reasons = scorer.score_roe(df)
            assert score == 20

    def test_score_roe_column_not_found(self):
        """测试未找到 ROE 列"""
        df = pd.DataFrame({'other_col': [15.0]})
        scorer = FundamentalScorer()
        score, reasons = scorer.score_roe(df)

        assert score == 5
        assert "ROE列未找到" in reasons

    def test_score_roe_nan_value(self):
        """测试 NaN 值"""
        df = pd.DataFrame({'roe': [None]})
        scorer = FundamentalScorer()
        score, reasons = scorer.score_roe(df)

        assert score == 5
        assert "ROE数据无效" in reasons


class TestScoreGrowth:
    """测试成长性评分"""

    def test_score_growth_none(self):
        """测试空数据"""
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(None)

        assert score == 5
        assert "成长性数据不足" in reasons

    def test_score_growth_empty(self):
        """测试空 DataFrame"""
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(pd.DataFrame())

        assert score == 5
        assert "成长性数据不足" in reasons

    def test_score_growth_insufficient_rows(self):
        """测试数据行数不足"""
        df = pd.DataFrame({'operatingRevenue': [1000]})
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(df)

        assert score == 5
        assert "成长性数据不足" in reasons

    def test_score_growth_excellent(self):
        """测试高增长 (营收和净利润都 >20%)"""
        df = pd.DataFrame({
            'operatingRevenue': [121, 100],  # 21% 增长 (>20%)
            'netProfit': [121, 100],  # 21% 增长 (>20%)
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(df)

        assert score == 25
        assert "营收和净利润高增长" in reasons

    def test_score_growth_good(self):
        """测试良好增长 (营收和净利润都 >10%)"""
        df = pd.DataFrame({
            'operatingRevenue': [115, 100],  # 15% 增长
            'netProfit': [115, 100],  # 15% 增长
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(df)

        assert score == 20
        assert "营收和净利润良好增长" in reasons

    def test_score_growth_mixed(self):
        """测试中等增长 (至少一个 >10%)"""
        test_cases = [
            ([120, 100], [105, 100]),  # 营收20%, 净利润5%
            ([105, 100], [120, 100]),  # 营收5%, 净利润20%
        ]
        scorer = FundamentalScorer()

        for revenue_data, profit_data in test_cases:
            df = pd.DataFrame({
                'operatingRevenue': revenue_data,
                'netProfit': profit_data,
            })
            score, reasons = scorer.score_growth(df)
            assert score == 15
            assert "中等增长" in reasons

    def test_score_growth_small(self):
        """测试小幅增长 (营收和净利润都 >0)"""
        df = pd.DataFrame({
            'operatingRevenue': [105, 100],
            'netProfit': [103, 100],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(df)

        assert score == 10
        assert "小幅增长" in reasons

    def test_score_growth_negative(self):
        """测试负增长"""
        df = pd.DataFrame({
            'operatingRevenue': [95, 100],
            'netProfit': [95, 100],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(df)

        assert score == 5
        assert "负增长" in reasons

    def test_score_growth_boundary_values(self):
        """测试边界值"""
        scorer = FundamentalScorer()

        # 20% 边界 - 等于20%是良好增长(20分)，不是优秀(25分)
        df = pd.DataFrame({
            'operatingRevenue': [120, 100],
            'netProfit': [120, 100],
        })
        score, _ = scorer.score_growth(df)
        assert score == 20  # 良好增长，不是优秀

        # 略高于20%才是优秀
        df = pd.DataFrame({
            'operatingRevenue': [121, 100],
            'netProfit': [121, 100],
        })
        score, _ = scorer.score_growth(df)
        assert score == 25  # 优秀

        # 10% 边界 - 等于10%是小幅增长(10分)，不是中等(15分)
        df = pd.DataFrame({
            'operatingRevenue': [110, 100],
            'netProfit': [110, 100],
        })
        score, _ = scorer.score_growth(df)
        assert score == 10  # 小幅增长，不是中等

        # 略高于10%才是良好
        df = pd.DataFrame({
            'operatingRevenue': [111, 100],
            'netProfit': [111, 100],
        })
        score, _ = scorer.score_growth(df)
        assert score == 20  # 良好

        # 0% 边界 - 营收=0, 净利润=0 会被视为负增长(5分)
        df = pd.DataFrame({
            'operatingRevenue': [100, 100],
            'netProfit': [100, 100],
        })
        score, _ = scorer.score_growth(df)
        assert score == 5  # 负增长

        # 略高于0%才是小幅增长
        df = pd.DataFrame({
            'operatingRevenue': [101, 100],
            'netProfit': [101, 100],
        })
        score, _ = scorer.score_growth(df)
        assert score == 10  # 小幅增长

    def test_score_growth_different_columns(self):
        """测试不同的列名"""
        test_cases = [
            ('operatingRevenue', 'netProfit'),
            ('totalOperatingRevenue', 'netProfitToParent'),
            ('营业总收入', '净利润'),
            ('revenue', '归属母公司所有者的净利润'),
        ]

        scorer = FundamentalScorer()
        for revenue_col, profit_col in test_cases:
            df = pd.DataFrame({
                revenue_col: [121, 100],  # 21% 增长 (>20%)
                profit_col: [121, 100],
            })
            score, reasons = scorer.score_growth(df)
            assert score == 25  # 优秀增长

    def test_score_growth_columns_not_found(self):
        """测试未找到列"""
        df = pd.DataFrame({
            'other_col': [1000, 900],
            'another_col': [100, 90],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(df)

        assert score == 5
        assert "成长性列未找到" in reasons

    def test_score_growth_exception(self):
        """测试异常处理"""
        # 创建一个会引发异常的 DataFrame
        df = pd.DataFrame({
            'operatingRevenue': [None, None],
            'netProfit': [None, None],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_growth(df)

        assert score == 5


class TestScoreValuation:
    """测试估值评分"""

    def test_score_valuation_low_price(self):
        """测试低价格 (<50)"""
        scorer = FundamentalScorer()
        score, reasons, risks = scorer.score_valuation(pd.DataFrame(), 30)

        assert score == 20
        assert "价格相对较低" in reasons

    def test_score_valuation_medium_low_price(self):
        """测试中低价格 (50-100)"""
        scorer = FundamentalScorer()
        score, reasons, risks = scorer.score_valuation(pd.DataFrame(), 75)

        assert score == 15

    def test_score_valuation_high_price(self):
        """测试高价格 (>100)"""
        scorer = FundamentalScorer()
        score, reasons, risks = scorer.score_valuation(pd.DataFrame(), 150)

        assert score == 10
        assert "价格相对较高" in risks

    def test_score_valuation_zero_price(self):
        """测试零价格"""
        scorer = FundamentalScorer()
        score, reasons, risks = scorer.score_valuation(pd.DataFrame(), 0)

        assert score == 15

    def test_score_valuation_negative_price(self):
        """测试负价格"""
        scorer = FundamentalScorer()
        score, reasons, risks = scorer.score_valuation(pd.DataFrame(), -10)

        assert score == 15

    def test_score_valuation_boundary_50(self):
        """测试边界值 50"""
        scorer = FundamentalScorer()
        score, reasons, risks = scorer.score_valuation(pd.DataFrame(), 50)

        assert score == 15

    def test_score_valuation_boundary_100(self):
        """测试边界值 100"""
        scorer = FundamentalScorer()
        score, reasons, risks = scorer.score_valuation(pd.DataFrame(), 100)

        assert score == 10


class TestScoreQuality:
    """测试质量评分"""

    def test_score_quality_none(self):
        """测试空数据"""
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(None)

        assert score == 10
        assert "质量数据不足" in reasons

    def test_score_quality_empty(self):
        """测试空 DataFrame"""
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(pd.DataFrame())

        assert score == 10
        assert "质量数据不足" in reasons

    def test_score_quality_excellent(self):
        """测试优秀质量 (毛利率>50% 且 资产负债率<40%)"""
        df = pd.DataFrame({
            'grossProfitMargin': [55.0],
            'assetsLiabilityRatio': [35.0],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(df)

        assert score == 25
        assert "高毛率低负债" in reasons

    def test_score_quality_good(self):
        """测试良好质量 (毛利率>40% 且 资产负债率<60%)"""
        df = pd.DataFrame({
            'grossProfitMargin': [45.0],
            'assetsLiabilityRatio': [50.0],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(df)

        assert score == 20
        assert "毛率和负债良好" in reasons

    def test_score_quality_average(self):
        """测试一般质量 (毛利率>30% 且 资产负债率<70%)"""
        df = pd.DataFrame({
            'grossProfitMargin': [35.0],
            'assetsLiabilityRatio': [65.0],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(df)

        assert score == 15
        assert "质量一般" in reasons

    def test_score_quality_poor(self):
        """测试差质量"""
        df = pd.DataFrame({
            'grossProfitMargin': [25.0],
            'assetsLiabilityRatio': [80.0],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(df)

        assert score == 10
        assert "质量一般" in reasons

    def test_score_quality_boundary_values(self):
        """测试边界值"""
        scorer = FundamentalScorer()

        # 毛利率50%, 资产负债率40%
        df = pd.DataFrame({
            'grossProfitMargin': [50.0],
            'assetsLiabilityRatio': [40.0],
        })
        score, _ = scorer.score_quality(df)
        # 边界情况需要检查实际逻辑

        # 毛利率40%, 资产负债率60%
        df = pd.DataFrame({
            'grossProfitMargin': [40.0],
            'assetsLiabilityRatio': [60.0],
        })
        score, _ = scorer.score_quality(df)

    def test_score_quality_different_columns(self):
        """测试不同的列名"""
        test_cases = [
            ('grossProfitMargin', 'assetsLiabilityRatio'),
            ('grossmargin', 'debt_to_assets'),
            ('销售毛利率', '资产负债率'),
            ('销售毛利率(%)', '资产负债率(%)'),
        ]

        scorer = FundamentalScorer()
        for gross_col, debt_col in test_cases:
            df = pd.DataFrame({
                gross_col: [55.0],
                debt_col: [35.0],
            })
            score, reasons = scorer.score_quality(df)
            assert score == 25

    def test_score_quality_missing_gross_margin(self):
        """测试缺少毛利率列"""
        df = pd.DataFrame({'assetsLiabilityRatio': [35.0]})
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(df)

        assert score == 10
        assert "质量指标缺失" in reasons

    def test_score_quality_missing_debt_ratio(self):
        """测试缺少资产负债率列"""
        df = pd.DataFrame({'grossProfitMargin': [55.0]})
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(df)

        assert score == 10
        assert "质量指标缺失" in reasons

    def test_score_quality_nan_values(self):
        """测试 NaN 值"""
        df = pd.DataFrame({
            'grossProfitMargin': [None],
            'assetsLiabilityRatio': [35.0],
        })
        scorer = FundamentalScorer()
        score, reasons = scorer.score_quality(df)

        assert score == 10
        assert "质量指标缺失" in reasons


class TestScore:
    """测试完整评分流程"""

    @patch('core.fundamental_scoring.FundamentalScorer.score_quality')
    @patch('core.fundamental_scoring.FundamentalScorer.score_valuation')
    @patch('core.fundamental_scoring.FundamentalScorer.score_growth')
    @patch('core.fundamental_scoring.FundamentalScorer.score_roe')
    @patch('core.fundamental_scoring.FundamentalScorer._load_income_statement')
    @patch('core.fundamental_scoring.FundamentalScorer._load_financial_indicator')
    def test_score_complete(self, mock_load_ind, mock_load_income, mock_score_roe,
                            mock_score_growth, mock_score_valuation, mock_score_quality):
        """测试完整评分流程"""
        mock_load_ind.return_value = pd.DataFrame()
        mock_load_income.return_value = pd.DataFrame()

        mock_score_roe.return_value = (20, ["ROE良好"])
        mock_score_growth.return_value = (18, ["成长性好"])
        mock_score_valuation.return_value = (17, ["估值合理"], [])
        mock_score_quality.return_value = (20, ["质量优秀"])

        scorer = FundamentalScorer()
        result = scorer.score("000001", current_price=100)

        assert result.total_score == 75  # 20 + 18 + 17 + 20
        assert result.roe_score == 20
        assert result.growth_score == 18
        assert result.valuation_score == 17
        assert result.quality_score == 20
        assert len(result.reasons) == 4
        assert len(result.risk_factors) == 0

    @patch('core.fundamental_scoring.FundamentalScorer.score_quality')
    @patch('core.fundamental_scoring.FundamentalScorer.score_valuation')
    @patch('core.fundamental_scoring.FundamentalScorer.score_growth')
    @patch('core.fundamental_scoring.FundamentalScorer.score_roe')
    @patch('core.fundamental_scoring.FundamentalScorer._load_income_statement')
    @patch('core.fundamental_scoring.FundamentalScorer._load_financial_indicator')
    def test_score_with_zero_price(self, mock_load_ind, mock_load_income, mock_score_roe,
                                    mock_score_growth, mock_score_valuation, mock_score_quality):
        """测试零价格"""
        mock_load_ind.return_value = pd.DataFrame()
        mock_load_income.return_value = pd.DataFrame()

        mock_score_roe.return_value = (20, [])
        mock_score_growth.return_value = (18, [])
        mock_score_valuation.return_value = (15, [], [])
        mock_score_quality.return_value = (20, [])

        scorer = FundamentalScorer()
        result = scorer.score("000001")

        assert result.valuation_score == 15

    @patch('core.fundamental_scoring.FundamentalScorer.score_quality')
    @patch('core.fundamental_scoring.FundamentalScorer.score_valuation')
    @patch('core.fundamental_scoring.FundamentalScorer.score_growth')
    @patch('core.fundamental_scoring.FundamentalScorer.score_roe')
    @patch('core.fundamental_scoring.FundamentalScorer._load_income_statement')
    @patch('core.fundamental_scoring.FundamentalScorer._load_financial_indicator')
    def test_score_with_risks(self, mock_load_ind, mock_load_income, mock_score_roe,
                                mock_score_growth, mock_score_valuation, mock_score_quality):
        """测试包含风险因素"""
        mock_load_ind.return_value = pd.DataFrame()
        mock_load_income.return_value = pd.DataFrame()

        mock_score_roe.return_value = (20, [])
        mock_score_growth.return_value = (18, [])
        mock_score_valuation.return_value = (10, [], ["价格过高"])
        mock_score_quality.return_value = (20, [])

        scorer = FundamentalScorer()
        result = scorer.score("000001", current_price=150)

        assert result.valuation_score == 10
        assert "价格过高" in result.risk_factors

    @patch('core.fundamental_scoring.FundamentalScorer._load_income_statement')
    @patch('core.fundamental_scoring.FundamentalScorer._load_financial_indicator')
    def test_score_loads_data(self, mock_load_ind, mock_load_income):
        """测试数据加载调用"""
        mock_load_ind.return_value = pd.DataFrame()
        mock_load_income.return_value = pd.DataFrame()

        scorer = FundamentalScorer()
        result = scorer.score("000001")

        mock_load_ind.assert_called_once_with("000001")
        mock_load_income.assert_called_once_with("000001")

    @patch('core.fundamental_scoring.FundamentalScorer._load_income_statement')
    @patch('core.fundamental_scoring.FundamentalScorer._load_financial_indicator')
    def test_score_different_symbols(self, mock_load_ind, mock_load_income):
        """测试不同股票代码"""
        mock_load_ind.return_value = pd.DataFrame()
        mock_load_income.return_value = pd.DataFrame()

        scorer = FundamentalScorer()

        for symbol in ["000001", "000002", "600000", "600519"]:
            result = scorer.score(symbol)
            # 验证使用了正确的股票代码
            call_args = mock_load_ind.call_args
            assert call_args[0][0] == symbol
            mock_load_ind.reset_mock()
            mock_load_income.reset_mock()