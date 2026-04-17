import pandas as pd

REPO_OWNER = "wangqi0821"
REPO_NAME = "uni-calendar-china"
BRANCH = "main"
BASE_RAW = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/"

print("正在处理 Uni.0.csv...\n")

df = pd.read_csv("Uni.0.csv", encoding="gbk")

def to_raw(path):
    if pd.isna(path) or not isinstance(path, str):
        return path
    p = path.strip()
    if p.startswith("http"):                    # 已经是直链就不动
        return p
    if "media.plus/" in p or "media/" in p:
        # 提取文件名部分（去掉 file:/// 开头的本地路径）
        if "media.plus/" in p:
            filename = p.split("media.plus/")[-1]
        else:
            filename = p.split("media/")[-1]
        return BASE_RAW + "media/" + filename     # 统一映射到 media/
    return p

df["Uni"] = df["Uni"].apply(to_raw)

output_file = "Uni.0_updated.csv"
df.to_csv(output_file, index=False, encoding="gbk")

print("✅ 转换完成！")
print(f"   新文件已保存为：{output_file}")
print("   Uni 列现在全部是网络直链")
print("   你可以直接把这个文件的内容复制到 Uni.csv")
input("\n按任意键退出...")