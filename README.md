# PU-SignUpBot
自动报名pu口袋校园的python脚本



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

## 代码情况

会多线程的发请求，报名成功会停止

如果一直没有报名成功，会持续报名60s防止服务器原因导致的报名失败

## TODO

+ 1.处理一下因为服务器原因导致登陆被挤掉的情况

+ 2.处理更多异常情况和返回值
