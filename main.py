"""系统信息查询：/sys 返回 CPU、内存、磁盘、网络、运行时长。仅白名单 QQ 可用。"""

import os
import time

import psutil

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Node, Nodes, Plain
from astrbot.api.star import Context, Star, register

DEFAULT_ALLOW = [q for q in os.getenv("SYSINFO_ALLOW_QQS", "").split(",") if q]
DATA_PATH = "/AstrBot/data"
# forward_threshold 默认 100 字，超过会被框架折成单个 Node（NapCat 不认），
# 所以这里控制正文长度，超了就用 Nodes 合并转发兜底。
SOFT_LIMIT = 95


def _fmt_size(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f%s" % (n, unit)
        n /= 1024
    return "%.1fPB" % n


def _fmt_uptime(sec: float) -> str:
    sec = int(sec)
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m = sec // 60
    out = ""
    if d:
        out += "%d天" % d
    if h:
        out += "%d小时" % h
    if m and not d:
        out += "%d分" % m
    return out or "不到1分钟"


@register(
    "sysinfo",
    "小肥鱼",
    "系统信息查询：/sys 看 CPU、内存、磁盘、网络、运行时长（仅白名单）",
    "1.0.0",
)
class SysInfoPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.conf = config or {}

    def _allow_ids(self) -> set:
        raw = self.conf.get("allow_ids")
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.replace("，", ",").split(",") if x.strip()]
        if not isinstance(raw, (list, tuple)) or not raw:
            raw = DEFAULT_ALLOW
        return {str(x).strip() for x in raw}

    @filter.command("sys", alias={"系统信息"})
    async def sys_info(self, event: AstrMessageEvent):
        if str(event.get_sender_id()) not in self._allow_ids():
            logger.info("[sysinfo] 拒绝非白名单用户 %s" % event.get_sender_id())
            return
        try:
            text = self._render()
        except Exception as exc:
            logger.exception("[sysinfo] 采集失败")
            yield event.plain_result("读不到系统信息：%s" % exc)
            return
        if len(text) <= SOFT_LIMIT:
            yield event.plain_result(text)
            return
        bot_id = str(event.get_self_id() or "0")
        nodes = [
            Node(name="小肥鱼", uin=bot_id, content=[Plain(line)])
            for line in text.split("\n")
        ]
        yield event.chain_result([Nodes(nodes=nodes)])

    def _render(self) -> str:
        cpu_pct = psutil.cpu_percent(interval=0.4)
        cores = psutil.cpu_count(logical=True) or 0
        try:
            load1 = os.getloadavg()[0]
        except Exception:
            load1 = 0.0
        mem = psutil.virtual_memory()
        du = psutil.disk_usage(DATA_PATH)
        net = psutil.net_io_counters()
        up = _fmt_uptime(time.time() - psutil.boot_time())
        return "\n".join([
            "CPU %.0f%%×%d核 load %.2f" % (cpu_pct, cores, load1),
            "内存 %s/%s %.0f%% · 盘 %s/%s" % (
                _fmt_size(mem.used), _fmt_size(mem.total), mem.percent,
                _fmt_size(du.used), _fmt_size(du.total)),
            "↑%s ↓%s · 开机 %s" % (
                _fmt_size(net.bytes_sent), _fmt_size(net.bytes_recv), up),
        ])
