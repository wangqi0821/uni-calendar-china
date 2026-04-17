import os

print("=== 删除文件名中的 _UTC ===\n")
FOLDER = "media.plus"   # ← 正式文件夹是 media

full_path = os.path.join(os.getcwd(), FOLDER)
count = 0

for filename in os.listdir(full_path):
    if "_UTC" in filename:
        new_name = filename.replace("_UTC", "")
        old_path = os.path.join(full_path, filename)
        new_path = os.path.join(full_path, new_name)
        
        try:
            os.rename(old_path, new_path)
            print(f"✅ 重命名: {filename} → {new_name}")
            count += 1
        except Exception as e:
            print(f"❌ 失败 {filename} - {e}")

print(f"\n🎉 完成！共处理 {count} 个文件")
input("按任意键退出...")