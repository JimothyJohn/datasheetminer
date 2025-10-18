# Filter System Quick Start

## TL;DR

Press `Ctrl+K` → Type attribute name → Select → Click icon to cycle modes (○ ✓ ✗) → Add value if needed

## 3-Mode Filter System

| Icon | Mode | Meaning | Use When |
|------|------|---------|----------|
| ○ | Neutral | Ignored | Want to keep filter but disable temporarily |
| ✓ | Include | MUST have | Want products with this feature |
| ✗ | Exclude | MUST NOT have | Want to remove unwanted options |

## Common Workflows

### Find Motors by Power
```
Ctrl+K → "Rated Power" → ✓ Include → Add value "5"
Result: All motors with 5HP power
```

### Exclude Unwanted Brands
```
Ctrl+K → "Manufacturer" → ✗ Exclude → Add value "BrandName"
Result: All products except that brand
```

### Complex Search
```
1. Select product type (Motors/Drives)
2. Ctrl+K → Add filters for must-haves (✓ Include)
3. Ctrl+K → Add filters for exclusions (✗ Exclude)
4. Click "Sort By..." → Choose attribute
5. Review results
```

## Keyboard Shortcuts

- `Ctrl+K` (or `Cmd+K` on Mac): Open filter selector
- `↑` / `↓`: Navigate attributes
- `Enter`: Select attribute
- `Escape`: Close selector
- Click icon: Cycle through modes

## Tips

1. **Start with product type**: Choose Motors/Drives/All first
2. **Add filters gradually**: One at a time to see impact
3. **Use neutral mode**: Keep filters around but disabled
4. **Sort after filtering**: Filter first, then sort results
5. **Clear and restart**: Use "Clear All" if stuck

## Try It Now

1. Open the Products page
2. Press `Ctrl+K`
3. Type "power"
4. Press Enter
5. Click the ○ icon twice to get ✓
6. Click "+ value" and enter a number
7. See results update instantly!

## Need Help?

See `FILTER_GUIDE.md` for detailed documentation and examples.
