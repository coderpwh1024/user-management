"""角色编码校验器单元测试。"""
import pytest

from app.utils.validators import validate_role_code


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("admin", "ADMIN"),       # 小写规整为大写
        ("ADMIN", "ADMIN"),       # 已大写
        (" guest ", "GUEST"),     # 去除首尾空白
        ("role_1", "ROLE_1"),     # 含数字与下划线
        ("ab", "AB"),             # 最短 2 位边界
        ("A" * 64, "A" * 64),     # 最长 64 位边界
    ],
)
def test_validate_role_code_ok(raw: str, expected: str) -> None:
    """合法角色编码应通过并规整为大写。"""
    assert validate_role_code(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",            # 空串
        "a",           # 少于 2 位
        "A" * 65,      # 超过 64 位
        "admin-1",     # 含非法字符 '-'
        "角色",        # 中文
        "ad min",      # 含空格
    ],
)
def test_validate_role_code_invalid(raw: str) -> None:
    """非法角色编码应抛出 ValueError。"""
    with pytest.raises(ValueError):
        validate_role_code(raw)
