from app.services.ast_context import extract_ast_context


def test_extracts_python_function_context() -> None:
    source = "\n".join(
        [
            "def helper():",
            "    return 1",
            "",
            "def target(value):",
            "    result = value + 1",
            "    return result",
        ]
    )

    contexts = extract_ast_context("src/service.py", source, [5])

    assert len(contexts) == 1
    assert contexts[0].symbol == "target"
    assert contexts[0].start_line == 4
    assert contexts[0].end_line == 6
    assert contexts[0].changed_lines == [5]
    assert "return result" in contexts[0].code
    assert contexts[0].degraded is False


def test_extracts_python_class_method_context() -> None:
    source = "\n".join(
        [
            "class OrderService:",
            "    def create_order(self, data):",
            "        order = data.copy()",
            "        return order",
            "",
            "    def cancel_order(self, order_id):",
            "        return order_id",
        ]
    )

    contexts = extract_ast_context("src/order_service.py", source, [3, 4])

    assert len(contexts) == 1
    assert contexts[0].symbol == "OrderService.create_order"
    assert contexts[0].start_line == 2
    assert contexts[0].end_line == 4
    assert contexts[0].changed_lines == [3, 4]
    assert "order = data.copy()" in contexts[0].code


def test_changed_line_outside_symbol_degrades_to_file_context() -> None:
    source = "\n".join(
        [
            "CONSTANT = 1",
            "",
            "def target():",
            "    return CONSTANT",
        ]
    )

    contexts = extract_ast_context("src/config.py", source, [1])

    assert len(contexts) == 1
    assert contexts[0].symbol is None
    assert contexts[0].start_line == 1
    assert contexts[0].end_line == 4
    assert contexts[0].changed_lines == [1]
    assert contexts[0].degraded is True
    assert contexts[0].reason == "changed lines are outside symbols"


def test_syntax_error_degrades_to_file_context() -> None:
    source = "def broken(:\n    return 1"

    contexts = extract_ast_context("src/broken.py", source, [1])

    assert len(contexts) == 1
    assert contexts[0].symbol is None
    assert contexts[0].language == "python"
    assert contexts[0].degraded is True
    assert contexts[0].reason == "python ast parse failed"


def test_unsupported_language_degrades_to_file_context() -> None:
    """不支持的语言（如 Ruby）降级为整文件上下文。"""
    source = "def hello\n  puts 'hello'\nend"

    contexts = extract_ast_context("src/app.rb", source, [1])

    assert len(contexts) == 1
    assert contexts[0].symbol is None
    assert contexts[0].language == "unknown"
    assert contexts[0].changed_lines == [1]
    assert contexts[0].degraded is True
    assert contexts[0].reason == "unsupported language"


def test_multiple_changed_symbols_return_multiple_contexts() -> None:
    source = "\n".join(
        [
            "def first():",
            "    return 1",
            "",
            "def second():",
            "    return 2",
        ]
    )

    contexts = extract_ast_context("src/service.py", source, [2, 5])

    assert [context.symbol for context in contexts] == ["first", "second"]
    assert [context.changed_lines for context in contexts] == [[2], [5]]


# ==================== JS/TS/Java 测试 ====================


def test_extracts_javascript_function_context() -> None:
    """测试 JS function 声明提取。"""
    source = "\n".join([
        "const x = 1;",
        "",
        "function fetchData(url) {",
        "  const result = fetch(url);",
        "  return result;",
        "}",
        "",
        "const y = 2;",
    ])

    contexts = extract_ast_context("src/api.js", source, [4])

    assert len(contexts) == 1
    assert contexts[0].symbol == "fetchData"
    assert contexts[0].start_line == 3
    assert contexts[0].end_line == 6
    assert contexts[0].changed_lines == [4]
    assert contexts[0].language == "javascript"
    assert contexts[0].degraded is False


def test_extracts_typescript_arrow_function_context() -> None:
    """测试 TS 箭头函数提取。"""
    source = "\n".join([
        "import { useState } from 'react';",
        "",
        "const calculateTotal = (items: Item[]) => {",
        "  let total = 0;",
        "  for (const item of items) {",
        "    total += item.price;",
        "  }",
        "  return total;",
        "};",
        "",
        "export default calculateTotal;",
    ])

    contexts = extract_ast_context("src/utils.ts", source, [5])

    assert len(contexts) == 1
    assert contexts[0].symbol == "calculateTotal"
    assert contexts[0].start_line == 3
    assert contexts[0].end_line == 9
    assert contexts[0].changed_lines == [5]
    assert contexts[0].language == "typescript"
    assert contexts[0].degraded is False


def test_extracts_java_method_context() -> None:
    """测试 Java 类方法提取。"""
    source = "\n".join([
        "package com.example;",
        "",
        "public class UserService {",
        "",
        "    public String getUserName(int id) {",
        "        String name = repository.findById(id);",
        "        return name;",
        "    }",
        "",
        "    private void logAccess(int id) {",
        "        System.out.println(id);",
        "    }",
        "}",
    ])

    contexts = extract_ast_context("src/UserService.java", source, [6])

    assert len(contexts) == 1
    assert "getUserName" in contexts[0].symbol
    assert contexts[0].start_line == 5
    assert contexts[0].end_line == 8
    assert contexts[0].changed_lines == [6]
    assert contexts[0].language == "java"
    assert contexts[0].degraded is False


def test_java_changed_line_outside_method_degrades() -> None:
    """测试 Java 变更行在方法外时降级为整文件。"""
    source = "\n".join([
        "package com.example;",
        "",
        "public class Config {",
        "    private static final int MAX = 100;",
        "",
        "    public int getValue() {",
        "        return MAX;",
        "    }",
        "}",
    ])

    contexts = extract_ast_context("src/Config.java", source, [4])

    assert len(contexts) == 1
    assert contexts[0].symbol is None
    assert contexts[0].degraded is True
    assert contexts[0].language == "java"
    assert contexts[0].reason == "changed lines are outside symbols"