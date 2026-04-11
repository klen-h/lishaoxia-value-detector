#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取个股数据 (双榜单版 - 好股票 vs 优质成长)
"""

import json
import pandas as pd
import akshare as ak
import time
import random
from datetime import datetime
from pathlib import Path

# 配置
STOCKS_DIR = Path("data/stocks")
STOCKS_DIR.mkdir(parents=True, exist_ok=True)

# 双评分体系
SCORE_WEIGHTS_BALANCED = {      # 好股票：均衡配置
    "value": 0.25,      # 价值
    "quality": 0.25,    # 质量
    "growth": 0.20,     # 成长（降低）
    "safety": 0.20,     # 安全（提升）
    "momentum": 0.10
}

SCORE_WEIGHTS_GROWTH = {        # 优质成长：进攻配置
    "value": 0.15,      # 价值（降低）
    "quality": 0.25,    # 质量
    "growth": 0.35,     # 成长（大幅提升）
    "safety": 0.15,     # 安全（降低）
    "momentum": 0.10
}

def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def fetch_all_quotes():
    """严格初筛 - 排除垃圾股"""
    print("正在获取全市场实时行情...")
    
    try:
        df = ak.stock_zh_a_spot_em()
        
        # 标准化列名
        df = df.rename(columns={
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'change_pct',
            '市盈率-动态': 'pe',
            '市净率': 'pb',
            '总市值': 'total_mv',
            '流通市值': 'circ_mv'
        })
        
        # 严格排除
        df = df[~df['name'].str.contains('ST|退|\*|N|C', na=False)]
        df = df[~df['code'].str.startswith(('2', '8', '9', '4', '8'))]
        
        for col in ['price', 'pe', 'pb', 'total_mv', 'circ_mv', 'change_pct']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 市值>100亿，PE 5-50，PB 0.5-5
        df = df[df['total_mv'] > 100 * 1e8]
        df = df[(df['pe'] > 5) & (df['pe'] < 50)]
        df = df[(df['pb'] > 0.5) & (df['pb'] < 5)]
        
        print(f"严格过滤后: {len(df)} 只")
        return df
        
    except Exception as e:
        print(f"获取行情失败: {e}")
        return pd.DataFrame()

def fetch_deep_fundamentals(code):
    """获取深度财务数据"""
    try:
        time.sleep(random.uniform(0.2, 0.5))
        
        fin_df = ak.stock_financial_analysis_indicator(symbol=code)
        if fin_df is None or fin_df.empty:
            return None
        
        latest = fin_df.iloc[0]
        
        return {
            "roe": float(latest.get('净资产收益率(%)', 0) or 0),
            "profit_growth": float(latest.get('净利润增长率(%)', 0) or 0),
            "revenue_growth": float(latest.get('主营业务收入增长率(%)', 0) or 0),
            "debt_ratio": float(latest.get('资产负债率(%)', 50) or 50),
            "gross_margin": float(latest.get('销售毛利率(%)', 0) or 0),
            "net_margin": float(latest.get('销售净利率(%)', 0) or 0)
        }
        
    except Exception as e:
        print(f"获取 {code} 财务数据失败: {e}")
        return None

def calculate_dual_scores(row, fund):
    """计算双评分：均衡分 + 成长分"""
    pe = row.get('pe', 999)
    pb = row.get('pb', 999)
    mv = row.get('total_mv', 0)
    
    # 基础五维分（0-100）
    # 1. 价值分
    if 10 <= pe <= 20: value = 100
    elif 8 <= pe < 10: value = 90
    elif 20 < pe <= 25: value = 85
    elif 5 <= pe < 8: value = 70
    elif 25 < pe <= 35: value = 70
    elif 35 < pe <= 50: value = 55
    else: value = 40
    
    if 1 <= pb <= 2: value += 10
    elif pb > 3: value -= 10
    value = max(0, min(100, value))
    
    # 2. 质量分（ROE）
    roe = fund.get('roe', 0)
    if roe >= 20: quality = 100
    elif roe >= 15: quality = 90
    elif roe >= 12: quality = 80
    elif roe >= 10: quality = 70
    elif roe >= 8: quality = 55
    else: quality = max(0, roe * 6)
    
    # 3. 成长分（核心差异点）
    p_g = fund.get('profit_growth', 0)
    r_g = fund.get('revenue_growth', 0)
    
    # 双增长验证（防财务调节）
    if p_g > 30 and r_g > 20: growth = 100      # 高成长
    elif p_g > 20 and r_g > 10: growth = 90     # 稳健成长
    elif p_g > 15 and r_g > 5: growth = 80      # 中速成长
    elif p_g > 10: growth = 70                   # 慢成长
    elif p_g > 0: growth = 55                    # 正增长
    elif p_g > -10: growth = 40                  # 轻微下滑
    else: growth = max(0, 20 + p_g)              # 大幅下滑
    
    # 毛利率加成（质量验证）
    gross = fund.get('gross_margin', 0)
    if gross > 40: growth += 5
    
    growth = min(100, growth)
    
    # 4. 安全分
    mv_score = 60 if mv > 500e8 else (mv / 500e8) * 60 + 40
    debt = fund.get('debt_ratio', 50)
    debt_score = max(0, 100 - debt)
    safety = mv_score * 0.5 + debt_score * 0.5
    
    # 5. 动量分
    change = row.get('change_pct', 0)
    if -3 <= change <= 5: momentum = 80
    elif -5 <= change < -3: momentum = 90
    elif 5 < change <= 10: momentum = 65
    elif change > 10: momentum = 45
    else: momentum = 50
    
    scores = {
        "value": round(value, 1),
        "quality": round(quality, 1),
        "growth": round(growth, 1),
        "safety": round(safety, 1),
        "momentum": round(momentum, 1)
    }
    
    # 计算双总分
    score_balanced = sum(scores[k] * SCORE_WEIGHTS_BALANCED[k] for k in scores)
    score_growth = sum(scores[k] * SCORE_WEIGHTS_GROWTH[k] for k in scores)
    
    return scores, round(score_balanced, 1), round(score_growth, 1)

def classify_stock(scores, fund, score_balanced, score_growth):
    """双标签分类"""
    tags = []
    
    # 好股票标签（基于均衡分）
    if score_balanced >= 80:
        tags.append("好股票")
    if scores['value'] >= 80 and scores['safety'] >= 70:
        tags.append("价值蓝筹")
    if fund.get('roe', 0) >= 15 and scores['safety'] >= 70:
        tags.append("白马蓝筹")
    
    # 优质成长标签（基于成长分）
    if score_growth >= 80:
        tags.append("优质成长")
    if scores['growth'] >= 85 and scores['quality'] >= 75:
        tags.append("高成长")
    if scores['growth'] >= 70 and fund.get('profit_growth', 0) > 30:
        tags.append("业绩爆发")
    
    # 通用标签
    if fund.get('roe', 0) >= 15:
        tags.append("高ROE")
    if fund.get('debt_ratio', 100) < 50:
        tags.append("低负债")
    
    return list(set(tags))  # 去重

def main():
    print("=" * 70)
    print("开始获取个股数据 (双榜单版)")
    print("目标：好股票TOP10 (均衡) + 优质成长TOP10 (进攻)")
    print("=" * 70)
    
    # 1. 初筛
    candidates = fetch_all_quotes()
    if candidates.empty:
        return
    
    today = get_today_str()
    
    # 2. 分层策略：确保两类都有代表性
    # 池1：价值型（PE 8-25，大盘）
    value_candidates = candidates[
        (candidates['pe'] >= 8) & (candidates['pe'] <= 25) &
        (candidates['total_mv'] > 500e8)
    ].sort_values('total_mv', ascending=False)
    
    # 池2：成长型（PE 15-40，增速潜力）
    growth_candidates = candidates[
        (candidates['pe'] > 15) & (candidates['pe'] <= 40)
    ]
    
    # 【调试用】保存初筛数据
    debug_file = STOCKS_DIR / "candidates_debug.json"
    try:
        debug_data = {
            "update_time": datetime.now().isoformat(),
            "value_candidates_count": len(value_candidates),
            "growth_candidates_count": len(growth_candidates),
            "value_candidates": value_candidates.to_dict('records'),
            "growth_candidates": growth_candidates.to_dict('records')
        }
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump(debug_data, f, ensure_ascii=False, indent=2)
        print(f"  - 调试数据已保存: {debug_file}")
    except Exception as e:
        print(f"  - 保存调试数据失败: {e}")
    
    # 合并，成长池优先（确保成长股不被价值股淹没）
    scan_targets = pd.concat([growth_candidates, value_candidates]).drop_duplicates('code').head(300)
    
    # 扫描策略汇总
    scan_summary = {
        "total_scan": len(scan_targets),
        "growth_candidates": len(growth_candidates),
        "value_candidates": len(value_candidates)
    }
    
    print(f"\n扫描策略: {scan_summary['total_scan']} 只")
    print(f"  - 成长候选: {scan_summary['growth_candidates']} 只")
    print(f"  - 价值候选: {scan_summary['value_candidates']} 只")
    
    # 3. 深度扫描
    data = {}
    
    for i, (_, row) in enumerate(scan_targets.iterrows()):
        code = row['code']
        
        if i % 30 == 0:
            print(f"[{i+1}/{len(scan_targets)}] {code} {row['name'][:6]}...")
        
        fund = fetch_deep_fundamentals(code)
        if not fund:
            continue
        
        scores, score_balanced, score_growth = calculate_dual_scores(row, fund)
        
        # 双门槛：均衡分>60 或 成长分>75（确保成长型有机会入选）
        if score_balanced < 60 and score_growth < 75:
            continue
        
        tags = classify_stock(scores, fund, score_balanced, score_growth)
        
        data[code] = {
            "code": code,
            "name": row['name'],
            "price": round(float(row['price']), 2),
            "pe": round(float(row['pe']), 2),
            "pb": round(float(row['pb']), 2),
            "market_cap": round(row['total_mv'] / 1e8, 2),
            "change_pct": round(float(row['change_pct']), 2),
            # 财务
            "roe": round(fund['roe'], 2),
            "profit_growth": round(fund['profit_growth'], 2),
            "revenue_growth": round(fund['revenue_growth'], 2),
            "gross_margin": round(fund['gross_margin'], 2),
            "debt_ratio": round(fund['debt_ratio'], 2),
            # 双评分
            "scores": scores,
            "score_balanced": score_balanced,    # 好股票分
            "score_growth": score_growth,        # 成长分
            "tags": tags,
            "update_time": datetime.now().isoformat()
        }
    
    # 4. 生成双TOP10
    # 好股票榜（按均衡分）
    top_good = sorted(data.items(), key=lambda x: x[1]['score_balanced'], reverse=True)[:10]
    
    # 优质成长榜（按成长分，且成长分>75）
    growth_candidates = {k: v for k, v in data.items() if v['score_growth'] >= 75}
    top_growth = sorted(growth_candidates.items(), key=lambda x: x[1]['score_growth'], reverse=True)[:10]
    
    # 如果成长股不足10只，降低门槛补充
    if len(top_growth) < 10:
        remaining = sorted(
            {k: v for k, v in data.items() if k not in growth_candidates}.items(),
            key=lambda x: x[1]['score_growth'], reverse=True
        )[:10-len(top_growth)]
        top_growth.extend(remaining)
        top_growth = top_growth[:10]
    
    # 5. 保存数据
    output = {
        "date": today,
        "update_time": datetime.now().isoformat(),
        "scan_summary": scan_summary,
        "total_stocks": len(data),
        "top_good_stocks": [v for _, v in top_good],
        "top_growth_stocks": [v for _, v in top_growth],
        "all_stocks": data
    }
    
    output_file = STOCKS_DIR / f"{today}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    latest_file = STOCKS_DIR / "latest.json"
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 6. 输出双榜单
    print(f"\n{'='*70}")
    print("✅ 完成！双榜单精选")
    print(f"{'='*70}")
    print(f"总入选: {len(data)} 只高质量股票")
    
    print(f"\n{'🏆'*15}")
    print("【好股票 TOP10】均衡配置型 - 适合核心仓")
    print(f"{'🏆'*15}")
    print("排名 | 代码   | 名称     | 均衡分 | PE   | ROE  | 增速  | 标签")
    print("-" * 70)
    for i, (code, info) in enumerate(top_good, 1):
        tags_str = ', '.join([t for t in info['tags'] if t in ['好股票', '价值蓝筹', '白马蓝筹', '高ROE']][:2])
        print(f"{i:2d}   | {code} | {info['name'][:8]:8} | {info['score_balanced']:5.1f} | {info['pe']:4.1f} | {info['roe']:4.1f}% | {info['profit_growth']:+5.1f}% | {tags_str}")
    
    print(f"\n{'🚀'*15}")
    print("【优质成长 TOP10】进攻配置型 - 适合卫星仓")
    print(f"{'🚀'*15}")
    print("排名 | 代码   | 名称     | 成长分 | PE   | ROE  | 增速  | 标签")
    print("-" * 70)
    for i, (code, info) in enumerate(top_growth, 1):
        tags_str = ', '.join([t for t in info['tags'] if t in ['优质成长', '高成长', '业绩爆发']][:2])
        print(f"{i:2d}   | {code} | {info['name'][:8]:8} | {info['score_growth']:5.1f} | {info['pe']:4.1f} | {info['roe']:4.1f}% | {info['profit_growth']:+5.1f}% | {tags_str}")
    
    # 重复榜提示
    overlap = set([code for code, _ in top_good]) & set([code for code, _ in top_growth])
    if overlap:
        print(f"\n{'⭐'*15}")
        print(f"【双料冠军】同时入选两榜: {len(overlap)} 只")
        for code in overlap:
            info = data[code]
            print(f"  {code} {info['name']}: 均衡{info['score_balanced']:.1f} + 成长{info['score_growth']:.1f}")
        print("  → 这类股票是核心+成长双重属性，可重仓")
    
    print(f"\n数据保存: {output_file}")

if __name__ == '__main__':
    main()