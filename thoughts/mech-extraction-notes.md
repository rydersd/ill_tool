# Mech Shape Extraction — Working Notes

## Session: 2026-03-25

### Approach v1: Threshold blobs → 0/10
### Approach v2: Canny edge fragments → 0/10 (228 confetti shapes)

### Approach v3: Construction-based blocking
Instead of detecting pixels, UNDERSTAND the form and draw construction shapes.
Like an illustrator blocking in a figure — simplified geometric forms for each body part.

### Right Mech Analysis (figure's left/right)
The figure is in ~3/4 view, turned slightly to figure's left (our right).

**Depth order (front to back):**
1. FOREGROUND: fig's left arm (our R), left leg (our R) — these come TOWARD camera
2. SAW BLADE: held in front, diagonal
3. MID: head, bandana, torso, hip armor
4. BACKGROUND: fig's right arm (our L), right leg (our L) — these go AWAY

### Key Learnings (accumulated across iterations)
- Shadows ≠ shapes. Light on a cylinder doesn't make two shapes.
- Construction = the form exists independent of lighting
- Need 15-30 clean closed shapes, each recognizable as a body part
- Use the harness: generator draws → evaluator (tyrannical art teacher) scores → iterate

### Iteration Scores: 0/10 → 3.1 → 4.1 → 4.5 → 3.0 (went DOWN)

### v3 iter1-2: Guessed coordinates → shapes float off the figure (60px above actual head)
### v3 iter3-4: Measured with scanner → shapes in right position BUT still bounding boxes

### CORE PROBLEM: Bounding boxes vs contours
Every shape is a 5-8 point simple polygon. The actual forms have complex silhouettes.
"You are drawing bounding boxes, not silhouettes." — Art Teacher
"Position without shape accuracy gives you correctly-placed wrong shapes."

### What's needed:
- MORE anchor points per shape (15-20, not 5-8) that trace the ACTUAL edge
- Dense sampling along each part's boundary, not just center/extent
- The scan data gives position; need to add CONTOUR TRACING within each part
- Each leg needs 3-4 shapes: thigh, knee joint, shin, foot (I had this but they weren't distinct enough)
- The head needs to capture the visor, brow, sensor housings — not be a box

### v5: Horizontal scan extents → rectangles by construction (3.8/10)
Even with 146 points, they sit on straight left/right edges = rectangle

### v6: findContours within tight crops → STILL rectangles (1.4/10)
Bug: tight crop = part fills crop = contour traces crop boundary
Fix needed: parts with <60% fill produce real contours; >80% fill = crop rectangle

### v7-v8: Background subtraction + bilateral smoothing
HEAD (48% fill) → FIRST REAL SILHOUETTE with visor/cap shape
SAW (45% fill) → actual blade contour
High-fill parts still rectangular

### KEY INSIGHT: fill percentage determines contour quality
- <60% fill: genuine irregular contour with concavities
- >80% fill: crop rectangle (figure fills entire crop)
- Fix: for high-fill parts, need wider context OR angular cut lines OR edge-based detection

### Score plateau at 4.x after 7 iterations
- Best shapes: red arm contour (follows actual form) and green saw blade (real contour)
- Worst shapes: torso/hip (rectangles because high fill)
- Head contour exists in data (48% fill, 12pts) but invisible in export
- Problem: can't break past rectangles for high-fill parts

### What breaks the plateau:
1. For high-fill parts: subdivide into smaller regions that drop below 60% fill threshold
2. OR: use edge-based detection (Canny) constrained by anatomical knowledge
3. OR: trace by hand using vision + measurement (the original centerline approach)
4. Need overlapping shapes showing depth hierarchy — not flat puzzle pieces
