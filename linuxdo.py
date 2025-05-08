"""
cron: 0 */6 * * *
new Env("Linux.Do 签到")
"""
import os
import random
import time
import functools
import sys
import requests
import re
from playwright.sync_api import sync_playwright
from notify import send
import logging
import gc


os.environ.pop("DISPLAY", None)
os.environ.pop("DYLD_LIBRARY_PATH", None)


# 配置 logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# 创建控制台 Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
# 将两个 Handler 添加到 logger
logger.addHandler(console_handler)


USERNAME = os.environ.get("LINUXDO_USERNAME")
PASSWORD = os.environ.get("LINUXDO_PASSWORD")
BROWSE_ENABLED = os.environ.get("BROWSE_ENABLED", "true").strip().lower() not in ['false', '0', 'off']
if not USERNAME:
    USERNAME = os.environ.get('USERNAME')
if not PASSWORD:
    PASSWORD = os.environ.get('PASSWORD')
HOME_URL = "https://linux.do/"
LOGIN_URL = "https://linux.do/login"


def retry_decorator(retries=3):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:  # 最后一次尝试
                        logger.error(f"函数 {func.__name__} 最终执行失败: {str(e)}")
                    logger.warning(f"函数 {func.__name__} 第 {attempt + 1}/{retries} 次尝试失败: {str(e)}")
                    time.sleep(1)
            return None

        return wrapper

    return decorator


class LinuxDoBrowser:
    __slots__ = ["pw", "browser", "context", "topic_list"]
    
    def __init__(self) -> None:
        self.pw = sync_playwright().start()
        self.browser = self.pw.firefox.launch(headless=True, timeout=30000,
            firefox_user_prefs={
                'javascript.enabled': True,
                'network.http.use-cache': True
            },
            args=['--disable-gpu', '--single-process', '--enable-low-end-device-mode']
            )
        self.context = self.browser.new_context(
            java_script_enabled=True,
            ignore_https_errors=True,
            extra_http_headers={'Accept-Encoding': 'gzip'}
        )

    def login(self):
        logger.info("开始登录")
        page = self.context.new_page()
        success = False
        try:
            page.goto(LOGIN_URL)
            time.sleep(random.uniform(5.0, 8.0))
            page.fill("#login-account-name", USERNAME)
            time.sleep(random.uniform(2.0, 3.0))
            page.fill("#login-account-password", PASSWORD)
            time.sleep(random.uniform(2.0, 3.0))
            page.click("#login-button")
            time.sleep(random.uniform(9.0, 11.0))
            user_ele = page.query_selector("#current-user")
            if not user_ele:
                logger.error("登录失败")
            else:
                logger.info("登录成功")
                time.sleep(random.uniform(2.0, 3.0))
                self.topic_list = [topic.get_attribute("href") for topic in page.query_selector_all("#list-area .title")[:30]]
                success = True
        finally:
            page.close()
            gc.collect()
            time.sleep(random.uniform(2.0, 3.0))

        return success
            
    def click_topic(self):
        logger.info(f"发现 {len(self.topic_list)} 个主题帖")
        for topic in self.topic_list:
            self.click_one_topic(topic)

    @retry_decorator()
    def click_one_topic(self, topic_url):
        page = self.context.new_page()
        try:
            page.goto(HOME_URL + topic_url)
            if random.random() < 0.3:  # 0.3 * 30 = 9
                self.click_like(page)
            self.browse_post(page)
        finally:
            page.close()
            gc.collect()
            time.sleep(random.uniform(2.0, 3.0))

    def browse_post(self, page):
        prev_url = None
        # 开始自动滚动，最多滚动10次
        for _ in range(10):
            # 随机滚动一段距离
            scroll_distance = random.randint(550, 650)  # 随机滚动 550-650 像素
            logger.info(f"向下滚动 {scroll_distance} 像素...")
            page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            logger.info(f"已加载页面: {page.url}")

            if random.random() < 0.03:  # 33 * 4 = 132
                logger.info("随机退出浏览")
                break

            # 检查是否到达页面底部
            at_bottom = page.evaluate("window.scrollY + window.innerHeight >= document.body.scrollHeight")
            current_url = page.url
            if current_url != prev_url:
                prev_url = current_url
            elif at_bottom and prev_url == current_url:
                logger.info("已到达页面底部，退出浏览")
                break

            # 动态随机等待
            wait_time = random.uniform(2, 4)  # 随机等待 2-4 秒
            logger.info(f"等待 {wait_time:.2f} 秒...")
            time.sleep(wait_time)

    def run(self):
        if not self.login(): # 登录
            logger.error("登录失败，程序终止")
            sys.exit(1)  # 使用非零退出码终止整个程序
        
        if BROWSE_ENABLED:
            self.click_topic() # 点击主题
            logger.info("完成浏览任务")
            
        self.send_notifications(BROWSE_ENABLED) # 发送通知

    def click_like(self, page):
        try:
            # 专门查找未点赞的按钮
            like_button = page.locator('.discourse-reactions-reaction-button[title="点赞此帖子"]').first
            if like_button:
                logger.info("找到未点赞的帖子，准备点赞")
                like_button.click()
                logger.info("点赞成功")
                time.sleep(random.uniform(1, 2))
            else:
                logger.info("帖子可能已经点过赞了")
        except Exception as e:
            logger.error(f"点赞失败: {str(e)}")

    def send_notifications(self, browse_enabled):
        status_msg = "✅登录成功"
        if browse_enabled:
            status_msg += " + 浏览任务完成"
        send("linuxdo签到日志：", status_msg)


if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("Please set USERNAME and PASSWORD")
        exit(1)
    l = LinuxDoBrowser()
    l.run()
