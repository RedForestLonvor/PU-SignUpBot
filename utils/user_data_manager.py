import json
import os
from concurrent.futures import ThreadPoolExecutor
from utils.single import single_account
from utils.headers import HEADERS_GET_SCHOOL
import requests

class UserDataManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.user_datas = self.read_user_data()

    def read_user_data(self):
        if not os.path.exists(self.file_path):
            return None

        with open(self.file_path, 'r') as file:
            try:
                data = json.load(file)
                if not data:
                    return None
                return data
            except json.JSONDecodeError:
                return None

    def write_user_data(self):
        with open(self.file_path, 'w') as file:
            json.dump(self.user_datas, file, indent=4)

    @staticmethod
    def get_school_list():
        url = 'https://pocketuni.net/index.php?app=api&mod=Sitelist&act=getSchools'
        response = requests.get(url, headers=HEADERS_GET_SCHOOL)
        return response.json()

    @staticmethod
    def find_schools(school_list, school_name):
        matching_schools = [school for school in school_list if school_name in school['name']]
        return matching_schools

    def get_sid(self):
        school_list = self.get_school_list()
        school_name = input("请输入学校全称：")
        matching_schools = self.find_schools(school_list, school_name)

        if not matching_schools:
            print("未找到匹配的学校。")
            return None

        if len(matching_schools) == 1:
            selected_school = matching_schools[0]
        else:
            print("找到多个匹配的学校，请选择：")
            for i, school in enumerate(matching_schools, start=1):
                print(f"{i}. {school['name']}")
            choice = int(input("请输入选择的序号：")) - 1
            selected_school = matching_schools[choice]

        return int(selected_school['go_id'])

    def add_new_user(self):
        user_name = input("请输入userName: ")
        password = input("请输入password: ")
        sid = self.get_sid()
        new_user = {
            'userName': user_name,
            'password': password,
            'sid': sid,
            'device': 'pc'
        }
        self.user_datas.append(new_user)

    def process_users(self):
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(single_account, user) for user in self.user_datas]
            for future in futures:
                future.result()  # 等待所有线程完成

