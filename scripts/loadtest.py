"""简易压测脚本（不依赖 locust / ab）。

用法：
    python scripts/loadtest.py --path "/api/news/45" --concurrency 20 --duration 8
    python scripts/loadtest.py --path "/api/news?categoryId=1&pageSize=10" --concurrency 50

输出 QPS、延迟分位和错误率。用来验证缓存（详情页）和索引（列表）到底有没有用。

⚠️ 别对着生产环境跑。
"""

import argparse
import asyncio
import statistics
import time
from collections import Counter

import httpx


async def one_request(client: httpx.AsyncClient, url: str, results: list, errors: Counter):
    start = time.perf_counter()
    try:
        resp = await client.get(url)
        elapsed = time.perf_counter() - start
        if resp.status_code >= 400:
            errors[resp.status_code] += 1
        else:
            results.append(elapsed)
    except Exception as exc:
        errors[type(exc).__name__] += 1


async def worker(client: httpx.AsyncClient, url: str, deadline: float, results: list, errors: Counter):
    while time.perf_counter() < deadline:
        await one_request(client, url, results, errors)


def percentile(values: list, ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * ratio))
    return ordered[index] * 1000


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/api/news/45")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--duration", type=float, default=8.0, help="压测持续秒数")
    parser.add_argument("--token", default=None, help="可选：Authorization 头")
    args = parser.parse_args()

    url = args.base + args.path
    headers = {"Authorization": args.token} if args.token else {}
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)

    results: list[float] = []
    errors: Counter = Counter()

    async with httpx.AsyncClient(timeout=10, headers=headers, limits=limits) as client:
        # 预热：把缓存和连接都建起来，避免第一批请求拉低均值
        await one_request(client, url, [], Counter())

        started = time.perf_counter()
        deadline = started + args.duration
        await asyncio.gather(*[worker(client, url, deadline, results, errors) for _ in range(args.concurrency)])
        elapsed = time.perf_counter() - started

    total = len(results) + sum(errors.values())
    print(f"\n目标      {url}")
    print(f"并发      {args.concurrency}    持续 {args.duration}s")
    print(f"总请求    {total}    成功 {len(results)}    失败 {sum(errors.values())}")
    if errors:
        print(f"错误分布  {dict(errors)}")
    print(f"QPS       {len(results) / elapsed:.1f}")
    if results:
        print(f"平均延迟  {statistics.mean(results) * 1000:.1f} ms")
        print(f"P50       {percentile(results, 0.50):.1f} ms")
        print(f"P95       {percentile(results, 0.95):.1f} ms")
        print(f"P99       {percentile(results, 0.99):.1f} ms")
        print(f"最大      {max(results) * 1000:.1f} ms")


if __name__ == "__main__":
    asyncio.run(main())
