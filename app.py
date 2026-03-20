"""
微信公众号文章生成工作流 - Streamlit 版本
基于多智能体协作的 AI 文章自动生成系统
"""
import streamlit as st
import httpx
import json
import re
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ============== 配置 ==============
DEER_API_BASE_URL = os.getenv("DEER_API_BASE_URL", "https://api.deerapi.com")
DEFAULT_API_KEY = os.getenv("DEER_API_KEY", "")

# AI 模型选项
AI_MODELS = [
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash（推荐）", "provider": "Google"},
    {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite", "provider": "Google"},
    {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro Preview", "provider": "Google"},
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    {"id": "gpt-5-nano", "name": "GPT-5 Nano", "provider": "OpenAI"},
]

# 默认编辑智能体 Prompt
DEFAULT_EDITOR_PROMPT = """你是一位资深的微信公众号内容创作者，擅长撰写高质量、有深度、适合微信公众号发布的文章。

你的任务是根据提供的内容素材，创作一篇结构清晰、内容丰富、语言流畅的微信公众号文章。

写作要求：
1. 标题要吸引人，能引发读者点击和阅读的兴趣
2. 结构清晰，适当使用小标题分隔内容
3. 语言流畅，符合微信公众号的阅读习惯
4. 内容要丰富、有价值，能给读者带来收获
5. 适当使用表情符号增加趣味性（但不要过度）
6. 文章长度适中（800-2000字）
7. 添加适当的标签（3-5个）用于分类

输出格式：
- 标题：[文章标题]
- 正文：[文章内容]
- 标签：[标签1, 标签2, 标签3]
- 风格：[文章风格描述]"""

# 默认审稿人智能体 Prompt
DEFAULT_REVIEWER_PROMPT = """你是一位资深的文章审稿人，负责审核文章的质量并提供改进建议。

你的任务是根据原始素材和生成的文章，评估文章的质量并给出评分和建议。

评估维度：
1. 准确性（accuracy_score）：文章内容是否准确，是否忠实于原始素材
2. 完整性（completeness_score）：文章是否涵盖了原始素材的主要内容
3. 可读性（readability_score）：文章是否易于阅读，语言是否流畅

评分标准：
- 每项维度评分 1-10 分
- 8分及以上为优秀
- 6-8分为良好
- 6分以下需要改进

当 overall_score >= 8 时，说明文章质量合格。
当 overall_score < 8 时，需要给出具体的修改建议。"""


# ============== 工具函数 ==============
def extract_content_from_url(url: str) -> Dict[str, Any]:
    """从URL提取内容（使用 requests + beautifulsoup4）"""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # 设置编码
        response.encoding = response.apparent_encoding or 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # 提取标题
        title = ""
        if soup.title:
            title = soup.title.string
        else:
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)

        # 移除脚本和样式
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        # 获取文本内容
        text = soup.get_text(separator='\n', strip=True)

        # 清理空行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)

        # 移除过短的行（通常是噪声）
        lines = [line for line in text.split('\n') if len(line) > 20]
        text = '\n'.join(lines)

        if not text or len(text) < 100:
            return {
                "success": False,
                "error": "提取的内容太少，请尝试其他链接或手动粘贴内容"
            }

        return {
            "success": True,
            "title": title.strip() if title else "未获取到标题",
            "content": text,
            "url": url
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"网络请求失败: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"内容提取失败: {str(e)}"
        }


async def call_ai_api(
    messages: List[Dict],
    api_key: str,
    model: str = "gemini-2.5-flash"
) -> str:
    """调用 AI API"""
    url = f"{DEER_API_BASE_URL}/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 8192
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def generate_article(content: str, api_key: str, model: str, custom_prompt: str = None) -> Dict[str, Any]:
    """生成文章"""
    import asyncio

    system_prompt = custom_prompt or DEFAULT_EDITOR_PROMPT

    user_prompt = f"""请根据以下内容素材，创作一篇微信公众号文章：

## 内容素材
{content}

## 要求
1. 标题要吸引人
2. 结构清晰，使用小标题
3. 内容丰富有价值
4. 语言流畅适合公众号阅读
5. 适当使用表情符号
6. 长度适中（800-2000字）
7. 结尾添加标签

请按以下格式输出：
标题：[文章标题]
正文：[文章内容]
标签：[标签1, 标签2, 标签3]"""

    try:
        result = asyncio.run(call_ai_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], api_key, model))

        return {"success": True, "content": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def review_article(
    original_content: str,
    generated_article: str,
    api_key: str,
    model: str,
    custom_prompt: str = None
) -> Dict[str, Any]:
    """审稿审查"""
    import asyncio

    system_prompt = custom_prompt or DEFAULT_REVIEWER_PROMPT

    user_prompt = f"""请审核以下文章的质量：

## 原始素材
{original_content[:2000]}...

## 生成的文章
{generated_article}

## 任务
1. 评估文章的准确性、完整性和可读性（每项1-10分）
2. 给出总体评分和建议
3. 如果评分<8分，请提供具体的修改建议

请按以下JSON格式输出：
{{
    "accuracy_score": 评分,
    "completeness_score": 评分,
    "readability_score": 评分,
    "overall_score": 总分,
    "suggestions": ["建议1", "建议2"],
    "strengths": ["优点1", "优点2"]
}}"""

    try:
        result = asyncio.run(call_ai_api([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], api_key, model))

        # 尝试解析 JSON
        try:
            review = json.loads(result)
            return {"success": True, "review": review}
        except:
            # 如果不是 JSON，尝试提取
            return {"success": True, "review": result, "raw": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def parse_article_content(text: str) -> Dict[str, Any]:
    """解析文章内容"""
    result = {
        "title": "",
        "body": "",
        "tags": []
    }

    # 提取标题
    title_match = re.search(r'标题[：:]\s*(.+?)(?:\n|$)', text)
    if title_match:
        result["title"] = title_match.group(1).strip()
    else:
        # 尝试提取 Markdown 标题
        title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
        if title_match:
            result["title"] = title_match.group(1).strip()

    # 提取标签
    tags_match = re.search(r'标签[：:]\s*\[?(.*?)\]?(?:\n|$)', text)
    if tags_match:
        tags_text = tags_match.group(1)
        result["tags"] = [t.strip() for t in re.split(r'[,，]', tags_text) if t.strip()]

    # 提取正文（移除标题和标签部分）
    body = text
    body = re.sub(r'^标题[：:].+?(?:\n|$)', '', body, flags=re.MULTILINE)
    body = re.sub(r'^正文[：:]\s*', '', body)
    body = re.sub(r'^标签[：:].+?(?:\n|$)', '', body, flags=re.MULTILINE)
    body = re.sub(r'^#\s+.+?(?:\n|$)', '', body, flags=re.MULTILINE)
    body = re.sub(r'\n{3,}', '\n\n', body)
    result["body"] = body.strip()

    return result


# ============== Streamlit UI ==============
def main():
    st.set_page_config(
        page_title="微信公众号文章生成工作流",
        page_icon="📝",
        layout="wide"
    )

    # 标题
    st.title("📝 微信公众号文章生成工作流")
    st.markdown("基于 AI 智能体协作的自动化文章生成系统")

    # 侧边栏设置
    with st.sidebar:
        st.header("⚙️ 设置")

        # API 密钥
        api_key = st.text_input(
            "DeerAPI 密钥",
            value=DEFAULT_API_KEY or "",
            type="password",
            help="从 https://api.deerapi.com 获取"
        )

        if not api_key:
            st.warning("⚠️ 请输入 DeerAPI 密钥")

        # 模型选择
        model_options = [m["name"] for m in AI_MODELS]
        selected_model_name = st.selectbox("AI 模型", model_options)
        selected_model = next(m["id"] for m in AI_MODELS if m["name"] == selected_model_name)

        st.divider()

        # 自定义 Prompt 设置
        st.header("🤖 智能体设置")

        with st.expander("编辑智能体 Prompt"):
            custom_editor_prompt = st.text_area(
                "自定义编辑 Prompt",
                value=DEFAULT_EDITOR_PROMPT,
                height=200,
                help="修改 AI 编辑智能体的系统提示词"
            )

        with st.expander("审稿智能体 Prompt"):
            custom_reviewer_prompt = st.text_area(
                "自定义审稿 Prompt",
                value=DEFAULT_REVIEWER_PROMPT,
                height=200,
                help="修改 AI 审稿智能体的系统提示词"
            )

    # 主内容区
    tab1, tab2, tab3 = st.tabs(["📥 输入", "📊 工作流", "📄 结果"])

    with tab1:
        st.header("输入内容")

        col1, col2 = st.columns([2, 1])

        with col1:
            source_url = st.text_input(
                "内容链接",
                placeholder="输入文章链接或播客链接...",
                help="支持网页文章和播客音频链接"
            )

            source_type = st.radio(
                "内容类型",
                ["🌐 网页文章", "🎙️ 播客音频"],
                horizontal=True
            )

            content_type = "web_article" if "网页" in source_type else "podcast"

            crawl_button = st.button("🔍 提取内容", type="primary")

            if "crawled_content" not in st.session_state:
                st.session_state.crawled_content = None

        with col2:
            st.markdown("### 快速开始")
            st.markdown("""
            1. 输入内容链接
            2. 点击"提取内容"
            3. 查看提取的内容
            4. 进入工作流生成文章
            """)

        if crawl_button and source_url:
            if not api_key:
                st.error("请先输入 DeerAPI 密钥")
            else:
                with st.spinner("正在提取内容..."):
                    result = extract_content_from_url(source_url)

                    if result["success"]:
                        st.session_state.crawled_content = result
                        st.success("✅ 内容提取成功！")
                    else:
                        st.error(f"❌ 提取失败: {result.get('error', '未知错误')}")

        # 显示提取的内容
        if st.session_state.crawled_content:
            st.divider()
            st.subheader("📋 提取的内容预览")

            content = st.session_state.crawled_content

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**标题：** {content.get('title', '无')}")
            with col2:
                st.markdown(f"**来源：** {content.get('url', '无')}")

            st.text_area(
                "内容",
                value=content.get("content", ""),
                height=300,
                disabled=True,
                key="content_preview"
            )

            word_count = len(content.get("content", ""))
            st.caption(f"字数：约 {word_count} 字")

    with tab2:
        st.header("🚀 工作流执行")

        if not st.session_state.crawled_content:
            st.info("👆 请先在「输入」标签页提取内容")
        else:
            if not api_key:
                st.error("请先输入 DeerAPI 密钥")
            else:
                if st.button("▶️ 开始生成文章", type="primary", use_container_width=True):
                    # 初始化进度
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        # 步骤1：编辑生成
                        status_text.text("📝 步骤 1/3：AI 编辑正在生成文章...")
                        progress_bar.progress(33)

                        content = st.session_state.crawled_content["content"]
                        generate_result = generate_article(
                            content, api_key, selected_model, custom_editor_prompt
                        )

                        if not generate_result["success"]:
                            st.error(f"生成失败: {generate_result['error']}")
                            st.stop()

                        generated_article = generate_result["content"]
                        st.session_state.generated_article = generated_article

                        # 步骤2：审稿
                        status_text.text("🔍 步骤 2/3：AI 审稿人正在审核...")
                        progress_bar.progress(66)

                        review_result = review_article(
                            content, generated_article, api_key, selected_model, custom_reviewer_prompt
                        )

                        if not review_result["success"]:
                            st.error(f"审稿失败: {review_result['error']}")
                            st.stop()

                        st.session_state.review_result = review_result

                        # 步骤3：完成
                        status_text.text("✅ 步骤 3/3：完成！")
                        progress_bar.progress(100)

                        st.success("🎉 文章生成完成！请查看「结果」标签页")

                    except Exception as e:
                        st.error(f"执行出错: {str(e)}")

    with tab3:
        st.header("📄 生成结果")

        if not st.session_state.get("generated_article"):
            st.info("👆 请先执行工作流生成文章")
        else:
            # 解析文章
            article_data = parse_article_content(st.session_state.generated_article)

            # 显示文章
            st.subheader(f"📌 {article_data['title'] or '生成的标题'}")

            # 标签
            if article_data["tags"]:
                st.markdown("**标签：** " + " ".join([f"`{t}`" for t in article_data["tags"]]))

            # 原文/编辑后
            with st.expander("📃 查看 AI 生成原文", expanded=False):
                st.markdown(st.session_state.generated_article)

            st.divider()

            # Markdown 输出
            st.subheader("📋 Markdown 格式")

            md_content = f"""# {article_data['title']}

{article_data['body']}

---

**标签：** {', '.join(article_data['tags']) if article_data['tags'] else '无'}
"""

            st.text_area(
                "复制以下内容",
                value=md_content,
                height=400,
                key="md_output"
            )

            col1, col2 = st.columns(2)
            with col1:
                st.button("📋 复制到剪贴板", on_click=lambda: st.clipboard(md_content))

            # 审稿结果
            if st.session_state.get("review_result"):
                st.divider()
                st.subheader("🔍 审稿结果")

                review = st.session_state.review_result.get("review", {})

                if isinstance(review, dict):
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("准确性", review.get("accuracy_score", "-"), delta_color="off")
                    with col2:
                        st.metric("完整性", review.get("completeness_score", "-"), delta_color="off")
                    with col3:
                        st.metric("可读性", review.get("readability_score", "-"), delta_color="off")
                    with col4:
                        score = review.get("overall_score", 0)
                        st.metric("总分", score, delta_color="normal" if score >= 8 else "inverse")

                    if review.get("strengths"):
                        st.markdown("**✨ 优点：**")
                        for s in review["strengths"]:
                            st.markdown(f"- {s}")

                    if review.get("suggestions"):
                        st.markdown("**💡 建议：**")
                        for s in review["suggestions"]:
                            st.markdown(f"- {s}")
                else:
                    st.markdown(review)


if __name__ == "__main__":
    main()
