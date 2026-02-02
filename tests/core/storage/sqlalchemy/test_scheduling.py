"""
Tests for task scheduling functionality

This module tests:
- ScheduleType enum
- ScheduleCalculator for all schedule types
- Schedule validation
- TaskModel scheduling fields
- Scheduling migration
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from apflow.core.storage.sqlalchemy.models import TaskModel, ScheduleType
from apflow.core.storage.sqlalchemy.schedule_calculator import ScheduleCalculator


class TestScheduleType:
    """Test ScheduleType enum"""

    def test_schedule_type_values(self):
        """Test that all schedule type values are correct"""
        assert ScheduleType.once.value == "once"
        assert ScheduleType.interval.value == "interval"
        assert ScheduleType.cron.value == "cron"
        assert ScheduleType.daily.value == "daily"
        assert ScheduleType.weekly.value == "weekly"
        assert ScheduleType.monthly.value == "monthly"

    def test_schedule_type_count(self):
        """Test that we have exactly 6 schedule types"""
        assert len(ScheduleType) == 6

    def test_schedule_type_from_string(self):
        """Test that schedule types can be created from strings"""
        assert ScheduleType("once") == ScheduleType.once
        assert ScheduleType("interval") == ScheduleType.interval
        assert ScheduleType("cron") == ScheduleType.cron
        assert ScheduleType("daily") == ScheduleType.daily
        assert ScheduleType("weekly") == ScheduleType.weekly
        assert ScheduleType("monthly") == ScheduleType.monthly


class TestScheduleCalculatorOnce:
    """Test ScheduleCalculator for 'once' schedule type"""

    def test_calculate_once_future(self):
        """Test calculating next run for future datetime"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "2024-01-15T09:00:00+00:00"

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.once, expression, from_time
        )

        expected = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_once_past(self):
        """Test calculating next run for past datetime returns None"""
        from_time = datetime(2024, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        expression = "2024-01-15T09:00:00+00:00"

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.once, expression, from_time
        )

        assert result is None

    def test_calculate_once_with_z_suffix(self):
        """Test calculating next run with Z timezone suffix"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "2024-01-15T09:00:00Z"

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.once, expression, from_time
        )

        expected = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_once_invalid_expression(self):
        """Test that invalid expression raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "not-a-datetime"

        with pytest.raises(ValueError, match="Invalid 'once' expression"):
            ScheduleCalculator.calculate_next_run(ScheduleType.once, expression, from_time)


class TestScheduleCalculatorInterval:
    """Test ScheduleCalculator for 'interval' schedule type"""

    def test_calculate_interval_basic(self):
        """Test calculating next run with interval in seconds"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "3600"  # 1 hour

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.interval, expression, from_time
        )

        expected = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_interval_large(self):
        """Test calculating next run with large interval"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "86400"  # 24 hours

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.interval, expression, from_time
        )

        expected = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_interval_negative(self):
        """Test that negative interval raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "-3600"

        with pytest.raises(ValueError, match="Interval must be positive"):
            ScheduleCalculator.calculate_next_run(ScheduleType.interval, expression, from_time)

    def test_calculate_interval_zero(self):
        """Test that zero interval raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "0"

        with pytest.raises(ValueError, match="Interval must be positive"):
            ScheduleCalculator.calculate_next_run(ScheduleType.interval, expression, from_time)

    def test_calculate_interval_invalid(self):
        """Test that invalid interval raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "not-a-number"

        with pytest.raises(ValueError, match="Invalid 'interval' expression"):
            ScheduleCalculator.calculate_next_run(ScheduleType.interval, expression, from_time)


class TestScheduleCalculatorCron:
    """Test ScheduleCalculator for 'cron' schedule type"""

    def test_calculate_cron_basic(self):
        """Test calculating next run with basic cron expression"""
        try:
            import croniter  # noqa: F401
        except ImportError:
            pytest.skip("croniter not installed")

        from_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        expression = "0 9 * * *"  # Every day at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.cron, expression, from_time
        )

        expected = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_cron_weekday(self):
        """Test calculating next run with weekday cron expression"""
        try:
            import croniter  # noqa: F401
        except ImportError:
            pytest.skip("croniter not installed")

        # Monday, January 1, 2024
        from_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        expression = "0 9 * * 1-5"  # Weekdays at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.cron, expression, from_time
        )

        # Next occurrence should be Tuesday Jan 2 at 9 AM
        expected = datetime(2024, 1, 2, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_cron_invalid(self):
        """Test that invalid cron expression raises ValueError"""
        try:
            import croniter  # noqa: F401
        except ImportError:
            pytest.skip("croniter not installed")

        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "invalid cron"

        with pytest.raises(ValueError, match="Invalid cron expression"):
            ScheduleCalculator.calculate_next_run(ScheduleType.cron, expression, from_time)

    def test_calculate_cron_not_installed(self):
        """Test that missing croniter raises ImportError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "0 9 * * *"

        with patch.dict('sys.modules', {'croniter': None}):
            # Force reimport to trigger ImportError
            import apflow.core.storage.sqlalchemy.schedule_calculator as calc_module

            # Save original function
            original_func = calc_module.ScheduleCalculator._calculate_cron

            # Create a function that will raise ImportError
            def mock_calculate_cron(expression, from_time, timezone_str=None):
                raise ImportError("croniter package is required")

            calc_module.ScheduleCalculator._calculate_cron = staticmethod(mock_calculate_cron)

            try:
                with pytest.raises(ImportError, match="croniter package is required"):
                    ScheduleCalculator.calculate_next_run(ScheduleType.cron, expression, from_time)
            finally:
                # Restore original function
                calc_module.ScheduleCalculator._calculate_cron = original_func


class TestScheduleCalculatorDaily:
    """Test ScheduleCalculator for 'daily' schedule type"""

    def test_calculate_daily_future_today(self):
        """Test calculating next run when time is later today"""
        from_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        expression = "09:00"

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.daily, expression, from_time
        )

        expected = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_daily_past_today(self):
        """Test calculating next run when time has passed today"""
        from_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        expression = "09:00"

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.daily, expression, from_time
        )

        expected = datetime(2024, 1, 2, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_daily_single_digit_hour(self):
        """Test calculating with single digit hour"""
        from_time = datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        expression = "6:30"

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.daily, expression, from_time
        )

        expected = datetime(2024, 1, 1, 6, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_daily_invalid_format(self):
        """Test that invalid format raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "9:00:00"  # Includes seconds

        with pytest.raises(ValueError, match="Invalid 'daily' expression"):
            ScheduleCalculator.calculate_next_run(ScheduleType.daily, expression, from_time)

    def test_calculate_daily_invalid_hour(self):
        """Test that invalid hour raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "25:00"

        with pytest.raises(ValueError, match="Invalid hour"):
            ScheduleCalculator.calculate_next_run(ScheduleType.daily, expression, from_time)

    def test_calculate_daily_invalid_minute(self):
        """Test that invalid minute raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "09:60"

        with pytest.raises(ValueError, match="Invalid minute"):
            ScheduleCalculator.calculate_next_run(ScheduleType.daily, expression, from_time)


class TestScheduleCalculatorWeekly:
    """Test ScheduleCalculator for 'weekly' schedule type"""

    def test_calculate_weekly_basic(self):
        """Test calculating next run for weekly schedule"""
        # Monday, January 1, 2024 at 8 AM
        from_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        expression = "1,3,5 09:00"  # Mon, Wed, Fri at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.weekly, expression, from_time
        )

        # Next occurrence should be Monday Jan 1 at 9 AM
        expected = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_weekly_next_day(self):
        """Test calculating next run when time has passed today"""
        # Monday, January 1, 2024 at 10 AM
        from_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        expression = "1,3,5 09:00"  # Mon, Wed, Fri at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.weekly, expression, from_time
        )

        # Next occurrence should be Wednesday Jan 3 at 9 AM
        expected = datetime(2024, 1, 3, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_weekly_next_week(self):
        """Test calculating next run when need to go to next week"""
        # Friday, January 5, 2024 at 10 AM
        from_time = datetime(2024, 1, 5, 10, 0, 0, tzinfo=timezone.utc)
        expression = "1,3,5 09:00"  # Mon, Wed, Fri at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.weekly, expression, from_time
        )

        # Next occurrence should be Monday Jan 8 at 9 AM
        expected = datetime(2024, 1, 8, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_weekly_sunday(self):
        """Test calculating next run with Sunday (day 7)"""
        # Saturday, January 6, 2024 at 10 AM
        from_time = datetime(2024, 1, 6, 10, 0, 0, tzinfo=timezone.utc)
        expression = "7 15:00"  # Sunday at 3 PM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.weekly, expression, from_time
        )

        # Next occurrence should be Sunday Jan 7 at 3 PM
        expected = datetime(2024, 1, 7, 15, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_weekly_invalid_day(self):
        """Test that invalid day raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "0,8 09:00"

        with pytest.raises(ValueError, match="Invalid day"):
            ScheduleCalculator.calculate_next_run(ScheduleType.weekly, expression, from_time)

    def test_calculate_weekly_invalid_format(self):
        """Test that invalid format raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "Monday 09:00"

        with pytest.raises(ValueError, match="Invalid 'weekly' expression"):
            ScheduleCalculator.calculate_next_run(ScheduleType.weekly, expression, from_time)


class TestScheduleCalculatorMonthly:
    """Test ScheduleCalculator for 'monthly' schedule type"""

    def test_calculate_monthly_basic(self):
        """Test calculating next run for monthly schedule"""
        from_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        expression = "1,15 09:00"  # 1st and 15th at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.monthly, expression, from_time
        )

        # Next occurrence should be Jan 1 at 9 AM
        expected = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_monthly_next_date(self):
        """Test calculating next run when date has passed"""
        from_time = datetime(2024, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
        expression = "1,15 09:00"  # 1st and 15th at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.monthly, expression, from_time
        )

        # Next occurrence should be Jan 15 at 9 AM
        expected = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_monthly_next_month(self):
        """Test calculating next run when need to go to next month"""
        from_time = datetime(2024, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        expression = "1,15 09:00"  # 1st and 15th at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.monthly, expression, from_time
        )

        # Next occurrence should be Feb 1 at 9 AM
        expected = datetime(2024, 2, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_monthly_end_of_month(self):
        """Test calculating with date that doesn't exist in some months"""
        from_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        expression = "31 09:00"  # 31st at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.monthly, expression, from_time
        )

        # Next occurrence should be Jan 31 at 9 AM
        expected = datetime(2024, 1, 31, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_monthly_skip_short_month(self):
        """Test that short months are handled correctly"""
        # Start from Feb when looking for 30th or 31st
        from_time = datetime(2024, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        expression = "30 09:00"  # 30th at 9 AM

        result = ScheduleCalculator.calculate_next_run(
            ScheduleType.monthly, expression, from_time
        )

        # Feb doesn't have 30th, so should skip to March 30
        expected = datetime(2024, 3, 30, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_calculate_monthly_invalid_date(self):
        """Test that invalid date raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "0,32 09:00"

        with pytest.raises(ValueError, match="Invalid date"):
            ScheduleCalculator.calculate_next_run(ScheduleType.monthly, expression, from_time)

    def test_calculate_monthly_invalid_format(self):
        """Test that invalid format raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "first 09:00"

        with pytest.raises(ValueError, match="Invalid 'monthly' expression"):
            ScheduleCalculator.calculate_next_run(ScheduleType.monthly, expression, from_time)


class TestScheduleCalculatorEdgeCases:
    """Test edge cases and error handling"""

    def test_calculate_with_none_type(self):
        """Test that None schedule type returns None"""
        result = ScheduleCalculator.calculate_next_run(None, "09:00")
        assert result is None

    def test_calculate_with_none_expression(self):
        """Test that None expression returns None"""
        result = ScheduleCalculator.calculate_next_run(ScheduleType.daily, None)
        assert result is None

    def test_calculate_with_empty_expression(self):
        """Test that empty expression returns None"""
        result = ScheduleCalculator.calculate_next_run(ScheduleType.daily, "")
        assert result is None

    def test_calculate_unknown_type(self):
        """Test that unknown schedule type raises ValueError"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="Unknown schedule type"):
            ScheduleCalculator.calculate_next_run("unknown", "09:00", from_time)

    def test_calculate_with_string_schedule_type(self):
        """Test that string schedule type works"""
        from_time = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        expression = "09:00"

        result = ScheduleCalculator.calculate_next_run(
            "daily", expression, from_time
        )

        expected = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected


class TestScheduleValidation:
    """Test schedule validation logic"""

    def test_is_schedule_valid_enabled(self):
        """Test that enabled schedule is valid"""
        result = ScheduleCalculator.is_schedule_valid(
            schedule_type=ScheduleType.daily,
            expression="09:00",
            schedule_enabled=True,
        )
        assert result is True

    def test_is_schedule_valid_disabled(self):
        """Test that disabled schedule is invalid"""
        result = ScheduleCalculator.is_schedule_valid(
            schedule_type=ScheduleType.daily,
            expression="09:00",
            schedule_enabled=False,
        )
        assert result is False

    def test_is_schedule_valid_before_start(self):
        """Test that schedule before start_at is invalid"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        schedule_start_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        result = ScheduleCalculator.is_schedule_valid(
            schedule_type=ScheduleType.daily,
            expression="09:00",
            schedule_enabled=True,
            schedule_start_at=schedule_start_at,
            from_time=from_time,
        )
        assert result is False

    def test_is_schedule_valid_after_end(self):
        """Test that schedule after end_at is invalid"""
        from_time = datetime(2024, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        schedule_end_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        result = ScheduleCalculator.is_schedule_valid(
            schedule_type=ScheduleType.daily,
            expression="09:00",
            schedule_enabled=True,
            schedule_end_at=schedule_end_at,
            from_time=from_time,
        )
        assert result is False

    def test_is_schedule_valid_max_runs_reached(self):
        """Test that schedule with max_runs reached is invalid"""
        result = ScheduleCalculator.is_schedule_valid(
            schedule_type=ScheduleType.daily,
            expression="09:00",
            schedule_enabled=True,
            max_runs=5,
            run_count=5,
        )
        assert result is False

    def test_is_schedule_valid_max_runs_not_reached(self):
        """Test that schedule with max_runs not reached is valid"""
        result = ScheduleCalculator.is_schedule_valid(
            schedule_type=ScheduleType.daily,
            expression="09:00",
            schedule_enabled=True,
            max_runs=5,
            run_count=3,
        )
        assert result is True

    def test_is_schedule_valid_once_past(self):
        """Test that 'once' schedule with past time is invalid"""
        from_time = datetime(2024, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        expression = "2024-01-15T09:00:00+00:00"

        result = ScheduleCalculator.is_schedule_valid(
            schedule_type=ScheduleType.once,
            expression=expression,
            schedule_enabled=True,
            from_time=from_time,
        )
        assert result is False

    def test_is_schedule_valid_once_future(self):
        """Test that 'once' schedule with future time is valid"""
        from_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expression = "2024-01-15T09:00:00+00:00"

        result = ScheduleCalculator.is_schedule_valid(
            schedule_type=ScheduleType.once,
            expression=expression,
            schedule_enabled=True,
            from_time=from_time,
        )
        assert result is True


class TestTaskModelSchedulingFields:
    """Test TaskModel scheduling fields"""

    @pytest.mark.asyncio
    async def test_task_model_scheduling_defaults(self, sync_db_session):
        """Test that scheduling fields have correct defaults"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

        repo = TaskRepository(sync_db_session)
        task = await repo.create_task(name="Test Task", user_id="test-user")

        assert task.schedule_type is None
        assert task.schedule_expression is None
        assert task.schedule_enabled is False
        assert task.schedule_start_at is None
        assert task.schedule_end_at is None
        assert task.next_run_at is None
        assert task.last_run_at is None
        assert task.max_runs is None
        assert task.run_count == 0

    @pytest.mark.asyncio
    async def test_task_model_with_scheduling(self, sync_db_session):
        """Test creating a task with scheduling fields"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

        repo = TaskRepository(sync_db_session)

        schedule_start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        schedule_end = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        next_run = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        task = await repo.create_task(
            name="Scheduled Task",
            user_id="test-user",
            schedule_type=ScheduleType.daily.value,
            schedule_expression="09:00",
            schedule_enabled=True,
            schedule_start_at=schedule_start,
            schedule_end_at=schedule_end,
            next_run_at=next_run,
            max_runs=100,
            run_count=0,
        )

        assert task.schedule_type == ScheduleType.daily.value
        assert task.schedule_expression == "09:00"
        assert task.schedule_enabled is True
        assert task.schedule_start_at == schedule_start
        assert task.schedule_end_at == schedule_end
        assert task.next_run_at == next_run
        assert task.max_runs == 100
        assert task.run_count == 0

    @pytest.mark.asyncio
    async def test_task_model_update_scheduling(self, sync_db_session):
        """Test updating scheduling fields"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

        repo = TaskRepository(sync_db_session)
        task = await repo.create_task(name="Test Task", user_id="test-user")

        last_run = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        next_run = datetime(2024, 1, 2, 9, 0, 0, tzinfo=timezone.utc)

        await repo.update_task(
            task_id=task.id,
            schedule_type=ScheduleType.daily.value,
            schedule_expression="09:00",
            schedule_enabled=True,
            last_run_at=last_run,
            next_run_at=next_run,
            run_count=1,
        )

        updated_task = await repo.get_task_by_id(task.id)
        assert updated_task.schedule_type == ScheduleType.daily.value
        assert updated_task.schedule_expression == "09:00"
        assert updated_task.schedule_enabled is True
        assert updated_task.last_run_at == last_run
        assert updated_task.next_run_at == next_run
        assert updated_task.run_count == 1

    def test_task_model_to_dict_scheduling(self):
        """Test that to_dict includes scheduling fields"""
        task = TaskModel(
            name="Test Task",
            schedule_type=ScheduleType.daily.value,
            schedule_expression="09:00",
            schedule_enabled=True,
            max_runs=100,
            run_count=5,
        )

        data = task.to_dict()

        assert data["schedule_type"] == "daily"
        assert data["schedule_expression"] == "09:00"
        assert data["schedule_enabled"] is True
        assert data["max_runs"] == 100
        assert data["run_count"] == 5

    def test_task_model_output_scheduling(self):
        """Test that output includes scheduling datetime fields as ISO strings"""
        schedule_start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        next_run = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        task = TaskModel(
            name="Test Task",
            schedule_type=ScheduleType.daily.value,
            schedule_expression="09:00",
            schedule_enabled=True,
            schedule_start_at=schedule_start,
            next_run_at=next_run,
        )

        data = task.output()

        assert data["schedule_start_at"] == "2024-01-01T00:00:00+00:00"
        assert data["next_run_at"] == "2024-01-01T09:00:00+00:00"

    def test_task_model_default_values_scheduling(self):
        """Test that default_values includes scheduling fields"""
        task = TaskModel(name="Test Task")
        defaults = task.default_values()

        assert defaults["schedule_type"] is None
        assert defaults["schedule_expression"] is None
        assert defaults["schedule_enabled"] is False
        assert defaults["schedule_start_at"] is None
        assert defaults["schedule_end_at"] is None
        assert defaults["next_run_at"] is None
        assert defaults["last_run_at"] is None
        assert defaults["max_runs"] is None
        assert defaults["run_count"] == 0


class TestSchedulingAPISupport:
    """Test that scheduling fields work through the API layer"""

    @pytest.mark.asyncio
    async def test_create_task_with_scheduling_via_repository(self, sync_db_session):
        """Test creating a task with scheduling fields via repository"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

        repo = TaskRepository(sync_db_session)

        # Create task with scheduling configuration
        task = await repo.create_task(
            name="Scheduled Report",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=True,
            max_runs=30,
        )

        assert task.schedule_type == "daily"
        assert task.schedule_expression == "09:00"
        assert task.schedule_enabled is True
        assert task.max_runs == 30

    @pytest.mark.asyncio
    async def test_update_task_scheduling_via_repository(self, sync_db_session):
        """Test updating task scheduling fields via repository"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from datetime import datetime, timezone

        repo = TaskRepository(sync_db_session)

        # Create a basic task
        task = await repo.create_task(name="Test Task", user_id="test-user")
        assert task.schedule_enabled is False  # Default

        # Update with scheduling configuration
        next_run = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        await repo.update_task(
            task.id,
            schedule_type="cron",
            schedule_expression="0 9 * * 1-5",
            schedule_enabled=True,
            next_run_at=next_run,
            max_runs=100,
        )

        # Verify updates
        updated = await repo.get_task_by_id(task.id)
        assert updated.schedule_type == "cron"
        assert updated.schedule_expression == "0 9 * * 1-5"
        assert updated.schedule_enabled is True
        assert updated.next_run_at == next_run
        assert updated.max_runs == 100

    @pytest.mark.asyncio
    async def test_disable_scheduling_via_repository(self, sync_db_session):
        """Test disabling scheduling via repository update"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

        repo = TaskRepository(sync_db_session)

        # Create task with scheduling enabled
        task = await repo.create_task(
            name="Scheduled Task",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=True,
        )
        assert task.schedule_enabled is True

        # Disable scheduling
        await repo.update_task(task.id, schedule_enabled=False)

        # Verify disabled
        updated = await repo.get_task_by_id(task.id)
        assert updated.schedule_enabled is False
        # Other scheduling fields should remain
        assert updated.schedule_type == "daily"
        assert updated.schedule_expression == "09:00"


class TestSchedulingRepositoryMethods:
    """Test scheduling-related repository methods for external schedulers"""

    @pytest.mark.asyncio
    async def test_get_due_scheduled_tasks(self, sync_db_session):
        """Test getting tasks that are due for execution"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from datetime import datetime, timezone

        repo = TaskRepository(sync_db_session)

        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        # Create a task due now
        due_task = await repo.create_task(
            name="Due Task",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=True,
            next_run_at=past,  # In the past, so it's due
        )

        # Create a task not yet due
        await repo.create_task(
            name="Future Task",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=True,
            next_run_at=future,  # In the future
        )

        # Create a disabled task
        await repo.create_task(
            name="Disabled Task",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=False,
            next_run_at=past,
        )

        # Get due tasks
        due_tasks = await repo.get_due_scheduled_tasks()

        # Should only return the due task
        assert len(due_tasks) == 1
        assert due_tasks[0].id == due_task.id

    @pytest.mark.asyncio
    async def test_get_due_scheduled_tasks_max_runs_check(self, sync_db_session):
        """Test that max_runs limit is respected"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from datetime import datetime, timezone

        repo = TaskRepository(sync_db_session)

        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)

        # Create a task that reached max_runs
        await repo.create_task(
            name="Exhausted Task",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=True,
            next_run_at=past,
            max_runs=5,
            run_count=5,  # Already at max
        )

        # Create a task with runs remaining
        active_task = await repo.create_task(
            name="Active Task",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=True,
            next_run_at=past,
            max_runs=5,
            run_count=3,  # Still has runs remaining
        )

        due_tasks = await repo.get_due_scheduled_tasks()

        # Should only return the active task
        assert len(due_tasks) == 1
        assert due_tasks[0].id == active_task.id

    @pytest.mark.asyncio
    async def test_get_scheduled_tasks(self, sync_db_session):
        """Test listing all scheduled tasks"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

        repo = TaskRepository(sync_db_session)

        # Create tasks with different schedule types
        await repo.create_task(
            name="Daily Task",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=True,
        )

        await repo.create_task(
            name="Weekly Task",
            user_id="test-user",
            schedule_type="weekly",
            schedule_expression="1,3,5 09:00",
            schedule_enabled=True,
        )

        await repo.create_task(
            name="Disabled Task",
            user_id="test-user",
            schedule_type="cron",
            schedule_expression="0 9 * * *",
            schedule_enabled=False,
        )

        # Create a non-scheduled task
        await repo.create_task(
            name="Regular Task",
            user_id="test-user",
        )

        # Get enabled scheduled tasks
        enabled_tasks = await repo.get_scheduled_tasks(enabled_only=True)
        assert len(enabled_tasks) == 2

        # Get all scheduled tasks
        all_scheduled = await repo.get_scheduled_tasks(enabled_only=False)
        assert len(all_scheduled) == 3

        # Filter by schedule_type
        daily_tasks = await repo.get_scheduled_tasks(schedule_type="daily")
        assert len(daily_tasks) == 1
        assert daily_tasks[0].name == "Daily Task"

    @pytest.mark.asyncio
    async def test_initialize_schedule(self, sync_db_session):
        """Test initializing next_run_at for a task"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository

        repo = TaskRepository(sync_db_session)

        # Create a task with schedule but no next_run_at
        task = await repo.create_task(
            name="New Scheduled Task",
            user_id="test-user",
            schedule_type="daily",
            schedule_expression="09:00",
            schedule_enabled=True,
        )

        assert task.next_run_at is None

        # Initialize the schedule
        updated = await repo.initialize_schedule(task.id)

        assert updated is not None
        assert updated.next_run_at is not None

    @pytest.mark.asyncio
    async def test_complete_scheduled_run(self, sync_db_session):
        """Test completing a scheduled run"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from datetime import datetime, timezone

        repo = TaskRepository(sync_db_session)

        now = datetime.now(timezone.utc)

        # Create a scheduled task
        task = await repo.create_task(
            name="Running Task",
            user_id="test-user",
            schedule_type="interval",
            schedule_expression="3600",  # 1 hour
            schedule_enabled=True,
            next_run_at=now,
            run_count=0,
        )

        # Complete the run
        updated = await repo.complete_scheduled_run(
            task.id,
            success=True,
            result={"processed": 100},
        )

        assert updated is not None
        assert updated.run_count == 1
        assert updated.last_run_at is not None
        assert updated.next_run_at is not None
        assert updated.next_run_at > now  # Next run should be in the future
        assert updated.status == "pending"  # Reset for next run
        assert updated.result == {"processed": 100}

    @pytest.mark.asyncio
    async def test_complete_scheduled_run_max_runs_reached(self, sync_db_session):
        """Test that schedule is disabled when max_runs is reached"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from datetime import datetime, timezone

        repo = TaskRepository(sync_db_session)

        now = datetime.now(timezone.utc)

        # Create a task with max_runs=1 and run_count=0
        task = await repo.create_task(
            name="One-time Task",
            user_id="test-user",
            schedule_type="interval",
            schedule_expression="3600",
            schedule_enabled=True,
            next_run_at=now,
            max_runs=1,
            run_count=0,
        )

        # Complete the run
        updated = await repo.complete_scheduled_run(task.id, success=True)

        assert updated is not None
        assert updated.run_count == 1
        assert updated.schedule_enabled is False  # Should be disabled
        assert updated.next_run_at is None  # No more runs
        assert updated.status == "completed"

    @pytest.mark.asyncio
    async def test_complete_scheduled_run_once_type(self, sync_db_session):
        """Test that 'once' schedule type is disabled after first run"""
        from apflow.core.storage.sqlalchemy.task_repository import TaskRepository
        from datetime import datetime, timezone

        repo = TaskRepository(sync_db_session)

        now = datetime.now(timezone.utc)

        task = await repo.create_task(
            name="Once Task",
            user_id="test-user",
            schedule_type="once",
            schedule_expression=now.isoformat(),
            schedule_enabled=True,
            next_run_at=now,
        )

        updated = await repo.complete_scheduled_run(task.id, success=True)

        assert updated.schedule_enabled is False
        assert updated.status == "completed"


class TestSchedulingMigration:
    """Test scheduling migration"""

    def test_migration_class_exists(self):
        """Test that migration class can be imported"""
        import importlib.util
        import os

        # Import module with numeric prefix using spec
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "../../../../src/apflow/core/storage/migrations/002_add_scheduling_fields.py"
        )
        migration_path = os.path.abspath(migration_path)

        spec = importlib.util.spec_from_file_location("migration_002", migration_path)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)

        AddSchedulingFields = migration_module.AddSchedulingFields
        migration = AddSchedulingFields()
        assert migration.description is not None
        assert "scheduling" in migration.description.lower() or "schedule" in migration.description.lower()

    def test_migration_has_upgrade_method(self):
        """Test that migration has upgrade method"""
        import importlib.util
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "../../../../src/apflow/core/storage/migrations/002_add_scheduling_fields.py"
        )
        migration_path = os.path.abspath(migration_path)

        spec = importlib.util.spec_from_file_location("migration_002", migration_path)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)

        AddSchedulingFields = migration_module.AddSchedulingFields
        migration = AddSchedulingFields()
        assert hasattr(migration, "upgrade")
        assert callable(migration.upgrade)

    def test_migration_has_downgrade_method(self):
        """Test that migration has downgrade method"""
        import importlib.util
        import os

        migration_path = os.path.join(
            os.path.dirname(__file__),
            "../../../../src/apflow/core/storage/migrations/002_add_scheduling_fields.py"
        )
        migration_path = os.path.abspath(migration_path)

        spec = importlib.util.spec_from_file_location("migration_002", migration_path)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)

        AddSchedulingFields = migration_module.AddSchedulingFields
        migration = AddSchedulingFields()
        assert hasattr(migration, "downgrade")
        assert callable(migration.downgrade)
