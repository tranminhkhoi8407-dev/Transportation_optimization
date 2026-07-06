"""
metrics.py
----------
Bộ chỉ số đánh giá chất lượng một lịch giao hàng (WeeklyResult), theo đúng yêu cầu #2
của đề bài: "đề xuất cách đánh giá chất lượng... và nêu rõ tiêu chí nào được ưu tiên hơn".

Các chỉ số, THEO THỨ TỰ ƯU TIÊN mà báo cáo sẽ lập luận (giải thích chi tiết hơn trong report):
  (1) Completion Rate (%)      -- ƯU TIÊN CAO NHẤT: tỉ lệ đơn giao thành công trong tuần.
                                   Đây là chỉ số "sống còn" của hệ thống logistics -- một
                                   route rất ngắn nhưng bỏ sót nhiều đơn thì vô giá trị
                                   với khách hàng lẫn doanh nghiệp.
  (2) Total Travel Distance (km) -- ưu tiên THỨ HAI: tổng quãng đường xe chạy cả tuần,
                                   phản ánh trực tiếp chi phí vận hành (xăng, khấu hao,
                                   nhân công theo giờ).
  (3) Total Waiting Time (phút) -- thời gian xe phải ĐỨNG CHỜ khách vì đến sớm hơn window.
                                   Chờ đợi là thời gian "chết", không tạo giá trị, nên
                                   cũng cần tối thiểu hoá, nhưng ít quan trọng hơn (2) vì
                                   không tốn nhiên liệu, chỉ tốn thời gian ca làm việc.
  (4) Route Duration Balance (độ lệch chuẩn giờ-về-kho giữa các ngày) -- đo mức cân bằng
                                   khối lượng công việc giữa các ngày trong tuần; một lịch
                                   "dồn" quá nhiều vào 1-2 ngày (làm việc sát 24h) trong khi
                                   ngày khác gần như trống là lịch kém bền vững cho tài xế.
  (5) Deferral Rate (%)         -- tỉ lệ đơn phải "hẹn lại" sang ngày khác thay vì giao
                                   ngay ngày có thể giao sớm nhất -- phản ánh mức độ "linh
                                   hoạt bị dùng tới"; không phải lúc nào thấp cũng tốt (đôi
                                   khi hẹn lại là hợp lý để tối ưu tổng thể), nên đây là chỉ
                                   số THAM KHẢO, không dùng để xếp hạng.

Thứ tự (1) > (2) > (3) > (4) được set cứng vì đề bài nhấn mạnh "không hoàn thành" là hậu
quả nghiêm trọng nhất (mất đơn hàng, mất uy tín) -- nên bất kỳ phương án nào đánh đổi vài
km/phút chờ để cứu thêm một đơn hàng đều đáng giá.
"""

import math
from dataclasses import dataclass
from typing import Dict, List
from data_model import Customer, euclidean
from scheduler import WeeklyResult


@dataclass
class DayMetrics:
    day: int
    n_stops: int
    distance_km: float
    waiting_minutes: float
    return_hour: float


@dataclass
class WeeklyMetrics:
    completion_rate: float           # %
    n_delivered: int
    n_total: int
    n_unfulfilled: int
    total_distance_km: float
    total_waiting_minutes: float
    route_duration_std_hours: float  # độ lệch chuẩn giờ về kho giữa các ngày có hoạt động
    deferral_rate: float             # % đơn KHÔNG được giao vào ngày sớm nhất có thể
    per_day: List[DayMetrics]


def compute_metrics(
    depot: Customer, customers: Dict[str, Customer], result: WeeklyResult
) -> WeeklyMetrics:
    n_total = len(customers)
    n_delivered = sum(len(r.served_ids()) for r in result.routes.values())
    n_unfulfilled = len(result.unfulfilled)

    per_day: List[DayMetrics] = []
    total_distance = 0.0
    total_waiting = 0.0
    active_return_hours = []

    all_points = {depot.id: depot, **customers}

    for day, route in result.routes.items():
        dist = 0.0
        wait = 0.0
        prev_point = depot
        prev_departure = 0.0
        for stop in route.stops:
            cust = all_points[stop.cust_id]
            dist += euclidean(prev_point, cust)
            wait += max(0.0, stop.service_start - stop.arrival)
            prev_point = cust
            prev_departure = stop.service_end
        if route.stops:
            dist += euclidean(prev_point, depot)
        total_distance += dist
        total_waiting += wait
        if route.stops:
            active_return_hours.append(route.return_time / 60.0)
        per_day.append(DayMetrics(day, len(route.stops), dist, wait, route.return_time / 60.0))

    if len(active_return_hours) >= 2:
        mean_h = sum(active_return_hours) / len(active_return_hours)
        var_h = sum((h - mean_h) ** 2 for h in active_return_hours) / len(active_return_hours)
        std_h = math.sqrt(var_h)
    else:
        std_h = 0.0

    # Deferral: với mỗi khách ĐÃ giao, so sánh ngày giao thực tế với ngày SỚM NHẤT có window
    # trong tuần mà khách đó có -- nếu giao trễ hơn ngày sớm nhất đó => bị "hẹn lại" ít nhất 1 lần.
    n_deferred = 0
    for cid, day_delivered in result.delivered_day_of.items():
        cust = customers[cid]
        earliest_possible_day = min(d for d in range(1, 8) if cust.has_any_window_on(d))
        if day_delivered > earliest_possible_day:
            n_deferred += 1
    deferral_rate = (n_deferred / n_delivered * 100.0) if n_delivered > 0 else 0.0

    return WeeklyMetrics(
        completion_rate=n_delivered / n_total * 100.0,
        n_delivered=n_delivered,
        n_total=n_total,
        n_unfulfilled=n_unfulfilled,
        total_distance_km=total_distance,
        total_waiting_minutes=total_waiting,
        route_duration_std_hours=std_h,
        deferral_rate=deferral_rate,
        per_day=per_day,
    )


def print_metrics(name: str, m: WeeklyMetrics):
    print(f"\n=== {name} ===")
    print(f"  Completion rate       : {m.completion_rate:.2f}%  ({m.n_delivered}/{m.n_total} đơn)")
    print(f"  Không hoàn thành      : {m.n_unfulfilled} đơn")
    print(f"  Tổng quãng đường      : {m.total_distance_km:.1f} km")
    print(f"  Tổng thời gian chờ    : {m.total_waiting_minutes:.1f} phút")
    print(f"  Độ lệch chuẩn giờ-về  : {m.route_duration_std_hours:.2f} giờ (giữa các ngày hoạt động)")
    print(f"  Tỉ lệ đơn bị hẹn lại  : {m.deferral_rate:.2f}%")


if __name__ == "__main__":
    from data_model import load_data
    from scheduler import weekly_scheduler
    from baselines import run_baseline

    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")

    main_result = weekly_scheduler(depot, customers)
    m_main = compute_metrics(depot, customers, main_result)
    print_metrics("Thuật toán chính (Cheapest Insertion + EDF liên-ngày)", m_main)

    nn_result = run_baseline(depot, customers, "nearest_neighbor")
    m_nn = compute_metrics(depot, customers, nn_result)
    print_metrics("Baseline 1 (Nearest Neighbor)", m_nn)

    edd_result = run_baseline(depot, customers, "earliest_deadline_append")
    m_edd = compute_metrics(depot, customers, edd_result)
    print_metrics("Baseline 2 (Earliest-Deadline-in-day, nối đuôi)", m_edd)

    md_result = run_baseline(depot, customers, "minimize_deferral")
    m_md = compute_metrics(depot, customers, md_result)
    print_metrics("Baseline 3 (Hạn chế tối đa việc hẹn lại)", m_md)
