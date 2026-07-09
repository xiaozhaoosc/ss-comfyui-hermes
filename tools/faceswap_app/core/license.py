"""License 管理：机器码绑定 + RSA-2048 签名 + 多位置冗余计数器

设计要点：
- 体验版限制 3 次换脸任务，计数器加密后冗余写入 3 处（APPDATA/LOCALAPPDATA/注册表）
- 篡改检测：2/3 一致则修复不一致项，3 个都不一致则锁定（count=999）
- 激活：离线 license key（RSA-2048 签名的 JSON payload），绑定机器码

私钥保存路径（仅开发者持有，绝不打包进 exe）：
    d:\\ai_projects\\ComfyUI\\tools\\faceswap_app\\build\\license_private_key.pem
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidSignature

# 硬编码 RSA-2048 公钥（私钥由开发者单独保存，不在代码中）
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA52gDyOUxzF+gkm+Qs1c9
QeaVbLW/fvZ57890uHm57Oms8PdJdpngp2dSwonjWU/Qp2rureuL3yxgCGdEFabn
b5WEg3FmtzPNxG0qjzEndDsiuFJCHtOLdXYOROSuSDAVhowIRu2wYPXRHN/CTn1E
Ce5OpKaZ9xiJUdC0RD13qliIBFo1vEJFFk97izs0IuPtHYTZwpk7dIhYGpqJZBgV
A+BF2C2FJJu7p7Fprb+yC5DhRoyZc7Fwg+t+1zCJ6uIPSiq3vlVlQ0xT/PvVc1R8
rX82+0DPzlM7F1axliPR7rMmcm2QW10LASZwf2bz8z8ZQzzigdj+nUuDM299oeKf
jwIDAQAB
-----END PUBLIC KEY-----
"""

# PBKDF2 派生 Fernet 密钥用的固定 salt
# Why: salt 固定虽不安全，但机器码本身已绑定硬件，攻击者拿到 salt 也无法跨机器伪造
_PBKDF2_SALT = b"FaceswapApp::License::v1::FixedSalt"
_PBKDF2_ITERATIONS = 100_000

_TRIAL_LIMIT = 3


# =====================================================================
# 机器码生成
# =====================================================================

def _psql(query: str) -> str:
    """执行 PowerShell 命令获取 WMI 信息，失败返回空字符串"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", query],
            capture_output=True, text=True, timeout=10,
        )
        # stderr 丢弃，只关心 stdout
        return proc.stdout.strip()
    except Exception:
        return ""


def _is_virtual_machine() -> bool:
    """检测是否在虚拟机中运行（用于警告，不阻止运行）"""
    model = _psql("(Get-CimInstance Win32_ComputerSystem).Model")
    if not model:
        return False
    keywords = ("Virtual", "VMware", "VirtualBox", "Xen", "KVM", "QEMU", "Hyper-V")
    low = model.lower()
    return any(k.lower() in low for k in keywords)


def get_machine_id() -> str:
    """生成机器唯一 ID（Windows）

    拼接 CPU ProcessorId + 主板 SerialNumber + 系统盘 SerialNumber，
    SHA256 后取前 16 位，格式化为 FSA-XXXX-XXXX-XXXX-XXXX。
    某项硬件信息获取失败用空字符串代替（不报错）。
    """
    cpu = _psql("(Get-CimInstance Win32_Processor).ProcessorId")
    board = _psql("(Get-CimInstance Win32_BaseBoard).SerialNumber")
    disk = _psql("(Get-CimInstance Win32_DiskDrive).SerialNumber")

    raw = f"{cpu}|{board}|{disk}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()
    # 每 4 位一段，便于用户复制和口头传达
    parts = [digest[i:i + 4] for i in range(0, 16, 4)]
    return "FSA-" + "-".join(parts)


# =====================================================================
# License key 验证
# =====================================================================

def _load_public_key():
    """从 PEM 字符串加载公钥（带缓存）"""
    return serialization.load_pem_public_key(PUBLIC_KEY_PEM)


def _b64url_encode(data: bytes) -> str:
    """URL-safe base64 编码并去掉 padding（缩短 key 长度）"""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """URL-safe base64 解码（自动补齐 padding）"""
    pad = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + ("=" * pad))


def verify_license(key: str, machine_id: str) -> tuple[bool, str]:
    """验证 license key

    返回 (is_valid, message)。
    检查：格式 → RSA 验签 → machine_id 匹配 → 是否过期。
    """
    if not key or "." not in key:
        return False, "license key 格式错误：缺少分隔符"

    parts = key.split(".")
    if len(parts) != 2:
        return False, "license key 格式错误：应为 payload.signature"

    payload_b64, sig_b64 = parts
    try:
        payload_bytes = _b64url_decode(payload_b64)
        sig = _b64url_decode(sig_b64)
    except Exception:
        return False, "license key 解码失败"

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return False, "license key payload 解析失败"

    # 验签：用 payload 原始字节（必须与签发时一致的 UTF-8 字节）
    pub = _load_public_key()
    try:
        pub.verify(
            sig,
            payload_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
    except InvalidSignature:
        return False, "license key 签名无效（可能被篡改）"
    except Exception as e:
        return False, f"签名验证异常: {e}"

    # machine_id 匹配
    if payload.get("machine_id", "") != machine_id:
        return False, "license key 与本机机器码不匹配"

    # 过期检查（expiry 为 "permanent" 或日期字符串 YYYY-MM-DD）
    expiry = payload.get("expiry", "")
    if expiry and expiry != "permanent":
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d")
            if datetime.now() > exp_date:
                return False, f"license 已过期（到期日 {expiry}）"
        except ValueError:
            return False, f"license 过期日期格式异常: {expiry}"

    return True, "license 验证通过"


# =====================================================================
# License 管理器
# =====================================================================

class LicenseManager:
    """License 管理器：计数、激活、验证

    计数器加密后冗余写入 3 处（APPDATA/LOCALAPPDATA/注册表），
    读取时多数一致修复，全部不一致则判定篡改并锁定。
    """

    TRIAL_LIMIT = _TRIAL_LIMIT

    def __init__(self):
        # 所有 license 操作都包 try-except，异常时退化为"无限试用"而非崩溃
        # Why: 宁可少拦截也不能让用户无法运行
        try:
            self.machine_id = get_machine_id()
        except Exception:
            self.machine_id = "FSA-UNKNOWN-0000-0000"

        try:
            self._store = self._load_store()
        except Exception:
            # 最差情况退化为未激活、count=0，避免无法运行
            self._store = {"count": 0, "activated": False, "tampered": False}

    # ---------- Fernet 密钥派生 ----------

    def _fernet_key(self) -> bytes:
        """从机器码派生 Fernet 对称密钥（PBKDF2-HMAC-SHA256）"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_PBKDF2_SALT,
            iterations=_PBKDF2_ITERATIONS,
        )
        raw = kdf.derive(self.machine_id.encode("utf-8"))
        return base64.urlsafe_b64encode(raw)

    # ---------- 存储位置 ----------

    def _store_paths(self) -> list[tuple[str, str | None]]:
        """返回 3 个存储位置

        每项为 (kind, location)：
        - ("file", path)：文件路径
        - ("registry", None)：注册表固定位置
        """
        appdata = os.path.expandvars(r"%APPDATA%\FaceswapApp")
        localappdata = os.path.expandvars(r"%LOCALAPPDATA%\FaceswapApp")
        return [
            ("file", os.path.join(appdata, "license.dat")),
            ("file", os.path.join(localappdata, "license.dat")),
            ("registry", None),
        ]

    def _reg_subkey(self):
        """注册表子键路径（HKCU 下）"""
        return r"Software\FaceswapApp"

    # ---------- 单位置读写 ----------

    def _read_location(self, kind: str, location) -> dict | None:
        """从单个位置读取并解密 store，失败返回 None（忽略该位置）"""
        fernet = Fernet(self._fernet_key())
        if kind == "file":
            if not location or not os.path.exists(location):
                return None
            with open(location, "rb") as f:
                blob = f.read()
            if not blob:
                return None
            try:
                plain = fernet.decrypt(blob)
                return json.loads(plain.decode("utf-8"))
            except (InvalidToken, json.JSONDecodeError, Exception):
                return None
        elif kind == "registry":
            if sys.platform != "win32":
                return None
            import winreg
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, self._reg_subkey(), 0, winreg.KEY_READ
                ) as key:
                    blob = winreg.QueryValueEx(key, "license")[0]
                    if isinstance(blob, str):
                        blob = blob.encode("utf-8")
                    plain = fernet.decrypt(blob)
                    return json.loads(plain.decode("utf-8"))
            except (FileNotFoundError, OSError, InvalidToken, json.JSONDecodeError, Exception):
                return None
        return None

    def _write_location(self, kind: str, location, data: dict):
        """向单个位置加密写入 store"""
        fernet = Fernet(self._fernet_key())
        blob = fernet.encrypt(json.dumps(data).encode("utf-8"))
        if kind == "file":
            os.makedirs(os.path.dirname(location), exist_ok=True)
            with open(location, "wb") as f:
                f.write(blob)
        elif kind == "registry":
            if sys.platform != "win32":
                return
            import winreg
            try:
                with winreg.CreateKey(
                    winreg.HKEY_CURRENT_USER, self._reg_subkey()
                ) as key:
                    winreg.SetValueEx(key, "license", 0, winreg.REG_BINARY, blob)
            except OSError:
                # 注册表无权限时忽略，其余 2 个文件位置已写入
                pass

    # ---------- 多位置一致性 ----------

    def _load_store(self) -> dict:
        """从 3 个位置加载，多数一致修复，全不一致判定篡改"""
        locations = self._store_paths()
        values = []
        for kind, loc in locations:
            values.append(self._read_location(kind, loc))

        # 过滤 None（读取失败/不存在）
        valid = [(i, v) for i, v in enumerate(values) if v is not None]

        if not valid:
            # 首次运行：全部不存在
            now = datetime.now().isoformat(timespec="seconds")
            return {
                "count": 0,
                "activated": False,
                "license_key": "",
                "machine_id": self.machine_id,
                "first_run": now,
                "last_run": now,
                "tampered": False,
            }

        # 统计每种值的出现次数（用 JSON 字符串做 key 以便比较）
        from collections import Counter
        counter = Counter()
        index_by_json = {}
        for i, v in valid:
            key_str = json.dumps(v, sort_keys=True)
            counter[key_str] += 1
            index_by_json[key_str] = i

        most_common_str, most_count = counter.most_common(1)[0]

        if most_count >= 2:
            # 2/3 或 3/3 一致：采用该值，并修复不一致的位置
            chosen = valid[index_by_json[most_common_str]][1]
            # 修复读取失败/不一致的位置
            for i, (kind, loc) in enumerate(locations):
                if values[i] is None or json.dumps(values[i], sort_keys=True) != most_common_str:
                    try:
                        self._write_location(kind, loc, chosen)
                    except Exception:
                        pass
            chosen.setdefault("tampered", False)
            return chosen
        else:
            # 3 个都不一致 → 判定篡改，锁定
            # Why: count=999 让试用直接耗尽，迫使用户激活或联系开发者
            locked = {
                "count": 999,
                "activated": False,
                "license_key": "",
                "machine_id": self.machine_id,
                "first_run": "",
                "last_run": datetime.now().isoformat(timespec="seconds"),
                "tampered": True,
            }
            # 锁定值写回 3 处，防止反复篡改重置
            for kind, loc in locations:
                try:
                    self._write_location(kind, loc, locked)
                except Exception:
                    pass
            return locked

    def _save_store(self, data: dict):
        """同时写入 3 个位置（Fernet 加密后写入）"""
        # 更新 last_run
        data["last_run"] = datetime.now().isoformat(timespec="seconds")
        for kind, loc in self._store_paths():
            try:
                self._write_location(kind, loc, data)
            except Exception:
                pass
        self._store = data

    # ---------- 公共 API ----------

    def get_remaining_trials(self) -> int:
        """返回剩余试用次数（已激活返回 -1 表示无限）"""
        if self._store.get("activated"):
            return -1
        count = int(self._store.get("count", 0))
        return max(0, self.TRIAL_LIMIT - count)

    def increment_usage(self):
        """完成 1 次换脸任务后调用，count += 1"""
        if self._store.get("activated"):
            return  # 已激活不计数
        self._store["count"] = int(self._store.get("count", 0)) + 1
        self._save_store(self._store)

    def is_activated(self) -> bool:
        """是否已激活"""
        return bool(self._store.get("activated", False))

    def is_tampered(self) -> bool:
        """是否被篡改锁定"""
        return bool(self._store.get("tampered", False))

    def activate(self, license_key: str) -> tuple[bool, str]:
        """激活：验证 key，通过则保存"""
        license_key = (license_key or "").strip()
        ok, msg = verify_license(license_key, self.machine_id)
        if not ok:
            return False, msg

        self._store["activated"] = True
        self._store["license_key"] = license_key
        self._store["tampered"] = False
        self._save_store(self._store)
        return True, "激活成功，感谢购买正版授权！"
