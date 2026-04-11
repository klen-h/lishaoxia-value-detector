#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成投资报告
"""

import json
from datetime import datetime
from config import DATA_DIR

def generate_daily_report():
    """生成每日投资简报"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 加载数据
    with open(DATA_DIR / "market/index_valuation.json", 'r') as f:
        market = json.load(f)
    
    with open(DATA_DIR / "indicators/warning_signals.json", 'r') as f:
        signals = json.load(f)
    
    # 生成Markdown报告
    report = f"""# 📊 大霄价值投资日报 - {today}

## 一、市场概览

**当前状态**: {market['overall']['description']}

**核心建议**: {market['overall']['suggestion']}

**仓位配置**: 
- 核心仓: {market['overall']['allocation']['core']}%
- 卫星仓: {market['overall']['allocation']['satellite']}%
- 现金: {market['overall']['allocation']['cash']}%

**沪深300估值**: PE {market['hs300']['pe_ttm']} | PB {market['hs300']['pb']}

---

## 二、今日信号

| 类型 | 数量 | 操作建议 |
|:---|:---:|:---|
| 🔥 强烈抄底 | {signals['summary']['strong_buy']} | 金字塔重仓 |
| ⭐ 中等抄底 | {signals['summary']['buy_signals'] - signals['summary']['strong_buy']} | 分批建仓 |
| ⚠️ 减仓预警 | {signals['summary']['sell_signals']} | 获利了结 |
| ❌ 清仓预警 | {signals['summary']['clear_signals']} | 立即离场 |
| 🚀 成长观察 | {signals['summary']['growth_watch']} | 加入观察池 |

**市场情绪**: {signals['summary']['market_temperature']}

---

## 三、重点推荐（钻石底）

"""
    
    # 添加钻石底股票
    diamond_stocks = [s for s in signals['buy'] if s['level'] == '强烈'][:5]
    for i, s in enumerate(diamond_stocks, 1):
        report += f"""
### {i}. {s['name']} ({s['code']})

- **当前价**: ¥{s['price']}
- **估值**: PE {s['metrics'].get('pe', 'N/A')} | PB {s['metrics'].get('pb', 'N/A')}
- **ROE**: {s['metrics'].get('roe', 'N/A')}%
- **净利增长**: {s['metrics'].get('profit_growth', 'N/A')}%
- **建议**: {s['suggestion']['action']}，目标仓位{s['suggestion']['allocation']}
- **止损**: ¥{s['suggestion']['stop_loss']}

"""
    
    report += f"""
---

## 四、风险提示

1. 本报告基于历史数据，不构成投资建议
2. 市场有风险，投资需谨慎
3. 建议践行"余钱投资、理性投资、价值投资"

*生成时间: {datetime.now().isoformat()}*
"""
    
    # 保存 Markdown 报告
    report_file = DATA_DIR / f"reports/report_{today}.md"
    report_file.parent.mkdir(exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 保存 JSON 报告供 Web 使用
    web_report = {
        "update_date": today,
        "market": {
            "trend": market['overall']['status'].upper().replace('EXTREME_', ''), # 统一格式如 BULL/BEAR
            "description": market['overall']['description'],
            "suggestion": market['overall']['suggestion'],
            "allocation": market['overall']['allocation']
        },
        "top_picks": [
            {
                "name": s['name'],
                "code": s['code'],
                "score": s['score'],
                "pe": s['metrics'].get('pe', 0),
                "pb": s['metrics'].get('pb', 0),
                "roe": s['metrics'].get('roe', 0),
                "signals": [s['level'] + "抄底"] if s in signals['buy'] else []
            } for s in diamond_stocks
        ]
    }
    
    # 也加入一些成长股到 top_picks
    growth_stocks = [s for s in signals.get('growth', [])][:5]
    for s in growth_stocks:
        web_report['top_picks'].append({
            "name": s['name'],
            "code": s['code'],
            "score": s['score'],
            "pe": s['metrics'].get('pe', 0),
            "roe": s['metrics'].get('roe', 0),
            "signals": ["高成长"]
        })

    json_report_file = DATA_DIR / "latest_report.json"
    with open(json_report_file, 'w', encoding='utf-8') as f:
        json.dump(web_report, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 报告已生成: {report_file}")
    print(f"✅ JSON数据已更新: {json_report_file}")

if __name__ == '__main__':
    generate_daily_report()