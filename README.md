# 古籍 OCR 与知识抽取系统

**Ancient Chinese Book OCR & Knowledge Extraction System**

面向竖排古籍的文档处理与研究工作台：把扫描图片/PDF 转为按阅读顺序排列的文本，进一步完成结构化知识抽取、记录管理、知识图谱和时空事件分析。

本科毕业项目源码整理版。公开仓库仅包含代码和配置示例，不包含原始简历、个人数据库、扫描 PDF、API 密钥或历史 OCR 输出。

## 功能

- **竖排 OCR**：使用 PaddleOCR 识别文字框，以 x 坐标分列、列间从右到左、列内从上到下恢复阅读顺序。
- **PDF 与批处理**：PyMuPDF 分页渲染，支持多页处理、OCR 缓存与批量任务。
- **结构化抽取**：通过 OpenAI 兼容接口抽取实体、三元组、摘要和现代汉语翻译，支持长文本分块与 JSON 解析回退。
- **知识记录**：SQLite/SQLAlchemy 存储，支持筛选、修改、重新抽取和导出。
- **图谱与分析**：人物关系网络、关系统计、跨文档时空事件聚类与时间线。
- **双界面**：Vue 3 管理前端与原有 Streamlit 页面。

未配置 LLM 时，部分知识抽取功能会使用规则回退。规则结果只是演示近似，不能当作真实模型推理或已核实的史学结论。OCR 仍然需要可用的 PaddleOCR 模型。

## 技术栈

| 部分 | 技术 |
|---|---|
| 文档与 OCR | Python、PaddleOCR/PaddlePaddle、PyMuPDF、NumPy |
| API 与存储 | FastAPI、SQLAlchemy、SQLite |
| 知识抽取 | OpenAI 兼容 API、Pydantic |
| 前端 | Vue 3、Vite、Element Plus、ECharts |
| 原有页面 | Streamlit |

## 目录

```text
main.py                 OCR、PDF 处理与文本分段
api_server.py           FastAPI 接口和静态前端托管
llm_service.py          LLM 调用、结构化解析与规则回退
models.py               数据表和数据库初始化
app.py / admin_app.py   Streamlit 页面
seed_db.py              本地示例数据初始化
scripts/                演示记录脚本
frontend/               Vue 3 工作台
.env.example            可选 LLM 配置示例
```

## 快速开始

建议使用独立 Python 3.11 环境、Node.js LTS。具体 PaddlePaddle 安装包须与操作系统/CPU 或 CUDA 环境匹配。

### 1. Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell 激活方式为 `.venv\Scripts\Activate.ps1`。若只使用规则回退，可保持 `OPENAI_API_KEY` 为空；调用在线服务时填写自己的 Key、Base URL 和 Model。

OCR 代码使用 PaddleOCR v3 的 `predict()` 接口。依赖范围已与该 API 对齐为 PaddleOCR 3.x / PaddlePaddle 3.x；首次模型初始化可能联网下载模型。安装说明以 [PaddleOCR 官方文档](https://www.paddleocr.ai/)为准，不建议直接复用归档内的 Windows 虚拟环境。

### 2. 启动 API

在仓库根目录：

```bash
uvicorn api_server:app --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000/docs`。启动时会在本地创建 SQLite 数据库，原数据库没有上传。

### 3. 前端开发

```bash
cd frontend
npm ci --ignore-scripts
npm run dev
```

访问 `http://localhost:5173`。开发代理会将 `/api` 请求转发给 `http://127.0.0.1:8000`。

生产构建：

```bash
npm run build
```

在 `frontend/dist/` 存在时，FastAPI 可托管构建后的页面；构建目录不纳入源码管理。

### 4. 原有 Streamlit 页面与命令行 OCR

```bash
streamlit run app.py
# 或
streamlit run admin_app.py
```

命令行 OCR 的参数和输出结构见 [docs/OCR_CLI_ORIGINAL.md](docs/OCR_CLI_ORIGINAL.md)。原示例图片没有上传，运行 `main.py` 前需将其中 `input_path` 改为你自己的图片/PDF。

## 数据与密钥

- `.env`、SQLite 数据库及 WAL/SHM 文件、OCR 输出和上传文档均已忽略。
- 不发布原压缩包中的简历、扫描 PDF 和既有数据库。
- 不要在前端配置或浏览器存储中保存长期服务密钥；需要对外部署时，应使用受控的服务端密钥与鉴权设计。
- 本项目是毕业设计与本地研究原型，当前接口不应未经鉴权和上传限制就直接开放到公网。

## 验证与限制

构建、静态检查与依赖审计结果见 [docs/VALIDATION.md](docs/VALIDATION.md)。完整 OCR / 在线模型效果需要另行准备模型、API 与测试文档，本次整理不虚构准确率或性能指标。

## 来源与许可

保留原项目 README 所标注的 MIT 许可声明；依赖库、模型权重和第三方文献分别遵循其自身许可。仓库不捆绑模型和第三方扫描书籍。历史示例文字的来源在种子脚本中标注。
