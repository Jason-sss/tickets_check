# 根据现有脚本改写的查询车次脚本

# coding: UTF-8

from datetime import datetime
import os
import json
import httplib2
import re
import argparse
import sys

CITY_CACHE = None
CITY_CACHE_FILE = ".cities"
URL_12306 = 'kyfw.12306.cn'
CITY_LIST_URL_FILE = "/otn/resources/js/framework/station_name.js"
CURRENT_CITY = ""
LOC_CACHE_FILE = ".cur_location"


# 对日期进行补0
def add_zero(date):
	if int(date) < 10:
		date = '0' + str(int(date))
	return str(date)

# 获取当前日期为默认出发日期
def get_default_date():
	date = datetime.now()
	date = [str(date.year),str(add_zero(date.month)),str(add_zero(date.day))]
	date = '-'.join(date)
	return date


# 格式化输入日期,输入错误返回1
def format_input_date(inp):
    # 年份，月份， 日期，其他格式，执行错误
    err_code = [1,2,3,4,5]
    inputs = []

    if not inp:
        return get_default_date()

    # try:
    for each in inp.split('-'):
        inputs.append(each)
    if len(inputs) == 2:
        # print("input=2")
        # 仅输入了月份和日期
        if int(inputs[0]) < 0 or int(inputs[0]) > 12:
            return err_code[1]
        if int(inputs[1]) < 0 or int(inputs[1]) > 31:
            return err_code[2]
        return(str(datetime.now().year) + '-' + add_zero(inputs[0]) + '-' + add_zero(inputs[1]))
    elif len(inputs) == 3:
        # print("input=3",int(inputs[0]), int(inputs[1]), int(inputs[2]))
        # 输入了年月日
        if int(inputs[0]) < datetime.now().year:
            return err_code[0]
        if int(inputs[1]) < 0 or int(inputs[1]) > 12:
            return err_code[1]
        if int(inputs[2]) < 0 or int(inputs[2]) > 31:
            return err_code[2]
        return (str(inputs[0]) + '-' + add_zero(inputs[1]) + '-' + add_zero(inputs[2]))
    else:
        return err_code[3]
    # except:
    #     return err_code[4]


# 加载城市信息
def load_cities():
    global CITY_CACHE
    if CITY_CACHE is not None:
        return CITY_CACHE
    cities = {}
    cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),CITY_CACHE_FILE)
    need_reload = True
    if os.path.exists(cache_file):
        with open(cache_file) as fp:
            cities = json.load(fp)
        if cities:
            need_reload = False

    if need_reload is True:
        conn = httplib2.HTTPSConnectionWithTimeout(URL_12306, timeout=20, disable_ssl_certificate_validation=True)
        conn.request("GET", url=CITY_LIST_URL_FILE)
        response = conn.getresponse()
        if response.code == 200:
            data = response.read().decode()
            for res in re.finditer(r'@[a-z]{3}\|(.+?)\|(.+?)\|[a-z]+?\|[a-z]+?\|[0-9]+?', data):
                city = res.group(1)
                city_code = res.group(2)
                cities[city] = city_code
            with open(cache_file, 'w') as cf:
                json.dump(cities, cf)

    CITY_CACHE = cities
    return cities


# 查看输入城市是否支持
def check_city(city):
    if city in load_cities():
        return True
    return False


# 获取本机出口ip
def get_local_ip():
    url = "jsonip.com"
    conn = httplib2.HTTPSConnectionWithTimeout(url, timeout=20)
    conn.request("GET", url='')
    response = conn.getresponse()

    if response.code == 200:
        data = response.read().decode()
        res = re.search('\d+\.\d+\.\d+\.\d+', data)
        if res:
            return res.group(0)
        return None

# 获取本机地理位置
def get_local_location(refresh=False):
    global CURRENT_CITY
    if CURRENT_CITY:
        return CURRENT_CITY
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOC_CACHE_FILE)
    if os.path.exists(path) and not refresh:
        with open(path, "r") as cf:
            data = cf.read()
            data = json.loads(data)
            CURRENT_CITY = data["data"]["city"][:-1]
    else:
        ip = get_local_ip()
        if ip:
            conn = httplib2.HTTPConnectionWithTimeout("ip.taobao.com", timeout=20)
            url = "/service/getIpInfo.php?ip=" + ip
            conn.request("GET", url)
            response = conn.getresponse()
            if response.code == 200:
                with open(path, "w") as cf:
                    data = json.loads(response.read())
                    json.dump(data,cf)
                    # print(data, file=cf)
                CURRENT_CITY = data["data"]["city"][:-1]

    return CURRENT_CITY

# 查询余票
def ticket_search(to_city, from_city=None, do_date=None, student=False ):
    ticket_type = "ADULT"
    if from_city == None:
        from_city = get_local_location()
        print("Using local city:", from_city)
    if do_date == None:
        do_date = get_default_date()
        print("Using current date:", do_date)
    else:
        print(do_date)
        do_date = format_input_date(do_date)
        print(do_date)
    if not check_city(from_city):
        print("暂不支持该城市:", from_city)
        exit(-1)
    if student:
        ticket_type = '0X00'
    print(do_date, ":", from_city, "->", to_city, "正在查询...")
    from_city = load_cities()[from_city]
    to_city = load_cities()[to_city]

    conn = httplib2.HTTPSConnectionWithTimeout(URL_12306, timeout=30, disable_ssl_certificate_validation=True)
    url_path = '/otn/leftTicket/query?\
leftTicketDTO.train_date={train_time}&\
leftTicketDTO.from_station={from_city}&\
leftTicketDTO.to_station={to_city}&\
purpose_codes={ticket_type}'
    url_path = url_path.format(train_time=do_date, from_city=from_city, to_city=to_city, ticket_type=ticket_type)
    # print(url_path)
    conn.request("GET", url_path)
    response = conn.getresponse()
    if response.code == 200:
        data = json.loads(response.read())
        # print(data["status"])
        if not "data" in data:
            return "未查询到相关车次"
        return data["data"]


# 显示查询结果

def show_trains(data):
    if isinstance(data, str):
        print(data)
        exit(0)

    count = 0
    print("车次\t", "始/终站\t\t", "始发/终到时间\t", "历时\t", "站台\t", "商务座\t",
          "一等\t", "二等\t", "高软\t", "软卧\t", "硬卧\t", "软座\t", "硬座\t", "无座")

    for each_train in data:
        # train_no = re.search( r'[A-Z][0-9]*', each_train["queryLeftNewDTO"]["train_no"][:-2]).group(0)
        train_no = each_train["queryLeftNewDTO"]["station_train_code"]
        start_station = each_train["queryLeftNewDTO"]["start_station_name"]
        end_station = each_train["queryLeftNewDTO"]["end_station_name"]
        off_time = each_train["queryLeftNewDTO"]["start_time"]
        arrive_time = each_train["queryLeftNewDTO"]["arrive_time"]
        duration = each_train["queryLeftNewDTO"]["lishi"]
        start_station_no = each_train["queryLeftNewDTO"]["from_station_no"]
        end_station_no = each_train["queryLeftNewDTO"]["to_station_no"]
        seat_buisness = each_train["queryLeftNewDTO"]["swz_num"]
        seat_first = each_train["queryLeftNewDTO"]["zy_num"]
        seat_second = each_train["queryLeftNewDTO"]["ze_num"]
        seat_sleep_soft_h = each_train["queryLeftNewDTO"]["gr_num"]
        seat_sleep_soft = each_train["queryLeftNewDTO"]["rw_num"]
        seat_sleep_hard = each_train["queryLeftNewDTO"]["yw_num"]
        seat_soft = each_train["queryLeftNewDTO"]["rz_num"]
        seat_hard = each_train["queryLeftNewDTO"]["yz_num"]
        seat_stand = each_train["queryLeftNewDTO"]["wz_num"]

        if off_time != "24:00":
            print(train_no,end='\t')
            print(start_station+'/'+end_station, end='\t\t')
            print(off_time+'/'+arrive_time, end='\t')
            print(duration, end='\t')
            print(start_station_no+'/'+end_station_no, end='\t')
            print(seat_buisness, end='\t')
            print(seat_first, end='\t')
            print(seat_second, end='\t')
            print(seat_sleep_soft_h, end='\t')
            print(seat_sleep_soft, end='\t')
            print(seat_sleep_hard, end='\t')
            print(seat_soft, end='\t')
            print(seat_hard, end='\t')
            print(seat_stand)

            count += 1
    print("共查询到 %d 班车次"%count)


# 引导模式
def guide_mode():
    print("==查询12306余票==")


if __name__ == "__main__":
    print("Your are excuting the source file!")
    parser = argparse.ArgumentParser(description="==查询12306余票==")
    parser.add_argument('-f', '--from_city', type=str, help='出发城市')
    parser.add_argument('-t', '--to_city', type=str, help='目的城市')
    parser.add_argument('-d', '--date', type=str, help='日期格式：2017-03-15')
    parser.add_argument('-s', '--student', action='store_true', help='学生票')
    parser.add_argument('-l', '--city_list', action='store_true', help='查看支持城市列表')

    args = parser.parse_args()
    from_city = args.from_city
    to_city = args.to_city
    do_date = args.date

    if args.city_list:
        i = 0
        for city, code in load_cities().items():
            if i < 15:
                print(city, end=" ")
                i += 1
            else:
                i = 0
                print(city)

    if not to_city:
        guide_mode()
    else:
        if check_city(to_city):
            data = ticket_search(to_city, from_city, do_date, args.student)
            show_trains(data)
        else:
            print("暂不支持该城市:", to_city)

