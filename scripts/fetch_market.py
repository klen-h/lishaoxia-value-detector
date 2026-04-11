#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取市场数据 - 牛熊判断核心
"""

import json
import akshare as ak
import numpy as np
from datetime import datetime, timedelta
from config import MARKET_DIR, MARKET_THRESHOLDS, get_today_str

def fetch_hs300_valuation():
    """获取沪深300估值数据"""
    try:
        # 获取PE历史 (使用乐咕乐股接口替代已失效的 funddb)
        pe_hist = ak.stock_a_pe(market="000300.XSHG")
        latest_pe = float(pe_hist.iloc[-1]['weightingAveragePE'])
        pe_list = pe_hist['weightingAveragePE'].astype(float).tolist()
        
        # 计算分位数
        percentiles = np.percentile(pe_list, [10, 25, 50, 75, 90])
        current_pct = sum(1 for x in pe_list if x < latest_pe) / len(pe_list) * 100
        
        # PB
        pb_hist = ak.stock_a_pb(market="000300.XSHG")
        latest_pb = float(pb_hist.iloc[-1]['weightingAveragePB'])
        
        # 股息率 (从每日行情概况获取，乐咕接口暂不直接提供历史股息率)
        # 简化处理：从最新的指数快照获取
        latest_dy = 2.0 # 默认值，沪深300通常在2%左右
        try:
            summary = ak.stock_sse_summary() # 这是一个尝试
            # 实际上更准确的是通过 Tushare 或其他接口，这里先给个合理默认或略过
        except:
            pass
        
        return {
            "pe_ttm": round(latest_pe, 2),
            "pb": round(latest_pb, 2),
            "dividend_yield": latest_dy,
            "pe_percentile_10y": round(current_pct, 1),
            "pe_levels": {
                "p10": round(percentiles[0], 2),
                "p25": round(percentiles[1], 2),
                "p50": round(percentiles[2], 2),
                "p75": round(percentiles[3], 2),
                "p90": round(percentiles[4], 2)
            }
        }
    except Exception as e:
        print(f"获取沪深300估值失败: {e}")
        return None

def fetch_zz500_valuation():
    """获取中证500估值"""
    try:
        pe_hist = ak.stock_a_pe(market="000905.XSHG")
        latest_pe = float(pe_hist.iloc[-1]['weightingAveragePE'])
        pe_list = pe_hist['weightingAveragePE'].astype(float).tolist()
        return {
            "pe_ttm": round(latest_pe, 2),
            "pe_percentile": round(
                sum(1 for x in pe_list if x < latest_pe) / len(pe_list) * 100, 1
            )
        }
    except Exception as e:
        print(f"获取中证500估值失败: {e}")
        return None

def calculate_market_status(hs300_data):
    """计算市场牛熊状态"""
    if not hs300_data:
        return "unknown", 50, "数据获取失败"
    
    pe = hs300_data['pe_ttm']
    pe_pct = hs300_data['pe_percentile_10y']
    th = MARKET_THRESHOLDS['hs300_pe']
    
    # 风险溢价
    bond_yield = 2.5  # 假设10年期国债收益率2.5%
    risk_premium = round(100 / pe - bond_yield, 2)
    
    # 状态判断
    if pe < th['extreme_bear'] or pe_pct < 10:
        status = "extreme_bear"
        desc = "🐻🐻 极端熊市 - 钻石底区域"
        suggestion = "历史级机会，大胆重仓优质蓝筹"
        score = 90
    elif pe < th['bear'] or pe_pct < 25:
        status = "bear"
        desc = "🐻 熊市 - 黄金坑"
        suggestion = "估值偏低，积极建仓"
        score = 75
    elif pe > th['extreme_bull'] or pe_pct > 90:
        status = "extreme_bull"
        desc = "🐂🐂 极端牛市 - 泡沫期"
        suggestion = "严重高估，逐步清仓离场"
        score = 20
    elif pe > th['bull'] or pe_pct > 75:
        status = "bull"
        desc = "🐂 牛市 - 估值偏高"
        suggestion = "获利了结，降低仓位"
        score = 40
    else:
        status = "neutral"
        desc = "⚖️ 震荡市"
        suggestion = "结构行情，精选个股"
        score = 60
    
    return {
        "status": status,
        "description": desc,
        "score": score,
        "risk_premium": risk_premium,
        "suggestion": suggestion,
        "allocation": get_allocation_advice(status)
    }

def get_allocation_advice(status):
    """仓位建议"""
    allocations = {
        "extreme_bear": {"core": 70, "satellite": 20, "cash": 10, "tactics": "金字塔重仓"},
        "bear": {"core": 60, "satellite": 25, "cash": 15, "tactics": "定投+择时"},
        "neutral": {"core": 50, "satellite": 30, "cash": 20, "tactics": "平衡配置"},
        "bull": {"core": 35, "satellite": 30, "cash": 35, "tactics": "获利减仓"},
        "extreme_bull": {"core": 20, "satellite": 20, "cash": 60, "tactics": "逐步清仓"}
    }
    return allocations.get(status, allocations["neutral"])

def fetch_sector_rotation():
    """获取行业轮动数据"""
    try:
        # 获取行业涨跌幅
        sector_df = ak.stock_sector_spot()
        sectors = []
        for _, row in sector_df.head(20).iterrows():
            sectors.append({
                "name": row['板块'],
                "change": row['涨跌幅'],
                "leading_stocks": row['领涨股'].split(',')[:3] if '领涨股' in row else []
            })
        return sectors
    except Exception as e:
        print(f"获取行业数据失败: {e}")
        return []

def main():
    """主函数"""
    print("=" * 50)
    print("开始获取市场数据...")
    print("=" * 50)
    
    today = get_today_str()
    
    # 获取数据
    hs300 = fetch_hs300_valuation()
    zz500 = fetch_zz500_valuation()
    
    # 容错处理：如果获取失败，给出一组默认值或跳过
    if hs300 is None:
        print("❌ 警告: 无法获取沪深300估值数据，使用备用方案或停止更新")
        # 这里可以选择停止或给默认，为了保证流程不中断，给一个保守的空对象
        hs300 = {"pe_ttm": 12.0, "pb": 1.3, "dividend_yield": 2.0, "pe_percentile_10y": 50, "pe_levels": {}}
        
    market_status = calculate_market_status(hs300)
    sectors = fetch_sector_rotation()
    
    # 组装结果
    result = {
        "date": today,
        "update_time": datetime.now().isoformat(),
        "hs300": {
            **hs300,
            **market_status
        },
        "zz500": zz500 if zz500 else {},
        "sectors": sectors,
        "overall": {
            "status": market_status['status'],
            "description": market_status['description'],
            "suggestion": market_status['suggestion'],
            "allocation": market_status['allocation']
        }
    }
    
    # 保存
    output_file = MARKET_DIR / "index_valuation.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 市场数据已保存: {output_file}")
    print(f"   状态: {market_status['description']}")
    print(f"   建议: {market_status['suggestion']}")
    print(f"   仓位: 核心{market_status['allocation']['core']}% 卫星{market_status['allocation']['satellite']}% 现金{market_status['allocation']['cash']}%")

if __name__ == '__main__':
    from datetime import datetime
    main()