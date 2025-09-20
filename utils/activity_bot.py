import threading
import requests
import time
from datetime import datetime, timedelta
from utils.headers import HEADERS_ACTIVITY, HEADERS_ACTIVITY_INFO
from loguru import logger
from typing import Dict, Optional
from concurrent.futures import ThreadPoolExecutor


class ActivityBot:
    def __init__(self, userData: Dict):
        """
        活动报名机器人
        :param userData: 用户数据，包含 userName、password、sid、token、email 等
        """
        self.user_data = userData
        self.cur_token = userData.get("token", "")
        self.activity_url = "https://apis.pocketuni.net/apis/activity/join"
        self.info_url = "https://apis.pocketuni.net/apis/activity/info"
        self.email = userData.get("email", "")
        self.signup_flags = {}  # 记录每个活动的报名状态
        self.debug = False
        self.debug_time = datetime.now() + timedelta(seconds=15)

        # 线程锁，避免多线程同时写入
        self._lock = threading.Lock()

        # 初始化 token
        if not self.cur_token:
            self._refresh_token()

    def _refresh_token(self) -> bool:
        """
        刷新 token，最多重试 5 次
        :return: True 表示获取成功，False 表示失败
        """
        for attempt in range(5):
            try:
                from utils.tools import get_token
                self.cur_token = get_token(self.user_data)
                if self.cur_token:
                    logger.info(f"用户 {self.user_data['userName']} Token 刷新成功")
                    return True
                logger.warning(f"用户 {self.user_data['userName']} 第 {attempt + 1} 次 Token 获取失败")
            except Exception as e:
                logger.error(f"用户 {self.user_data['userName']} Token 获取异常: {str(e)}")
            time.sleep(1)

        logger.error(f"用户 {self.user_data['userName']} Token 获取失败，已达最大重试次数")
        return False

    def _get_headers(self) -> Dict:
        """
        构造请求头
        :return: dict 格式的请求头
        """
        headers = HEADERS_ACTIVITY.copy()
        headers["Authorization"] = f"Bearer {self.cur_token}:{self.user_data.get('sid')}"
        return headers

    def get_join_start_time(self, activity_id: str) -> Optional[datetime]:
        """
        获取活动的报名开始时间
        :param activity_id: 活动 ID
        :return: datetime 对象，如果失败返回 None
        """
        if self.debug:
            return self.debug_time

        try:
            headers = HEADERS_ACTIVITY_INFO.copy()
            headers["Authorization"] = f"Bearer {self.cur_token}:{self.user_data.get('sid')}"
            payload = {"id": activity_id}

            logger.info(f"用户 {self.user_data['userName']} 获取活动 {activity_id} 开始时间")
            response = requests.post(self.info_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            join_start_time_str = response.json().get("data", {}).get("baseInfo", {}).get("joinStartTime")
            if join_start_time_str:
                start_time = datetime.strptime(join_start_time_str, '%Y-%m-%d %H:%M:%S')
                logger.info(f"用户 {self.user_data['userName']} 活动 {activity_id} 开始时间: {start_time}")
                return start_time

        except Exception as e:
            logger.error(f"用户 {self.user_data['userName']} 获取活动 {activity_id} 信息失败: {str(e)}")

        return None

    def _send_signup_request(self, activity_id: str) -> bool:
        """
        发送报名请求
        :param activity_id: 活动 ID
        :return: True 表示报名成功/已报名，False 表示失败
        """
        if self.signup_flags.get(activity_id):
            return True

        try:
            data = {"activityId": activity_id}
            headers = self._get_headers()

            response = requests.post(self.activity_url, headers=headers, json=data, timeout=10)

            if response.status_code != 200:
                logger.warning(f"用户 {self.user_data['userName']} 报名请求失败: {response.status_code}")
                return False

            response_text = response.text
            logger.info(f"用户 {self.user_data['userName']} 报名响应: {response_text}")

            if '"message":"成功"' in response_text and "报名成功" in response_text:
                # 报名成功
                with self._lock:
                    self.signup_flags[activity_id] = True
                    logger.success(f"用户 {self.user_data['userName']} 活动 {activity_id} 报名成功！")
                    self._send_email_notification(activity_id)
                return True

            elif "您已报名" in response_text:
                # 已经报名过
                with self._lock:
                    self.signup_flags[activity_id] = True
                    logger.info(f"用户 {self.user_data['userName']} 已报名活动 {activity_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"用户 {self.user_data['userName']} 报名请求异常: {str(e)}")
            return False

    def _send_email_notification(self, activity_id: str):
        """
        报名成功后发送邮件通知
        :param activity_id: 活动 ID
        """
        try:
            from config import ENABLE_EMAIL_NOTIFICATION
            if not (ENABLE_EMAIL_NOTIFICATION and self.email and self.email.strip()):
                return

            from utils.tools import make_email, send_email

            logger.info(f"用户 {self.user_data['userName']} 发送报名成功邮件通知...")
            email_content = make_email(activity_id, self.user_data)

            if email_content and send_email(email_content, self.email):
                logger.success(f"用户 {self.user_data['userName']} 邮件发送成功！")
            else:
                logger.error(f"用户 {self.user_data['userName']} 邮件发送失败")

        except Exception as e:
            logger.error(f"用户 {self.user_data['userName']} 邮件发送异常: {str(e)}")

    def signup(self, activity_id: str):
        """
        报名活动入口
        :param activity_id: 活动 ID
        """
        logger.info(f"用户 {self.user_data['userName']} 开始报名活动 {activity_id}")

        # 确保 token 有效
        if not self.cur_token and not self._refresh_token():
            logger.error(f"用户 {self.user_data['userName']} 无法获取有效 Token，报名中止")
            return

        # 获取活动开始时间
        start_time = self.get_join_start_time(activity_id)
        if not start_time:
            logger.error(f"用户 {self.user_data['userName']} 无法获取活动 {activity_id} 开始时间")
            return

        current_time = datetime.now()
        time_to_start = (start_time - current_time).total_seconds()

        logger.info(f"用户 {self.user_data['userName']} 活动 {activity_id} 距离开始: {time_to_start:.1f} 秒")

        # 等待到活动开始前 60 秒
        if time_to_start > 60:
            sleep_time = time_to_start - 60
            logger.info(f"用户 {self.user_data['userName']} 等待 {sleep_time:.1f} 秒到活动开始前 60 秒")
            time.sleep(sleep_time)

            # 刷新 token
            logger.info(f"用户 {self.user_data['userName']} 刷新 Token 准备报名")
            self._refresh_token()

        # 等待到活动精确开始时间
        current_time = datetime.now()
        time_to_start = (start_time - current_time).total_seconds()
        if time_to_start > 0:
            logger.info(f"用户 {self.user_data['userName']} 等待 {time_to_start:.1f} 秒到活动开始")
            time.sleep(time_to_start - 0.1)

        # 开始抢报名
        self._start_signup_threads(activity_id)

    def _start_signup_threads(self, activity_id: str):
        """
        启动多线程报名
        :param activity_id: 活动 ID
        """
        logger.info(f"用户 {self.user_data['userName']} 开始多线程报名活动 {activity_id}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []

            # 第一轮：快速尝试 3 次
            futures.extend([executor.submit(self._signup_worker, activity_id) for _ in range(5)])

            # 第二轮：每秒一次，最多 10 次
            for i in range(10):
                if self.signup_flags.get(activity_id):
                    break
                futures.append(executor.submit(self._signup_worker, activity_id))
                time.sleep(1)

            # 第三轮：每秒一次，最多 60 次
            for i in range(60):
                if self.signup_flags.get(activity_id):
                    break
                futures.append(executor.submit(self._signup_worker, activity_id))
                time.sleep(1)

            # 等待所有任务完成
            for future in futures:
                try:
                    future.result(timeout=1)
                except:
                    pass

    def _signup_worker(self, activity_id: str) -> bool:
        """
        报名工作线程
        :param activity_id: 活动 ID
        :return: True 表示报名成功，False 表示失败
        """
        max_attempts = 100  # 每个线程最多尝试 100 次

        for attempt in range(max_attempts):
            if self.signup_flags.get(activity_id):
                return True

            try:
                if self._send_signup_request(activity_id):
                    return True
                time.sleep(0.1)  # 短暂延迟避免过于频繁请求

            except Exception as e:
                logger.error(f"用户 {self.user_data['userName']} 报名线程异常: {str(e)}")
                time.sleep(0.1)

        return False
