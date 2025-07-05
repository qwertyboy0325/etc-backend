#!/usr/bin/env python3
"""
系統測試腳本
測試 ETC 點雲標注系統的基礎功能
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict

import httpx


class SystemTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = None
        self.test_results = []

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def test_endpoint(
        self, endpoint: str, expected_status: int = 200, test_name: str = None
    ) -> Dict[str, Any]:
        """測試單個端點"""
        test_name = test_name or f"Test {endpoint}"
        url = f"{self.base_url}{endpoint}"

        try:
            print(f"🔍 Testing: {test_name}")
            print(f"   URL: {url}")

            response = await self.client.get(url)

            # 檢查狀態碼
            success = response.status_code == expected_status

            result = {
                "test_name": test_name,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": response.status_code,
                "success": success,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if success:
                print(
                    f"   ✅ Status: {response.status_code} (Expected: {expected_status})"
                )
                print(f"   ⏱️  Response time: {result['response_time_ms']:.2f}ms")

                # 嘗試解析JSON響應
                try:
                    response_data = response.json()
                    result["response_data"] = response_data
                    print(f"   📄 Response preview: {str(response_data)[:100]}...")
                except:
                    result["response_data"] = response.text[:200]
                    print(f"   📄 Response preview: {response.text[:100]}...")
            else:
                print(
                    f"   ❌ Status: {response.status_code} (Expected: {expected_status})"
                )
                result["error"] = response.text

            self.test_results.append(result)
            print()

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            result = {
                "test_name": test_name,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": "ERROR",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
            self.test_results.append(result)
            print()

        return result

    async def run_all_tests(self):
        """運行所有測試"""
        print("🚀 開始 ETC 點雲標注系統測試")
        print("=" * 60)

        # 測試端點列表
        test_endpoints = [
            ("/health", 200, "基礎健康檢查"),
            ("/api/v1/system/health", 200, "系統健康檢查"),
            ("/api/v1/system/database/status", 200, "數據庫狀態檢查"),
            ("/api/v1/system/models/validate", 200, "模型驗證"),
            ("/api/v1/system/info", 200, "系統信息"),
            ("/api/v1/system/ping", 200, "Ping 測試"),
            ("/api/v1/", 200, "API v1 根端點"),
            ("/api/v1/test", 200, "測試端點"),
            ("/", 200, "根端點"),
        ]

        # 運行所有測試
        for endpoint, expected_status, test_name in test_endpoints:
            await self.test_endpoint(endpoint, expected_status, test_name)

        # 生成測試報告
        await self.generate_report()

    async def generate_report(self):
        """生成測試報告"""
        print("📊 測試報告")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests

        print(f"總測試數: {total_tests}")
        print(f"通過測試: {passed_tests}")
        print(f"失敗測試: {failed_tests}")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
        print()

        # 詳細結果
        if failed_tests > 0:
            print("❌ 失敗的測試:")
            for result in self.test_results:
                if not result["success"]:
                    print(
                        f"  - {result['test_name']}: {result.get('error', 'Status code mismatch')}"
                    )
            print()

        # 性能統計
        response_times = [
            r.get("response_time_ms", 0) for r in self.test_results if r["success"]
        ]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)

            print(f"⏱️  性能統計:")
            print(f"  平均響應時間: {avg_response_time:.2f}ms")
            print(f"  最大響應時間: {max_response_time:.2f}ms")
            print(f"  最小響應時間: {min_response_time:.2f}ms")
            print()

        # 保存詳細報告
        report_data = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": passed_tests / total_tests * 100,
                "test_date": datetime.utcnow().isoformat(),
            },
            "detailed_results": self.test_results,
        }

        with open("test_report.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"📁 詳細報告已保存至: test_report.json")

        # 返回測試結果
        return passed_tests == total_tests


async def main():
    """主測試函數"""
    print("🎯 ETC 點雲標注系統 - 系統測試")
    print(f"📅 測試時間: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    try:
        async with SystemTester() as tester:
            success = await tester.run_all_tests()

            if success:
                print("🎉 所有測試通過！系統運行正常。")
                sys.exit(0)
            else:
                print("⚠️  部分測試失敗，請查看上述報告。")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n❌ 測試被用戶中斷")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 測試運行失敗: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
