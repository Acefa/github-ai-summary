import requests
from typing import List, Dict, Callable
import logging
from datetime import datetime, timedelta, timezone
import os
from statistics import mean

"""
GitHub项目爬虫模块

该模块负责从GitHub API获取符合特定条件的优质项目。
主要功能：
1. 构建高级搜索查询
2. 处理API请求和响应
3. 解析项目数据

使用示例：
    config = {
        "search_keywords": "AI",
        "min_stars": 100,
        "max_results": 20,
        ...
    }
    crawler = GitHubCrawler(config)
    projects = crawler.search_repositories()
"""

logger = logging.getLogger(__name__)

class GitHubCrawler:
    """
    GitHub项目爬虫类
    
    负责构建搜索查询并从GitHub API获取项目信息。
    支持多种过滤条件，如stars数、更新时间、fork数等。
    """

    def __init__(self, config: dict):
        """
        初始化爬虫实例
        
        Args:
            config (dict): 配置字典，包含搜索参数和API设置
                - api: API相关配置
                - search_criteria: 搜索条件
                - topics: 主题标签列表
        """
        self.config = config  # 保存配置到实例变量
        self.base_url = config['api']['base_url']
        self.headers = {
            "Accept": config['api']['accept'],
            "User-Agent": f"{config['api']['user_agent']} (contact: {config['api']['contact_email']})"
        }
        self.search_query = self._build_search_query(config)
        self.search_params = {
            "q": self.search_query,
            "sort": config['search_criteria']['sort_by'],
            "order": config['search_criteria']['sort_order'],
            "per_page": config['max_results']
        }
        logger.debug(f"初始化搜索参数: {self.search_params}")  # 添加调试日志

    def _build_search_query(self, config: dict) -> str:
        """
        构建GitHub高级搜索查询字符串
        
        构建包括多个条件的搜索查询，支持：
        - 关键词搜索（可选）
        - stars数过滤
        - 编程语言过滤
        - 更新时间过滤
        - fork数过滤
        - 主题标签过滤
        
        Args:
            config (dict): 包含搜索条件的配置字典
            
        Returns:
            str: 格式化的搜索查询字符串
            
        示例查询:
            "stars:>=1000 pushed:>2024-02-07 forks:>=100"
        """
        criteria = config['search_criteria']
        # 获取当前时间和时间范围
        now = datetime.now(timezone.utc)
        update_days = criteria['update_within_days']
        
        # 计算时间范围（例如：最近2天的项目）
        date_range = [
            (now - timedelta(days=update_days)).strftime('%Y-%m-%d'),
            now.strftime('%Y-%m-%d')
        ]
        
        query_parts = []
        
        # 添加关键词搜索（如果有）
        if config.get('search_keywords'):
            keywords = " OR ".join(config['search_keywords'].split(","))
            query_parts.append(keywords)
        
        # 使用star范围而不是最小值，以发现潜力项目
        query_parts.append(f"stars:{config['min_stars']}..{config['min_stars']*500}")

        # 添加语言过滤（如果有）
        if config.get('language'):
            query_parts.append(f"language:{config['language']}")

        # 使用精确的时间范围
        query_parts.append(f"pushed:{date_range[0]}..{date_range[1]}")

        # 使用fork与star的比例作为过滤条件
        min_fork_ratio = 0.05  # fork数至少是star数的5%
        query_parts.append(f"forks:>={int(config['min_stars'] * min_fork_ratio)}")

        # 排除fork的仓库
        if criteria['exclude_forks']:
            query_parts.append("fork:false")

        # 添加额外的质量指标
        query_parts.append("good-first-issues:>0")  # 有良好的新手问题
        query_parts.append("topics:>=2")  # 至少有2个主题标签

        # 组合查询字符串
        query = ' '.join(query_parts)
        logger.debug(f"构建查询语句: {query}")
        return query

    def _calculate_project_score(self, project: Dict) -> float:
        """
        计算项目质量分数
        
        使用多个维度评估项目质量：
        - 活跃度：更新频率、issue处理速度
        - 受欢迎度：stars和forks的比例
        - 维护性：文档完整度、issue响应率
        - 成熟度：项目年龄、主题标签数量、描述完整性
        
        Args:
            project (Dict): 项目信息字典
        
        Returns:
            float: 0-100之间的质量分数
        """
        scores = []
        
        # 1. 活跃度评分 (35分)
        now = datetime.now(timezone.utc)
        updated_at = datetime.fromisoformat(project['updated_at'].replace('Z', '+00:00'))
        update_days = (now - updated_at).days
        # 最近更新得高分
        activity_score = 35 * (1 - min(update_days / 7, 1))
        scores.append(activity_score)
        
        # 2. 增长潜力评分 (25分)
        if project['stars'] > 0:
            fork_ratio = project['forks'] / project['stars']
            growth_score = 25 * min(fork_ratio * 2, 1)  # fork比例越高说明越有潜力
        else:
            growth_score = 0
        scores.append(growth_score)
        
        # 3. 社区活跃度评分 (20分)
        if project['stars'] > 0:
            # 看issue数量是否适中（太少说明不活跃，太多说明维护不足）
            issue_ratio = project['open_issues'] / project['stars']
            ideal_ratio = 0.1  # 理想的issue比例
            maintenance_score = 20 * (1 - min(abs(issue_ratio - ideal_ratio) * 5, 1))
            scores.append(maintenance_score)
        
        # 4. 成熟度评分 (20分) - 不再使用项目大小
        # 4.1 项目年龄 (10分)
        created_at = datetime.fromisoformat(project['created_at'].replace('Z', '+00:00'))
        project_age_days = (now - created_at).days
        # 项目存在时间越长，越成熟（最高考虑2年）
        age_score = 10 * min(project_age_days / 730, 1)
        
        # 4.2 主题标签完整性 (5分)
        # 主题标签数量越多，说明项目定义越清晰
        topics_score = 5 * min(len(project['topics']) / 5, 1)
        
        # 4.3 描述完整性 (5分)
        description = project['description'] or ""
        # 描述越详细越好（理想长度为100个字符）
        desc_score = 5 * min(len(description) / 100, 1)
        
        # 合并成熟度分数
        maturity_score = age_score + topics_score + desc_score
        scores.append(maturity_score)
        
        # 确保总分不超过100
        total_score = sum(scores)
        return min(total_score, 100)

    def _filter_projects(self, projects: List[Dict], min_score: float = 60.0) -> List[Dict]:
        """
        根据质量分数过滤项目
        
        Args:
            projects (List[Dict]): 原始项目列表
            min_score (float): 最低质量分数要求，默认60分
        
        Returns:
            List[Dict]: 过滤后的高质量项目列表
        """
        scored_projects = []
        for project in projects:
            score = self._calculate_project_score(project)
            if score >= min_score:
                project['quality_score'] = round(score, 2)
                scored_projects.append(project)
        
        # 使用多重排序：先按更新时间排序，再按质量分数排序
        return sorted(
            scored_projects,
            key=lambda x: (
                datetime.fromisoformat(x['updated_at'].replace('Z', '+00:00')),
                x['quality_score']
            ),
            reverse=True
        )

    def _apply_custom_filters(self, projects: List[Dict], filters: List[Callable[[Dict], bool]] = None) -> List[Dict]:
        """
        应用自定义过滤器
        
        Args:
            projects (List[Dict]): 项目列表
            filters (List[Callable]): 过滤函数列表，每个函数返回bool
        
        Returns:
            List[Dict]: 过滤后的项目列表
        """
        if not filters:
            filters = [
                # 基本要求
                lambda p: p['description'] is not None,
                # 确保有基本文档
                lambda p: len(p['topics']) >= 2,
                # 确保项目不是太新（避免昙花一现）
                lambda p: (datetime.now(timezone.utc) - datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))).days >= 7,
                # 确保近期有更新
                lambda p: (datetime.now(timezone.utc) - datetime.fromisoformat(p['updated_at'].replace('Z', '+00:00'))).days <= 7,
            ]
        
        filtered_projects = projects
        for filter_func in filters:
            filtered_projects = [p for p in filtered_projects if filter_func(p)]
        return filtered_projects

    def search_repositories(self) -> List[Dict]:
        """
        执行GitHub API搜索并获取符合条件的项目
        
        处理API请求、响应和错误，包括：
        - API速率限制处理
        - 网络错误处理
        - 响应数据解析
        - 结果多样性保证
        
        Returns:
            List[Dict]: 项目信息列表，每个项目包含：
                - name: 项目全名
                - url: 项目地址
                - description: 项目描述
                - stars: star数量
                - forks: fork数量
                - updated_at: 最后更新时间
                - language: 主要编程语言
                - topics: 主题标签列表
                - size: 仓库大小(KB)
                - open_issues: 开放问题数量
                - quality_score: 质量评分
        
        Raises:
            RuntimeError: 当遇到API限制时
            requests.exceptions.RequestException: 当API请求失败时
        """
        logger.info(f"🔍 启动GitHub搜索 | 条件: {self.search_params}")
        
        # 添加请求前的调试信息
        logger.debug(f"发送请求 | URL: {self.base_url} | Headers: {self.headers}")
        
        response = requests.get(self.base_url, params=self.search_params, headers=self.headers)
        logger.debug(f"📡 收到API响应 | 状态码: {response.status_code}")
        
        if response.status_code == 403:
            rate_limit = response.headers.get('X-RateLimit-Reset')
            reset_time = datetime.fromtimestamp(int(rate_limit)).strftime('%Y-%m-%d %H:%M:%S')
            logger.error(f"GitHub API限制 | 重置时间: {reset_time}")
            raise RuntimeError("GitHub API请求受限")
        
        response.raise_for_status()
        items = response.json()["items"]
        logger.info(f"✅ 获取{len(items)}个优质项目")
        
        # 转换API响应为标准格式
        projects = [{
            "name": item["full_name"],
            "url": item["html_url"],
            "description": item["description"],
            "stars": item["stargazers_count"],
            "forks": item["forks_count"],
            "updated_at": item["pushed_at"],
            "created_at": item["created_at"],
            "language": item["language"],
            "topics": item.get("topics", []),
            "size": item["size"],
            "open_issues": item["open_issues_count"]
        } for item in items]

        # 应用质量过滤
        quality_projects = self._filter_projects(projects)
        
        # 应用自定义过滤器
        custom_filters = [
            lambda p: p['description'] is not None and len(p['description']) > 30,  # 要求基本描述
            lambda p: len(p['topics']) >= 1,  # 要求至少有1个主题标签
            lambda p: p['forks'] >= p['stars'] * 0.05,  # fork数至少是star数的5%
        ]
        filtered_projects = self._apply_custom_filters(quality_projects, custom_filters)
        
        # 如果过滤后项目太少，放宽条件重试
        if len(filtered_projects) < 3:
            logger.warning("项目数量过少，放宽过滤条件重试...")
            custom_filters = [
                lambda p: p['description'] is not None,  # 只要有描述即可
                lambda p: p['stars'] >= self.config['min_stars'],  # 保持最低star要求
            ]
            filtered_projects = self._apply_custom_filters(quality_projects, custom_filters)
        
        # 确保语言多样性
        final_projects = self._ensure_diversity(filtered_projects)
        
        logger.info(f"🎯 筛选出{len(final_projects)}个高质量项目 | 平均质量分数: {mean([p['quality_score'] for p in final_projects]):.2f}")
        
        # 确保返回足够的项目
        return final_projects[:self.config['max_results']]

    def _ensure_diversity(self, projects: List[Dict]) -> List[Dict]:
        """
        确保结果的多样性，包括语言、主题和领域的多样性
        
        Args:
            projects (List[Dict]): 过滤后的项目列表
            
        Returns:
            List[Dict]: 具有多样性的项目列表
        """
        if not projects:
            return []
        
        # 按语言分组
        language_groups = {}
        for project in projects:
            lang = project['language'] or 'Unknown'
            if lang not in language_groups:
                language_groups[lang] = []
            language_groups[lang].append(project)
        
        # 计算每种语言应该选择的项目数量
        max_results = self.config['max_results']
        languages = list(language_groups.keys())
        
        # 如果语言种类少于目标数量，每种语言至少选一个
        if len(languages) <= max_results:
            projects_per_language = {lang: max(1, max_results // len(languages)) for lang in languages}
        else:
            # 如果语言种类多于目标数量，选择最流行的几种语言
            sorted_langs = sorted(languages, 
                                 key=lambda l: sum(p['stars'] for p in language_groups[l]), 
                                 reverse=True)
            projects_per_language = {lang: 0 for lang in languages}
            for lang in sorted_langs[:max_results]:
                projects_per_language[lang] = 1
        
        # 从每种语言中选择最优质的项目
        diverse_projects = []
        for lang, count in projects_per_language.items():
            if count > 0:
                # 按质量分数排序
                sorted_projects = sorted(language_groups[lang], 
                                        key=lambda p: p['quality_score'], 
                                        reverse=True)
                diverse_projects.extend(sorted_projects[:count])
        
        # 如果还有剩余名额，从所有项目中选择最优质的填充
        remaining_slots = max_results - len(diverse_projects)
        if remaining_slots > 0:
            # 排除已选项目
            selected_urls = {p['url'] for p in diverse_projects}
            remaining_projects = [p for p in projects if p['url'] not in selected_urls]
            # 按质量分数排序
            sorted_remaining = sorted(remaining_projects, 
                                     key=lambda p: p['quality_score'], 
                                     reverse=True)
            diverse_projects.extend(sorted_remaining[:remaining_slots])
        
        # 最终按质量分数排序
        return sorted(diverse_projects, key=lambda p: p['quality_score'], reverse=True)

