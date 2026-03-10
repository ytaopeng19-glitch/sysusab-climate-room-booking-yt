import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
from supabase import create_client, Client

# --- 配置区 ---
st.set_page_config(page_title="农生学院气候室预约系统", layout="wide") 
ADMIN_PASSWORD = "kexueyuan2026"
MAX_USER_DAYS = 120 

# 1. 定义基础场地和它们的容量
BASE_ROOMS = {
    "1号人工气候室": 5,
    "2号人工气候室": 5,
    "工务署玻璃温室": 20
}

# 2. 动态生成 B114C 房间的培养架列表
# 包括 1-42号，以及特定的几个大号架子
b114c_racks_list = [f"{i}号培养架" for i in range(1, 43)] + [
    "143号培养架", "155号培养架", "166号培养架", 
    "177号培养架", "188号培养架", "199号培养架", 
    "211号培养架", "222号培养架"
]

# 3. 将所有场地合并到一个总字典中，用于后台校验
ROOM_CAPACITIES = BASE_ROOMS.copy()
RACK_CAPACITY = 1  # 设定每个独立的培养架最多允许 1 人预约
for rack in b114c_racks_list:
    ROOM_CAPACITIES[f"B114C-{rack}"] = RACK_CAPACITY

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
    max_cap = ROOM_CAPACITIES[room]
    
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

def check_user_quota(user_name, phone, req_start, req_end, data):
    req_days = (req_end - req_start).days + 1
    existing_days = 0
    for record in data:
        if record.get("status") in ["待审批", "已通过"]:
            if record.get("user") == user_name or record.get("phone") == phone:
                try:
                    rec_start = datetime.strptime(record["start_date"], "%Y-%m-%d").date()
                    rec_end = datetime.strptime(record["end_date"], "%Y-%m-%d").date()
                    existing_days += (rec_end - rec_start).days + 1
                except:
                    continue
    if existing_days + req_days > MAX_USER_DAYS:
        return True, existing_days
    return False, existing_days

# --- 界面区 ---
st.title("🌱 农生学院气候室预约系统")

reservations = load_data()
tab1, tab2, tab3 = st.tabs(["📝 提交预约", "📅 预约状态与日历", "👨‍💼 管理员后台"])

# --- Tab 1: 提交预约 ---
with tab1:
    st.subheader("填写预约信息")
    with st.form("reservation_form"):
        user_name = st.text_input("预约人姓名/课题组", placeholder="例如：张三 / 李四课题组")
        phone_number = st.text_input("联系手机号码 (必填)", placeholder="例如：13800138000") 
        
        room_choice = st.selectbox(
            "选择具体场地（💡 支持直接键盘打字搜索，如输入 '143'）：", 
            list(ROOM_CAPACITIES.keys())
        )
        
        # 优化 1：在日期选择器上增加醒目的 24:00 规则提示语
        dates = st.date_input("选择使用日期区间 (注：结束日期默认至当晚24:00，下一位同学需从次日0:00开始预约)", [])
        
        st.info(f"💡 规则提示：为保证公共资源的合理高效利用，避免公共资源长时间被占用。每人（同姓名或同手机号）在线预约天数，合计不能超过 **{MAX_USER_DAYS}** 天。")
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
                    st.error(f"❌ 额度不足！您之前已占用 {used_days} 天，本次申请 {req_days} 天，超过了最高 {MAX_USER_DAYS} 天。")
                else:
                    is_full, conflict_date = check_capacity(room_choice, start_date, end_date, reservations)
                    
                    if is_full:
                        formatted_date = conflict_date.strftime("%Y年%m月%d日")
                        limit = ROOM_CAPACITIES[room_choice]
                        
                        # 优化 2：报错信息更加智能，直接告诉同学应该从哪一天开始预约
                        next_day = (conflict_date + timedelta(days=1)).strftime("%Y年%m月%d日")
                        if limit == 1: # 针对培养架的专属报错语
                            st.error(f"❌ 冲突！【{room_choice}】在 **{formatted_date}** 尚未到期（被占用至当日24:00）。请将您的起始日期延后至 **{next_day}** 或更晚。")
                        else: # 针对气候室的报错语
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
                            "reject_reason": "无"
                        }
                        insert_record(new_record)
                        st.success(f"✅ 申请已提交！您预约了 【{room_choice}】，当前状态为【待审批】。")
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
                curr_d = s_date
                while curr_d <= e_date:
                    if curr_d.year == sel_year and curr_d.month == sel_month:
                        # 兼容处理：确保旧数据如果不在新字典里不会报错
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
                        
                        # 新增逻辑：检查今天是否有任何场地被预约
                        day_has_booking = False 
                        
                        for room, max_cap in ROOM_CAPACITIES.items():
                            booked = usage_dict[day][room]["count"]
                            
                            # 核心修改：只有 booked > 0 (有人预约) 才显示出来
                            if booked > 0:
                                day_has_booking = True
                                users_str = "、".join(usage_dict[day][room]["users"])
                                name_display = f"<br><span style='color:gray; font-size:11px; line-height:1.2; display:block;'>👤 {users_str}</span>"
                                
                                # 为了显示美观，如果是培养架，把前缀修饰一下
                                display_name = room.replace("B114C-", "[B114C] ")
                                
                                if booked >= max_cap:
                                    st.markdown(f"<span style='color:red; font-size:12px;'>🔴 {display_name}: 满({booked}/{max_cap})</span>{name_display}", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<span style='color:#FF8C00; font-size:12px;'>🟡 {display_name}: {booked}/{max_cap}</span>{name_display}", unsafe_allow_html=True)
                                    
                        # 如果遍历完所有场地，发现一个预约都没有，就显示空闲
                        if not day_has_booking:
                            st.markdown("<span style='color:green; font-size:12px;'>🟢 今日全场地空闲</span>", unsafe_allow_html=True)

    st.markdown("---")
    
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




