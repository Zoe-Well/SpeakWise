"""SSE 流式输出封装"""

from sse_starlette.sse import EventSourceResponse


async def sse_event_stream(generator, extra_meta: dict | None = None):
    """将异步生成器包装为 SSE EventSourceResponse。

    约定事件类型：
    - `event: meta`  → 首帧元数据（模式、response_id）
    - `event: token` → 逐段增量
    - `event: done`  → 完成（含完整内容与指标）
    """

    async def _inner():
        if extra_meta:
            import json
            yield {"event": "meta", "data": json.dumps(extra_meta, ensure_ascii=False)}
        async for token in generator:
            yield {"event": "token", "data": token}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(_inner())
