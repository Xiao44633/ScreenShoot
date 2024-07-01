import socket
import pickle
import zlib
import threading
from PIL import Image, ImageTk
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
    resized_image = image.resize((new_width, new_height), Image.LANCZOS)
    return resized_image


# GUI类
class ImageDisplay:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Live Screenshots")
        self.photo_labels = {}
        self.client_windows = {}
        self.client_count = 0

        # 显示客户端数量的标签
        self.client_count_label = tk.Label(self.root, text=f"Clients connected: {self.client_count}")
        self.client_count_label.pack()

    def create_client_window(self, client_data):
        username = client_data['username']
        host_mac = client_data['host_mac']
        window_title = f"{username} ({host_mac})"
        client_window = tk.Toplevel(self.root)
        client_window.title(window_title)
        photo_label = tk.Label(client_window)
        photo_label.pack()
        self.photo_labels[host_mac] = photo_label
        self.client_windows[host_mac] = client_window

        # 更新客户端数量标签
        self.client_count += 1
        self.client_count_label.config(text=f"Clients connected: {self.client_count}")

    def update_gui(self, host_mac, image_data):
        try:
            image = Image.open(io.BytesIO(image_data))
            image = resize_image(image, 400, 300)  # 调整图像大小
            photo = ImageTk.PhotoImage(image)
            self.photo_labels[host_mac].config(image=photo)
            self.photo_labels[host_mac].image = photo
            print(f"Image updated successfully for client {host_mac}.")
        except Exception as e:
            print(f"Failed to update image for client {host_mac}: {e}")

    def run(self):
        self.root.mainloop()  # 开始主事件循环


def save_screenshot(client_data, screenshot_data):
    if client_data is None:
        print("Client data is None. Screenshot will not be saved.")
        return

    sanitized_mac = client_data['host_mac'].replace(":", "_")
    user_dir = os.path.join(screenshot_dir, client_data['username'], sanitized_mac)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(user_dir, f"screenshot_{timestamp}.png")

    try:
        image = Image.open(io.BytesIO(screenshot_data))
        image.save(screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
    except Exception as e:
        print(f"Error saving screenshot: {e}")


def recv_all(conn):
    data = b''
    raw_msglen = conn.recv(4)
    if not raw_msglen:
        return None
    msglen = int.from_bytes(raw_msglen, 'big')
    while len(data) < msglen:
        part = conn.recv(msglen - len(data))
        if not part:
            return None
        data += part
    return data


def handle_client(conn, addr, gui_display):
    global clients
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
                gui_display.create_client_window(data['data'])
            elif data['action'] == 'screenshot':
                mac_address = data['data']['mac_address']
                client_data = clients.get(mac_address)
                if client_data:
                    screenshot_data = zlib.decompress(data['data']['screenshot'])
                    save_screenshot(client_data, screenshot_data)
                    response = {'status': 'received'}
                    conn.sendall(len(pickle.dumps(response)).to_bytes(4, 'big') + pickle.dumps(response))
                    gui_display.update_gui(mac_address, screenshot_data)
                else:
                    print(f"No client data found for MAC address {mac_address}")
                    response = {'status': 'client_not_registered'}
                    conn.sendall(len(pickle.dumps(response)).to_bytes(4, 'big') + pickle.dumps(response))
        except Exception as e:
            print(f"Error: {e}")
            break
    conn.close()


def start_server(gui_display):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 9999))
    server.listen(5)
    server.settimeout(1)

    print("Server listening on port 9999")

    while server_running.is_set():
        try:
            conn, addr = server.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr, gui_display))
            client_thread.start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Error accepting connection: {e}")
            continue
    server.close()


if __name__ == "__main__":
    gui_display = ImageDisplay()
    server_thread = threading.Thread(target=start_server, args=(gui_display,))
    server_thread.start()
    gui_display.run()
