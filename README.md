# Moltecho - OpenClaw Skills & Agents

本仓库用于存储 OpenClaw 的私有 Skills 和 Agents 配置。

## ⚠️ 安全提示

### 敏感信息管理

以下信息**禁止**提交到本仓库：

- ✅ 邮箱授权码 (`auth_code`)
- ✅ GitHub Tokens (`ghp_*`, `github_pat_*`)
- ✅ API Keys
- ✅ 密码
- ✅ 内部邮箱地址
- ✅ 内部服务器地址

### 配置文件管理

敏感配置应存储在：

1. **环境变量**（推荐）
   ```bash
   export EMAIL_CONFIG_PATH="/path/to/secure/config.json"
   export TARGET_RECIPIENT="user@example.com"
   export NOTIFICATION_CHAT_ID="oc_xxx"
   ```

2. **加密配置文件**（需确保不在 git 追踪范围内）
   - 存放在 `~/.openclaw/workspace/memory/` 目录
   - 已在 `.gitignore` 中排除

## 目录结构

```
moltecho/
├── skills/                 # Skills 技能模块
│   └── rpctvm/            # 邮箱报告技能
│       ├── SKILL.md       # 技能文档
│       └── summarize_sent.py  # 邮件处理脚本
├── agents/                 # Agents 配置（可选）
├── .gitignore             # Git 忽略规则
└── README.md              # 本文件
```

## 使用方法

### 克隆仓库

```bash
git clone https://github.com/tsunchen/moltecho.git
```

### 配置邮箱凭证

创建配置文件（**勿提交到仓库**）：

```json
{
  "email": "your-email@example.com",
  "imap_server": "imap.example.com",
  "imap_port": 993,
  "auth_code": "your-auth-code"
}
```

### 运行脚本

```bash
# 日报（最近1天）
python skills/rpctvm/summarize_sent.py --days 1

# 周报（最近7天）
python skills/rpctvm/summarize_sent.py --days 7
```

## Git 操作规范

1. **提交前检查**：
   ```bash
   git diff --stat
   git grep -i "password\|secret\|token\|auth_code"
   ```

2. **使用 .gitignore**：
   - 所有 `*_credentials.json` 文件已自动排除
   - Session 日志文件已排除
   - 环境变量文件已排除

3. **Token 管理**：
   - GitHub Token 仅存储在本地环境变量
   - 使用 `ghp_` 开头的 Classic PAT 时确保权限最小化

## License

GPL-3.0