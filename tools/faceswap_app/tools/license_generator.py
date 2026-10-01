"""License Key 生成工具（开发者专用，不打包进 exe）

用法：
    python tools/license_generator.py

运行后交互式输入：
1. 机器码（用户提供的 FSA-XXXX-... ）
2. 有效期（天数，如 365，或输入 "permanent" 永久）
3. 授权类型（pro/enterprise）

输出：license key 字符串（发给用户）

依赖：读取 build/license_private_key.pem 私钥文件
"""
from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timedelta

# 让脚本在直接运行时能找到 core.license（开发模式下）
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_here)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from core.license import _b64url_encode

# 私钥路径（绝对不要打包进 exe，仅开发者使用）
PRIVATE_KEY_PATH = os.path.join(_project_root, "build", "license_private_key.pem")


def load_private_key():
    """从 PEM 文件加载 RSA 私钥"""
    if not os.path.exists(PRIVATE_KEY_PATH):
        print(f"[错误] 私钥文件不存在: {PRIVATE_KEY_PATH}")
        print("请先运行以下命令生成 RSA-2048 密钥对，并将私钥保存到该路径：")
        print("  python -c \"from cryptography.hazmat.primitives.asymmetric import rsa; "
              "from cryptography.hazmat.primitives import serialization; "
              "key=rsa.generate_private_key(public_exponent=65537,key_size=2048); "
              "open(r'" + PRIVATE_KEY_PATH + "','wb').write("
              "key.private_bytes(serialization.Encoding.PEM,"
              "serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))\"")
        sys.exit(1)
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def generate_license_key(machine_id: str, expiry: str, license_type: str = "pro") -> str:
    """生成 license key

    格式：base64url(json_payload) + "." + base64url(rsa_signature)
    签名算法：RSA-PSS + SHA256（与 core.license.verify_license 验签一致）
    """
    payload = {
        "machine_id": machine_id,
        "expiry": expiry,  # "permanent" 或 "YYYY-MM-DD"
        "type": license_type,
    }
    # Why: 签名输入必须是确定的字节串，验签时用同一份字节解码后比对
    payload_bytes = json.dumps(payload).encode("utf-8")

    private_key = load_private_key()
    signature = private_key.sign(
        payload_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )

    return _b64url_encode(payload_bytes) + "." + _b64url_encode(signature)


def _parse_expiry(input_str: str) -> str:
    """解析有效期输入，返回 "permanent" 或 "YYYY-MM-DD" 字符串"""
    s = input_str.strip().lower()
    if s in ("permanent", "perm", "forever", "永久", "0"):
        return "permanent"
    try:
        days = int(s)
        if days <= 0:
            return "permanent"
        exp_date = datetime.now() + timedelta(days=days)
        return exp_date.strftime("%Y-%m-%d")
    except ValueError:
        print(f"[错误] 无法解析有效期: {input_str}（请输入数字天数或 permanent）")
        sys.exit(1)


def main():
    print("=" * 60)
    print("  FaceswapApp License Key 生成工具（开发者专用）")
    print("=" * 60)
    print()

    machine_id = input("请输入用户机器码（FSA-XXXX-XXXX-XXXX-XXXX）: ").strip()
    if not machine_id or not machine_id.startswith("FSA-"):
        print("[错误] 机器码格式不正确，应以 FSA- 开头")
        sys.exit(1)

    expiry_input = input("请输入有效期（天数，如 365；或输入 permanent 永久）: ").strip()
    expiry = _parse_expiry(expiry_input)

    license_type = input("请输入授权类型（pro/enterprise，默认 pro）: ").strip()
    if not license_type:
        license_type = "pro"

    print()
    print("-" * 60)
    print(f"机器码: {machine_id}")
    print(f"有效期: {expiry}")
    print(f"授权类型: {license_type}")
    print("-" * 60)

    key = generate_license_key(machine_id, expiry, license_type)
    print()
    print("✅ License Key 生成成功（复制以下整行发给用户）：")
    print()
    print(key)
    print()
    print(f"Key 长度: {len(key)} 字符")

    # 自检：用公钥验证一次，确保 key 可被 verify_license 通过
    try:
        from core.license import verify_license
        ok, msg = verify_license(key, machine_id)
        if ok:
            print(f"✅ 自检通过：verify_license 返回 ({ok}, {msg})")
        else:
            print(f"⚠️ 自检失败：verify_license 返回 ({ok}, {msg})")
    except Exception as e:
        print(f"⚠️ 自检异常: {e}")


if __name__ == "__main__":
    main()
