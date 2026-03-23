---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3046022100ec7e7c99f3203ce02ead45f95f301741a6175cd10bf0447e6672126fc3cb3bea022100dc12b9604471dd145ee1e1e6a0bb118c429e8d551a811e1e5fe6800a47c7b40f
    ReservedCode2: 3046022100c6b5cff46f08f9c3ff342195c8fb1ecd47938d51e1f81c3e4d39b264d0c24f9d022100bb7993459ab72125fe0d7c50a38e1ab87d1102878eda604f2ad64654c1496ec0
---

# Streamlit Cloud 部署配置

这是一个 Streamlit Cloud 部署配置文件。

## 部署步骤

### 1. Fork 或复制此仓库到您的 GitHub

### 2. 在 Streamlit Cloud 上连接仓库

1. 访问 [Streamlit Cloud](https://streamlit.io/cloud)
2. 使用 GitHub 账号登录
3. 点击 "New app"
4. 选择您的仓库

### 3. 配置环境变量

在 Streamlit Cloud 的高级设置中，添加以下密钥：

- `DEER_API_KEY`: 您的 DeerAPI 密钥

### 4. 部署

点击 "Deploy!" 按钮即可部署。

## 本地运行

```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

## 访问应用

部署成功后，您将获得一个公开可访问的 URL，格式如：
`https://your-app-name.streamlit.app`
