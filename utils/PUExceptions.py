
class BaseException(Exception):
    """
    Base Exception class
    """
    def __init__(self, msg,**kwargs):
        super().__init__(msg)
        self.kwargs = kwargs
        self.msg = msg
    def __str__(self):
        return f"ERROR INFO：{self.msg}"



class ActivityIDsEmptyError(BaseException):
    """
    用户没有要加入的活动
    """
    def __init__(self, username):
        self.username = username
        super().__init__(msg = f"用户：{username} 的活动列表为空！！")

