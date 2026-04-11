#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算预警信号 - 抄底/减仓/清仓/成长
"""

import json
from datetime import datetime
from pathlib import Path
from config import INDICATORS_DIR, STOCKS_DIR, MARKET_DIR, SIGNAL_THRESHOLDS

def load_data():
    """加载数据"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 市场数据
    with open(MARKET_DIR / "index_valuation.json", 'r') as f:
        market = json.load(f)
    
    # 个股数据
    with open(STOCKS_DIR / f"{today}.json", 'r') as f:
        stocks = json.load(f)
    
    return market, stocks

def calculate_diamond_bottom(stock, thresh):
    """钻石底信号"""
    pe = stock.get('pe', 999)
    pb = stock.get('pb', 999)
    dy = stock.get('dividend_yield', 0)
    roe = stock.get('roe', 0)
    
    conditions = [
        pe < thresh['pe'] if pe > 0 else False,
        pb < thresh['pb'],
        dy > thresh['dividend_yield'],
        roe > thresh['roe']
    ]
    
    score = sum(conditions)
    if score >= 4:  # 全部满足
        return {
            "level": "强烈",
            "score": 95,
            "conditions": {
                "pe": pe,
                "pb": pb,
                "dividend_yield": dy,
                "roe": roe
            }
        }
    elif score >= 3:  # 满足3项
        return {
            "level": "中等",
            "score": 80,
            "conditions": {
                "pe": pe,
                "pb": pb,
                "dividend_yield": dy,
                "roe": roe
            }
        }
    return None

def calculate_gold_pit(stock, thresh):
    """黄金坑信号"""
    pe = stock.get('pe', 999)
    pb = stock.get('pb', 999)
    dy = stock.get('dividend_yield', 0)
    roe = stock.get('roe', 0)
    
    if pe < thresh['pe'] and dy > thresh['dividend_yield'] and roe > thresh['roe']:
        return {
            "level": "中等",
            "score": 75,
            "conditions": {
                "pe": pe,
                "dividend_yield": dy,
                "roe": roe
            }
        }
    return None

def calculate_overvalued(stock, thresh):
    """高估减仓信号"""
    pe = stock.get('pe', 0)
    pb = stock.get('pb', 0)
    pct_52w = stock.get('percentile_52w', 0)
    
    if pe > thresh['pe'] or (pct_52w > thresh['52w_percentile'] and pe > 30):
        return {
            "level": "强烈" if pe > 50 else "中等",
            "score": max(0, 100 - (pe - thresh['pe']) * 2),
            "conditions": {
                "pe": pe,
                "pb": pb,
                "52w_percentile": pct_52w
            }
        }
    return None

def calculate_deterioration(stock, thresh):
    """基本面恶化清仓信号"""
    roe = stock.get('roe', 15)
    profit_g = stock.get('profit_growth', 0)
    debt = stock.get('debt_ratio', 50)
    
    if roe < thresh['roe'] or profit_g < thresh['profit_growth'] or debt > thresh['debt_ratio']:
        return {
            "level": "强烈",
            "score": 20,
            "conditions": {
                "roe": roe,
                "profit_growth": profit_g,
                "debt_ratio": debt
            }
        }
    return None

def calculate_high_growth(stock, thresh):
    """高成长观察信号"""
    profit_g = stock.get('profit_growth', 0)
    revenue_g = stock.get('revenue_growth', 0)
    pe = stock.get('pe', 999)
    
    if profit_g > thresh['profit_growth'] and revenue_g > thresh['revenue_growth'] and pe < thresh['pe']:
        return {
            "level": "观察",
            "score": 70,
            "conditions": {
                "profit_growth": profit_g,
                "revenue_growth": revenue_g,
                "pe": pe
            }
        }
    return None

def generate_signal_detail(signal_type, level, stock, conditions, market_status):
    """生成信号详情"""
    base = {
        "type": signal_type,
        "level": level,
        "code": stock['code'],
        "name": stock['name'],
        "industry": stock.get('industry', '未知'),
        "price": stock['price'],
        "market_cap": stock.get('market_cap', 0),
        "metrics": conditions,
        "update_time": datetime.now().isoformat()
    }
    
    # 根据信号类型生成建议
    if signal_type == "抄底":
        base["suggestion"] = {
            "action": "金字塔建仓" if level == "强烈" else "分批买入",
            "allocation": "核心仓60-70%" if level == "强烈" else "核心仓40-50%",
            "entry_zone": [
                round(stock['price'] * 0.95, 2),
                round(stock['price'] * 1.02, 2)
            ],
            "stop_loss": round(stock['price'] * (0.88 if level == "强烈" else 0.90), 2),
            "target_price": round(stock['price'] * 1.25, 2),
            "holding_period": "2-3年",
            "reason": "符合李大霄钻石底标准" if level == "强烈" else "估值合理，股息良好"
        }
    
    elif signal_type == "减仓":
        base["suggestion"] = {
            "action": "分批减仓" if level == "中等" else "大幅减仓",
            "reduce_ratio": "30%" if level == "中等" else "50%",
            "target_cash": "增加现金储备，等待更好买点",
            "reason": f"PE{conditions.get('pe', 0):.1f}处于历史高位，获利了结"
        }
    
    elif signal_type == "清仓":
        base["suggestion"] = {
            "action": "立即清仓",
            "reason": "基本面严重恶化，不符合价值投资标准，远离黑五类"
        }
    
    elif signal_type == "成长观察":
        base["suggestion"] = {
            "action": "加入观察池",
            "allocation": "卫星仓20%",
            "entry_condition": f"回调至PE<{conditions.get('pe', 30)*0.8:.0f}或股价跌破20日均线",
            "reason": "业绩高增长，估值合理，关注回调买入机会"
        }
    
    return base

def main():
    """主函数"""
    print("=" * 50)
    print("开始计算预警信号...")
    print("=" * 50)
    
    market, stocks = load_data()
    market_status = market.get('hs300', {}).get('status', 'neutral')
    
    signals = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "market_status": market_status,
        "market_suggestion": market.get('overall', {}).get('suggestion', ''),
        "buy": [],      # 抄底
        "sell": [],     # 减仓
        "clear": [],    # 清仓
        "watch": []     # 观察
    }
    
    # 遍历所有股票
    for code, stock in stocks.items():
        # 1. 钻石底抄底
        diamond = calculate_diamond_bottom(stock, SIGNAL_THRESHOLDS['diamond_bottom'])
        if diamond:
            signals['buy'].append(generate_signal_detail(
                "抄底", diamond['level'], stock, 
                diamond['conditions'], market_status
            ))
            continue  # 钻石底不再检查其他
        
        # 2. 黄金坑买入
        gold = calculate_gold_pit(stock, SIGNAL_THRESHOLDS['gold_pit'])
        if gold:
            signals['buy'].append(generate_signal_detail(
                "抄底", gold['level'], stock,
                gold['conditions'], market_status
            ))
            continue
        
        # 3. 高估减仓
        overvalued = calculate_overvalued(stock, SIGNAL_THRESHOLDS['overvalued'])
        if overvalued:
            signals['sell'].append(generate_signal_detail(
                "减仓", overvalued['level'], stock,
                overvalued['conditions'], market_status
            ))
            continue
        
        # 4. 基本面恶化清仓
        bad = calculate_deterioration(stock, SIGNAL_THRESHOLDS['deterioration'])
        if bad:
            signals['clear'].append(generate_signal_detail(
                "清仓", bad['level'], stock,
                bad['conditions'], market_status
            ))
            continue
        
        # 5. 高成长观察
        growth = calculate_high_growth(stock, SIGNAL_THRESHOLDS['high_growth'])
        if growth:
            signals['watch'].append(generate_signal_detail(
                "成长观察", growth['level'], stock,
                growth['conditions'], market_status
            ))
    
    # 排序
    signals['buy'].sort(key=lambda x: (0 if x['level']=='强烈' else 1, -x['metrics'].get('pe', 999)))
    signals['sell'].sort(key=lambda x: -x['metrics'].get('pe', 0))
    signals['clear'].sort(key=lambda x: x['metrics'].get('roe', 0))
    signals['watch'].sort(key=lambda x: -x['metrics'].get('profit_growth', 0))
    
    # 统计
    signals['summary'] = {
        "total_stocks": len(stocks),
        "buy_signals": len(signals['buy']),
        "strong_buy": sum(1 for s in signals['buy'] if s['level']=='强烈'),
        "sell_signals": len(signals['sell']),
        "clear_signals": len(signals['clear']),
        "growth_watch": len(signals['watch']),
        "market_temperature": "过热" if len(signals['sell']) > len(signals['buy']) * 2 else 
                            "寒冷" if len(signals['buy']) > 50 else "温和"
    }
    
    # 保存
    with open(INDICATORS_DIR / "warning_signals.json", 'w', encoding='utf-8') as f:
        json.dump(signals, f, ensure_ascii=False, indent=2)
    
    # 生成好股票池（评分>=70）
    good_stocks = {k: v for k, v in stocks.items() if v.get('overall_score', 0) >= 70}
    with open(INDICATORS_DIR / "good_stocks.json", 'w', encoding='utf-8') as f:
        json.dump(good_stocks, f, ensure_ascii=False, indent=2)
    
    # 生成成长股池（成长评分>=70且PE<40）
    growth_stocks = {k: v for k, v in stocks.items() 
                     if v.get('scores', {}).get('growth', 0) >= 70 
                     and v.get('pe', 999) < 40}
    with open(INDICATORS_DIR / "growth_stocks.json", 'w', encoding='utf-8') as f:
        json.dump(growth_stocks, f, ensure_ascii=False, indent=2)
    
    # 生成价值股池（价值评分>=80）
    value_stocks = {k: v for k, v in stocks.items() 
                    if v.get('scores', {}).get('value', 0) >= 80}
    with open(INDICATORS_DIR / "value_stocks.json", 'w', encoding='utf-8') as f:
        json.dump(value_stocks, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 50)
    print("✅ 预警信号计算完成")
    print(f"   抄底信号: {signals['summary']['buy_signals']}个 (强烈{signals['summary']['strong_buy']}个)")
    print(f"   减仓信号: {signals['summary']['sell_signals']}个")
    print(f"   清仓信号: {signals['summary']['clear_signals']}个")
    print(f"   成长观察: {signals['summary']['growth_watch']}个")
    print(f"   市场情绪: {signals['summary']['market_temperature']}")
    print(f"   好股票池: {len(good_stocks)}只")
    print(f"   成长股池: {len(growth_stocks)}只")
    print(f"   价值股池: {len(value_stocks)}只")

if __name__ == '__main__':
    main()