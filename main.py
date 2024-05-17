from utils.user_data_manager import UserDataManager

def main():
    user_data_file = 'user_data.json'
    user_manager = UserDataManager(user_data_file)

    if not user_manager.user_datas:
        print("无用户数据！")
        user_manager.user_datas = []
    else:
        print("用户数据：")
        for user in user_manager.user_datas:
            print(user['userName'])

    add_user = input("是否新增用户 (y/n): ").strip().lower()
    if add_user == 'y':
        user_manager.add_new_user()
        user_manager.write_user_data()

    user_manager.process_users()
    

if __name__ == "__main__":
    main()
