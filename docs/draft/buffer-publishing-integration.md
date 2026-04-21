# Buffer 发布中转集成需求文档

> 本文档用于扩展项目发布模块，接入 Buffer GraphQL API 实现多平台自媒体内容发布。

---

## 背景与选型依据

### 为什么不直连 X (Twitter) API

- X 官方 API 已于 2026年2月全面切换为按量付费，新开发者无免费档
- **关键限制**：个人 App 级每日发帖硬上限 **17条/天**，无法通过付费绕过
- Buffer 等中转平台使用自己的高配额 App，可突破此限制

### 为什么选 Buffer

- 通过 Buffer 发布到 X，借用其平台级配额，无 17条/天限制
- 支持 11 个主流平台：X/Twitter、Instagram、LinkedIn、Threads、TikTok、Facebook、YouTube、Pinterest、Mastodon、Google Business、Bluesky
- 免费计划：3个频道，实时发布无限制（队列上限10条，但立即发布不占队列）
- Essentials 付费档：$5/月/频道，无限发帖
- API 已从旧 REST 迁移至 **GraphQL**，文档完善，Beta 阶段但积极迭代
- 原生支持 MCP，可接入 Claude 等 AI 工具直接操作

---

## API 基础信息

| 项目 | 值 |
|------|---|
| Endpoint | `https://api.buffer.com` |
| 协议 | GraphQL（所有请求均为 POST） |
| 认证 | `Authorization: Bearer <API_KEY>` |
| API Key 获取 | `publish.buffer.com/settings/api` |
| 速率限制 | 滚动窗口，按 plan 档位，免费档约60次/分钟 |
| Key 有效期 | 可选 7天/30天/60天/90天/1年（推荐选1年） |

> **注意**：API Key 基于账号所有者个人生成，不对外共享。免费账号1个Key，付费最多5个。

---

## 核心功能需求

### 1. 实时发布（主要场景）

本地工具生成内容后，立即推送到指定平台发布。

**GraphQL Mutation：**

```graphql
mutation {
  createPost(input: {
    text: "内容正文"
    channelId: "CHANNEL_ID"
    mode: now
  }) {
    ... on PostActionSuccess {
      post { id status }
    }
    ... on MutationError {
      message
    }
  }
}
```

**HTTP 请求示例（Python）：**

```python
import requests

def publish_now(api_key: str, channel_id: str, text: str) -> dict:
    query = """
    mutation($text: String!, $channelId: String!) {
      createPost(input: {
        text: $text
        channelId: $channelId
        mode: now
      }) {
        ... on PostActionSuccess {
          post { id status }
        }
        ... on MutationError {
          message
        }
      }
    }
    """
    resp = requests.post(
        "https://api.buffer.com",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        json={"query": query, "variables": {"text": text, "channelId": channel_id}}
    )
    return resp.json()
```

### 2. 定时发布

指定未来某时间点发布，适合批量排期。

```graphql
mutation {
  createPost(input: {
    text: "内容正文"
    channelId: "CHANNEL_ID"
    dueAt: "2026-04-18T09:00:00Z"   # ISO 8601 UTC
  }) {
    ... on PostActionSuccess {
      post { id status dueAt }
    }
    ... on MutationError {
      message
    }
  }
}
```

### 3. 加入发布队列

由 Buffer 按预设时间表自动排队发布（需在 Buffer 后台配置发布时间段）。

```graphql
createPost(input: {
  text: "内容正文"
  channelId: "CHANNEL_ID"
  mode: addToQueue
})
```

### 4. 多平台同发

Buffer API 每次只接受单个 `channelId`，多平台需循环调用。

```python
def publish_to_platforms(api_key: str, channel_ids: list[str], text: str):
    results = []
    for channel_id in channel_ids:
        result = publish_now(api_key, channel_id, text)
        results.append({"channel": channel_id, "result": result})
    return results
```

### 5. 查询频道列表

初始化时获取已连接的频道 ID，存入本地配置。

```graphql
query {
  channels(input: { organizationId: "ORG_ID" }) {
    id
    name
    service    # x, instagram, linkedin, etc.
    avatar
  }
}
```

---

## 数据模型

### 发布请求

```python
@dataclass
class PublishRequest:
    text: str                          # 正文内容
    channel_ids: list[str]             # 目标频道列表
    mode: str = "now"                  # now | addToQueue
    due_at: str | None = None          # ISO 8601，定时发布时使用
    media_urls: list[str] | None = None  # 图片/视频URL（需公开可访问）
```

### 配置

```python
@dataclass
class BufferConfig:
    api_key: str
    org_id: str
    channels: dict[str, str]  # {"x": "ch_xxx", "linkedin": "ch_yyy", ...}
```

---

## 错误处理

Buffer GraphQL API 始终返回 HTTP 200，错误信息在响应体内：

```python
def handle_response(data: dict) -> dict:
    result = data.get("data", {}).get("createPost", {})

    # 成功
    if "post" in result:
        return {"ok": True, "post_id": result["post"]["id"]}

    # 业务错误（队列满、内容违规等）
    if "message" in result:
        return {"ok": False, "error": result["message"]}

    # GraphQL 层错误
    if "errors" in data:
        return {"ok": False, "error": data["errors"][0]["message"]}

    return {"ok": False, "error": "unknown"}
```

常见错误场景：
- 队列已满（免费档10条上限）：切换 `mode: now` 或清空队列
- 媒体 URL 不可访问：确保图片/视频 URL 无需认证，匿名可直接访问
- API Key 过期：Key 默认30天有效，建议生成时选1年

---

## 媒体附件

发布带图片/视频的帖子时，媒体通过公开 URL 引用，Buffer 自动拉取：

```graphql
mutation {
  createPost(input: {
    text: "带图片的内容"
    channelId: "CHANNEL_ID"
    mode: now
    media: {
      photo: "https://your-domain.com/image.jpg"
    }
  }) {
    ... on PostActionSuccess {
      post { id }
    }
  }
}
```

> TikTok 特殊要求：媒体 URL 必须在帖子实际发布时仍然有效，定时发布时不能提前删除源文件。

---

## 实现建议

1. **初始化阶段**：调用 channels query 获取各平台 channelId，写入本地 `.env` 或配置文件，避免每次发布时查询
2. **发布优先用 `mode: now`**：实时发布不占队列，无需担心队列满的问题
3. **API Key 管理**：存入环境变量 `BUFFER_API_KEY`，生成时选1年有效期，设置到期提醒
4. **重试策略**：遇到网络错误做指数退避重试，遇到业务错误（如内容违规）不重试直接报错
5. **多平台发布**：可并发请求提高速度，注意速率限制（60次/分钟）

---

## 未来扩展

- **循环发布**：Buffer API 已于2026年3月新增 `createPostRecurrence`，可实现定期重复发帖
- **草稿模式**：先创建 Idea（草稿），人工审核后再发布
- **分析数据**：Buffer 分析 API 尚未开放，暂通过 Buffer 后台查看；后续开放后可接入
- **MCP 接入**：Buffer 官方提供 MCP Server（`mcp.buffer.com/mcp`），可接入 Claude Code 直接用自然语言操作发布

---

## 参考链接

- Buffer GraphQL API 文档：`https://developers.buffer.com/`
- API Key 管理：`https://publish.buffer.com/settings/api`
- REST → GraphQL 迁移指南：`https://developers.buffer.com/guides/rest-migration.html`
- API Changelog：`https://developers.buffer.com/changelog.html`
