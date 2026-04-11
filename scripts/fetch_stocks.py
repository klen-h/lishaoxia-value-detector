#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取全市场个股数据
"""

import json
import pandas as pd
import akshare as ak
from datetime import datetime
from config import STOCKS_DIR, STOCK_FILTERS, SCORE_WEIGHTS, get_today_str, get_latest_trade_date

def fetch_stock_list():
    """获取股票列表并筛选"""
    print("获取股票列表...")
    df = ak.stock_zh_a_spot_em()
    
    # 筛选条件
    filters = []
    
    if STOCK_FILTERS['exclude_st']:
        filters.append(~df['名称'].str.contains('ST|退|*ST', na=False))
    
    if STOCK_FILTERS['exclude_b']:
        filters.append(~df['代码'].str.startswith('2'))  # B股
        filters.append(~df['代码'].str.startswith('9'))  # B股
    
    if STOCK_FILTERS['min_market_cap']:
        filters.append(df['总市值'] >= STOCK_FILTERS['min_market_cap'])
    
    if STOCK_FILTERS['max_market_cap']:
        filters.append(df['总市值'] <= STOCK_FILTERS['max_market_cap'])
    
    # 应用筛选
    from functools import reduce
    if filters:
        mask = reduce(lambda x, y: x & y, filters)
        df = df[mask]
    
    print(f"筛选后: {len(df)}只股票")
    return df

def parse_float(val):
    """安全解析浮点数"""
    try:
        if pd.isna(val):
            return 0
        return float(val)
    except:
        return 0

def fetch_financial_data(code):
    """获取财务数据（带异常处理）"""
    try:
        fin = ak.stock_financial_analysis_indicator(symbol=code)
        if fin.empty:
            return None
        
        latest = fin.iloc[0]
        return {
            "roe": parse_float(latest.get('净资产收益率(%)')),
            "roe_diluted": parse_float(latest.get('净资产收益率-摊薄(%)')),
            "profit_growth": parse_float(latest.get('净利润同比增长率(%)')),
            "revenue_growth": parse_float(latest.get('营业收入同比增长率(%)')),
            "debt_ratio": parse_float(latest.get('资产负债率(%)')),
            "gross_margin": parse_float(latest.get('销售毛利率(%)')),
            "net_margin": parse_float(latest.get('销售净利率(%)')),
            "report_period": str(latest.get('报告期', ''))
        }
    except Exception as e:
        print(f"  财务数据获取失败 {code}: {e}")
        return None

def fetch_dividend_data(code):
    """获取分红数据"""
    try:
        div = ak.stock_dividend_cninfo(symbol=code)
        if div.empty:
            return {"years": 0, "continuous": 0, "latest": 0}
        
        # 解析年份
        years = []
        for _, row in div.iterrows():
            if '派息日' in row and pd.notna(row['派息日']):
                year = int(str(row['派息日'])[:4])
                years.append(year)
        
        unique_years = sorted(set(years), reverse=True)
        current_year = datetime.now().year
        
        # 计算连续分红
        continuous = 0
        for i, year in enumerate(unique_years):
            if year == current_year - i:
                continuous += 1
            else:
                break
        
        # 最新分红
        latest_div = 0
        if '派息比例' in div.columns and not div.empty:
            latest_div = parse_float(div.iloc[0]['派息比例'])
        
        return {
            "years": len(unique_years),
            "continuous": continuous,
            "latest": latest_div,
            "history": [
                {"year": y, "dividend": parse_float(div[div['派息日'].str.startswith(str(y))].iloc[0]['派息比例']) 
                 if len(div[div['派息日'].str.startswith(str(y))]) > 0 else 0}
                for y in unique_years[:5]
            ]
        }
    except Exception as e:
        return {"years": 0, "continuous": 0, "latest": 0}

def calculate_scores(stock_data):
    """计算五维评分"""
    scores = {}
    
    # 1. 价值评分（低PE+高股息+破净）
    pe = stock_data.get('pe', 999)
    pb = stock_data.get('pb', 999)
    dy = stock_data.get('dividend_yield', 0)
    
    value_score = 0
    value_score += max(0, (30 - pe) * 1.5)  # PE越低越好
    value_score += dy * 8                    # 股息率越高越好
    value_score += max(0, (1 - pb)) * 20     # 破净加分
    scores['value'] = min(100, max(0, value_score))
    
    # 2. 质量评分（ROE+利润率）
    roe = stock_data.get('roe', 0)
    net_margin = stock_data.get('net_margin', 0)
    
    quality_score = roe * 3
    quality_score += net_margin * 0.5
    scores['quality'] = min(100, max(0, quality_score))
    
    # 3. 安全评分（分红+市值+负债）
    continuous = stock_data.get('continuous_dividend', 0)
    cap = stock_data.get('market_cap', 0)
    debt = stock_data.get('debt_ratio', 100)
    
    safety_score = continuous * 4  # 每年分红+4分
    safety_score += min(20, cap / 500)  # 市值加分
    safety_score += max(0, (100 - debt) * 0.2)  # 低负债加分
    scores['safety'] = min(100, max(0, safety_score))
    
    # 4. 成长评分（业绩增速）
    profit_g = stock_data.get('profit_growth', 0)
    revenue_g = stock_data.get('revenue_growth', 0)
    
    # 增速适中最好（30-50%），过高可能不可持续
    if 20 < profit_g < 50:
        growth_score = 70 + (profit_g - 20) * 0.5
    elif profit_g >= 50:
        growth_score = 85
    elif profit_g > 0:
        growth_score = 50 + profit_g
    else:
        growth_score = max(0, 50 + profit_g)  # 负增长扣分
    
    scores['growth'] = min(100, growth_score)
    
    # 5. 动量评分（技术面）
    pct_52w = stock_data.get('percentile_52w', 50)
    # 50-70%区间最好（趋势向上但不过热）
    if 40 < pct_52w < 70:
        momentum_score = 70
    elif pct_52w >= 70:
        momentum_score = max(0, 100 - (pct_52w - 70) * 2)  # 过高减分
    else:
        momentum_score = 40 + pct_52w * 0.5  # 过低（弱势）减分
    
    scores['momentum'] = min(100, momentum_score)
    
    return {k: round(v, 1) for k, v in scores.items()}

def get_rating(score):
    """评分转评级"""
    if score >= 85: return "钻石底"
    if score >= 75: return "黄金坑"
    if score >= 65: return "优质蓝筹"
    if score >= 55: return "观察"
    if score >= 45: return "谨慎"
    return "远离"

def main():
    """主函数"""
    print("=" * 50)
    print("开始获取个股数据...")
    print("=" * 50)
    
    today = get_today_str()
    
    # 获取股票列表
    stock_list = fetch_stock_list()
    
    data = {}
    processed = 0
    errors = 0
    
    for idx, row in stock_list.iterrows():
        code = row['代码']
        
        try:
            print(f"[{processed+1}/{len(stock_list)}] {code} {row['名称'][:8]}...", end=' ')
            
            # 基础数据
            stock_data = {
                "code": code,
                "name": row['名称'],
                "industry": row.get('所属行业', '未知'),
                "price": parse_float(row['最新价']),
                "change": parse_float(row['涨跌额']),
                "change_pct": parse_float(row['涨跌幅']),
                "open": parse_float(row['今开']),
                "high": parse_float(row['最高价']),
                "low": parse_float(row['最低价']),
                "volume": parse_float(row['成交量']),
                "amount": parse_float(row['成交额']),
                "amplitude": parse_float(row['振幅']),
                "turnover": parse_float(row['换手率']),
                "pe": parse_float(row.get('市盈率-动态')),
                "pb": parse_float(row.get('市净率')),
                "ps": parse_float(row.get('市销率')),
                "pcf": parse_float(row.get('市现率')),
                "dividend_yield": parse_float(row.get('股息率')),
                "market_cap": parse_float(row['总市值']),
                "float_cap": parse_float(row['流通市值']),
                "52w_high": parse_float(row.get('52周最高价', 0)),
                "52w_low": parse_float(row.get('52周最低价', 0)),
            }
            
            # 计算52周位置
            if stock_data['52w_high'] > stock_data['52w_low']:
                stock_data['percentile_52w'] = round(
                    (stock_data['price'] - stock_data['52w_low']) / 
                    (stock_data['52w_high'] - stock_data['52w_low']) * 100, 1
                )
            else:
                stock_data['percentile_52w'] = 50
            
            # 获取财务数据（每10只打印进度）
            if processed % 10 == 0:
                print(f"获取财务...", end=' ')
            fin_data = fetch_financial_data(code)
            if fin_data:
                stock_data.update(fin_data)
                print(f"ROE{fin_data['roe']:.1f}%", end=' ')
            
            # 获取分红数据
            div_data = fetch_dividend_data(code)
            stock_data['dividend_years'] = div_data['years']
            stock_data['continuous_dividend'] = div_data['continuous']
            stock_data['latest_dividend'] = div_data['latest']
            
            # 计算评分
            stock_data['scores'] = calculate_scores(stock_data)
            stock_data['overall_score'] = round(
                sum(stock_data['scores'][k] * SCORE_WEIGHTS[k] 
                    for k in stock_data['scores']), 1
            )
            stock_data['rating'] = get_rating(stock_data['overall_score'])
            
            # 更新时间
            stock_data['update_time'] = datetime.now().isoformat()
            
            data[code] = stock_data
            processed += 1
            print(f"✓ 评分{stock_data['overall_score']}")
            
            # 每50只保存一次（防止中断丢失）
            if processed % 50 == 0:
                with open(STOCKS_DIR / f"{today}_temp.json", 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                print(f"  [自动保存 {processed}只]")
            
        except Exception as e:
            print(f"✗ 错误: {str(e)[:30]}")
            errors += 1
            continue
    
    # 最终保存
    output_file = STOCKS_DIR / f"{today}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 创建软链接
    import os
    latest_link = STOCKS_DIR / "latest.json"
    if os.path.exists(latest_link) or os.path.islink(latest_link):
        os.remove(latest_link)
    os.symlink(f"{today}.json", latest_link)
    
    print("\n" + "=" * 50)
    print(f"✅ 完成！成功: {processed}, 失败: {errors}")
    print(f"   保存至: {output_file}")
    print(f"   股票数: {len(data)}")
    print(f"   平均分: {sum(s['overall_score'] for s in data.values())/len(data):.1f}")

if __name__ == '__main__':
    main()