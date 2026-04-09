# OKX 理财产品追踪 Skill

追踪 OKX 平台低风险投资机会，包括稳定币理财、ETH/SOL 质押、资金费率套利等。

## 功能

- 稳定币活期/定期理财收益追踪
- ETH/SOL 质押收益追踪
- 资金费率套利机会监控
- 定期推送最高收益产品报告

## 触发词

- OKX 理财
- 稳定币收益
- 资金费率
- ETH 质押
- SOL 质押
- OKX 收益
- 低风险投资

## 配置文件

配置文件位于 `memory/okx-earn-tracker.json`

## API 凭证

存储在 `memory/okx_credentials.json`

## 使用方式

### 手动查询

```
用户: OKX 理财收益
Agent: 执行 okx-earn-tracker skill，返回当前最高收益产品
```

### 定时推送

在 HEARTBEAT.md 中配置定期检查，推送到飞书群。

## 数据存储

- `memory/okx-earn-tracker.json`: 追踪配置和历史数据
- `memory/okx-earn-history.json`: 历史收益记录

## 输出示例

```
📊 OKX 理财产品收益报告 (2026-04-04)

🥇 USDT 活期最高: Morpho (Katana) 4.39%
🥈 USDC 活期最高: Spark (Ethereum) 3.56%
🥉 套利最高年化: ETH 7.00%

💡 推荐:
- 保守型: USDT Morpho 4.39%
- 稳健型: 60% USDT + 25% ETH质押 + 15% SOL质押
- 进取型: 40% USDT + 20% ETH质押 + 15% SOL质押 + 15% 套利
```