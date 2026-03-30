# DSM Find — Proof of Concept

> "I have a rack and pinion with a 25mm diameter and need a 250N thrust force to ramp up to 5m/s on my rail, which motor and gear ratio could do this? I have 200V on site and need to size a servo drive as well"

## Sizing Summary

| Parameter | Value |
|---|---|
| Pinion diameter | 25mm (r = 0.0125m) |
| Thrust force | 250 N |
| Linear speed | 5 m/s |
| **Torque at pinion** | **3.125 Nm** |
| **Pinion RPM** | **3820 RPM** |
| **Power** | **1250 W** |

## Queries Used

```bash
# Find motors >= 1.5kW at 200-240V, sorted by torque
dsm find --type motor \
  --where "rated_power>=1500" --where "rated_power<=3000" \
  --where "rated_voltage>=200" --where "rated_voltage<=240" \
  --sort "rated_torque:desc" -n 15

# Find drives with 200V+ input
dsm find --type drive --where "input_voltage>=200" --sort "output_power:desc" -n 10

# Find gearheads by continuous torque
dsm find --type gearhead --where "max_continuous_torque>=3" --sort "max_continuous_torque:asc" -n 10
```

## Recommended Approach: 1.5kW motor + direct drive (no gearbox)

Since 3820 RPM and 3.125 Nm are within range of a single 1.5kW AC servo, the pinion can be direct-driven. This is ideal for rack-and-pinion since gearboxes add backlash.

### Top Motor Picks

| Motor | Power | Voltage | Speed | Cont. Torque | Peak Torque |
|---|---|---|---|---|---|
| Panasonic `MSMA102S1` | 1000W | 200V | 3000 RPM | 3.18 Nm | 9.5 Nm |
| Panasonic `MFMA152P1` | 1500W | 200V | 2000 RPM | 7.15 Nm | 21.5 Nm |
| Kollmorgen `AKM53M` | 2740W | 240V | 3000 RPM | 8.72 Nm | 29.7 Nm |

- **1kW MSMA102S1** — 3.18 Nm barely clears 3.125 Nm with no margin.
- **1.5kW MFMA152P1** — 7.15 Nm gives 2x headroom for acceleration ramps, but 2000 RPM base speed limits top linear velocity.
- **2.7kW AKM53M** — 8.72 Nm at 3000 RPM, safest choice. 240V rating works on 200V supply (derate slightly).

### Gear Ratio

With a 3000 RPM motor and 3820 RPM pinion requirement:

- **1:1 direct drive** — accept 3000 RPM (3.9 m/s instead of 5 m/s)
- **1:1.3 step-up timing belt** — low backlash, gets to 3900 RPM
- Higher-speed motor variant (some Kollmorgen AKM go to 5000 RPM)

For rack-and-pinion at these speeds, a timing belt is typically preferred over a gearbox (lower backlash, lighter).

### Servo Drive

Pair with the matching drive family:

- **Panasonic MINAS A4 motors** -> Panasonic MCDDT series driver (200V input, matched)
- **Kollmorgen AKM motors** -> Kollmorgen AKD servo drive (200-240V input)

Both accept 200V site power directly.
