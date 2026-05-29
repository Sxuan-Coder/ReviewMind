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
    source = "export const value = 1;"

    contexts = extract_ast_context("src/app.ts", source, [1])

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