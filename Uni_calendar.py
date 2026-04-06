import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="Uni 日历", layout="wide", page_icon="🐱")

st.title("🐱 Uni 日历")
st.markdown("### 小猫 Uni 的每日媒体记录")

# 加载数据
@st.cache_data
def load_data():
    df = pd.read_csv("Uni.csv", encoding="gbk")
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df

df = load_data()

# 侧边栏统计
st.sidebar.markdown("### 统计信息")
st.sidebar.write(f"总记录数：**{len(df)}** 条")
if not df.empty:
    min_date = df["日期"].min()
    max_date = df["日期"].max()
    st.sidebar.write(f"日期范围：**{min_date}** 至 **{max_date}**")

# 日期选择
selected_date = st.date_input(
    "选择日期",
    value=datetime.today().date(),
    min_value=datetime(2019, 1, 1).date(),
    max_value=datetime.today().date()
)

selected_date_str = selected_date.strftime("%Y-%m-%d")

# 筛选当天记录
day_df = df[df["日期"] == selected_date_str]

if day_df.empty:
    st.warning(f"📅 {selected_date_str} 还没有记录哦～")
else:
    st.success(f"📅 {selected_date_str} 共有 {len(day_df)} 条记录")
    
    for idx, row in day_df.iterrows():
        st.markdown(f"**{row['描述']}**")
        
        # 处理 Uni 列（支持一行多图/视频）
        media_str = str(row.get("Uni", "")).strip()
        if media_str:
            media_list = [m.strip() for m in media_str.split("\n") if m.strip()]
            cols = st.columns(min(3, len(media_list)))  # 最多一行3个
            for i, media_path in enumerate(media_list):
                col = cols[i % len(cols)]
                with col:
                    if media_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        st.image(media_path, use_column_width=True)
                    elif media_path.lower().endswith(('.mp4', '.mov', '.webm')):
                        st.video(media_path)
                    else:
                        st.write(f"📎 {media_path}")
        
        # 原链接
        if pd.notna(row.get("原链接")):
            st.markdown(f"[🔗 查看原帖]({row['原链接']})")
        
        st.divider()

# 页脚
st.caption("Uni 日历 · Powered by Streamlit + GitHub")