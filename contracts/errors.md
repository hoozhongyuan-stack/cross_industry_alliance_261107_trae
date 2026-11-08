# 错误码与响应约定

## 契约状态

- **目标契约**：`contracts/p0-api.yaml` 已定义统一响应包裹与错误结构，P0 接口按此实现。
- **当前实现**：已实现的 13 个接口仍返回 DRF 默认 `{"detail": "..."}`；实现新接口时按目标契约输出，旧接口随迭代迁移。

## 目标响应包裹

```json
{
  "code": "OK",
  "message": "success",
  "traceId": "...",
  "data": {}
}
```

错误响应不含 `data`，包含可选的 `details`：

```json
{
  "code": "ORDER_STATE_CONFLICT",
  "message": "订单处于 PENDING_PAYMENT，不接受事件 MERCHANT_ACCEPT",
  "traceId": "...",
  "details": {}
}
```

## 错误码清单

| code | HTTP | 含义 | 来源 |
|---|---|---|---|
| `AUTH_REQUIRED` | 401 | 未登录 / Token 失效 | SimpleJWT |
| `PERMISSION_DENIED` | 403 | 无角色或跨商户访问 | 权限层 |
| `VALIDATION_ERROR` | 422 | 字段校验失败 | serializer |
| `ORDER_STATE_CONFLICT` | 409 | 订单当前状态不接受该事件 | `InvalidTransition` |
| `ORDER_EXPIRED` | 409 | 订单已超时关闭 | 订单服务 |
| `STOCK_NOT_ENOUGH` | 409 | 库存不足 | 库存服务 |
| `SLOT_FULL` | 409 | 预约时段已满 | 预约服务 |
| `VERIFY_CODE_INVALID` | 409 | 核销码无效 / 过期 / 非本店 | 核销服务 |
| `AFTER_SALE_NOT_ALLOWED` | 409 | 当前状态不支持售后 | 售后服务 |
| `REFUND_AMOUNT_EXCEEDED` | 409 | 退款超过可退金额 | 售后/退款服务 |
| `WITHDRAW_BALANCE_NOT_ENOUGH` | 409 | 可提现余额不足 | 提现服务 |
| `SETTLEMENT_NOT_DUE` | 409 | 结算项未到 `due_at` | 结算服务 |
| `IDEMPOTENCY_CONFLICT` | 409 | 幂等键复用但请求体不一致 | 幂等中间件 |
| `PAY_AMOUNT_MISMATCH` | 409 | 回调金额与支付单不一致 | 支付回调 |
| `LEDGER_UNBALANCED` | 409 | 借贷不平 | `UnbalancedTransaction` |
| `LEDGER_NEGATIVE_BALANCE` | 409 | 余额不足（pending/frozen/withdrawing） | `NegativeBalance` |
| `RATE_LIMITED` | 429 | 触发限流 | 限流中间件 |

## 约定

- 新增错误码必须先在 `p0-api.yaml` 与本表登记，再改代码与测试。
- 错误信息面向用户可读，不暴露堆栈、SQL、密钥。
- 写接口的错误必须明确“可重试 / 不可重试”；不可重试时在 `message` 或 `details` 给出下一步动作。
- 回调接口失败返回非 200，让微信重试；禁止把失败包装成 200。
