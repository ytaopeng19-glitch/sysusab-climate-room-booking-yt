import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime, timedelta

# --- 配置区 ---
st.set_page_config(page_title="人工气候室预约系统", layout="centered")
DATA_FILE = "reservations.json"
MAX_CAPACITY = 5      # 每天最大预约人数
ADMIN_PASSWORD = "kexueyuan2026" # 管理员密码

# --- 数据处理函数 ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_capacity(room, req_start, req_end, data):
    current_date = req_start
    while current_date <= req_end:
        daily_count = 0
        for record in data:
            status = record.get("status", "已通过")
            # 只有当状态是"待审批"或"已通过"时，才占用名额
            if record["room"] == room and status in ["待审批", "已通过"]:
                rec_start = datetime.strptime(record["start_date"], "%Y-%m-%d").date()
                rec_end = datetime.strptime(record["end_date"], "%Y-%m-%d").date()
                if rec_start <= current_date <= rec_end:
                    daily_count += 1
                    
        if daily_count >= MAX_CAPACITY:
            return True, current_date
        current_date += timedelta(days=1)
    return False, None

# --- 界面区 ---
st.title("🌱 人工气候室预约系统")

reservations = load_data()
tab1, tab2, tab3 = st.tabs(["📝 提交预约", "📅 查看记录", "👨‍💼 管理员后台"])

# --- Tab 1: 提交预约 ---
with tab1:
    st.subheader("填写预约信息")
    with st.form("reservation_form"):
        user_name = st.text_input("预约人姓名/课题组", placeholder="例如：张三 / 李四课题组")
        room_choice = st.selectbox("选择人工气候室", ["1号人工气候室", "2号人工气候室"])
        dates = st.date_input("选择使用日期区间", [])
        submitted = st.form_submit_button("提交申请")
        
        if submitted:
            if not user_name:
                st.warning("⚠️ 请填写预约人姓名！")
            elif len(dates) == 0:
                st.warning("⚠️ 请选择预约日期！")
            else:
                start_date = dates[0]
                end_date = dates[1] if len(dates) > 1 else dates[0]
                
                is_full, conflict_date = check_capacity(room_choice, start_date, end_date, reservations)
                
                if is_full:
                    formatted_date = conflict_date.strftime("%Y年%m月%d日")
                    st.error(f"❌ 抱歉，{room_choice} 在 **{formatted_date}** 的预约名额（{MAX_CAPACITY}人）已满！")
                else:
                    new_record = {
                        "user": user_name,
                        "room": room_choice,
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "待审批"
                    }
                    reservations.append(new_record)
                    save_data(reservations)
                    st.success(f"✅ 申请已提交！当前状态为【待审批】，请等待管理员审核。")

# --- Tab 2: 查看记录 ---
with tab2:
    st.subheader("所有预约状态")
    if reservations:
        df_data = []
        for r in reservations:
            # 处理显示状态（如果被拒绝且有理由，则展示理由）
            status_text = r.get("status", "已通过")
            if status_text == "已拒绝" and r.get("reject_reason"):
                status_text += f" (理由: {r['reject_reason']})"
                
            df_data.append({
                "当前状态": status_text,
                "气候室": r["room"],
                "预约人": r["user"],
                "开始日期": r["start_date"],
                "结束日期": r["end_date"],
                "提交时间": r["timestamp"]
            })
            
        df = pd.DataFrame(df_data)
        # 按照提交时间倒序排列（最新的在最上面）
        df = df.sort_values(by="提交时间", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("目前还没有任何预约记录。")

# --- Tab 3: 管理员后台 ---
with tab3:
    st.subheader("管理员身份验证")
    pwd = st.text_input("请输入管理员密码", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("身份验证成功！")
        
        # 模块一：待审批列表
        st.markdown("### 📋 待审批列表")
        pending_records = [(i, r) for i, r in enumerate(reservations) if r.get("status") == "待审批"]
        
        if not pending_records:
            st.info("当前没有需要审批的申请。")
        else:
            for index, record in pending_records:
                with st.container():
                    st.write(f"**申请人**: {record['user']} | **房间**: {record['room']}")
                    st.write(f"**时间**: {record['start_date']} 至 {record['end_date']} | **提交于**: {record['timestamp']}")
                    
                    # 新增：填写拒绝理由的输入框
                    reason = st.text_input("📝 拒绝理由（若拒绝请填写）", key=f"reason_{index}")
                    
                    col1, col2 = st.columns([1, 1])
                    if col1.button("✅ 批准", key=f"approve_{index}"):
                        reservations[index]["status"] = "已通过"
                        save_data(reservations)
                        st.rerun()
                    if col2.button("❌ 拒绝", key=f"reject_{index}"):
                        reservations[index]["status"] = "已拒绝"
                        # 保存拒绝理由，如果没填就显示"无"
                        reservations[index]["reject_reason"] = reason if reason.strip() else "无"
                        save_data(reservations)
                        st.rerun()
                st.markdown("---")
                
        # 模块二：管理所有记录（删除功能）
        st.markdown("### 🗑️ 管理所有记录")
        with st.expander("点击展开管理（可删除记录）"):
            if not reservations:
                st.write("暂无记录可管理。")
            else:
                for index, record in enumerate(reservations):
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        status_tag = f"[{record.get('status', '已通过')}]"
                        st.write(f"{status_tag} **{record['user']}** - {record['room']} ({record['start_date']}至{record['end_date']})")
                    with col_btn:
                        # 删除按钮
                        if st.button("删除", key=f"del_{index}"):
                            reservations.pop(index) # 从列表中移除该记录
                            save_data(reservations) # 保存更新后的数据
                            st.rerun() # 刷新页面
                    st.markdown("---")

    elif pwd != "":
        st.error("密码错误！")