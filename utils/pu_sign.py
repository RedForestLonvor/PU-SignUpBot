import base64
import json
import time
import secrets
import string
from typing import Dict, Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

# 固定 16 字节密钥
PSK = bytes([121, 121, 0, 19, 5, 49, 2, 43, 13, 17, 11, 9, 4, 29, 60, 11])


def generate_random_echo(length: int = 16) -> str:
    """生成与 pu.js generateRandomString 等价的 62 字符随机串。"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def current_timestamp_str() -> str:
    """当前时间戳（秒）字符串。"""
    return str(int(time.time()))


def _aes_cbc_encrypt_pkcs7(plaintext_bytes: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    return cipher.encrypt(pad(plaintext_bytes, AES.block_size))


def _aes_cbc_decrypt_pkcs7(ciphertext_bytes: bytes, key: bytes, iv: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    return unpad(cipher.decrypt(ciphertext_bytes), AES.block_size)


def encrypt_payload_to_n(payload: Dict[str, Any], iv: bytes | None = None) -> str:
    """
    将明文 payload（字典）加密为 n（base64）。
    - 算法：AES-128-CBC + PKCS7；n = base64( IV(16) + CIPHER )
    - 若未提供 iv，则生成随机 16 字节 IV。
    """
    if iv is None:
        iv = get_random_bytes(16)
    if len(iv) != 16:
        raise ValueError("IV 必须是 16 字节")

    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = _aes_cbc_encrypt_pkcs7(plaintext, PSK, iv)
    combined = iv + ciphertext
    return base64.b64encode(combined).decode("ascii")


def generate_x_sign(echo: str | None = None, timestamp: str | None = None, client: str = "web",
                    iv: bytes | None = None) -> str:
    """
    生成 X-Sign：
    - echo：默认随机 16 位字母数字
    - timestamp：默认当前秒
    - client：默认 'web'
    - iv：可传固定 16 字节；不传则随机
    返回：n（base64）
    """
    if echo is None:
        echo = generate_random_echo()
    if timestamp is None:
        timestamp = current_timestamp_str()
    payload = {"echo": echo, "timestamp": timestamp, "client": client}
    return encrypt_payload_to_n(payload, iv=iv)
