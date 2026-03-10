import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
from supabase import create_client, Client

# --- 配置区 ---
st.set_page_config(page_title="农生学院气候室及培养架在线预约系统", layout="wide") 
ADMIN_PASSWORD = "kexueyuan2026"
MAX_USER_DAYS = 120 

BASE_ROOMS = {
    "1号人工气候室": 5,
    "2号人工气候室": 5,
    "工务署玻璃温室": 20
}

# 变量名修改为 B114A
b114a_racks_list = [f"{i}号培养架" for i in range(1, 43)] + [
    "143号培养架", "155号培养架", "166号培养架", 
    "177号培养架", "188号培养架", "199号培养架", 
    "211号培养架", "222号培养架"
]

ROOM_CAPACITIES = BASE_ROOMS.copy()
RACK_CAPACITY = 1  
for rack in b114a_racks_list:
    # 场地前缀修改为 B114A
    ROOM_CAPACITIES[f"B114A-{rack}"] = RACK_CAPACITY

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

# 新增：保存被单独取消的日期
def update_cancelled_dates(record_id, cancelled_dates_str):
    supabase.table("reservations").update({"cancelled_dates": cancelled_dates_str}).eq("id", record_id).execute()

def check_capacity(room, req_start, req_end, data):
    current_date = req_start
    max_cap = ROOM_CAPACITIES[room]
    
    while current_date <= req_end:
        daily_count = 0
        for record in data:
            if record["room"] == room and record.get("status") in ["待审批", "已通过"]:
                # 排除被管理员单独取消的日期
                cancelled = record.get("cancelled_dates") or ""
                if current_date.strftime("%Y-%m-%d") in cancelled:
                    continue
                    
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

def check_user_quota(user_name, phone, req_start, req_end, data):
    req_days = (req_end - req_start).days + 1
    existing_days = 0
    for record in data:
        if record.get("status") in ["待审批", "已通过"]:
            if record.get("user") == user_name or record.get("phone") == phone:
                cancelled = record.get("cancelled_dates") or ""
                try:
                    rec_start = datetime.strptime(record["start_date"], "%Y-%m-%d").date()
                    rec_end = datetime.strptime(record["end_date"], "%Y-%m-%d").date()
                    curr_d = rec_start
                    while curr_d <= rec_end:
                        # 动态计算天数时，扣除被取消的日期
                        if curr_d.strftime("%Y-%m-%d") not in cancelled:
                            existing_days += 1
                        curr_d += timedelta(days=1)
                except:
                    continue
    if existing_days + req_days > MAX_USER_DAYS:
        return True, existing_days
    return False, existing_days

# --- 界面区 ---
st.title("🌱 农生学院气候室及培养架在线预约系统")

reservations = load_data()
tab1, tab2, tab3 = st.tabs(["📝 提交预约", "📅 预约状态与日历", "👨‍💼 管理员后台"])

# --- Tab 1: 提交预约 ---
with tab1:
    st.subheader("填写预约信息")
    
    # 新增：预约成功后的悬停弹窗提示与下载按钮
    if st.session_state.get('show_download_prompt'):
        st.success(f"✅ 线上申请已提交！您预约了 【{st.session_state.get('last_booked_room')}】，当前状态为【待审批】。")
        st.info("⚠️ **下一步重要操作：**\n\n请务必下载下方的《预约申请表》，填写相关信息并签字后，提交至：\n\n**📍 1010办公室 彭宇涛 老师 （18996131636）**")
        
        try:
            # 核心修改：这里改成了读取 .pdf 文件
            with open("application_form.pdf", "rb") as file:
                st.download_button(
                    label="⬇️ 点击下载《预约申请表》PDF版",  # 按钮文字更新
                    data=file,
                    file_name="农生学院气候室预约申请表.pdf",   # 下载后的文件名更新
                    mime="application/pdf"                    # 文件识别码改为 PDF
                )
        except FileNotFoundError:
            st.error("⚠️ 提示：系统找不到 'application_form.pdf' 文件，请联系管理员确认是否已上传至后台。")
            
        if st.button("👌 我已了解并下载，关闭此提示"):
            st.session_state['show_download_prompt'] = False
            st.rerun()
            
        st.markdown("---")
        
    with st.form("reservation_form"):
        user_name = st.text_input("预约人姓名/课题组", placeholder="例如：张三 / 李四课题组")
        phone_number = st.text_input("联系手机号码 (必填)", placeholder="例如：13800138000") 
        
        room_choice = st.selectbox(
            "选择具体场地（💡 支持直接键盘打字搜索，如输入 '143'）：", 
            list(ROOM_CAPACITIES.keys())
        )
        
        dates = st.date_input("选择使用日期区间 (注：结束日期默认至当晚24:00，下一位同学需从次日0:00开始预约)", [])
        
        st.info(f"💡 **管理规定**：为保证公共资源的合理高效利用，避免公共资源长时间被占用，每人（同姓名或同手机号）在线预约天数，合计不能超过 **{MAX_USER_DAYS}** 天。")
        submitted = st.form_submit_button("提交申请")
        
        if submitted:
            if not user_name:
                st.warning("⚠️ 请填写预约人姓名！")
            elif not phone_number:
                st.warning("⚠️ 必须填写联系手机号码才能进行预约！")
            elif len(dates) == 0:
                st.warning("⚠️ 请选择预约日期！")
            else:
                start_date = dates[0]
                end_date = dates[1] if len(dates) > 1 else dates[0]
                
                is_quota_exceeded, used_days = check_user_quota(user_name, phone_number, start_date, end_date, reservations)
                
                if is_quota_exceeded:
                    req_days = (end_date - start_date).days + 1
                    st.error(f"❌ **额度超限拦截**：为保证公共资源的合理高效利用，每人最多预约 {MAX_USER_DAYS} 天！您之前已占用 {used_days} 天，本次申请 {req_days} 天，合计已超过上限。")
                else:
                    is_full, conflict_date = check_capacity(room_choice, start_date, end_date, reservations)
                    
                    if is_full:
                        formatted_date = conflict_date.strftime("%Y年%m月%d日")
                        limit = ROOM_CAPACITIES[room_choice]
                        
                        next_day = (conflict_date + timedelta(days=1)).strftime("%Y年%m月%d日")
                        if limit == 1: 
                            st.error(f"❌ 冲突！【{room_choice}】在 **{formatted_date}** 尚未到期（被占用至当日24:00）。请将您的起始日期延后至 **{next_day}** 或更晚。")
                        else: 
                            st.error(f"❌ 抱歉，【{room_choice}】在 **{formatted_date}** 的预约名额（{limit}人）已满！请避开此日期。")
                    else:
                        new_record = {
                            "user": user_name,
                            "phone": phone_number,
                            "room": room_choice,
                            "start_date": start_date.strftime("%Y-%m-%d"),
                            "end_date": end_date.strftime("%Y-%m-%d"),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "status": "待审批",
                            "reject_reason": "无",
                            "cancelled_dates": ""
                        }
                        insert_record(new_record)
                        
                        st.session_state['show_download_prompt'] = True
                        st.session_state['last_booked_room'] = room_choice
                        st.rerun()

# --- Tab 2: 预约状态与日历 ---
with tab2:
    st.subheader("📅 当月余量及人员看板")
    
    today = datetime.now()
    col_year, col_month, _ = st.columns([1, 1, 3])
    with col_year:
        sel_year = st.selectbox("选择年份", range(today.year, today.year + 3), index=0)
    with col_month:
        sel_month = st.selectbox("选择月份", range(1, 13), index=today.month - 1)
        
    usage_dict = {day: {r: {"count": 0, "users": []} for r in ROOM_CAPACITIES} for day in range(1, 32)}
    
    for r in reservations:
        if r.get("status") in ["待审批", "已通过"]:
            try:
                s_date = datetime.strptime(r["start_date"], "%Y-%m-%d").date()
                e_date = datetime.strptime(r["end_date"], "%Y-%m-%d").date()
                cancelled = r.get("cancelled_dates") or "" # 获取该记录被取消的日期
                
                curr_d = s_date
                while curr_d <= e_date:
                    # 如果这一天没有被取消，才在日历上显示并计数
                    if curr_d.strftime("%Y-%m-%d") not in cancelled:
                        if curr_d.year == sel_year and curr_d.month == sel_month:
                            if r["room"] in usage_dict[curr_d.day]:
                                usage_dict[curr_d.day][r["room"]]["count"] += 1
                                if r["user"] not in usage_dict[curr_d.day][r["room"]]["users"]:
                                    usage_dict[curr_d.day][r["room"]]["users"].append(r["user"])
                    curr_d += timedelta(days=1)
            except:
                continue

    cal = calendar.monthcalendar(sel_year, sel_month)
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    
    header_cols = st.columns(7)
    for idx, day_name in enumerate(weekdays):
        header_cols[idx].markdown(f"**{day_name}**")
        
    st.markdown("---")
    
    for week in cal:
        day_cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                day_cols[i].write("") 
            else:
                with day_cols[i]:
                    with st.container(border=True):
                        st.markdown(f"**{sel_month}月{day}日**")
                        
                        day_has_booking = False 
                        
                        for room, max_cap in ROOM_CAPACITIES.items():
                            booked = usage_dict[day][room]["count"]
                            
                            if booked > 0:
                                day_has_booking = True
                                users_str = "、".join(usage_dict[day][room]["users"])
                                name_display = f"<br><span style='color:gray; font-size:11px; line-height:1.2; display:block;'>👤 {users_str}</span>"
                                
                                # 日历显示文本中的 B114C 修改为 B114A
                                display_name = room.replace("B114A-", "[B114A] ")
                                
                                if booked >= max_cap:
                                    st.markdown(f"<span style='color:red; font-size:12px;'>🔴 {display_name}: 满({booked}/{max_cap})</span>{name_display}", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<span style='color:#FF8C00; font-size:12px;'>🟡 {display_name}: {booked}/{max_cap}</span>{name_display}", unsafe_allow_html=True)
                                    
                        if not day_has_booking:
                            st.markdown("<span style='color:green; font-size:12px;'>🟢 今日全场地空闲</span>", unsafe_allow_html=True)

    st.markdown("---")
    
    with st.expander("点击查看：📝 所有详细预约记录列表"):
        if reservations:
            df_data = []
            for r in reservations:
                status_text = r.get("status")
                cancelled = r.get("cancelled_dates") or ""
                
                if status_text == "已拒绝" and r.get("reject_reason") != "无":
                    status_text += f" (理由: {r['reject_reason']})"
                if cancelled: # 如果有部分取消，在列表里给个提示
                    status_text += f" [注: 已释放部分日期]"
                    
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
                
        # 核心更新：可以针对特定日期取消的详细管理界面
        st.markdown("### 🛠️ 记录管理与日期释放")
        if not reservations:
            st.write("暂无记录可管理。")
        else:
            for record in reservations:
                rec_id = record['id']
                
                # 展开面板，每个记录一个独立的抽屉
                with st.expander(f"[{record.get('status')}] {record['user']} - {record['room']} ({record['start_date']} 至 {record['end_date']})"):
                    st.write(f"📞 联系电话: {record.get('phone', '未提供')} | 🕒 提交时间: {record['timestamp']}")
                    
                    # 生成该预约的所有日期列表
                    try:
                        rec_start_dt = datetime.strptime(record["start_date"], "%Y-%m-%d").date()
                        rec_end_dt = datetime.strptime(record["end_date"], "%Y-%m-%d").date()
                        
                        date_list = []
                        temp_d = rec_start_dt
                        while temp_d <= rec_end_dt:
                            date_list.append(temp_d.strftime("%Y-%m-%d"))
                            temp_d += timedelta(days=1)
                            
                        # 获取已经取消的日期
                        cancelled_str = record.get("cancelled_dates") or ""
                        current_cancelled = [d.strip() for d in cancelled_str.split(",") if d.strip() and d.strip() in date_list]
                        
                        # 重点体验：提供一个多选框供管理员精确操作
                        selected_to_cancel = st.multiselect(
                            "🛑 释放特定日期（选中下方日期，该日期的名额将被释放重新开放）：",
                            options=date_list,
                            default=current_cancelled,
                            key=f"cancel_dates_{rec_id}"
                        )
                        
                        col_save, col_del = st.columns([1, 1])
                        with col_save:
                            if st.button("💾 保存日期释放设置", key=f"save_cancel_{rec_id}"):
                                new_cancelled_str = ",".join(selected_to_cancel)
                                update_cancelled_dates(rec_id, new_cancelled_str)
                                st.success("特定日期释放成功！日历已同步更新。")
                                st.rerun()
                        with col_del:
                            if st.button("🗑️ 彻底删除该整条记录", key=f"del_all_{rec_id}"):
                                delete_record(rec_id)
                                st.rerun()
                    except:
                        st.write("日期数据异常，无法展开详细管理。")
    elif pwd != "":
        st.error("密码错误！")
