# 以即刻为例的社交媒体传播属性研究

## 项目简介
社交媒体已然是现代人生活中不可分割的一部分，尤其对于信息传播而言。AI 时代剧烈地放大了创作者的创作能力和影响力，因此越来越多的人开始非常有意识地运营自己的社交媒体，打造自己的”个人IP”，尝试第二条事业轨道。因此，对社交媒体传播属性的研究，理解其中的原理，对于运营自己的“个人IP”、网络运营和营销都十分有用。其次，自媒体不仅是个人影响力的发大器，也是现代网络生态中的重要构成，对其的研究也是对时代精神的一窥。

本研究选取的社交媒体是即刻，数据来源是最近一年多即刻镇小报中的 1880 篇用户动态文章。即刻镇小报是一个由即刻小编运营的，每天更新的产品，精选最近的用户动态文章，其本质是在分布式的信息传播网络中，官方塑造的非推荐式的中心化的传播渠道，其精选的文章能反应平台的价值取向和特质。以点带面，相信对即刻镇小报的研究，不仅能反应即刻的传播属性也能反应社交媒体的传播属性。

## 研究方法
本研究“**追求以假设为驱动、以事实为基础、符合逻辑的真知灼见**”。
- 假设来源于：
  1. 平时使用即刻的经验
  2. 通过与 AI 对话快速学习相关传播知识之后形成的直觉
  3. AI 做出的假设
- 数据来源于爬虫机器人对上述提到的即刻镇小报的爬取。
- 分析来源于利用编程和 AI 从多维度对文本进行分析和数据可视化，最后人工对数据和 AI 的分析报告进行归纳、整理

研究的流程为：
1. 确定假设结论，确定假设相关数据指标
2. 通过爬虫收集用户动态
3. 生成用户动态多维度指标
4. 分析用户动态多维度指标生成分析数据和表格
5. 基于分析数据，AI 和人工撰写分析报告从中提取趋势

反复迭代上述流程

## 项目成功的指标
1. 数据足够有代表性
    - 有足够的时间跨度：半年到一年
    - 数据样本量：足够多的用户动态，上千个
    - 类型平衡：对于不同话题都具有代表性
2. 采用多种分析方法
    - 对基本数据的统计（点赞量，作者粉丝数）
    - 用机器学习 AI 方法获取关于文本的分析：情感分析、主题提取、热点、写作风格
3. 研究结论清晰，有应用、创新价值
    - 总结哪些用户动态容易上即刻镇小报
    - 针对即刻创作者的具体内容优化建议和运营建议
    - 开发社交媒体创作者工具，辅助内容创作

## 研究报告
[总报告]()
[圈子报告]()
[作者影响力报告]()
[内容报告]()

## Repo 结构介绍
- `src`: 包含所有的代码
  - `core`：项目的关键代码
    - `crawler.py`：爬虫代码
    - `parser.py`：生成用户动态文章的多维度指标
    - `aiproxy.py`：对 AI 调用的封装
    - `data_models.py`：核心数据模型
  - `scripts`:
    - `analyzer.py`：基于用户动态文章的多维度指标进行系统分析
    - `jike_2024_top_100_posts.py`：获取即刻 2024 年点赞率前 100 的用户动态
  - `constants.py`: 项目全局配置常量

- `doc`: 文档
  - `analysis_report`：分析报告
  - `prompt`：使 AI 产生分析报告的，包换分析数据的 prompt

- `data`：数据
  - 从即刻上爬下来的原始数据
  - 对原始数据分析之后的包含多维度指标的数据
  - 备份数据

## 代码运行
下载项目和配置项目环境
```shell
# Step 1: download the project
git clone git@github.com:Dimen61/jike-analy.git

cd jike-analy

# Step 2: create your local virtual python environment
python -m venv .venv

# activate the virtual environment
source .venv/bin/activate

# install related python package
pip freeze > requirements.txt
```

运行脚本
```shell
cd src
# Step 1: crawl jike user posts. You need to configure your JIKE_ACCESS_TOKEN in constants.py
python3 -m core.crawler

# Step 2: parse the downloaded posts and generate different dimension measurement values
python3 -m core.parser

# Step 3: analyze the different measurements of posts (comment unnecessary code)
python3 -m scripts.analyzer
```
