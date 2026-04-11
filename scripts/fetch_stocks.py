#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取个股数据 (AKShare 深度优化版)
解决 Tushare 积分不足及 GitHub Actions 网络封锁问题
"""

import json
import pandas as pd
import akshare as ak
import os
import time
import random
from datetime import datetime
from config import STOCKS_DIR, STOCK_FILTERS, SCORE_WEIGHTS, get_today_str

def fetch_all_quotes(retries=3):
    """第一步：获取全市场实时行情概览 (使用 AKShare)"""
    print("正在获取全市场实时行情初筛...")
    for i in range(retries):
        try:
            df = ak.stock_zh_a_spot_em()
            # 预清洗：重命名列并转换类型
            df = df[['代码', '名称', '最新价', '涨跌幅', '市盈率-动态', '市净率', '总市值', '流通市值']]
            df.columns = ['code', 'name', 'price', 'change_pct', 'pe', 'pb', 'total_mv', 'circ_mv']
            
            # 排除 ST 和 B 股
            df = df[~df['name'].str.contains('ST|退', na=False)]
            df = df[~df['code'].str.startswith(('2', '9'))]
            
            # 转换数值类型，处理异常
            for col in ['price', 'pe', 'pb', 'total_mv', 'circ_mv']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 初步过滤：放宽 PE/PB 限制，确保能筛选出足够的候选股
        # PE 放宽到 60，PB 放宽到 6，市值放宽到 30 亿
        mask = (df['pe'] > 0) & (df['pe'] < 60) & (df['pb'] > 0) & (df['pb'] < 6) & (df['total_mv'] > 30 * 1e8)
        df_filtered = df[mask].copy()
            
            print(f"全市场 {len(df)} 只标的，初筛出 {len(df_filtered)} 只价值候选股")
            return df_filtered
        except Exception as e:
            print(f"获取全市场行情第 {i+1} 次尝试失败: {e}")
            if i < retries - 1:
                time.sleep(2)
            continue
    return pd.DataFrame()

def fetch_deep_fundamentals(code):
    """第二步：针对候选股抓取深度指标 (按需请求)"""
    try:
        # 添加随机延迟，模拟真人操作，防止被封 IP
        time.sleep(random.uniform(0.5, 1.5)) 
        # 获取主要财务指标
        fin_df = ak.stock_financial_analysis_indicator(symbol=code)
        if fin_df is None or fin_df.empty: return None
        
        latest = fin_df.iloc[0]
        return {
            "roe": float(latest['净资产收益率(%)']) if pd.notna(latest['净资产收益率(%)']) else 0,
            "netprofit_growth": float(latest['净利润增长率(%)']) if pd.notna(latest['净利润增长率(%)']) else 0,
            "revenue_growth": float(latest['主营业务收入增长率(%)']) if pd.notna(latest['主营业务收入增长率(%)']) else 0,
            "debt_ratio": float(latest['资产负债率(%)']) if pd.notna(latest['资产负债率(%)']) else 0
        }
    except Exception as e:
        print(f"抓取 {code} 深度数据失败: {e}")
        return None

def calculate_scores(row, fund):
    """计算五维雷达评分"""
    scores = {
        "value": 0,    # 价值
        "quality": 0,  # 质量
        "safety": 0,   # 安全
        "growth": 0,   # 成长
        "momentum": 0  # 动量
    }
    
    # 1. 价值分 (PE, PB)
    pe = row['pe']
    pb = row['pb']
    if 0 < pe < 10: scores['value'] = 100
    elif pe < 15: scores['value'] = 85
    elif pe < 20: scores['value'] = 70
    elif pe < 30: scores['value'] = 50
    else: scores['value'] = 30
    
    # 2. 质量分 (ROE)
    roe = fund.get('roe', 0)
    if roe > 20: scores['quality'] = 100
    elif roe > 15: scores['quality'] = 85
    elif roe > 10: scores['quality'] = 70
    elif roe > 5: scores['quality'] = 50
    else: scores['quality'] = 30
    
    # 3. 安全分 (市值 + 负债率)
    mv_score = min(100, (row['total_mv'] / 1e11) * 20 + 40) # 越大越安全
    debt = fund.get('debt_ratio', 100)
    debt_score = max(0, 100 - debt)
    scores['safety'] = mv_score * 0.6 + debt_score * 0.4
    
    # 4. 成长分 (净利增长 + 营收增长)
    p_growth = fund.get('netprofit_growth', 0)
    r_growth = fund.get('revenue_growth', 0)
    growth_val = (p_growth + r_growth) / 2
    if growth_val > 50: scores['growth'] = 100
    elif growth_val > 30: scores['growth'] = 85
    elif growth_val > 15: scores['growth'] = 70
    elif growth_val > 0: scores['growth'] = 50
    else: scores['growth'] = 20
    
    # 5. 动量分 (涨跌幅)
    change = row['change_pct']
    scores['momentum'] = min(100, max(0, 50 + change * 5))
    
    return scores

def main():
    print("=" * 50)
    print("开始获取个股数据 (AKShare 深度优化版)...")
    print("=" * 50)
    
    # 1. 获取全市场初筛数据
    candidates = fetch_all_quotes()
    if candidates.empty:
        print("未能获取到初筛数据，任务中止")
        return

    today = get_today_str()
    data = {}
    
    # 先将所有初筛通过的股票（1165只）放入数据池，即使没有深度财务数据
    print(f"正在将 {len(candidates)} 只初筛标的存入基础池...")
    for _, row in candidates.iterrows():
        code = row['code']
        # 初始评分（仅基于 PE/PB/市值/动量）
        # 给一个基础的 fund 对象，让计算不报错
        dummy_fund = {"roe": 5, "netprofit_growth": 0, "revenue_growth": 0, "debt_ratio": 50}
        scores = calculate_scores(row, dummy_fund)
        overall = sum(scores[k] * SCORE_WEIGHTS[k] for k in scores)
        
        data[code] = {
            "code": code,
            "name": row['name'],
            "price": float(row['price']),
            "pe": float(row['pe']),
            "pb": float(row['pb']),
            "roe": 0, # 深度扫描前默认为 0
            "profit_growth": 0,
            "revenue_growth": 0,
            "debt_ratio": 0,
            "market_cap": round(row['total_mv'] / 1e8, 2),
            "scores": {k: round(v, 1) for k, v in scores.items()},
            "overall_score": round(overall, 1),
            "update_time": datetime.now().isoformat(),
            "is_deep_scanned": False
        }

    # 2. 排序并选择前 150 名（进行深度分析，更新 ROE 等数据）
    # 排序逻辑：优先 PE * PB 小且市值大的（蓝筹/银行）
    candidates['val_index'] = candidates['pe'] * candidates['pb']
    top_picks = candidates.sort_values(['val_index', 'total_mv'], ascending=[True, False]).head(150).copy()
    
    print(f"开始深度分析前 {len(top_picks)} 只潜力股 (重点挖掘银行/蓝筹)...")
    
    for i, (_, row) in enumerate(top_picks.iterrows()):
        code = row['code']
        if i % 10 == 0:
            print(f"进度: {i}/{len(top_picks)}...")
            
        fund = fetch_deep_fundamentals(code)
        if not fund:
            continue
            
        # 使用真实财务数据重新计算评分
        scores = calculate_scores(row, fund)
        overall = sum(scores[k] * SCORE_WEIGHTS[k] for k in scores)
        
        data[code].update({
            "roe": round(fund['roe'], 2),
            "profit_growth": round(fund['netprofit_growth'], 2),
            "revenue_growth": round(fund['revenue_growth'], 2),
            "debt_ratio": round(fund['debt_ratio'], 2),
            "scores": {k: round(v, 1) for k, v in scores.items()},
            "overall_score": round(overall, 1),
            "is_deep_scanned": True
        })

    # 保存结果
    output_file = STOCKS_DIR / f"{today}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 同步更新 latest.json
    latest_link = STOCKS_DIR / "latest.json"
    with open(latest_link, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 完成！深度扫描了 {len(data)} 只优质股票")
    print(f"   结果已保存至: {output_file}")

if __name__ == '__main__':
    main()
