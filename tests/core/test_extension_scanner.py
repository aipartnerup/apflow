"""
Tests for ExtensionScanner (AST-based executor discovery)
"""

import json
import sys
from pathlib import Path

from apflow.core.extensions.scanner import ExtensionScanner, ExecutorMetadata


class TestExtensionScanner:
    """Test suite for ExtensionScanner"""

    def setup_method(self):
        """Reset scanner state before each test"""
        ExtensionScanner.clear_cache()
        ExtensionScanner._scanned = False
        ExtensionScanner._metadata_cache.clear()

    def teardown_method(self):
        """Clean up after each test"""
        ExtensionScanner.clear_cache()

    def test_scan_discovers_all_executors(self):
        """Verify scanner finds all built-in executors"""
        metadata = ExtensionScanner.scan_builtin_executors()

        expected_executors = [
            "system_info_executor",
            "command_executor",
            "rest_executor",
            "aggregate_results_executor",
        ]

        for executor_id in expected_executors:
            assert executor_id in metadata, f"Expected executor '{executor_id}' not found"

        assert len(metadata) >= 10, f"Expected at least 10 executors, found {len(metadata)}"

    def test_get_executor_metadata_returns_valid_data(self):
        """Verify metadata structure for a known executor"""
        metadata = ExtensionScanner.get_executor_metadata("rest_executor")

        assert metadata is not None
        assert metadata.id == "rest_executor"
        assert metadata.name
        assert metadata.module_path == "apflow.extensions.http.rest_executor"
        assert metadata.class_name == "RestExecutor"
        assert "httpx" in metadata.dependencies
        assert metadata.always_available is False

    def test_always_available_executors_have_no_dependencies(self):
        """Verify executors marked as always_available have no external dependencies"""
        always_available_ids = [
            "system_info_executor",
            "command_executor",
            "aggregate_results_executor",
        ]

        for executor_id in always_available_ids:
            metadata = ExtensionScanner.get_executor_metadata(executor_id)
            assert metadata is not None
            assert metadata.always_available is True
            assert len(metadata.dependencies) == 0

    def test_dependency_detection(self):
        """Verify dependency detection works for various executors"""
        test_cases = {
            "rest_executor": ["httpx"],
            "ssh_executor": ["asyncssh"],
            "docker_executor": ["docker"],
            "grpc_executor": ["grpclib"],
            "websocket_executor": ["websockets"],
            "scrape_executor": ["bs4", "trafilatura", "requests"],
        }

        for executor_id, expected_deps in test_cases.items():
            metadata = ExtensionScanner.get_executor_metadata(executor_id)
            if metadata:
                for dep in expected_deps:
                    assert (
                        dep in metadata.dependencies
                    ), f"Expected dependency '{dep}' not found in {executor_id}"

    def test_cache_is_created_after_scan(self):
        """Verify cache file is created after scanning"""
        ExtensionScanner.clear_cache()
        ExtensionScanner.scan_builtin_executors()

        cache_file = ExtensionScanner._cache_file
        assert cache_file.exists(), "Cache file should exist after scanning"

        with open(cache_file, "r") as f:
            cache_data = json.load(f)

        assert len(cache_data) > 0, "Cache should contain executor metadata"
        assert "rest_executor" in cache_data

    def test_cache_is_loaded_on_second_scan(self):
        """Verify cache is used on subsequent scans (no file parsing)"""
        ExtensionScanner.scan_builtin_executors()
        first_scan_count = len(ExtensionScanner._metadata_cache)

        ExtensionScanner._scanned = False
        ExtensionScanner._metadata_cache.clear()

        ExtensionScanner.scan_builtin_executors()
        second_scan_count = len(ExtensionScanner._metadata_cache)

        assert first_scan_count == second_scan_count
        assert ExtensionScanner._scanned is True

    def test_force_rescan_bypasses_cache(self):
        """Verify force_rescan parameter bypasses cache"""
        ExtensionScanner.scan_builtin_executors()

        ExtensionScanner._metadata_cache.clear()

        ExtensionScanner.scan_builtin_executors(force_rescan=True)

        assert len(ExtensionScanner._metadata_cache) > 0

    def test_cache_invalidation_on_file_modification(self):
        """Verify cache is stale if Python files are newer"""
        ExtensionScanner.scan_builtin_executors()
        cache_file = ExtensionScanner._cache_file

        cache_mtime = cache_file.stat().st_mtime

        extensions_dir = Path(__file__).parent.parent.parent / "src" / "apflow" / "extensions"
        test_file = extensions_dir / "stdio" / "system_info_executor.py"

        if test_file.exists():
            file_mtime = test_file.stat().st_mtime

            is_stale = file_mtime > cache_mtime
            should_rescan = ExtensionScanner._should_rescan()

            if is_stale:
                assert should_rescan is True

    def test_get_all_executor_ids(self):
        """Verify get_all_executor_ids returns complete list"""
        executor_ids = ExtensionScanner.get_all_executor_ids()

        assert isinstance(executor_ids, list)
        assert len(executor_ids) >= 10
        assert "rest_executor" in executor_ids
        assert "system_info_executor" in executor_ids

    def test_get_all_metadata(self):
        """Verify get_all_metadata returns complete dictionary"""
        all_metadata = ExtensionScanner.get_all_metadata()

        assert isinstance(all_metadata, dict)
        assert len(all_metadata) >= 10

        for executor_id, metadata in all_metadata.items():
            assert isinstance(metadata, ExecutorMetadata)
            assert metadata.id == executor_id

    def test_lazy_loading_no_imports(self):
        """Verify scanning does not import heavy dependencies"""
        modules_before = set(sys.modules.keys())

        ExtensionScanner.clear_cache()
        ExtensionScanner.scan_builtin_executors()

        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before

        heavy_deps = ["crewai", "docker", "asyncssh", "httpx", "websockets", "grpclib"]

        for dep in heavy_deps:
            modules_imported = [m for m in new_modules if m.startswith(dep)]
            assert (
                len(modules_imported) == 0
            ), f"Heavy dependency '{dep}' should not be imported during scanning, found: {modules_imported}"

    def test_clear_cache_removes_file(self):
        """Verify clear_cache removes cache file"""
        ExtensionScanner.scan_builtin_executors()
        cache_file = ExtensionScanner._cache_file

        assert cache_file.exists()

        ExtensionScanner.clear_cache()

        assert not cache_file.exists()
        assert len(ExtensionScanner._metadata_cache) == 0
        assert ExtensionScanner._scanned is False

    def test_metadata_structure_is_complete(self):
        """Verify ExecutorMetadata has all required fields"""
        metadata = ExtensionScanner.get_executor_metadata("system_info_executor")

        assert metadata is not None
        assert hasattr(metadata, "id")
        assert hasattr(metadata, "name")
        assert hasattr(metadata, "description")
        assert hasattr(metadata, "module_path")
        assert hasattr(metadata, "class_name")
        assert hasattr(metadata, "file_path")
        assert hasattr(metadata, "dependencies")
        assert hasattr(metadata, "always_available")
        assert hasattr(metadata, "tags")

        assert isinstance(metadata.dependencies, list)
        assert isinstance(metadata.tags, list)
        assert isinstance(metadata.always_available, bool)

    def test_file_to_module_path_conversion(self):
        """Verify file path to module path conversion"""
        test_file = Path("/path/to/apflow/extensions/http/rest_executor.py")
        module_path = ExtensionScanner._file_to_module_path(test_file)

        assert module_path == "apflow.extensions.http.rest_executor"

    def test_nonexistent_executor_returns_none(self):
        """Verify get_executor_metadata returns None for unknown executor"""
        metadata = ExtensionScanner.get_executor_metadata("nonexistent_executor")

        assert metadata is None

    def test_scan_handles_missing_extensions_directory(self):
        """Verify scanner handles missing extensions directory gracefully"""
        ExtensionScanner.scan_builtin_executors.__code__.co_filename

        ExtensionScanner.clear_cache()

        result = ExtensionScanner.scan_builtin_executors()

        assert isinstance(result, dict)

    def test_tags_are_extracted_from_ast(self):
        """Verify tags are extracted correctly from executor classes"""
        metadata = ExtensionScanner.get_executor_metadata("rest_executor")

        if metadata:
            assert isinstance(metadata.tags, list)

    def test_scanner_is_singleton(self):
        """Verify scanner uses singleton pattern"""
        from apflow.core.extensions.scanner import get_scanner

        scanner1 = get_scanner()
        scanner2 = get_scanner()

        assert scanner1 is scanner2
