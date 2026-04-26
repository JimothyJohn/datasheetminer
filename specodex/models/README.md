# models

Pydantic schemas for product types. New models are auto-discovered at runtime — drop a file here and it appears in all CLIs and the web app.

## Adding a Product Type

1. Create `<type>.py` with a class inheriting from `ProductBase`
2. Set `product_type: Literal["<type>"] = "<type>"`
3. Type fields with the narrowest quantity alias in `common.py` (`Voltage`, `Current`, `Power`, ...). Fall back to `ValueUnit` / `MinMaxUnit` only for compound units (V/krpm, mm/s) or domain-specific units (arcmin, dB).
4. Add `"<type>"` to the `ProductType` literal in `common.py`

## Files

| File | Description |
|------|-------------|
| `product.py` | `ProductBase` — common fields (name, manufacturer, part number, dimensions, weight) and DynamoDB PK/SK |
| `common.py` | Shared types: `ValueUnit` / `MinMaxUnit`, per-quantity narrowed aliases (`Voltage`, `Current`, `Power`, ...), `IpRating`, `ProductType` literal |
| `llm_schema.py` | Builds the Gemini JSON response_schema from a Pydantic model |
| `motor.py` | Motors — voltage, current, power, torque, speed, encoder, inertia |
| `drive.py` | Drives — I/O voltage, power, fieldbus, digital/analog I/O counts |
| `gearhead.py` | Gearheads — ratio, backlash, torque, rigidity, service life |
| `contactor.py` | Contactors — coil/line voltage, AC-3 ratings, switching durability |
| `electric_cylinder.py` | Electric cylinders — stroke, force, linear speed, repeatability |
| `robot_arm.py` | Robot arms — payload, reach, repeatability, per-axis specs |
| `datasheet.py` | Datasheet source metadata (URL, pages, product family) |
| `manufacturer.py` | Manufacturer metadata |
