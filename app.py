import streamlit as st
import os
from models.query import MathProblemSolver
from PIL import Image
import io
import re

# 页面配置
st.set_page_config(
    page_title="数学题目解答系统",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# LaTeX公式渲染函数
def render_text_with_latex(text):
    """
    解析文本中的LaTeX公式并使用st.latex()渲染
    支持格式: $...$, $$...$$, \(...\), \[...\], 以及各种变体
    改进版本：更好地处理转义字符和多行公式
    """
    if not text:
        return
    
    # 预处理：修复可能的转义问题
    # 处理双反斜杠转义（但保留单个反斜杠用于LaTeX命令）
    lines = text.split('\n')
    processed_lines = []
    for line in lines:
        # 修复常见的转义问题，但保留LaTeX命令
        line = re.sub(r'\\(\\+)([\[\(])', r'\1\2', line)  # \\[ -> \[
        processed_lines.append(line)
    text = '\n'.join(processed_lines)
    
    # 存储所有找到的公式位置和内容
    all_matches = []
    
    # 1. 先匹配块级公式 $$...$$ (支持多行)
    for match in re.finditer(r'\$\$((?:(?!\$\$).|\n)+?)\$\$', text, re.DOTALL):
        formula = match.group(1).strip()
        if formula:
            all_matches.append((match.start(), match.end(), 'block', formula))
    
    # 2. 匹配块级公式 \[...\] (支持多行)
    for match in re.finditer(r'\\\[((?:(?!\\\]).|\n)+?)\\\]', text, re.DOTALL):
        start, end = match.start(), match.end()
        # 检查是否在已有的$$公式内
        is_inside = any(m_start <= start < m_end for m_start, m_end, _, _ in all_matches)
        if not is_inside:
            formula = match.group(1).strip()
            if formula:
                all_matches.append((start, end, 'block', formula))
    
    # 3. 匹配行内公式 $...$ (排除$$的情况，支持单行)
    for match in re.finditer(r'(?<!\$)\$(?![$])((?:(?!\$[^$]|$$).)+?)\$(?!\$)', text):
        start, end = match.start(), match.end()
        # 检查是否在已有的块级公式内
        is_inside = any(m_start <= start < m_end for m_start, m_end, _, _ in all_matches)
        if not is_inside:
            formula = match.group(1).strip()
            if formula and '$' not in formula:  # 确保不是$$的一部分
                all_matches.append((start, end, 'inline', formula))
    
    # 4. 匹配行内公式 \(...\) (支持单行)
    for match in re.finditer(r'\\\(((?:(?!\\\)).)+?)\\\)', text):
        start, end = match.start(), match.end()
        # 检查是否在已有的公式内
        is_inside = any(m_start <= start < m_end for m_start, m_end, _, _ in all_matches)
        if not is_inside:
            formula = match.group(1).strip()
            if formula:
                all_matches.append((start, end, 'inline', formula))
    
    # 按位置排序
    all_matches.sort(key=lambda x: x[0])
    
    # 移除重叠的匹配（保留第一个遇到的）
    filtered_matches = []
    for match in all_matches:
        start, end, mtype, content = match
        overlaps = any(existing_start < end and start < existing_end 
                     for existing_start, existing_end, _, _ in filtered_matches)
        if not overlaps:
            filtered_matches.append(match)
    
    all_matches = filtered_matches
    
    # 辅助函数：检查文本是否真的有内容（不是只有空白字符）
    def has_real_content(s):
        if not s:
            return False
        # 移除所有空白字符（包括空格、换行、制表符等）
        cleaned = re.sub(r'\s+', '', s)
        return len(cleaned) > 0
    
    # 辅助函数：清理HTML内容，移除空的HTML标签
    def clean_html_content(content):
        """移除空的HTML标签和占位元素"""
        if not content:
            return content
        
        # 移除空的div标签（包括只有空白字符的div）
        content = re.sub(r'<div[^>]*>\s*</div>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<div[^>]*>\s*<div[^>]*>\s*</div>\s*</div>', '', content, flags=re.IGNORECASE)
        
        # 移除空的hr标签
        content = re.sub(r'<hr[^>]*>\s*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<hr[^>]*/>', '', content, flags=re.IGNORECASE)
        
        # 移除空的img标签（不可见图片）
        content = re.sub(r'<img[^>]*>\s*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<img[^>]*/>', '', content, flags=re.IGNORECASE)
        
        # 移除空的span、p等标签
        content = re.sub(r'<span[^>]*>\s*</span>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<p[^>]*>\s*</p>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<br[^>]*>\s*', '', content, flags=re.IGNORECASE)
        
        return content
    
    # 如果没有找到任何公式，直接使用Streamlit的markdown渲染（只渲染有内容的）
    if not all_matches:
        if has_real_content(text):
            cleaned_text = text.strip()
            # 清理HTML内容，移除空的HTML标签
            cleaned_text = clean_html_content(cleaned_text)
            if cleaned_text and has_real_content(cleaned_text):
                st.markdown(cleaned_text, unsafe_allow_html=True)
        return
    
    # 重构文本：将行内公式嵌入文本流，块级公式单独处理
    result_parts = []
    last_end = 0
    
    for start, end, formula_type, formula_content in all_matches:
        # 添加公式前的文本（只添加有实际内容的文本）
        if start > last_end:
            text_before = text[last_end:start]
            if has_real_content(text_before):
                result_parts.append(('text', text_before))
        
        # 根据公式类型处理（只添加有内容的公式）
        if formula_type == 'block':
            # 块级公式：单独添加标记
            if has_real_content(formula_content):
                result_parts.append(('block_latex', formula_content))
        else:
            # 行内公式：转换为markdown格式，嵌入文本中
            if has_real_content(formula_content):
                result_parts.append(('inline_latex', formula_content))
        
        last_end = end
    
    # 添加最后剩余的文本（只添加有实际内容的文本）
    if last_end < len(text):
        remaining_text = text[last_end:]
        if has_real_content(remaining_text):
            result_parts.append(('text', remaining_text))
    
    # 渲染：合并连续的文本和行内公式，单独处理块级公式
    # 使用容器来减少空白间隔
    current_text_block = ""
    text_blocks = []
    
    for part_type, content in result_parts:
        if part_type == 'text':
            # 积累文本，等待后续可能的行内公式（只积累有内容的文本）
            if has_real_content(content):
                current_text_block += content
        elif part_type == 'inline_latex':
            # 行内公式：直接添加到当前文本块中，使用markdown格式
            if has_real_content(content):
                current_text_block += f"${content}$"
        elif part_type == 'block_latex':
            # 先保存积累的文本块（只保存有内容的）
            if has_real_content(current_text_block):
                text_blocks.append(('text', current_text_block))
                current_text_block = ""
            # 块级公式单独保存（只保存有内容的）
            if has_real_content(content):
                text_blocks.append(('block_latex', content))
    
    # 添加最后剩余的文本块（只添加有内容的）
    if has_real_content(current_text_block):
        text_blocks.append(('text', current_text_block))
    
    # 合并连续的文本块，一次性渲染以减少空白
    merged_blocks = []
    current_merged_text = ""
    
    for block_type, block_content in text_blocks:
        if block_type == 'text':
            # 合并连续的文本块（只合并有内容的）
            if has_real_content(block_content):
                if current_merged_text:
                    current_merged_text += "\n\n" + block_content
                else:
                    current_merged_text = block_content
        else:
            # 遇到块级公式，先渲染积累的文本（只保存有内容的）
            if has_real_content(current_merged_text):
                merged_blocks.append(('text', current_merged_text))
                current_merged_text = ""
            # 只添加有内容的块级公式
            if has_real_content(block_content):
                merged_blocks.append(('block_latex', block_content))
    
    # 添加最后合并的文本（只添加有内容的）
    if has_real_content(current_merged_text):
        merged_blocks.append(('text', current_merged_text))
    
    # 渲染合并后的块（严格避免渲染空内容）
    for block_type, block_content in merged_blocks:
        if block_type == 'text':
            # 只渲染有实际内容的文本
            if has_real_content(block_content):
                cleaned_content = block_content.strip()
                # 清理HTML内容，移除空的HTML标签
                cleaned_content = clean_html_content(cleaned_content)
                # 再次检查清理后的内容
                if cleaned_content and has_real_content(cleaned_content):
                    st.markdown(cleaned_content, unsafe_allow_html=True)
        else:
            # 块级公式：单独一行居中显示（只渲染有实际内容的公式）
            if has_real_content(block_content):
                try:
                    st.latex(block_content)
                except Exception as e:
                    cleaned_formula = block_content.replace('\\\\', '\\').strip()
                    if has_real_content(cleaned_formula):
                        try:
                            st.latex(cleaned_formula)
                        except:
                            st.markdown(f"`{cleaned_formula}`", unsafe_allow_html=True)

# 自定义CSS样式
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .result-box {
        padding: 0.5rem 0;
        margin: 0;
        background-color: transparent;
        border: none;
    }
    .result-box > * {
        margin: 0;
        padding: 0;
    }
    .knowledge-item {
        padding: 0.5rem;
        margin: 0.5rem 0;
        background-color: #ffffff;
        border-left: 4px solid #1f77b4;
        border-radius: 5px;
        display: flex;
        align-items: flex-start;
    }
    .knowledge-item > * {
        margin: 0;
        padding: 0;
    }
    .solution-box {
        padding: 0;
        margin: 0;
        background-color: transparent;
        border: none;
        border-radius: 0;
    }
    .solution-box > * {
        margin: 0;
        padding: 0;
    }
    .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
        font-weight: bold;
        border-radius: 5px;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #1565a0;
    }
    /* 减少markdown块之间的间距 */
    .stMarkdown {
        margin-bottom: 0.2rem !important;
        margin-top: 0 !important;
    }
    .stMarkdown p {
        margin-bottom: 0.2rem !important;
        margin-top: 0 !important;
        line-height: 1.6;
    }
    /* 减少LaTeX公式前后的间距 */
    .stLatex {
        margin: 0.3rem 0 !important;
    }
    /* 确保文本连贯性，移除空容器的占位 */
    div[data-testid="stMarkdownContainer"] > div {
        margin-bottom: 0 !important;
        min-height: 0 !important;
    }
    /* 减少元素之间的空白 */
    .element-container {
        margin-bottom: 0.2rem !important;
    }
    /* 移除空的元素占位（只针对内容区域的特定容器，不影响Streamlit组件） */
    .result-box > div:empty:not([data-testid]),
    .solution-box > div:empty:not([data-testid]),
    .knowledge-item > div:empty:not([data-testid]),
    .result-box > hr:not([data-testid]),
    .solution-box > hr:not([data-testid]),
    .knowledge-item > hr:not([data-testid]),
    .result-box > img[width="0"],
    .result-box > img[height="0"],
    .solution-box > img[width="0"],
    .solution-box > img[height="0"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    /* 隐藏只有空白字符的div和所有空元素 */
    .result-box > div:not([data-testid]):empty,
    .solution-box > div:not([data-testid]):empty,
    .knowledge-item > div:not([data-testid]):empty,
    .knowledge-item:empty,
    .knowledge-item > *:empty:not([data-testid]) {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    /* 隐藏知识点容器内的空hr、br等占位元素 */
    .knowledge-item > hr,
    .knowledge-item > br:only-child,
    .knowledge-item > img[width="0"],
    .knowledge-item > img[height="0"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    /* 确保Streamlit的核心组件始终显示 - 进度条 */
    [data-testid="stProgress"],
    [data-testid="stProgress"] > div,
    [data-testid="stProgress"] > div > div {
        display: block !important;
        visibility: visible !important;
        min-height: auto !important;
    }
    /* 确保Streamlit的核心组件始终显示 - 滑块 */
    [data-testid="stSlider"],
    [data-testid="stSlider"] > div,
    [data-testid="stSlider"] > div > div {
        display: block !important;
        visibility: visible !important;
    }
    /* 确保状态文本和所有Streamlit组件显示 */
    [data-testid="stMarkdownContainer"],
    [data-testid="stProgress"],
    [data-testid="stSlider"] {
        display: block !important;
        visibility: visible !important;
    }
    /* 移除hr等分隔线的默认样式 */
    hr {
        margin: 0.3rem 0 !important;
        border: none;
        height: 1px;
        background-color: transparent;
    }
    </style>
""", unsafe_allow_html=True)

# 标题
st.markdown('<h1 class="main-header">📐 数学题目解答系统</h1>', unsafe_allow_html=True)

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 系统配置")
    
    # API密钥输入
    api_key = st.text_input(
        "ARK API Key",
        type="password",
        help="请输入火山引擎ARK API密钥",
        value=os.getenv('ARK_API_KEY', '')
    )
    
    st.markdown("---")
    
    # 知识点数量设置
    top_k = st.slider(
        "检索知识点数量",
        min_value=1,
        max_value=10,
        value=3,
        help="设置检索相关知识点的数量"
    )
    
    st.markdown("---")
    st.markdown("### 📖 使用说明")
    st.markdown("""
    1. 在上方输入框中输入或粘贴您的ARK API密钥
    2. 上传包含数学题目的图片
    3. 点击"识别并解答"按钮
    4. 系统将自动识别题目、检索知识点并生成解答
    """)
    
    st.markdown("---")
    st.markdown("### ℹ️ 支持格式")
    st.markdown("- 图片格式：PNG, JPG, JPEG, WEBP")
    st.markdown("- 题目类型：各类数学题目")

# 主内容区
if not api_key:
    st.warning("⚠️ 请在侧边栏输入ARK API密钥以开始使用")
else:
    # 保存API密钥到环境变量
    os.environ['ARK_API_KEY'] = api_key
    
    # 文件上传
    st.subheader("📤 上传数学题目图片")
    
    # 定义最大文件大小（50MB）
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    uploaded_file = st.file_uploader(
        "选择图片文件",
        type=['png', 'jpg', 'jpeg', 'webp'],
        help=f"支持PNG、JPG、JPEG、WEBP格式，最大文件大小：{MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
    )
    
    if uploaded_file is not None:
        # 检查文件大小
        if uploaded_file.size > MAX_FILE_SIZE:
            st.error(f"❌ 文件太大！当前文件大小：{uploaded_file.size / 1024 / 1024:.2f} MB，最大允许：{MAX_FILE_SIZE / 1024 / 1024:.0f} MB")
            st.stop()
        # 显示上传的图片
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📷 上传的图片")
            image = Image.open(uploaded_file)
            st.image(image, caption="数学题目图片", use_container_width=True)
        
        with col2:
            st.subheader("📊 图片信息")
            st.info(f"**文件名：** {uploaded_file.name}\n\n"
                   f"**文件大小：** {uploaded_file.size / 1024:.2f} KB\n\n"
                   f"**图片尺寸：** {image.size[0]} × {image.size[1]} 像素")
        
        # 处理按钮
        st.markdown("---")
        if st.button("🚀 识别并解答", type="primary", use_container_width=True):
            # 初始化求解器
            try:
                with st.spinner("正在初始化系统..."):
                    solver = MathProblemSolver(api_key)
                
                # 保存上传的图片到临时文件
                temp_image_path = f"temp_{uploaded_file.name}"
                with open(temp_image_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 处理题目
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # 步骤1: 识别题目
                    status_text.text("步骤1/3: 正在识别题目内容...")
                    progress_bar.progress(33)
                    problem_text = solver.extract_problem_text(temp_image_path)
                    
                    # 步骤2: 检索知识点
                    status_text.text("步骤2/3: 正在检索相关知识点...")
                    progress_bar.progress(66)
                    related_knowledge = solver.search_related_knowledge(problem_text, top_k=top_k)
                    
                    # 步骤3: 生成解答
                    status_text.text("步骤3/3: 正在生成解答...")
                    progress_bar.progress(100)
                    solution = solver.solve_math_problem(problem_text, related_knowledge)
                    
                    status_text.empty()
                    progress_bar.empty()
                    
                    # 显示结果
                    st.markdown("---")
                    st.success("✅ 处理完成！")
                    
                    # 识别到的题目
                    st.subheader("📝 识别到的题目")
                    st.markdown('<div class="result-box">', unsafe_allow_html=True)
                    render_text_with_latex(problem_text)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # 相关知识点
                    st.subheader("📚 相关知识点")
                    # 过滤空的知识点（使用与render_text_with_latex相同的检查逻辑）
                    def has_real_content_check(s):
                        if not s or not isinstance(s, str):
                            return False
                        cleaned = re.sub(r'\s+', '', str(s).strip())
                        return len(cleaned) > 0
                    
                    valid_knowledge = []
                    for knowledge in related_knowledge:
                        if knowledge and has_real_content_check(knowledge):
                            valid_knowledge.append(knowledge)
                    
                    if not valid_knowledge:
                        st.info("未找到相关知识")
                    else:
                        for i, knowledge in enumerate(valid_knowledge, 1):
                            # 将编号和内容合并到一个容器中，避免错乱
                            with st.container():
                                st.markdown(f'<div class="knowledge-item">', unsafe_allow_html=True)
                                # 创建一个包含编号和内容的文本
                                knowledge_with_number = f"{i}. {knowledge}"
                                render_text_with_latex(knowledge_with_number)
                                st.markdown('</div>', unsafe_allow_html=True)
                    
                    # 解答
                    st.subheader("💡 详细解答")
                    st.markdown('<div class="solution-box">', unsafe_allow_html=True)
                    render_text_with_latex(solution)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # 清理临时文件
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)
                    
                except Exception as e:
                    status_text.empty()
                    progress_bar.empty()
                    st.error(f"❌ 处理过程中出现错误: {str(e)}")
                    if os.path.exists(temp_image_path):
                        os.remove(temp_image_path)
                        
            except Exception as e:
                st.error(f"❌ 初始化失败: {str(e)}")
                st.info("请检查API密钥是否正确，以及向量索引文件是否存在")

# 页脚
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #666; padding: 1rem;">'
    '数学题目解答系统 | 基于火山引擎ARK & RAG检索增强生成技术'
    '</div>',
    unsafe_allow_html=True
)

