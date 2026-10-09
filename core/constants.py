"""Shared constants used across core/, services/, and pipeline/ modules."""
import uuid

# UUID namespace for grc_context point IDs.
# ID formula: uuid5(CONTEXT_UUID_NS, "{document_id}:{chunk_id}")
#
# WARNING: Never change this value. Changing it invalidates all existing
# point IDs in the grc_context collection — a full reindex would be required.
#
# Used by: core/ask.py, pipeline/embed_context_index.py,
#          services/trace_service.py, services/evidence_service.py
CONTEXT_UUID_NS = uuid.UUID("b5f2e8d1-3a7c-4e9f-b8a2-6d4f1c7e3b5a")


# Tag and type filters (docs/PIPELINE_REDESIGN_PLAN.md). Domain tags and requirement types are no longer assigned by the pipeline, so a filter on them would match nothing. The options are still accepted and
# answer with a warning instead. Set to True only together with re-enabling enrichment.
TAG_TYPE_FILTERS_ENABLED = False
TAG_TYPE_FILTERS_OFF_WARNING = "Tag and type filters are off: the pipeline no longer assigns domain tags or requirement types, so the filter was ignored."
