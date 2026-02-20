"""Tests for AutoCode Pydantic models and ORM table creation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bristlenose.llm.structured import AutoCodeBatchResult, AutoCodeTagAssignment

# ---------------------------------------------------------------------------
# AutoCodeTagAssignment
# ---------------------------------------------------------------------------


class TestAutoCodeTagAssignment:
    """Tests for the individual tag assignment model."""

    def test_valid_assignment(self) -> None:
        """Normal tag assignment parses correctly."""
        a = AutoCodeTagAssignment(
            quote_index=0,
            tag_name="user need",
            confidence=0.85,
            rationale="Participant describes what they came to do",
        )
        assert a.quote_index == 0
        assert a.tag_name == "user need"
        assert a.confidence == 0.85
        assert a.rationale == "Participant describes what they came to do"

    def test_low_confidence(self) -> None:
        """Low confidence for weak matches is valid."""
        a = AutoCodeTagAssignment(
            quote_index=3,
            tag_name="value proposition",
            confidence=0.15,
            rationale="Weak match — quote is about poodle grooming, not product evaluation",
        )
        assert a.confidence == 0.15

    def test_confidence_lower_bound(self) -> None:
        """Confidence 0.0 is valid (absolute minimum)."""
        a = AutoCodeTagAssignment(
            quote_index=0, tag_name="x", confidence=0.0, rationale="r"
        )
        assert a.confidence == 0.0

    def test_confidence_upper_bound(self) -> None:
        """Confidence 1.0 is valid (absolute maximum)."""
        a = AutoCodeTagAssignment(
            quote_index=0, tag_name="x", confidence=1.0, rationale="r"
        )
        assert a.confidence == 1.0

    def test_confidence_below_zero_rejected(self) -> None:
        """Confidence below 0.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            AutoCodeTagAssignment(
                quote_index=0, tag_name="x", confidence=-0.1, rationale="r"
            )

    def test_confidence_above_one_rejected(self) -> None:
        """Confidence above 1.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            AutoCodeTagAssignment(
                quote_index=0, tag_name="x", confidence=1.1, rationale="r"
            )

    def test_empty_rationale(self) -> None:
        """Empty rationale string is valid."""
        a = AutoCodeTagAssignment(
            quote_index=0, tag_name="x", confidence=0.5, rationale=""
        )
        assert a.rationale == ""


# ---------------------------------------------------------------------------
# AutoCodeBatchResult
# ---------------------------------------------------------------------------


class TestAutoCodeBatchResult:
    """Tests for the batch result container."""

    def test_empty_batch(self) -> None:
        """Empty assignment list is valid (though unusual)."""
        result = AutoCodeBatchResult(assignments=[])
        assert result.assignments == []

    def test_single_assignment(self) -> None:
        """Batch with one assignment."""
        result = AutoCodeBatchResult(
            assignments=[
                AutoCodeTagAssignment(
                    quote_index=0,
                    tag_name="feature requirement",
                    confidence=0.9,
                    rationale="Participant wants a filter feature",
                )
            ]
        )
        assert len(result.assignments) == 1

    def test_full_batch_of_25(self) -> None:
        """A full 25-item batch parses correctly."""
        assignments = [
            AutoCodeTagAssignment(
                quote_index=i,
                tag_name=f"tag-{i}",
                confidence=0.5 + i * 0.02,
                rationale=f"Rationale for quote {i}",
            )
            for i in range(25)
        ]
        result = AutoCodeBatchResult(assignments=assignments)
        assert len(result.assignments) == 25
        assert result.assignments[0].quote_index == 0
        assert result.assignments[24].quote_index == 24

    def test_mixed_confidence_levels(self) -> None:
        """Batch with high and low confidence assignments."""
        result = AutoCodeBatchResult(
            assignments=[
                AutoCodeTagAssignment(
                    quote_index=0,
                    tag_name="visual design",
                    confidence=0.92,
                    rationale="Clear reference to colours and imagery",
                ),
                AutoCodeTagAssignment(
                    quote_index=1,
                    tag_name="user need",
                    confidence=0.18,
                    rationale="Weak match — mostly navigational narration",
                ),
            ]
        )
        assert result.assignments[0].confidence > 0.9
        assert result.assignments[1].confidence < 0.2

    def test_json_round_trip(self) -> None:
        """Model can serialise to JSON and parse back."""
        original = AutoCodeBatchResult(
            assignments=[
                AutoCodeTagAssignment(
                    quote_index=0,
                    tag_name="information architecture",
                    confidence=0.77,
                    rationale="Participant confused about category grouping",
                )
            ]
        )
        json_str = original.model_dump_json()
        parsed = AutoCodeBatchResult.model_validate_json(json_str)
        assert parsed.assignments[0].tag_name == "information architecture"
        assert parsed.assignments[0].confidence == 0.77


# ---------------------------------------------------------------------------
# ORM table creation (smoke test)
# ---------------------------------------------------------------------------


class TestAutoCodeORMTables:
    """Verify the new ORM tables can be created and populated."""

    def test_autocode_job_table_exists(self) -> None:
        """AutoCodeJob table is created by Base.metadata.create_all."""
        from sqlalchemy import create_engine

        from bristlenose.server.db import Base
        from bristlenose.server.models import AutoCodeJob  # noqa: F401

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        assert "autocode_jobs" in Base.metadata.tables

    def test_proposed_tag_table_exists(self) -> None:
        """ProposedTag table is created by Base.metadata.create_all."""
        from sqlalchemy import create_engine

        from bristlenose.server.db import Base
        from bristlenose.server.models import ProposedTag  # noqa: F401

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        assert "proposed_tags" in Base.metadata.tables

    def test_autocode_job_insert(self) -> None:
        """Can insert an AutoCodeJob row."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SASession

        from bristlenose.server.db import Base
        from bristlenose.server.models import AutoCodeJob, Project

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with SASession(engine) as db:
            project = Project(name="Test", slug="test", input_dir="/tmp", output_dir="/tmp")
            db.add(project)
            db.flush()
            job = AutoCodeJob(
                project_id=project.id,
                framework_id="garrett",
                status="running",
            )
            db.add(job)
            db.commit()
            assert job.id is not None
            assert job.status == "running"
            assert job.total_quotes == 0
            assert job.proposed_count == 0
            assert job.error_message == ""

    def test_proposed_tag_insert(self) -> None:
        """Can insert a ProposedTag row linked to a job and quote."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SASession

        from bristlenose.server.db import Base
        from bristlenose.server.models import (
            AutoCodeJob,
            CodebookGroup,
            Project,
            ProposedTag,
            Quote,
            TagDefinition,
        )

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with SASession(engine) as db:
            project = Project(name="Test", slug="test", input_dir="/tmp", output_dir="/tmp")
            db.add(project)
            db.flush()
            job = AutoCodeJob(
                project_id=project.id, framework_id="garrett", status="running"
            )
            db.add(job)
            group = CodebookGroup(name="Strategy", subtitle="Why we build it", colour_set="ux")
            db.add(group)
            db.flush()
            tag_def = TagDefinition(name="user need", codebook_group_id=group.id)
            db.add(tag_def)
            quote = Quote(
                project_id=project.id,
                session_id="s1",
                participant_id="p1",
                start_timecode=134.0,
                end_timecode=140.0,
                text="I need a way to filter by water parameters",
                quote_type="screen_specific",
            )
            db.add(quote)
            db.flush()
            proposed = ProposedTag(
                job_id=job.id,
                quote_id=quote.id,
                tag_definition_id=tag_def.id,
                confidence=0.85,
                rationale="Participant describes a core need",
                status="pending",
            )
            db.add(proposed)
            db.commit()
            assert proposed.id is not None
            assert proposed.confidence == 0.85
            assert proposed.status == "pending"

    def test_unique_constraint_project_framework(self) -> None:
        """Cannot create two AutoCodeJobs for same project+framework."""
        from sqlalchemy import create_engine
        from sqlalchemy.exc import IntegrityError
        from sqlalchemy.orm import Session as SASession

        from bristlenose.server.db import Base
        from bristlenose.server.models import AutoCodeJob, Project

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with SASession(engine) as db:
            project = Project(name="Test", slug="test", input_dir="/tmp", output_dir="/tmp")
            db.add(project)
            db.flush()
            db.add(AutoCodeJob(
                project_id=project.id, framework_id="garrett", status="completed"
            ))
            db.commit()
            db.add(AutoCodeJob(
                project_id=project.id, framework_id="garrett", status="running"
            ))
            with pytest.raises(IntegrityError):
                db.commit()

    def test_unique_constraint_job_quote(self) -> None:
        """Cannot create two ProposedTags for same job+quote."""
        from sqlalchemy import create_engine
        from sqlalchemy.exc import IntegrityError
        from sqlalchemy.orm import Session as SASession

        from bristlenose.server.db import Base
        from bristlenose.server.models import (
            AutoCodeJob,
            CodebookGroup,
            Project,
            ProposedTag,
            Quote,
            TagDefinition,
        )

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with SASession(engine) as db:
            project = Project(name="Test", slug="test", input_dir="/tmp", output_dir="/tmp")
            db.add(project)
            db.flush()
            job = AutoCodeJob(
                project_id=project.id, framework_id="garrett", status="running"
            )
            db.add(job)
            group = CodebookGroup(name="Scope", subtitle="What it includes", colour_set="emo")
            db.add(group)
            db.flush()
            tag1 = TagDefinition(name="feature requirement", codebook_group_id=group.id)
            tag2 = TagDefinition(name="content requirement", codebook_group_id=group.id)
            db.add_all([tag1, tag2])
            quote = Quote(
                project_id=project.id,
                session_id="s1",
                participant_id="p1",
                start_timecode=200.0,
                end_timecode=210.0,
                text="There's no filter",
                quote_type="screen_specific",
            )
            db.add(quote)
            db.flush()
            db.add(ProposedTag(
                job_id=job.id, quote_id=quote.id, tag_definition_id=tag1.id,
                confidence=0.8, rationale="r1",
            ))
            db.commit()
            db.add(ProposedTag(
                job_id=job.id, quote_id=quote.id, tag_definition_id=tag2.id,
                confidence=0.7, rationale="r2",
            ))
            with pytest.raises(IntegrityError):
                db.commit()

    def test_job_proposed_tags_relationship(self) -> None:
        """AutoCodeJob.proposed_tags relationship loads correctly."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SASession

        from bristlenose.server.db import Base
        from bristlenose.server.models import (
            AutoCodeJob,
            CodebookGroup,
            Project,
            ProposedTag,
            Quote,
            TagDefinition,
        )

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with SASession(engine) as db:
            project = Project(name="Test", slug="test", input_dir="/tmp", output_dir="/tmp")
            db.add(project)
            db.flush()
            job = AutoCodeJob(
                project_id=project.id, framework_id="garrett", status="completed"
            )
            db.add(job)
            group = CodebookGroup(name="Surface", subtitle="Visual", colour_set="opp")
            db.add(group)
            db.flush()
            tag = TagDefinition(name="visual design", codebook_group_id=group.id)
            db.add(tag)
            q1 = Quote(
                project_id=project.id, session_id="s1", participant_id="p1",
                start_timecode=10.0, end_timecode=20.0, text="Q1",
                quote_type="screen_specific",
            )
            q2 = Quote(
                project_id=project.id, session_id="s1", participant_id="p1",
                start_timecode=30.0, end_timecode=40.0, text="Q2",
                quote_type="screen_specific",
            )
            db.add_all([q1, q2])
            db.flush()
            db.add_all([
                ProposedTag(
                    job_id=job.id, quote_id=q1.id, tag_definition_id=tag.id,
                    confidence=0.9, rationale="r1",
                ),
                ProposedTag(
                    job_id=job.id, quote_id=q2.id, tag_definition_id=tag.id,
                    confidence=0.6, rationale="r2",
                ),
            ])
            db.commit()
            db.refresh(job)
            assert len(job.proposed_tags) == 2
