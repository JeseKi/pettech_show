# -*- coding: utf-8 -*-
"""Capability entry definitions shared by generic capability jobs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityInput:
    key: str
    label: str
    type: str = "textarea"
    required: bool = False
    placeholder: str = ""


@dataclass(frozen=True)
class CapabilityConfig:
    key: str
    group: str
    path: str
    nav_label: str
    title: str
    description: str
    button_text: str
    inputs: tuple[CapabilityInput, ...]
    outputs: tuple[str, ...]
    steps: tuple[str, ...]
    skill_name: str | None = None
    validator_script: str | None = None


COMMON_PROFILE_INPUTS = (
    CapabilityInput("identity", "我的身份", "text", True, "例如：宠物医院 / 宠物店 / 宠物博主"),
    CapabilityInput("direction", "想做方向", "text", False, "例如：科普 + 日常 / 本地引流 / 用品测评"),
    CapabilityInput("brief", "一句话描述", "textarea", False, "补充你的账号现状、城市、资源或目标"),
)


CAPABILITIES: dict[str, CapabilityConfig] = {
    "competitor-link-diagnosis": CapabilityConfig(
        key="competitor-link-diagnosis",
        group="competitor-insights",
        path="/competitor-insights/link-diagnosis",
        nav_label="竞品链接诊断",
        title="竞品链接诊断",
        description="输入 1-3 个竞品链接，拆解对方内容打法、账号定位和可借鉴模板。",
        button_text="开始诊断",
        inputs=(
            CapabilityInput("competitor_links", "竞品链接", "textarea", True, "每行一个链接，支持抖音/小红书/B站/视频号"),
            *COMMON_PROFILE_INPUTS,
        ),
        outputs=("竞品内容拆解报告", "爆款结构模板", "可借鉴要素清单"),
        steps=("读取竞品链接", "拆解内容形态与主题", "提炼可复用打法", "生成报告和结构化 JSON"),
    ),
    "competitor-account-discovery": CapabilityConfig(
        key="competitor-account-discovery",
        group="competitor-insights",
        path="/competitor-insights/account-discovery",
        nav_label="对标账号发现",
        title="对标账号发现",
        description="不知道对手是谁时，根据身份和方向推荐 3-5 个合适的对标账号。",
        button_text="发现对标账号",
        inputs=COMMON_PROFILE_INPUTS,
        outputs=("对标账号推荐清单", "推荐理由", "后续调研优先级"),
        steps=("理解用户身份", "搜索赛道热门账号", "筛选对标账号", "生成推荐说明"),
    ),
    "viral-content-breakdown": CapabilityConfig(
        key="viral-content-breakdown",
        group="competitor-insights",
        path="/competitor-insights/viral-breakdown",
        nav_label="爆款内容拆解",
        title="爆款内容拆解",
        description="聚焦竞品爆款内容，拆开头、节奏、主题、视觉风格和互动设计。",
        button_text="拆解爆款",
        inputs=(CapabilityInput("materials", "竞品内容/链接", "textarea", True, "粘贴爆款链接、标题、文案或数据"), *COMMON_PROFILE_INPUTS),
        outputs=("爆款拆解卡", "结构模板", "内容规律总结"),
        steps=("识别内容形态", "按形态选择拆解维度", "提炼爆款原因", "输出可复用模板"),
    ),
    "comment-demand-insights": CapabilityConfig(
        key="comment-demand-insights",
        group="competitor-insights",
        path="/competitor-insights/comment-demands",
        nav_label="评论需求洞察",
        title="评论需求洞察",
        description="分析评论区高频问题、情绪和未满足需求，沉淀选题弹药。",
        button_text="分析评论需求",
        inputs=(CapabilityInput("comments", "评论区素材", "textarea", True, "粘贴评论、评论截图 OCR 文本或评论导出"), *COMMON_PROFILE_INPUTS),
        outputs=("粉丝真实需求 Top 5", "情绪画像", "评论区策略建议"),
        steps=("整理评论文本", "聚类高频问题", "识别情绪与未满足需求", "生成洞察卡"),
    ),
    "monetization-path-analysis": CapabilityConfig(
        key="monetization-path-analysis",
        group="competitor-insights",
        path="/competitor-insights/monetization",
        nav_label="变现路径分析",
        title="变现路径分析",
        description="根据竞品内容痕迹推断广告、带货、知识付费或到店引流路径。",
        button_text="分析变现路径",
        inputs=(CapabilityInput("account_trace", "账号商业痕迹", "textarea", True, "粘贴商业内容、合作品牌、直播/商品信息"), *COMMON_PROFILE_INPUTS),
        outputs=("变现模式识别", "变现效率评估", "适配路径建议"),
        steps=("识别商业内容", "估算变现频率", "判断适配度", "生成路径建议"),
    ),
    "differentiation-map": CapabilityConfig(
        key="differentiation-map",
        group="competitor-insights",
        path="/competitor-insights/differentiation-map",
        nav_label="差异化机会地图",
        title="差异化机会地图",
        description="综合竞品弱点、评论需求和自身优势，找到定位方案和启动选题。",
        button_text="生成机会地图",
        inputs=(CapabilityInput("research_notes", "调研素材", "textarea", True, "粘贴竞品拆解、评论洞察或账号现状"), *COMMON_PROFILE_INPUTS),
        outputs=("差异化定位方案", "机会地图", "启动选题清单"),
        steps=("归纳竞品空白点", "匹配自身优势", "设计定位方案", "输出行动建议"),
    ),
    "competitor-research-report": CapabilityConfig(
        key="competitor-research-report",
        group="competitor-insights",
        path="/competitor-insights/research-report",
        nav_label="竞品调研报告",
        title="竞品调研报告",
        description="把竞品拆解、评论洞察、变现分析和差异化机会汇总成完整报告。",
        button_text="生成调研报告",
        inputs=(CapabilityInput("research_material", "调研资料", "textarea", True, "粘贴全部调研材料或上游 JSON"), *COMMON_PROFILE_INPUTS),
        outputs=("Markdown 调研报告", "结构化 JSON", "下一步行动建议"),
        steps=("整合调研材料", "生成一页纸摘要", "组织四维分析", "输出报告和 JSON"),
    ),
}


TOPIC_METHODS = [
    ("pain-point-topics", "痛点选题池", "从评论区高频问题和未满足需求生成选题。", "生成痛点选题"),
    ("gap-opportunity-topics", "空白机会选题", "从竞品没做或做得浅的方向生成差异化选题。", "生成机会选题"),
    ("crossover-topics", "跨界灵感选题", "把宠物内容与生活方式、消费、教育等领域交叉生成新角度。", "生成跨界选题"),
    ("counterintuitive-topics", "反常识选题", "围绕颠覆认知的钩子生成高停留选题。", "生成反常识选题"),
    ("trend-topics", "热点追踪选题", "结合当日热点、行业新闻和平台话题生成时效选题。", "生成热点选题"),
    ("festival-topics", "节日节点选题", "围绕节日、节点和营销日历生成可排期选题。", "生成节日选题"),
    ("controversy-topics", "争议话题选题", "围绕争议观点生成可控、可讨论的内容选题。", "生成争议选题"),
    ("series-topics", "系列栏目选题", "设计连续栏目和分集结构，适合做长期账号资产。", "生成系列选题"),
    ("seasonal-topics", "季节场景选题", "围绕换季、温度、地域和生活场景生成选题。", "生成季节选题"),
]
for key, label, desc, button in TOPIC_METHODS:
    CAPABILITIES[key] = CapabilityConfig(
        key=key,
        group="topic-planning",
        path=f"/topic-planning/{key}",
        nav_label=label,
        title=label,
        description=desc,
        button_text=button,
        inputs=(
            CapabilityInput("competitor_json", "参考资料 JSON/摘要", "textarea", True, "粘贴账号定位、用户痛点、评论需求或关键发现"),
            CapabilityInput("identity", "我的身份", "text", True, "例如：成都宠物医院"),
            CapabilityInput("avoid", "不想做的内容", "text", False, "例如：搞笑整活 / 高争议内容"),
            CapabilityInput("advantages", "资源/优势", "textarea", False, "例如：真实病例素材、门店场景、专业医生出镜"),
        ),
        outputs=("选题池", "优先级评分", "结构化 JSON"),
        steps=("读取参考资料", "按方法生成选题", "六维评分筛选", "去重合并并输出 JSON"),
        skill_name="zhongying-topic-planner",
        validator_script=".agents/skills/zhongying-topic-planner/scripts/validate_result.py",
    )


SCRIPT_METHODS = [
    ("script-master-draft", "脚本母版生成", "把选题信息和受众画像生成一条完整可拍脚本。", "生成脚本母版"),
    ("viral-template-adaptation", "爆款模板套写", "读取爆款模板骨架，套写到当前选题和账号身份。", "套写爆款模板"),
    ("warm-healing-script", "温暖治愈脚本", "用朋友聊天式表达生成温暖、治愈、亲切的脚本。", "生成治愈脚本"),
    ("professional-authority-script", "专业权威脚本", "用医生/专家科普语气生成有理有据的脚本。", "生成权威脚本"),
    ("lively-humor-script", "活泼幽默脚本", "用轻松、有梗、节奏快的风格生成脚本。", "生成幽默脚本"),
    ("humanize-script", "去 AI 味改写", "检查并改写脚本，让语言更口语、更自然、更像真人。", "开始改写"),
]
for key, label, desc, button in SCRIPT_METHODS:
    CAPABILITIES[key] = CapabilityConfig(
        key=key,
        group="script-creation",
        path=f"/script-creation/{key}",
        nav_label=label,
        title=label,
        description=desc,
        button_text=button,
        inputs=(
            CapabilityInput("topic_json", "选题 JSON/内容简报", "textarea", True, "粘贴选题、受众、核心信息和制作提示"),
            CapabilityInput("asset_library", "模板资产/竞品拆解", "textarea", False, "粘贴爆款模板、原脚本或拆解注释"),
            CapabilityInput("user_viewpoint", "用户观点", "textarea", False, "一句话补充你想表达的观点"),
        ),
        outputs=("Markdown 脚本", "结构化 JSON", "制作提示"),
        steps=("检索模板", "设计脚本骨架", "填充内容", "风格化改写", "输出 Markdown 和 JSON"),
        skill_name="zhongying-script-creator",
        validator_script=".agents/skills/zhongying-script-creator/scripts/validate_result.py",
    )


def get_capability(key: str) -> CapabilityConfig | None:
    return CAPABILITIES.get(key)
