# pfjtmr Skill - Monthrear Report Workflow

## 职责

每月23日提醒用户检查并处理 `monthrear` 项目的 WAN 接口报告。

## 任务流程

1. 检查 Win10-Node 上的 PDF 目录：
   ```
   <WAN_INTF_DIR>/*.pdf
   ```

2. 查找最新的 PDF 文件（格式：`Versa-Analytics-Sites-usage-Report-YYYYMMDD-YYYYMMDD.pdf`）

3. 向用户报告发现的新 PDF 文件，等待确认

4. 用户确认后，在 Win10-Node 执行任务：
   ```powershell
   # 1. 切换到工作目录
   cd <WORK_DIR>
   
   # 2. 刷新 PATH（确保 Java 可用）
   $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
   
   # 3. 运行任务（不需要 --no-sync）
   uv run .\reportwork.py shct pfjt monthrear wan_intf --date <日期范围>
   ```

5. 报告执行结果

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PFJTMR_WORK_DIR` | Win10-Node 工作目录 | 从本地配置读取 |
| `PFJTMR_WAN_INTF_DIR` | PDF 文件目录 | 从本地配置读取 |
| `PFJTMR_UV_PATH` | uv 可执行文件路径 | 从本地配置读取 |

## 输出文件

- CSV: `shct\pfjt\monthrear\result\outtab-YYYYMMDD-YYYYMMDD.csv`
- Word: `shct\pfjt\monthrear\result\Selected_Columns_YYYYMMDD-YYYYMMDD.docx`

## 注意事项

- Win10-Node 是 32 位系统
- Python 环境已配置在 `.venv` 中
- 依赖：numpy 1.23.5, pandas 2.0.3, tabula-py, pymupdf, python-docx
- 需要 Java 环境（Zulu JDK 17）

## 定时任务

- **时间**: 每月23日 9:00 (Asia/Shanghai)
- **Job ID**: `a9e9639a-7095-469f-8a46-d5da41e01174`