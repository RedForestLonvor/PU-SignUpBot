"""
对单独账号的抢活动
"""
import threading
from utils.activity_bot import ActivityBot

def single_account(user_data:dict,file_path = "activity_ids.txt"):
    print('线程：'+user_data['userName'])
    pass
    bot = ActivityBot(user_data)
    try:
        with open(file_path, 'r') as file:
            activity_ids = [int(line.strip()) for line in file if line.strip()]
        threads = []
        for activity_id in activity_ids:
            thread = threading.Thread(target=bot.signup, args=(activity_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
    except FileNotFoundError:
        print("线程："+user_data['userName']+"活动ID文件不存在")
    