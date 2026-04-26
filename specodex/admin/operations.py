"""Admin operations for moving data between dev and prod tables.

All mutating operations default to dry-run. Callers must explicitly pass
``apply=True`` to actually write. This mirrors the existing safety posture of
``DynamoDBClient.delete_all``.

Conventions:
- A "stage" is a short string like ``dev``, ``staging``, or ``prod``. The
  DynamoDB table is named ``products-{stage}``, matching the CDK stack.
- The blacklist is enforced on ``promote`` only. ``demote`` and ``purge`` run
  unconditionally — the blacklist is a guard on the path *into* prod.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from specodex.admin.blacklist import Blacklist
from specodex.config import SCHEMA_CHOICES
from specodex.db.dynamo import DynamoDBClient
from specodex.models.manufacturer import Manufacturer
from specodex.models.product import ProductBase

# Sourced from auto-discovery in specodex.config so new product types
# registered via models/<type>.py are promoted/demoted/purged without a manual
# allowlist edit here.
PRODUCT_MODELS: Dict[str, Type[ProductBase]] = SCHEMA_CHOICES


def make_client(stage: str) -> DynamoDBClient:
    """Return a DynamoDBClient pointing at ``products-{stage}``."""
    return DynamoDBClient(table_name=f"products-{stage}")


def _resolve_model(product_type: str) -> Type[ProductBase]:
    try:
        return PRODUCT_MODELS[product_type]
    except KeyError as exc:
        supported = ", ".join(sorted(PRODUCT_MODELS))
        raise ValueError(
            f"Unknown product_type {product_type!r}. Supported: {supported}"
        ) from exc


def _list_products(
    client: DynamoDBClient,
    product_type: str,
    manufacturer: Optional[str] = None,
) -> List[ProductBase]:
    model = _resolve_model(product_type)
    if manufacturer:
        return client.list(
            model,
            filter_expr="manufacturer = :mfg",
            filter_values={":mfg": manufacturer},
        )
    return client.list(model)


def _list_manufacturers(client: DynamoDBClient) -> List[Manufacturer]:
    """Query all Manufacturer records from the table.

    The existing DynamoDBClient is product-centric, so we query PK=MANUFACTURER
    directly here.
    """
    response = client.table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": "MANUFACTURER"},
    )
    items: List[Dict[str, Any]] = list(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = client.table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": "MANUFACTURER"},
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    result: List[Manufacturer] = []
    for item in items:
        data = {k: v for k, v in item.items() if k not in ("PK", "SK")}
        try:
            result.append(Manufacturer(**data))
        except Exception as exc:  # pragma: no cover - defensive
            print(
                f"Warning: could not deserialize manufacturer {item.get('SK')}: {exc}"
            )
    return result


# ── Result types ───────────────────────────────────────────────────


@dataclass
class DiffResult:
    product_type: str
    source_stage: str
    target_stage: str
    only_in_source: List[str] = field(default_factory=list)  # product_ids
    only_in_target: List[str] = field(default_factory=list)
    in_both: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_type": self.product_type,
            "source_stage": self.source_stage,
            "target_stage": self.target_stage,
            "only_in_source": self.only_in_source,
            "only_in_target": self.only_in_target,
            "in_both_count": len(self.in_both),
        }


@dataclass
class PromoteResult:
    product_type: str
    considered: int = 0
    blocked_by_blacklist: List[str] = field(default_factory=list)  # product_ids
    promoted_products: int = 0
    promoted_manufacturers: int = 0
    applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_type": self.product_type,
            "considered": self.considered,
            "blocked_by_blacklist": len(self.blocked_by_blacklist),
            "blocked_manufacturers": sorted(set(self.blocked_by_blacklist)),
            "promoted_products": self.promoted_products,
            "promoted_manufacturers": self.promoted_manufacturers,
            "applied": self.applied,
        }


@dataclass
class PurgeResult:
    product_type: Optional[str]
    manufacturer: Optional[str]
    matched: int = 0
    deleted: int = 0
    applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_type": self.product_type,
            "manufacturer": self.manufacturer,
            "matched": self.matched,
            "deleted": self.deleted,
            "applied": self.applied,
        }


# ── Core operations ────────────────────────────────────────────────


def diff(
    source: DynamoDBClient,
    target: DynamoDBClient,
    product_type: str,
    source_stage: str,
    target_stage: str,
    manufacturer: Optional[str] = None,
) -> DiffResult:
    """Compute what's in source-but-not-target and vice versa, by product_id."""
    src_products = _list_products(source, product_type, manufacturer)
    tgt_products = _list_products(target, product_type, manufacturer)

    src_ids = {str(p.product_id): p for p in src_products}
    tgt_ids = {str(p.product_id): p for p in tgt_products}

    only_src = sorted(set(src_ids) - set(tgt_ids))
    only_tgt = sorted(set(tgt_ids) - set(src_ids))
    both = sorted(set(src_ids) & set(tgt_ids))

    return DiffResult(
        product_type=product_type,
        source_stage=source_stage,
        target_stage=target_stage,
        only_in_source=only_src,
        only_in_target=only_tgt,
        in_both=both,
    )


def promote(
    source: DynamoDBClient,
    target: DynamoDBClient,
    product_type: str,
    blacklist: Blacklist,
    manufacturer: Optional[str] = None,
    apply: bool = False,
) -> PromoteResult:
    """Copy products of ``product_type`` from source → target, skipping any
    whose manufacturer is on the blacklist. Also copies matching Manufacturer
    records (filtered by blacklist by name).
    """
    products = _list_products(source, product_type, manufacturer)

    result = PromoteResult(product_type=product_type, considered=len(products))
    to_write: List[ProductBase] = []
    for p in products:
        if blacklist.contains(p.manufacturer):
            result.blocked_by_blacklist.append(p.manufacturer)
            continue
        to_write.append(p)

    # Manufacturer records: pull all from source, filter by blacklist, and only
    # write ones whose name appears on a product being promoted (keeps the
    # target table tight — we don't drag over orphan manufacturers).
    promoted_mfg_names = {p.manufacturer for p in to_write}
    manufacturers = [
        m
        for m in _list_manufacturers(source)
        if m.name in promoted_mfg_names and not blacklist.contains(m.name)
    ]

    if apply:
        if to_write:
            result.promoted_products = target.batch_create(to_write)
        if manufacturers:
            result.promoted_manufacturers = target.batch_create(manufacturers)
        result.applied = True
    else:
        result.promoted_products = len(to_write)
        result.promoted_manufacturers = len(manufacturers)

    return result


def demote(
    source: DynamoDBClient,
    target: DynamoDBClient,
    product_type: str,
    manufacturer: Optional[str] = None,
    apply: bool = False,
) -> PromoteResult:
    """Copy products prod → dev. No blacklist check — the blacklist only guards
    the path *into* prod. Reuses ``PromoteResult`` for symmetry.
    """
    products = _list_products(source, product_type, manufacturer)
    result = PromoteResult(product_type=product_type, considered=len(products))

    promoted_mfg_names = {p.manufacturer for p in products}
    manufacturers = [
        m for m in _list_manufacturers(source) if m.name in promoted_mfg_names
    ]

    if apply:
        if products:
            result.promoted_products = target.batch_create(products)
        if manufacturers:
            result.promoted_manufacturers = target.batch_create(manufacturers)
        result.applied = True
    else:
        result.promoted_products = len(products)
        result.promoted_manufacturers = len(manufacturers)

    return result


def purge(
    client: DynamoDBClient,
    product_type: Optional[str] = None,
    manufacturer: Optional[str] = None,
    apply: bool = False,
) -> PurgeResult:
    """Delete products matching ``product_type`` and/or ``manufacturer``.

    At least one of ``product_type`` or ``manufacturer`` must be set — we do
    not support "delete everything" through this path; use
    ``DynamoDBClient.delete_all`` if you really mean it.
    """
    if not product_type and not manufacturer:
        raise ValueError("purge requires at least one of product_type or manufacturer")

    result = PurgeResult(product_type=product_type, manufacturer=manufacturer)

    # Collect matching items from each relevant product type.
    types_to_scan = [product_type] if product_type else list(PRODUCT_MODELS.keys())
    matched_keys: List[Dict[str, str]] = []
    for ptype in types_to_scan:
        for p in _list_products(client, ptype, manufacturer):
            matched_keys.append(
                {
                    "PK": f"PRODUCT#{ptype.upper()}",
                    "SK": f"PRODUCT#{p.product_id}",
                }
            )

    result.matched = len(matched_keys)

    if not apply:
        return result

    # Batch delete in chunks of 25.
    batch_size = 25
    for i in range(0, len(matched_keys), batch_size):
        batch = matched_keys[i : i + batch_size]
        with client.table.batch_writer() as writer:
            for key in batch:
                writer.delete_item(Key=key)
                result.deleted += 1

    result.applied = True
    return result


# ── Formatting ─────────────────────────────────────────────────────


def format_diff_table(diff_result: DiffResult) -> str:
    lines = [
        f"Diff: {diff_result.source_stage} vs {diff_result.target_stage}  "
        f"(product_type={diff_result.product_type})",
        f"  only in {diff_result.source_stage}: {len(diff_result.only_in_source)}",
        f"  only in {diff_result.target_stage}: {len(diff_result.only_in_target)}",
        f"  in both:                            {len(diff_result.in_both)}",
    ]
    if diff_result.only_in_source:
        lines.append(f"  → candidates to promote ({diff_result.source_stage}):")
        for pid in diff_result.only_in_source[:20]:
            lines.append(f"      {pid}")
        if len(diff_result.only_in_source) > 20:
            lines.append(f"      ... and {len(diff_result.only_in_source) - 20} more")
    return "\n".join(lines)


def format_promote_summary(label: str, result: PromoteResult) -> str:
    mode = "APPLIED" if result.applied else "DRY RUN"
    lines = [
        f"{label} [{mode}] product_type={result.product_type}",
        f"  considered:              {result.considered}",
        f"  blocked by blacklist:    {len(result.blocked_by_blacklist)}",
        f"  products written:        {result.promoted_products}",
        f"  manufacturers written:   {result.promoted_manufacturers}",
    ]
    if result.blocked_by_blacklist:
        unique_blocked = sorted(set(result.blocked_by_blacklist))
        lines.append(f"  blocked manufacturers:   {', '.join(unique_blocked)}")
    return "\n".join(lines)


def format_purge_summary(result: PurgeResult) -> str:
    mode = "APPLIED" if result.applied else "DRY RUN"
    scope_bits = []
    if result.product_type:
        scope_bits.append(f"type={result.product_type}")
    if result.manufacturer:
        scope_bits.append(f"manufacturer={result.manufacturer}")
    scope = ", ".join(scope_bits) or "all"
    lines = [
        f"Purge [{mode}] {scope}",
        f"  matched:  {result.matched}",
        f"  deleted:  {result.deleted}",
    ]
    return "\n".join(lines)
