import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from utils.single import single_account
from loguru import logger


class UserDataManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.user_datas = self.read_user_data()

    def read_user_data(self):
        """
        读取用户数据
        :return: 用户数据 or None
        """
        logger.info("开始加载用户数据")
        if not os.path.exists(self.file_path):
            logger.warning("未找到用户数据文件，请检查文件路径是否正确")
            return None

        with open(self.file_path, 'r') as file:
            try:
                data = json.load(file)
                if not data:
                    logger.warning("用户数据为空")
                    return None
                return data
            except json.JSONDecodeError:
                logger.error("用户数据格式解析错误")
                return None

    def write_user_data(self) -> None:
        """
        写入用户数据
        :return: None
        """
        with open(self.file_path, 'w', encoding='utf-8') as file:
            json.dump(self.user_datas, file, indent=4)

    def add_new_user(self):
        """
        添加新用户
        :return: None
        """
        logger.info("开始添加新用户")

        from utils.tools import get_sid
        sid = get_sid()

        if sid is None:
            logger.error("获取学校SID失败，无法添加用户")
            return


        user_name = input("请输入userName: ")
        password = input("请输入password: ")

        new_user = {
            'userName': user_name,
            'password': password,
            'sid': sid,
            'device': 'pc',
            'activity_ids': [], # 想要报名的活动id, 自动获取
            'categorys': [],# 想要报名的类别id
            'oids':[], # 想要报名的阻止id
            'cids':[], # 想要报名的院系id
            'allowYears':[] # 想要报名的参与年级
        }

        token = ""
        from utils.tools import get_token
        for i in range(3):
            logger.info("正在尝试登录...")
            token = get_token(new_user)
            if token:
                break
            else:
                logger.error("登录失败，请检查用户名密码是否正确")
                logger.info(f'您还有{2-i}次重试')
                new_user['userName'] = input("请重新输入userName: ")
                new_user['password'] = input("请重新输入password: ")

        if not token:
            logger.error("多次登录失败，请检查用户名密码是否正确。")
            logger.info("或者请去官网重置用户密码")
            return

        new_user["college"] = input("请输入您所在院系的名称，务必保证为全名（如经济管理学院、计算机科学与工程学院...）： ")
        email = input("如果您想在报名成功后通知您，请输入您的邮箱： ")
        new_user["email"] = email if email else ""
        self.user_datas.append(new_user)
        logger.info(f"新用户添加成功: {new_user.get('userName')}")

    def process_user(self,user : Dict) ->  None:
        """
        处理用户报名信息数据，获取用户预报名信息并获取筛选后的活动列表
        :return: None
        """
        logger.info(f"开始处理用户{user.get('userName')}报名信息数据")
        from utils.tools import get_token
        token = get_token(user)
        if not token:
            logger.error("获取token失败，请检查用户名密码是否正确")
            return
        user['token'] = token

        flag = input(f"是否为用户{user.get('userName')}获取活动列表? [y/n]")
        if flag == 'y':
            from utils.tools import get_allowed_activity_list, filter_activity_type
            flag = input(f"是否为用户{user.get('userName')}获取指定类型的活动列表? [y/n]")
            activity_ids = []
            if flag == 'y':
                filter_activity_type( user)
                activities = get_allowed_activity_list(user)
            else:
                activities = get_allowed_activity_list(user)

            print(f"共找到了{len( activities)}个满足需求的活动，以下是详细信息：")
            for i, activity in enumerate(activities):
                print(f"{i+1}: ")
                for key, value in activity.items():
                    print(f"{key}: {value}")
                if input("是否添加该活动? [y/n]") == 'y':
                    activity_ids.append(activity.get('activity_id'))

            user['activity_ids'] = activity_ids
        logger.info(f"用户{user.get('userName')}处理完毕")


    def sign_up(self):
        """
        处理用户报名
        :return: None
        """
        logger.info("开始处理用户报名任务")
        with ThreadPoolExecutor() as executor:
            futures = []
            for user in self.user_datas:

                futures.append(executor.submit(single_account, user))
            for future in futures:
                future.result()  # 等待所有线程完成