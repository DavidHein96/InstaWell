# Layout Designer Guide

The Layout Designer is a visual tool for creating plate layout CSV files without using Excel.

## Features

- **Visual Grid**: Interactive 96-well or 384-well plate representation
- **Smart Import**: Upload raw.csv to automatically highlight wells with data
- **Easy Assignment**: Select wells and assign conditions with a form
- **Export**: Download layout.csv ready for InstaWell pipeline

## How to Use

### Step 1: Choose Plate Type

Select either 96-well or 384-well plate format from the dropdown.

### Step 2: Import Wells (Optional)

If you already have a raw data CSV:
1. Click "Import from Raw CSV"
2. Select your raw.csv file
3. Wells with data will be highlighted in blue

### Step 3: Select Wells

- Click on wells in the grid to select them
- Drag to select multiple wells
- Selected wells will be highlighted
- You'll see "X wells selected" below the grid

### Step 4: Assign Conditions

Fill in the condition form:
- **Concentration**: Numeric value (e.g., 10)
- **Unit**: Select nM, uM, or mM
- **Ligand**: Compound name (e.g., ATP)
- **Protein**: Protein name or "NPC" for no-protein controls
- **Buffer**: Buffer condition (e.g., Buffer1)

Click "Assign to Wells" to apply the condition.

### Step 5: Repeat or Modify

- Select different wells and assign different conditions
- Use "Clear Selected" to remove conditions from selected wells
- Use "Reset All" to start over

### Step 6: Export

Click "Download Layout CSV" to save your layout.

The exported CSV will have the format:
```
Well,1,2,3,4,...
A,10uM_ATP_Protein1_Buffer1,10uM_ATP_Protein1_Buffer1,...
B,10uM_ATP_NPC_Buffer1,10uM_ATP_NPC_Buffer1,...
...
```

## Tips

- **Use NPC for background controls**: Assign wells with no protein as "NPC" in the protein field
- **Group replicates**: Assign the same condition to multiple wells (technical replicates)
- **Visual verification**: Each well shows a compact view of its assignment
- **Import first**: If you have raw data, import it first to see which wells need conditions

## Integration with Pipeline

After exporting your layout.csv:

1. Return to the "New Experiment" section
2. Upload your raw.csv
3. Upload the exported layout.csv
4. Configure separator and fields
5. Run the pipeline

Or use the CLI:
```bash
instawell init my_experiment --raw raw.csv --layout layout.csv
instawell run my_experiment --all
```

## Example Workflow

1. **Prepare**: Have your raw data CSV with Temperature column and well columns (A1, A2, etc.)
2. **Open Designer**: Click "Show Designer" if hidden
3. **Import**: Upload raw.csv to see which wells have data
4. **Design Conditions**:
   - Select wells A1, A2, A3 → Assign "10uM ATP Protein1 Buffer1"
   - Select wells A4, A5, A6 → Assign "10uM ATP NPC Buffer1"
   - Select wells B1, B2, B3 → Assign "20uM ATP Protein1 Buffer1"
   - ... repeat for all conditions
5. **Export**: Download layout.csv
6. **Run**: Use with InstaWell pipeline!
