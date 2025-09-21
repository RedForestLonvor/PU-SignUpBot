import random
import threading
import requests
import time
import json
from datetime import datetime, timedelta
from utils.headers import HEADERS_ACTIVITY, HEADERS_ACTIVITY_INFO
from loguru import logger
from typing import Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime


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
        self.server_time_offset = 0.0  # 服务器时间偏差

        # 线程锁，避免多线程同时写入
        self._lock = threading.Lock()

        # 初始化 token 和时间同步
        if not self.cur_token:
            self._refresh_token()

        # 同步服务器时间
        self._sync_server_time()

    def _sync_server_time(self) -> None:
        """同步服务器时间，获取时间偏差"""
        try:
            start_time = time.time()
            response = requests.head("https://apis.pocketuni.net/", timeout=5)
            end_time = time.time()

            server_time_str = response.headers.get('Date')
            if server_time_str:
                server_time = parsedate_to_datetime(server_time_str)
                # 考虑网络延迟，使用请求中点时间
                local_time = datetime.fromtimestamp((start_time + end_time) / 2)

                self.server_time_offset = (server_time - local_time).total_seconds()
                logger.info(f"用户 {self.user_data['userName']} 服务器时间偏差: {self.server_time_offset:.3f}秒")
        except Exception as e:
            logger.warning(f"用户 {self.user_data['userName']} 时间同步失败: {e}")
            self.server_time_offset = 0.0

    def _get_corrected_now(self) -> datetime:
        """获取校正后的当前时间"""
        return datetime.now() + timedelta(seconds=self.server_time_offset)

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
        获取活动的报名开始时间（改进版本）
        :param activity_id: 活动 ID
        :return: datetime 对象，如果失败返回 None
        """
        if self.debug:
            return self.debug_time

        for retry in range(3):
            try:
                headers = self._get_headers()
                payload = {"id": activity_id}

                logger.info(f"用户 {self.user_data['userName']} 获取活动 {activity_id} 开始时间 (尝试 {retry + 1}/3)")
                response = requests.post(self.info_url, headers=headers, json=payload, timeout=8)

                if response.status_code == 401:
                    logger.warning(f"用户 {self.user_data['userName']} Token 失效，尝试刷新 (重试 {retry + 1}/3)")
                    if self._refresh_token():
                        continue
                    else:
                        break

                response.raise_for_status()

                data = response.json()
                join_start_time_str = data.get("data", {}).get("baseInfo", {}).get("joinStartTime")

                if join_start_time_str:
                    start_time = datetime.strptime(join_start_time_str, '%Y-%m-%d %H:%M:%S')
                    logger.info(f"用户 {self.user_data['userName']} 活动 {activity_id} 开始时间: {start_time}")
                    return start_time

            except Exception as e:
                logger.warning(f"用户 {self.user_data['userName']} 获取活动信息失败 (重试 {retry + 1}/3): {e}")
                if retry < 2:  # 不是最后一次重试
                    time.sleep(2 ** retry)  # 指数退避

        logger.error(f"用户 {self.user_data['userName']} 获取活动 {activity_id} 信息最终失败")
        return None

    def _monitor_start_time(self,
                            activity_id: str,
                            start_time: Optional[datetime],
                            min_minutes: int = 15,
                            max_minutes: int = 60,
                            buffer_seconds: int = 600) -> Optional[datetime]:
        """
        定时查询活动开始时间，发现变化则更新
        :param activity_id: 活动id
        :param start_time: 开始时间
        :param min_minutes: 最小等待时间
        :param max_minutes: 最大等待时间
        :param buffer_seconds: 小于该时间就返回
        :return: 开始时间
        """
        if not start_time:
            return None

        while True:
            now = self._get_corrected_now()
            time_to_start = (start_time - now).total_seconds()

            # 如果已经很接近开始（<= buffer_seconds），停止低频监控，返回当前 start_time
            if time_to_start <= float(buffer_seconds):
                logger.info(f"用户 {self.user_data['userName']} 活动 {activity_id} 进入最终等待阶段")
                return start_time

            # 计算允许的最大睡眠分钟（留出 buffer_seconds 缓冲）
            max_allowed_minutes = max(1, int((time_to_start - buffer_seconds) / 60))

            # 决定随机区间
            lower = min(min_minutes, max_allowed_minutes)
            upper = min(max_minutes, max_allowed_minutes)

            if upper < 1:
                return start_time

            sleep_minutes = random.randint(max(1, lower), upper)

            logger.info(
                f"用户 {self.user_data['userName']} 等待 {sleep_minutes} 分钟后再次确认开始时间 "
                f"(距离开始 {time_to_start / 60:.1f} 分钟)")

            time.sleep(sleep_minutes * 60)

            # 重新获取活动时间
            new_start = self.get_join_start_time(activity_id)
            if new_start and new_start != start_time:
                logger.warning(
                    f"用户 {self.user_data['userName']} 活动 {activity_id} 开始时间变更: {start_time} -> {new_start}")
                start_time = new_start

    def _precise_wait_until(self, target_time: datetime, advance_ms: int = 50):
        """
        精确等待到目标时间前advance_ms毫秒
        :param target_time: 目标时间
        :param advance_ms: 提前毫秒数
        """
        while True:
            current_time = self._get_corrected_now()
            remaining = (target_time - current_time).total_seconds()

            if remaining <= advance_ms / 1000.0:
                break

            # 如果剩余时间>1秒，粗略等待
            if remaining > 1:
                time.sleep(remaining - 0.5)
            elif remaining > 0.1:
                # 中等精度等待
                time.sleep(0.05)
            else:
                # 高精度等待
                time.sleep(0.001)

    def _parse_signup_response(self, response_text: str) -> Tuple[bool, str]:
        """
        解析报名响应，返回(是否成功, 状态描述)
        :param response_text: 响应文本
        :return: (是否成功, 状态描述)
        """
        try:
            data = json.loads(response_text)
            code = data.get('code')
            message = data.get('message', '')

            # 根据具体的响应码判断
            if code == 0 and ("成功" in message or "报名成功" in str(data)):
                return True, "报名成功"
            elif code == 9405 or "您已报名" in response_text:
                return True, "已报名"
            else:
                return False, f"报名失败: {message} (code: {code})"

        except json.JSONDecodeError:
            # 备用字符串匹配
            if "报名成功" in response_text:
                return True, "报名成功"
            elif "您已报名" in response_text:
                return True, "已报名"
            else:
                return False, f"未知响应: {response_text[:100]}"

    def _send_signup_request(self, activity_id: str) -> bool:
        """
        发送报名请求（改进版本）
        :param activity_id: 活动 ID
        :return: True 表示报名成功/已报名，False 表示失败
        """
        if self.signup_flags.get(activity_id):
            return True

        try:
            data = {"activityId": activity_id}
            headers = self._get_headers()

            # 使用更短的超时时间提高响应速度
            response = requests.post(self.activity_url, headers=headers, json=data, timeout=5)

            if response.status_code != 200:
                logger.warning(f"用户 {self.user_data['userName']} 报名请求失败: HTTP {response.status_code}")
                return False

            # 使用改进的响应解析
            success, status_msg = self._parse_signup_response(response.text)

            if success:
                with self._lock:
                    if not self.signup_flags.get(activity_id):  # 双重检查
                        self.signup_flags[activity_id] = True
                        logger.success(f"用户 {self.user_data['userName']} 活动 {activity_id} {status_msg}！")

                        if "报名成功" in status_msg:
                            self._send_email_notification(activity_id)
                return True
            else:
                logger.debug(f"用户 {self.user_data['userName']} 报名响应: {status_msg}")
                return False

        except requests.exceptions.Timeout:
            logger.warning(f"用户 {self.user_data['userName']} 报名请求超时")
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

            from utils.tools import make_success_email, send_email

            logger.info(f"用户 {self.user_data['userName']} 发送报名成功邮件通知...")
            email_content = make_success_email(activity_id, self.user_data)

            if email_content and send_email(email_content, self.email):
                logger.success(f"用户 {self.user_data['userName']} 邮件发送成功！")
            else:
                logger.error(f"用户 {self.user_data['userName']} 邮件发送失败")

        except Exception as e:
            logger.error(f"用户 {self.user_data['userName']} 邮件发送异常: {str(e)}")

    def _send_fail_email_notification(self, activity_id: str):
        """
        报名失败后发送邮件通知
        :param activity_id: 活动 ID
        """
        try:
            from config import ENABLE_EMAIL_NOTIFICATION
            if not (ENABLE_EMAIL_NOTIFICATION and self.email and self.email.strip()):
                return

            from utils.tools import make_fail_email, send_email

            logger.info(f"用户 {self.user_data['userName']} 发送报名失败邮件通知...")
            email_content = make_fail_email(activity_id, self.user_data)

            if email_content and send_email(email_content, self.email):
                logger.success(f"用户 {self.user_data['userName']} 报名失败邮件发送成功！")
            else:
                logger.error(f"用户 {self.user_data['userName']} 报名失败邮件发送失败")

        except Exception as e:
            logger.error(f"用户 {self.user_data['userName']} 报名失败邮件异常: {str(e)}")

    def signup(self, activity_id: str):
        """
        报名活动入口，自动轮询获取报名时间
        :param activity_id: 活动id
        """
        logger.info(f"用户 {self.user_data['userName']} 开始报名活动 {activity_id}")

        # 确保 token 有效
        if not self.cur_token and not self._refresh_token():
            logger.error(f"用户 {self.user_data['userName']} 无法获取有效 Token，报名中止")
            return

        # 初次获取活动开始时间
        start_time = self.get_join_start_time(activity_id)
        if not start_time:
            logger.error(f"用户 {self.user_data['userName']} 无法获取活动 {activity_id} 开始时间")
            return

        # 启动定时监控，确保时间更新
        monitored_start_time = self._monitor_start_time(activity_id, start_time)
        if not monitored_start_time:
            logger.error(f"用户 {self.user_data['userName']} 监控活动时间失败，报名中止")
            return

        # 计算距离开始的秒数
        current_time = self._get_corrected_now()
        time_to_start = (monitored_start_time - current_time).total_seconds()
        logger.info(f"用户 {self.user_data['userName']} 活动 {activity_id} 距离开始: {time_to_start:.1f} 秒")

        # 等待到活动开始前 60 秒
        if time_to_start > 60:
            sleep_time = time_to_start - 60
            logger.info(f"用户 {self.user_data['userName']} 等待 {sleep_time:.1f} 秒到活动开始前 60 秒")
            time.sleep(max(0.0, sleep_time))

            # 在靠近报名时刷新 token
            logger.info(f"用户 {self.user_data['userName']} 刷新 Token 准备报名")
            self._refresh_token()

        # 精确等待到报名开始时间
        logger.info(f"用户 {self.user_data['userName']} 进入精确等待阶段")
        self._precise_wait_until(monitored_start_time, advance_ms=30)

        # 开始多线程抢报名
        self._start_signup_threads(activity_id)

    def _start_signup_threads(self, activity_id: str):
        """
        启动多线程报名（优化版本）
        :param activity_id: 活动 ID
        """
        logger.info(f"用户 {self.user_data['userName']} 开始多线程报名活动 {activity_id}")

        # 使用更多初始线程，提高成功率
        max_workers = 8
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            # 第一轮：立即发起5个快速请求
            logger.info("启动第一轮快速报名...")
            futures.extend([executor.submit(self._signup_worker, activity_id) for _ in range(5)])

            # 第二轮：每0.5秒一次，持续15次
            logger.info("启动第二轮密集报名...")
            for i in range(15):
                if self.signup_flags.get(activity_id):
                    logger.success("报名成功，停止后续请求")
                    break
                futures.append(executor.submit(self._signup_worker, activity_id))
                time.sleep(0.5)

            # 第三轮：每秒一次，持续45次
            logger.info("启动第三轮持续报名...")
            for i in range(45):
                if self.signup_flags.get(activity_id):
                    logger.success("报名成功，停止后续请求")
                    break
                futures.append(executor.submit(self._signup_worker, activity_id))
                time.sleep(1)

            # 等待所有任务完成
            completed_count = 0
            for future in futures:
                try:
                    result = future.result(timeout=2)
                    if result:
                        completed_count += 1
                except Exception as e:
                    logger.debug(f"报名线程异常: {e}")

            # 最终状态检查
            if self.signup_flags.get(activity_id, False):
                logger.success(f"用户 {self.user_data['userName']} 活动 {activity_id} 报名成功！")
            else:
                logger.error(f"用户 {self.user_data['userName']} 活动 {activity_id} 报名失败，发送失败邮件通知")
                self._send_fail_email_notification(activity_id)

    def _signup_worker(self, activity_id: str) -> bool:
        """
        报名工作线程（优化版本）
        :param activity_id: 活动 ID
        :return: True 表示报名成功，False 表示失败
        """
        max_attempts = 10  # 每个线程最多尝试 10 次

        for attempt in range(max_attempts):
            if self.signup_flags.get(activity_id):
                return True

            try:
                if self._send_signup_request(activity_id):
                    return True

                # 动态调整等待时间：前几次快一些，后面慢一些
                if attempt < 5:
                    time.sleep(0.05)  # 50ms
                elif attempt < 15:
                    time.sleep(0.1)  # 100ms
                else:
                    time.sleep(0.2)  # 200ms

            except Exception as e:
                logger.error(f"用户 {self.user_data['userName']} 报名线程异常: {str(e)}")
                time.sleep(0.1)

        return False
