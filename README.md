# Moltecho - OpenClaw Skills & Agents

本仓库用于存储 OpenClaw 的私有 Skills 和 Agents 配置。

## ⚠️ 安全提示

### 敏感信息管理

以下信息**禁止**提交到本仓库：

- ❌ 邮箱授权码 (`auth_code`)
- ❌ GitHub Tokens (`ghp_*`, `github_pat_*`)
- ❌ API Keys / App Secrets
- ❌ 密码
- ❌ 内部邮箱地址
- ❌ 用户 Open ID / Group ID
- ❌ 内部服务器地址

### 配置文件管理

敏感配置应存储在：

1. **环境变量**（推荐）
   ```bash
   export FEISHU_APP_ID="cli_xxx"
   export FEISHU_APP_SECRET="xxx"
   export FEISHU_CALENDAR_ID="xxx@group.calendar.feishu.cn"
   ```

2. **本地配置文件**（已排除在 Git 外）
   - 存放在 `~/.openclaw/workspace/skills/<skill>/config.json`
   - 已在 `.gitignore` 中排除

## 目录结构

```
moltecho/
├── skills/                      # Skills 技能模块
│   ├── rpctvm/                 # 邮箱 IMAP 访问
│   │   ├── SKILL.md            # 技能文档
│   │   └── summarize_sent.py   # 邮件处理脚本
│   ├── pfjtmr/                 # 月度报告提醒
│   │   ├── SKILL.md            # 技能文档
│   │   └── config.example.json # 配置模板
│   └── feishu-calendar/        # 飞书日历操作
│       ├── SKILL.md            # 技能文档
│       └── config.example.json # 配置模板
├── .gitignore                  # Git 忽略规则
├── LICENSE                     # GPL-3.0
└── README.md                   # 本文件
```

## Skills 说明

### rpctvm - 邮箱 IMAP 访问

自动读取邮箱已发送文件夹，生成邮件汇总报告。

**功能**：
- 支持 163 邮箱 IMAP ID 命令
- 日报/周报生成
- 支持 Proximity 和 Alert 类型邮件解析

**配置文件**：`~/.openclaw/workspace/memory/email_credentials.json`

```json
{
  "email": "your-email@163.com",
  "imap_server": "imap.163.com",
  "imap_port": 993,
  "auth_code": "your-auth-code",
  "target_recipient": "recipient@example.com"
}
```

### pfjtmr - 月度报告提醒

每月 23 日提醒用户处理 monthrear 项目 WAN 接口报告。

**功能**：
- 检查 Win10-Node PDF 目录
- 生成任务执行命令
- 支持 CSV/Word 输出

**配置文件**：`~/.openclaw/workspace/skills/pfjtmr/config.json`

```json
{
  "work_dir": "C:\\path\\to\\Reportwork",
  "wan_intf_dir": "C:\\path\\to\\wan_intf",
  "uv_path": "C:\\path\\to\\uv.exe",
  "node_name": "DESKTOP-XXX"
}
```

### feishu-calendar - 飞书日历操作

飞书日历的创建、修改、删除和提醒功能。

**功能**：
- 创建/修改/删除日程
- 心跳检查提醒（提前 30 分钟）
- 日程状态管理（完成/分期）

**配置文件**：`~/.openclaw/workspace/skills/feishu-calendar/config.json`

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

## 使用方法

### 克隆仓库

```bash
git clone https://github.com/tsunchen/moltecho.git
cd moltecho
```

### 创建本地配置

每个 skill 都有 `config.example.json` 模板，复制并填入真实配置：

```bash
# rpctvm 配置
cp skills/rpctvm/config.example.json ~/.openclaw/workspace/memory/email_credentials.json

# pfjtmr 配置
cp skills/pfjtmr/config.example.json ~/.openclaw/workspace/skills/pfjtmr/config.json

# feishu-calendar 配置
cp skills/feishu-calendar/config.example.json ~/.openclaw/workspace/skills/feishu-calendar/config.json
```

### 运行示例

```bash
# rpctvm: 日报（最近1天）
python skills/rpctvm/summarize_sent.py --days 1

# rpctvm: 周报（最近7天）
python skills/rpctvm/summarize_sent.py --days 7
```

## Git 操作规范

### 提交前检查

```bash
# 1. 查看变更文件
git diff --stat

# 2. 检查敏感信息
git grep -i "password\|secret\|token\|auth_code\|@163\|@company"

# 3. 确认 .gitignore 生效
git status
```

### .gitignore 规则

```gitignore
# 敏感配置文件
*_credentials.json
*_config.json
.env
.env.*

# 认证相关
auth_code*
token*
password*
secret*

# Session 日志
sessions/
*.jsonl

# 内存/缓存
memory/
*.cache
```

### Token 管理

- GitHub Token 仅存储在本地环境变量
- 使用 `ghp_` 开头的 Classic PAT 时确保权限最小化
- Fine-grained PAT 需要配置仓库访问权限

## License

GPL-3.0