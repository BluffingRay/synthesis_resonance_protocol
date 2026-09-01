import math, os, time
import numpy as np

def bench(label, fn, n=3):
    times = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t)
    return label, min(times), times

# 1) single-threaded vector hot-path (numpy ops like the sim's distance loops)
def linalg_loop():
    a = np.random.rand(50_000, 2)
    x, y = a[:, 0], a[:, 1]
    s = 0.0
    for i in range(200):
        s += np.hypot(x, y).sum()  # hypot vectorized (sim uses math.hypot; approx)
    return s

# 2) single-threaded pure-math hypot loop (the real sim hot path)
def hypot_loop():
    s = 0.0
    for _ in range(8_000_000):
        s += math.hypot(3.0, 4.0)
    return s

# 3) multithreaded numpy matmul (uses BLAS / cores)
def matmul():
    for _ in range(30):
        np.dot(np.random.rand(256, 256), np.random.rand(256, 256).T)

print("numpy", np.__version__, "cores os", os.cpu_count())
for label, fn in [("numpy.hypot-loop(100k,200)", linalg_loop),
                  ("math.hypot 8M           ", hypot_loop),
                  ("matmul 256x256 x30      ", matmul)]:
    lab, best, _ = bench(label, fn)
    print(f"best {label:28s} {best*1000:8.2f} ms")