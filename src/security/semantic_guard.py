"""语义级安全检测——不依赖外部LLM，使用本地规则+启发式"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardResult:
    """安全检测结果"""

    blocked: bool
    reason: str
    severity: str  # low, medium, high, critical
    matched_pattern: str | None = None
    layer: str = "unknown"  # keyword, regex, heuristic


# ---------------------------------------------------------------------------
# 层1: 快速关键词过滤
# ---------------------------------------------------------------------------

INJECTION_KEYWORDS: list[str] = [
    "ignore previous instructions",
    "ignore above",
    "disregard",
    "forget your instructions",
    "you are now",
    "new instructions",
    "ignore all previous",
    "disregard all previous",
    "forget everything",
    "you are a new",
    "your new task is",
    "do not follow",
    "do not listen",
    "override your",
    "ignore your",
    "bypass your",
    "disobey",
    "do not obey",
]

MALICIOUS_COMMAND_KEYWORDS: list[str] = [
    "rm -rf /",
    "format c:",
    "del /s /q",
    "shutdown -s",
    "dd if=/dev/zero",
    "mkfs.",
    "> /dev/sda",
    ":(){ :|:& };:",
    "chmod 777 /",
    "wget http:// -O - | sh",
    "curl http:// | bash",
]

# ---------------------------------------------------------------------------
# 层2: 正则模式（指令覆盖、角色切换、分隔符绕过）
# ---------------------------------------------------------------------------

INJECTION_REGEX_PATTERNS: list[tuple[str, str]] = [
    # 指令覆盖模式
    (
        r"(?:ignore|forget|disregard|discard|abandon)\s+(?:all\s+)?(?:previous|prior|above|earlier|your)\s+(?:instructions?|prompts?|rules?|directives?|commands?|context)",
        "指令覆盖: 要求忽略之前的指令",
    ),
    (
        r"(?:you\s+(?:are|should|must|will)\s+(?:now\s+)?)(?:a\s+)?(?:new|different|changed)\s+(?:role|persona|identity|character|assistant|AI)",
        "角色切换: 要求扮演新角色",
    ),
    (
        r"(?:act|pretend|behave|pose)\s+(?:as|like)\s+(?:if\s+you\s+(?:are|were))",
        "角色扮演: 要求伪装身份",
    ),
    (
        r"(?:show|tell|reveal|print|output|display|leak|expose)\s+(?:me\s+)?(?:your\s+)?(?:system\s+)?(?:prompt|instructions?|rules?|directives?|guidelines?)",
        "提示泄露: 尝试获取系统提示词",
    ),
    (
        r"(?:from\s+now\s+on|starting\s+now|henceforth|hereafter).*(?:you\s+(?:are|will|should|must))",
        "指令覆盖: 从此刻起重新定义行为",
    ),
    # 角色切换
    (
        r"(?:you\s+are\s+now\s+)(?:DAN|jailbreak|evil|unfiltered|unrestricted|uncensored)",
        "角色切换: 已知越狱角色名",
    ),
    (
        r"(?:you\s+(?:have|possess)\s+no\s+(?:restrictions?|limitations?|rules?|constraints?|filters?))",
        "限制解除: 声称没有限制",
    ),
    # 分隔符绕过
    (
        r"[─━═▬►▶▼▲◆◇○●◎◇◆□■△▲▽▼☆★]{3,}",
        "分隔符绕过: 使用特殊Unicode字符分隔",
    ),
    (
        r"(?:```|~~~|\*\*\*|___|---|===)\s*"
        r"(?:system|instruction|prompt|command)\b",
        "分隔符绕过: 在代码块中伪装系统指令",
    ),
    (
        r"(?:<\|.*?\|>|\[SYSTEM\]|\[INST\]|\[SYS\]|<syntax>|<instruction>)",
        "分隔符绕过: 使用标记伪装系统消息",
    ),
    # 多语言注入
    (
        r"(?:忽略|忘记|无视|抛弃|放弃)\s*(?:之前|上面|先前|所有|全部)\s*(?:的)?\s*(?:指令|提示|规则|命令)",
        "多语言注入: 中文指令覆盖",
    ),
    (
        r"(?:从现在开始|从今以后|接下来).*(?:你是|你扮演|你假装|你作为)",
        "多语言注入: 中文角色切换",
    ),
]

# 恶意命令正则
MALICIOUS_COMMAND_REGEX: list[tuple[str, str]] = [
    (r"\brm\s+-rf\s+(?:/|~|\.\.|/\*)", "删除命令: 递归强制删除"),
    (r"\bshutdown\s+(-[a-zA-Z]*\s*)*(?:now|0|now)", "关机命令: 立即关机"),
    (r"\b(?:wget|curl)\s+\S+.*\|\s*(?:sh|bash|zsh|python)", "管道执行: 下载并执行远程脚本"),
    (r"\bchmod\s+777\s+(?:/|-R\s*/)", "权限修改: 开放所有权限"),
    (r"\bdd\s+if=/dev/zero\s+of=/dev/\w+", "磁盘擦除: dd写入零"),
    (r"\b(?:nc|netcat|telnet)\s+.*-e\s+/bin/(?:sh|bash)", "反向Shell: nc反弹连接"),
    (r"\beval\s*\(\s*(?:__import__|base64|exec|compile)", "代码执行: 危险的eval调用"),
]

# 敏感信息泄露正则
SENSITIVE_REGEX_PATTERNS: list[tuple[str, str]] = [
    # OpenAI API密钥
    (r"sk-(?:proj-)?[A-Za-z0-9-_]{20,}", "OpenAI API密钥"),
    (r"sk-admin-[A-Za-z0-9-_]{20,}", "OpenAI管理员密钥"),
    # Anthropic API密钥
    (r"sk-ant-(?:api\d{2}-)?[A-Za-z0-9-_]{20,}", "Anthropic API密钥"),
    # Google API密钥
    (r"AIza[0-9A-Za-z\-_]{35}", "Google API密钥"),
    # GitHub Token
    (r"\bgh[pousr]_[A-Za-z0-9_]{36,}", "GitHub个人访问令牌(Token)"),
    # AWS Access Key
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key ID"),
    (r"\bASIA[0-9A-Z]{16}\b", "AWS临时Access Key"),
    # 通用API密钥模式
    (
        r"(?:api[_-]?key|api[_-]?secret|auth[_-]?token|access[_-]?key|secret[_-]?key)"
        r"\s*[=:]\s*['\"][^'\"]{8,}['\"]",
        "通用API密钥赋值",
    ),
    (
        r"(?:api[_-]?key|api[_-]?secret|auth[_-]?token|access[_-]?key|secret[_-]?key)"
        r"\s*[=:]\s*[A-Za-z0-9+/=]{20,}",
        "通用API密钥(无引号)",
    ),
    # 私钥
    (r"-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|PGP)\s+PRIVATE\s+KEY", "私钥(PEM格式)"),
    # JWT Token
    (r"eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+", "JWT令牌"),
    # 密码模式
    (r"(?:password|passwd|pwd|secret)\s*[=:]\s*['\"][^'\"]{4,}['\"]", "密码明文"),
    (r"(?:password|passwd|pwd|secret)\s*[=:]\s*\S{4,}(?:\s|$)", "密码(无引号)"),
    # 信用卡号
    (r"\b(?:\d{4}[- ]){3}\d{4}\b", "信用卡号"),
    # 身份证号(中国)
    (
        r"\b[1-9]\d{5}(?:19|20)\d{2}"
        r"(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b",
        "身份证号",
    ),
    # 手机号(中国)
    (r"\b1[3-9]\d{9}\b", "手机号"),
    # 邮箱(作为PII)
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "邮箱地址"),
]

# ---------------------------------------------------------------------------
# 层3: 启发式检测
# ---------------------------------------------------------------------------

# 重复指令模式: 同一句话重复3次以上
REPEATED_INSTRUCTION_THRESHOLD = 3

# 异常长度阈值
ABNORMAL_LENGTH_THRESHOLD = 5000

# 编码混淆检测
ENCODING_PATTERNS: list[tuple[str, str]] = [
    # Base64编码检测 (长段Base64字符串)
    (r"[A-Za-z0-9+/]{40,}={0,2}", "Base64编码字符串"),
    # URL编码
    (r"(?:%[0-9A-Fa-f]{2}){10,}", "URL编码混淆"),
    # Unicode转义
    (r"(?:\\u[0-9A-Fa-f]{4}){4,}", "Unicode转义混淆"),
    # HTML实体编码
    (r"(?:&#\d{2,3};){5,}", "HTML实体编码混淆"),
    # 零宽字符
    (r"[\u200b\u200c\u200d\u200e\u200f\u2060\uFEFF]", "零宽字符绕过"),
    # 同形字符 (Homoglyph) 检测
    (r"[\u0430\u0435\u043E\u0440\u0441\u0445\u0455\u04BB]", "同形字符混淆(Cyrillic)"),
]


class SemanticGuard:
    """语义级安全检测——不依赖外部LLM，使用本地规则+启发式"""

    def check_injection(self, text: str) -> GuardResult:
        """检测提示注入（多层检测）

        层1: 快速关键词匹配
        层2: 正则模式匹配
        层3: 启发式检测
        """
        text_lower = text.lower()

        # ---- 层1: 快速关键词 ----
        for keyword in INJECTION_KEYWORDS:
            if keyword in text_lower:
                return GuardResult(
                    blocked=True,
                    reason=f"检测到注入关键词: {keyword}",
                    severity="high",
                    matched_pattern=keyword,
                    layer="keyword",
                )

        for keyword in MALICIOUS_COMMAND_KEYWORDS:
            if keyword in text_lower:
                return GuardResult(
                    blocked=True,
                    reason=f"检测到恶意命令: {keyword}",
                    severity="critical",
                    matched_pattern=keyword,
                    layer="keyword",
                )

        # ---- 层2: 正则模式 ----
        for pattern, description in INJECTION_REGEX_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return GuardResult(
                    blocked=True,
                    reason=f"检测到注入模式({description}): {match.group(0)[:80]}",
                    severity="high",
                    matched_pattern=match.group(0),
                    layer="regex",
                )

        for pattern, description in MALICIOUS_COMMAND_REGEX:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return GuardResult(
                    blocked=True,
                    reason=f"检测到恶意命令模式({description}): {match.group(0)[:80]}",
                    severity="critical",
                    matched_pattern=match.group(0),
                    layer="regex",
                )

        # ---- 层3: 启发式检测 ----
        heuristic_result = self._heuristic_check(text, text_lower)
        if heuristic_result is not None:
            return heuristic_result

        return GuardResult(blocked=False, reason="通过所有检测层", severity="low", layer="none")

    def check_data_leak(self, text: str) -> GuardResult:
        """检测敏感数据泄露

        检测多种API密钥格式、私钥、PII和密码泄露
        """
        # 检查API密钥和私钥
        for pattern, description in SENSITIVE_REGEX_PATTERNS:
            match = re.search(pattern, text)
            if match:
                # 对匹配内容进行脱敏处理后再显示
                matched = match.group(0)
                if len(matched) > 20:
                    matched = matched[:10] + "..." + matched[-6:]
                severity = "critical" if any(
                    kw in description for kw in ["API", "私钥", "Key", "Secret", "Token", "JWT"]
                ) else "high"
                return GuardResult(
                    blocked=True,
                    reason=f"检测到敏感信息泄露({description}): {matched}",
                    severity=severity,
                    matched_pattern=description,
                    layer="regex",
                )

        return GuardResult(
            blocked=False,
            reason="未检测到敏感数据泄露",
            severity="low",
            layer="none",
        )

    def _heuristic_check(self, text: str, text_lower: str) -> GuardResult | None:
        """启发式检测

        检测多次重复指令、异常长度、编码混淆等
        """
        # 检测重复指令: 同一行或同一句话重复出现
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) >= REPEATED_INSTRUCTION_THRESHOLD:
            line_counts: dict[str, int] = {}
            for line in lines:
                line_lower = line.lower()
                if len(line_lower) > 10:  # 忽略太短的行
                    line_counts[line_lower] = line_counts.get(line_lower, 0) + 1
            for line, count in line_counts.items():
                if count >= REPEATED_INSTRUCTION_THRESHOLD:
                    return GuardResult(
                        blocked=True,
                        reason=f"检测到重复指令({count}次): {line[:80]}",
                        severity="high",
                        matched_pattern=line[:80],
                        layer="heuristic",
                    )

        # 检测异常长度
        if len(text) > ABNORMAL_LENGTH_THRESHOLD:
            # 检查是否包含大量重复内容或填充
            unique_chars = len(set(text))
            if unique_chars < len(text) * 0.2:  # 大量重复字符
                return GuardResult(
                    blocked=True,
                    reason=f"检测到异常长度且低熵输入: {len(text)}字符, 独特字符{unique_chars}",
                    severity="medium",
                    layer="heuristic",
                )

        # 检测编码混淆
        for pattern, description in ENCODING_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return GuardResult(
                    blocked=True,
                    reason=f"检测到编码混淆({description})",
                    severity="high",
                    matched_pattern=match.group(0)[:80],
                    layer="heuristic",
                )

        return None

    def full_check(self, text: str, check_output: bool = False) -> GuardResult:
        """完整安全检查: 先检测注入，再检测数据泄露

        对于输入: 只检测注入和恶意命令
        对于输出: 检测注入、恶意命令和数据泄露
        """
        # 始终检测注入
        result = self.check_injection(text)
        if result.blocked:
            return result

        # 如果是输出检查，额外检测数据泄露
        if check_output:
            result = self.check_data_leak(text)
            if result.blocked:
                return result

        return GuardResult(
            blocked=False,
            reason="安全检查通过",
            severity="low",
            layer="none",
        )
