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
    with open(DATA_DIR / "market/index_valuation.json", 'r', encoding='utf-8') as f:
        market = json.load(f)
    
    with open(DATA_DIR / "indicators/warning_signals.json", 'r', encoding='utf-8') as f:
        signals = json.load(f)

    # 加载双榜单数据
    with open(DATA_DIR / "stocks/latest.json", 'r', encoding='utf-8') as f:
        stocks_data = json.load(f)
        all_stocks = list(stocks_data.get('all_stocks', {}).values())
        # 保持旧逻辑用于 Markdown 报告生成
        top_good = stocks_data.get('top_good_stocks', [])
        top_growth = stocks_data.get('top_growth_stocks', [])

    # 加载初筛调试数据 (candidates_debug.json) 
    candidates_debug = {}
    try:
        with open(DATA_DIR / "stocks/candidates_debug.json", 'r', encoding='utf-8') as f:
            candidates_debug = json.load(f)
    except Exception as e:
        print(f"⚠️ 加载调试数据失败: {e}")
    
    # 生成Markdown报告
    report_file = DATA_DIR / "reports" / f"report_{today}.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
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

## 三、双榜单精选 (核心 + 卫星)

### 🏆 【好股票 TOP5】均衡配置型 (核心仓)
"""
    for i, s in enumerate(top_good[:5], 1):
        report += f"{i}. **{s['name']}** ({s['code']}) - 均衡分: {s['score_balanced']} | PE: {s['pe']} | ROE: {s['roe']}%\n"

    report += "\n### 🚀 【优质成长 TOP5】进攻配置型 (卫星仓)\n"
    for i, s in enumerate(top_growth[:5], 1):
        report += f"{i}. **{s['name']}** ({s['code']}) - 成长分: {s['score_growth']} | PE: {s['pe']} | 增速: {s['profit_growth']}%\n"

    report += f"""
---

## 四、重点推荐（钻石底预警）

"""
    # ... (原有钻石底推荐逻辑不变)
    diamond_stocks = [s for s in signals['buy'] if s['level'] == '强烈'][:5]
    for i, s in enumerate(diamond_stocks, 1):
        report += f"""
### {i}. {s['name']} ({s['code']})

- **当前价**: ¥{s['price']}
- **估值**: PE {s['metrics'].get('pe', 'N/A')} | PB {s['metrics'].get('pb', 'N/A')}
- **ROE**: {s['metrics'].get('roe', 'N/A')}%
- **净利增长**: {s['metrics'].get('profit_growth', 'N/A')}%
- **建议**: {s['suggestion']['action']}
"""

    # 组装 web_report (增加双榜单字段)
    web_report = {
        "update_date": today,
        "scan_summary": stocks_data.get('scan_summary', {}),
        "candidates_count": {
            "value": candidates_debug.get('value_candidates_count', 0),
            "growth": candidates_debug.get('growth_candidates_count', 0)
        },
        "market": {
            "trend": market['overall']['status'].upper().replace('EXTREME_', ''),
            "description": market['overall']['description'],
            "suggestion": market['overall']['suggestion'],
            "allocation": market['overall']['allocation']
        },
        "all_stocks": all_stocks,  # 将所有入选股票传给前端
        "top_picks": [] # 保持兼容性
    }
    
    # 填充原有的 top_picks 用于兼容
    for s in diamond_stocks:
        web_report['top_picks'].append({
            "name": s['name'],
            "code": s['code'],
            "score": s['score'],
            "pe": s['metrics'].get('pe', 0),
            "roe": s['metrics'].get('roe', 0),
            "signals": [s['level'] + "抄底"]
        })
    
    # 保存 JSON
    json_report_file = DATA_DIR / "latest_report.json"
    with open(json_report_file, 'w', encoding='utf-8') as f:
        json.dump(web_report, f, ensure_ascii=False, indent=2)

    # 保存 Markdown
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)

    
    print(f"✅ 报告已生成: {report_file}")
    print(f"✅ JSON数据已更新: {json_report_file}")

if __name__ == '__main__':
    generate_daily_report()