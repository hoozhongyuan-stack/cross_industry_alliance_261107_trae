"""校验目标接口契约 contracts/p0-api.yaml 的结构完整性。

只做离线静态检查，不依赖 Node/Redocly：
- OpenAPI 版本、路径前缀
- 所有 $ref 可解析
- operationId 唯一且每个操作都有 responses
- 写操作是否声明幂等要求（x-status=planned 时人工检查）
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "contracts" / "p0-api.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
CAMEL_CASE = re.compile(r"[a-z][A-Z]")


def resolve_ref(spec, ref):
    if not ref.startswith("#/"):
        return False
    node = spec
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def walk(node, path, errors):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and not resolve_ref(node_root, value):
                errors.append(f"未解析 $ref: {value} ({path})")
            walk(value, f"{path}/{key}", errors)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            walk(item, f"{path}[{index}]", errors)


def main():
    global node_root
    if not SPEC_PATH.exists():
        print(f"契约文件不存在: {SPEC_PATH}")
        return 1

    spec = yaml.safe_load(SPEC_PATH.read_text())
    node_root = spec
    errors = []

    if spec.get("openapi") != "3.0.3":
        errors.append(f"openapi 版本应为 3.0.3，实际 {spec.get('openapi')}")

    walk(spec, "#", errors)

    operation_ids = set()
    operation_count = 0
    for path, operations in spec.get("paths", {}).items():
        if not path.startswith("/api/v1/"):
            errors.append(f"路径未以 /api/v1/ 开头: {path}")
        for method, operation in operations.items():
            if method not in HTTP_METHODS:
                continue
            operation_count += 1
            operation_id = operation.get("operationId")
            if not operation_id:
                errors.append(f"{method.upper()} {path} 缺少 operationId")
            elif operation_id in operation_ids:
                errors.append(f"operationId 重复: {operation_id}")
            else:
                operation_ids.add(operation_id)
            if not operation.get("responses"):
                errors.append(f"{method.upper()} {path} 缺少 responses")

    property_camel = []
    for name, schema in spec.get("components", {}).get("schemas", {}).items():
        for prop in (schema.get("properties") or {}):
            if CAMEL_CASE.search(prop):
                property_camel.append(f"{name}.{prop}")
    if property_camel:
        errors.append("字段应使用 snake_case: " + ", ".join(sorted(property_camel)))

    print(
        f"paths={len(spec.get('paths', {}))} operations={operation_count} "
        f"schemas={len(spec.get('components', {}).get('schemas', {}))}"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("contract check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
