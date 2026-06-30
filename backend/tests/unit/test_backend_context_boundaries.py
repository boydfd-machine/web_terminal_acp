from __future__ import annotations

import ast
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"
CONTEXTS_ROOT = APP_ROOT / "contexts"
CANONICAL_ROOTS = (
    CONTEXTS_ROOT,
    APP_ROOT / "platform",
    APP_ROOT / "shared",
)
LEGACY_FACADE_ROOTS = (
    APP_ROOT / "agent_plugins",
    APP_ROOT / "agent_tools",
    APP_ROOT / "artifact_plugins",
    APP_ROOT / "domain",
    APP_ROOT / "repositories",
    APP_ROOT / "routers",
    APP_ROOT / "schemas",
    APP_ROOT / "services",
)

LEGACY_BUSINESS_PREFIXES = (
    "app.agent_plugins",
    "app.agent_tools",
    "app.artifact_plugins",
    "app.domain",
    "app.repositories",
    "app.routers",
    "app.schemas",
    "app.services",
)
DOMAIN_FORBIDDEN_PREFIXES = (
    "app.config",
    "app.db",
    "app.models",
    "fastapi",
    "sqlalchemy",
)

DOMAIN_IMPORT_ALLOWLIST: set[str] = set()

API_INFRASTRUCTURE_IMPORT_ALLOWLIST: set[str] = set()

CROSS_CONTEXT_INFRASTRUCTURE_IMPORT_ALLOWLIST: set[str] = set()

LEGACY_FACADE_ALLOWLIST = {
    "schemas/__init__.py",
    "schemas/agent_records.py",
    "schemas/misc.py",
    "schemas/windows.py",
}


def test_canonical_modules_do_not_import_legacy_business_facades():
    violations: list[tuple[Path, int, str]] = []
    for root in CANONICAL_ROOTS:
        for path in _python_files(root):
            for lineno, module in _app_imports(path):
                if not module.startswith(LEGACY_BUSINESS_PREFIXES):
                    continue
                violations.append((path, lineno, module))

    assert _format_import_violations(violations) == []


def test_domain_modules_are_pure_rules_and_values():
    violations: list[tuple[Path, int, str]] = []
    for path in _python_files(CONTEXTS_ROOT):
        _context_name, layer = _context_and_layer(path)
        if layer != "domain":
            continue
        for lineno, module in _app_imports(path):
            _imported_context, imported_layer = _context_import(module)
            if (
                imported_layer in {"api", "application", "infrastructure"}
                or module.startswith(DOMAIN_FORBIDDEN_PREFIXES)
            ):
                violations.append((path, lineno, module))

    assert _without_allowlist(violations, DOMAIN_IMPORT_ALLOWLIST) == []


def test_api_modules_do_not_import_infrastructure():
    violations: list[tuple[Path, int, str]] = []
    for path in _python_files(CONTEXTS_ROOT):
        _context_name, layer = _context_and_layer(path)
        if layer != "api":
            continue
        for lineno, module in _app_imports(path):
            _imported_context, imported_layer = _context_import(module)
            if imported_layer != "infrastructure":
                continue
            violations.append((path, lineno, module))

    assert _without_allowlist(violations, API_INFRASTRUCTURE_IMPORT_ALLOWLIST) == []


def test_legacy_business_paths_are_only_facades():
    violations: list[str] = []
    for root in LEGACY_FACADE_ROOTS:
        for path in _python_files(root):
            relative_path = str(path.relative_to(APP_ROOT))
            if relative_path in LEGACY_FACADE_ALLOWLIST:
                continue
            if _is_package_marker(path):
                continue
            if _assigns_module_alias(path):
                continue
            violations.append(relative_path)

    assert violations == []


def test_contexts_do_not_import_other_context_infrastructure():
    violations: list[tuple[Path, int, str]] = []
    for path in _python_files(CONTEXTS_ROOT):
        context_name, layer = _context_and_layer(path)
        if layer is None:
            continue

        for lineno, module in _app_imports(path):
            imported_context, imported_layer = _context_import(module)
            if imported_context in {None, context_name}:
                continue
            if imported_layer == "infrastructure":
                violations.append((path, lineno, module))

    assert _without_allowlist(violations, CROSS_CONTEXT_INFRASTRUCTURE_IMPORT_ALLOWLIST) == []


def test_application_entrypoint_uses_context_routes_and_services():
    violations: list[tuple[Path, int, str]] = []
    main_path = APP_ROOT / "main.py"

    for lineno, module in _app_imports(main_path):
        if not module.startswith(LEGACY_BUSINESS_PREFIXES):
            continue
        violations.append((main_path, lineno, module))

    assert _format_import_violations(violations) == []


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _app_imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _is_package_marker(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return all(isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) for node in tree.body)


def _assigns_module_alias(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if _is_sys_modules_name_assignment(target):
                return True
    return False


def _is_sys_modules_name_assignment(node: ast.AST) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    if not isinstance(node.value, ast.Attribute):
        return False
    if not isinstance(node.value.value, ast.Name):
        return False
    if node.value.value.id != "sys" or node.value.attr != "modules":
        return False
    return isinstance(node.slice, ast.Name) and node.slice.id == "__name__"


def _without_allowlist(
    violations: list[tuple[Path, int, str]],
    allowlist: set[str],
) -> list[str]:
    actual = {_import_violation_key(path, module) for path, _lineno, module in violations}
    stale = sorted(allowlist - actual)
    unexpected = [
        violation
        for violation in _format_import_violations(violations)
        if _import_violation_key_from_text(violation) not in allowlist
    ]
    if stale:
        unexpected.extend(f"stale allowlist entry: {entry}" for entry in stale)
    return unexpected


def _format_import_violations(violations: list[tuple[Path, int, str]]) -> list[str]:
    return [
        f"{path.relative_to(APP_ROOT)}:{lineno} imports {module}"
        for path, lineno, module in violations
    ]


def _import_violation_key(path: Path, module: str) -> str:
    return f"{path.relative_to(APP_ROOT)} imports {module}"


def _import_violation_key_from_text(value: str) -> str:
    path, _line_and_import, _module = value.partition(":")
    _line, _separator, module = value.partition(" imports ")
    return f"{path} imports {module}"


def _context_and_layer(path: Path) -> tuple[str, str | None]:
    relative = path.relative_to(CONTEXTS_ROOT)
    parts = relative.parts
    layer = parts[1] if len(parts) > 2 else None
    return parts[0], layer


def _context_import(module: str) -> tuple[str | None, str | None]:
    prefix = "app.contexts."
    if not module.startswith(prefix):
        return None, None
    parts = module[len(prefix):].split(".")
    if len(parts) < 2:
        return parts[0], None
    return parts[0], parts[1]
