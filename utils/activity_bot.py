import threading
import requests
import time
from datetime import datetime, timedelta
from utils.headers import HEADERS_LOGIN, HEADERS_ACTIVITY, HEADERS_ACTIVITY_INFO
from loguru import logger
from typing import Dict

lock = threading.Lock()

class ActivityBot:

    def __init__(self,userData : Dict):
        self.curToken = userData.get("token","")
        if not self.curToken:
            from utils.tools import get_token
            self.curToken = get_token(userData)
        self.activity_url = "https://apis.pocketuni.net/apis/activity/join"
        self.info_url = "https://apis.pocketuni.net/apis/activity/info"
        self.userData = {
            'userName': userData.get("userName"),
            'password': userData.get("password"),
            'sid': userData.get("sid"),
            'device': 'pc',
        }
        self.email = userData.get("email", "")
        self.flag = {}
        self.debug = False


    def signup(self, activity_id):
        """
        报名
        :param activity_id: 活动id
        :return: None
        """
        logger.info(f"用户 {self.userData['userName']} 开始为活动 {activity_id} 报名")
        cnt = 0
        while True:
            cnt += 1
            logger.info(f"用户 {self.userData['userName']} 第 {cnt} 次尝试登录")
            if self.curToken:
                break
            if cnt >= 5:
                logger.error(f"用户 {self.userData['userName']} 登录失败次数达到上限，报名中止")
                break

        if not self.curToken:
            logger.error(f"用户 {self.userData['userName']} 无法获取有效的Token, 报名中止")
            return

        logger.info(f"用户 {self.userData['userName']} 登录成功，开始报名活动 {activity_id}")
        data = {"activityId": activity_id}

        def send_request():
            if self.flag.get(activity_id) == True:
                return
            while True:
                try:
                    headers = HEADERS_ACTIVITY.copy()
                    headers["Authorization"] = f"Bearer {self.curToken}" + ":" + str(self.userData.get("sid"))
                    response = requests.post(self.activity_url, headers=headers, json=data)
                    if response.status_code == 200:
                        logger.info(f"用户 {self.userData['userName']} 请求成功,活动: {activity_id}, 响应: {response.text}, 请求时间: {datetime.now()}")

                        if(response.text == '{"code":0,"message":"成功","data":{"msg":"PU君提示：报名成功，请留意活动签到时间哦~"}}'):
                            lock.acquire()
                            try:
                                self.flag[activity_id] = True
                                logger.info(f"用户 {self.userData['userName']} 报名活动 {activity_id} 成功")
                            finally:
                                lock.release()

                        if(response.text == '{"code":9405,"message":"您已报名，请勿重复操作","data":{}}'):
                            lock.acquire()
                            try:
                                self.flag[activity_id] = True
                                logger.info(f"用户 {self.userData['userName']} 已报名活动 {activity_id}，无需重复报名")
                            finally:
                                lock.release()
                        break
                    else:
                        logger.warning(f"用户 {self.userData['userName']} 报名尝试失败: {response.text}")
                        time.sleep(0.1)  # Maintain a short delay to avoid being blocked by the server
                except Exception as e:
                    logger.error(f"用户 {self.userData['userName']} 报名过程中出错: {str(e)}")
                    time.sleep(0.1)  # Error handling with short delay

        current_time = datetime.now()
        start_time = self.get_join_start_time(activity_id)

        if start_time is None:
            logger.error(f"用户 {self.userData['userName']} 未能获取活动 {activity_id} 的开始时间")
            return

        time_to_start = (start_time - current_time).total_seconds()
        logger.info(f"用户 {self.userData['userName']} 活动 {activity_id} 距离开始时间: {time_to_start} 秒")

        if time_to_start <= 60:
            logger.info(f"用户 {self.userData['userName']} 活动 {activity_id} 即将开始，重新登录获取Token")
            while True :
                self.curToken = self.login()
                if self.curToken != None:
                    break

        else :
            sleep_time = time_to_start - 60
            logger.info(f"用户 {self.userData['userName']} 活动 {activity_id} 等待时间: {sleep_time} 秒, 当前时间: {datetime.now()}")
            time.sleep(sleep_time)

        current_time = datetime.now()
        time_to_start = (start_time - current_time).total_seconds()

        if time_to_start > 0:
            sleep_time = time_to_start
            logger.info(f"用户 {self.userData['userName']} 活动 {activity_id} 等待时间: {sleep_time} 秒, 当前时间: {datetime.now()}")
            time.sleep(sleep_time)

        for _ in range(3):
            threading.Thread(target=send_request).start()
            # time.sleep(0.5)
        for _ in range(10):
            if self.flag.get(activity_id) == True:
                break
            threading.Thread(target=send_request).start()
            time.sleep(1)
        for _ in range(60):
            if self.flag.get(activity_id) == True:
                break
            threading.Thread(target=send_request).start()
            time.sleep(1)

    debugTime = datetime.now() + timedelta(seconds=15)

    def get_join_start_time(self, activity_id):
        if self.debug == True:
            return self.debugTime
        headers = HEADERS_ACTIVITY_INFO.copy()
        headers["Authorization"] = f"Bearer {self.curToken}" + ":" + str(self.userData.get("sid"))
        payload = {"id": activity_id}
        try:
            logger.info(f"用户 {self.userData['userName']} 开始获取活动 {activity_id} 的开始时间")
            response = requests.post(self.info_url, headers=headers, json=payload)
            join_start_time_str = response.json().get("data", {}).get("baseInfo", {}).get("joinStartTime")
            logger.info(f"用户 {self.userData['userName']} 获取活动 {activity_id} 的开始时间响应: {join_start_time_str}")
            if join_start_time_str:
                return datetime.strptime(join_start_time_str, '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logger.error(f"用户 {self.userData['userName']} 获取活动 {activity_id} 信息失败: {str(e)}")
        return None
