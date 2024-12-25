import sys
import requests
import json
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont

model_name = "llama3.2-vision"

# API线程，用于与服务器进行交互
class ApiThread(QThread):
    # Signal to send the response back to the main thread
    response_received = pyqtSignal(str, bool)

    def __init__(self, user_message):
        super().__init__()
        self.user_message = user_message
        self.conversation = ""  # 存储拼接对话内容
        self.model_response = ""  # 存储模型的拼接回答
        self.done = False

    def run(self):
        try:
            # API请求的URL
            api_url = "http://localhost:11434/api/chat"
            headers = {'Content-Type': 'application/json'}
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": self.user_message}]
            }

            # 循环直到 'done' 为 True
            while not self.done:
                # 向API发送请求
                response = requests.post(api_url, headers=headers, json=payload)

                # 检查API返回是否成功
                if response.status_code != 200:
                    raise Exception(f"Failed to get a valid response from the API, Status Code: {response.status_code}")

                # 逐行处理返回的消息
                try:
                    for line in response.text.splitlines():
                        # 解析每一行的JSON对象
                        response_json = json.loads(line)

                        # 获取返回的内容并拼接到模型的响应中
                        content = response_json['message'].get('content', '')
                        self.model_response += content  # 拼接每个片段

                        # 如果 'done' 为 True，结束对话
                        if response_json.get('done', False):
                            self.done = True
                            self.response_received.emit(self.model_response, self.done)
                            break

                        # 为下一轮消息准备
                        payload['messages'].append({"role": "assistant", "content": content})

                except json.JSONDecodeError as e:
                    print(f"JSON Decode Error: {e}")
                    self.response_received.emit(f"Error: Failed to parse JSON response: {e}", True)
                    return

        except Exception as e:
            print(f"Error: {e}")
            self.response_received.emit(f"Error: {e}\n", True)


# 主聊天窗口
class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()

        # 变量
        self.send_button = None
        self.input_field = None
        self.generating_label = None
        self.chat_display = None
        self.model_label = None
        self.layout = None
        self.api_thread = None

        self.init_ui()
        self.previous_user_message = None  # 保存上次的用户输入，防止重复显示

    def init_ui(self):
        self.setWindowTitle('{} LLM GUI'.format(model_name))
        self.setStyleSheet("background-color: #f6f6f6")

        # 布局设置
        self.layout = QVBoxLayout()

        # 放大的字体
        font = QFont("Jetbrains Mono, 微软雅黑", 13)

        # 显示“Model”标签
        self.model_label = QLabel(model_name, self)
        self.model_label.setStyleSheet("color: #8785a2")
        self.model_label.setFont(font)
        self.layout.addWidget(self.model_label)

        # 显示对话的文本框
        self.chat_display = QTextEdit(self)
        self.chat_display.setReadOnly(True)  # 使显示区域只读
        self.chat_display.setFont(font)  # 将字体应用于QTextEdit
        self.chat_display.setObjectName("chat_display")
        self.chat_display.setStyleSheet("""
            #chat_display {
                transition-duration: 2s;
                background-color: transparent;
                border-radius: 0px; border: 2px dashed;
                overflow: hidden;
            }
        """)

        self.layout.addWidget(self.chat_display)


        # 显示“Generating...”标签
        self.generating_label = QLabel("生成中...", self)
        self.generating_label.setStyleSheet("color: green;")
        self.generating_label.setVisible(False)  # 初始时不显示
        self.layout.addWidget(self.generating_label)

        # 用户输入的文本框
        self.input_field = QLineEdit(self)
        self.input_field.setFont(font)
        self.layout.addWidget(self.input_field)

        # 发送按钮
        self.send_button = QPushButton('发送', self)
        self.send_button.setFont(font)
        self.send_button.clicked.connect(self.start_conversation)
        self.send_button.setObjectName("send_button")
        self.send_button.setStyleSheet("""
            #send_button {
                background: #A5D6A7;
            }
        """)
        self.layout.addWidget(self.send_button)

        self.setLayout(self.layout)

        # 获取屏幕的尺寸
        screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()

        # 计算窗口的中心位置
        window_width = 1000  # 设置窗口宽度
        window_height = 800  # 设置窗口高度
        x = (screen_rect.width() - window_width) // 2  # 计算X坐标
        y = (screen_rect.height() - window_height) // 2  # 计算Y坐标

        # 设置窗口位置和大小
        self.setGeometry(x, y, window_width, window_height)

    def start_conversation(self):
        # 获取用户输入的消息
        user_message = self.input_field.text()

        # 判断用户输入是否重复
        if user_message == self.previous_user_message:
            return  # 如果当前输入和上一次一样，则不做任何处理

        # 清空输入框，准备下一次输入
        self.input_field.clear()

        # 保存当前用户消息，防止下次重复输入
        self.previous_user_message = user_message

        # 先将用户输入添加到聊天框，设置蓝色
        self.chat_display.append('<font color="#f67280" style="background-color: #9E9E9E;">You</font>: <br>'
                                 + '<span style="border-radius: 2px; color: #c06c84">'
                                 + user_message + '</span>')

        # 显示“Generating...”标签
        self.generating_label.setVisible(True)

        # 创建并启动线程以发送API请求
        self.api_thread = ApiThread(user_message)

        # 在发送请求之前，不直接将用户输入添加到chat_display
        self.api_thread.response_received.connect(self.update_chat)
        self.api_thread.start()

    def update_chat(self, model_response, done):
        # 只将模型的响应添加到聊天框，不重复用户的输入，设置绿色
        self.chat_display.append('<font color="#6c5b7b" style="background-color: #9E9E9E;">'+model_name+'</font>: <br>'
                                 + '<span style="border-radius: 2px; color: #35477d;">'
                                 + model_response + '</span>')

        # 让文本框自动滚动到底部
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.End)
        self.chat_display.setTextCursor(cursor)

        # 如果对话已完成，退出线程
        if done:
            self.api_thread.quit()

            # 隐藏“Generating...”标签，恢复按钮状态
            self.generating_label.setVisible(False)

    def keyPressEvent(self, event):
        # 当按下 Enter 键时触发发送按钮点击事件
        if event.key() == 16777220:  # 16777220 是 Enter 键的虚拟键值
            self.start_conversation()
        else:
            super().keyPressEvent(event)


# 启动应用
def main():
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
