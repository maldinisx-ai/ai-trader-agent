# -*- coding: utf-8 -*-
"""
股票数据下载监视器

实时显示下载进度和状态
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def format_size(bytes_size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


class DownloadMonitor:
    """下载监视器"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.progress_file = self.data_dir / "download_progress.json"

        # 状态追踪
        self.start_time = None
        self.last_stats = None

    def get_progress(self) -> dict:
        """获取进度数据"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "downloaded": [],
            "failed": [],
            "last_update": None
        }

    def get_file_stats(self) -> dict:
        """获取文件统计"""
        stocks_dir = self.data_dir / "stocks"
        if not stocks_dir.exists():
            return {
                "total_files": 0,
                "total_size": 0,
                "avg_rows": 0,
                "recent_files": []
            }

        files = list(stocks_dir.glob("*.csv"))
        total_size = sum(f.stat().st_size for f in files)

        # 计算平均行数
        total_rows = 0
        recent_files = []

        for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    rows = sum(1 for _ in file) - 1  # 减去表头
                    total_rows += rows
                    recent_files.append({
                        "name": f.name,
                        "rows": rows,
                        "size": f.stat().st_size
                    })
            except:
                pass

        avg_rows = total_rows // len(files) if files else 0

        return {
            "total_files": len(files),
            "total_size": total_size,
            "avg_rows": avg_rows,
            "recent_files": recent_files
        }

    def calculate_speed(self) -> dict:
        """计算下载速度"""
        now = datetime.now()
        progress = self.get_progress()

        if self.last_stats is None:
            self.last_stats = {
                "time": now,
                "downloaded_count": len(progress.get("downloaded", []))
            }
            return {"per_second": 0, "per_minute": 0, "eta": None}

        if self.start_time is None:
            self.start_time = now

        time_delta = (now - self.last_stats["time"]).total_seconds()
        if time_delta < 1:
            return self._last_speed

        downloaded_count = len(progress.get("downloaded", []))
        count_delta = downloaded_count - self.last_stats["downloaded_count"]

        if count_delta == 0:
            speed_per_second = 0
        else:
            speed_per_second = count_delta / time_delta

        speed_per_minute = speed_per_second * 60

        # 估算剩余时间
        failed_count = len(progress.get("failed", []))
        if speed_per_second > 0 and failed_count > 0:
            eta = failed_count / speed_per_second
        else:
            eta = None

        self.last_stats = {
            "time": now,
            "downloaded_count": downloaded_count
        }

        self._last_speed = {
            "per_second": speed_per_second,
            "per_minute": speed_per_minute,
            "eta": eta
        }

        return self._last_speed

    def display(self):
        """显示状态"""
        clear_screen()

        progress = self.get_progress()
        file_stats = self.get_file_stats()
        speed = self.calculate_speed()

        downloaded_count = len(progress.get("downloaded", []))
        failed_count = len(progress.get("failed", []))

        print("=" * 70)
        print(" 📊 股票数据下载监视器")
        print("=" * 70)

        # 进度条
        total = downloaded_count + failed_count
        if total > 0:
            success_rate = downloaded_count / total * 100
        else:
            success_rate = 100

        bar_width = 40
        filled = int(bar_width * success_rate / 100)
        bar = "█" * filled + "░" * (bar_width - filled)

        print(f"\n 进度: [{bar}] {success_rate:.1f}%")
        print(f"     ✓ 已下载: {downloaded_count} 只")
        print(f"     ✗ 失败: {failed_count} 只")

        # 速度
        print(f"\n 🚀 速度:")
        print(f"     {speed['per_second']:.2f} 股/秒")
        print(f"     {speed['per_minute']:.2f} 股/分钟")

        if speed['eta']:
            print(f"     ⏱ 预计剩余: {format_duration(speed['eta'])}")

        # 文件统计
        print(f"\n 📁 数据文件:")
        print(f"     总数: {file_stats['total_files']} 个")
        print(f"     大小: {format_size(file_stats['total_size'])}")
        print(f"     平均: {file_stats['avg_rows']} 行/文件")

        # 最近文件
        if file_stats['recent_files']:
            print(f"\n 📋 最近下载:")
            for f in file_stats['recent_files'][:5]:
                print(f"     {f['name']}: {f['rows']} 行")

        # 时间信息
        print(f"\n ⏰ 时间信息:")
        last_update = progress.get("last_update")
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update)
                time_ago = (datetime.now() - last_time).total_seconds()
                print(f"     最后更新: {format_duration(time_ago)} 前")
            except:
                print(f"     最后更新: {last_update}")

        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            print(f"     运行时间: {format_duration(elapsed)}")

        # 失败列表
        if failed_count > 0:
            print(f"\n ⚠️ 失败股票 (显示前10个):")
            failed_list = progress.get("failed", [])
            for code in failed_list[:10]:
                print(f"     {code}")
            if len(failed_list) > 10:
                print(f"     ... 还有 {len(failed_list) - 10} 个")

        print("\n" + "=" * 70)
        print(" 按 Ctrl+C 退出监视器")
        print("=" * 70)

    def run(self, refresh_interval: float = 1.0):
        """运行监视器"""
        print("启动下载监视器... (按 Ctrl+C 退出)")
        time.sleep(1)

        try:
            while True:
                self.display()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\n监视器已停止")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="股票数据下载监视器")
    parser.add_argument("--data-dir", default="data",
                        help="数据目录路径")
    parser.add_argument("--refresh", type=float, default=1.0,
                        help="刷新间隔（秒）")

    args = parser.parse_args()

    monitor = DownloadMonitor(data_dir=args.data_dir)
    monitor.run(refresh_interval=args.refresh)


if __name__ == "__main__":
    main()