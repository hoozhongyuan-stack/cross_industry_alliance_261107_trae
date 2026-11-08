# AGENTS.md · 异业联盟商城后端

给人类与 AI 协作者的唯一入口。动手前先读本文件；涉及金额、状态、结算时，再读对应 service。
产品真值：`异业联盟商城系统_PRD_v0.2.html`；方案真值：`异业联盟商城系统_技术方案与数据模型_v1.0.html`。

## 1. 技术栈与定位

- Python 3.9 + Django 4.2 LTS + DRF + SimpleJWT；模块化单体，不做微服务。
- 数据库：开发 SQLite，生产 MySQL 8（`DB_ENGINE=mysql`）。
- 金额一律 BIGINT 存「分」；时间统一 Asia/Shanghai；主键 BigAutoField。
- 代码在 `backend/`，API 前缀 `/api/v1/`，契约在 `contracts/openapi.yaml`。

## 2. 目录地图

```
backend/
  config/          settings（含 DB 切换、JWT、spectacular）
  apps/common/     抽象模型、健康检查、单号生成
  apps/accounts/   用户、渠道身份、JWT 登录
  apps/merchants/  商户、员工、资质
  apps/catalog/    类目、商品、SKU、预约时段
  apps/orders/     订单、状态机（services.py）
  apps/payments/   支付单、退款单
  apps/fulfillment/配送、核销码、预约
  apps/aftersales/ 售后、仲裁、举证
  apps/ledger/     虚拟账户、复式记账、结算、提现
  apps/governance/ 规则版本、审核、操作日志、内容位
  apps/notifications/ 通知、Outbox
contracts/        OpenAPI 与错误码契约
```

## 3. 常用命令（在仓库根目录）

```bash
make install    # 建 venv，安装依赖
make dev        # runserver
make test       # pytest + 覆盖率门槛
make lint       # ruff check + format 检查
make check      # django check + 迁移一致性
make audit      # 资金对账：流水 vs 账户快照
make schema     # 重新生成 OpenAPI 契约
make verify     # 以上门禁总和，提交前必跑
```

CI（GitHub Actions）执行同一套 `make verify`；本地不通过，CI 一定不通过。

## 4. 硬规则

1. 金额只用整数「分」；禁止 float、禁止元/分混用。
2. 余额只能经 `apps/ledger/services.py::post_transaction` 变更；分录只追加，不改不删。
3. 每个记账事务必须借贷相等、带唯一 `idempotency_key`，并与业务状态在同一事务提交。
4. 订单状态只能经 `apps/orders/services.py::transit_order` 变更；非法迁移抛 `InvalidTransition`。
5. 写接口必须能回答「重复调用会怎样」；幂等键或唯一约束至少落一个。
6. 一张订单只有一个结算项（`unique(order)`）；`due_at = completed_at + merchant.settlement_cycle_days`。
7. 业务代码分层：view → serializer → service → model；view 不写业务规则，serializer 不做计算。
8. 未确认的业务规则标 `TBD` 并写进契约或注释，禁止凭空补规则、补默认值。
9. 密钥、商户号、证书只进 `.env`；`.env` 不入库，代码不写死。
10. 所有表结构变更必须生成迁移并提交；禁止手改数据库结构。

## 5. 常见任务 playbook

**新增一个接口**
1. 先写 serializer 字段与权限（消费者 / 商户 / 平台）。
2. 业务逻辑放 service；view 只做参数校验与调用。
3. 写测试：成功、越权、重复调用。
4. `make schema` 更新契约并一起提交。

**新增字段**
1. 改 model → `makemigrations` → `migrate`。
2. 检查是否需要快照（订单、结算项、佣金率必须快照）。
3. 补迁移到契约（如出现在响应中）。

**新增订单事件/状态**
1. 先改 `ORDER_TRANSITIONS` 与守卫条件。
2. 补时间戳副作用与 `OrderStatusLog`。
3. 补非法迁移测试与正常流转测试。

**新增记账事件**
1. 在 `post_transaction` 的调用方组装平衡分录，不新开写余额的入口。
2. 幂等键用业务唯一号（如 `payment:{payment_no}`）。
3. 补借贷平衡、幂等、负余额、对账命令测试。

## 6. 完成定义（DoD）

一个改动算完成，需同时满足：

- [ ] `make verify` 全绿
- [ ] 有迁移且 `makemigrations --check` 通过
- [ ] 关键路径有测试；资金/状态改动覆盖成功与失败分支
- [ ] 契约已更新（如有接口变化）
- [ ] 错误码、日志字段（order_no / txn_no / merchant_id）可定位问题
- [ ] 未定项标 TBD，没有伪造规则

## 7. 禁止事项

- 直接 `update()` 余额字段或写裸 SQL 改账。
- 删除、覆盖 `ledger_entry` / `ledger_transaction`。
- 删除失败单据或改状态「抹平」差异；差异走反向分录 + `AccountAdjustment`。
- 在 view 中计算佣金、结算金额或修改订单状态。
- 提交 `.env`、密钥、证书、真实银行信息。
- 为了让测试变绿而放宽 CHECK 约束或跳过测试。

## 8. 不确定时

先看 `contracts/errors.md` 与对应 app 的 `services.py`；仍不确定就把问题写成 `TBD` 并说明影响范围，不要自行发明业务规则。
