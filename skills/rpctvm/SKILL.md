# rpctvm Skill - Email IMAP Access & Bitable Sync

## 任务

自动读取指定邮箱的已发送文件夹（Sent），生成邮件汇总报告，并同步到飞书多维表格。

## 重要：时间窗口计算（2026-03-27 修复）

### 问题

原脚本使用滑动窗口计算截止时间，导致日报数据不完整：

```python
# 错误：滑动窗口
cutoff_date = datetime.now(cst) - timedelta(days=1)  # 当前时间 - 24小时
```

当日报 9:00 执行时，截止时间 = 9:00 - 24h = 昨天 9:00。但巡检邮件在昨天 8:xx 发出，会被 `break` 逻辑错误排除。

### 修复

改为固定日期窗口：

```python
if args.days == 1:
    # 日报：从昨天 00:00 开始
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = today_start - timedelta(days=1)  # 昨天 00:00
else:
    # 周报等：使用滑动窗口
    cutoff_date = now - timedelta(days=args.days)
```

### 其他修复

- `break` 改为 `continue`：遇到旧邮件继续搜索，不停止
- IMAP SSL 支持：端口 993 使用 `IMAP4_SSL`

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `EMAIL_CONFIG_PATH` | 邮箱配置文件路径 | `{workspace}/memory/email_credentials.json` |
| `BITABLE_CONFIG_PATH` | 多维表格配置文件路径 | `{workspace}/memory/rpctvm_bitable.json` |
| `TARGETS_CONFIG_PATH` | 推送目标配置文件路径 | `{workspace}/memory/rpctvm_targets.json` |
| `TOWER_CONFIG_PATH` | Tower 配置文件路径 | `{workspace}/memory/rpctvm_tower.json` |
| `FEISHU_CONFIG_PATH` | 飞书凭证文件路径 | `{workspace}/memory/feishu_credentials.json` |
| `OUTPUT_PATH` | 邮件数据输出路径 | `{workspace}/memory/sent_emails_data.json` |

### 配置文件格式

#### 邮箱配置 (email_credentials.json)

```json
{
  "email": "your-email@example.com",
  "imap_server": "imap.example.com",
  "imap_port": 143,
  "auth_code": "your-auth-code",
  "target_recipient": "recipient@example.com"
}
```

#### 多维表格配置 (rpctvm_bitable.json)

```json
{
  "app_token": "your-bitable-app-token",
  "table_id": "your-table-id",
  "name": "表格名称",
  "url": "表格链接"
}
```

#### 推送目标配置 (rpctvm_targets.json)

```json
{
  "group_chat_id": "your-group-chat-id",
  "user_open_id": "your-user-open-id"
}
```

#### Tower 配置 (rpctvm_tower.json)

```json
{
  "tower_url": "https://tower.im/teams/{team_id}/todos/{todo_id}",
  "tower_name": "任务名称",
  "active_month": "YYYY-MM",
  "node_name": "远程节点名称"
}
```

#### 飞书凭证 (feishu_credentials.json)

```json
{
  "app_id": "your-app-id",
  "app_secret": "your-app-secret"
}
```

**注意**: 所有配置文件应存储在安全目录（如 `{workspace}/memory/`），并已添加到 `.gitignore`。

### 路径占位符

脚本中的 `{workspace}` 会被自动替换为实际的工作目录：
- Agent workspace: `/root/.openclaw/agents/{agent_name}/workspace`
- 上传到 ClawHub 后：由 skill-creator 自动处理

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
`{workspace}/memory/sent_emails_data.json`

---

## 多维表格同步（每日汇总）

### 配置读取

多维表格的 `app_token` 和 `table_id` 从配置文件读取：

```python
import os
import json

config_path = os.environ.get('BITABLE_CONFIG_PATH', 
                              '{workspace}/memory/rpctvm_bitable.json')
with open(config_path, 'r') as f:
    config = json.load(f)

app_token = config['app_token']
table_id = config['table_id']
```

### 字段结构

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 日期 | DateTime | 当天日期（时间戳毫秒） |
| 租户 | Text | 租户名称（默认：浦发） |
| 邮件数 | Number | 当天邮件数量 |
| 特殊设备数 | Number | special 类型设备数量 |
| 一般关注设备数 | Number | general 类型设备数量 |
| 设备详情 | Text | 设备名称及问题（去重合并） |

### 写入流程

日报任务在推送群消息后，执行以下步骤：

1. **读取配置**: 从配置文件获取 `app_token` 和 `table_id`
2. **解析数据**: 从 `sent_emails_data.json` 读取邮件数据
3. **按日期合并**: 同一天的多封邮件合并为一行
4. **去重统计**: 设备按名称去重，保留最新问题描述
5. **写入表格**: 使用 `feishu_bitable_create_record` 写入

### 周报任务写入顺序

**⚠️ 重要**：周报任务检查并补充过去 7 天缺失的日期

1. 获取过去 7 天的邮件数据
2. 查询多维表格中已存在的日期
3. 对比找出缺失的日期
4. 按日期升序写入缺失日期的数据
5. **不推送消息** - 周报仅更新表格

### 数据格式

从 `sent_emails_data.json` 提取：

**Proximity 类型邮件**：
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

**Alert 类型邮件（CRITICAL 告警）**：
```json
{
  "date": "Tue, 24 Mar 2026 08:03:15 +0800",
  "type": "Alert",
  "alert_devices": [
    {
      "device": "Device-Name",
      "tenant": "Tenant-Name",
      "details": "UNREACHABLE ( No Loading Any Uplink ... )",
      "status": "unreachable"
    }
  ],
  "has_unreachable": true
}
```

**Alert 邮件解析**：
- 从邮件 HTML 内容提取 `Device:`、`Descriptions:`、`Tenant:` 字段
- 检测 `UNREACHABLE`、`offline`、`失联` 关键词标记为失联设备
- 失联设备在日报中排在最前面（优先级最高）

### 设备详情格式

- **失联设备**: `🔴 设备名 (UNREACHABLE/失联)` - 最高优先级
- **特殊设备**: `🟠 设备名 (问题详情)` - 双链路告警等
- **一般设备**: `🟡 设备名 (问题详情)` - Wan2能见度下降等
- 多个设备用 `, ` 分隔

示例：
```
🔴 Device-001 (UNREACHABLE)
🟠 Device-002 (Wan1 双链路告警)
🟡 Device-003 (Wan2 能见度80%)
```

**排序优先级**：失联设备 > 特殊设备 > 一般设备

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
- **Token** 应通过配置文件管理，**禁止提交到 Git**

## 定时任务

| 任务 | 时间 | 说明 |
|------|------|------|
| 日报 | 周一至周六 9:00 (北京时间) | 推送群消息+语音+Tower评论 |
| 周报 | 周日 12:00 (北京时间) | **仅更新表格，不推送消息** |

### 推送目标

| 消息类型 | 目标 | 配置字段 | 用途 |
|----------|------|----------|------|
| **文字报告** | 群聊 | `group_chat_id` | 主要查看 |
| **语音播报** | 私聊 | `user_open_id` | 语音播报 |

推送目标 ID 从配置文件读取：

```python
import os
import json

config_path = os.environ.get('TARGETS_CONFIG_PATH',
                              '{workspace}/memory/rpctvm_targets.json')
with open(config_path, 'r') as f:
    config = json.load(f)

group_chat_id = config['group_chat_id']
user_open_id = config['user_open_id']
```

---

## 日报任务流程

**执行时间**: 每天上午 9:00（周一至周六）

**数据范围**: 从昨天 00:00 到当前（昨天24小时 + 当天已过小时数）

**时间计算**: 报告时长 = 24 + floor(当前小时)
- 例如：09:00 执行 → 24 + 9 = **33小时**
- 例如：10:00 执行 → 24 + 10 = **34小时**

**流程步骤**:

### 1. 获取邮件数据

```bash
python3 {workspace}/skills/rpctvm/summarize_sent.py --days 1
```

脚本会自动检测正确的 workspace 路径，输出文件：`{workspace}/memory/sent_emails_data.json`

### 2. 生成汇总报告

分析邮件类型 (Proximity/Alert)，提取关键设备信息。

### 3. 推送群消息

- 目标：从 `rpctvm_targets.json` 读取 `group_chat_id`
- 格式：使用格式一（带 emoji），标题为 **设备时报 Device Hourly**

### 4. 推送私聊语音

- 目标：从 `rpctvm_targets.json` 读取 `user_open_id`
- 使用 `tts` 工具生成语音
- **格式要求**: 提取要点，简短突出重点（控制在30秒内）
  - 开头: "设备时报"
  - 正文: 仅播报需要关注的设备，按优先级排序
    1. 失联设备（最优先）: "失联{X}台：{设备名}..."
    2. 特殊设备: "特殊{X}台：{设备名}..."
    3. 一般设备（仅报数量）: "一般关注{X}台"
  - 结尾: "共{X}台需关注，详情见群消息"

**语音示例**：
- 有失联设备: "设备时报。失联2台：Device-001、Device-002。特殊1台：双链路告警。一般关注1台。共4台需关注，详情见群消息。"
- 只有特殊设备: "设备时报。特殊3台：双链路告警。一般2台：Wan2能见度80%。共5台需关注，详情见群消息。"
- 只有一般设备: "设备时报。一般关注2台。Device-001 Wan2能见度80%。详情见群消息。"
- 无异常: "设备时报。巡检完成，一切正常。"

### 5. Tower 评论

- 任务 URL：从 `rpctvm_tower.json` 读取
- 评论格式：使用格式二（纯文本）
- **前置检查**: 检查远程节点是否在线
- **离线跳过**: 如果节点离线，记录日志并跳过

### 6. Tower 评论提交流程

1. **检查节点状态**: 确保远程节点在线
2. **打开 Tower 任务页面**: URL 从配置文件读取
3. **等待页面加载**: 确保评论区可见
4. **激活编辑器**: 点击评论区激活富文本编辑器
5. **输入评论内容**: 使用 `type` 命令输入（Tower 富文本编辑器需要此方式）
6. **提交评论**: 点击"发表评论"按钮

**关键**: Tower 富文本编辑器不支持 `innerHTML` 或 `evaluate` 方式输入内容，必须使用 `type` 命令。

---

## 评论模板（两类格式）

### 📱 格式一：群聊推送（带 emoji）

用于推送到飞书群聊，支持 emoji 和丰富格式，便于阅读。

```
📊 设备时报 Device Hourly
━━━━━━━━━━━━━━━━━━
📈 总体统计
• 邮件总数: X 封
• 告警类型: Proximity/Alert
• 涉及设备: X 台
━━━━━━━━━━━━━━━━━━
🔴 失联设备（优先关注）
[失联设备列表]
━━━━━━━━━━━━━━━━━━
🟠 特殊设备
[特殊设备列表]
━━━━━━━━━━━━━━━━━━
🟡 一般设备
[一般设备列表]
━━━━━━━━━━━━━━━━━━
💡 建议
[建议内容]
━━━━━━━━━━━━━━━━━━
报告时间: YYYY-MM-DD HH:MM
```

### 📝 格式二：Tower 评论区

**纯文本格式**，不使用 emoji，保持简洁：

```
{YYYY}年{MM}月{DD}日巡检完成。{租户}租户{报告类型}报告。{失联/特殊设备汇总}。{一般设备汇总}。共Z台设备需关注。
```

**日期来源**：脚本执行当天的日期（北京时间）
- 例如：2026年3月30日执行 → "2026年3月30日巡检完成"

**示例**：
```
2026年3月30日巡检完成。浦发租户Proximity报告。1台特殊设备Wan1告警(Device-001)。6台一般设备能见度75%-80%。美赛尔租户Alert报告。1台设备失联(Device-002)。共9台设备需关注。
```

---

### 失联设备识别关键词

在邮件数据中识别失联设备的关键词：
- `失联` / `offline` / `disconnected`
- `无法访问` / `unreachable`
- `长时间无响应`
- `无响应` / `no response`

---

## 错误处理

### Tower 评论失败

1. 检查远程节点是否在线
2. 检查是否需要重新登录 Tower
3. 确认使用 `type` 命令输入内容（不是 `innerHTML` 或 `evaluate`）
4. 记录错误日志并跳过此步骤

### 邮箱连接失败

1. 检查网络连接
2. 检查 IMAP 端口（143 或 993）
3. 确认 163 邮箱发送了 ID 命令

### 飞书 API 失败

1. 检查 `feishu_credentials.json` 配置
2. 检查 app_id 和 app_secret 是否正确
3. 检查飞书应用权限

---

## 相关文档

- `{workspace}/MEMORY.md` - Agent 长期记忆
- `{workspace}/memory/email_credentials.json` - 邮箱配置
- `{workspace}/memory/rpctvm_targets.json` - 推送目标配置
- `{workspace}/memory/rpctvm_tower.json` - Tower 配置
- `{workspace}/memory/rpctvm_bitable.json` - 多维表格配置
- `{workspace}/memory/feishu_credentials.json` - 飞书凭证