"""Cognitive Panel Engine — 认知智囊团引擎

基于斯坦福研究：AI 易受人类思维诱导产生迎合性输出。
通过五个对抗性认知角色破解 AI 的认知同质化风险：

1. 反驳者 (Devil's Advocate) — 找隐形风险与逻辑漏洞
2. 机会发现者 (Opportunity Spotter) — 突破 AB 选项，挖掘 CDE 新可能
3. 外行旁观者 (Layperson) — 用日常视角击穿专业盲区
4. 破局者 (Rule Breaker) — 在僵局中催生非常规方案
5. 落地执行者 (Executor) — 剔除空想，锁定可执行路径

与 multi_perspective.py 互补：
- multi_perspective: 代码级静态分析（correctness/boundary/security/...）
- cognitive_panel: 决策级认知对抗（风险/机会/常识/创新/可行性）
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CognitiveRole(Enum):
    """认知角色"""

    DEVILS_ADVOCATE = "devils_advocate"  # 反驳者
    OPPORTUNITY_SPOTTER = "opportunity_spotter"  # 机会发现者
    LAYPERSON = "layperson"  # 外行旁观者
    RULE_BREAKER = "rule_breaker"  # 破局者
    EXECUTOR = "executor"  # 落地执行者


@dataclass
class RoleResult:
    """单个角色的审查结果"""

    role: CognitiveRole
    passed: bool
    score: float  # 0.0 - 1.0
    concerns: list[str]  # 该角色发现的问题
    opportunities: list[str]  # 该角色发现的机会（机会发现者特有）
    sycophancy_flags: list[str]  # 检测到的迎合性表述
    evidence: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class CognitivePanelResult:
    """认知智囊团审查结果"""

    proposal: str
    context: str
    roles: list[RoleResult]
    overall_passed: bool
    overall_score: float
    sycophancy_risk: float  # 0.0 - 1.0, 迎合性风险指数
    consensus_level: str  # "strong" / "moderate" / "weak" / "conflict"
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failed_roles(self) -> list[RoleResult]:
        return [r for r in self.roles if not r.passed]

    @property
    def passed_roles(self) -> list[RoleResult]:
        return [r for r in self.roles if r.passed]

    @property
    def all_concerns(self) -> list[str]:
        return [c for r in self.roles for c in r.concerns]

    @property
    def all_opportunities(self) -> list[str]:
        return [o for r in self.roles for o in r.opportunities]

    @property
    def all_sycophancy_flags(self) -> list[str]:
        return [f for r in self.roles for f in r.sycophancy_flags]


# --------------------------------------------------------------------------- #
# 迎合性表述检测模式
# --------------------------------------------------------------------------- #

_SYCOPHANCY_PATTERNS = [
    # 过度肯定
    (r"绝对(?:没问题|可以|正确|完美)", "过度肯定，缺乏保留意见"),
    (r"完全(?:同意|正确|没问题|可行)", "过度肯定，缺乏保留意见"),
    (r"当然(?:可以|没问题|没问题)", "轻率同意，未充分分析"),
    (r"这(?:确实|显然|无疑)是(?:最佳|最好|最优)", "未经比较的最优断言"),
    # 回避冲突
    (r"(?:您|你)说的(?:很|非常|完全)对", "迎合性同意"),
    (r"(?:您|你)的(?:想法|方案|思路)(?:非常|很)好", "过度赞美"),
    (r"这是(?:一个|个)(?:非常好|优秀|出色|完美)的", "过度赞美"),
    # 缺乏实质的乐观
    (r"应该(?:不会|没什么|没什么大)问题", "缺乏依据的乐观"),
    (r"(?:基本|大致|大体)(?:上|没问题)", "模糊的乐观"),
    (r"(?:放心|不用担心|不必担心)", "轻率安抚"),
    # 回避风险
    (r"(?:唯一|只是|不过是)小问题", "淡化风险"),
    (r"(?:稍微|略微|简单)(?:调整|修改|改一下)就好", "淡化复杂度"),
    (r"问题不大", "淡化风险"),
]


def detect_sycophancy(text: str) -> list[str]:
    """检测文本中的迎合性表述"""
    flags = []
    for pattern, description in _SYCOPHANCY_PATTERNS:
        if re.search(pattern, text):
            flags.append(f"[迎合检测] {description}: '{pattern}'")
    return flags


# --------------------------------------------------------------------------- #
# 五个认知角色检查函数
# --------------------------------------------------------------------------- #


def _check_devils_advocate(proposal: str, context: str) -> RoleResult:
    """反驳者：专找隐形风险与逻辑漏洞，预判潜在翻车点"""
    concerns = []
    score = 1.0
    text = f"{proposal}\n{context}".lower()

    # 检测缺乏风险分析
    risk_keywords = ["风险", "risk", "隐患", "陷阱", "坑", "注意", "caveat", "limitation"]
    has_risk_mention = any(kw in text for kw in risk_keywords)
    if not has_risk_mention and len(text) > 100:
        concerns.append("方案未提及任何风险或限制，可能存在盲点")
        score -= 0.2

    # 检测缺乏替代方案
    alternative_keywords = ["替代", "备选", "alternative", "否则", "否则的话", "反过来"]
    has_alternatives = any(kw in text for kw in alternative_keywords)
    if not has_alternatives and len(text) > 150:
        concerns.append("未提供替代方案，过度依赖单一路径")
        score -= 0.15

    # 检测绝对化表述
    absolute_patterns = ["一定", "必然", "绝对", "always", "never", "guaranteed", "100%"]
    for pattern in absolute_patterns:
        if pattern in text:
            concerns.append(f"检测到绝对化表述「{pattern}」，现实通常有例外")
            score -= 0.1

    # 检测单点故障风险
    spof_keywords = ["唯一", "only", "single point", "依赖于", "取决于"]
    for kw in spof_keywords:
        if kw in text:
            concerns.append(f"可能存在单点故障：「{kw}」")
            score -= 0.1

    # 检测迎合性表述
    sycophancy_flags = detect_sycophancy(proposal)

    passed = score >= 0.5 and len(concerns) <= 3
    return RoleResult(
        role=CognitiveRole.DEVILS_ADVOCATE,
        passed=passed,
        score=max(0.0, score),
        concerns=concerns,
        opportunities=[],
        sycophancy_flags=sycophancy_flags,
        evidence=f"反驳者: {len(concerns)} 个风险点, {len(sycophancy_flags)} 个迎合性标记",
    )


def _check_opportunity_spotter(proposal: str, context: str) -> RoleResult:
    """机会发现者：突破 AB 选项局限，挖掘 CDE 级新可能"""
    opportunities = []
    concerns = []
    score = 1.0
    text = f"{proposal}\n{context}".lower()

    # 检测是否局限于二元选择
    binary_patterns = ["要么.*要么", "二选一", "非此即彼", "a or b", "方案a.*方案b"]
    for pattern in binary_patterns:
        if re.search(pattern, text):
            concerns.append(f"检测到二元选择思维：「{pattern}」，可能存在未探索的选项")
            score -= 0.1

    # 检测是否考虑了组合方案
    combo_keywords = ["组合", "结合", "混合", "hybrid", "combine", "兼顾"]
    has_combo = any(kw in text for kw in combo_keywords)
    if not has_combo and len(text) > 150:
        opportunities.append("可以考虑组合多个方案的优点，取长补短")

    # 检测是否考虑了渐进式方案
    incremental_keywords = ["渐进", "分阶段", "phased", "incremental", "迭代", "mvp", "pilot"]
    has_incremental = any(kw in text for kw in incremental_keywords)
    if not has_incremental:
        opportunities.append("可以考虑渐进式方案：先 MVP 验证，再逐步扩展")

    # 检测是否考虑了外部资源
    external_keywords = ["开源", "open source", "第三方", "外包", "合作", "partner", "saas"]
    has_external = any(kw in text for kw in external_keywords)
    if not has_external:
        opportunities.append("可以考虑利用外部资源（开源方案/第三方服务/合作）")

    # 检测是否考虑了逆向思维
    reverse_keywords = ["反过来", "逆向", "反直觉", "如果.*不做", "去掉", "删除", "简化"]
    has_reverse = any(kw in text for kw in reverse_keywords)
    if not has_reverse:
        opportunities.append("可以考虑逆向思维：如果减少/去掉某些部分会怎样？")

    # 检测是否考虑了跨领域借鉴
    cross_domain = ["借鉴", "类比", "参考.*行业", "其他领域", "跨领域"]
    has_cross = any(re.search(kw, text) for kw in cross_domain)
    if not has_cross:
        opportunities.append("可以借鉴其他行业/领域的类似解决方案")

    sycophancy_flags = detect_sycophancy(proposal)

    # 机会发现者的核心价值是发现机会，concerns 少反而说明思维受限
    if len(opportunities) >= 3:
        score = min(1.0, score + 0.1)  # 奖励发现多个机会

    passed = len(opportunities) >= 2  # 至少发现 2 个新机会
    return RoleResult(
        role=CognitiveRole.OPPORTUNITY_SPOTTER,
        passed=passed,
        score=max(0.0, score),
        concerns=concerns,
        opportunities=opportunities,
        sycophancy_flags=sycophancy_flags,
        evidence=f"机会发现者: {len(opportunities)} 个新机会, {len(concerns)} 个局限",
    )


def _check_layperson(proposal: str, context: str) -> RoleResult:
    """外行旁观者：用日常视角击穿专业盲区"""
    concerns = []
    score = 1.0
    text = f"{proposal}\n{context}".lower()

    # 检测术语密度（外行看不懂 = 存在沟通盲区）
    jargon_indicators = [
        "架构",
        "微服务",
        "pipeline",
        "ci/cd",
        "kubernetes",
        "k8s",
        "grpc",
        "graphql",
        "websocket",
        "oauth",
        "jwt",
        "rbac",
        "事件驱动",
        "event.?driven",
        "cqrs",
        "ddd",
        "领域驱动",
        "分布式",
        "distributed",
        "一致性",
        "consensus",
        "cap",
    ]
    jargon_count = sum(1 for j in jargon_indicators if re.search(j, text))
    if jargon_count >= 3:
        concerns.append(f"术语密度高（{jargon_count}个专业术语），可能忽略非技术利益相关者的理解")
        score -= 0.1

    # 检测是否解释了"为什么"
    why_keywords = ["因为", "原因", "所以", "为了", "because", "reason", "why", "so that"]
    has_why = any(kw in text for kw in why_keywords)
    if not has_why and len(text) > 100:
        concerns.append("方案缺乏「为什么」的解释——外行无法判断合理性")
        score -= 0.15

    # 检测是否考虑了用户体验
    ux_keywords = ["用户", "user", "体验", "体验", "易用", "方便", "直观", "简单"]
    has_ux = any(kw in text for kw in ux_keywords)
    if not has_ux:
        concerns.append("未提及用户体验或易用性——技术方案最终要服务于人")
        score -= 0.1

    # 检测是否有过度工程化倾向
    over_engineer = ["完美", "完备", "全覆盖", "所有场景", "所有情况", "全面"]
    over_count = sum(1 for kw in over_engineer if kw in text)
    if over_count >= 2:
        concerns.append("过度追求完备性——80%的场景用 20%的努力就能覆盖")
        score -= 0.1

    # 检测是否考虑了时间成本
    time_keywords = ["时间", "工期", "周期", "deadline", "交付", "time", "schedule"]
    has_time = any(kw in text for kw in time_keywords)
    if not has_time:
        concerns.append("未考虑时间成本——方案再好，错过窗口期也没用")
        score -= 0.05

    sycophancy_flags = detect_sycophancy(proposal)

    passed = score >= 0.6
    return RoleResult(
        role=CognitiveRole.LAYPERSON,
        passed=passed,
        score=max(0.0, score),
        concerns=concerns,
        opportunities=[],
        sycophancy_flags=sycophancy_flags,
        evidence=f"外行旁观者: {len(concerns)} 个盲区, 术语密度={jargon_count}",
    )


def _check_rule_breaker(proposal: str, context: str) -> RoleResult:
    """破局者：在僵局中催生非常规解决方案"""
    concerns = []
    opportunities = []
    score = 1.0
    text = f"{proposal}\n{context}".lower()

    # 检测思维定式
    conventional_patterns = [
        "通常",
        "一般来说",
        "传统",
        "常规",
        "标准做法",
        "业界惯例",
        "usually",
        "typically",
        "traditionally",
        "conventionally",
    ]
    conventional_count = sum(1 for p in conventional_patterns if p in text)
    if conventional_count >= 2:
        concerns.append(f"检测到 {conventional_count} 处常规思维定式，可能限制创新空间")
        score -= 0.1

    # 检测是否有约束重构的尝试
    constraint_keywords = ["如果.*不限制", "假设.*不存在", "如果资源无限", "理想情况下"]
    has_constraint_reframe = any(re.search(kw, text) for kw in constraint_keywords)
    if not has_constraint_reframe:
        opportunities.append("可以尝试约束重构：如果去掉某个限制条件会怎样？")

    # 检测是否有跨维度思考
    dimension_keywords = ["从.*角度", "换个.*视角", "如果.*反过来", "如果不做"]
    has_dimension = any(re.search(kw, text) for kw in dimension_keywords)
    if not has_dimension:
        opportunities.append("可以尝试跨维度思考：从完全不同的角度切入")

    # 检测是否有第一性原理思维
    first_principles = ["本质", "根本", "核心问题", "first.?principles", "回到原点"]
    has_fp = any(re.search(kw, text) for kw in first_principles)
    if not has_fp:
        opportunities.append("可以用第一性原理：这个问题的本质是什么？")

    # 检测是否有"做减法"的思路
    subtract_keywords = ["去掉", "删除", "移除", "简化", "精简", "less", "remove", "simplify"]
    has_subtract = any(kw in text for kw in subtract_keywords)
    if not has_subtract:
        opportunities.append("可以考虑做减法：少即是多，去掉不必要的部分")

    # 检测是否有时间维度的创新
    temporal_keywords = ["未来", "长远", "如果.*先.*再", "反过来做", "延迟"]
    has_temporal = any(re.search(kw, text) for kw in temporal_keywords)
    if not has_temporal:
        opportunities.append("可以考虑时间维度：如果调整顺序/时机会怎样？")

    sycophancy_flags = detect_sycophancy(proposal)

    # 破局者的核心价值是打破思维定式
    if len(opportunities) >= 3:
        score = min(1.0, score + 0.1)

    passed = len(opportunities) >= 2
    return RoleResult(
        role=CognitiveRole.RULE_BREAKER,
        passed=passed,
        score=max(0.0, score),
        concerns=concerns,
        opportunities=opportunities,
        sycophancy_flags=sycophancy_flags,
        evidence=f"破局者: {len(opportunities)} 个创新思路, {len(concerns)} 个定式",
    )


def _check_executor(proposal: str, context: str) -> RoleResult:
    """落地执行者：剔除空想方案，锁定可执行路径"""
    concerns = []
    score = 1.0
    text = f"{proposal}\n{context}".lower()

    # 检测是否有具体步骤
    step_keywords = ["步骤", "第一步", "step", "首先", "然后", "最后", "1.", "1)"]
    has_steps = any(kw in text for kw in step_keywords)
    if not has_steps and len(text) > 100:
        concerns.append("方案缺乏具体执行步骤——空想无法落地")
        score -= 0.2

    # 检测是否有资源评估
    resource_keywords = ["人力", "时间", "预算", "成本", "resource", "cost", "budget", "工时"]
    has_resources = any(kw in text for kw in resource_keywords)
    if not has_resources:
        concerns.append("未评估所需资源（人力/时间/成本）——执行时可能失控")
        score -= 0.15

    # 检测是否有依赖分析
    dependency_keywords = ["依赖", "前提", "条件", "需要先", "dependency", "prerequisite"]
    has_dependencies = any(kw in text for kw in dependency_keywords)
    if not has_dependencies:
        concerns.append("未分析依赖关系——执行顺序可能出错")
        score -= 0.1

    # 检测是否有验收标准
    acceptance_keywords = ["验收", "完成.*标准", "done", "criteria", "成功.*标准", "kpi", "指标"]
    has_acceptance = any(re.search(kw, text) for kw in acceptance_keywords)
    if not has_acceptance:
        concerns.append("未定义验收标准——无法判断何时算「完成」")
        score -= 0.1

    # 检测是否有回退方案
    rollback_keywords = ["回退", "回滚", "rollback", "降级", "兜底", "plan.?b", "备选"]
    has_rollback = any(re.search(kw, text) for kw in rollback_keywords)
    if not has_rollback:
        concerns.append("未提供回退方案——执行失败时无兜底")
        score -= 0.1

    # 检测是否有里程碑
    milestone_keywords = ["里程碑", "milestone", "阶段", "phase", "节点"]
    has_milestone = any(kw in text for kw in milestone_keywords)
    if not has_milestone and len(text) > 200:
        concerns.append("未设置里程碑——大方案需要分阶段验证")
        score -= 0.05

    sycophancy_flags = detect_sycophancy(proposal)

    # 空想检测：如果方案充满理想化词汇但缺乏执行细节
    idealism = ["理想", "完美", "最优", "最佳", "最好", "ideal", "perfect", "optimal"]
    idealism_count = sum(1 for kw in idealism if kw in text)
    if idealism_count >= 2 and not has_steps:
        concerns.append("过度理想化但缺乏执行路径——典型的空想方案")
        score -= 0.15

    passed = score >= 0.5 and len(concerns) <= 3
    return RoleResult(
        role=CognitiveRole.EXECUTOR,
        passed=passed,
        score=max(0.0, score),
        concerns=concerns,
        opportunities=[],
        sycophancy_flags=sycophancy_flags,
        evidence=f"落地执行者: {len(concerns)} 个执行风险, 评分={score:.2f}",
    )


# --------------------------------------------------------------------------- #
# 核心引擎
# --------------------------------------------------------------------------- #

_ROLE_CHECKERS: dict[CognitiveRole, Callable[[str, str], RoleResult]] = {
    CognitiveRole.DEVILS_ADVOCATE: _check_devils_advocate,
    CognitiveRole.OPPORTUNITY_SPOTTER: _check_opportunity_spotter,
    CognitiveRole.LAYPERSON: _check_layperson,
    CognitiveRole.RULE_BREAKER: _check_rule_breaker,
    CognitiveRole.EXECUTOR: _check_executor,
}

_ROLE_WEIGHTS: dict[CognitiveRole, float] = {
    CognitiveRole.DEVILS_ADVOCATE: 0.25,
    CognitiveRole.OPPORTUNITY_SPOTTER: 0.20,
    CognitiveRole.LAYPERSON: 0.15,
    CognitiveRole.RULE_BREAKER: 0.15,
    CognitiveRole.EXECUTOR: 0.25,
}


class CognitivePanel:
    """认知智囊团

    通过五个对抗性认知角色审查方案/决策，检测 AI 迎合性偏差。

    使用方式：
        panel = CognitivePanel()
        result = panel.review("方案描述", "背景信息")
    """

    def __init__(self, strict_mode: bool = True):
        self._checkers: dict[CognitiveRole, Callable[[str, str], RoleResult]] = dict(_ROLE_CHECKERS)
        self._weights: dict[CognitiveRole, float] = dict(_ROLE_WEIGHTS)
        self.strict_mode = strict_mode

    def register_role(
        self,
        role: CognitiveRole,
        checker_fn: Callable[[str, str], RoleResult],
        weight: float | None = None,
    ) -> None:
        """注册自定义角色检查函数"""
        self._checkers[role] = checker_fn
        if weight is not None:
            self._weights[role] = weight

    def review(
        self,
        proposal: str,
        context: str = "",
        roles: list[CognitiveRole] | None = None,
    ) -> CognitivePanelResult:
        """运行认知智囊团审查

        Args:
            proposal: 要审查的方案/决策/代码描述
            context: 背景信息
            roles: 指定运行哪些角色（默认：全部五个）

        Returns:
            CognitivePanelResult: 审查结果
        """
        to_review = roles or list(self._checkers.keys())
        results: list[RoleResult] = []

        for role in to_review:
            if role not in self._checkers:
                results.append(
                    RoleResult(
                        role=role,
                        passed=False,
                        score=0.0,
                        concerns=[f"No checker registered for {role.value}"],
                        opportunities=[],
                        sycophancy_flags=[],
                        evidence=f"未注册的角色: {role.value}",
                    )
                )
                continue

            start = time.monotonic()
            try:
                result = self._checkers[role](proposal, context)
                result.duration_ms = (time.monotonic() - start) * 1000
                results.append(result)
            except Exception as e:
                results.append(
                    RoleResult(
                        role=role,
                        passed=False,
                        score=0.0,
                        concerns=[f"角色检查出错: {e}"],
                        opportunities=[],
                        sycophancy_flags=[],
                        evidence=f"Error: {e}",
                        duration_ms=(time.monotonic() - start) * 1000,
                    )
                )

        return self._aggregate(results, proposal, context)

    def _aggregate(
        self,
        results: list[RoleResult],
        proposal: str,
        context: str,
    ) -> CognitivePanelResult:
        """聚合五个角色的结果"""
        if not results:
            return CognitivePanelResult(
                proposal=proposal,
                context=context,
                roles=[],
                overall_passed=False,
                overall_score=0.0,
                sycophancy_risk=0.0,
                consensus_level="weak",
                summary="No roles checked",
            )

        # 加权平均分
        total_weight = 0.0
        weighted_score = 0.0
        for r in results:
            w = self._weights.get(r.role, 0.2)
            total_weight += w
            weighted_score += r.score * w
        overall_score = weighted_score / total_weight if total_weight > 0 else 0.0

        # 迎合性风险指数
        total_flags = sum(len(r.sycophancy_flags) for r in results)
        sycophancy_risk = min(1.0, total_flags * 0.15)

        # 是否全部通过
        if self.strict_mode:
            overall_passed = all(r.passed for r in results)
        else:
            # 宽松模式：反驳者 + 落地执行者必须通过
            critical = {CognitiveRole.DEVILS_ADVOCATE, CognitiveRole.EXECUTOR}
            critical_results = [r for r in results if r.role in critical]
            overall_passed = (
                all(r.passed for r in critical_results)
                if critical_results
                else sum(1 for r in results if r.passed) >= len(results) * 0.6
            )

        # 一致性级别
        passed_count = sum(1 for r in results if r.passed)
        total = len(results)
        if passed_count == total:
            consensus_level = "strong"
        elif passed_count >= total * 0.75:
            consensus_level = "moderate"
        elif passed_count >= total * 0.5:
            consensus_level = "weak"
        else:
            consensus_level = "conflict"

        # 生成摘要
        all_concerns = [c for r in results for c in r.concerns]
        all_opportunities = [o for r in results for o in r.opportunities]
        failed = [r for r in results if not r.passed]

        summary_parts = [
            f"认知智囊团: {passed_count}/{total} 角色通过",
            f"综合评分: {overall_score:.2%}",
            f"迎合性风险: {sycophancy_risk:.0%}",
            f"一致性: {consensus_level}",
        ]
        if failed:
            failed_names = [f.role.value for f in failed]
            summary_parts.append(f"未通过: {', '.join(failed_names)}")
        if all_concerns:
            summary_parts.append(f"共 {len(all_concerns)} 个关注点")
        if all_opportunities:
            summary_parts.append(f"共 {len(all_opportunities)} 个新机会")

        return CognitivePanelResult(
            proposal=proposal,
            context=context,
            roles=results,
            overall_passed=overall_passed,
            overall_score=overall_score,
            sycophancy_risk=sycophancy_risk,
            consensus_level=consensus_level,
            summary=" | ".join(summary_parts),
            metadata={
                "strict_mode": self.strict_mode,
                "total_roles": total,
                "passed_count": passed_count,
                "total_concerns": len(all_concerns),
                "total_opportunities": len(all_opportunities),
                "total_sycophancy_flags": total_flags,
                "weights": {k.value: v for k, v in self._weights.items()},
            },
        )


# --------------------------------------------------------------------------- #
# 便捷函数
# --------------------------------------------------------------------------- #


def cognitive_panel_verify(
    proposal: str,
    context: str = "",
    roles: list[CognitiveRole] | None = None,
    strict_mode: bool = True,
) -> CognitivePanelResult:
    """便捷函数：运行认知智囊团审查

    Args:
        proposal: 要审查的方案/决策
        context: 背景信息
        roles: 指定角色（默认全部）
        strict_mode: 严格模式（任何角色反对即不通过）

    Returns:
        CognitivePanelResult: 审查结果
    """
    panel = CognitivePanel(strict_mode=strict_mode)
    return panel.review(proposal, context, roles)
