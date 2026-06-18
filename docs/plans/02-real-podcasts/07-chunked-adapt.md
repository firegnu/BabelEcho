# 02.07 Chunked DeepSeek Adapt

状态：done

## 目标

把中文改写阶段从每个 transcript segment 调用一次 LLM，改为按 chunk 批量调用，降低真实播客上百段 transcript 的 DeepSeek 调用次数、等待时间和失败面。

## 范围

- 新增 `adapt.mode: chunked` 配置。
- 按完整 transcript segment 聚合 chunk，不切开单个 segment 内部文本。
- 使用 `chunk_max_segments` 和 `chunk_max_chars` 两个上限切 chunk。
- LLM 返回必须包含原始 segment id；合并时按原始 id 顺序重建 `script/zh.json`。
- 每个 chunk 的结果保存到 run-local `script/adapt-chunks/chunk-000N.json`，便于排查。

## 不做

- 不做并发 chunk 调用。
- 不做自动重试。
- 不在 chunk 边界内拆分一个超长 segment。
- 不改变 TTS 输入合同；TTS 仍只读取最终 `script/zh.json`。

## 验收记录

- `tests/test_adapt.py` 覆盖 chunk 分割、乱序返回按 id 合并、speaker 保留和缺失 id 拒绝。
- `tests/test_llm.py` 覆盖 OpenAI-compatible provider 的 batch JSON 请求。
- 真实 DeepSeek smoke 使用 `Karaoke Videos` 20 段 excerpt，chunk 大小 5 段，生成 4 个 chunk 文件和 20 段中文脚本。
