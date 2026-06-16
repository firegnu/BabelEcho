# 计划文档索引

## 目的

`docs/plans/` 用来保存可执行计划。它和架构、调研、runbook 文档分开：架构文档回答“系统应该长什么样”，计划文档回答“下一步按什么顺序做”。

产品阶段和长期优先级见：[BabelEcho Roadmap](../roadmap.md)。

## 编号规则

采用两级编号：

- 大计划目录：`NN-topic/`
- 子计划文件：`NN-short-name.md`

例如：

```text
docs/plans/
  01-backend-mvp0/
    01-local-llm-adapt.md
    02-real-transcript-source.md
    03-local-tts.md
  02-publish-and-app/
    01-static-feed-hosting.md
    02-macos-reader-app.md
```

对应关系：

- `01-backend-mvp0/` 是第 1 个大计划。
- `01-backend-mvp0/01-local-llm-adapt.md` 是第 1 个大计划下的第 1 个子计划，也可以口头称为 `01.01`。
- 同一个目录下只追加新编号，不复用旧编号。
- 已有未编号文档暂不重命名，避免破坏链接；后续从 `docs/plans/` 开始保持编号。

## 状态约定

每个计划文件应包含：

- `状态`：`draft`、`ready`、`in_progress`、`done`、`blocked`
- `目标`
- `范围`
- `前置条件`
- `执行步骤`
- `验收标准`
- `风险和分支处理`

## 当前计划

### 01 Backend MVP-0

- [01.01 DeepSeek LLM Adapt 基线接入](./01-backend-mvp0/01-local-llm-adapt.md) - `done`
- [01.03 本地中文 TTS 接入](./01-backend-mvp0/03-local-tts.md) - `done`

### Roadmap

- [BabelEcho Roadmap](../roadmap.md) - `active`
