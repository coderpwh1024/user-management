"""通用字段校验工具。

提供手机号、身份证号等中国大陆常用证件 / 联系方式的格式校验。
"""
import re

# 中国大陆手机号：1 开头，第二位 3-9，共 11 位
_PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")

# 18 位身份证号：6 位地址码 + 8 位出生日期 + 3 位顺序码 + 1 位校验码
_ID_CARD_PATTERN = re.compile(r"^\d{17}[\dXx]$")

# 角色编码：字母 / 数字 / 下划线，2-64 位（统一规整为大写）
_ROLE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_]{2,64}$")

# 视频链接：必须以 http:// 或 https:// 开头
_VIDEO_URL_PATTERN = re.compile(r"^https?://\S+$", re.IGNORECASE)

# 身份证校验：加权因子与校验码映射
_ID_CARD_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_ID_CARD_CHECK_CODES = ["1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2"]


def validate_phone(phone: str) -> str:
    """校验手机号格式。

    :param phone: 待校验手机号。
    :return: 去除首尾空白后的手机号。
    :raises ValueError: 格式非法时抛出。
    """
    phone = (phone or "").strip()
    if not _PHONE_PATTERN.match(phone):
        raise ValueError("手机号格式不正确")
    return phone


def validate_id_card(id_card: str) -> str:
    """校验 18 位身份证号格式与校验位。

    :param id_card: 待校验身份证号。
    :return: 规整为大写后的身份证号。
    :raises ValueError: 格式或校验位非法时抛出。
    """
    id_card = (id_card or "").strip().upper()
    if not _ID_CARD_PATTERN.match(id_card):
        raise ValueError("身份证号格式不正确")

    total = sum(int(id_card[i]) * _ID_CARD_WEIGHTS[i] for i in range(17))
    expected = _ID_CARD_CHECK_CODES[total % 11]
    if id_card[-1] != expected:
        raise ValueError("身份证号校验位不正确")
    return id_card


def validate_video_url(video_url: str) -> str:
    """校验视频链接格式。

    :param video_url: 待校验视频链接。
    :return: 去除首尾空白后的视频链接。
    :raises ValueError: 非 http(s) 链接或为空时抛出。
    """
    video_url = (video_url or "").strip()
    if not _VIDEO_URL_PATTERN.match(video_url):
        raise ValueError("视频链接格式不正确（需以 http:// 或 https:// 开头）")
    return video_url


def validate_role_code(role_code: str) -> str:
    """校验角色编码格式。

    :param role_code: 待校验角色编码。
    :return: 去除首尾空白并规整为大写后的角色编码。
    :raises ValueError: 格式非法时抛出。
    """
    role_code = (role_code or "").strip().upper()
    if not _ROLE_CODE_PATTERN.match(role_code):
        raise ValueError("角色编码格式不正确（仅允许字母/数字/下划线，2-64 位）")
    return role_code
