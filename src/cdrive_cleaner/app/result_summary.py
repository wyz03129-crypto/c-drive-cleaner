"""User-readable failure reasons without storing sensitive file paths."""

from collections import Counter

from cdrive_cleaner.domain import CleanupReceipt

REASONS = {
    "backup_not_completed": "备份/校验未完成，原文件未确认删除；请检查隔离盘空间、卷、权限及记录",
    "application_running": "相关应用仍在运行：完全退出后重新扫描",
    "process_state_unknown": "无法确认应用状态：本次跳过",
    "elevation_required": "需要管理员权限",
    "file_in_use": "文件正在使用：关闭相关应用后重新扫描",
    "permission_denied": "权限不足或文件只读",
    "identity_changed": "扫描后文件已变化：重新扫描",
    "not_found": "文件已不存在",
    "protected_name": "受保护的文件类型或名称",
    "denylisted": "位于受保护目录",
    "project_tree": "位于项目目录",
    "reparse_point": "链接或重解析点：不跟随",
    "rule_predicate": "不满足文件年龄或名称限制",
    "rule_changed": "规则或清理计划不匹配：重新扫描",
    "os_error": "系统拒绝操作或文件身份变化：本次跳过",
}


def failure_summary(receipt: CleanupReceipt) -> str:
    counts = Counter(
        result.error_code
        or (result.authorization_code.value if result.authorization_code else "unknown")
        for result in receipt.results
        if result.status.value in {"skipped", "denied"}
    )
    return "\n".join(f"{REASONS.get(code, code)}：{count} 项" for code, count in counts.items())
