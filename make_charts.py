"""
make_charts.py
--------------
Sinh các biểu đồ so sánh 4 phương án (Thuật toán chính, Baseline NN, Baseline EDD-append,
Baseline Minimize-Deferral) để đưa vào báo cáo PDF. Lưu ảnh PNG độ phân giải cao vào
thư mục hiện tại.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from data_model import load_data
from weekly_route import plot_weekly_routes_interactive
from scheduler import weekly_scheduler
from baselines import run_baseline
from metrics import compute_metrics

plt.rcParams["font.family"] = "DejaVu Sans"  # hỗ trợ tốt tiếng Việt có dấu

depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")

main_result = weekly_scheduler(depot, customers)
plot_weekly_routes_interactive(depot, customers, main_result, "main_algorithm_routes.html")
nn_result = run_baseline(depot, customers, "nearest_neighbor")
edd_result = run_baseline(depot, customers, "earliest_deadline_append")
md_result = run_baseline(depot, customers, "minimize_deferral")

m_main = compute_metrics(depot, customers, main_result)
m_nn = compute_metrics(depot, customers, nn_result)
m_edd = compute_metrics(depot, customers, edd_result)
m_md = compute_metrics(depot, customers, md_result)

labels = [
    "Thuật toán chính\n(Cheapest Insertion + EDF)",
    "Baseline 1\n(Nearest Neighbor)",
    "Baseline 2\n(Earliest-Deadline\nnối đuôi)",
    "Baseline 3\n(Hạn chế tối đa\nviệc hẹn lại)",
]
colors = ["#2E86AB", "#E67E22", "#95A5A6", "#8E44AD"]

# ----- Chart 1: Completion rate + tổng quãng đường (2 subplot cạnh nhau) -----
fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))

vals_completion = [m_main.completion_rate, m_nn.completion_rate, m_edd.completion_rate, m_md.completion_rate]
bars = axes[0].bar(labels, vals_completion, color=colors)
axes[0].set_ylabel("Tỉ lệ hoàn thành (%)")
axes[0].set_title("Completion Rate — chỉ số ưu tiên #1")
axes[0].set_ylim(0, 105)
axes[0].yaxis.set_major_formatter(mticker.PercentFormatter())
axes[0].tick_params(axis="x", labelsize=8.5)
for b, v in zip(bars, vals_completion):
    axes[0].text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}%", ha="center", fontweight="bold")

vals_dist = [m_main.total_distance_km, m_nn.total_distance_km, m_edd.total_distance_km, m_md.total_distance_km]
bars2 = axes[1].bar(labels, vals_dist, color=colors)
axes[1].set_ylabel("Tổng quãng đường (km)")
axes[1].set_title("Tổng quãng đường di chuyển cả tuần")
axes[1].tick_params(axis="x", labelsize=8.5)
for b, v in zip(bars2, vals_dist):
    axes[1].text(b.get_x() + b.get_width() / 2, v + 40, f"{v:.0f} km", ha="center", fontweight="bold")

plt.tight_layout()
plt.savefig("chart1_completion_distance.png", dpi=150)
plt.close()

# ----- Chart 2: Số điểm dừng mỗi ngày, 4 phương án -----
fig, ax = plt.subplots(figsize=(10, 4.8))
days = list(range(1, 8))
day_names = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
width = 0.2

stops_main = [len(main_result.routes[d].stops) for d in days]
stops_nn = [len(nn_result.routes[d].stops) for d in days]
stops_edd = [len(edd_result.routes[d].stops) for d in days]
stops_md = [len(md_result.routes[d].stops) for d in days]

x = range(len(days))
ax.bar([i - 1.5 * width for i in x], stops_main, width, label="Thuật toán chính", color=colors[0])
ax.bar([i - 0.5 * width for i in x], stops_nn, width, label="Baseline 1: Nearest Neighbor", color=colors[1])
ax.bar([i + 0.5 * width for i in x], stops_edd, width, label="Baseline 2: Earliest-Deadline nối đuôi", color=colors[2])
ax.bar([i + 1.5 * width for i in x], stops_md, width, label="Baseline 3: Hạn chế tối đa hẹn lại", color=colors[3])
ax.set_xticks(list(x))
ax.set_xticklabels(day_names)
ax.set_ylabel("Số đơn giao trong ngày")
ax.set_title("Phân bố số đơn giao theo từng ngày trong tuần")
ax.legend(fontsize=9)
plt.tight_layout()
plt.savefig("chart2_daily_distribution.png", dpi=150)
plt.close()

# ----- Chart 3: Bar tổng hợp 4 chỉ số chất lượng (4 phương án) -----
fig, ax = plt.subplots(figsize=(9.5, 5))
metrics_names = ["Completion\nRate (%)", "Waiting time\n(giờ)", "Route balance\n(độ lệch chuẩn, giờ)", "Deferral\nrate (%)"]

main_vals = [m_main.completion_rate, m_main.total_waiting_minutes / 60, m_main.route_duration_std_hours, m_main.deferral_rate]
nn_vals = [m_nn.completion_rate, m_nn.total_waiting_minutes / 60, m_nn.route_duration_std_hours, m_nn.deferral_rate]
edd_vals = [m_edd.completion_rate, m_edd.total_waiting_minutes / 60, m_edd.route_duration_std_hours, m_edd.deferral_rate]
md_vals = [m_md.completion_rate, m_md.total_waiting_minutes / 60, m_md.route_duration_std_hours, m_md.deferral_rate]

x = range(len(metrics_names))
width = 0.2
ax.bar([i - 1.5 * width for i in x], main_vals, width, label="Thuật toán chính", color=colors[0])
ax.bar([i - 0.5 * width for i in x], nn_vals, width, label="Baseline 1: NN", color=colors[1])
ax.bar([i + 0.5 * width for i in x], edd_vals, width, label="Baseline 2: EDD nối đuôi", color=colors[2])
ax.bar([i + 1.5 * width for i in x], md_vals, width, label="Baseline 3: Hạn chế hẹn lại", color=colors[3])
ax.set_xticks(list(x))
ax.set_xticklabels(metrics_names)
ax.set_title("So sánh tổng hợp các chỉ số chất lượng lịch giao hàng")
ax.legend(fontsize=9)
plt.tight_layout()
plt.savefig("chart3_metrics_comparison.png", dpi=150)
plt.close()

print("Đã tạo xong 3 biểu đồ (4 phương án): chart1_completion_distance.png, "
      "chart2_daily_distribution.png, chart3_metrics_comparison.png")
