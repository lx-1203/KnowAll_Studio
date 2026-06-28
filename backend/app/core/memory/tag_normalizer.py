"""Tag normalizer - maps LLM-generated tags to a canonical vocabulary"""
import re

# Canonical tag mappings: {synonym: canonical}
DOMAIN_SYNONYMS = {
    # Math
    "高等数学": "高数",
    "微积分": "微积分",
    "calculus": "微积分",
    "数学分析": "数学分析",
    "线性代数": "线性代数",
    "概率论": "概率论",
    "统计学": "统计学",
    "离散数学": "离散数学",
    # CS
    "数据结构": "数据结构",
    "算法": "算法",
    "操作系统": "操作系统",
    "计算机网络": "计算机网络",
    "数据库": "数据库",
    "编译原理": "编译原理",
    "人工智能": "人工智能",
    "机器学习": "机器学习",
    "深度学习": "深度学习",
    # Physics
    "物理学": "物理学",
    "力学": "力学",
    "电磁学": "电磁学",
    "量子力学": "量子力学",
    "热力学": "热力学",
    "光学": "光学",
    # Chemistry
    "化学": "化学",
    "有机化学": "有机化学",
    "无机化学": "无机化学",
    "物理化学": "物理化学",
    # Biology
    "生物学": "生物学",
    "分子生物学": "分子生物学",
    "细胞生物学": "细胞生物学",
    "遗传学": "遗传学",
    # Economics/Business
    "经济学": "经济学",
    "微观经济学": "微观经济学",
    "宏观经济学": "宏观经济学",
    "管理学": "管理学",
    "金融学": "金融学",
    "会计学": "会计学",
    # General academic
    "定义": "概念定义",
    "概念": "概念定义",
    "定理": "定理公式",
    "公式": "定理公式",
}

MEMORY_TAG_CANONICAL = {
    "需要记忆": "需记忆",
    "背诵": "需记忆",
    "必背": "需记忆",
    "理解": "需理解",
    "推导": "需推导",
    "计算": "需计算",
    "应用": "需应用",
    "易混淆": "易混淆",
    "容易混": "易混淆",
    "对比": "易混淆",
    "核心": "核心重点",
    "重点": "核心重点",
    "重要": "核心重点",
    "基础": "基础知识",
}


class TagNormalizer:
    """Normalize tags from LLM output to canonical forms."""

    @staticmethod
    def normalize_domain_tag(tag: str) -> str:
        """Map a domain tag to its canonical form."""
        tag_clean = tag.strip().lower()
        # Direct lookup
        if tag_clean in DOMAIN_SYNONYMS:
            return DOMAIN_SYNONYMS[tag_clean]
        # Substring match
        for syn, canonical in DOMAIN_SYNONYMS.items():
            if syn in tag_clean or tag_clean in syn:
                return canonical
        # Return original with first char capitalized
        return tag.strip()

    @staticmethod
    def normalize_memory_tag(tag: str) -> str:
        """Map a memory strategy tag to its canonical form."""
        tag_clean = tag.strip().lower()
        if tag_clean in MEMORY_TAG_CANONICAL:
            return MEMORY_TAG_CANONICAL[tag_clean]
        for syn, canonical in MEMORY_TAG_CANONICAL.items():
            if syn in tag_clean or tag_clean in syn:
                return canonical
        return tag.strip()

    @staticmethod
    def normalize_tags(tags: list) -> dict:
        """Normalize a list of tags into {domain_tags, memory_tags}.

        Accepts both flat list (backward compat) and structured dict.
        """
        if isinstance(tags, dict):
            domain = [TagNormalizer.normalize_domain_tag(t)
                      for t in tags.get("domain_tags", [])]
            memory = [TagNormalizer.normalize_memory_tag(t)
                      for t in tags.get("memory_tags", [])]
            return {"domain_tags": list(set(domain)), "memory_tags": list(set(memory))}

        if isinstance(tags, list):
            domain = []
            memory = []
            for t in tags:
                if isinstance(t, str):
                    # Heuristic: short English/Chinese concept names are domain tags
                    norm_d = TagNormalizer.normalize_domain_tag(t)
                    norm_m = TagNormalizer.normalize_memory_tag(t)
                    # Check if it maps to a known domain or memory tag
                    if norm_d in DOMAIN_SYNONYMS.values():
                        domain.append(norm_d)
                    elif norm_m in MEMORY_TAG_CANONICAL.values():
                        memory.append(norm_m)
                    else:
                        domain.append(norm_d)
            return {"domain_tags": list(set(domain)), "memory_tags": list(set(memory))}

        return {"domain_tags": [], "memory_tags": []}

    @classmethod
    def enrich_from_knowledge_point(
        cls,
        tags: dict,
        knowledge_point: dict | None,
    ) -> dict:
        """Enrich card tags with tags from the associated knowledge point."""
        if not knowledge_point:
            return tags

        kp_tags = knowledge_point.get("tags", []) if isinstance(knowledge_point, dict) else []
        if hasattr(knowledge_point, 'tags'):
            kp_tags = knowledge_point.tags or []

        for t in kp_tags:
            domain_tag = cls.normalize_domain_tag(t) if isinstance(t, str) else t
            if domain_tag not in tags.get("domain_tags", []):
                tags.setdefault("domain_tags", []).append(domain_tag)

        return tags


tag_normalizer = TagNormalizer()
