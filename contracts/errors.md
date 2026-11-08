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
| `PAYMENT_NOT_FOUND` | 404 | 支付单不存在 | 支付回调 |
| `PAYMENT_NOT_SUCCESS` | 400 | 支付状态不是 SUCCESS | 支付回调 |
| `PAYMENT_TRANSACTION_CONFLICT` | 409 | 交易号与已支付记录不一致 | 支付回调 |
| `WECHAT_PAY_NOT_CONFIGURED` | 503 | 真实微信支付未接入 | 支付适配层 |
| `PRODUCT_NOT_AVAILABLE` | 409 | 商品不存在或已下架 | 购物车/下单 |
| `MERCHANT_NOT_AVAILABLE` | 409 | 商户不存在或未营业 | 下单 |
| `MERCHANT_MISMATCH` | 409 | 商品不属于订单商户 | 下单 |
| `DELIVERY_TYPE_NOT_SUPPORTED` | 409 | 订单类型与商品类型不匹配 | 下单 |
| `APPOINTMENT_REQUIRED` | 409 | 服务商品未选择预约时段 | 下单 |
| `SLOT_NOT_AVAILABLE` | 409 | 预约时段不存在或不可用 | 下单 |
| `SKU_NOT_FOUND` | 409 | 规格不存在或不属于商品 | 购物车/下单 |
| `CROSS_STORE_CART` | 409 | 跨店购物车 | 购物车 |
| `ACCOUNT_UNION_CONFLICT` | 409 | 手机号账号已绑定其他微信身份 | 短信登录 |
| `ACCOUNT_DISABLED` | 403 | 账号被禁用 | 登录 |
| `SMS_CODE_INVALID` | 422 | 验证码错误或已过期 | 短信登录 |
| `WECHAT_NOT_CONFIGURED` | 503 | 真实微信登录未接入 | 认证适配层 |
| `SMS_NOT_CONFIGURED` | 503 | 短信服务商未确定 | 短信适配层 |
| `NOT_FOUND` | 404 | 资源不存在或无权访问 | 通用 |
| `LEDGER_UNBALANCED` | 409 | 借贷不平 | `UnbalancedTransaction` |
| `LEDGER_NEGATIVE_BALANCE` | 409 | 余额不足（pending/frozen/withdrawing） | `NegativeBalance` |
| `RATE_LIMITED` | 429 | 触发限流 | 限流中间件 |

## 约定

- 新增错误码必须先在 `p0-api.yaml` 与本表登记，再改代码与测试。
- 错误信息面向用户可读，不暴露堆栈、SQL、密钥。
- 写接口的错误必须明确“可重试 / 不可重试”；不可重试时在 `message` 或 `details` 给出下一步动作。
- 回调接口失败返回非 200，让微信重试；禁止把失败包装成 200。
