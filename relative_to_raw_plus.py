import pandas as pd
import os

# ================== 配置区 ==================
REPO_OWNER = "wangqi0821"          # 你的 GitHub 用户名
REPO_NAME = "uni-calendar-china"   # 你的仓库名
BRANCH = "main"                    # 主分支名（通常是 main）

# 基础 raw 链接
BASE_RAW = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/"
# ===========================================

print("正在读取 Uni.csv...")

df = pd.read_csv("Uni.csv", encoding="gbk")

def convert_path(media_str):
    if pd.isna(media_str) or not isinstance(media_str, str):
        return media_str
    
    # 支持一行多图（你原来的换行格式）
    lines = [line.strip() for line in media_str.split("\n") if line.strip()]
    new_lines = []
    
    for line in lines:
        line = line.strip()
        if line.startswith("http"):          # 已经是完整链接就不动
            new_lines.append(line)
        elif line.startswith("media.plus/") or line.startswith("media/"):
            # 转成 raw 直链
            full_url = BASE_RAW + line
            new_lines.append(full_url)
        else:
            new_lines.append(line)           # 其他情况不动
    
    # 转回换行字符串
    return "\n".join(new_lines)

# 对 Uni 列批量转换
df["Uni"] = df["Uni"].apply(convert_path)

# 保存新文件（不覆盖原文件）
output_file = "Uni_updated.csv"
df.to_csv(output_file, index=False, encoding="gbk")

print(f"✅ 转换完成！")
print(f"   新文件已保存为：{output_file}")
print(f"   一共处理了 {len(df)} 条记录")
print(f"   你可以直接把 Uni_updated.csv 重命名为 Uni.csv，然后用 GitHub Desktop 推送即可。")