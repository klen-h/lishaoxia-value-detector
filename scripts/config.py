#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大霄价值投资探测器 - 全局配置
"""

import os
from pathlib import Path

# 路径配置
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
MARKET_DIR = DATA_DIR / "market"
STOCKS_DIR = DATA_DIR / "stocks"
INDICATORS_DIR = DATA_DIR / "indicators"
HISTORY_DIR = DATA_DIR / "history"

# 确保目录存在
for d in [MARKET_DIR, STOCKS_DIR, INDICATORS_DIR, HISTORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 牛熊判断阈值（李大霄标准）
MARKET_THRESHOLDS = {
    "hs300_pe": {
        "extreme_bear": 10,      # <10%分位，钻石底
        "bear": 12,              # <25%分位，黄金坑
        "neutral_low": 15,       # 25-50%分位
        "neutral_high": 18,      # 50-75%分位
        "bull": 22,              # >75%分位，偏高
        "extreme_bull": 25       # >90%分位，泡沫
    },
    "risk_premium": {
        "excellent": 5.0,        # >5%，股债性价比极高
        "good": 3.5,             # >3.5%，值得投资
        "fair": 2.0,             # >2%，中性
        "poor": 1.0              # <1%，偏贵
    }
}

# 股票筛选条件
STOCK_FILTERS = {
    "min_market_cap": 50,        # 最小市值50亿
    "max_market_cap": 50000,     # 最大市值5万亿
    "exclude_st": True,          # 排除ST
    "exclude_b": True,           # 排除B股
    "exclude_delisting": True    # 排除退市
}

# 评分权重（五维雷达）
SCORE_WEIGHTS = {
    "value": 0.30,       # 价值（低估值+高股息）
    "quality": 0.25,     # 质量（ROE+稳定性）
    "safety": 0.20,      # 安全（分红+市值）
    "growth": 0.15,      # 成长（业绩增速）
    "momentum": 0.10     # 动量（技术面）
}

# 预警阈值
SIGNAL_THRESHOLDS = {
    "diamond_bottom": {   # 钻石底
        "pe": 8,
        "pb": 1.0,
        "dividend_yield": 5.0,
        "roe": 10
    },
    "gold_pit": {         # 黄金坑
        "pe": 12,
        "pb": 1.5,
        "dividend_yield": 3.0,
        "roe": 12
    },
    "overvalued": {       # 高估减仓
        "pe": 40,
        "pb": 5.0,
        "52w_percentile": 90
    },
    "deterioration": {    # 基本面恶化
        "roe": 5,
        "profit_growth": -30,
        "debt_ratio": 95
    },
    "high_growth": {      # 高成长
        "profit_growth": 50,
        "revenue_growth": 30,
        "pe": 30
    }
}

def get_today_str():
    """获取今日日期字符串"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")

def get_latest_trade_date():
    """获取最近交易日（简化版，实际需判断节假日）"""
    from datetime import datetime, timedelta
    today = datetime.now()
    # 周末回退
    if today.weekday() == 5:  # 周六
        today -= timedelta(days=1)
    elif today.weekday() == 6:  # 周日
        today -= timedelta(days=2)
    return today.strftime("%Y-%m-%d")