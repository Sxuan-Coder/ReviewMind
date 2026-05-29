import ast
from dataclasses import dataclass

from app.schemas.ast_context import AstContext

PYTHON_EXTENSIONS = {".py"}


@dataclass(frozen=True)
class SymbolRange:
    symbol: str
    start_line: int
    end_line: int


def extract_ast_context(file_path: str, source_code: str, changed_lines: list[int]) -> list[AstContext]:
    language = detect_language(file_path)
    normalized_lines = sorted(set(line for line in changed_lines if line > 0))

    if language != "python":
        return [_file_context(file_path, source_code, normalized_lines, language, reason="unsupported language")]

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return [_file_context(file_path, source_code, normalized_lines, language, reason="python ast parse failed")]

    symbol_ranges = collect_python_symbol_ranges(tree)
    matched_ranges = [symbol_range for symbol_range in symbol_ranges if _overlaps(symbol_range, normalized_lines)]
    if not matched_ranges:
        return [_file_context(file_path, source_code, normalized_lines, language, reason="changed lines are outside symbols")]

    source_lines = source_code.splitlines()
    return [
        AstContext(
            file=file_path,
            symbol=symbol_range.symbol,
            start_line=symbol_range.start_line,
            end_line=symbol_range.end_line,
            changed_lines=[line for line in normalized_lines if symbol_range.start_line <= line <= symbol_range.end_line],
            language=language,
            code="\n".join(source_lines[symbol_range.start_line - 1 : symbol_range.end_line]),
        )
        for symbol_range in _dedupe_ranges(matched_ranges)
    ]


def detect_language(file_path: str) -> str:
    return "python" if file_path.endswith(tuple(PYTHON_EXTENSIONS)) else "unknown"


def collect_python_symbol_ranges(tree: ast.AST) -> list[SymbolRange]:
    ranges: list[SymbolRange] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.ClassDef):
            ranges.extend(_class_method_ranges(node))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            ranges.append(_node_range(node.name, node))
    return sorted(ranges, key=lambda item: (item.start_line, item.end_line, item.symbol))


def _class_method_ranges(class_node: ast.ClassDef) -> list[SymbolRange]:
    ranges: list[SymbolRange] = []
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            ranges.append(_node_range(f"{class_node.name}.{node.name}", node))
    return ranges


def _node_range(symbol: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> SymbolRange:
    return SymbolRange(
        symbol=symbol,
        start_line=node.lineno,
        end_line=getattr(node, "end_lineno", node.lineno),
    )


def _overlaps(symbol_range: SymbolRange, changed_lines: list[int]) -> bool:
    return any(symbol_range.start_line <= line <= symbol_range.end_line for line in changed_lines)


def _dedupe_ranges(ranges: list[SymbolRange]) -> list[SymbolRange]:
    seen: set[tuple[str, int, int]] = set()
    unique_ranges: list[SymbolRange] = []
    for item in ranges:
        key = (item.symbol, item.start_line, item.end_line)
        if key not in seen:
            seen.add(key)
            unique_ranges.append(item)
    return unique_ranges


def _file_context(
    file_path: str,
    source_code: str,
    changed_lines: list[int],
    language: str,
    reason: str,
) -> AstContext:
    source_lines = source_code.splitlines()
    return AstContext(
        file=file_path,
        symbol=None,
        start_line=1 if source_lines else 0,
        end_line=len(source_lines),
        changed_lines=changed_lines,
        language=language,
        code=source_code,
        degraded=True,
        reason=reason,
    )