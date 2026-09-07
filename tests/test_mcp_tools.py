from app.mcp_server import tools


def test_find_definition_locates_function(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)
    (tmp_path / "sample.py").write_text(
        "def target_func(x):\n    return x + 1\n", encoding="utf-8"
    )

    result = tools.find_definition("target_func")

    assert "target_func" in result
    assert "sample.py" in result


def test_find_definition_missing_symbol(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)
    (tmp_path / "sample.py").write_text("def other():\n    pass\n", encoding="utf-8")

    result = tools.find_definition("does_not_exist")

    assert "No definition found" in result


def test_apply_patch_replaces_function_body(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def broken():\n    return 1 / 0\n", encoding="utf-8")

    result = tools.apply_patch(
        "sample.py",
        "broken",
        "def broken():\n    return 42\n"
    )

    assert "Successfully patched" in result
    assert "return 42" in target.read_text(encoding="utf-8")


def test_apply_patch_rejects_missing_function(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def real_func():\n    pass\n", encoding="utf-8")

    result = tools.apply_patch("sample.py", "ghost_func", "def ghost_func():\n    pass\n")

    assert "not found" in result


def test_read_file_blocks_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")

    result = tools.read_file("../secret.txt")

    assert "Access denied" in result


def test_write_file_blocks_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)

    result = tools.write_file("../escape.py", "print('pwned')")

    assert "Access denied" in result
    assert not (tmp_path.parent / "escape.py").exists()
