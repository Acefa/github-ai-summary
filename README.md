# 🤖 GitHub AI 项目分析器

一个基于AI的自动化工具，用于发现、分析和总结GitHub上的高质量AI相关项目。系统会自动生成详细的分析报告并通过邮件发送。

## 🌟 主要功能

- **智能项目发现**：自动搜索并筛选优质GitHub项目
- **AI深度分析**：使用AI模型分析项目特点和价值
- **报告生成**：生成结构化的Word格式分析报告
- **邮件通知**：自动发送分析报告到指定邮箱

## 🛠️ 技术架构

- **GitHub API**：项目数据获取
- **DeepSeek AI**：智能分析引擎
- **Python-docx**：Word文档生成
- **SMTP**：邮件发送服务

## 📋 系统要求

- Python 3.8+
- Windows/Linux/MacOS
- 稳定的网络连接

## 🚀 快速开始

1. **克隆项目**
```bash
git clone [repository-url]
cd github-ai-summary
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置文件设置**
- 复制`config.yaml.template`为`config.yaml`
- 修改配置参数：
  - GitHub搜索条件
  - AI API密钥
  - 邮件服务设置

## ⚙️ 配置说明

### GitHub配置
```yaml
github:
search_keywords: "AI" # 搜索关键词
min_stars: 500 # 最低star数要求
max_results: 15 # 分析项目数量
language: "" # 编程语言筛选
search_criteria:
min_forks: 100 # 最低fork数
update_within_days: 3 # 最近更新时间
```

### AI分析配置
```yaml
openrouter:
model: "deepseek-r1"
api_url: "https://api.lkeap.cloud.tencent.com/v1/chat/completions"
max_tokens: 2000
```

### 邮件配置
```yaml
email:
smtp_server: "smtp.qq.com"
smtp_port: 465
sender_email: "your-email@qq.com"
recipients: ["recipient@example.com"]
subject: "GitHub项目分析报告"
```

## 📁 项目结构
```
github-ai-summary/
├── main.py # 程序入口
├── github_crawler.py # GitHub项目爬虫
├── ai_analyzer.py # AI分析模块
├── report_generator.py # Word报告生成器
├── email_sender.py # 邮件发送模块
├── config.yaml # 配置文件
├── logging_config.yaml # 日志配置
├── requirements.txt # 项目依赖
├── logs/ # 日志目录
└── reports/ # 分析报告目录
```

## 📝 使用说明

1. **运行分析器**
```bash
python main.py
```

2. **查看输出**
- 分析报告：`reports/GitHub项目分析报告_[时间戳].docx`
- 运行日志：`logs/github_analyzer_[日期].log`

## 🔍 分析维度

- 项目概述
- 主要功能
- 技术特点
- 应用场景
- 解决痛点
- 项目价值

## ⚠️ 注意事项

1. **API限制**
   - 请注意GitHub API的使用限制
   - 合理设置项目分析数量

2. **配置安全**
   - 保护好API密钥
   - 不要提交敏感配置到代码库

3. **运行环境**
   - 确保稳定的网络连接
   - 推荐使用虚拟环境

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 📄 许可证

MIT License

## 🔄 更新日志

### v1.0.0 (2025-02-14)
- 初始版本发布
- 实现基础功能：项目搜索、AI分析、报告生成、邮件发送



