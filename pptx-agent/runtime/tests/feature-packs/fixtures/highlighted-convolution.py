"""Guided algorithm walkthrough: one-channel cross-correlation and its gradients.

This source is a complete numerical experiment, not a Python execution debugger.
Edit K[0][0] or dZ[0][0], then run again. Indices start at zero; row precedes column.
The fixed settings are stride 1, padding 0 and dilation 1 (no spacing between taps).
"""

import json

# X has 3 rows and 3 columns. These integers are an arithmetic image fixture.
X = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
# K has 2 rows and 2 columns; keep this orientation while moving across X.
K = [[1, -1], [2, 0]]
BIAS = 0
# dZ is the supplied derivative of a scalar objective with respect to Z[2][2].
dZ = [[1, 1], [1, 1]]

# Two valid positions fit on each axis: 3 - 2 + 1 = 2.
Z = [[0 for _ in range(2)] for _ in range(2)]
forward_trace = []
for i in range(2):
    for j in range(2):
        # Each (i, j) names the top-left input pixel and the matching output cell.
        products = []
        for u in range(2):
            for v in range(2):
                # Kernel offsets (u, v) select four input/weight pairs without a flip.
                product = X[i + u][j + v] * K[u][v]  # WALKTHROUGH_PRODUCT
                products.append(product)
        Z[i][j] = sum(products) + BIAS  # WALKTHROUGH_OUTPUT
        # Save computed numbers for a replayable, guided patch-by-patch explanation.
        forward_trace.append({"position": [i, j], "products": products[:], "sum": Z[i][j]})

# Every derivative starts at zero and has the shape of the object it differentiates.
dK = [[0 for _ in range(2)] for _ in range(2)]
dX = [[0 for _ in range(3)] for _ in range(3)]
db = 0
backward_trace = []
for i in range(2):
    for j in range(2):
        upstream = dZ[i][j]  # WALKTHROUGH_UPSTREAM
        db += upstream  # WALKTHROUGH_BIAS
        for u in range(2):
            for v in range(2):
                # Sum every use of the same weight; assignment alone would lose uses.
                dK[u][v] += upstream * X[i + u][j + v]  # WALKTHROUGH_KERNEL
                # Several overlapping patches can contribute to the same input cell.
                dX[i + u][j + v] += upstream * K[u][v]  # WALKTHROUGH_INPUT
        # Copy rows so later accumulation cannot silently modify earlier states.
        backward_trace.append({"position": [i, j], "dK": [row[:] for row in dK],
                               "dX": [row[:] for row in dX], "db": db})

# A scene must bind its matrix and gradient displays to this actual run's result.
result = {"input": X, "kernel": K, "bias": BIAS, "output": Z,
          "forward_trace": forward_trace, "upstream": dZ,
          "dK": dK, "dX": dX, "db": db, "backward_trace": backward_trace}
print(json.dumps(result, allow_nan=False))

# Return the computed object to the local worker.
result
