import sys
from ctypes import windll
import yaml
from datetime import datetime
import os
from github_crawler import GitHubCrawler
from ai_analyzer import AIAnalyzer
from report_generator import ReportGenerator
from email_sender import EmailSender
import logging
import logging.config
from logging import StreamHandler

class Utf8StreamHandler(StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        if sys.platform == "win32" and hasattr(self.stream, "reconfigure"):
            self.stream.reconfigure(encoding="utf-8")

def main():
    # 修复Windows控制台编码问题
    if sys.platform == 'win32':
        windll.kernel32.SetConsoleOutputCP(65001)
        os.environ["PYTHONIOENCODING"] = "utf-8"
    
    # 确保日志目录存在
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # 生成日志文件名（包含时间戳）
    log_file = os.path.join(log_dir, f'github_analyzer_{datetime.now().strftime("%Y%m%d")}.log')
    
    # 初始化日志
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,  # 防止禁用其他模块的日志器
        'formatters': {
            'colored': {
                'format': '%(asctime)s 🌟 [%(name)s] %(levelname)s ➤ %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {
            'console': {
                '()': Utf8StreamHandler,
                'formatter': 'colored',
                'level': 'INFO'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_file,
                'formatter': 'colored',
                'maxBytes': 10*1024*1024,  # 10MB
                'backupCount': 3,
                'encoding': 'utf-8',
                'mode': 'a',  # 明确指定追加模式
                'delay': False  # 立即打开文件
            }
        },
        'root': {
            'level': 'DEBUG',  # 降低日志级别以捕获更多信息
            'handlers': ['console', 'file']
        }
    })
    
    # 获取主程序日志器
    logger = logging.getLogger(__name__)
    
    # 验证日志配置
    logger.debug("日志系统初始化完成")
    logger.info(f"日志文件路径: {os.path.abspath(log_file)}")
    
    try:
        logger.info("🚀 启动GitHub智能分析系统 | 版本: 1.0")

        # 加载配置
        with open("config.yaml", encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 初始化组件
        crawler = GitHubCrawler(config['github'])
        analyzer = AIAnalyzer(config['openrouter'])
        report = ReportGenerator()
        emailer = EmailSender(config['email'])

        # 执行采集和分析
        projects = crawler.search_repositories()
        analyzed_projects = analyzer.analyze_projects(projects)
        for project in analyzed_projects:
            report.add_project(project, project['analysis'])

        # 生成报告文件
        os.makedirs('reports', exist_ok=True)
        filename = f"GitHub项目分析报告_{datetime.now().strftime('%Y%m%d%H%M')}.docx"
        full_path = os.path.abspath(os.path.join('reports', filename))
        report.save(full_path)
        logger.info(f"报告文件完整路径: {full_path}")

        # 发送邮件
        emailer.send_email(os.path.join('reports', filename))
    except Exception as e:
        logger.exception("💥 发生严重错误 | 详情:")
        raise

if __name__ == "__main__":
    try:
        main()
    finally:
        logging.shutdown()  # 确保日志缓冲区刷新 