#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数集合
"""

import json
import os
from datetime import datetime, timedelta

def save_json(data, filepath, indent=2):
    """安全保存JSON"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)

def load_json(filepath, default=None):
    """安全加载JSON"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default

def format_money(num):
    """格式化金额"""
    if num >= 1e8:
        return f"{num/1e8:.2f}亿"
    elif num >= 1e4:
        return f"{num/1e4:.2f}万"
    return f"{num:.2f}"

def format_percent(num):
    """格式化百分比"""
    return f"{num:.2f}%"

def is_trade_date(date=None):
    """判断是否为交易日（简化版）"""
    if date is None:
        date = datetime.now()
    
    # 周末
    if date.weekday() >= 5:
        return False
    
    # 节假日（2026年简化判断，实际需完整日历）
    holidays = [
        "2026-01-01", "2026-01-02", "2026-01-03",  # 元旦
        "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",  # 春节
        "2026-04-04", "2026-04-05", "2026-04-06",  # 清明
        "2026-05-01", "2026-05-02", "2026-05-03",  # 劳动节
        # ... 其他节假日
    ]
    
    return date.strftime("%Y-%m-%d") not in holidays

def get_trade_dates(start, end):
    """获取日期范围内的交易日"""
    dates = []
    current = start
    while current <= end:
        if is_trade_date(current):
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates