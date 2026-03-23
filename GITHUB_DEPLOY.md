---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3046022100a705fc835d2cc7fb42a209bbd45daa9a4c260f7b78a91c15589430e32d8eba3f022100b0ccc94982943ab90fd8287364a2e51497955ef6f48129d21445cd1522218f72
    ReservedCode2: 304402201ca793a7a4dab4970dfd67e9af64e0478d3f550fdc8ca4a1d037b5de5dd2967b02204f60972d8094f9f084836ccee729329eebcc9703bb4d30f6620d853b815c640b
---

# 🚀 GitHub + Streamlit Cloud 一键部署指南

本指南将帮助您将微信公众号文章生成工作流部署到 Streamlit Cloud，实现云端运行！

## 📋 部署流程概览

```
┌─────────────────────────────────────────────────────────────┐
│  1. 创建 GitHub 仓库                                        │
│  2. 上传代码到仓库                                           │
│  3. 连接 Streamlit Cloud                                    │
│  4. 配置 DeerAPI 密钥                                       │
│  5. 部署并访问！                                             │
└─────────────────────────────────────────────────────────────┘
```

## 📝 详细步骤

### 步骤 1：创建 GitHub 仓库

1. 访问 [GitHub](https://github.com) 并登录
2. 点击右上角 **"+"** → **"New repository"**
3. 填写仓库信息：
   - **Repository name**: `wechat-article-workflow`
   - **Description**: 微信公众号文章生成工作流
   - **选择 Public**（Streamlit Cloud 需要公开仓库）
   - **不要勾选** "Add a README file"（我们已有）

### 步骤 2：上传代码

在您创建的空仓库页面：

1. 点击 **"uploading an existing file"** 或使用 Git 命令：

```bash
# 在本地初始化 Git 仓库
cd streamlit_app
git init
git add .
git commit -m "Initial commit: 微信公众号文章生成工作流"

# 添加远程仓库（替换为您的仓库 URL）
git remote add origin https://github.com/YOUR_USERNAME/wechat-article-workflow.git

# 推送代码
git branch -M main
git push -u origin main
```

### 步骤 3：连接 Streamlit Cloud

1. 访问 [share.streamlit.io](https://share.streamlit.io)
2. 点击 **"Sign up with GitHub"** 登录
3. 点击 **"New app"**

### 步骤 4：配置应用

在部署页面填写：

| 配置项 | 值 |
|--------|-----|
| **Repository** | `YOUR_USERNAME/wechat-article-workflow` |
| **Branch** | `main` |
| **Main file path** | `app.py` |
| **App URL** | 您的应用名称（如 `wechat-article-workflow`） |

### 步骤 5：配置密钥

点击 **"Advanced settings"** → **"Secrets"**，添加：

```toml
DEER_API_KEY = "sk-ard5a2VJsJSgUoucA7D3qiGPfRBEl9R7Jm58C8Ik1ltp8Pth"
```

> ⚠️ **重要**：请替换为您自己的 DeerAPI 密钥！

### 步骤 6：部署！

点击 **"Deploy!"** 按钮，等待 2-3 分钟部署完成。

部署成功后，您将获得：
```
https://wechat-article-workflow.streamlit.app
```

## 🎉 访问应用

部署完成后，您可以直接通过浏览器访问应用链接，无需任何本地运行！

## 🔄 更新代码

更新代码后，只需推送到 GitHub，Streamlit Cloud 会自动重新部署。

```bash
git add .
git commit -m "Your update message"
git push
```

## 🛠️ 故障排除

### 部署失败？
- 检查 `requirements.txt` 是否正确
- 确保所有依赖都兼容 Python 3.9+
- 查看 Streamlit Cloud 的部署日志

### 应用运行慢？
- Streamlit Cloud 免费版有资源限制
- 考虑使用更高配置的付费计划

### 密钥配置问题？
- 确保在 Advanced settings 中正确配置
- 密钥名称必须与代码中一致

## 📚 完整项目结构

```
streamlit_app/
├── app.py                 # 主应用代码
├── requirements.txt       # Python 依赖
├── .env.example          # 环境变量示例
├── .streamlit/
│   └── config.toml       # Streamlit 配置
├── .gitignore
└── README.md
```

## 💡 提示

- **保持密钥安全**：不要将真实密钥提交到 GitHub
- **使用 .env**：敏感信息通过环境变量或 Streamlit Secrets 配置
- **定期更新**：保持依赖包最新以获得性能和安全改进

---

**有问题？** 欢迎提交 Issue 或联系开发者！
