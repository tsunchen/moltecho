# rpctvm Skill - Email IMAP Access & Bitable Sync

## 任务

自动读取指定邮箱的已发送文件夹（Sent），生成邮件汇总报告，并同步到飞书多维表格。

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

---

## 多维表格同步（每日汇总）

### 表格配置

| 项目 | 值 |
|------|------|
| 表格名称 | rpctvm日报记录_每日汇总 |
| app_token | `KMuSbNqaFaWDMEsDdt3cu4Yen41` |
| table_id | `tbldrD3fewjKJ6qI` |
| 链接 | https://scn4g7d1hhzh.feishu.cn/base/KMuSbNqaFaWDMEsDdt3cu4Yen41 |

### 字段结构

| 字段名 | 字段ID | 类型 | 说明 |
|--------|--------|------|------|
| 日期 | fldPjdZdYn | DateTime | 当天日期（时间戳毫秒） |
| 租户 | fld655kae9 | Text | 租户名称（默认：浦发） |
| 邮件数 | fldS7aEHIl | Number | 当天邮件数量 |
| 特殊设备数 | fldNB30OrH | Number | special 类型设备数量 |
| 一般关注设备数 | fldDWG1yJn | Number | general 类型设备数量 |
| 设备详情 | fldImzJFEY | Text | 设备名称及问题（去重合并） |

### 写入流程

日报任务在推送群消息后，执行以下步骤：

1. **解析数据**: 从 `sent_emails_data.json` 读取邮件数据
2. **按日期合并**: 同一天的多封邮件合并为一行
3. **去重统计**: 设备按名称去重，保留最新问题描述
4. **写入表格**: 使用 `feishu_bitable_create_record` 写入

### 数据格式

从 `sent_emails_data.json` 提取：

```json
{
  "date": "Fri, 13 Mar 2026 08:05:04 +0800 (CST)",
  "type": "Proximity",
  "granular_spoke_stats": {
    "special": [...],
    "general": [...],
    "skipped": [...]
  }
}
```

### 合并逻辑

```python
# 按日期分组
daily_data = {}
for email in emails:
    date_key = parse_date(email["date"]).date()
    if date_key not in daily_data:
        daily_data[date_key] = {
            "count": 0,
            "special_devices": {},  # 去重
            "general_devices": {}   # 去重
        }
    daily_data[date_key]["count"] += 1
    # 合并设备，去重保留最新详情
    for dev in email["granular_spoke_stats"]["special"]:
        daily_data[date_key]["special_devices"][dev["device"]] = dev["details"]
    for dev in email["granular_spoke_stats"]["general"]:
        daily_data[date_key]["general_devices"][dev["device"]] = dev["details"]
```

### 写入示例

```json
{
  "app_token": "KMuSbNqaFaWDMEsDdt3cu4Yen41",
  "table_id": "tbldrD3fewjKJ6qI",
  "fields": {
    "日期": 1773312304000,
    "租户": "浦发",
    "邮件数": 1,
    "特殊设备数": 0,
    "一般关注设备数": 2,
    "设备详情": "PuFaJiTuan-050100-04 (Wan2 能见度80%), PuFaJiTuan-060200-01 (Wan2 能见度80%)"
  }
}
```

### 设备详情格式

- **一般设备**: `设备名 (问题详情)`
- **特殊设备**: `[特殊] 设备名 (问题详情)`
- 多个设备用 `, ` 分隔

示例：
```
[特殊] PuFaJiTuan-010000-01 (Wan2 Wan2), PuFaJiTuan-040100-01 (Wan2 能见度80%)
```

### 时间戳转换

```python
import email.utils
from datetime import datetime

date_str = "Fri, 13 Mar 2026 08:05:04 +0800 (CST)"
dt = email.utils.parsedate_to_datetime(date_str)
timestamp_ms = int(dt.timestamp() * 1000)
```

---

## 安全边界

- **仅允许读取** `Sent` 文件夹（已发送）
- **禁止读取** 收件箱、删除邮件、修改设置
- **禁止发送邮件**
- **授权码** 应通过环境变量或加密配置文件管理，**禁止硬编码**

## 定时任务

| 任务 | 时间 | Cron ID |
|------|------|---------|
| 日报 | 周一至周六 8:30 | `fbbd8ccd-1184-4725-b1a1-74d9f4a20e32` |
| 周报 | 周日 12:00 | `77445691-4e3c-433c-af6b-3c06995650a7` |

日报任务流程：
1. 获取邮件数据 (`--days 1`)
2. 解析并生成汇总报告
3. 推送群消息
4. 写入多维表格（每天一行）

## 相关文档

- `/root/.openclaw/workspace/MEMORY.md` - 邮件安全与操作约束
- `/root/.openclaw/agents/rpctvm/workspace/MEMORY.md` - Agent 长期记忆