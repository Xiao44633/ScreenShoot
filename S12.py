import socket
import pickle
import zlib
import threading
from PIL import Image ,ImageTk
import io
import os
from datetime import datetime
import tkinter as tk

# 存储截图的目录
screenshot_dir = "screenshots"

# 创建截图存储目录
if not os.path.exists(screenshot_dir):
    os.makedirs(screenshot_dir)

clients = {}
server_running = threading.Event()
server_running.set()


def resize_image(image, max_width, max_height):
    """
    Resize the image to fit within the specified width and height while maintaining aspect ratio.
    """
    original_width, original_height = image.size
    ratio = min(max_width / original_width, max_height / original_height)
    new_width = int(original_width * ratio)
    new_height = int(original_height * ratio)
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return resized_image


# GUI类
class ImageDisplay:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Live Screenshots")
        self.canvas_width = 800  # 定义画布宽度
        self.canvas_height = 600  # 定义画布高度
        self.canvas = tk.Canvas(self.root, width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack()
        self.photo = None  # 初始化为 None，确保引用持久存在


    def update_gui(self, image_data):
        # 确保在 GUI 线程（主线程）中执行图像更新
        try:
            image = Image.open(io.BytesIO(image_data))
            image = resize_image(image, self.canvas_width, self.canvas_height)  # 调整图像大小
            self.photo = ImageTk.PhotoImage(image)
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
            self.canvas.image = self.photo
            print("Image updated successfully.")  # 成功更新时打印信息
        except Exception as e:
            print(f"Failed to update image: {e}")  # 异常时打印错误信息

    def update_image(self, image_data):
        # 使用 after 调用 update_gui 来确保在正确的线程中执行
        self.root.after(0, self.update_gui, image_data)

    def run(self):
        self.root.mainloop()  # 开始主事件循环

# 初始化GUI
#gui_display = ImageDisplay()

def save_screenshot(client_data, screenshot_data):
    if client_data is None:
        print("Client data is None. Screenshot will not be saved.")
        return

    # 替换MAC地址中的冒号
    sanitized_mac = client_data['host_mac'].replace(":", "_")

    # 创建以用户名和MAC地址命名的目录
    user_dir = os.path.join(screenshot_dir, client_data['username'], sanitized_mac)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    # 以时间戳命名截图文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(user_dir, f"screenshot_{timestamp}.png")

    # 保存图像
    try:
        image = Image.open(io.BytesIO(screenshot_data))
        image.save(screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        gui_display.update_image(screenshot_data)  # 更新GUI显示
    except Exception as e:
        print(f"Error saving screenshot: {e}")


def recv_all(conn):
    data = b''
    # 先接收数据长度
    raw_msglen = conn.recv(4)
    if not raw_msglen:
        return None
    msglen = int.from_bytes(raw_msglen, 'big')
    # 再根据数据长度接收完整的数据
    while len(data) < msglen:
        part = conn.recv(msglen - len(data))
        if not part:
            return None
        data += part
    return data


def handle_client(conn, addr):
    while server_running.is_set():
        try:
            data = recv_all(conn)
            if not data:
                break

            data = pickle.loads(data)
            if data['action'] == 'register':
                mac_address = data['data']['host_mac']
                clients[mac_address] = data['data']
                response = {'status': 'registered'}
                conn.sendall(len(pickle.dumps(response)).to_bytes(4, 'big') + pickle.dumps(response))
                print(f"Client {addr} registered with data: {data['data']}")
            elif data['action'] == 'screenshot':
                mac_address = data['data']['mac_address']
                client_data = clients.get(mac_address)
                if client_data:
                    screenshot_data = zlib.decompress(data['data']['screenshot'])

                    # 将接收到的截图数据保存到本地文件，以便调试
                    with open('received_screenshot_data.bin', 'wb') as f:
                        f.write(screenshot_data)

                    save_screenshot(client_data, screenshot_data)
                    response = {'status': 'received'}
                    conn.sendall(len(pickle.dumps(response)).to_bytes(4, 'big') + pickle.dumps(response))
                else:
                    print(f"No client data found for MAC address {mac_address}")
                    response = {'status': 'client_not_registered'}
                    conn.sendall(len(pickle.dumps(response)).to_bytes(4, 'big') + pickle.dumps(response))
        except Exception as e:
            print(f"Error: {e}")
            break
    conn.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 9999))
    server.listen(5)
    server.settimeout(1)  # 设置超时时间以便定期检查server_running状态
    print("Server listening on port 9999")

    while server_running.is_set():
        try:
            conn, addr = server.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error accepting connection: {e}")
            continue
    server.close()


def listen_for_exit():
    global server_running
    while True:
        command = input("Enter 'exit' to stop the server: ")
        if command.strip().lower() == 'exit':
            server_running.clear()
            break


if __name__ == "__main__":
    gui_display = ImageDisplay()  # 创建GUI实例

    server_thread = threading.Thread(target=start_server)
    server_thread.start()

    gui_display.run()  # 运行GUI

    listen_for_exit()
    server_thread.join()
    print("Server has been stopped.")
