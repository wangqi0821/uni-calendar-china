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

# 获取所有有记录的日期（用于自动跳转）
available_dates = sorted(pd.to_datetime(df["日期"]).dt.date.unique())

# 标题
st.title("Uni 日历")

# 默认日期为 2020-06-10
default_date = datetime(2020, 6, 10).date()

selected_date = st.date_input(
    "选择日期",
    value=default_date,
    min_value=datetime(2019, 1, 1).date(),
    max_value=datetime(2027, 12, 31).date()
)

selected_date_str = selected_date.strftime("%Y-%m-%d")

# 如果选择的日期没有记录，自动跳转到最近的有记录日期
if selected_date_str not in df["日期"].values:
    selected_date_obj = selected_date.date()
    closest_date = min(available_dates, key=lambda x: abs((x - selected_date_obj).days))
    closest_str = closest_date.strftime("%Y-%m-%d")
    
    st.warning(f"📅 {selected_date_str} 还没有记录，已自动跳转到最近的有记录日期 **{closest_str}**")
    selected_date_str = closest_str

# 筛选当天记录
day_df = df[df["日期"] == selected_date_str].copy()

if day_df.empty:
    st.info(f"📅 {selected_date_str} 还没有记录")
else:
    st.success(f"📅 {selected_date_str} 共有 {len(day_df)} 条帖子")
    
    for _, row in day_df.iterrows():
        st.subheader(row["描述"])

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

        if pd.notna(row.get("原链接")) and str(row["原链接"]).strip():
            st.markdown(f"[🔗 查看原帖]({row['原链接']})")

        st.divider()

# 底部声明
st.caption("日历由Uni粉丝制作，供大家方便检索 Uni 的可爱瞬间，未经主人允许请勿用于其他用途。")