"""
性能优化中间件
包括响应压缩、请求限流、性能监控等
"""

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """性能监控中间件"""

    def __init__(self, app, enable_logging: bool = True):
        super().__init__(app)
        self.enable_logging = enable_logging
        self.request_stats = defaultdict(list)
        self.slow_requests = deque(maxlen=100)  # 保留最近100个慢请求

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并监控性能"""
        start_time = time.time()

        # 记录请求开始
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        try:
            # 处理请求
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 记录性能数据
            self._record_performance(method, path, process_time, response.status_code)

            # 添加性能头
            response.headers["X-Process-Time"] = str(round(process_time, 4))
            response.headers["X-Timestamp"] = str(int(time.time()))

            # 记录慢请求
            if process_time > 2.0:  # 超过2秒的请求
                self.slow_requests.append(
                    {
                        'method': method,
                        'path': path,
                        'process_time': process_time,
                        'status_code': response.status_code,
                        'timestamp': datetime.now().isoformat(),
                        'client_ip': client_ip,
                    }
                )

                if self.enable_logging:
                    logger.warning(f"慢请求: {method} {path} - {process_time:.2f}s - {response.status_code}")

            # 记录正常请求
            elif self.enable_logging and process_time > 0.5:
                logger.info(f"请求: {method} {path} - {process_time:.2f}s - {response.status_code}")

            return response

        except Exception as e:
            process_time = time.time() - start_time

            # 记录错误
            self._record_performance(method, path, process_time, 500)

            if self.enable_logging:
                logger.error(f"请求错误: {method} {path} - {process_time:.2f}s - {str(e)}")

            raise

    def _record_performance(self, method: str, path: str, process_time: float, status_code: int):
        """记录性能数据"""
        key = f"{method} {path}"
        self.request_stats[key].append(
            {'process_time': process_time, 'status_code': status_code, 'timestamp': time.time()}
        )

        # 只保留最近1小时的数据
        cutoff_time = time.time() - 3600
        self.request_stats[key] = [stat for stat in self.request_stats[key] if stat['timestamp'] > cutoff_time]

    def get_stats(self) -> dict:
        """获取性能统计"""
        stats = {}

        for endpoint, records in self.request_stats.items():
            if not records:
                continue

            process_times = [r['process_time'] for r in records]
            status_codes = [r['status_code'] for r in records]

            stats[endpoint] = {
                'total_requests': len(records),
                'avg_response_time': sum(process_times) / len(process_times),
                'min_response_time': min(process_times),
                'max_response_time': max(process_times),
                'success_rate': len([s for s in status_codes if 200 <= s < 400]) / len(status_codes),
                'error_rate': len([s for s in status_codes if s >= 400]) / len(status_codes),
            }

        return {'endpoint_stats': stats, 'slow_requests': list(self.slow_requests), 'total_endpoints': len(stats)}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """请求限流中间件"""

    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.client_requests = defaultdict(lambda: {'minute': deque(), 'hour': deque()})

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求限流"""
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # 清理过期记录
        self._cleanup_expired_requests(client_ip, current_time)

        # 检查限流
        if self._is_rate_limited(client_ip, current_time):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "请求过于频繁",
                    "message": f"每分钟最多{self.requests_per_minute}次请求，每小时最多{self.requests_per_hour}次请求",
                    "retry_after": 60,
                },
                headers={"Retry-After": "60"},
            )

        # 记录请求
        self.client_requests[client_ip]['minute'].append(current_time)
        self.client_requests[client_ip]['hour'].append(current_time)

        # 处理请求
        response = await call_next(request)

        # 添加限流头
        minute_requests = len(self.client_requests[client_ip]['minute'])
        hour_requests = len(self.client_requests[client_ip]['hour'])

        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(max(0, self.requests_per_minute - minute_requests))
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, self.requests_per_hour - hour_requests))

        return response

    def _cleanup_expired_requests(self, client_ip: str, current_time: float):
        """清理过期的请求记录"""
        minute_cutoff = current_time - 60
        hour_cutoff = current_time - 3600

        # 清理分钟级记录
        while (
            self.client_requests[client_ip]['minute'] and self.client_requests[client_ip]['minute'][0] < minute_cutoff
        ):
            self.client_requests[client_ip]['minute'].popleft()

        # 清理小时级记录
        while self.client_requests[client_ip]['hour'] and self.client_requests[client_ip]['hour'][0] < hour_cutoff:
            self.client_requests[client_ip]['hour'].popleft()

    def _is_rate_limited(self, client_ip: str, current_time: float) -> bool:
        """检查是否超过限流"""
        minute_requests = len(self.client_requests[client_ip]['minute'])
        hour_requests = len(self.client_requests[client_ip]['hour'])

        return minute_requests >= self.requests_per_minute or hour_requests >= self.requests_per_hour


class ResponseOptimizationMiddleware(BaseHTTPMiddleware):
    """响应优化中间件"""

    def __init__(self, app, enable_compression: bool = True, min_size: int = 1000):
        super().__init__(app)
        self.enable_compression = enable_compression
        self.min_size = min_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """优化响应"""
        response = await call_next(request)

        # 添加缓存头
        if request.method == "GET" and response.status_code == 200:
            # 静态资源缓存
            if any(request.url.path.endswith(ext) for ext in ['.js', '.css', '.png', '.jpg', '.ico']):
                response.headers["Cache-Control"] = "public, max-age=86400"  # 1天
            # API响应缓存
            elif "/api/" in request.url.path:
                response.headers["Cache-Control"] = "public, max-age=300"  # 5分钟

        # 添加安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response


class ConcurrencyLimitMiddleware(BaseHTTPMiddleware):
    """并发限制中间件"""

    def __init__(self, app, max_concurrent_requests: int = 100):
        super().__init__(app)
        self.max_concurrent_requests = max_concurrent_requests
        self.current_requests = 0
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """限制并发请求数"""
        if self.current_requests >= self.max_concurrent_requests:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "服务器繁忙",
                    "message": "当前并发请求过多，请稍后重试",
                    "max_concurrent": self.max_concurrent_requests,
                },
            )

        async with self.semaphore:
            self.current_requests += 1
            try:
                response = await call_next(request)
                response.headers["X-Concurrent-Requests"] = str(self.current_requests)
                return response
            finally:
                self.current_requests -= 1


def setup_performance_middleware(app):
    """设置性能优化中间件"""

    # 1. 响应压缩（内置）
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 2. 并发限制
    app.add_middleware(ConcurrencyLimitMiddleware, max_concurrent_requests=50)

    # 3. 请求限流
    app.add_middleware(RateLimitMiddleware, requests_per_minute=120, requests_per_hour=2000)

    # 4. 响应优化
    app.add_middleware(ResponseOptimizationMiddleware)

    # 5. 性能监控（最后添加，确保监控所有请求）
    app.add_middleware(PerformanceMonitoringMiddleware, enable_logging=True)

    logger.info("✅ 性能优化中间件设置完成")
    return app
