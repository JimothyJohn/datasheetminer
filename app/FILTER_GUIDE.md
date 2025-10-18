# Advanced Filter and Sort System

## Overview

The web application now includes a powerful filtering and sorting system that allows you to search and filter products by any attribute with three distinct modes:

- **○ Neutral**: Attribute is ignored (doesn't affect filtering)
- **✓ Include**: Products MUST have this attribute/value
- **✗ Exclude**: Products MUST NOT have this attribute/value

## Features

### 1. Keyboard-Driven Attribute Selection

Press `Ctrl+K` (or `Cmd+K` on Mac) to open the attribute selector, similar to ChatGPT's command palette:

- Type to search attributes by name or key
- Use arrow keys (↑/↓) to navigate
- Press Enter to select
- Press Escape to close

### 2. Filter Modes

Each filter chip has three modes that you can cycle through by clicking the icon:

#### Neutral Mode (○)
- Gray background
- Filter is present but inactive
- Doesn't affect search results
- Use this when you want to keep a filter but temporarily disable it

#### Include Mode (✓)
- Green background
- Products MUST have this attribute
- If you specify a value, it must match
- Multiple include filters create an AND condition

#### Exclude Mode (✗)
- Red background
- Products MUST NOT have this attribute/value
- Use this to filter out unwanted options
- Great for narrowing down choices

### 3. Dynamic Value Editing

- Click on a filter chip to add or edit specific values
- Leave value empty to just check for attribute existence
- Values support both text and numeric input
- Press Enter to save, Escape to cancel

### 4. Sorting

- Click "Sort By..." to open the attribute selector
- Choose any attribute to sort by
- Click again to toggle between ascending (↑) and descending (↓)
- Click a third time to clear sorting

### 5. Product Type Filtering

- Choose between "All Products", "Motors Only", or "Drives Only"
- Available attributes update based on selected product type
- Filters are preserved when switching types (if applicable)

## Usage Examples

### Example 1: Find High-Power Motors

1. Select "Motors Only" from product type
2. Press `Ctrl+K` and select "Rated Power"
3. Click the filter chip icon until it shows ✓ (Include)
4. Click on the filter value and enter "5" (for 5+ HP)
5. Click "Sort By..." and select "Rated Power"

### Example 2: Exclude Specific Manufacturers

1. Press `Ctrl+K` and select "Manufacturer"
2. Click the icon to change to ✗ (Exclude)
3. Click "+ value" and enter the manufacturer name
4. Repeat for additional manufacturers to exclude

### Example 3: Filter Drives by I/O Count

1. Select "Drives Only"
2. Add filter for "Digital Inputs" (Include mode)
3. Set value to minimum required (e.g., "8")
4. Add filter for "Digital Outputs" (Include mode)
5. Set value to minimum required
6. Sort by "Output Power"

### Example 4: Complex Multi-Filter Search

1. Select product type
2. Add "IP Rating" filter (Include) with value "65"
3. Add "Manufacturer" filter (Include) with preferred brand
4. Add "Series" filter (Exclude) with unwanted series
5. Sort by "Rated Power" descending

## Attribute Types

### String Attributes
- Manufacturer, Part Number, Series, Motor Type, Drive Type
- Partial matching (case-insensitive)

### Numeric Attributes
- Poles, IP Rating, Ethernet Ports, I/O counts, Humidity
- Exact matching for discrete values

### Range Attributes (Min/Max)
- Rated Voltage, Input Voltage, Ambient Temperature
- Checks if specified value falls within range

### Object Attributes (Value + Unit)
- Rated Power, Rated Speed, Rated Torque, Weight, etc.
- Compares numeric value, ignores unit

### Array Attributes
- Fieldbus, Control Modes, Safety Features, Approvals
- Matches if any array element contains the search value

## Tips

1. **Start Broad**: Begin with product type and key requirements
2. **Refine Gradually**: Add filters one at a time to narrow results
3. **Use Neutral Mode**: Keep filters around for quick toggling
4. **Combine Modes**: Mix Include and Exclude for precise control
5. **Sort Last**: Add sorting after filtering for best results
6. **Keyboard Shortcuts**: Use `Ctrl+K` for fast filter addition

## Filter Persistence

- Filters persist while navigating the product list
- Filters are reset when you refresh the page
- Use "Clear All" to remove all filters and sorting at once

## Performance

- Client-side filtering for instant results
- No server round-trips for filter changes
- Smooth for datasets up to thousands of products
- All filtering happens in real-time as you adjust filters

## Future Enhancements

Potential future features:
- Save filter presets
- Share filter configurations via URL
- AI-powered natural language filtering
- Advanced range sliders for numeric values
- Filter history and undo/redo
- Export filtered results

## Troubleshooting

**Problem**: No results showing
- Check if filters are too restrictive
- Switch some filters from Include to Neutral
- Use "Clear All" and start over

**Problem**: Attribute not showing in selector
- Verify correct product type is selected
- Some attributes are specific to motors or drives
- Check spelling in search box

**Problem**: Filter value not matching
- Values are case-insensitive for text
- Numeric values must match exactly
- Range values check if your input falls within min/max

## Architecture

The filter system is built with:

- **TypeScript**: Full type safety for all filter operations
- **React Hooks**: State management with useState and useEffect
- **Client-side Logic**: All filtering happens in the browser
- **Keyboard Navigation**: Full keyboard support like modern UIs
- **Responsive Design**: Works on desktop and mobile devices

For technical details, see:
- `/frontend/src/types/filters.ts` - Filter types and utilities
- `/frontend/src/components/FilterBar.tsx` - Main filter UI
- `/frontend/src/components/AttributeSelector.tsx` - Attribute picker
- `/frontend/src/components/FilterChip.tsx` - Individual filter chips
