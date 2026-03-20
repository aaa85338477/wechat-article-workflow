---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 304502200481c7e852325092870b5be92f19c8056bbfeaa74ece6bf79a2939f5b0d428aa022100b4fd9ba77d3ff9f3b951eb23f980a7059d544fb1a60d4fe7dbf6cb8e9a09426e
    ReservedCode2: 3045022100c2c5784f278ee66f76a25c2e74c554a0dadbea246d69bf3d54855c546fc11ebc02204b7bac41d0e7d4d8a158622ab7ce965d8830e3b45ebe679c56f161328637d57a
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
