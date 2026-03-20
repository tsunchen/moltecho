# rpctvm Skill - Email IMAP Access & Bitable Sync

## 任务

自动读取指定邮箱的已发送文件夹（Sent），生成邮件汇总报告，并同步到飞书多维表格。

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `EMAIL_CONFIG_PATH` | 邮箱配置文件路径 | `/root/.openclaw/workspace/memory/email_credentials.json` |
| `BITABLE_CONFIG_PATH` | 多维表格配置文件路径 | `/root/.openclaw/workspace/memory/rpctvm_bitable.json` |
| `TARGETS_CONFIG_PATH` | 推送目标配置文件路径 | `/root/.openclaw/workspace/memory/rpctvm_targets.json` |
| `TARGET_RECIPIENT` | 目标收件人邮箱 | 从配置文件读取 |
| `NOTIFICATION_CHAT_ID` | 推送群 ID | 从配置文件读取 |

### 配置文件格式

#### 邮箱配置 (email_credentials.json)

```json
{
  "email": "your-email@example.com",
  "imap_server": "imap.example.com",
  "imap_port": 993,
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
  "task_url": "https://tower.im/teams/YOUR_TEAM/todos/YOUR_TODO",
  "node_name": "YOUR_NODE_NAME"
}
```

**注意**: 所有配置文件应存储在安全目录（如 `~/.openclaw/workspace/memory/`），并已添加到 `.gitignore`。

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

### 配置读取

多维表格的 `app_token` 和 `table_id` 从配置文件读取：

```python
import os
import json

config_path = os.environ.get('BITABLE_CONFIG_PATH', 
                              '/root/.openclaw/workspace/memory/rpctvm_bitable.json')
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

**⚠️ 重要**：周报任务按日期降序写入（最新日期在前）

1. 获取最近7天的邮件数据
2. 按日期降序排列（最新在前）
3. 检查多维表格中已存在的日期
4. 仅写入新日期（按降序写入）
5. **不推送消息** - 周报仅更新表格

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
- **Token** 应通过配置文件管理，**禁止提交到 Git**

## 定时任务

| 任务 | 时间 | Cron ID | 说明 |
|------|------|---------|------|
| 日报 | 周一至周六 9:00 (北京时间) | `6aa30983-efb0-4275-98b4-8048dedbbe0e` | 推送群消息+语音+更新表格 |
| 周报 | 周日 12:00 | `77445691-4e3c-433c-af6b-3c06995650a7` | **仅更新表格，不推送消息** |

### 推送目标

| 消息类型 | 目标 | 配置字段 | 用途 |
|----------|------|----------|------|
| **文字报告** | 群聊 | `group_chat_id` | 备用查看 |
| **语音播报** | 私聊 | `user_open_id` | 主要播报，点击播放 |

推送目标 ID 从配置文件读取：

```python
import os
import json

config_path = os.environ.get('TARGETS_CONFIG_PATH',
                              '/root/.openclaw/workspace/memory/rpctvm_targets.json')
with open(config_path, 'r') as f:
    config = json.load(f)

group_chat_id = config['group_chat_id']
user_open_id = config['user_open_id']
```

### 日报任务流程

**执行时间**: 每天上午 8:30（周一至周六）

**数据范围**:
- **多维表格（简报）**: 汇总**除当天之外**的邮件数据（即截止到昨天），仅写入新日期
- **群消息推送**: 推送**最近24小时**的邮件数据汇总

**写入规则**: 
1. 读取 `sent_emails_data.json` 中的邮件数据
2. **简报写入**: 按日期分组，排除当天，检查多维表格是否已有该日期，新日期追加
3. **群消息推送**: 汇总最近24小时的所有邮件数据，生成报告推送

**流程步骤**:
1. 获取邮件数据
2. 解析并生成汇总报告
3. **推送群消息** → 最近24小时数据
4. **推送私聊语音** → 用户（从 `rpctvm_targets.json` 读取 `user_open_id`，最近24小时数据）
   - 使用 `tts` 工具将文字报告转换为语音
   - 推送到用户私聊
   - **格式要求**: 提取要点，简短突出重点（控制在30秒内）
     - 开头: "设备日报，{日期}"
     - 正文: 仅播报需要关注的设备，按优先级排序
       1. 失联设备（最优先）: "失联{X}台：{设备名}..."
       2. 特殊设备: "特殊{X}台：{设备名}..."
       3. 一般设备（仅报数量）: "一般关注{X}台"
     - 结尾: "共{X}台需关注，详情见群消息"
     - **省略规则**: 设备详情和问题描述只在必要时提及，优先报数量
   - **语音示例**：
     - 有失联设备: "设备日报，3月20日。失联2台：PuFaJiTuan-010000-01、HuaQiao-020200-03。特殊1台：双链路告警。一般关注1台。共4台需关注，详情见群消息。"
     - 只有特殊设备: "设备日报，3月19日。特殊3台：双链路告警。一般2台：Wan2能见度80%。共5台需关注，详情见群消息。"
     - 只有一般设备: "设备日报，3月17日。一般关注2台。PuFaJiTuan-040100-01 Wan2能见度80%。详情见群消息。"
     - 无异常: "设备日报，3月16日。巡检完成，一切正常。"
5. **写入多维表格** → 排除当天，仅新日期

**时间戳计算**: 使用日期对应的北京时间 00:00 转换为 UTC 时间戳（毫秒）
- 北京时间 2026-03-15 00:00 = UTC 2026-03-14 16:00
- 时间戳: 1773504000000

## Tower 评论格式

### 配置文件

Tower 任务配置存储在 `/root/.openclaw/workspace/memory/rpctvm_tower.json`

---

## 评论模板（两类格式）

### 📱 格式一：群聊推送（带 emoji）

用于推送到飞书群聊，支持 emoji 和丰富格式，便于阅读。

**格式模板**：
```
📊 设备日报 Device Daily (YYYY/MM/DD)
━━━━━━━━━━━━━━━━━━
📈 总体统计
• 邮件总数: X 封
• 告警类型: Proximity/Alert
• 涉及设备: X 台
━━━━━━━━━━━━━━━━━━
🔴 失联设备（优先关注）
[失联设备列表，每个一行]
━━━━━━━━━━━━━━━━━━
🟠 特殊设备
[特殊设备列表，每个一行]
━━━━━━━━━━━━━━━━━━
🟡 一般设备
[一般设备列表，每个一行]
━━━━━━━━━━━━━━━━━━
💡 建议
[建议内容]
━━━━━━━━━━━━━━━━━━
报告时间: YYYY-MM-DD HH:MM
```

**示例1：无异常**
```
📊 设备日报 Device Daily (2026/03/17)
━━━━━━━━━━━━━━━━━━
📈 总体统计
• 邮件总数: 2 封
• 告警类型: Proximity
• 涉及设备: 0 台
━━━━━━━━━━━━━━━━━━
✅ 巡检完成，一切正常。
━━━━━━━━━━━━━━━━━━
报告时间: 2026-03-17 08:30
```

**示例2：只有一般设备**
```
📊 设备日报 Device Daily (2026/03/17)
━━━━━━━━━━━━━━━━━━
📈 总体统计
• 邮件总数: 3 封
• 告警类型: Proximity
• 涉及设备: 2 台
━━━━━━━━━━━━━━━━━━
🟡 一般设备
• PuFaJiTuan-040100-01: Wan2 能见度 80%
• PuFaJiTuan-100200-01: Wan2 能见度 75%
━━━━━━━━━━━━━━━━━━
💡 建议
请关注设备链路状态。
━━━━━━━━━━━━━━━━━━
报告时间: 2026-03-17 08:30
```

**示例3：特殊设备 + 一般设备**
```
📊 设备日报 Device Daily (2026/03/19)
━━━━━━━━━━━━━━━━━━
📈 总体统计
• 邮件总数: 4 封
• 告警类型: Proximity
• 涉及设备: 5 台
━━━━━━━━━━━━━━━━━━
🟠 特殊设备
• PuFaJiTuan-050300-01: 双链路告警
• PuFaJiTuan-090000-03: 双链路告警
• PuFaJiTuan-090000-04: 双链路告警
━━━━━━━━━━━━━━━━━━
🟡 一般设备
• PuFaJiTuan-060200-01: Wan2 能见度 80%
• PuFaJiTuan-040100-02: Wan2 能见度 75%
━━━━━━━━━━━━━━━━━━
💡 建议
特殊设备需优先排查双链路问题。
━━━━━━━━━━━━━━━━━━
报告时间: 2026-03-19 08:30
```

**示例4：失联设备 + 特殊设备 + 一般设备**
```
📊 设备日报 Device Daily (2026/03/20)
━━━━━━━━━━━━━━━━━━
📈 总体统计
• 邮件总数: 5 封
• 告警类型: Proximity + Alert
• 涉及设备: 6 台
━━━━━━━━━━━━━━━━━━
🔴 失联设备（优先关注）
• PuFaJiTuan-010000-01: 长时间无响应
• HuaQiao-020200-03: 无法访问
━━━━━━━━━━━━━━━━━━
🟠 特殊设备
• PuFaJiTuan-050300-01: 双链路告警
• PuFaJiTuan-090000-03: 双链路告警
• PuFaJiTuan-090000-04: 双链路告警
━━━━━━━━━━━━━━━━━━
🟡 一般设备
• PuFaJiTuan-060200-01: Wan2 能见度 80%
━━━━━━━━━━━━━━━━━━
💡 建议
失联设备请立即检查！特殊设备需排查双链路问题。
━━━━━━━━━━━━━━━━━━
报告时间: 2026-03-20 08:30
```

---

### 📝 格式二：Tower 评论区（纯文本）

**⚠️ 重要**: Tower 富文本编辑器不支持 emoji 和复杂格式！必须使用简短纯文本！

**格式模板**：
```
YYYY年MM月DD日巡检完成。{租户}租户{报告类型}报告。{失联/特殊设备汇总}。{一般设备汇总}。共Z台设备需关注。
```

**设备分类优先级**（按严重程度排序）：
1. **失联设备** - 最高优先级，放在评论最前面
2. **特殊设备** - 双链路告警等严重问题
3. **一般设备** - Wan2能见度下降等一般关注

**示例1：无异常**
```
巡检已完成，一切正常。
```

**示例2：只有一般设备**
```
2026年3月17日巡检完成。浦发租户Proximity报告。1台一般设备Wan2能见度80%(PuFaJiTuan-040100-01)。共1台设备需关注。
```

**示例3：特殊设备 + 一般设备**
```
2026年3月19日巡检完成。浦发租户Proximity报告。3台特殊设备双链路告警(PuFaJiTuan-050300-01,090000-03,090000-04)，2台一般设备Wan2能见度75%-80%(PuFaJiTuan-060200-01,040100-02)。共5台设备需关注。
```

**示例4：失联设备 + 特殊设备 + 一般设备**
```
2026年3月20日巡检完成。浦发租户Proximity报告。2台设备失联(PuFaJiTuan-010000-01,HuaQiao-020200-03)。3台特殊设备双链路告警(PuFaJiTuan-050300-01,090000-03,090000-04)。1台一般设备Wan2能见度80%(PuFaJiTuan-060200-01)。共6台设备需关注。
```

**示例5：只有失联设备**
```
2026年3月21日巡检完成。华桥租户Alert报告。2台设备失联(HuaQiao-020200-03,HuaQiao-020200-04)。请立即检查。
```

---

### 失联设备识别关键词

在邮件数据中识别失联设备的关键词：
- `失联` / `offline` / `disconnected`
- `无法访问` / `unreachable`
- `长时间无响应`
- `无响应` / `no response`

### 推送规则

| 推送目标 | 格式 | 说明 |
|----------|------|------|
| 飞书群聊 | 格式一（带 emoji） | 丰富格式，便于阅读 |
| Tower 评论区 | 格式二（纯文本） | 简短格式，兼容 Tower 编辑器 |

### 写入流程

1. 读取 `sent_emails_data.json` 获取最新邮件数据
2. 按日期汇总统计
3. 生成符合模板格式的评论
4. 通过浏览器自动化提交到 Tower 任务评论区

### 登录要求

- 需要通过飞书扫码授权
- Win10-Node Edge 浏览器需要单独授权

### 浏览器配置

rpctvm Agent 使用远程节点 Edge 浏览器提交 Tower 评论：

| 配置项 | 值 |
|--------|------|
| 浏览器 | Microsoft Edge (Chromium) |
| Profile | openclaw |
| CDP 端口 | 18800 |
| 数据目录 | 从环境变量或配置文件读取 |

### Tower 评论提交流程

**⚠️ 节点名从配置文件读取**

1. **检查浏览器状态**: 确保 Edge 浏览器已启动并连接 CDP 端口
2. **打开 Tower 任务页面**: URL 从配置文件读取
3. **等待页面加载**: 确保评论区可见
4. **点击评论输入框**: 找到富文本编辑器并激活
5. **输入评论内容**: 使用 browser act 输入评论
6. **点击发表评论按钮**: 提交评论
7. **关闭标签页**: 清理浏览器资源

**关键**: 所有 browser 操作的节点名和 URL 从配置文件读取，不要硬编码！

### 错误处理

如果 Tower 评论失败：
1. 检查浏览器是否有 Tower 页面标签
2. 检查是否需要重新登录 Tower
3. 记录错误日志并通知管理员

---

## 相关文档

- `/root/.openclaw/workspace/MEMORY.md` - 邮件安全与操作约束
- `/root/.openclaw/agents/rpctvm/workspace/MEMORY.md` - Agent 长期记忆