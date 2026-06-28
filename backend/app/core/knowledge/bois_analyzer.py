"""BOIS (Basic Ordering Ideas) Analyzer - 基于托尼·巴赞思维导图理论

BOIS 是思维导图创始人托尼·巴赞提出的核心技术之一，与关键词技术并列为
思维导图两大支柱。BOIS 强调通过"位阶（阶层）"来组织知识，使思维从
无序发散变为有序收敛。

核心原理：
  1. 上位阶（上位词）：更大、更抽象的分类概念
  2. 同位阶（同类词）：同一层级的并列概念
  3. 下位阶（下位词）：更具体、更细分的子概念

BOIS 三步操作法：
  - 上找大类：这个想法属于哪个更大的类别？
  - 中找同类：这个大类下还有哪些同级别的概念？
  - 下找小类：这个概念还可以怎样细分？

参考：
  - 《思维导图》托尼·巴赞 著，第9章
  - 《思维导图工作法》王玉印 著，第四章
"""

from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class BOISMetrics:
    """BOIS 质量评估指标"""
    # 基础统计
    total_nodes: int = 0
    total_edges: int = 0
    max_depth: int = 0
    depth_distribution: dict[int, int] = field(default_factory=dict)  # {level: count}

    # BOIS 核心指标
    avg_children_per_node: float = 0.0           # 平均子节点数（同位阶广度）
    branching_factor: float = 0.0                # 分支因子 = 总边数/总节点数
    hierarchy_balance: float = 0.0               # 层级均衡度 0-1（同级节点数分布均匀性）
    coverage_completeness: float = 0.0            # 覆盖完整性（是否缺少中间层级）

    # 同位阶分析（中找同类）
    peer_groups: dict[int, list[str]] = field(default_factory=dict)  # {level: [node_labels]}
    peer_variance: float = 0.0                   # 同级节点数方差（越小越均衡）

    # 结构诊断
    orphan_nodes: int = 0                        # 孤立节点数（无父节点、非根节点）
    shallow_nodes: int = 0                       # 浅层节点数（有父无子）
    deep_nodes: int = 0                          # 深层节点数（深度>=3）

    # BOIS 综合评分
    bois_score: float = 0.0                      # 0-100 综合评分

    # 优化建议
    suggestions: list[str] = field(default_factory=list)

    # 分类标签体系
    category_framework: dict = field(default_factory=dict)  # BOIS 分类框架


class BOISAnalyzer:
    """BOIS 知识导图分析器

    对已有知识树进行 BOIS 理论分析，输出质量指标和改进建议。
    可用于：
    - 评估现有思维导图的 BOIS 质量
    - 指导 LLM 重新组织知识结构
    - 提供用户可视化的质量反馈
    """

    # BOIS 评分权重
    WEIGHT_HIERARCHY = 0.30       # 层级结构合理性
    WEIGHT_BRANCHING = 0.25       # 分支发散度
    WEIGHT_PEER_BALANCE = 0.20    # 同位阶均衡性
    WEIGHT_COVERAGE = 0.15        # 覆盖完整性
    WEIGHT_CONNECTIVITY = 0.10    # 节点连通性

    # 理想参数
    IDEAL_MAX_CHILDREN = 7        # 米勒定律：人类短期记忆 7±2
    IDEAL_MAX_DEPTH = 4           # 推荐最大深度
    IDEAL_MIN_DEPTH = 2           # 推荐最小深度

    def analyze(self, nodes: list[dict], edges: list[dict]) -> BOISMetrics:
        """对知识节点和边进行完整的 BOIS 分析。

        Args:
            nodes: 节点列表，每个节点含 id, label, level 等
            edges: 边列表，每条边含 source, target, relation

        Returns:
            BOISMetrics 包含所有分析结果
        """
        metrics = BOISMetrics()

        if not nodes:
            metrics.suggestions.append("无节点数据，请先上传文档并生成知识总结")
            return metrics

        node_map = {n["id"]: n for n in nodes}
        metrics.total_nodes = len(nodes)
        metrics.total_edges = len(edges)

        # 1. 基础统计
        metrics.max_depth = max((n.get("level", 0) for n in nodes), default=0)
        metrics.depth_distribution = self._count_by_level(nodes)

        # 2. 构建父子关系
        children_map: dict[str, list[str]] = defaultdict(list)
        parent_map: dict[str, str] = {}
        for edge in edges:
            if edge.get("relation") == "parent_child":
                children_map[edge["source"]].append(edge["target"])
                parent_map[edge["target"]] = edge["source"]

        # 3. 计算分支指标
        child_counts = [len(v) for v in children_map.values() if v]
        metrics.avg_children_per_node = (
            sum(child_counts) / max(len(child_counts), 1) if child_counts else 0.0
        )
        metrics.branching_factor = (
            metrics.total_edges / metrics.total_nodes if metrics.total_nodes > 0 else 0.0
        )

        # 4. 同位阶分析
        metrics.peer_groups = self._group_by_level(nodes)
        metrics.peer_variance = self._compute_peer_variance(metrics.peer_groups)

        # 5. 层级均衡度
        metrics.hierarchy_balance = self._compute_balance(metrics.peer_groups, metrics.max_depth)

        # 6. 覆盖完整性
        metrics.coverage_completeness = self._compute_coverage(
            nodes, node_map, children_map, parent_map, metrics.max_depth
        )

        # 7. 节点分类
        root_ids = {n["id"] for n in nodes if n.get("parent_id") is None}
        # 孤节点：声称为子节点但无对应 parent_child 边（父节点缺失）
        metrics.orphan_nodes = sum(
            1 for n in nodes
            if n.get("parent_id") and n["id"] not in parent_map
            and n["id"] not in root_ids
        )
        # 浅层节点（叶节点）：无子节点的节点
        parent_ids = {e["source"] for e in edges if e.get("relation") == "parent_child"}
        metrics.shallow_nodes = sum(
            1 for n in nodes if n["id"] not in parent_ids
        )
        # 深层节点：深度 >= 3
        metrics.deep_nodes = sum(
            1 for n in nodes if n.get("level", 0) >= 3
        )

        # 8. 综合评分
        metrics.bois_score = self._compute_score(metrics)

        # 9. 生成建议
        metrics.suggestions = self._generate_suggestions(metrics)

        # 10. 构建分类框架
        metrics.category_framework = self._build_category_framework(nodes, children_map)

        return metrics

    # ─── 内部计算方法 ───────────────────────────────────────────

    def _count_by_level(self, nodes: list[dict]) -> dict[int, int]:
        dist = defaultdict(int)
        for n in nodes:
            dist[n.get("level", 0)] += 1
        return dict(sorted(dist.items()))

    def _group_by_level(self, nodes: list[dict]) -> dict[int, list[str]]:
        groups = defaultdict(list)
        for n in nodes:
            groups[n.get("level", 0)].append(n.get("label", n.get("title", "")))
        return dict(sorted(groups.items()))

    def _compute_peer_variance(self, peer_groups: dict[int, list[str]]) -> float:
        """计算同级节点数的方差。方差越小，各层宽度越均衡。"""
        counts = [len(v) for v in peer_groups.values()]
        if not counts:
            return 0.0
        mean = sum(counts) / len(counts)
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        return variance

    def _compute_balance(self, peer_groups: dict[int, list[str]], max_depth: int) -> float:
        """计算层级均衡度 0-1。

        理想情况：每一层的节点数是上一层的 2-7 倍（逐步发散）。
        如果某层节点数为 0 或远大于上层，扣分。
        """
        if max_depth < 1 or len(peer_groups) < 2:
            return 0.5  # 只有一层，中性

        levels = sorted(peer_groups.keys())
        scores = []
        for i in range(1, len(levels)):
            prev_count = len(peer_groups[levels[i - 1]])
            curr_count = len(peer_groups[levels[i]])
            if prev_count == 0:
                scores.append(0.0)
                continue
            ratio = curr_count / prev_count
            # 理想 ratio 在 1.5-5 之间
            if 1.5 <= ratio <= 5.0:
                scores.append(1.0)
            elif 1.0 <= ratio < 1.5 or 5.0 < ratio <= 7.0:
                scores.append(0.7)
            elif ratio < 1.0:
                scores.append(0.3)  # 下层比上层少，不合理
            else:
                scores.append(0.4)  # 扩散过度
        return sum(scores) / len(scores) if scores else 0.5

    def _compute_coverage(
        self,
        nodes: list[dict],
        children_map: dict[str, list[str]],
        parent_map: dict[str, str],
        max_depth: int,
    ) -> float:
        """检测是否缺少中间层级（跳级）。

        e.g. L1 -> L3 但缺少 L2，说明覆盖不完整。
        """
        if max_depth <= 2:
            return 1.0  # 层级少，不扣分

        gaps = 0
        total_paths = 0
        leaves = [n["id"] for n in nodes if n["id"] not in children_map or not children_map[n["id"]]]

        for leaf_id in leaves:
            current = leaf_id
            levels_seen = set()
            while current in parent_map:
                node = next((n for n in nodes if n["id"] == current), None)
                if node:
                    levels_seen.add(node.get("level", 0))
                current = parent_map[current]
            # 根节点
            root = next((n for n in nodes if n["id"] == current), None)
            if root:
                levels_seen.add(root.get("level", 0))

            if levels_seen:
                expected = set(range(min(levels_seen), max(levels_seen) + 1))
                gaps += len(expected - levels_seen)
                total_paths += 1

        if total_paths == 0:
            return 1.0
        gap_ratio = gaps / (total_paths * max_depth)
        return max(0.0, 1.0 - gap_ratio)

    def _compute_score(self, m: BOISMetrics) -> float:
        """计算综合 BOIS 评分 0-100。"""
        scores = []

        # 1. 层级合理性 (30%)
        if m.max_depth == 0:
            scores.append(0)
        elif m.max_depth == 1:
            scores.append(30)  # 只有一级太浅
        elif self.IDEAL_MIN_DEPTH <= m.max_depth <= self.IDEAL_MAX_DEPTH:
            scores.append(100)
        elif m.max_depth > self.IDEAL_MAX_DEPTH:
            scores.append(70)  # 太深，可能分类过细
        else:
            scores.append(50)

        # 2. 分支发散度 (25%)
        if m.avg_children_per_node == 0:
            scores.append(0)
        elif 2 <= m.avg_children_per_node <= self.IDEAL_MAX_CHILDREN:
            scores.append(100)
        elif m.avg_children_per_node < 2:
            scores.append(50)  # 发散不足
        else:
            scores.append(70)  # 发散过度

        # 3. 同位阶均衡性 (20%)
        balance_score = m.hierarchy_balance * 100
        scores.append(balance_score)

        # 4. 覆盖完整性 (15%)
        scores.append(m.coverage_completeness * 100)

        # 5. 连通性 (10%)
        if m.total_nodes <= 1:
            scores.append(100)
        else:
            orphan_ratio = m.orphan_nodes / m.total_nodes
            scores.append((1.0 - orphan_ratio) * 100)

        weights = [
            self.WEIGHT_HIERARCHY, self.WEIGHT_BRANCHING,
            self.WEIGHT_PEER_BALANCE, self.WEIGHT_COVERAGE,
            self.WEIGHT_CONNECTIVITY,
        ]
        return sum(s * w for s, w in zip(scores, weights))

    def _generate_suggestions(self, m: BOISMetrics) -> list[str]:
        """根据 BOIS 指标生成人类可读的改进建议。"""
        suggestions = []

        if m.max_depth < self.IDEAL_MIN_DEPTH:
            suggestions.append(
                f"【下找小类】当前只有 {m.max_depth} 层，建议进一步细分知识点。"
                f"对每个一级节点追问\u201c还可以怎样细分？\u201d，至少展开到 "
                f"{self.IDEAL_MIN_DEPTH}-{self.IDEAL_MAX_DEPTH} 层。"
            )

        if m.avg_children_per_node < 1.5:
            suggestions.append(
                f"【中找同类】平均每个节点仅 {m.avg_children_per_node:.1f} 个子节点，"
                f"分支发散不足。建议检查每个节点是否存在遗漏的同位阶概念，"
                f"目标每节点 2-7 个子节点（米勒定律）。"
            )

        if m.orphan_nodes > 0:
            suggestions.append(
                f"【结构修复】检测到 {m.orphan_nodes} 个孤立节点，"
                f"请通过\u201c上找大类\u201d为它们找到合适的父节点归属。"
            )

        if m.hierarchy_balance < 0.5:
            suggestions.append(
                "【层级均衡】各层节点数分布不均，建议调整知识结构使上层简洁、"
                "下层充分展开，形成\u201c倒金字塔\u201d形状。"
            )

        if m.coverage_completeness < 0.7:
            suggestions.append(
                "【跳级检测】存在层级跳跃（如 L1→L3 缺少 L2），"
                "建议补充中间层级以保证思维递进的连续性。"
            )

        if m.shallow_nodes > m.total_nodes * 0.6:
            suggestions.append(
                "【发散不足】超过60%的节点没有子节点，思维导图偏向列表而非"
                "真正的放射性结构。建议对关键知识点进行\u201c下找小类\u201d展开。"
            )

        if m.max_depth > self.IDEAL_MAX_DEPTH + 1:
            suggestions.append(
                f"【收拢建议】深度达 {m.max_depth} 层，可能分类过细。"
                f"建议合并底层节点或提升部分子节点层级，控制在 "
                f"{self.IDEAL_MAX_DEPTH} 层以内。"
            )

        if not suggestions:
            suggestions.append(
                "思维导图 BOIS 结构良好，层级合理、分支充分、分类均衡。"
                "可以继续关注知识点之间的横向关联（跨分支连线）。"
            )

        return suggestions

    def _build_category_framework(
        self, nodes: list[dict], children_map: dict[str, list[str]]
    ) -> dict:
        """构建 BOIS 分类框架。

        从根节点出发，提取三级分类体系：
        - 大类（上位阶）：L1 节点
        - 中类（同位阶）：L2 节点
        - 小类（下位阶）：L3+ 节点
        """
        levels = defaultdict(list)
        for n in nodes:
            levels[n.get("level", 0)].append(n)

        framework = {
            "上位阶（大类）": [
                {"id": n["id"], "label": n.get("label", n.get("title", "")), "child_count": len(children_map.get(n["id"], []))}
                for n in levels.get(1, [])
            ],
            "中位阶（中类）": [
                {"id": n["id"], "label": n.get("label", n.get("title", "")), "parent_id": n.get("parent_id")}
                for n in levels.get(2, [])
            ],
            "下位阶（小类）": [
                {"id": n["id"], "label": n.get("label", n.get("title", ""))}
                for n in levels.get(3, []) + levels.get(4, [])
            ],
        }
        return framework

    def suggest_restructure(
        self, nodes: list[dict], edges: list[dict], metrics: BOISMetrics
    ) -> dict:
        """基于 BOIS 分析生成具体的重构建议。

        返回一个结构化的重构方案，可供 LLM 或前端使用。

        Returns:
            dict with:
                - merge_suggestions: 可合并的节点组
                - split_suggestions: 应拆分的节点
                - reclassify_suggestions: 应重新分类的节点
                - new_category_suggestions: 建议新增的类别
        """
        children_map = defaultdict(list)
        for edge in edges:
            if edge.get("relation") == "parent_child":
                children_map[edge["source"]].append(edge["target"])

        # 找可以合并的节点（同一个父节点下仅1-2个子节点且深度一致）
        merge_candidates = []
        for parent_id, child_ids in children_map.items():
            if len(child_ids) == 1:
                parent = next((n for n in nodes if n["id"] == parent_id), None)
                child = next((n for n in nodes if n["id"] == child_ids[0]), None)
                if parent and child:
                    merge_candidates.append({
                        "parent": {"id": parent_id, "label": parent.get("label", "")},
                        "child": {"id": child_ids[0], "label": child.get("label", "")},
                        "reason": "单子节点，可将二者合并以减少冗余层级",
                    })

        # 找需要拆分的节点（子节点过多 > 7）
        split_candidates = []
        for parent_id, child_ids in children_map.items():
            if len(child_ids) > self.IDEAL_MAX_CHILDREN:
                parent = next((n for n in nodes if n["id"] == parent_id), None)
                split_candidates.append({
                    "node": {"id": parent_id, "label": parent.get("label", "") if parent else ""},
                    "child_count": len(child_ids),
                    "reason": f"子节点过多({len(child_ids)}个)，建议引入中间类别分组",
                    "suggested_groups": self._suggest_groups([n for n in nodes if n["id"] in child_ids]),
                })

        # 找需要重新分类的节点（孤立节点或深度异常）
        reclassify = []
        root_ids = {n["id"] for n in nodes if n.get("parent_id") is None}
        for n in nodes:
            if n["id"] not in root_ids and n.get("parent_id") and n["id"] not in [
                c for clist in children_map.values() for c in clist
            ]:
                # 不在 children_map 中 = 孤儿（作为子节点但找不到对应的父节点边）
                continue  # orphan_nodes 已在 metrics 中计数

            if n.get("level", 0) > self.IDEAL_MAX_DEPTH:
                reclassify.append({
                    "node": {"id": n["id"], "label": n.get("label", n.get("title", ""))},
                    "current_level": n.get("level", 0),
                    "reason": f"层级过深({n.get('level', 0)}层)，建议提升层级或合并",
                })

        return {
            "merge_suggestions": merge_candidates,
            "split_suggestions": split_candidates,
            "reclassify_suggestions": reclassify[:10],  # 限制数量
            "summary": (
                f"共 {len(merge_candidates)} 个合并建议、{len(split_candidates)} 个拆分建议、"
                f"{len(reclassify)} 个重分类建议"
            ),
        }

    def _suggest_groups(self, child_nodes: list[dict]) -> list[dict]:
        """将过多子节点按语义相似度分组。使用简单启发式按标签长度和前缀聚类。"""
        groups = []
        ungrouped = list(child_nodes)

        # 简单分组：按标签前2字聚类（可作为 LLM 精细分组的前处理）
        prefix_groups = defaultdict(list)
        for n in ungrouped:
            label = n.get("label", n.get("title", ""))
            prefix = label[:2] if len(label) >= 2 else label
            prefix_groups[prefix].append(n)

        for prefix, members in sorted(prefix_groups.items()):
            if len(members) >= 2:
                groups.append({
                    "suggested_category": f"{prefix}相关",
                    "members": [{"id": m["id"], "label": m.get("label", m.get("title", ""))} for m in members],
                    "count": len(members),
                })

        return groups


# 全局单例
bois_analyzer = BOISAnalyzer()
