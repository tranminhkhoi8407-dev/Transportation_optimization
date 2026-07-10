"""
make_chart_local_search.py
---------------------------
So sánh Thuật toán chính TRƯỚC và SAU khi thêm Local Search (2-opt + Or-opt), tách rõ
đóng góp của (a) riêng Local Search (chỉ đổi thứ tự, không đổi completion rate) và
(b) bước "chèn thêm candidate bị bỏ lại" (có thể tăng nhẹ completion rate/route length).
Giữ cùng style màu với make_charts.py để nhất quán khi đưa vào report.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from main_algorithm.data_model import load_data, euclidean
from main_algorithm.scheduler import (
    weekly_scheduler, weekly_scheduler_with_local_search,
    day_route_cheapest_insertion, earliest_window_end_in_week, WeeklyResult,
)
from main_algorithm.local_search import improve_route
from test_algorithm.metrics import compute_metrics

plt.rcParams["font.family"] = "DejaVu Sans"

depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")
all_points_full = {depot.id: depot, **customers}


def route_distance(route):
    if not route.stops:
        return 0.0
    d = euclidean(depot, all_points_full[route.stops[0].cust_id])
    for a, b in zip(route.stops, route.stops[1:]):
        d += euclidean(all_points_full[a.cust_id], all_points_full[b.cust_id])
    d += euclidean(all_points_full[route.stops[-1].cust_id], depot)
    return d


# --- 3 biến thể: Cheapest Insertion + EDF + local_cost_insertion / thêm Local Search / thêm multi-start cho nhóm ưu tiên ---
res_base = weekly_scheduler(depot, customers)

pending = dict(customers)
res_ls_only = WeeklyResult()
for day in range(1, 8):
    candidates = [c for c in pending.values() if c.has_any_window_on(day)]
    candidates.sort(key=lambda c: earliest_window_end_in_week(c, day))
    all_points = {depot.id: depot, **pending}
    route, _unserved = day_route_cheapest_insertion(candidates, depot, all_points, day)
    route = improve_route(route, depot, all_points, day)
    res_ls_only.routes[day] = route
    for cid in set(route.served_ids()):
        res_ls_only.delivered_day_of[cid] = day
        del pending[cid]
res_ls_only.unfulfilled = list(pending.keys())

res_full = weekly_scheduler_with_local_search(depot, customers)

m_base = compute_metrics(depot, customers, res_base)
m_ls_only = compute_metrics(depot, customers, res_ls_only)
m_full = compute_metrics(depot, customers, res_full)

d_base = sum(route_distance(r) for r in res_base.routes.values())
d_ls_only = sum(route_distance(r) for r in res_ls_only.routes.values())
d_full = sum(route_distance(r) for r in res_full.routes.values())

labels = [
    "Gốc\n(Cheapest Insertion\n+ EDF + Heuristic)",
    "+ Local Search\n(2-opt + Or-opt)\nchỉ đổi thứ tự",
    "+ multi-start\ncho nhóm ưu tiên",
]
colors = ["#2E86AB", "#27AE60", "#8E44AD"]

fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))

# Panel 1: Completion rate
vals_completion = [m_base.completion_rate, m_ls_only.completion_rate, m_full.completion_rate]
bars = axes[0].bar(labels, vals_completion, color=colors)
axes[0].set_ylabel("Tỉ lệ hoàn thành (%)")
axes[0].set_title("Completion Rate")
axes[0].set_ylim(0, 105)
axes[0].tick_params(axis="x", labelsize=8.5)
for b, v in zip(bars, vals_completion):
    axes[0].text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.2f}%", ha="center", fontweight="bold", fontsize=9)

# Panel 2: Tổng quãng đường THUẦN (không phải return_time)
vals_dist = [d_base, d_ls_only, d_full]
bars2 = axes[1].bar(labels, vals_dist, color=colors)
axes[1].set_ylabel("Tổng quãng đường thuần (km)")
axes[1].set_title("Tổng quãng đường di chuyển cả tuần")
axes[1].tick_params(axis="x", labelsize=8.5)
for b, v in zip(bars2, vals_dist):
    axes[1].text(b.get_x() + b.get_width() / 2, v + 15, f"{v:.1f} km", ha="center", fontweight="bold", fontsize=9)

# Panel 3: Tổng return_time (thước đo mà Local Search thực sự tối ưu)
vals_return = [
    sum(r.return_time for r in res_base.routes.values() if r.stops),
    sum(r.return_time for r in res_ls_only.routes.values() if r.stops),
    sum(r.return_time for r in res_full.routes.values() if r.stops),
]
vals_return_h = [v / 60 for v in vals_return]
bars3 = axes[2].bar(labels, vals_return_h, color=colors)
axes[2].set_ylabel("Tổng return_time (giờ)")
axes[2].set_title("Tổng return_time cả tuần\n(thước đo Local Search tối ưu)")
axes[2].tick_params(axis="x", labelsize=8.5)
for b, v in zip(bars3, vals_return_h):
    axes[2].text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}h", ha="center", fontweight="bold", fontsize=9)

plt.tight_layout()
plt.savefig("test_algorithm/fig/chart4_local_search_comparison.png", dpi=150)
plt.close()

print("Đã tạo chart4_local_search_comparison.png")
print()
print(f"Completion rate : gốc={m_base.completion_rate:.2f}%  ->  +LS={m_ls_only.completion_rate:.2f}%  ->  +multi-start={m_full.completion_rate:.2f}%")
print(f"Distance thuần  : gốc={d_base:.1f}km  ->  +LS={d_ls_only:.1f}km ({(d_base-d_ls_only)/d_base*100:+.2f}%)  ->  +multi-start={d_full:.1f}km ({(d_base-d_full)/d_base*100:+.2f}%)")
print(f"return_time     : gốc={vals_return_h[0]:.1f}h  ->  +LS={vals_return_h[1]:.1f}h ({(vals_return_h[0]-vals_return_h[1])/vals_return_h[0]*100:+.2f}%)  ->  +multi-start={vals_return_h[2]:.1f}h ({(vals_return_h[0]-vals_return_h[2])/vals_return_h[0]*100:+.2f}%)")
