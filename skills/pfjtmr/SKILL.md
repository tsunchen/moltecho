# pfjtmr Skill - Monthrear Report Workflow

## 职责

每月23日提醒用户检查并处理 `monthrear` 项目的 WAN 接口报告。

## 任务流程

### 1. 检查 PDF 源文件

检查 Win10-Node 上的 PDF 目录：
```
{WORK_DIR}/shct/pfjt/monthrear/data/wan_intf/
```

具体路径从 `config.json` 读取。

查找最新的 PDF 文件（格式：`Versa-Analytics-Sites-usage-Report-YYYYMMDD-YYYYMMDD.pdf`）

### 2. 向用户报告

发现新 PDF 文件后，向用户报告：
- 文件名
- 日期范围
- 状态

### 3. 用户确认后执行

执行报告生成任务。

## Win10-Node 授权配置

### 节点信息

| 配置项 | 值 |
|--------|-----|
| 节点名 | `DESKTOP-58PJJ39` |
| 平台 | Windows 10 x86 (32-bit) |
| 模式 | `gateway.mode: "remote"` |

### 已授权命令

```bash
# 添加 Python 虚拟环境授权
openclaw approvals allowlist add --node "DESKTOP-58PJJ39" --agent "main" "C:\\44.189\\aworkflow\\applet\\py\\Reportwork\\Reportwork\\.venv\\Scripts\\*.exe"

# 添加 uv 授权
openclaw approvals allowlist add --node "DESKTOP-58PJJ39" --agent "main" "C:\\Users\\moltsunx\\.local\\bin\\uv.exe"
```

### 授权检查命令

```bash
# 检查节点状态
openclaw nodes status

# 测试命令执行
openclaw nodes invoke --node "DESKTOP-58PJJ39" --command "system.run" --params '{"command": ["C:\\Windows\\system32\\whoami.exe"]}'
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PFJTMR_WORK_DIR` | Win10-Node 工作目录 | 从 config.json 读取 |
| `PFJTMR_WAN_INTF_DIR` | PDF 文件目录 | `{WORK_DIR}/shct/pfjt/monthrear/data/wan_intf` |
| `PFJTMR_RESULT_DIR` | 输出目录 | `{WORK_DIR}/shct/pfjt/monthrear/result` |

## 执行命令

### ✅ 推荐方式：uv run

**脚本已修复**（2026-03-24），现在可以直接使用 `uv run`：

```powershell
cd C:\44.189\aworkflow\applet\py\Reportwork\Reportwork
uv run .\reportwork.py shct pfjt monthrear wan_intf --date YYYYMMDD-YYYYMMDD
```

### 脚本修复说明

**文件**: `reportwork.py`

**修改内容**: 将硬编码的 `python` 替换为 `sys.executable`

| 行号 | 修改前 | 修改后 |
|------|--------|--------|
| 61 | `cmd1 = f"python {script} ..."` | `cmd1 = [sys.executable, script, ...]` |
| 63 | `subprocess.run(cmd1, shell=True, ...)` | `subprocess.run(cmd1, check=True)` |
| 67 | `cmd2 = f"python {script} ..."` | `cmd2 = [sys.executable, script, ...]` |
| 69 | `subprocess.run(cmd2, shell=True, ...)` | `subprocess.run(cmd2, check=True)` |

**关键修改**:
- 使用 `sys.executable` 代替硬编码的 `"python"`
- 移除 `shell=True`（不再需要 shell 解析）
- 使用列表格式传递参数（更安全）

### 备用方式：直接调用子脚本

如果 `uv` 不可用，可以直接调用子脚本：

```python
# 步骤1: 提取 CSV
nodes invoke --node "{NODE_NAME}" --command "system.run" --params '{
  "command": ["{PYTHON_VENV}",
              "{WORK_DIR}/shct/pfjt/monthrear/wan_intf/src/tabdf_monthrear.py",
              "-p", "{WAN_INTF_DIR}/Versa-Analytics-Sites-usage-Report-YYYYMMDD-YYYYMMDD.pdf",
              "-o", "{RESULT_DIR}/outtab-YYYYMMDD-YYYYMMDD.csv"],
  "invokeTimeoutMs": 60000
}'

# 步骤2: 生成汇总 DOCX
nodes invoke --node "{NODE_NAME}" --command "system.run" --params '{
  "command": ["{PYTHON_VENV}",
              "{WORK_DIR}/shct/pfjt/monthrear/wan_intf/src/omni_monthrear.py",
              "-c", "{RESULT_DIR}/outtab-YYYYMMDD-YYYYMMDD.csv",
              "-o", "{RESULT_DIR}/Selected_Columns_YYYYMMDD-YYYYMMDD.docx"],
  "invokeTimeoutMs": 60000
}'
```

## 输出文件

| 文件 | 路径 | 说明 |
|------|------|------|
| CSV | `result/outtab-YYYYMMDD-YYYYMMDD.csv` | 提取的数据表 |
| DOCX | `result/Selected_Columns_YYYYMMDD-YYYYMMDD.docx` | 汇总报告（按租户聚合） |

### CSV 格式示例

```
Site,Sessions,VolumeTX,VolumeRX
PuFaJiTuan-000000-01-M,50.37 M,906.68 GB,536.39 GB
controller02,44.95 M,183.69 GB,190.62 GB
PuFaJiTuan-050100-04,8.98 M,80.51 GB,89.12 GB
...
```

### DOCX 汇总说明

`omni_monthrear.py` 脚本会：
1. 提取租户名称：`Site[0:13]` → `PuFaJiTuan-0`
2. 按租户分组求和：合并同一租户的 Sessions、VolumeTX、VolumeRX
3. 单位转换：
   - `50.37 M` → `50370000`（百万）
   - `906.68 GB` → `906.68`（数字）
4. 生成 Word 表格

## 依赖环境

### Python 虚拟环境

位置: `{WORK_DIR}/.venv/`

具体路径从 `config.json` 的 `python_venv` 字段读取。

### 已安装包

| 包名 | 版本 |
|------|------|
| pandas | 2.0.3 |
| numpy | 1.23.5 |
| tabula-py | 2.9.3 |
| pymupdf | 1.27.1 |
| python-docx | 1.2.0 |
| lxml | 6.0.2 |

### ⚠️ 注意：Java 依赖

`tabula-py` 需要 Java 环境：
- Zulu JDK 17 已安装
- 如果 `jpype` 模块缺失，会回退到 subprocess 模式
- 确保系统 PATH 包含 Java 路径

## 定时任务

| 任务 | 时间 | Job ID | 说明 |
|------|------|---------|------|
| 月度提醒 | 每月23日 9:00 (Asia/Shanghai) | `a9e9639a-7095-469f-8a46-d5da41e01174` | 提醒检查 WAN 接口报告 |

## 故障排除

### 问题1: "ModuleNotFoundError: No module named 'tabula'"

**原因**: 脚本使用系统 Python 而非虚拟环境 Python

**解决**: 
1. 使用 `uv run` 执行（已修复脚本）
2. 或直接调用虚拟环境 Python

```bash
.\.venv\Scripts\python.exe .\reportwork.py shct pfjt monthrear wan_intf --date YYYYMMDD-YYYYMMDD
```

### 问题2: "SYSTEM_RUN_DENIED: approval required"

**原因**: 节点命令未授权

**解决**: 添加命令到 allowlist

```bash
openclaw approvals allowlist add --node "DESKTOP-58PJJ39" --agent "main" "<命令路径>"
```

### 问题3: "gateway timeout"

**原因**: 命令执行时间过长

**解决**: 增加 `invokeTimeoutMs` 参数

```json
{
  "invokeTimeoutMs": 120000
}
```

### 问题4: 脚本执行失败 "python can't open file"

**原因**: `reportwork.py` 内部使用 `shell=True` 调用 `python`

**解决**: 脚本已修复，使用 `sys.executable` 代替硬编码的 `python`

## 安全边界

- 仅读取 PDF 和生成报告
- 不修改源文件
- 不发送外部网络请求
- 输出文件存储在本地目录

## 相关文档

- `/root/.openclaw/workspace/MEMORY.md` - Win10-Node 配置
- `/root/.openclaw/agents/pfjtmr/workspace/` - Agent 工作空间