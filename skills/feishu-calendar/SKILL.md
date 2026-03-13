---
name: feishu-calendar
description: |
  Feishu calendar operations. Activate when user mentions calendar, 日程, 提醒, meeting, schedule.
---

# Feishu Calendar Tool

飞书日历操作工具，用于创建、修改、删除日程。

## 配置

以下配置通过环境变量或配置文件读取：

| 变量 | 说明 |
|------|------|
| `FEISHU_APP_ID` | 飞书应用 ID |
| `FEISHU_APP_SECRET` | 飞书应用密钥 |
| `FEISHU_CALENDAR_ID` | 日历 ID |
| `FEISHU_USER_OPEN_ID` | 用户 Open ID |
| `FEISHU_REMINDER_GROUP` | 提醒群 ID |
| `FEISHU_REMINDER_ADVANCE` | 提前提醒时间（分钟），默认 30 |

### 配置文件示例

```json
{
  "app_id": "cli_xxx",
  "app_secret": "xxx",
  "calendar_id": "xxx@group.calendar.feishu.cn",
  "user_open_id": "ou_xxx",
  "reminder_group": "oc_xxx",
  "reminder_advance": 30
}
```

**注意**: 配置文件应存储在安全目录，禁止提交到 Git。

## 获取 Token

所有 API 调用需要先获取 tenant_access_token：

```bash
TENANT_TOKEN=$(curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d "{\"app_id\":\"$APP_ID\",\"app_secret\":\"$APP_SECRET\"}" | grep -o '"tenant_access_token":"[^"]*"' | cut -d'"' -f4)
```

## Actions

### create - 创建日程

```bash
curl -s -X POST "https://open.feishu.cn/open-apis/calendar/v4/calendars/$CALENDAR_ID/events?user_id_type=open_id" \
  -H "Authorization: Bearer $TENANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "{事件名称}",
    "start_time": { "timestamp": {开始时间戳} },
    "end_time": { "timestamp": {结束时间戳} },
    "attendees": [{ "type": "user", "open_id": "{USER_OPEN_ID}" }]
  }'
```

**返回**: `event_id` 可用于后续修改/删除

### update - 修改日程

```bash
curl -s -X PATCH "https://open.feishu.cn/open-apis/calendar/v4/calendars/$CALENDAR_ID/events/{event_id}?user_id_type=open_id" \
  -H "Authorization: Bearer $TENANT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "{新名称}",
    "start_time": { "timestamp": {新开始时间戳} },
    "end_time": { "timestamp": {新结束时间戳} }
  }'
```

### delete - 删除日程

```bash
curl -s -X DELETE "https://open.feishu.cn/open-apis/calendar/v4/calendars/$CALENDAR_ID/events/{event_id}" \
  -H "Authorization: Bearer $TENANT_TOKEN"
```

### list - 查询日程列表

```bash
# 获取时间范围内的日程
START_TIMESTAMP={开始时间戳}
END_TIMESTAMP={结束时间戳}

curl -s "https://open.feishu.cn/open-apis/calendar/v4/calendars/$CALENDAR_ID/events?start_time=$START_TIMESTAMP&end_time=$END_TIMESTAMP&user_id_type=open_id" \
  -H "Authorization: Bearer $TENANT_TOKEN"
```

## 时间转换

### 北京时间 → 时间戳

```bash
# 格式: date -d "YYYY-MM-DD HH:MM Asia/Shanghai" +%s

# 示例: 2026-03-11 10:00 北京时间
date -d "2026-03-11 02:00 UTC" +%s
# 输出: 1773194400

# 示例: 2026-03-12 12:00 北京时间 (UTC+8)
# UTC 时间 = 北京时间 - 8小时
date -d "2026-03-12 04:00 UTC" +%s
```

### 时间戳 → 可读时间

```bash
# 格式: date -d @时间戳 '+%Y-%m-%d %H:%M %Z'
date -d @1773194400 '+%Y-%m-%d %H:%M %Z'
# 输出: 2026-03-11 02:00 UTC (即北京时间 10:00)
```

## 使用示例

### 创建日程

用户说: "周三10点开会"

1. 计算时间戳:
   - 周三 10:00 CN = 周三 02:00 UTC
   - 开始: 1773194400
   - 结束: 1773198000 (1小时后)

2. 执行创建 API

3. 返回 event_id

### 修改日程时间

用户说: "把周三的会议改到11点"

1. 找到 event_id (从之前的创建结果或 list)

2. 计算新时间戳:
   - 11:00 CN = 03:00 UTC = 1773198000
   - 12:00 CN = 04:00 UTC = 1773201600

3. 执行 update API

## 日程提醒机制

### 心跳检查流程

在每次心跳时执行：

1. **获取飞书日历事件**（当天+次日）
2. **计算时间差**：比较事件开始时间与当前时间
3. **判断是否需要提醒**：如果 `0 < 时间差 ≤ 30分钟`，推送提醒
4. **避免重复推送**：记录已提醒的 event_id

### 提醒推送

- **推送群**: 从配置文件读取
- **推送格式**: 
  ```
  📅 【日程提醒】{事件名称}
  ⏰ 开始时间：{HH:MM}
  ⏱️ 还有 {X} 分钟开始
  ```

### 示例代码

```bash
# 心跳中检查日程
NOW=$(date +%s)
START_TS=$((NOW - 3600))  # 1小时前
END_TS=$((NOW + 86400))    # 24小时后

# 获取事件
EVENTS=$(curl -s "https://open.feishu.cn/open-apis/calendar/v4/calendars/$CALENDAR_ID/events?start_time=$START_TS&end_time=$END_TS" \
  -H "Authorization: Bearer $TENANT_TOKEN")

# 遍历检查时间差
for event in $EVENTS; do
  START=$(echo $event | jq -r '.start_time.timestamp')
  DIFF=$(( (START - NOW) / 60 ))  # 分钟差
  
  if [ $DIFF -gt 0 ] && [ $DIFF -le 30 ]; then
    # 推送提醒
    SUMMARY=$(echo $event | jq -r '.summary')
    message send --group "$REMINDER_GROUP" "📅 【日程提醒】$SUMMARY\n⏰ 还有 $DIFF 分钟开始"
  fi
done
```

## 日程状态处理规则

### ✅ 已完成

当用户确认日程完成时，更新事件名称添加标记：

```bash
# 更新事件名称
curl -s -X PATCH "https://open.feishu.cn/open-apis/calendar/v4/calendars/$CALENDAR_ID/events/$EVENT_ID" \
  -H "Authorization: Bearer $TENANT_TOKEN" \
  -d '{"summary": "事件名称（已完成）"}'
```

### ⏳ 未完成（分期）

当用户确认日程未完成时，执行两步操作：

1. **原位置创建分期事件**：
   ```bash
   # 创建新事件，名称为"原事件名（分期）"
   curl -s -X POST "https://open.feishu.cn/open-apis/calendar/v4/calendars/$CALENDAR_ID/events" \
     -H "Authorization: Bearer $TENANT_TOKEN" \
     -d '{
       "summary": "原事件名（分期）",
       "start_time": { "timestamp": 原开始时间 },
       "end_time": { "timestamp": 原结束时间 }
     }'
   ```

2. **移动原事件到新日期**：
   ```bash
   # 更新原事件的时间
   curl -s -X PATCH "https://open.feishu.cn/open-apis/calendar/v4/calendars/$CALENDAR_ID/events/$EVENT_ID" \
     -H "Authorization: Bearer $TENANT_TOKEN" \
     -d '{
       "start_time": { "timestamp": 新开始时间 },
       "end_time": { "timestamp": 新结束时间 }
     }'
   ```

**示例**：
- 原事件：`浦汇智途` (03-11 11:00-12:00)
- 未完成处理：
  - 原位置新建：`浦汇智途（分期）` (03-11 11:00-12:00)
  - 原事件移动到：03-12 11:00-12:00

## 注意事项

1. **时间戳是 UTC 时间**，北京时间需要减8小时
2. **token 有效期 2 小时**，建议每次调用前重新获取
3. **日历 ID 固定**，使用配置文件中的值
4. **用户 open_id 固定**，作为参与者自动添加