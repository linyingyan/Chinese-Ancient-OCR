# 发布整理验证记录

检查日期：2026-10-30。本次发布是源码展示，不是已完成生产加固的在线服务。

## 已完成

- 8 个原始 Python 源文件通过 AST 语法检查。
- 前端执行 `npm ci --ignore-scripts`，并完成声明范围内的依赖更新；`npm run build` 通过。
- 前端锁文件随更新提交；本地生成的 `node_modules/` 和 `dist/` 不上传。
- 在独立临时 SQLite 数据库中验证健康检查、创建/读取/列出记录、规则回退抽取。OCR 模块明确使用测试替身，任何 OCR 调用都会失败；未执行 OCR 或远程模型请求。
- 原压缩包保持原样；`.env`、个人简历、原数据库、扫描 PDF、OCR 输出和虚拟环境均未纳入发布文件。

文本 API 冒烟测试可在安装所需 FastAPI、SQLAlchemy、Pydantic、python-dotenv、python-multipart、httpx 后执行：

```bash
python scripts/smoke_text_api.py
```

## 依赖审计与未完成验证

`npm audit --json` 初次报告 9 项 high、2 项 moderate；同大版本更新后为 **1 项 high、2 项 moderate**，无 critical。原始/更新后的计数和具体公告地址保存在 `validation-results.json`。

| 依赖 | 级别与可达范围 | 当前处理 |
|---|---|---|
| Vite 5 | high；本地开发服务器/编辑器集成路径 | 开发脚本默认仅监听 127.0.0.1。只对可信页面和本机开发使用；限制监听并不等于修复漏洞。修复涉及 Vite 大版本和插件迁移，未在源码整理中强制升级。 |
| esbuild（Vite 间接依赖） | moderate；开发服务请求读取风险 | 随 Vite 迁移处理；不将开发服务器部署到公网。 |
| ECharts 5 | moderate；不可信图表内容进入 HTML tooltip 等路径时有 XSS 风险 | 保留原图谱/图表接口，后续升级 ECharts 6 并检查所有 tooltip 数据边界；不能假设所有外部文档都可信。 |

这三项暂缓至单独的依赖迁移工作，复查日期 **2026-11-06**。仅发布源码，不发布含这些依赖的公共运行实例。

仍未执行完整 PaddleOCR 模型推理、在线 LLM 调用和全流程 UI 联调；没有声称 OCR 准确率、吞吐或生产安全已验证。Python 运行依赖尚未做完整漏洞审计。首次下载模型、CPU/CUDA 与 Python 版本匹配仍需使用者在本地准备。

构建仍有大文件分包提示，尚未做 bundle 性能优化。项目的接口鉴权、上传限制、CORS 和浏览器侧密钥处理需要在任何公网运行前单独加固。
