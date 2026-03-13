# rpctvm Agent - 邮箱IMAP访问技能

## 任务

自动读取指定邮箱的已发送文件夹（Sent），生成邮件汇总报告。

## 邮箱配置

- **邮箱**: 从环境变量 `EMAIL_ADDRESS` 读取
- **IMAP服务器**: 从环境变量 `IMAP_SERVER` 读取
- **端口**: 993 (SSL)
- **授权码**: 从环境变量 `EMAIL_AUTH_CODE` 读取

### 配置文件示例

```json
{
  "email": "your-email@example.com",
  "imap_server": "imap.example.com",
  "imap_port": 993,
  "auth_code": "your-auth-code"
}
```

**注意**: 配置文件路径应通过环境变量 `EMAIL_CONFIG_PATH` 指定，或使用默认路径。

## 163邮箱IMAP安全检查（关键）

163邮箱对第三方IMAP客户端有特殊安全限制，**必须**在登录后发送 `ID` 命令，否则会返回 "Unsafe Login" 错误。

### 错误示例

```
SELECT Unsafe Login. Please contact kefu@188.com for help
```

### 正确流程

```python
import imaplib

# 1. 连接并登录
mail = imaplib.IMAP4_SSL('imap.163.com', 993)
mail.login(email_address, auth_code)

# 2. 关键：动态注册ID命令
imaplib.Commands['ID'] = ('AUTH')
mail._simple_command('ID', '("name" "test" "version" "1.0.0" "vendor" "myclient")')

# 3. 现在可以正常操作
mail.select('&XfJT0ZAB-')  # Sent文件夹（IMAP UTF-7编码）
```

### 为什么需要ID命令

- 163邮箱要求客户端标识身份（RFC 2971 IMAP ID扩展）
- 这是163特有的安全策略，其他邮箱（Gmail、Outlook）无此要求
- 不发送ID命令会导致所有SELECT操作失败

## 文件夹名称

163邮箱的Sent文件夹使用IMAP UTF-7编码：

| 显示名称 | IMAP名称 |
|----------|----------|
| 已发送 | `&XfJT0ZAB-` |
| 收件箱 | `INBOX` |
| 草稿箱 | `&g0l6P3ux-` |
| 垃圾箱 | `&XfJSIJZk-` |

## 读取邮件示例

```python
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import json
import os
from datetime import datetime, timedelta, timezone

# 从环境变量或配置文件加载
config_path = os.environ.get('EMAIL_CONFIG_PATH', '/path/to/config.json')
with open(config_path) as f:
    config = json.load(f)

# 连接
mail = imaplib.IMAP4_SSL(config['imap_server'], config['imap_port'])
mail.login(config['email'], config['auth_code'])

# 关键：发送ID命令
imaplib.Commands['ID'] = ('AUTH')
mail._simple_command('ID', '("name" "test" "version" "1.0.0" "vendor" "myclient")')

# 选择Sent文件夹
mail.select('&XfJT0ZAB-')

# 搜索邮件
status, messages = mail.search(None, 'ALL')
email_ids = messages[0].split()

# 读取邮件
for email_id in email_ids[-10:]:
    status, msg_data = mail.fetch(email_id, "(RFC822.HEADER)")
    msg = email.message_from_bytes(msg_data[0][1])
    
    # 解码主题
    subject = msg.get('Subject', '')
    decoded = decode_header(subject)
    # ... 处理邮件

mail.logout()
```

## 安全边界

- **仅允许读取** `Sent` 文件夹（已发送）
- **禁止读取** 收件箱、删除邮件、修改设置
- **禁止发送邮件**
- **授权码** 应通过环境变量或加密配置文件管理，**禁止硬编码**

## 定时任务

- **日报**: 周一至周六 8:30 (Asia/Shanghai)
- **周报**: 周日 12:00 (Asia/Shanghai)
- **推送群**: 通过环境变量 `NOTIFICATION_CHAT_ID` 配置

## 相关文档

- Agent 配置文件应存储在安全目录中
- 敏感信息通过环境变量注入