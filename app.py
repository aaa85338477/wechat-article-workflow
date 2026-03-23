"""
微信公众号文章生成工作流 - 多智能体版本
基于多智能体协作的 AI 文章自动生成系统
架构：输入 → 素材提取 → 多智能体协同博弈 → 导出分发
"""
import streamlit as st
import httpx
import json
import re
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ============== 配置 ==============
DEER_API_BASE_URL = os.getenv("DEER_API_BASE_URL", "https://api.deerapi.com")
DEFAULT_API_KEY = os.getenv("DEER_API_KEY", "")
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")

# AI 模型选项
AI_MODELS = [
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash（推荐）", "provider": "Google"},
    {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite", "provider": "Google"},
    {"id": "gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro Preview", "provider": "Google"},
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    {"id": "gpt-5-nano", "name": "GPT-5 Nano", "provider": "OpenAI"},
]

# 默认提示词配置
DEFAULT_PROMPTS = {
    "editor": """你是一位资深的微信公众号内容创作者，擅长撰写高质量、有深度、适合微信公众号发布的文章。

你的任务是根据提供的内容素材，创作一篇结构清晰、内容丰富、语言流畅的微信公众号文章。

写作要求：
1. 标题要吸引人，能引发读者点击和阅读的兴趣
2. 结构清晰，适当使用小标题分隔内容
3. 语言流畅，符合微信公众号的阅读习惯
4. 内容要丰富、有价值，能给读者带来收获
5. 适当使用表情符号增加趣味性（但不要过度）
6. 文章长度适中（800-2000字）
7. 添加适当的标签（3-5个）用于分类

重要：必须忠实于原始素材，不得虚构内容。""",

    "reviewer": """你是一位资深的文章审稿人，负责审核文章的质量并提供改进建议。你的审稿风格严格、公正，被称为"毒舌主编"。

你的任务是根据原始素材和生成的文章，评估文章的质量并给出评分和建议。

评估维度：
1. 准确性（accuracy_score）：文章内容是否准确，是否忠实于原始素材，有无虚构内容
2. 完整性（completeness_score）：文章是否涵盖了原始素材的主要内容
3. 可读性（readability_score）：文章是否易于阅读，语言是否流畅
4. 原创性（originality_score）：文章是否有独特观点和价值

评分标准：
- 每项维度评分 1-10 分
- 总分 = 各项平均分
- 8分及以上为优秀，可直接发布
- 6-8分为良好，小修小改即可
- 6分以下需要大幅修改

当 overall_score >= 8 时，说明文章质量合格，可以定稿。
当 overall_score < 8 时，必须给出具体的修改建议。""",

    "reviser": """你是一位资深的内容编辑，负责根据审稿意见对文章进行修改润色。

你的任务：
1. 仔细阅读审稿人给出的修改意见
2. 对照原始素材，确保修改后的内容忠实于素材
3. 逐条落实修改建议，提升文章质量
4. 保持原文的优点和风格

重要：
- 不得删除素材中的重要信息
- 不得添加素材中没有的内容
- 修改要有针对性，不是大段重写"""
}

# prompts.json 文件路径
PROMPTS_FILE = "prompts.json"


def load_prompts() -> Dict[str, str]:
    """从文件加载提示词配置"""
    if os.path.exists(PROMPTS_FILE):
        try:
            with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_PROMPTS.copy()


def save_prompts(prompts: Dict[str, str]) -> bool:
    """保存提示词配置到文件"""
    try:
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(prompts, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False


# ============== 素材提取 ==============
def extract_web_content(url: str) -> Dict[str, Any]:
    """从网页URL提取内容"""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
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

        # 移除噪声标签
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()

        # 获取文本内容
        text = soup.get_text(separator='\n', strip=True)

        # 清理
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        lines = [line for line in lines if len(line) > 15]
        text = '\n'.join(lines)

        if not text or len(text) < 100:
            return {"success": False, "error": "提取的内容太少"}

        return {
            "success": True,
            "type": "web",
            "title": title.strip() if title else "未获取到标题",
            "content": text,
            "url": url
        }
    except Exception as e:
        return {"success": False, "error": f"网页提取失败: {str(e)}"}


def extract_youtube_content(url: str) -> Dict[str, Any]:
    """从YouTube视频提取字幕"""
    try:
        import requests

        # 提取视频ID
        video_id = None
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break

        if not video_id:
            return {"success": False, "error": "无法解析YouTube链接"}

        # 方法1：尝试使用 yt-dlp 或 youtube-transcript-api
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['zh-Hans', 'zh-Hant', 'en'])
            text = ' '.join([item['text'] for item in transcript])
            return {
                "success": True,
                "type": "youtube",
                "title": f"YouTube视频内容",
                "content": text,
                "url": url,
                "video_id": video_id
            }
        except:
            pass

        # 方法2：使用 Jina AI 提取
        try:
            jina_url = f"https://r.jina.ai/{url}"
            headers = {"Accept": "application/json"}
            response = requests.get(jina_url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "type": "youtube",
                    "title": data.get("title", "YouTube视频内容"),
                    "content": data.get("content", ""),
                    "url": url,
                    "video_id": video_id
                }
        except:
            pass

        return {"success": False, "error": "无法获取字幕，请尝试其他链接"}

    except Exception as e:
        return {"success": False, "error": f"YouTube提取失败: {str(e)}"}


def extract_content(url: str) -> Dict[str, Any]:
    """统一的内容提取入口"""
    url_lower = url.lower()

    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return extract_youtube_content(url)
    else:
        return extract_web_content(url)


# ============== AI 调用 ==============
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

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def generate_draft(content: str, api_key: str, model: str, editor_prompt: str) -> Dict[str, Any]:
    """Step 2: 编辑生成初稿"""
    import asyncio

    user_prompt = f"""请根据以下原始素材，创作一篇微信公众号文章：

## 原始素材
{content}

## 要求
1. 标题要吸引人，包含关键词
2. 结构清晰，使用小标题分隔章节
3. 内容丰富有价值
4. 语言流畅，适合公众号阅读
5. 适当使用表情符号增加趣味性
6. 长度适中（800-2000字）
7. 结尾添加标签

请直接输出文章内容，不需要额外说明。"""

    try:
        result = asyncio.run(call_ai_api([
            {"role": "system", "content": editor_prompt},
            {"role": "user", "content": user_prompt}
        ], api_key, model))

        return {"success": True, "content": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def review_draft(
    original_content: str,
    draft: str,
    api_key: str,
    model: str,
    reviewer_prompt: str
) -> Dict[str, Any]:
    """Step 3: 审稿人审查（事实核查）"""
    import asyncio

    user_prompt = f"""## 原始素材（唯一的事实基准）
请严格对照此素材检查文章的准确性：
---
{original_content[:3000]}
---

## 待审稿的文章
---
{draft}
---

## 审稿任务
1. **事实核查**：文章内容是否忠实于原始素材？是否有虚构或夸大？
2. **完整性检查**：文章是否涵盖了素材的主要观点？
3. **可读性评估**：语言是否流畅？结构是否清晰？
4. **给出评分**：准确性、完整性、可读性各1-10分

## 输出格式（必须严格按JSON格式）
{{
    "accuracy_score": 1-10,
    "completeness_score": 1-10,
    "readability_score": 1-10,
    "overall_score": 平均分,
    "accuracy_issues": ["具体的事实错误列表"],
    "suggestions": ["修改建议列表"],
    "strengths": ["文章优点列表"],
    "can_publish": true/false
}}"""

    try:
        result = asyncio.run(call_ai_api([
            {"role": "system", "content": reviewer_prompt},
            {"role": "user", "content": user_prompt}
        ], api_key, model))

        # 解析 JSON
        try:
            review = json.loads(result)
            return {"success": True, "review": review}
        except:
            return {"success": True, "review": result, "raw": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def revise_draft(
    original_content: str,
    draft: str,
    review: Dict,
    api_key: str,
    model: str,
    reviser_prompt: str
) -> Dict[str, Any]:
    """Step 4: 根据审稿意见修改文章"""
    import asyncio

    suggestions_text = "\n".join([f"- {s}" for s in review.get("suggestions", [])])

    user_prompt = f"""## 原始素材（必须忠实于素材，不得添加虚构内容）
---
{original_content[:3000]}
---

## 原文章
---
{draft}
---

## 审稿修改意见
{suggestions_text}

## 修改任务
请根据上述修改意见，对文章进行修改润色。
- 逐条落实修改建议
- 不得添加素材中没有的内容
- 不得删除素材中的重要信息
- 保持原文的优点和风格

请直接输出修改后的完整文章。"""

    try:
        result = asyncio.run(call_ai_api([
            {"role": "system", "content": reviser_prompt},
            {"role": "user", "content": user_prompt}
        ], api_key, model))

        return {"success": True, "content": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============== 导出功能 ==============
def export_to_docx(content: str, title: str) -> bytes:
    """导出为 Word 文档"""
    try:
        from docx import Document
        from docx.shared import Pt
        from io import BytesIO

        doc = Document()
        doc.add_heading(title, 0)

        # 添加内容（处理 Markdown 格式）
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith('# '):
                doc.add_heading(line[2:], level=1)
            elif line.startswith('## '):
                doc.add_heading(line[3:], level=2)
            elif line.startswith('### '):
                doc.add_heading(line[4:], level=3)
            else:
                # 处理 Markdown 强调
                line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
                line = re.sub(r'\*(.+?)\*', r'\1', line)
                doc.add_paragraph(line)

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
    except ImportError:
        return None


def send_to_feishu(content: str, webhook_url: str) -> Dict[str, Any]:
    """发送内容到飞书群"""
    try:
        import requests

        payload = {
            "msg_type": "text",
            "content": {
                "text": f"📝 微信公众号文章内容：\n\n{content[:4000]}"
            }
        }

        response = requests.post(webhook_url, json=payload, timeout=10)
        result = response.json()

        if result.get("code") == 0:
            return {"success": True}
        else:
            return {"success": False, "error": result.get("msg", "发送失败")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def parse_article(text: str) -> Dict[str, Any]:
    """解析文章内容"""
    result = {"title": "", "body": "", "tags": []}

    # 提取标题
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    if title_match:
        result["title"] = title_match.group(1).strip()

    title_match = re.search(r'^标题[：:]\s*(.+?)(?:\n|$)', text, re.MULTILINE)
    if title_match and not result["title"]:
        result["title"] = title_match.group(1).strip()

    # 提取标签
    tags_match = re.search(r'标签[：:]\s*\[?(.*?)\]?(?:\n|$)', text, re.MULTILINE)
    if tags_match:
        tags_text = tags_match.group(1)
        result["tags"] = [t.strip() for t in re.split(r'[,，]', tags_text) if t.strip()]

    # 提取正文
    body = re.sub(r'^#\s+.+?(?:\n|$)', '', text, flags=re.MULTILINE)
    body = re.sub(r'^标题[：:].+?(?:\n|$)', '', body, flags=re.MULTILINE)
    body = re.sub(r'^正文[：:]\s*', '', body)
    body = re.sub(r'^标签[：:].+?(?:\n|$)', '', body, flags=re.MULTILINE)
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

    # 加载提示词配置
    prompts = load_prompts()

    # 标题
    st.title("📝 微信公众号文章生成工作流")
    st.markdown("**多智能体协作：编辑 → 审稿（事实核查）→ 修改 → 定稿**")

    # ============== 侧边栏 ==============
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

        # 提示词管理
        st.header("🤖 提示词管理")

        # 加载/保存按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存", use_container_width=True):
                prompts_to_save = {
                    "editor": st.session_state.get("editor_prompt_input", prompts["editor"]),
                    "reviewer": st.session_state.get("reviewer_prompt_input", prompts["reviewer"]),
                    "reviser": st.session_state.get("reviser_prompt_input", prompts.get("reviser", DEFAULT_PROMPTS["reviser"]))
                }
                if save_prompts(prompts_to_save):
                    st.success("✅ 已保存到 prompts.json")
                else:
                    st.error("❌ 保存失败")

        with col2:
            if st.button("🔄 重置", use_container_width=True):
                prompts = DEFAULT_PROMPTS.copy()
                save_prompts(prompts)
                st.rerun()

        # 提示词编辑
        with st.expander("✏️ 编辑智能体提示词", expanded=False):
            editor_prompt = st.text_area(
                "编辑 Prompt",
                value=prompts.get("editor", DEFAULT_PROMPTS["editor"]),
                height=150,
                key="editor_prompt_input"
            )

        with st.expander("🔍 审稿智能体提示词", expanded=False):
            reviewer_prompt = st.text_area(
                "审稿 Prompt",
                value=prompts.get("reviewer", DEFAULT_PROMPTS["reviewer"]),
                height=150,
                key="reviewer_prompt_input"
            )

        with st.expander("✂️ 修改智能体提示词", expanded=False):
            reviser_prompt = st.text_area(
                "修改 Prompt",
                value=prompts.get("reviser", DEFAULT_PROMPTS["reviser"]),
                height=150,
                key="reviser_prompt_input"
            )

        st.divider()

        # 导出设置
        st.header("📤 导出设置")

        feishu_webhook = st.text_input(
            "飞书 Webhook URL",
            value=FEISHU_WEBHOOK_URL or "",
            placeholder="可选，发送文章到飞书群",
            help="在飞书群设置中添加自定义机器人获取"
        )

    # ============== 主内容区 ==============
    tab1, tab2, tab3, tab4 = st.tabs(["📥 输入", "🕷️ 素材", "⚙️ 工作流", "📄 结果"])

    # ---------- Tab 1: 输入 ----------
    with tab1:
        st.header("📥 输入内容")

        col1, col2 = st.columns([3, 1])

        with col1:
            source_url = st.text_input(
                "🔗 内容链接",
                placeholder="输入文章链接、YouTube视频链接...",
                help="支持网页文章、YouTube视频"
            )

            source_type = st.radio(
                "📌 内容类型",
                ["🌐 网页文章", "📺 YouTube视频", "📝 手动输入"],
                horizontal=True,
                help="选择内容来源类型"
            )

            content_type = "web" if "网页" in source_type else ("youtube" if "YouTube" in source_type else "manual")

        with col2:
            st.markdown("### 💡 提示")
            st.markdown("""
            - 支持常见新闻网站
            - 支持 YouTube 视频（自动提取字幕）
            - 也可以手动粘贴内容
            """)

        if content_type == "manual":
            manual_content = st.text_area(
                "📝 手动输入内容",
                height=200,
                placeholder="在此粘贴文章内容..."
            )
            if manual_content:
                st.session_state.manual_content = manual_content
        else:
            if st.button("🔍 提取内容", type="primary"):
                if not source_url:
                    st.error("请输入链接地址")
                elif not api_key:
                    st.error("请先输入 DeerAPI 密钥")
                else:
                    with st.spinner("正在提取内容..."):
                        result = extract_content(source_url)

                        if result["success"]:
                            st.session_state.extracted_content = result
                            st.success(f"✅ {result['type'].upper()} 内容提取成功！")
                        else:
                            st.error(f"❌ 提取失败: {result.get('error', '未知错误')}")

    # ---------- Tab 2: 素材预览 ----------
    with tab2:
        st.header("🕷️ 素材池")

        content_to_show = None

        if "extracted_content" in st.session_state:
            content_to_show = st.session_state.extracted_content
        elif "manual_content" in st.session_state:
            content_to_show = {
                "success": True,
                "type": "manual",
                "title": "手动输入内容",
                "content": st.session_state.manual_content,
                "url": ""
            }

        if content_to_show:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**📌 标题：** {content_to_show.get('title', '无')}")
            with col2:
                st.markdown(f"**📎 类型：** `{content_to_show.get('type', 'unknown')}`")

            if content_to_show.get('url'):
                st.markdown(f"**🔗 来源：** {content_to_show['url']}")

            st.divider()

            word_count = len(content_to_show.get("content", ""))
            st.markdown(f"**📊 字数：** 约 {word_count} 字")

            st.text_area(
                "素材内容",
                value=content_to_show.get("content", ""),
                height=400,
                disabled=True
            )
        else:
            st.info("👆 请先在「输入」标签页提取或输入内容")

    # ---------- Tab 3: 工作流 ----------
    with tab3:
        st.header("⚙️ 多智能体工作流")

        if not content_to_show:
            st.info("👆 请先在「输入」标签页提取内容")
        else:
            if not api_key:
                st.error("⚠️ 请先输入 DeerAPI 密钥")
            else:
                st.markdown("""
                ### 工作流程
                ```
                素材 → Step 2: 编辑生成初稿 → Step 3: 审稿人审查 → Step 4: 修改润色 → 定稿
                ```
                """)

                if st.button("▶️ 启动多智能体工作流", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    try:
                        original_content = content_to_show["content"]

                        # Step 2: 生成初稿
                        status_text.text("📝 Step 2/4：编辑智能体正在生成初稿...")
                        progress_bar.progress(20)
                        st.info("正在调用编辑智能体...")

                        draft_result = generate_draft(
                            original_content, api_key, selected_model,
                            editor_prompt if 'editor_prompt' in dir() else prompts["editor"]
                        )

                        if not draft_result["success"]:
                            st.error(f"❌ 初稿生成失败: {draft_result['error']}")
                            st.stop()

                        draft = draft_result["content"]
                        st.session_state.draft = draft
                        st.success("✅ 初稿生成完成")

                        with st.expander("📄 查看初稿", expanded=False):
                            st.markdown(draft)

                        # Step 3: 审稿审查
                        status_text.text("🔍 Step 3/4：审稿人正在审查（事实核查）...")
                        progress_bar.progress(50)
                        st.info("审稿人正在核查事实...")

                        review_result = review_draft(
                            original_content, draft, api_key, selected_model,
                            reviewer_prompt if 'reviewer_prompt' in dir() else prompts["reviewer"]
                        )

                        if not review_result["success"]:
                            st.error(f"❌ 审稿失败: {review_result['error']}")
                            st.stop()

                        review = review_result.get("review", {})
                        if isinstance(review, str):
                            st.error("审稿结果解析失败")
                            st.stop()

                        st.session_state.review = review
                        st.success(f"✅ 审稿完成，总分：{review.get('overall_score', '?')}/10")

                        # 显示审稿结果
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("准确性", review.get("accuracy_score", "-"))
                        with col2:
                            st.metric("完整性", review.get("completeness_score", "-"))
                        with col3:
                            st.metric("可读性", review.get("readability_score", "-"))
                        with col4:
                            score = review.get("overall_score", 0)
                            st.metric("总分", score,
                                     delta_color="normal" if score >= 8 else "inverse")

                        if review.get("suggestions"):
                            st.markdown("**💡 修改建议：**")
                            for s in review["suggestions"]:
                                st.markdown(f"- {s}")

                        if review.get("strengths"):
                            st.markdown("**✨ 优点：**")
                            for s in review["strengths"]:
                                st.markdown(f"- {s}")

                        # Step 4: 修改润色
                        if review.get("overall_score", 0) < 8:
                            status_text.text("✂️ Step 4/4：根据意见修改文章...")
                            progress_bar.progress(75)
                            st.info("正在根据审稿意见修改文章...")

                            revise_result = revise_draft(
                                original_content, draft, review, api_key, selected_model,
                                reviser_prompt if 'reviser_prompt' in dir() else prompts["reviser"]
                            )

                            if revise_result["success"]:
                                final_article = revise_result["content"]
                                st.session_state.final_article = final_article
                                st.success("✅ 修改完成！")
                            else:
                                st.warning(f"⚠️ 修改失败，使用初稿: {revise_result.get('error', '')}")
                                st.session_state.final_article = draft
                        else:
                            st.success("🎉 文章质量优秀，无需修改！")
                            st.session_state.final_article = draft

                        # 完成
                        status_text.text("✅ 工作流完成！")
                        progress_bar.progress(100)
                        st.balloons()

                    except Exception as e:
                        st.error(f"❌ 执行出错: {str(e)}")

    # ---------- Tab 4: 结果 ----------
    with tab4:
        st.header("📄 生成结果")

        if "final_article" not in st.session_state:
            st.info("👆 请先执行工作流生成文章")
        else:
            article_data = parse_article(st.session_state.final_article)

            # 文章标题
            st.subheader(f"📌 {article_data['title'] or '生成的标题'}")

            # 标签
            if article_data["tags"]:
                st.markdown("**标签：** " + " ".join([f"`{t}`" for t in article_data["tags"]]))

            # 显示文章内容
            st.markdown(article_data["body"])

            st.divider()

            # 导出选项
            col1, col2, col3 = st.columns(3)

            with col1:
                # Markdown 下载
                md_content = f"""# {article_data['title']}

{article_data['body']}

---
标签：{', '.join(article_data['tags']) if article_data['tags'] else '无'}
生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                st.download_button(
                    "📥 下载 Markdown",
                    md_content,
                    file_name=f"{article_data['title'] or 'article'}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

            with col2:
                # Word 文档下载
                try:
                    from docx import Document
                    from io import BytesIO

                    doc = Document()
                    doc.add_heading(article_data['title'] or '文章标题', 0)

                    for para in article_data['body'].split('\n'):
                        para = para.strip()
                        if para:
                            if para.startswith('## '):
                                doc.add_heading(para[3:], level=2)
                            elif para.startswith('# '):
                                doc.add_heading(para[2:], level=1)
                            else:
                                doc.add_paragraph(para)

                    buffer = BytesIO()
                    doc.save(buffer)
                    buffer.seek(0)

                    st.download_button(
                        "📄 下载 Word",
                        buffer.getvalue(),
                        file_name=f"{article_data['title'] or 'article'}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                except ImportError:
                    st.caption("需要 python-docx 库")

            with col3:
                # 复制到剪贴板
                st.button("📋 复制全文", on_click=lambda: st.clipboard(md_content), use_container_width=True)

            # 发送飞书
            if feishu_webhook:
                st.divider()
                if st.button("🚀 发送到飞书群", use_container_width=True):
                    result = send_to_feishu(article_data["body"], feishu_webhook)
                    if result["success"]:
                        st.success("✅ 已发送到飞书群！")
                    else:
                        st.error(f"❌ 发送失败: {result.get('error', '')}")

            # 审稿结果
            if "review" in st.session_state:
                st.divider()
                st.subheader("🔍 审稿结果")

                review = st.session_state["review"]
                if isinstance(review, dict):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("准确性", review.get("accuracy_score", "-"))
                    with col2:
                        st.metric("完整性", review.get("completeness_score", "-"))
                    with col3:
                        st.metric("可读性", review.get("readability_score", "-"))
                    with col4:
                        score = review.get("overall_score", 0)
                        st.metric("总分", score,
                                 delta_color="normal" if score >= 8 else "inverse")


if __name__ == "__main__":
    main()
