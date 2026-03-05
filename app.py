import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client

# --- 配置区 ---
st.set_page_config(page_title="人工气候室预约系统", layout="centered")
MAX_CAPACITY = 5
ADMIN_PASSWORD = "kexueyuan2026"

# --- 数据库连接初始化 ---
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- 数据库操作函数 ---
def load_data():
    response = supabase.table("reservations").select("*").execute()
    return response.data

def insert_record(record_data):
    supabase.table("reservations").insert(record_data).execute()

def update_status(record_id, new_status, reason="无"):
    supabase.table("reservations").update({"status": new_status, "reject_reason": reason}).eq("id", record_id).execute()

def delete_record(record_id):
    supabase.table("reservations").delete().eq("id", record_id).execute()

def check_capacity(room, req_start, req_end, data):
    current_date = req_start
    while current_date <= req_end:
        daily_count = 0
        for record in data:
            if record["room"] == room and record.get("status") in ["待审批", "已通过"]:
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
        # 新增：手机号码输入框
        phone_number = st.text_input("联系手机号码", placeholder="例如：13800138000") 
        room_choice = st.selectbox("选择人工气候室", ["1号人工气候室", "2号人工气候室"])
        dates = st.date_input("选择使用日期区间", [])
        submitted = st.form_submit_button("提交申请")
        
        if submitted:
            if not user_name:
                st.warning("⚠️ 请填写预约人姓名！")
            elif not phone_number: # 新增：手机号必填校验
                st.warning("⚠️ 请填写联系手机号码！")
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
                        "phone": phone_number, # 新增：将手机号写入数据库
                        "room": room_choice,
                        "start_date": start_date.strftime("%Y-%m-%d"),
                        "end_date": end_date.strftime("%Y-%m-%d"),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "待审批",
                        "reject_reason": "无"
                    }
                    insert_record(new_record)
                    st.success(f"✅ 申请已提交！当前状态为【待审批】。")
                    st.rerun()

# --- Tab 2: 查看记录 ---
with tab2:
    st.subheader("所有预约状态")
    if reservations:
        df_data = []
        for r in reservations:
            status_text = r.get("status")
            if status_text == "已拒绝" and r.get("reject_reason") != "无":
                status_text += f" (理由: {r['reject_reason']})"
                
            df_data.append({
                "当前状态": status_text,
                "气候室": r["room"],
                "预约人": r["user"],
                "手机号码": r.get("phone", "未提供"), # 新增：在表格中展示手机号（兼容老数据）
                "开始日期": r["start_date"],
                "结束日期": r["end_date"],
                "提交时间": r["timestamp"]
            })
            
        df = pd.DataFrame(df_data)
        # 调整一下列的显示顺序
        df = df[["当前状态", "气候室", "预约人", "手机号码", "开始日期", "结束日期", "提交时间"]]
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
        
        st.markdown("### 📋 待审批列表")
        pending_records = [r for r in reservations if r.get("status") == "待审批"]
        
        if not pending_records:
            st.info("当前没有需要审批的申请。")
        else:
            for record in pending_records:
                rec_id = record['id']
                with st.container():
                    # 新增：在管理员审批卡片上显示手机号
                    st.write(f"**申请人**: {record['user']} (📞 {record.get('phone', '未提供')}) | **房间**: {record['room']}")
                    st.write(f"**时间**: {record['start_date']} 至 {record['end_date']} | **提交于**: {record['timestamp']}")
                    
                    reason = st.text_input("📝 拒绝理由", key=f"reason_{rec_id}")
                    
                    col1, col2 = st.columns([1, 1])
                    if col1.button("✅ 批准", key=f"approve_{rec_id}"):
                        update_status(rec_id, "已通过")
                        st.rerun()
                    if col2.button("❌ 拒绝", key=f"reject_{rec_id}"):
                        final_reason = reason if reason.strip() else "无"
                        update_status(rec_id, "已拒绝", final_reason)
                        st.rerun()
                st.markdown("---")
                
        st.markdown("### 🗑️ 管理所有记录")
        with st.expander("点击展开管理（可删除记录）"):
            if not reservations:
                st.write("暂无记录可管理。")
            else:
                for record in reservations:
                    rec_id = record['id']
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        # 新增：在删除列表里也显示手机号
                        st.write(f"[{record.get('status')}] **{record['user']}** ({record.get('phone', '未提供')}) - {record['room']} ({record['start_date']}至{record['end_date']})")
                    with col_btn:
                        if st.button("删除", key=f"del_{rec_id}"):
                            delete_record(rec_id)
                            st.rerun()
                    st.markdown("---")
    elif pwd != "":
        st.error("密码错误！")
