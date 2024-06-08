import threading
import requests
import time
from datetime import datetime, timedelta
from utils.headers import HEADERS_LOGIN, HEADERS_ACTIVITY, HEADERS_ACTIVITY_INFO

lock = threading.Lock()

class ActivityBot:

    def __init__(self,userData):
        self.login_url = "https://apis.pocketuni.net/uc/user/login"
        self.activity_url = "https://apis.pocketuni.net/apis/activity/join"
        self.info_url = "https://apis.pocketuni.net/apis/activity/info"
        self.userData = userData
        self.curToken = ""
        self.flag = {}
        self.debug = False
        

    def login(self):
        try:
            response = requests.post(self.login_url, headers=HEADERS_LOGIN, json=self.userData)
            response.raise_for_status()
            self.curToken = response.json().get("data", {}).get("token")
            if self.curToken:
                print("线程"+self.userData['userName']+"获取的Token:", self.curToken)
                return self.curToken
            else:
                raise ValueError("Token获取失败")
        except Exception as e:
            print("登录失败:", e)
            return None

    def signup(self, activity_id):
        cnt = 0
        while True:
            cnt += 1
            self.curToken = self.login()
            if self.curToken != None:
                break
            if cnt >= 5:
                break

        if not self.curToken:
            print("无法获取有效的Token, 报名中止")
            return

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
                        print("请求成功,活动:",activity_id , response.text, "请求时间:" ,datetime.now())
                        if(response.text == '{"code":0,"message":"成功","data":{"msg":"PU君提示：报名成功，请留意活动签到时间哦~"}}'):
                            lock.acquire()
                            try:
                                self.flag[activity_id] = True
                            finally:
                                lock.release()

                        if(response.text == '{"code":9405,"message":"您已报名，请勿重复操作","data":{}}'):
                            lock.acquire()
                            try:
                                self.flag[activity_id] = True
                            finally:
                                lock.release()
                        break
                    else:
                        print("报名尝试失败:", response.text)
                        time.sleep(0.1)  # Maintain a short delay to avoid being blocked by the server
                except Exception as e:
                    print("报名过程中出错:", e)
                    time.sleep(0.1)  # Error handling with short delay

        current_time = datetime.now()
        start_time = self.get_join_start_time(activity_id)

        if start_time is None:
            print("未能获取活动开始时间")
            return

        time_to_start = (start_time - current_time).total_seconds()

        if time_to_start <= 60:

            while True :
                self.curToken = self.login()
                if self.curToken != None:
                    break

        else :

            print(datetime.now(),"sleep:",time_to_start - 60)
            time.sleep(time_to_start - 60)

        current_time = datetime.now()
        time_to_start = (start_time - current_time).total_seconds()

        if time_to_start > 0:
            print(datetime.now(), "sleep:", time_to_start - 0)
            time.sleep(time_to_start - 0)

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
            response = requests.post(self.info_url, headers=headers, json=payload)
            join_start_time_str = response.json().get("data", {}).get("baseInfo", {}).get("joinStartTime")
            print(join_start_time_str)
            if join_start_time_str:
                return datetime.strptime(join_start_time_str, '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"获取活动信息失败：{e}")
        return None
