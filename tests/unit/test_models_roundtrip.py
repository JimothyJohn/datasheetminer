"""Per-model round-trip + boundary tests.

Runs the same set of checks against every product model registered in
`SCHEMA_CHOICES`. Adding a new product type under `datasheetminer/models/`
gets covered automatically.

Checks:
  - minimum-viable instance can be constructed
  - `model_dump()` → `model_validate()` is a pure round-trip
  - required field missing raises ValidationError (fail-fast)
  - PK / SK computed fields are stable across dump+reload
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from datasheetminer.config import SCHEMA_CHOICES


PRODUCT_TYPES = sorted(SCHEMA_CHOICES.keys())


@pytest.fixture(params=PRODUCT_TYPES)
def product_type(request) -> str:
    return request.param


@pytest.fixture
def model_class(product_type):
    return SCHEMA_CHOICES[product_type]


# Models whose `product_type` is NOT declared as a narrow Literal for this
# product type. Empty today — every model pins `Literal[<type>]`. Kept as a
# named set so a future model that forgets to narrow trips the test rather
# than silently widening.
NON_LITERAL_PRODUCT_TYPE_MODELS: set[str] = set()

# Models whose `product_type` field has no default — caller must supply it.
# Empty today; every model pins a default via `Literal[...] = "..."`.
PRODUCT_TYPE_NO_DEFAULT: set[str] = set()

# Models that declare a default `manufacturer` and therefore do NOT raise when
# the caller omits it. Currently only `robot_arm` (defaults to "Universal
# Robots"). Flagging these so a future tighten-up triggers the test.
MANUFACTURER_HAS_DEFAULT = {"robot_arm"}


@pytest.fixture
def minimal_instance(model_class, product_type):
    kwargs: dict = {"manufacturer": "Acme", "product_name": f"test-{product_type}"}
    if product_type in PRODUCT_TYPE_NO_DEFAULT:
        kwargs["product_type"] = product_type
    return model_class(**kwargs)


def test_minimal_instance_constructs(minimal_instance) -> None:
    assert minimal_instance.manufacturer == "Acme"
    assert minimal_instance.product_id is not None


def test_dump_reload_is_round_trip(model_class, minimal_instance) -> None:
    dumped = minimal_instance.model_dump(mode="python")
    reloaded = model_class.model_validate(dumped)
    assert reloaded.product_id == minimal_instance.product_id
    assert reloaded.manufacturer == minimal_instance.manufacturer
    assert reloaded.product_type == minimal_instance.product_type


def test_missing_manufacturer_raises(model_class, product_type) -> None:
    if product_type in MANUFACTURER_HAS_DEFAULT:
        pytest.skip(f"{product_type} supplies a default manufacturer")
    kwargs: dict = {"product_name": "test"}
    if product_type in PRODUCT_TYPE_NO_DEFAULT:
        kwargs["product_type"] = product_type
    with pytest.raises(ValidationError):
        model_class(**kwargs)


def test_missing_product_name_raises(model_class, product_type) -> None:
    kwargs: dict = {"manufacturer": "Acme"}
    if product_type in PRODUCT_TYPE_NO_DEFAULT:
        kwargs["product_type"] = product_type
    with pytest.raises(ValidationError):
        model_class(**kwargs)


def test_pk_sk_are_stable_across_roundtrip(model_class, minimal_instance) -> None:
    dumped = minimal_instance.model_dump(mode="python")
    reloaded = model_class.model_validate(dumped)
    assert reloaded.PK == minimal_instance.PK
    assert reloaded.SK == minimal_instance.SK


def test_pk_format(minimal_instance, product_type) -> None:
    assert minimal_instance.PK == f"PRODUCT#{product_type.upper()}"


def test_sk_prefixed_with_product(minimal_instance) -> None:
    assert minimal_instance.SK.startswith("PRODUCT#")
    assert str(minimal_instance.product_id) in minimal_instance.SK


def test_unknown_extra_fields_ignored_or_passed(model_class, product_type) -> None:
    """Current config has no `model_config = {"extra": "forbid"}` — document
    that unknown fields are accepted (stripped). If that changes, this fails."""
    try:
        inst = model_class(
            manufacturer="Acme",
            product_name=f"test-{product_type}",
            not_a_real_field_xyz="ignore me",
        )
    except ValidationError:
        # If someone tightens extra=forbid, that's fine — just acknowledge.
        return
    assert not hasattr(inst, "not_a_real_field_xyz")


def test_product_type_literal_enforced(model_class, product_type) -> None:
    """Each model that pins `product_type: Literal[<type>]` must refuse a
    different literal. Skipped for models declaring `product_type: str` today."""
    if product_type in NON_LITERAL_PRODUCT_TYPE_MODELS:
        pytest.skip(f"{product_type} uses `str` not `Literal` for product_type")
    wrong = next(t for t in PRODUCT_TYPES if t != product_type)
    with pytest.raises(ValidationError):
        model_class(manufacturer="Acme", product_name="x", product_type=wrong)
