"""Tests for skills module - improving coverage"""

import tempfile
from pathlib import Path

from src.skills import (
    Skill,
    SkillDiscovery,
    SkillExecutor,
    SkillLoaderImpl,
    SkillMetadata,
)


class TestSkillDiscoveryCoverage:
    """SkillDiscovery 覆盖率测试"""

    def test_discover_with_search_paths(self):
        """测试带搜索路径的发现"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            skill_dir = tmpdir / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n# Test\n")

            discovery = SkillDiscovery([tmpdir])
            skills = discovery.discover()
            assert len(skills) == 1

    def test_discover_single_file(self):
        """测试发现单个文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            skill_file = tmpdir / "SKILL.md"
            skill_file.write_text("---\nname: test\n---\n# Test\n")

            discovery = SkillDiscovery()
            skills = discovery.discover(skill_file)
            assert len(skills) == 1

    def test_discover_with_yaml_metadata(self):
        """测试发现带 YAML 元数据的技能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            skill_dir = tmpdir / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
version: 2.0.0
tags:
  - test
  - example
dependencies:
  - dep1
  - dep2
---

# Test Skill

Content here.
""")

            discovery = SkillDiscovery()
            skills = discovery.discover(tmpdir)
            assert len(skills) == 1
            assert skills[0].name == "test-skill"
            assert skills[0].version == "2.0.0"
            assert "test" in skills[0].tags

    def test_discover_without_metadata(self):
        """测试发现没有元数据的技能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            skill_dir = tmpdir / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# My Skill\n\nContent here.")

            discovery = SkillDiscovery()
            skills = discovery.discover(tmpdir)
            assert len(skills) == 1
            assert skills[0].name == "my-skill"


class TestSkillLoaderImplCoverage:
    """SkillLoaderImpl 覆盖率测试"""

    def test_load_with_cache(self):
        """测试带缓存的加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            skill_dir = tmpdir / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: test\n---\n# Test\n")

            loader = SkillLoaderImpl([tmpdir])
            skill1 = loader.load("test")
            skill2 = loader.load("test")
            assert skill1 is skill2  # 应该返回缓存的实例

    def test_list_skills_empty(self):
        """测试列出空技能"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = SkillLoaderImpl([Path(tmpdir)])
            skills = loader.list_skills()
            assert len(skills) == 0


class TestSkillExecutorCoverage:
    """SkillExecutor 覆盖率测试"""

    def test_execute_with_variables(self):
        """测试带变量的执行"""
        executor = SkillExecutor()
        executor.set_variable("name", "test")
        executor.set_variable("version", "1.0")

        metadata = SkillMetadata(name="test-skill", description="Test")
        skill = Skill(metadata=metadata, content="# {{name}} v{{version}}\n\nContent.")

        result = executor.execute(skill)
        assert "test" in result["output"]
        assert "1.0" in result["output"]

    def test_validate_with_dependencies(self):
        """测试带依赖的验证"""
        executor = SkillExecutor()
        executor.register_function("dep1", lambda: None)

        metadata = SkillMetadata(name="test", description="Test", dependencies=["dep1", "dep2"])
        skill = Skill(metadata=metadata, content="Test")

        errors = executor.validate(skill)
        assert len(errors) == 1
        assert "dep2" in errors[0]

    def test_extract_instructions(self):
        """测试提取指令"""
        executor = SkillExecutor()
        content = """# Test Skill

1. First step
2. Second step
3. Third step

- Item A
- Item B
"""
        instructions = executor._extract_instructions(content)
        assert len(instructions) == 5
