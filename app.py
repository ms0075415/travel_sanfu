import requests
from bs4 import BeautifulSoup
import schedule
import time
import logging
from datetime import datetime

# LINE Notify token
LINE_NOTIFY_TOKEN = "1kDVvMINkD7slEpOHenWTfzItYUtNKiXvAnSuLT4Y7u"

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Connection': 'keep-alive',
}

# 全局變量
MAX_REQUESTS_PER_HOUR = 600
request_count = 0
start_time = time.time()
filter_input = "11-12"  # 查詢月份
previous_seat_counts = {}

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def filter_by_month(date_str, filter_months):
    if not filter_months:
        return True
    # 去掉日期中的週資訊
    date_str = date_str.split(' ')[0]
    date = datetime.strptime(date_str, "%Y/%m/%d")
    month = date.month
    return str(month) in filter_months

def get_travel_data(filter_input=""):
    url = "https://www.travel4u.com.tw/group/itinerary/MUC13WS-D/products/"
    response = requests.get(url)
    html_content = response.text

    soup = BeautifulSoup(html_content, 'html.parser')
    nav_tab_content = soup.find(id="nav-tabContent")

    data = []
    filter_months = [m.strip() for m in filter_input.split('-')] if filter_input else []

    for row in nav_tab_content.find_all('tr', class_='table-hover'):
        columns = row.find_all('td')
        if len(columns) >= 7:
            序 = columns[0].text.strip()
            出發日 = columns[1].text.strip()
            總機位 = columns[3].text.strip()
            可售機位 = columns[4].text.strip().split()[0]  # 只保留數字部分
            價格 = columns[6].text.strip().split()[-1]

            if filter_by_month(出發日, filter_months):
                data.append({
                    '序': 序,
                    '出發日': 出發日,
                    '總機位': 總機位,
                    '可售機位': int(可售機位),  # 轉換為整數
                    '價格': 價格,
                })

    return data, url

def send_line_notify(message):
    notify_url = "https://notify-api.line.me/api/notify"
    headers = {
        "Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"
    }
    data = {
        "message": message
    }
    response = requests.post(notify_url, headers=headers, data=data)
    if response.status_code != 200:
        logging.error(f"Failed to send message: {response.text}")

def check_website():
    global request_count, start_time, filter_input, previous_seat_counts
    current_time = time.time()
    if current_time - start_time > 3600:
        request_count = 0
        start_time = current_time
    if request_count >= MAX_REQUESTS_PER_HOUR:
        logging.warning("已達到每小時最大請求次數")
        return

    try:
        travel_data, monitored_url = get_travel_data(filter_input)
        
        if travel_data:
            message = "每小時監控-山富：\n"
            for item in travel_data:
                出發日 = item['出發日']
                可售機位 = item['可售機位']

                if 出發日 in previous_seat_counts:
                    previous_count = previous_seat_counts[出發日]
                    if 可售機位 < previous_count:
                        sold_seats = previous_count - 可售機位
                        send_line_notify(f"{出發日} 已售出 {sold_seats} 位")
                
                previous_seat_counts[出發日] = 可售機位

                message += f"{item['出發日']}\n 可售機位：{item['可售機位']} 個, 價格：{item['價格']}\n\n"
            message += f"\n來源網址：{monitored_url}"
            send_line_notify(message)
        else:
            send_line_notify(f"沒有找到符合條件的資料。\n來源網址：{monitored_url}")
        
    except requests.RequestException as e:
        logging.error(f"檢查網站時發生錯誤: {e}")

def daily_summary():
    travel_data, monitored_url = get_travel_data(filter_input)
    
    if travel_data:
        message = "每日監控-山富：\n"
        for item in travel_data:
            message += f"{item['出發日']}\n 可售機位：{item['可售機位']} 個, 價格：{item['價格']}\n\n"
        message += f"\n來源網址：{monitored_url}"
        send_line_notify(message)
    else:
        send_line_notify(f"沒有找到符合條件的資料。\n來源網址：{monitored_url}")

# 設置每小時執行一次檢查
schedule.every().hour.do(check_website)

# 設置每天午夜00:00執行一次整體資訊通知
schedule.every().day.at("00:00").do(daily_summary)

# 主循環
if __name__ == "__main__":
    # 初始執行一次，便於測試
    check_website()
    while True:
        schedule.run_pending()
        time.sleep(1)
