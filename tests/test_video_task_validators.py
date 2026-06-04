"""视频链接校验器单元测试。"""
import pytest

from app.utils.validators import validate_video_url


@pytest.mark.parametrize(
    "url",
    [
        "http://a.com/v.mp4",
        "https://cdn.example.com/path/to/video.mp4",
        "HTTPS://CDN.EXAMPLE.COM/v.mp4",
        "  https://x.com/v.mp4  ",  # 首尾空白应被去除
    ],
)
def test_valid_video_url(url: str) -> None:
    """合法链接应通过并去除首尾空白。"""
    assert validate_video_url(url).startswith(("http://", "https://", "HTTPS://"))


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "ftp://a.com/v.mp4",
        "a.com/v.mp4",
        "javascript:alert(1)",
        "https://has space.com/v.mp4",
    ],
)
def test_invalid_video_url(url: str) -> None:
    """非法链接应抛 ValueError。"""
    with pytest.raises(ValueError):
        validate_video_url(url)
