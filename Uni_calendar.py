import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Uni 日历",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 加载数据
@st.cache_data
def load_data():
    df = pd.read_csv("Uni.csv", encoding="gbk")
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df

df = load_data()

# 标题
st.title("Uni 日历")

# 日期选择（默认2020-06-10）
default_date = datetime(2020, 6, 10).date()

selected_date = st.date_input(
    "选择日期",
    value=default_date,
    min_value=datetime(2019, 1, 1).date(),
    max_value=datetime(2027, 12, 31).date()
)

selected_date_str = selected_date.strftime("%Y-%m-%d")

# 筛选当天记录
day_df = df[df["日期"] == selected_date_str].copy()

if day_df.empty:
    st.info(f"📅 {selected_date_str} 还没有记录")
else:
    st.success(f"📅 {selected_date_str} 共有 {len(day_df)} 条帖子")
    
    for _, row in day_df.iterrows():
        st.subheader(row["描述"])

        # 处理 Uni 列（一行多图/视频）
        media_str = str(row.get("Uni", "")).strip()
        if media_str:
            media_list = [m.strip() for m in media_str.split("\n") if m.strip()]
            
            cols = st.columns(min(3, len(media_list)))
            for i, media_path in enumerate(media_list):
                with cols[i % len(cols)]:
                    if media_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        st.image(media_path, width=270)
                    elif media_path.lower().endswith(('.mp4', '.mov', '.webm')):
                        st.video(media_path, width=270)
                    else:
                        st.write(f"📎 {media_path}")

        # 原链接
        if pd.notna(row.get("原链接")) and str(row["原链接"]).strip():
            st.markdown(f"[🔗 查看原帖]({row['原链接']})")

        st.divider()

# 底部声明（按你的要求添加）
st.caption("日历由Uni粉丝制作，供大家方便检索 Uni 的可爱瞬间，未经主人允许请勿用于其他用途。")