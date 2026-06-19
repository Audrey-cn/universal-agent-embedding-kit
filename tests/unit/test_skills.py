"""Tests for skill loader"""

import tempfile
from pathlib import Path

import pytest

from src.skills import (
    Skill,
    SkillDiscovery,
    SkillExecutor,
    SkillLoaderImpl,
    SkillMetadata,
    SkillStatus,
)


# 测试辅助函数
def create_skill_file(path: Path, name: str, description: str, content: str) -> Path:
    """创建技能文件"""
    skill_dir = path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(f"""---
name: {name}
description: {description}
version: 1.0.0
tags:
  - test
  - example
---

# {name}

{content}
""")
    return skill_file


class TestSkillMetadata:
    """测试 SkillMetadata"""

    def test_metadata_creation(self):
        """测试元数据创建"""
        metadata = SkillMetadata(
            name="test-skill",
            description="A test skill",
            version="1.0.0",
        )
        assert metadata.name == "test-skill"
        assert metadata.description == "A test skill"
        assert metadata.version == "1.0.0"

    def test_metadata_from_dict(self):
        """测试从字典创建元数据"""
        data = {
            "name": "test-skill",
            "description": "A test skill",
            "version": "2.0.0",
            "tags": ["test", "example"],
        }
        metadata = SkillMetadata.from_dict(data)
        assert metadata.name == "test-skill"
        assert metadata.version == "2.0.0"
        assert "test" in metadata.tags


class TestSkill:
    """测试 Skill"""

    def test_skill_creation(self):
        """测试技能创建"""
        metadata = SkillMetadata(name="test-skill", description="A test skill")
        skill = Skill(metadata=metadata, content="# Test Skill\n\nThis is a test.")
        assert skill.metadata.name == "test-skill"
        assert skill.status == SkillStatus.DISCOVERED

    def test_skill_invalid_name(self):
        """测试无效技能名称"""
        metadata = SkillMetadata(name="", description="A test skill")
        with pytest.raises(ValueError, match="Skill name cannot be empty"):
            Skill(metadata=metadata, content="Test")

    def test_skill_reset(self):
        """测试技能重置"""
        metadata = SkillMetadata(name="test-skill", description="A test skill")
        skill = Skill(metadata=metadata, content="Test")
        skill.status = SkillStatus.COMPLETED
        skill.result = "test"

        skill.reset()
        assert skill.status == SkillStatus.DISCOVERED
        assert skill.result is None


class TestSkillDiscovery:
    """测试 SkillDiscovery"""

    def test_discover_in_directory(self):
        """测试在目录中发现技能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # 创建测试技能
            create_skill_file(tmpdir, "skill1", "Skill 1", "Content 1")
            create_skill_file(tmpdir, "skill2", "Skill 2", "Content 2")

            discovery = SkillDiscovery()
            skills = discovery.discover(tmpdir)

            assert len(skills) == 2
            names = [s.name for s in skills]
            assert "skill1" in names
            assert "skill2" in names

    def test_discover_nonexistent_path(self):
        """测试发现不存在的路径"""
        discovery = SkillDiscovery()
        skills = discovery.discover(Path("/nonexistent/path"))
        assert len(skills) == 0

    def test_discover_empty_directory(self):
        """测试发现空目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery = SkillDiscovery()
            skills = discovery.discover(Path(tmpdir))
            assert len(skills) == 0


class TestSkillLoaderImpl:
    """测试 SkillLoaderImpl"""

    def test_load_skill(self):
        """测试加载技能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            create_skill_file(tmpdir, "test-skill", "A test skill", "Test content")

            loader = SkillLoaderImpl([tmpdir])
            skill = loader.load("test-skill")

            assert skill.metadata.name == "test-skill"
            assert skill.status == SkillStatus.LOADED
            assert "Test content" in skill.content

    def test_load_nonexistent_skill(self):
        """测试加载不存在的技能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = SkillLoaderImpl([Path(tmpdir)])
            with pytest.raises(KeyError, match="Skill 'nonexistent' not found"):
                loader.load("nonexistent")

    def test_list_skills(self):
        """测试列出技能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            create_skill_file(tmpdir, "skill1", "Skill 1", "Content 1")
            create_skill_file(tmpdir, "skill2", "Skill 2", "Content 2")

            loader = SkillLoaderImpl([tmpdir])
            skills = loader.list_skills()

            assert len(skills) == 2

    def test_reload_skill(self):
        """测试重新加载技能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            skill_path = create_skill_file(tmpdir, "test-skill", "A test skill", "Original content")

            loader = SkillLoaderImpl([tmpdir])
            skill1 = loader.load("test-skill")
            assert "Original content" in skill1.content

            # 修改技能文件
            skill_path.write_text("""---
name: test-skill
description: A test skill
---

# Test Skill

Updated content
""")

            # 重新加载
            skill2 = loader.reload("test-skill")
            assert "Updated content" in skill2.content

    def test_clear_cache(self):
        """测试清除缓存"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            create_skill_file(tmpdir, "test-skill", "A test skill", "Test content")

            loader = SkillLoaderImpl([tmpdir])
            loader.load("test-skill")

            assert "test-skill" in loader._cache

            loader.clear_cache()
            assert len(loader._cache) == 0


class TestSkillExecutor:
    """测试 SkillExecutor"""

    def test_execute_skill(self):
        """测试执行技能"""
        metadata = SkillMetadata(name="test-skill", description="A test skill")
        skill = Skill(metadata=metadata, content="# Test Skill\n\n1. Step one\n2. Step two")

        executor = SkillExecutor()
        result = executor.execute(skill)

        assert skill.status == SkillStatus.COMPLETED
        assert "instructions" in result
        assert len(result["instructions"]) == 2

    def test_execute_with_context(self):
        """测试带上下文执行"""
        metadata = SkillMetadata(name="test-skill", description="A test skill")
        skill = Skill(metadata=metadata, content="# {{name}}\n\nHello {{user}}!")

        executor = SkillExecutor()
        result = executor.execute(skill, context={"name": "My Skill", "user": "Alice"})

        assert "My Skill" in result["output"]
        assert "Alice" in result["output"]

    def test_validate_skill(self):
        """测试验证技能"""
        metadata = SkillMetadata(name="test-skill", description="A test skill")
        skill = Skill(metadata=metadata, content="Test content")

        executor = SkillExecutor()
        errors = executor.validate(skill)

        assert len(errors) == 0

    def test_validate_empty_skill(self):
        """测试验证空技能"""
        metadata = SkillMetadata(name="empty-skill", description="Empty")
        skill = Skill(metadata=metadata, content="")

        executor = SkillExecutor()
        errors = executor.validate(skill)

        assert len(errors) > 0
        assert "Skill content is empty" in errors

    def test_set_variable(self):
        """测试设置变量"""
        executor = SkillExecutor()
        executor.set_variable("name", "test")
        assert executor.variables["name"] == "test"

    def test_register_function(self):
        """测试注册函数"""
        executor = SkillExecutor()
        executor.register_function("test_func", lambda: "test")
        assert "test_func" in executor.functions
