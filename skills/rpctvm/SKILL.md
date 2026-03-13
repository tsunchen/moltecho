# rpctvm Skill - Email IMAP Access

## 任务

自动读取指定邮箱的已发送文件夹（Sent），生成邮件汇总报告。

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `EMAIL_CONFIG_PATH` | 配置文件路径 | `/root/.openclaw/workspace/memory/email_credentials.json` |
| `TARGET_RECIPIENT` | 目标收件人邮箱 | 从配置文件读取 |
| `NOTIFICATION_CHAT_ID` | 推送群 ID | 从配置文件读取 |

### 配置文件格式

```json
{
  "email": "your-email@example.com",
  "imap_server": "imap.example.com",
  "imap_port": 993,
  "auth_code": "your-auth-code",
  "target_recipient": "recipient@example.com",
  "notification_chat_id": "oc_xxx"
}
```

**注意**: 配置文件应存储在安全目录，禁止提交到 Git。

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
mail = imaplib.IMAP4_SSL(imap_server, 993)
mail.login(email_address, auth_code)

# 2. 关键：动态注册ID命令
imaplib.Commands['ID'] = ('AUTH')
mail._simple_command('ID', '("name" "openclaw" "version" "1.0.0")')

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

## 脚本

### summarize_sent.py

读取已发送邮件并生成汇总报告。

```bash
# 日报（最近1天）
python summarize_sent.py --days 1

# 周报（最近7天）
python summarize_sent.py --days 7
```

### 输出

脚本会将结果保存到 `OUTPUT_PATH` 环境变量指定的路径，默认为：
`/root/.openclaw/agents/rpctvm/workspace/memory/sent_emails_data.json`

## 安全边界

- **仅允许读取** `Sent` 文件夹（已发送）
- **禁止读取** 收件箱、删除邮件、修改设置
- **禁止发送邮件**
- **授权码** 应通过环境变量或加密配置文件管理，**禁止硬编码**

## 定时任务

- **日报**: 周一至周六 8:30 (Asia/Shanghai)
- **周报**: 周日 12:00 (Asia/Shanghai)

## 相关文档

- `/root/.openclaw/workspace/MEMORY.md` - 邮件安全与操作约束