# Scientific Plot Digitizer Extraction Guide

## Figure-Type Decisions

Use the bundled script when:

- The plot is an XY chart with visible axes.
- A target curve or marker set has a separable color or darkness.
- The panel is cropped tightly enough that labels and legends do not contaminate the mask.
- The axis mapping can be described by independent x and y linear or log10 calibration.

Use an interactive digitizer when:

- Multiple series overlap or share color.
- Error bars, gridlines, and curve strokes cannot be separated by color.
- A curve is dashed, thin, or heavily anti-aliased.
- The figure uses broken axes, transformed axes, polar/ternary coordinates, or inset panels.

Use a VLM-assisted workflow only for rough extraction from bar/box plots or batches of paper figures, then verify against the image. VLM extraction is not a substitute for coordinate calibration when high numerical precision matters.

## Calibration Rules

- Calibrate from tick marks, not from axis-label text.
- Use far-apart calibration points to reduce pixel error.
- Crop the panel before calibration if the figure includes multiple panels.
- For logarithmic axes, calibrate using the true numeric tick values and set `x_scale` or `y_scale` to `log10`.
- If the axis is not horizontal/vertical, rotate/correct the image first or use an interactive digitizer.

## Extraction Settings

- Start with a strict color tolerance (`20-40`) for solid colored lines; increase only if the overlay misses the line.
- For black curves, start with `--mode dark --threshold 90`; lower the threshold if labels/gridlines are included.
- For dense line plots, `--trace line --line-stat median` is usually more stable than mean.
- For scatter plots, use `--trace scatter --min-area` large enough to remove text/grid noise.
- For bars, crop to the bar region and use `--trace bars`; inspect the overlay and bounding boxes carefully.

## QA Checklist

- The overlay highlights the intended series and not the axes, gridlines, legend, or labels.
- Extracted x and y ranges match the visible axis range.
- Known visible points or bar heights agree within the expected image-reading error.
- For log axes, values are positive and spacing looks multiplicative, not linear.
- Output rows are sorted by x unless order carries another meaning.
- The final response labels outputs as digitized estimates and lists any precision risks.

## Common Failure Modes

- Axis labels included in the ROI cause false components.
- Gridlines share the same color as the target curve.
- JPEG compression adds colored artifacts around labels.
- Low-resolution figures make thin curves jump between adjacent pixel rows.
- Anti-aliasing shifts the detected centerline if only edge pixels are captured.
- Multiple panels are extracted together, mixing coordinate systems.
