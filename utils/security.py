import bcrypt

BCRYPT_MAX_BYTES = 72


def _to_bytes(password: str) -> bytes:
    """转成 bcrypt 需要的字节，并守住 72 字节上限。

    bcrypt 只处理前 72 字节，且 bcrypt 5.0 对超长输入会直接抛错（不再像旧版那样静默截断）。
    这里提前拦截并给出明确提示，避免变成一个看不懂的 500。
    """
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError(f"密码过长：UTF-8 编码后 {len(raw)} 字节，上限 {BCRYPT_MAX_BYTES} 字节")
    return raw


def get_hash_password(password: str) -> str:
    """生成密码哈希，返回值可直接入库。"""
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """校验明文密码与库中哈希是否匹配。

    超长密码（>72 字节）在这里按「不匹配」处理，而不是让它抛 ValueError：
    登录接口不应该因为用户多打了几个字就返回 500。
    """
    try:
        return bcrypt.checkpw(_to_bytes(password), hashed.encode("utf-8"))
    except ValueError:
        return False
