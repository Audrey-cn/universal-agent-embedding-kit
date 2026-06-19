"""Tests for optimization and extensions"""

import tempfile
from pathlib import Path

import pytest

from src.extensions import (
    ReportGenerator,
    TaskTemplate,
    TemplateLibrary,
    WorkflowReport,
)
from src.optimization import (
    BatchProcessor,
    Cache,
    ConnectionPool,
    PerformanceMetrics,
    PerformanceProfiler,
)


class TestPerformanceMetrics:
    """PerformanceMetrics 测试"""

    def test_update(self):
        """测试更新指标"""
        metrics = PerformanceMetrics(function_name="test")
        metrics.update(0.1)
        metrics.update(0.2)
        metrics.update(0.3)

        assert metrics.call_count == 3
        assert metrics.total_time == pytest.approx(0.6)
        assert metrics.min_time == pytest.approx(0.1)
        assert metrics.max_time == pytest.approx(0.3)
        assert metrics.avg_time == pytest.approx(0.2)

    def test_to_dict(self):
        """测试转换为字典"""
        metrics = PerformanceMetrics(function_name="test")
        metrics.update(0.1)

        d = metrics.to_dict()
        assert d["function"] == "test"
        assert d["calls"] == 1
        assert d["total_ms"] == pytest.approx(100.0)


class TestPerformanceProfiler:
    """PerformanceProfiler 测试"""

    def test_profile(self):
        """测试性能分析"""
        profiler = PerformanceProfiler()

        @profiler.profile
        def test_func():
            return 42

        result = test_func()
        assert result == 42

        metrics = profiler.get_metrics()
        assert len(metrics) == 1
        assert metrics[0]["function"] == "test_func"

    def test_get_summary(self):
        """测试获取摘要"""
        profiler = PerformanceProfiler()

        @profiler.profile
        def func1():
            pass

        @profiler.profile
        def func2():
            pass

        func1()
        func2()

        summary = profiler.get_summary()
        assert summary["total_functions"] == 2
        assert summary["total_calls"] == 2

    def test_reset(self):
        """测试重置"""
        profiler = PerformanceProfiler()

        @profiler.profile
        def test_func():
            pass

        test_func()
        assert len(profiler.metrics) == 1

        profiler.reset()
        assert len(profiler.metrics) == 0


class TestCache:
    """Cache 测试"""

    def test_get_set(self):
        """测试获取和设置"""
        cache = Cache(max_size=10, ttl=1.0)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_ttl(self):
        """测试过期"""
        import time

        cache = Cache(max_size=10, ttl=0.1)
        cache.set("key1", "value1")
        time.sleep(0.2)
        assert cache.get("key1") is None

    def test_max_size(self):
        """测试最大大小"""
        cache = Cache(max_size=2, ttl=1.0)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        assert cache.size() == 2
        assert cache.get("key1") is None  # 被淘汰

    def test_clear(self):
        """测试清除"""
        cache = Cache(max_size=10, ttl=1.0)
        cache.set("key1", "value1")
        cache.clear()
        assert cache.size() == 0


class TestBatchProcessor:
    """BatchProcessor 测试"""

    def test_add_and_flush(self):
        """测试添加和刷新"""
        processed = []
        processor = BatchProcessor(batch_size=2)
        processor.set_processor(lambda items: processed.extend(items))

        processor.add(1)
        assert len(processed) == 0

        processor.add(2)
        assert len(processed) == 2
        assert processed == [1, 2]

    def test_flush_empty(self):
        """测试刷新空缓冲区"""
        processor = BatchProcessor(batch_size=10)
        processor.flush()  # 不应该抛出异常


class TestConnectionPool:
    """ConnectionPool 测试"""

    def test_acquire_release(self):
        """测试获取和释放"""
        pool = ConnectionPool(max_size=2)
        conn = pool.acquire()
        assert conn is None  # 空池

        pool._pool.append("conn1")
        conn = pool.acquire()
        assert conn == "conn1"

        pool.release(conn)
        assert pool.available() == 1

    def test_size(self):
        """测试大小"""
        pool = ConnectionPool(max_size=5)
        pool._pool.extend(["conn1", "conn2"])
        assert pool.size() == 2
        assert pool.available() == 2


class TestTaskTemplate:
    """TaskTemplate 测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        template = TaskTemplate(
            name="test",
            description="Test template",
            tasks=[{"id": "t1", "name": "Task 1"}],
        )
        d = template.to_dict()
        assert d["name"] == "test"
        assert len(d["tasks"]) == 1

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "name": "test",
            "description": "Test template",
            "tasks": [{"id": "t1", "name": "Task 1"}],
        }
        template = TaskTemplate.from_dict(data)
        assert template.name == "test"

    def test_save_load(self):
        """测试保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "template.json"
            template = TaskTemplate(
                name="test",
                description="Test template",
                tasks=[{"id": "t1", "name": "Task 1"}],
            )
            template.save(path)

            loaded = TaskTemplate.load(path)
            assert loaded.name == "test"
            assert len(loaded.tasks) == 1


class TestTemplateLibrary:
    """TemplateLibrary 测试"""

    def test_builtin_templates(self):
        """测试内置模板"""
        library = TemplateLibrary()
        templates = library.list_templates()
        assert len(templates) >= 4

    def test_get_template(self):
        """测试获取模板"""
        library = TemplateLibrary()
        template = library.get("feature-development")
        assert template is not None
        assert template.name == "feature-development"

    def test_add_remove(self):
        """测试添加和删除"""
        library = TemplateLibrary()
        template = TaskTemplate(name="custom", description="Custom", tasks=[])
        library.add(template)
        assert library.get("custom") is not None

        library.remove("custom")
        assert library.get("custom") is None

    def test_save_to_directory(self):
        """测试保存到目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            library = TemplateLibrary()
            library.save_to_directory(Path(tmpdir))

            # 重新加载
            library2 = TemplateLibrary(Path(tmpdir))
            assert len(library2.templates) >= 4


class TestWorkflowReport:
    """WorkflowReport 测试"""

    def test_duration(self):
        """测试持续时间"""
        report = WorkflowReport(
            workflow_id="test",
            start_time=1.0,
            end_time=3.5,
            tasks=[],
            success=True,
        )
        assert report.duration == pytest.approx(2.5)

    def test_to_dict(self):
        """测试转换为字典"""
        report = WorkflowReport(
            workflow_id="test",
            start_time=1.0,
            end_time=3.5,
            tasks=[{"id": "t1", "status": "completed"}],
            success=True,
        )
        d = report.to_dict()
        assert d["workflow_id"] == "test"
        assert d["success"] is True

    def test_save(self):
        """测试保存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            report = WorkflowReport(
                workflow_id="test",
                start_time=1.0,
                end_time=3.5,
                tasks=[],
                success=True,
            )
            report.save(path)
            assert path.exists()


class TestReportGenerator:
    """ReportGenerator 测试"""

    def test_generate_summary(self):
        """测试生成摘要"""
        generator = ReportGenerator()
        reports = [
            WorkflowReport(
                workflow_id="w1",
                start_time=0.0,
                end_time=1.0,
                tasks=[],
                success=True,
            ),
            WorkflowReport(
                workflow_id="w2",
                start_time=0.0,
                end_time=2.0,
                tasks=[],
                success=False,
            ),
        ]

        summary = generator.generate_summary(reports)
        assert summary["total_workflows"] == 2
        assert summary["success"] == 1
        assert summary["failed"] == 1
        assert summary["success_rate"] == 0.5
