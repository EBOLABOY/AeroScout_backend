"""
密码工具函数
"""
from passlib.context import CryptContext

# 密码加密上下文 - 支持多种哈希算法
pwd_context = CryptContext(
    schemes=["bcrypt", "scrypt"],
    deprecated="auto"
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码 - 支持bcrypt和scrypt格式"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        from loguru import logger
        # 记录更详细的错误，以便调试
        logger.warning(f"密码验证时发生异常: {e}")
        return False


def get_password_hash(password: str) -> str:
    """生成密码哈希 - 默认使用bcrypt"""
    return pwd_context.hash(password, scheme="bcrypt")