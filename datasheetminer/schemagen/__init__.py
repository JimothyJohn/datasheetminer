"""Propose a new Pydantic product model from a PDF datasheet.

Public surface: ``propose_model`` (LLM call), ``render_model_file`` and
``render_product_type_patch`` (pure renderers), and the ``ProposedModel``
/ ``ProposedField`` meta-schema the LLM fills in. The CLI orchestration
lives in ``cli.schemagen``.
"""

from datasheetminer.schemagen.meta_schema import (
    ProposedField,
    ProposedModel,
    ProposedSource,
)
from datasheetminer.schemagen.renderer import (
    render_model_file,
    render_product_type_patch,
    render_reasoning_doc,
)

__all__ = [
    "ProposedField",
    "ProposedModel",
    "ProposedSource",
    "render_model_file",
    "render_product_type_patch",
    "render_reasoning_doc",
]
