import os
import sys

from utils.user_data_manager import UserDataManager
from loguru import logger

# 增加全局日志配置
logger.remove()      # 清掉默认配置

# 1. 日志文件：只写 WARNING 和 ERROR
logger.add(
    "logs/{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    compression="zip",
    enqueue=True,
    encoding="utf-8",
    filter=lambda rec: rec["level"].no >= 30          # 30=WARNING
)

# 2. 控制台：保持 INFO 及以上
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

def main():
    user_data_file = 'user_data.json'
    user_manager = UserDataManager(user_data_file)
    os.makedirs("logs", exist_ok=True)

    if not user_manager.user_datas:
        logger.warning("未找到用户数据文件或用户数据为空，将创建新的用户数据")
        user_manager.user_datas = []
    else:
        logger.info("加载用户数据成功")
        for user in user_manager.user_datas:
            logger.info(f"用户: {user['userName']}")

    add_user = input("是否新增用户 (y/n): ").strip().lower()
    if add_user == 'y':
        logger.info("开始添加新用户")
        user_manager.add_new_user()
        logger.info("新用户添加完成")


    logger.info("开始处理用户数据")
    for user in user_manager.user_datas:
        logger.info(f"处理用户: {user['userName']}")
        user_manager.process_user(user)
    logger.info("用户数据处理完成")

    logger.info("正在保存用户数据")
    user_manager.write_user_data()
    logger.info("用户数据保存完成")

    logger.info("开始处理用户报名任务")
    user_manager.sign_up()
    logger.info("所有用户任务处理完成")

if __name__ == "__main__":
    main()
