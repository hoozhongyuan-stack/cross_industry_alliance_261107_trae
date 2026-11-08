# 错误码与响应约定

## 现状（P0）

- 业务接口走 DRF 默认异常结构：`{"detail": "..."}`，HTTP 状态码表达类别。
- 401：未登录或 token 失效；403：角色/数据范围不足；409：状态冲突（订单状态机、记账失败）；422：参数校验。
- 订单非法迁移抛 `InvalidTransition`，记账抛 `LedgerError` 子类；**尚未**统一映射为错误码响应（TBD）。

## 目标（P1，未实现）

统一响应包裹：

```json
{
  "code": "ORDER_STATE_CONFLICT",
  "message": "订单处于 PENDING_PAYMENT，不接受事件 MERCHANT_ACCEPT",
  "request_id": "...",
  "details": {}
}
```

## 错误码清单（TBD：待 P1 落地后与代码对齐）

| code | HTTP | 含义 | 来源 |
|---|---|---|---|
| `AUTH_REQUIRED` | 401 | 未登录 / token 失效 | SimpleJWT |
| `PERMISSION_DENIED` | 403 | 无角色或跨商户访问 | 权限层 |
| `ORDER_STATE_CONFLICT` | 409 | 订单当前状态不接受该事件 | `InvalidTransition` |
| `LEDGER_UNBALANCED` | 409 | 借贷不平 | `UnbalancedTransaction` |
| `LEDGER_NEGATIVE_BALANCE` | 409 | 余额不足（pending/frozen/withdrawing） | `NegativeBalance` |
| `IDEMPOTENCY_CONFLICT` | 409 | 幂等键复用但业务参数不一致 | TBD |
| `VALIDATION_ERROR` | 422 | 字段校验失败 | serializer |

## 约定

- 新增错误码必须先改本表，再改代码与测试。
- 错误信息面向用户可读，不暴露堆栈、SQL、密钥。
- 所有写接口的错误响应必须可重试或明确不可重试；不可重试的要给出下一步动作。
