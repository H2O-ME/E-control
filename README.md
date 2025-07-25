<div align="center">
  <img width="100" height="100" src="https://img.icons8.com/metro/100/console.png" alt="console"/>
  <h1>E-control 远程控制系统</h1>
  <p>基于电子邮件的远程控制工具</p>
  
  ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
  ![Email](https://img.shields.io/badge/Email-D14836?style=flat&logo=gmail&logoColor=white)
  ![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white)
</div>

## 系统概述

这是一个基于电子邮件的远程控制系统，email_controller.py在受控端长期运行，用于监控指定的电子邮件帐户中的传入命令。系统使用POP3进行命令接收，使用SMTP进行结果传输，形成了一个双向通信通道，可以通过防火墙和网络限制进行远程控制。

## 系统架构

```mermaid
graph TD
    A[程序启动] --> B[初始化配置]
    B --> C[发送启动通知]
    C --> D[主循环开始]
    D --> E{连接到POP3服务器?}
    E -->|成功| F[获取邮件列表]
    E -->|失败| D
    F --> G{有新邮件?}
    G -->|是| H[获取最新邮件]
    G -->|否| D
    H --> I[解析邮件内容]
    I --> J{Base64解码内容}
    J -->|成功| K[获取命令内容]
    J -->|失败| L[记录解码错误]
    L --> D
    K --> M{命令类型判断}
    
    %% 命令处理分支
    M -->|cmd+| N[执行系统命令]
    N --> O[创建子进程]
    O --> P{需要管理员权限?}
    P -->|是| Q[尝试提权执行]
    P -->|否| R[普通权限执行]
    Q --> S{提权成功?}
    S -->|是| T[执行命令]
    S -->|否| U[记录权限错误]
    
    M -->|website+| V[打开网站]
    V --> W[验证URL格式]
    W --> X[调用默认浏览器打开]
    
    M -->|list_desktop| Y[获取桌面文件列表]
    M -->|list_folder| Z[获取指定文件夹内容]
    M -->|send_file| AA[发送指定文件]
    
    %% 结果处理
    T --> AB[收集命令输出]
    R --> AB
    X --> AB
    Y --> AB
    Z --> AB
    AA --> AB
    
    %% 错误处理
    U --> AC
    
    %% 结果发送
    AB --> AC[格式化结果]
    AC --> AD[连接SMTP服务器]
    AD --> AE{连接成功?}
    AE -->|是| AF[发送结果邮件]
    AE -->|否| AG[记录发送失败]
    AG --> D
    AF --> D
    
    %% 超时处理
    N -->|超时| AH[终止超时进程]
    AH --> AI[记录超时错误]
    AI --> AC
    
    %% 循环控制
    D -->|检查间隔| AJ[等待CHECK_INTERVAL秒]
    AJ --> D
    
    %% 异常处理
    E -->|异常| AK[记录连接错误]
    AK --> AJ
    F -->|异常| AL[记录获取邮件错误]
    AL --> AJ
```
### 核心模块架构
本系统分为四个主要功能模块，每个模块负责远程控制作的特定方面。
<img width="1614" height="802" alt="image" src="https://github.com/user-attachments/assets/9093501e-7d11-4a10-8b7e-862d0f3f2976" />
### 通信协议和数据流
本系统实现了一种基于电子邮件的异步通信协议，该协议支持目标设备命令和广播命令。
### 命令格式结构
<img width="1531" height="811" alt="image" src="https://github.com/user-attachments/assets/61eeb938-9580-4238-84d3-b6ffd2b3265c" />

### 命令类别和处理
<img width="1242" height="804" alt="image" src="https://github.com/user-attachments/assets/da953939-54ea-4856-9cd0-b2245ccbff18" />

### 设备命令过滤
设备过滤机制将确保命令仅在预期目标上执行。
<img width="1699" height="324" alt="image" src="https://github.com/user-attachments/assets/bdb95b7a-03d1-4383-adb3-6a5bdc3aaeda" />

## 部署与使用
### Python环境要求
该系统需要 Python 3.6+ 。
### 安装所需库
```python
pip install psutil pillow
```
### 电子邮件通信配置
* `EMAIL_ACCOUNT`：用于受控设备的电子邮件地址
* `EMAIL_PASSWORD`：受控设备的电子邮件的SMTP/POP3 授权码
* `RESULT_EMAIL`：控制端电子邮件地址
* `POP3_SERVER`：受控端邮箱POP3服务器地址（例如，“pop.yeah.net”）
* `POP3_PORT`：POP3 服务端口（通常为 110）
* `SMTP_SERVER`：受控端邮件SMTP服务器主机名（例如，“smtp.yeah.net”）
* `SMTP_PORT`：SMTP 服务端口（通常为 25 ）
  <img width="1686" height="390" alt="image" src="https://github.com/user-attachments/assets/4e92dd44-5bf6-4202-ae2c-29b74365f180" />
### 运行程序
#### 1.通过python运行
导航到包含Python文件的目录，然后按住Shift键并右键单击空白处，选择“在此处打开PowerShell窗口”。在PowerShell窗口中，输入以下命令：
```powershell
python email_controller.py
```
#### 2.使用PyInstaller打包成exe文件运行
导航到包含Python文件的目录，然后按住Shift键并右键单击空白处，选择“在此处打开PowerShell窗口”。在PowerShell窗口中，输入以下命令：
```powershell
pyinstaller -F -w  email_controller.py
```
在dist目录下可以找到生成的email_controller.exe，双击运行。
