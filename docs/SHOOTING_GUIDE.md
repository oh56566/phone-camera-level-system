# VidToLevel Shooting Guide

## Camera Setup

- Record at 4K 30fps.
- Enable optical/electronic stabilization.
- Lock exposure and focus before starting the main pass.
- Clean the lens and avoid digital zoom.

## Movement

- Walk at roughly half normal speed.
- Keep turns slow and continuous.
- Maintain at least 70% overlap between neighboring viewpoints.
- Finish loop captures by returning to the starting viewpoint.

## Residential Street Pass

- For streets and alleys, capture both travel directions.
- Use a default 45-degree body angle toward the opposite side of the road to
  keep parallax visible.
- At corners, continue 10-20m into the next segment before stopping. This gives
  COLMAP enough shared features for alignment.
- Capture the ArUco marker for at least 3 seconds while standing still.

## Avoid

- Rain, night shots, harsh backlight, and strong moving shadows.
- Large blank walls without features.
- Glass, mirrors, parked cars, and moving pedestrians when they dominate the
  frame.

## Minimum Checklist

- [ ] 4K 30fps video captured.
- [ ] AE/AF locked.
- [ ] Start/end loop closure captured.
- [ ] ArUco marker captured in focus.
- [ ] Each segment has 10-20m overlap with adjacent segments.
- [ ] Notes recorded for scale landmarks such as doors, poles, or curb widths.

