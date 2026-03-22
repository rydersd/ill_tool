// Simple maze generator for Illustrator using recursive backtracking
var cols = 10;
var rows = 10;
var cellSize = 40; // points
var wallWeight = 2;
var margin = 50;

// Create new document
var doc = app.documents.add(
    DocumentColorSpace.RGB,
    cols * cellSize + margin * 2,
    rows * cellSize + margin * 2
);

var layer = doc.layers[0];
layer.name = "Maze";

// Initialize grid - each cell tracks walls: [top, right, bottom, left]
var grid = [];
var visited = [];
for (var i = 0; i < rows; i++) {
    grid[i] = [];
    visited[i] = [];
    for (var j = 0; j < cols; j++) {
        grid[i][j] = [true, true, true, true]; // all walls up
        visited[i][j] = false;
    }
}

// Recursive backtracker maze generation
var stack = [];
var cr = 0, cc = 0;
visited[cr][cc] = true;
var totalCells = rows * cols;
var visitedCount = 1;

while (visitedCount < totalCells) {
    // Find unvisited neighbors
    var neighbors = [];
    // top
    if (cr > 0 && !visited[cr-1][cc]) neighbors.push([cr-1, cc, 0, 2]);
    // right
    if (cc < cols-1 && !visited[cr][cc+1]) neighbors.push([cr, cc+1, 1, 3]);
    // bottom
    if (cr < rows-1 && !visited[cr+1][cc]) neighbors.push([cr+1, cc, 2, 0]);
    // left
    if (cc > 0 && !visited[cr][cc-1]) neighbors.push([cr, cc-1, 3, 1]);

    if (neighbors.length > 0) {
        // Pick random neighbor
        var idx = Math.floor(Math.random() * neighbors.length);
        var next = neighbors[idx];
        var nr = next[0], nc = next[1], wall = next[2], oppWall = next[3];

        // Remove walls between current and next
        grid[cr][cc][wall] = false;
        grid[nr][nc][oppWall] = false;

        stack.push([cr, cc]);
        cr = nr;
        cc = nc;
        visited[cr][cc] = true;
        visitedCount++;
    } else if (stack.length > 0) {
        var prev = stack.pop();
        cr = prev[0];
        cc = prev[1];
    }
}

// Draw the maze walls
// Illustrator Y is flipped (0 at bottom), so we work top-down from docHeight - margin
var docH = doc.height;
var originX = margin;
var originY = docH - margin;

var strokeColor = new RGBColor();
strokeColor.red = 30;
strokeColor.green = 30;
strokeColor.blue = 30;

for (var r = 0; r < rows; r++) {
    for (var c = 0; c < cols; c++) {
        var x = originX + c * cellSize;
        var y = originY - r * cellSize;

        // Top wall
        if (grid[r][c][0]) {
            var line = layer.pathItems.add();
            line.setEntirePath([[x, y], [x + cellSize, y]]);
            line.filled = false;
            line.stroked = true;
            line.strokeWidth = wallWeight;
            line.strokeColor = strokeColor;
            line.strokeCap = StrokeCap.ROUNDENDCAP;
        }
        // Right wall
        if (grid[r][c][1]) {
            var line = layer.pathItems.add();
            line.setEntirePath([[x + cellSize, y], [x + cellSize, y - cellSize]]);
            line.filled = false;
            line.stroked = true;
            line.strokeWidth = wallWeight;
            line.strokeColor = strokeColor;
            line.strokeCap = StrokeCap.ROUNDENDCAP;
        }
        // Bottom wall
        if (grid[r][c][2]) {
            var line = layer.pathItems.add();
            line.setEntirePath([[x, y - cellSize], [x + cellSize, y - cellSize]]);
            line.filled = false;
            line.stroked = true;
            line.strokeWidth = wallWeight;
            line.strokeColor = strokeColor;
            line.strokeCap = StrokeCap.ROUNDENDCAP;
        }
        // Left wall
        if (grid[r][c][3]) {
            var line = layer.pathItems.add();
            line.setEntirePath([[x, y], [x, y - cellSize]]);
            line.filled = false;
            line.stroked = true;
            line.strokeWidth = wallWeight;
            line.strokeColor = strokeColor;
            line.strokeCap = StrokeCap.ROUNDENDCAP;
        }
    }
}

// Open entrance (top-left) and exit (bottom-right)
// Remove top wall of [0,0]
// Remove bottom wall of [rows-1, cols-1]
// (Already drawn, so add white lines on top)
var bgColor = new RGBColor();
bgColor.red = 255;
bgColor.green = 255;
bgColor.blue = 255;

// Entrance - top of cell [0,0]
var entrance = layer.pathItems.add();
var ex = originX;
var ey = originY;
entrance.setEntirePath([[ex + 2, ey], [ex + cellSize - 2, ey]]);
entrance.filled = false;
entrance.stroked = true;
entrance.strokeWidth = wallWeight + 2;
entrance.strokeColor = bgColor;

// Exit - bottom of cell [rows-1, cols-1]
var exitLine = layer.pathItems.add();
var exx = originX + (cols-1) * cellSize;
var exy = originY - (rows-1) * cellSize - cellSize;
exitLine.setEntirePath([[exx + 2, exy], [exx + cellSize - 2, exy]]);
exitLine.filled = false;
exitLine.stroked = true;
exitLine.strokeWidth = wallWeight + 2;
exitLine.strokeColor = bgColor;

// Add start/end markers
var greenColor = new RGBColor();
greenColor.red = 46;
greenColor.green = 204;
greenColor.blue = 113;

var redColor = new RGBColor();
redColor.red = 231;
redColor.green = 76;
redColor.blue = 60;

// Start dot
var startDot = layer.pathItems.ellipse(
    originY - 8, originX + 8, cellSize - 16, cellSize - 16
);
startDot.filled = true;
startDot.fillColor = greenColor;
startDot.stroked = false;

// End dot
var endDot = layer.pathItems.ellipse(
    originY - (rows-1) * cellSize - 8,
    originX + (cols-1) * cellSize + 8,
    cellSize - 16, cellSize - 16
);
endDot.filled = true;
endDot.fillColor = redColor;
endDot.stroked = false;

// Add title
var title = layer.textFrames.add();
title.contents = "MAZE";
title.position = [margin, docH - 15];
title.textRange.characterAttributes.size = 18;
title.textRange.characterAttributes.fillColor = strokeColor;

'Maze created: ' + cols + 'x' + rows + ' grid';
