import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
from supabase import create_client, Client

# --- 配置区 ---
st.set_page_config(page_title="科研设施预约系统", layout="wide") # 页面改宽一点，方便看日历
ADMIN_PASSWORD = "kexueyuan2026"

# 定义不同房间的最大容量（重点修改：不同房间不同容量）
ROOM_CAPACITIES = {
    "1号人工气候室": 5,
    "2号人工气候室": 5,
    "工务署玻璃温室": 20
}

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
    max_cap = ROOM_CAPACITIES[room] # 获取对应房间的容量限制
    
    while current_date <= req_end:
        daily_count = 0
        for record in data:
            if record["room"] == room and record.get("status") in ["待审批", "已通过"]:
                try:
                    rec_start = datetime.strptime(record["start_date"], "%Y-%m-%d").date()
                    rec_end = datetime.strptime(record["end_date"], "%Y-%m-%d").date()
                    if rec_start <= current_date <= rec_end:
                        daily_count += 1
                except:
                    continue
        if daily_count >= max_cap:
            return True, current_date
        current_date += timedelta(days=1)
    return False, None

# --- 界面区 ---
st.title("🌱 科研设施在线预约系统")

reservations = load_data()
tab1, tab2, tab3 = st.tabs(["📝 提交预约", "📅 预约状态与日历", "👨‍💼 管理员后台"])

# --- Tab 1: 提交预约 ---
with tab1:
    st.subheader("填写预约信息")
    with st.form("reservation_form"):
        user_name = st.text_input("预约人姓名/课题组", placeholder="例如：张三 / 李四课题组")
        phone_number = st.text_input("联系手机号码", placeholder="例如：13800138000") 
        # 新增选项：工务署玻璃温室
        room_choice = st.selectbox("选择预约场地", list(ROOM_CAPACITIES.keys()))
        dates = st.date_input("选择使用日期区间", [])
        submitted = st.form_submit_button("提交申请")
        
        if submitted:
            if not user_name:
                st.warning("⚠️ 请填写预约人姓名！")
            elif not phone_number:
                st.warning("⚠️ 请填写联系手机号码！")
            elif len(dates) == 0:
                st.warning("⚠️ 请选择预约日期！")
            else:
                start_date = dates[0]
                end_date = dates[1] if len(dates) > 1 else dates[0]
                
                is_full, conflict_date = check_capacity(room_choice, start_date, end_date, reservations)
                
                if is_full:
                    formatted_date = conflict_date.strftime("%Y年%m月%d日")
                    limit = ROOM_CAPACITIES[room_choice]
                    st.error(f"❌ 抱歉，{room_choice} 在 **{formatted_date}** 的预约名额（{limit}人）已满！")
                else:
                    new_record = {
                        "user": user_name,
                        "phone": phone_number,
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

# --- Tab 2: 预约状态与日历 ---
with tab2:
    st.subheader("📅 当月余量日历看板")
    
    # 1. 月份选择器
    today = datetime.now()
    col_year, col_month, _ = st.columns([1, 1, 3])
    with col_year:
        sel_year = st.selectbox("选择年份", range(today.year, today.year + 3), index=0)
    with col_month:
        sel_month = st.selectbox("选择月份", range(1, 13), index=today.month - 1)
        
    # 2. 计算所选月份每一天的预约人数
    # usage_dict 结构: { 日期(1-31): {"1号人工气候室": 2, "工务署玻璃温室": 5...} }
    usage_dict = {day: {r: 0 for r in ROOM_CAPACITIES} for day in range(1, 32)}
    for r in reservations:
        if r.get("status") in ["待审批", "已通过"]:
            try:
                s_date = datetime.strptime(r["start_date"], "%Y-%m-%d").date()
                e_date = datetime.strptime(r["end_date"], "%Y-%m-%d").date()
                curr_d = s_date
                while curr_d <= e_date:
                    if curr_d.year == sel_year and curr_d.month == sel_month:
                        usage_dict[curr_d.day][r["room"]] += 1
                    curr_d += timedelta(days=1)
            except:
                continue

    # 3. 绘制日历网格
    cal = calendar.monthcalendar(sel_year, sel_month)
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    
    # 画表头
    header_cols = st.columns(7)
    for idx, day_name in enumerate(weekdays):
        header_cols[idx].markdown(f"**{day_name}**")
        
    st.markdown("---")
    
    # 画每一天的小方块
    for week in cal:
        day_cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                day_cols[i].write("") # 空白日期
            else:
                with day_cols[i]:
                    # 也可以用 st.container(border=True) 画个边框
                    with st.container(border=True):
                        st.markdown(f"**{sel_month}月{day}日**")
                        # 遍历每一个房间显示状态
                        for room, max_cap in ROOM_CAPACITIES.items():
                            booked = usage_dict[day][room]
                            # 根据占用率显示不同颜色
                            if booked >= max_cap:
                                st.markdown(f"<span style='color:red; font-size:13px;'>🔴 {room}: 满({booked}/{max_cap})</span>", unsafe_allow_html=True)
                            elif booked > 0:
                                st.markdown(f"<span style='color:#FF8C00; font-size:13px;'>🟡 {room}: {booked}/{max_cap}</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<span style='color:green; font-size:13px;'>🟢 {room}: 空({booked}/{max_cap})</span>", unsafe_allow_html=True)

    st.markdown("---")
    
    # 4. 保留原来的详细列表
    with st.expander("点击查看：📝 所有详细预约记录列表"):
        if reservations:
            df_data = []
            for r in reservations:
                status_text = r.get("status")
                if status_text == "已拒绝" and r.get("reject_reason") != "无":
                    status_text += f" (理由: {r['reject_reason']})"
                df_data.append({
                    "当前状态": status_text,
                    "场地": r["room"],
                    "预约人": r["user"],
                    "手机号码": r.get("phone", "未提供"),
                    "开始日期": r["start_date"],
                    "结束日期": r["end_date"],
                    "提交时间": r["timestamp"]
                })
            df = pd.DataFrame(df_data)
            df = df[["当前状态", "场地", "预约人", "手机号码", "开始日期", "结束日期", "提交时间"]]
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
                    st.write(f"**申请人**: {record['user']} (📞 {record.get('phone', '未提供')}) | **场地**: {record['room']}")
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
                        st.write(f"[{record.get('status')}] **{record['user']}** ({record.get('phone', '未提供')}) - {record['room']} ({record['start_date']}至{record['end_date']})")
                    with col_btn:
                        if st.button("删除", key=f"del_{rec_id}"):
                            delete_record(rec_id)
                            st.rerun()
                    st.markdown("---")
    elif pwd != "":
        st.error("密码错误！")
