import requests
import time
from typing import Dict, List
import logging
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
from asyncio import Semaphore

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self, config: dict):
        self.api_key = config['api_key']
        self.model = config['model']
        self.api_url = config['api_url']
        self.max_tokens = config['max_tokens']
        self.max_retries = 3
        self.max_workers = 1  # 降低并发数
        self.retry_delay = 1  # 初始重试延迟（秒）
        self.request_interval = 3  # 请求间隔（秒）
        logger.debug(f"初始化AI分析器 | 模型: {self.model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=20),  # 增加重试等待时间
        reraise=True
    )
    def _make_api_request(self, project: Dict) -> str:
        """
        发送单个API请求并处理响应
        
        Args:
            project (Dict): 项目信息
            
        Returns:
            str: AI分析结果
            
        Raises:
            requests.exceptions.RequestException: 当请求失败时
        """
        prompt = self._build_prompt(project)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        logger.debug(f"发送API请求 | 项目: {project['name']}")
        
        # 添加请求前的延迟
        time.sleep(self.request_interval)
        
        response = requests.post(self.api_url, json=payload, headers=headers)
        
        if response.status_code != 200:
            if "concurrency exceeded" in response.text:
                logger.warning(f"API并发限制，等待后重试 | 项目: {project['name']}")
                time.sleep(self.request_interval * 2)  # 遇到并发限制时增加等待时间
                raise RuntimeError("API并发限制")
            logger.error(f"API请求失败 | 状态码: {response.status_code} | 响应: {response.text}")
            response.raise_for_status()
        
        result = response.json()
        if 'choices' not in result:
            error_msg = f"API响应格式错误: {result}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 成功请求后的冷却时间
        time.sleep(self.request_interval)
        return result['choices'][0]['message'].get('content', '无分析内容')

    def _build_prompt(self, project: Dict) -> str:
        """
        构建项目分析提示词
        
        生成结构化的分析提示，引导AI生成适合Word文档展示的分析结果
        
        Args:
            project (Dict): 项目信息字典
            
        Returns:
            str: 格式化的提示词
        """
        return f"""请用中文分析以下GitHub项目：
        项目名称：{project['name']}
        项目地址：{project['url']}
        项目描述：{project.get('description', '无描述')}
        技术栈：{project.get('language', '未知')}
        Stars数：{project.get('stars', 0)}
        Fork数：{project.get('forks', 0)}
        主题标签：{', '.join(project.get('topics', []))}
        
        请按以下格式输出分析结果（不要使用Markdown格式，避免使用特殊符号）：
        
        【项目概述】
        用2-3句话简要概括项目的核心功能和主要特点。
        
        【主要功能】
        用简洁的语言列出3-4个核心功能点。
        
        【技术特点】
        重点描述项目的技术创新点和技术架构特色。
        
        【应用场景】
        具体列举2-3个典型的应用场景和目标用户群体。
        
        【解决痛点】
        分析该项目解决了哪些具体问题或行业痛点。
        
        【项目价值】
        总结项目的商业价值、技术价值和社会价值。
        
        注意事项：
        1. 使用清晰的段落划分
        2. 避免使用markdown标记和特殊符号
        3. 使用中文标点符号
        4. 保持专业性的同时确保可读性
        5. 适当使用分行，但不要过度分行
        """

    def _format_analysis(self, raw_analysis: str) -> str:
        """
        格式化分析结果
        
        处理AI返回的原始分析文本，使其更适合Word文档展示
        
        Args:
            raw_analysis (str): AI返回的原始分析文本
            
        Returns:
            str: 格式化后的分析文本
        """
        # 移除可能的Markdown标记
        cleaned = raw_analysis.replace('#', '').replace('*', '').replace('`', '')
        
        # 统一中文标点
        cleaned = cleaned.replace(':', '：').replace('!', '！').replace('?', '？')
        
        # 确保段落之间有适当的空行
        cleaned = cleaned.replace('\n\n\n', '\n\n').replace('\n\n\n\n', '\n\n')
        
        # 移除行首尾的空白字符
        cleaned = '\n'.join(line.strip() for line in cleaned.split('\n'))
        
        return cleaned

    def analyze_project(self, project: Dict) -> str:
        try:
            raw_analysis = self._make_api_request(project)
            return self._format_analysis(raw_analysis)
        except Exception as e:
            logger.error(f"项目分析失败 | 项目: {project['name']} | 错误: {str(e)}")
            return f"分析失败：{str(e)}"

    def analyze_projects(self, projects: List[Dict]) -> List[Dict]:
        """
        串行分析多个项目（避免并发问题）
        
        Args:
            projects (List[Dict]): 项目列表
            
        Returns:
            List[Dict]: 带有分析结果的项目列表
        """
        logger.info(f"🚀 开始分析 {len(projects)} 个项目")
        results = []
        
        total = len(projects)
        # 改用串行处理
        for index, project in enumerate(projects, 1):
            try:
                logger.info(f"🔍 开始分析 {index}/{total} | 项目：{project['name']}")
                analysis = self.analyze_project(project)
                project['analysis'] = analysis
                results.append(project)
                logger.info(f"✅ 完成分析 {index}/{total} | 项目：{project['name']}")
            except Exception as e:
                logger.error(f"❌ 分析失败 {index}/{total} | 项目：{project['name']} | 错误: {str(e)}")
                project['analysis'] = f"分析失败：{str(e)}"
                results.append(project)
            
            # 项目间添加间隔
            time.sleep(self.request_interval * 2)
        
        logger.info(f"🎉 分析完成 | 共处理 {total} 个项目")
        return results

