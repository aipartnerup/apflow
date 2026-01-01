"""
Docker executor feature

This feature provides Docker container execution capabilities for tasks.
Useful for running commands in isolated Docker containers.
"""

from apflow.extensions.docker.docker_executor import DockerExecutor

__all__ = ["DockerExecutor"]

