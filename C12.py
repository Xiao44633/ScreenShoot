import socket
import os
import time
import pyautogui
import pickle
import zlib
import uuid
from threading import Thread
from PIL import Image
import io
import hashlib  # 导入 hashlib 模块

# 客户端参数配置
config = {
    'username': 'test_user',
    'password': 'test_pass',
    'server_ip': '127.0.0.1',
    'server_port': 9999,
    'monitor_frequency': 5  # 监控频率，以秒为单位
}

# 获取主机信息
config['host_ip'] = socket.gethostbyname(socket.gethostname())
config['host_mac'] = ':'.join(
    ['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 2 * 6, 2)][::-1])


def send_data(data):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((config['server_ip'], config['server_port']))
            serialized_data = pickle.dumps(data)
            # 发送数据长度和数据
            s.sendall(len(serialized_data).to_bytes(4, 'big') + serialized_data)
            response_length = s.recv(4)
            if not response_length:
                return None
            response_length = int.from_bytes(response_length, 'big')
            response = s.recv(response_length)
            return pickle.loads(response)
    except Exception as e:
        print(f"Error during sending data: {e}")
        return None


def register():
    try:
        # 使用 hashlib 计算密码的 SHA-1 哈希值
        password_hash = hashlib.sha1(config['password'].encode()).hexdigest()
        # 将哈希值作为密码发送
        config['password'] = password_hash

        response = send_data({'action': 'register', 'data': config})
        if response and response.get('status') == 'registered':
            print("Client registered successfully.")
            return True
        else:
            print("Client registration failed.")
            return False
    except Exception as e:
        print(f"Error during registration: {e}")
        return False


def capture_and_send():
    while True:
        try:
            # 截屏
            screenshot = pyautogui.screenshot()

            # 转换截图对象为字节流
            img_byte_array = io.BytesIO()
            screenshot.save(img_byte_array, format='PNG')
            screenshot_bytes = img_byte_array.getvalue()

            # 压缩图像
            compressed_screenshot = zlib.compress(screenshot_bytes, level=9)

            response = send_data({
                'action': 'screenshot',
                'data': {
                    'mac_address': config['host_mac'],
                    'screenshot': compressed_screenshot
                }
            })
            print(response)
        except Exception as e:
            print(f"Error during screenshot capture and send: {e}")

        # 等待监控频率时间
        time.sleep(config['monitor_frequency'])


def start_monitoring():
    monitor_thread = Thread(target=capture_and_send)
    monitor_thread.daemon = True  # 设置线程为守护线程
    monitor_thread.start()


if __name__ == "__main__":
    if register():
        start_monitoring()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Client stopped by user.")