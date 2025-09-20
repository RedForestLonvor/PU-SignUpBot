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

    def get_info(activity_id):
        """
        获得单个活动的详细信息
        :param activity_id: 活动id
        :return: 当前id活动的详细信息
        """
        payload = {"id": activity_id}
        response = requests.post("https://apis.pocketuni.net/apis/activity/info", headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("data", {}).get("baseInfo", {})

    def get_single_activity(activity_id : str, info : Dict):
        """
        筛选获取单个活动的信息
        :param activity_id: 活动id
        :param info: 当前活动的详细信息
        :return:
        """
        a = {"activity_id": activity_id, "分数": info.get("credit"),
             "活动分类": info.get("categoryName"), "举办组织": info.get("creatorName"),
             "活动名称": info.get("name"), "开始报名时间": info.get("joinStartTime"),
             "活动开始时间": info.get("startTime"), "活动结束时间": info.get("endTime"),
             "活动地址": info.get("address"), "可报名人数": info.get("allowUserCount") - info.get("joinUserCount")}
        return a

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
                info = get_info(activity.get("id"))
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

def make_email(info : Dict) -> str:

