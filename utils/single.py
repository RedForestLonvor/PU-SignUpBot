"""
对单独账号的查询活动并抢活动
"""
import threading
from utils.activity_bot import ActivityBot
from utils.PUExceptions import ActivityIDsEmptyError
from loguru import logger

def single_account(user_data:dict):
    logger.info(f"开始处理用户 {user_data['userName']} 的报名请求")
    bot = ActivityBot(user_data)
    try:
        activity_ids = user_data.get('activity_ids',[]) # 获取用户要报名的所有活动id
        if not activity_ids:
            raise ActivityIDsEmptyError(user_data['userName'])
        logger.info(f"用户 {user_data['userName']} 需要报名的活动ID: {activity_ids}")
        threads = []
        for activity_id in activity_ids:
            logger.info(f"用户 {user_data['userName']} 创建活动 {activity_id} 的报名线程")
            thread = threading.Thread(target=bot.signup, args=(activity_id,))
            threads.append(thread)
            thread.start()

        logger.info(f"用户 {user_data['userName']} 等待所有活动报名线程完成")
        for thread in threads:
            thread.join()
        logger.info(f"用户 {user_data['userName']} 所有活动报名线程已完成")
    except ActivityIDsEmptyError as e:
        logger.warning(f"用户 {user_data['userName']} 获取到的活动id为空，可能是因为没有可报名的活动，或者程序出现错误")
        logger.info(f"用户数据: {user_data}")
        return

    