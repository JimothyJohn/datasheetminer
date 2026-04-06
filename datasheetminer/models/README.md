# models

Pydantic schemas for product types. New models are auto-discovered at runtime — drop a file here and it appears in all CLIs and the web app.

## Adding a Product Type

1. Create `<type>.py` with a class inheriting from `ProductBase`
2. Set `product_type: Literal["<type>"] = "<type>"`
3. Add unit mappings to `csv_schema.py:UNITS` for any `ValueUnit`/`MinMaxUnit` fields
4. Add `"<type>"` to the `ProductType` literal in `common.py`

## Files

| File | Description |
|------|-------------|
| `product.py` | `ProductBase` — common fields (name, manufacturer, part number, dimensions, weight) and DynamoDB PK/SK |
| `common.py` | Shared types: `ValueUnit` ("20;V"), `MinMaxUnit` ("100-240;V"), `ProductType` literal |
| `csv_schema.py` | Generates CSV headers from model fields, reconstructs `value;unit` strings from LLM output |
| `motor.py` | Motors — voltage, current, power, torque, speed, encoder, inertia |
| `drive.py` | Drives — I/O voltage, power, fieldbus, digital/analog I/O counts |
| `gearhead.py` | Gearheads — ratio, backlash, torque, rigidity, service life |
| `electric_cylinder.py` | Electric cylinders — stroke, force, linear speed, repeatability |
| `robot_arm.py` | Robot arms — payload, reach, repeatability, per-axis specs |
| `factory.py` | General industrial equipment |
| `datasheet.py` | Datasheet source metadata (URL, pages, product family) |
| `manufacturer.py` | Manufacturer metadata |
