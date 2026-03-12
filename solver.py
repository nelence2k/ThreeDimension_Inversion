import numpy as np
import pyvista as pv


def solve_thermal_field(L, W, T, k, V, T_boundary, nx=40, ny=40, nz=10):
    """
    简化的芯片热场 DEMO 求解器（方形芯片）
    
    参数:
        L, W, T: 芯片尺寸（X, Y, Z方向，um）
        k: 热导率（W/mK）
        V: 驱动电压（V）
        T_boundary: 边界温度（K）
        nx, ny, nz: 网格密度

    返回:
        grid: PyVista StructuredGrid
        stats: dict, Tmin/Tmax/Tavg/dT
    """

    # 防御性处理
    k = max(k, 1e-6)
    L = max(L, 1e-6)
    W = max(W, 1e-6)
    T = max(T, 1e-6)

    # 构建规则网格
    x = np.linspace(0, L, nx)
    y = np.linspace(0, W, ny)
    z = np.linspace(0, T, nz)

    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")

    # -------------------------------
    # 构造热场：芯片中间热，边缘接近边界温度
    # -------------------------------
    # X方向：中间更热，两端稍低
    fx = np.sin(np.pi * X / L) ** 1.2
    # Y方向：中间更热，边缘稍低
    fy = np.sin(np.pi * Y / W) ** 1.2
    # Z方向：厚度中心略热
    fz = 1.0 - np.abs(Z - T/2) / (T/2)
    fz = np.clip(fz, 0.2, 1.0)

    # 简化热源强度
    amplitude = 1400.0 * (V ** 2) / k
    geom_factor = (L / 200.0) * (20.0 / max(W, 1e-6)) ** 0.1 * (10.0 / max(T, 1e-6)) ** 0.1

    delta_T = amplitude * geom_factor * fx * fy * fz
    temperature = T_boundary + delta_T

    # 创建 PyVista StructuredGrid
    grid = pv.StructuredGrid(X, Y, Z)
    grid["Temperature"] = temperature.ravel(order="F")

    stats = {
        "Tmin": float(np.min(temperature)),
        "Tmax": float(np.max(temperature)),
        "Tavg": float(np.mean(temperature)),
        "dT": float(np.max(temperature) - np.min(temperature)),
    }

    return grid, stats


def extract_centerline_profile(grid):
    """
    提取芯片中间中心线温度曲线
    - 沿 X方向中线 Y=W/2, Z=T/2
    """
    pts = grid.points
    temps = grid["Temperature"]

    # 找最接近 Y=W/2, Z=T/2 的点
    y_abs = np.abs(pts[:, 1] - np.mean([pts[:, 1].min(), pts[:, 1].max()]))
    z_abs = np.abs(pts[:, 2] - np.mean([pts[:, 2].min(), pts[:, 2].max()]))

    score = y_abs + z_abs
    min_score = np.min(score)
    mask = np.isclose(score, min_score, atol=1e-12)

    center_pts = pts[mask]
    center_temps = temps[mask]

    # 按 X 排序
    order = np.argsort(center_pts[:, 0])
    center_pts = center_pts[order]
    center_temps = center_temps[order]

    # 同一个 X 位置可能多个点，做平均
    xs = center_pts[:, 0]
    unique_x = np.unique(xs)
    x_coords = []
    t_vals = []
    for ux in unique_x:
        idx = np.where(np.isclose(xs, ux))[0]
        x_coords.append(float(ux))
        t_vals.append(float(np.mean(center_temps[idx])))

    return np.array(x_coords), np.array(t_vals)