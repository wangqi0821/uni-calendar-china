import instaloader
import pandas as pd
import os
import time
from collections import defaultdict

print("=== 下载 Instagram 媒体到 media.plus 文件夹 ===\n")
print("本次会根据 Uni.0.csv 中的【原链接】列抓取所有 Instagram 帖子\n")

CSV_FILE = "Uni.0.csv"               # ← 这里已改成你现在的文件名
MEDIA_FOLDER = "media.plus"
os.makedirs(MEDIA_FOLDER, exist_ok=True)

L = instaloader.Instaloader(download_pictures=True, download_videos=True, compress_json=False)

# ================== 自动保存登录状态 ==================
SESSION_FILE = "instagram_session"

try:
    L.load_session_from_file(SESSION_FILE)
    print("✅ 已使用保存的登录状态，直接开始抓取\n")
except:
    print("需要首次登录...")
    username = input("请输入你的 Instagram 用户名: ")
    password = input("请输入你的 Instagram 密码: ")
    L.login(username, password)
    L.save_session_to_file(SESSION_FILE)
    print("✅ 登录成功！登录状态已保存，下次无需再输入\n")
# =====================================================

df = pd.read_csv(CSV_FILE, encoding="gbk")
print(f"成功读取 Uni.0.csv，共 {len(df)} 条记录\n")

day_post_count = defaultdict(int)

for idx, row in df.iterrows():
    link = str(row.get("原链接", "")).strip()
    if "instagram.com" not in link:
        continue

    date_str = str(row.get("日期", "")).strip()
    try:
        post_date = pd.to_datetime(date_str)
        date_key = post_date.strftime("%Y-%m-%d")
    except:
        print(f"⚠️ 第 {idx+1} 行日期格式异常，跳过")
        continue

    day_post_count[date_key] += 1
    post_num = day_post_count[date_key]

    try:
        shortcode = link.split("/p/")[-1].split("/")[0].split("?")[0]
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        L.download_post(post, target=MEDIA_FOLDER)

        downloaded = [f for f in os.listdir(MEDIA_FOLDER) if shortcode in f]

        for f in downloaded:
            full_path = os.path.join(MEDIA_FOLDER, f)
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.webm')):
                new_name = f"{date_key}.{post_num}.{len([x for x in downloaded if x.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov', '.webm'))] - len(downloaded) + downloaded.index(f) + 1)}{os.path.splitext(f)[1]}"
                new_path = os.path.join(MEDIA_FOLDER, new_name)
                os.rename(full_path, new_path)
                print(f"✅ 下载并重命名: {new_name}")
            else:
                os.remove(full_path)
                print(f"🗑️ 删除多余文件: {f}")

    except Exception as e:
        print(f"❌ 第 {idx+1} 行 下载失败 - {e}")

    time.sleep(4)

print("\n🎉 全部抓取完成！")
print(f"媒体已全部保存到 {MEDIA_FOLDER} 文件夹")
print("你现在可以直接在 Uni.0.csv 的 Uni 列写相对路径，例如：media.plus/2025-09-19.1.1.jpg")
input("\n按任意键退出...")