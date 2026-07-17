"""字段校验工具单元测试。"""
import pytest

from app.utils.validators import validate_id_card, validate_phone, validate_video_url


class TestValidatePhone:
    def test_valid_phone(self):
        assert validate_phone("13800138000") == "13800138000"

    def test_strip_whitespace(self):
        assert validate_phone("  13900139000 ") == "13900139000"

    @pytest.mark.parametrize("bad", ["12345", "12800138000", "1380013800", "abc"])
    def test_invalid_phone(self, bad):
        with pytest.raises(ValueError):
            validate_phone(bad)


class TestValidateIdCard:
    def test_valid_id_card(self):
        # 该号码满足 GB11643 校验位规则
        assert validate_id_card("110101199003077352") == "110101199003077352"

    def test_lowercase_x_normalized(self):
        assert validate_id_card("11010119900101004x") == "11010119900101004X"

    @pytest.mark.parametrize(
        "bad",
        ["1101011990010112", "11010119900101123A", "110101199001011234"],
    )
    def test_invalid_id_card(self, bad):
        with pytest.raises(ValueError):
            validate_id_card(bad)


class TestValidateVideoUrl:
    """视频 URL 校验测试。"""

    @pytest.mark.parametrize("value", ["https://example.com/a.mp4", " http://example.com/a.mp4 "])
    def test_valid_video_url(self, value: str) -> None:
        """合法 HTTP(S) 视频地址应通过校验并去除首尾空白。"""
        assert validate_video_url(value).endswith("/a.mp4")

    @pytest.mark.parametrize("value", ["", "ftp://example.com/a.mp4", "not-a-url"])
    def test_invalid_video_url(self, value: str) -> None:
        """非法视频地址应拒绝。"""
        with pytest.raises(ValueError):
            validate_video_url(value)
