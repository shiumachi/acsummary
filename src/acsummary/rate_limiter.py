import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

@dataclass
class RateLimiter:
    """
    非同期のレート制限を実装するクラス
    
    Attributes:
        requests_per_period: 期間内に許可するリクエスト数
        period_seconds: 期間（秒）
        _request_times: リクエスト時刻を保持するdeque
    """
    requests_per_period: int
    period_seconds: float
    _request_times: deque[datetime] = field(default_factory=deque)
    
    async def acquire(self) -> None:
        """
        レート制限に従ってリクエストの実行を制御
        
        非同期でリクエストのタイミングを待機し、
        期間内のリクエスト数が制限を超えないようにする
        """
        now = datetime.now()
        
        # 期間外のタイムスタンプを削除
        while (
            self._request_times and 
            now - self._request_times[0] > timedelta(seconds=self.period_seconds)
        ):
            self._request_times.popleft()
        
        # 期間内のリクエスト数が制限に達している場合は待機
        if len(self._request_times) >= self.requests_per_period:
            wait_time = (
                self._request_times[0] + 
                timedelta(seconds=self.period_seconds) - 
                now
            ).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        # 現在のリクエスト時刻を記録
        self._request_times.append(datetime.now())