import yt_dlp
import os
from pathlib import Path

# 配置
BILIBILI_SPACE_URL = "https://space.bilibili.com/393264421"
TEMP_DIR = Path("./temp_test_audio")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def test_fetch_and_download():
    # 使用一个具体的视频 URL 进行验证，避免主页爬取被封
    TEST_VIDEO_URL = "https://www.bilibili.com/video/BV19u4y1L7pS" # 替换为一个有效的视频 URL
    print(f"1. 正在尝试下载指定视频音频: {TEST_VIDEO_URL}")
    
    print("\n2. 正在尝试下载音频 (仅提取，不转换格式以避开 ffmpeg 依赖)...")
    ydl_opts_dl = {
        'format': 'bestaudio/best',
        'outtmpl': str(TEMP_DIR / "%(id)s.%(ext)s"),
        'max_filesize': 50 * 1024 * 1024, # 限制 50MB
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
        'referer': 'https://www.bilibili.com/',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl_dl:
        try:
            info = ydl_dl.extract_info(TEST_VIDEO_URL, download=True)
            audio_file = TEMP_DIR / f"{info['id']}.{info['ext']}"
            if audio_file.exists():
                print(f"\n✅ 验证成功！音频文件已保存至: {audio_file}")
                print(f"文件大小: {os.path.getsize(audio_file) / 1024 / 1024:.2f} MB")
            else:
                print("\n❌ 文件下载失败，请检查网络或 URL。")
        except Exception as e:
            print(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    test_fetch_and_download()
