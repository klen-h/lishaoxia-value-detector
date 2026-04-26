#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大霄视频自动化解析流水线
功能：监控 B 站更新 -> 下载音频 -> 语音转文字 -> AI 深度解析 -> 生成 JSON
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

# 尝试导入必要的库，如果不存在则提示安装
try:
    import yt_dlp
    from openai import OpenAI
except ImportError:
    print("请先安装依赖: pip install yt-dlp openai")
    exit(1)

# 配置区域
BILIBILI_SPACE_URL = "https://space.bilibili.com/2137589551" # 李大霄 B 站主页
TEMP_DIR = Path("./temp_audio")
OUTPUT_DIR = Path("./data/video_analysis")
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "你的_KIMI_API_KEY")

# 确保目录存在
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

client = OpenAI(
    api_key=KIMI_API_KEY,
    base_url="https://api.moonshot.cn/v1",
)

def get_latest_video():
    """使用 yt-dlp 获取最新视频信息"""
    print("正在检查 B 站更新...")
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.bilibili.com/',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(f"{BILIBILI_SPACE_URL}/video", download=False)
            if 'entries' in result and len(result['entries']) > 0:
                latest = result['entries'][0]
                return {
                    'title': latest['title'],
                    'url': latest['url'],
                    'id': latest['id']
                }
        except Exception as e:
            print(f"获取视频列表失败: {e}")
            print("提示：如果遇到 412 错误，可能是 IP 被 B 站封锁，请尝试更换网络环境或在本地运行。")
    return None

def download_audio(video_url):
    """下载视频并提取音频"""
    print(f"正在下载音频: {video_url}")
    output_template = str(TEMP_DIR / "%(id)s.%(ext)s")
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_template,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.bilibili.com/',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=True)
            return TEMP_DIR / f"{info['id']}.mp3"
        except Exception as e:
            print(f"下载音频失败: {e}")
            return None

def transcribe_audio(audio_path):
    """
    语音转文字
    方案 A: 使用本地 Whisper (需安装 pip install openai-whisper)
    方案 B: 使用 OpenAI Whisper API (更稳定，需付费)
    这里演示方案 A 的逻辑（假设用户本地有环境）
    """
    print("正在进行语音转文字 (ASR)...")
    # 如果用户想用本地，可以取消下面注释
    # import whisper
    # model = whisper.load_model("base")
    # result = model.transcribe(str(audio_path))
    # return result["text"]
    
    # 方案 B: 暂时模拟返回，或者调用 API
    # return "这里是模拟的转录文字..."
    return "[转录示例]：各位观众朋友们大家好，大霄老师今天又来跟大家聊股票了。目前的市场处于钻石底阶段..."

def analyze_with_ai(text):
    """调用 Kimi API 进行深度解析"""
    print("正在调用 AI 进行深度解析...")
    prompt = f"""
    你是一个专业的财经分析师。请对以下李大霄的视频发言进行深度解析。
    要求：
    1. 提取核心观点（看空、看多、中性）。
    2. 识别提到的具体板块或股票。
    3. 总结金句。
    4. 输出严格的 JSON 格式。

    发言文本：
    {text}
    """
    
    completion = client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {"role": "system", "content": "你是一个金融专家，擅长将非结构化文本转化为结构化 JSON 数据。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )
    
    content = completion.choices[0].message.content
    # 提取 JSON 部分（防止 AI 输出多余文字）
    try:
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        return json.loads(content[json_start:json_end])
    except Exception as e:
        print(f"JSON 解析失败: {e}")
        return {"error": "AI 输出格式错误"}

def main():
    # 1. 获取最新视频
    video = get_latest_video()
    if not video:
        print("未找到视频")
        return

    # 检查是否已经处理过
    output_file = OUTPUT_DIR / f"{video['id']}.json"
    if output_file.exists():
        print(f"视频 {video['title']} 已处理过，跳过。")
        return

    # 2. 下载音频
    audio_path = download_audio(video['url'])
    if not audio_path:
        print("音频下载失败，停止后续流程。")
        return

    # 3. 转录文字
    text = transcribe_audio(audio_path)

    # 4. AI 解析
    result = analyze_with_ai(text)
    
    # 5. 保存结果
    result['meta'] = {
        'title': video['title'],
        'url': video['url'],
        'processed_at': datetime.now().isoformat()
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"处理完成！结果已保存至: {output_file}")

if __name__ == "__main__":
    main()
