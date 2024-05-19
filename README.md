# PU-SignUpBot
自动报名pu口袋校园的python脚本

## 注意

这个脚本基于pu的网页端构建，确保你可以通过网页登陆和报名

## 使用方法

### 1.替换个人信息

替换掉`main.py`中的`ActivityBot`类中的

```python
    def __init__(self):
        ...
        self.userData = dataCrypter.decrypt()
        ...
```

```python
self.userData = {'userName': '...', 'password': '...', 'sid': ..., 'device': 'pc'}
```

userName通常是学号，sid可以通过抓包获得

或者使用cryptwood，详情参考[cryptwood](https://github.com/RedForestLonvor/cryptwood)

### 2.替换活动信息

替换掉`activity_ids.txt`中的活动id，活动id可以通过网页端活动的url获得

### 3.运行main.py

运行main.py

## 关于sid

如果使用网页端登陆，那么在选完学校以后，你发现url变成了
```url
https://class.pocketuni.net/#/login?sid=xxxxxxxxxxxxxxxxxx
```

sid就是这里的xxxxxxxxxxxxxxxxxx

此时应该在输入账号密码的界面

## 代码情况

会多线程的发请求，报名成功会停止

如果一直没有报名成功，会持续报名60s防止服务器原因导致的报名失败

## TODO

+ 1.处理一下因为服务器原因导致登陆被挤掉的情况

+ 2.处理更多异常情况和返回值
