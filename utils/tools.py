import random
import time
import requests
from loguru import logger
from typing import Dict, List

from utils.headers import HEADERS_GET_SCHOOL, HEADERS_ACTIVITY


def get_token(userData: Dict) -> str | None:
    """
    登录获取token
    :return: token | None
    """
    import requests
    try:
        logger.info(f"用户 {userData['userName']} 开始登录")
        from utils.headers import HEADERS_LOGIN

        login_url = "https://apis.pocketuni.net/uc/user/login"
        payload = {
            "userName": userData['userName'],
            "password": userData['password'],
            'sid': int(userData.get("sid")),
            "device": "pc",
        }
        response = requests.post(login_url, headers=HEADERS_LOGIN, json=payload)
        response.raise_for_status()

        token = response.json().get("data", {}).get("token")

        if token:
            logger.info(f"用户 {userData['userName']} 登录成功，Token: {token}")
            return token
        else:
            logger.error(f"用户 {userData['userName']} 获取Token失败，响应: {response.text}")
            raise ValueError("Token获取失败")
    except requests.exceptions.HTTPError as e:
        logger.error(f"用户 {userData['userName']} 登录失败，HTTP错误: {str(e)}")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"用户 {userData['userName']} 登录失败，网络错误: {str(e)}，请检查是否是国内的网络环境")
        return None
    except Exception as e:
        logger.error(f"用户 {userData['userName']} 登录失败，未知错误: {str(e)}")
        return None


def get_sid() -> int | None:
    """
    获取用户sid，即学校id
    :return: 如果匹配返回sid，否则返回None
    """
    logger.info("开始获取学校SID")

    def get_school_list() -> Dict:
        """
        获取学校列表
        :return: 所有学校列表
        """
        url = 'https://pocketuni.net/index.php?app=api&mod=Sitelist&act=getSchools'
        response = requests.get(url, headers=HEADERS_GET_SCHOOL)
        return response.json()

    def find_schools(school_list, school_name) -> List[Dict]:
        """
        根据学校名称查找学校
        :param school_list: 学校列表
        :param school_name: 学校名称
        :return: 匹配的学校列表
        """
        matching_schools = [school for school in school_list if school_name in school['name']]
        return matching_schools

    school_name = input("请输入学校全称：")
    for _ in range(3):
        school_list = get_school_list()
        matching_schools = find_schools(school_list, school_name)

        if not matching_schools:
            logger.warning("未找到匹配的学校。")
            school_name = input("请重新输入学校全称：")
            continue

        if len(matching_schools) == 1:
            selected_school = matching_schools[0]
            logger.info(f"自动选择学校: {selected_school['name']}")
        else:
            logger.info(f"找到 {len(matching_schools)} 个匹配的学校，请选择：")
            for i, school in enumerate(matching_schools, start=1):
                print(f"{i}. {school['name']}")
            choice = int(input("请输入选择的序号：")) - 1
            selected_school = matching_schools[choice]
            logger.info(f"用户选择学校: {selected_school['name']}")

        sid = int(selected_school['go_id'])
        logger.info(f"获取学校SID成功: {sid}")
        return sid
    else:
        logger.error("获取学校SID失败，请检查网络或重新运行程序。")
        return None


def get_activity_type(token: str, sid: str) -> List | None:
    """
    获取本学校的活动类型
    :param token: 用户当前会话token
    :param sid: 用户学校id
    :return: 用户学校的活动类型信息
    """
    logger.info("开始获取本学校的活动类型")
    type_url = "https://apis.pocketuni.net/apis/mapping/data"
    payload = {
        "key": "eventFilter",
        "puType": 0
    }
    headers = HEADERS_ACTIVITY.copy()
    headers['Authorization'] = f"Bearer {token}:{sid}"
    try:
        response = requests.post(type_url, headers=headers, json=payload)
        response.raise_for_status()
        res = []
        data = response.json().get("data", {}).get("list", [])
        for d in data:
            if d.get("name","未知") in ["活动分类","参与年级"]:
                res.append(d)
        return res
    except requests.exceptions.HTTPError as e:
        logger.error(f"获取活动类型失败，HTTP错误: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"获取活动类型失败，未知错误: {str(e)}")
        return None


def get_info(activity_id :  str, token : str, sid : str):
    """
    获得单个活动的详细信息
    :param activity_id: 活动id
    :return: 当前id活动的详细信息
    """
    headers = HEADERS_ACTIVITY.copy()
    headers['Authorization'] = f"Bearer {token}" + ":" + str(sid)
    payload = {"id": int(activity_id)}
    try:
        response = requests.post("https://apis.pocketuni.net/apis/activity/info", headers=headers, json=payload)
        response.raise_for_status()
        if response.status_code != 200:
            logger.error(f"获取活动信息失败，响应: {response.text}")
            return {}
    except requests.exceptions.HTTPError as e:
        logger.error(f"获取活动信息失败，HTTP错误: {str(e)}")
        return {}
    return response.json().get("data", {}).get("baseInfo", {})

def get_single_activity(activity_id : str, info : Dict):
    """
    筛选获取单个活动的信息
    :param activity_id: 活动id
    :param info: 当前活动的详细信息
    :return:
    """
    logger.info(f"正在解析活动 {activity_id} 的信息")
    a = {"activity_id": activity_id, "分数": info.get("credit"),
         "活动分类": info.get("categoryName"), "举办组织": info.get("creatorName"),
         "活动名称": info.get("name"), "开始报名时间": info.get("joinStartTime"),
         "活动开始时间": info.get("startTime"), "活动结束时间": info.get("endTime"),
         "活动地址": info.get("address"), "可报名人数": info.get("allowUserCount") - info.get("joinUserCount")}
    logger.info(f"活动{activity_id} 的信息为解析完成")
    return a

def get_allowed_activity_list(user : Dict) -> List:
    """
    获取满足用户筛选需求的活动

    :return: 满足要求的活动id列表
    """
    logger.info("开始获取满足用户筛选条件的活动")
    activity_url = "https://apis.pocketuni.net/apis/activity/list"
    headers = HEADERS_ACTIVITY.copy()
    headers['Authorization'] =f"Bearer {user.get('token')}" + ":" + str(user.get("sid"))
    payload = {
        "page": 1,
        "limit":20,
        "sort": 0,
        "puType": 0,
        "status": 1, # 1未开始，2进行中，3已结束
        "isAudit":[0] # 0不需要审核，1需要审核
    }

    categorys = user.get("categorys",[])
    if categorys:
        payload['categorys'] = categorys
    allowYears = user.get("allowYears",[])
    if allowYears:
        payload['allowYears'] = allowYears
    oids = user.get("oids",[])
    if oids:
        payload['oids'] = oids

    logger.info(f"正在获取满足用户{user.get('userName')}筛选条件的活动，请求参数: {payload}")
    try:
        response = requests.post(activity_url, headers=headers, json=payload)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"获取活动列表失败，HTTP错误: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"获取活动列表失败，未知错误: {str(e)}")
        return []

    def is_valid(info : Dict, college : str) -> bool:
        """
        判断当前活动是否满足用户筛选条件
        :param info: 当前活动的详细信息
        :return: True | False
        """
        if info.get("allowUserCount") - info.get("joinUserCount") <= 0:
            return False
        if info.get("allowTribe"): # 如果有allowTribe（活动部落）直接返回，这种是指定班级的，不需要抢
            return False
        # 虽然在请求时已经指定了状态为1，但是返回活动任然可能不是未开始，所以需要再次判断
        if not info.get("statusName") == '未开始':
            return False
        if info.get("allowCollege") and not college in [t.get("name") for t in info.get("allowCollege")]:
            return False
        return True

    try:
        pages = int(response.json().get('data').get('pageInfo').get("total",0))
    except Exception as e:
        logger.error(f"获取活动列表失败，返回的数据格式错误: {str(e)}")
        return []
    activity_list = []
    try:
        for page in range(1, pages+1):
            payload['page'] = page
            response = requests.post(activity_url, headers=headers, json=payload)
            response.raise_for_status()
            for activity in response.json().get("data", {}).get("list", []):
                info = get_info(activity.get("id"), user.get('token'), user.get('sid'))
                if not is_valid(info,user.get("college")):
                    continue
                activity_list.append(get_single_activity(activity.get("id"), info))

            time.sleep(0.5 + random.random() * (2 - 0.5))
    except requests.exceptions.HTTPError as e:
        logger.error(f"获取活动列表失败，HTTP错误: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"获取活动列表失败，未知错误: {str(e)}")
        return []

    logger.info(f"获取满足用户筛选条件的活动成功，共有{len(activity_list)}个活动")
    return activity_list

def filter_activity_type(user : Dict) -> None:
    """
    获取用户需要筛选的活动类型
    :param user:
    :return: None
    """
    activity_types = get_activity_type(token=user.get('token'), sid=user['sid'])

    for activity_type in activity_types:
        print(f"当前类型: {activity_type.get('name', '未知')}")
        key = activity_type.get('key')

        # 指定参与年级
        if key == 'allowYears':
            year = input("请输入参与年级：")
            user[key].extend(list(
                info.get('id') for info in activity_type.get('infoList', []) if info.get('name') == year))
            continue

        f = input(f"需要特定此类型的活动吗？[y/n]")
        if f == 'n':
            continue
        for idx, info in enumerate(activity_type.get('infoList', [])):
            print(f"{idx}：\n  类型名称：{info.get('name', '未知')}")
            flag = input("是否添加该类型活动? [y/n] ").lower()
            if flag == 'y':
                user[key].append(info.get('id'))

        print("该类型已添加完毕。")
        print("=" * 20)

def make_email(activity_id : str, user : Dict) -> str:
    """
    制作报名成功邮件信息
    :param activity_id: 活动id
    :param user: 用户信息
    :return: 邮件信息
    """
    logger.info("开始制作报名成功邮件信息")
    info = get_single_activity(activity_id, get_info(activity_id, user.get('token'), user.get('sid')))
    
    # 创建邮件内容
    email_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px; }}
            .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 5px; margin-top: 20px; }}
            .activity-info {{ background-color: white; padding: 15px; border-left: 4px solid #4CAF50; margin: 10px 0; }}
            .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 报名成功通知</h1>
            </div>
            
            <div class="content">
                <p>亲爱的 {user.get('userName', '用户')}，</p>
                
                <p>恭喜您！您已成功报名参加以下活动：</p>
                
                <div class="activity-info">
                    <h3>📋 活动详情</h3>
                    <p><strong>活动名称：</strong>{info.get('活动名称', '未知活动')}</p>
                    <p><strong>活动分类：</strong>{info.get('活动分类', '未分类')}</p>
                    <p><strong>举办组织：</strong>{info.get('举办组织', '未知组织')}</p>
                    <p><strong>活动地址：</strong>{info.get('活动地址', '待定')}</p>
                    <p><strong>活动分数：</strong>{info.get('分数', '0')} 分</p>
                    <p><strong>开始报名时间：</strong>{info.get('开始报名时间', '待定')}</p>
                    <p><strong>活动开始时间：</strong>{info.get('活动开始时间', '待定')}</p>
                    <p><strong>活动结束时间：</strong>{info.get('活动结束时间', '待定')}</p>
                </div>
                
                <p><strong>💡 温馨提示：</strong></p>
                <ul>
                    <li>请务必留意活动签到时间，准时参加</li>
                    <li>请携带相关证件按时到达活动地点</li>
                    <li>如有疑问，请联系活动主办方</li>
                </ul>   
                
                <p>祝您活动愉快！</p>
            </div>
            
            <div class="footer">
                <p>此邮件由 PU-SignUpBot 自动发送，请勿回复</p>
            </div>
        </div>
    </body>
    </html>
    """
    logger.info("邮件制作完毕")
    return email_content.strip()


def send_email(email_info : str, addressee : str):
    """
    发送报名成功邮件
    :param email_info: 邮件内容（HTML格式）
    :param addressee: 收件人邮箱地址
    :return: 发送成功返回True，失败返回False
    """
    from dotenv import load_dotenv
    load_dotenv()
    import smtplib
    import os
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.header import Header
    try:
        # 从环境变量获取邮件配置
        smtp_server = "smtp.qq.com"  # QQ邮箱SMTP服务器
        smtp_port = int(os.getenv("INFO_EMAIL_PORT", "465"))  # 默认465端口
        sender_email = os.getenv("INFO_EMAIL_HOST", "").strip('"')
        sender_password = os.getenv("INFO_EMAIL_SMTP_PASS", "").strip('"')
        
        # 检查配置是否完整
        if not sender_email or not sender_password:
            logger.warning("邮件配置不完整，请检查 .env 文件中的 INFO_EMAIL_HOST 和 INFO_EMAIL_SMTP_PASS 配置")
            return False
        
        if not addressee or addressee.strip() == "":
            logger.warning("收件人邮箱地址为空，无法发送邮件")
            return False
            
        # 创建邮件对象
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header('🎉 PU活动报名成功通知', 'utf-8')
        from email.utils import formataddr
        msg['From'] = formataddr(('PU活动助手 ', sender_email))

        msg['To'] = formataddr(("你", addressee))


        # 添加HTML内容
        html_part = MIMEText(email_info, 'html', 'utf-8')
        msg.attach(html_part)
        
        # 连接SMTP服务器并发送邮件
        logger.info(f"正在发送邮件到 {addressee}...")
        
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            
        logger.success(f"邮件发送成功！收件人: {addressee}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"邮件发送失败：SMTP认证错误，请检查邮箱账号和授权码是否正确 - {str(e)}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"邮件发送失败：SMTP错误 - {str(e)}")
        return False
    except Exception as e:
        logger.error(f"邮件发送失败：未知错误 - {str(e)}")
        return False



