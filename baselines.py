"""
baselines.py
------------
Ba phương án cơ sở (baseline) để so sánh với thuật toán chính (Cheapest Insertion + EDF ngày),
đúng theo 3 gợi ý nêu trong đề bài:

  BASELINE 1 — "Nearest Neighbor" (luôn giao đến khách gần nhất):
    Mỗi ngày, với tập candidates hôm đó, xây route bằng cách lặp: từ vị trí hiện tại,
    tìm khách CHƯA GIAO gần nhất (Euclidean) mà việc chèn vào CUỐI route vẫn khả thi
    (đúng time window, không vượt quá 24h) -> thêm vào cuối route. Đây là heuristic
    "tham lam theo khoảng cách" kinh điển, được đề bài gợi ý làm baseline.

  BASELINE 2 — "Earliest Window-End First, không tối ưu chèn" (luôn giao đơn có khung
    giờ kết thúc sớm nhất trước, chèn nối đuôi theo đúng thứ tự đó — không tìm vị trí
    chèn tối ưu):
    Mỗi ngày, sắp xếp candidates theo window.end sớm nhất trong ngày hôm đó (không nhìn
    xa hơn trong tuần như EDF của thuật toán chính), rồi lần lượt thử chèn vào CUỐI route
    theo đúng thứ tự đó. Đây là "tham lam theo deadline trong ngày", đơn giản hơn EDF
    liên-ngày và không dùng cheapest insertion (chỉ nối đuôi).

  BASELINE 3 — "Hạn chế tối đa việc hẹn lại" (Minimize Deferral / Maximum Packing):
    Khác biệt CĂN BẢN so với 2 baseline trên: thay vì tối ưu quãng đường (baseline 1)
    hay xử lý theo deadline (baseline 2), baseline này đặt mục tiêu DUY NHẤT là nhồi
    được CÀNG NHIỀU đơn CÀNG TỐT vào route của ngày hôm nay, chấp nhận đi vòng vèo hơn,
    miễn là còn khả thi (đúng time window, về kho kịp giờ). Cụ thể: với mỗi candidate
    (duyệt theo thứ tự nhu cầu tăng dần -- ưu tiên "nhét" các đơn nhỏ, dễ chèn trước, để
    dành chỗ trống cho nhiều đơn hơn), thử LẦN LƯỢT MỌI vị trí có thể chèn trong route
    hiện tại và chấp nhận NGAY vị trí khả thi ĐẦU TIÊN tìm thấy -- không tìm vị trí tối
    ưu như Cheapest Insertion, không giới hạn chỉ nối đuôi như baseline 1/2. Đây chính
    là điểm tương ứng với gợi ý đề bài "hạn chế tối đa việc hẹn lại khách sang ngày hôm
    sau": ưu tiên tuyệt đối cho SỐ LƯỢNG đơn giữ lại trong ngày, hy sinh chất lượng
    route (tổng quãng đường / thời gian chờ) để đổi lấy mục tiêu đó.

Cả 3 baseline đều dùng chung luật rolling-horizon (đơn không giao được thì tự động thử
lại các ngày sau trong tuần) giống thuật toán chính, để việc so sánh là công bằng — khác
biệt DUY NHẤT nằm ở (a) thứ tự chọn candidate mỗi ngày, và (b) chiến lược chèn vào route.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from data_model import Customer, euclidean, travel_time_minutes
from scheduler import (
    DayRoute, Stop, WeeklyResult, DAY_END_MINUTE,
    earliest_feasible_service, earliest_window_end_in_week,
    try_insert_at_position,
)


def _try_append_at_end(
    stops: List[Stop], depot: Customer, all_points: Dict[str, Customer],
    cust: Customer, day: int,
) -> Optional[Stop]:
    """Thử nối `cust` vào CUỐI route hiện tại (không chèn giữa). Trả về Stop mới nếu khả thi."""
    windows = cust.windows_on(day)
    if not windows:
        return None
    prev_point = depot if not stops else all_points[stops[-1].cust_id]
    prev_departure = 0.0 if not stops else stops[-1].service_end
    arrival = prev_departure + travel_time_minutes(prev_point, cust)
    res = earliest_feasible_service(arrival, windows)
    if res is None:
        return None
    service_start, w = res
    service_end = service_start + cust.service_time
    # kiểm tra về kho vẫn kịp trước 24h
    return_time = service_end + travel_time_minutes(cust, depot)
    if return_time > DAY_END_MINUTE:
        return None
    return Stop(cust.id, arrival, service_start, service_end, w)


def day_route_nearest_neighbor(
    candidates: List[Customer], depot: Customer, all_points: Dict[str, Customer], day: int,
):
    """BASELINE 1: luôn chọn khách CHƯA GIAO gần điểm hiện tại nhất (Euclidean) mà nối đuôi
    được (thoả time window + về kho kịp giờ)."""
    remaining = {c.id: c for c in candidates}
    stops: List[Stop] = []
    current_point = depot

    while remaining:
        best = None  # (distance, cust_id, stop)
        for cust in remaining.values():
            stop = _try_append_at_end(stops, depot, all_points, cust, day)
            if stop is None:
                continue
            d = euclidean(current_point, cust)
            if best is None or d < best[0]:
                best = (d, cust.id, stop)
        if best is None:
            break
        _, chosen_id, stop = best
        stops.append(stop)
        current_point = all_points[chosen_id]
        del remaining[chosen_id]

    return_time = 0.0 if not stops else stops[-1].service_end + travel_time_minutes(current_point, depot)
    route = DayRoute(day=day, stops=stops, return_time=return_time)
    return route, list(remaining.values())


def day_route_earliest_deadline_append(
    candidates: List[Customer], depot: Customer, all_points: Dict[str, Customer], day: int,
):
    """BASELINE 2: sắp xếp candidates theo window.end sớm nhất TRONG NGÀY HÔM ĐÓ, rồi nối
    đuôi lần lượt (không tìm vị trí chèn tối ưu, không nhìn deadline xa hơn trong tuần)."""

    def day_deadline(c: Customer) -> int:
        wins = c.windows_on(day)
        return min(w.end for w in wins) if wins else float("inf")

    ordered = sorted(candidates, key=day_deadline)
    stops: List[Stop] = []
    current_point = depot
    unserved = []

    for cust in ordered:
        stop = _try_append_at_end(stops, depot, all_points, cust, day)
        if stop is None:
            unserved.append(cust)
            continue
        stops.append(stop)
        current_point = all_points[cust.id]

    return_time = 0.0 if not stops else stops[-1].service_end + travel_time_minutes(current_point, depot)
    route = DayRoute(day=day, stops=stops, return_time=return_time)
    return route, unserved


def day_route_minimize_deferral(
    candidates: List[Customer], depot: Customer, all_points: Dict[str, Customer], day: int,
):
    """BASELINE 3: "hạn chế tối đa việc hẹn lại khách sang ngày hôm sau".

    Khác với Cheapest Insertion (thuật toán chính) vốn quét HẾT mọi (khách, vị trí) rồi
    mới chọn phép chèn rẻ nhất, hàm này theo đúng tinh thần "maximum packing": duyệt
    candidates theo demand TĂNG DẦN (đơn nhỏ dễ "nhét vừa" hơn, ưu tiên xử lý trước để
    dành chỗ cho được nhiều đơn hơn về sau), và với MỖI candidate, thử lần lượt từng vị
    trí chèn từ đầu route -> cuối route, CHẤP NHẬN NGAY vị trí khả thi ĐẦU TIÊN tìm được
    (không so sánh tiếp các vị trí còn lại để tìm vị trí "rẻ nhất"). Mục tiêu duy nhất là
    tối đa hoá SỐ LƯỢNG đơn giữ được trong ngày hôm nay, chấp nhận route có thể đi vòng
    vèo, kém tối ưu về quãng đường/thời gian hơn thuật toán chính.
    """

    def demand_key(c: Customer) -> float:
        return c.demand

    ordered = sorted(candidates, key=demand_key)
    stops: List[Stop] = []
    unserved: List[Customer] = []

    for cust in ordered:
        placed = False
        for pos in range(len(stops) + 1):
            res = try_insert_at_position(stops, depot, all_points, cust, day, pos)
            if res is not None:
                _new_stop, _new_return_time, new_full_stops, _local_cost = res
                stops = new_full_stops
                placed = True
                break  # dừng ngay khi tìm được 1 vị trí khả thi -- không tìm tiếp vị trí tốt hơn
        if not placed:
            unserved.append(cust)

    return_time = 0.0
    if stops:
        last_point = all_points[stops[-1].cust_id]
        return_time = stops[-1].service_end + travel_time_minutes(last_point, depot)
    route = DayRoute(day=day, stops=stops, return_time=return_time)
    return route, unserved


def run_baseline(depot: Customer, customers: Dict[str, Customer], strategy: str) -> WeeklyResult:
    """
    strategy: 'nearest_neighbor', 'earliest_deadline_append', hoặc 'minimize_deferral'
    Dùng chung khung rolling-horizon 7 ngày như weekly_scheduler_with_local_search(), chỉ khác hàm xây route/ngày.
    Candidate mỗi ngày = khách còn pending & có window đúng ngày đó (giống thuật toán chính,
    để đảm bảo so sánh công bằng về mặt "cơ hội được xét").
    """
    day_fn = {
        "nearest_neighbor": day_route_nearest_neighbor,
        "earliest_deadline_append": day_route_earliest_deadline_append,
        "minimize_deferral": day_route_minimize_deferral,
    }[strategy]

    result = WeeklyResult()
    pending = dict(customers)

    for day in range(1, 8):
        candidates = [c for c in pending.values() if c.has_any_window_on(day)]
        all_points = {depot.id: depot, **pending}
        route, _unserved_today = day_fn(candidates, depot, all_points, day)
        result.routes[day] = route

        for stop in route.stops:
            result.delivered_day_of[stop.cust_id] = day
            del pending[stop.cust_id]

    result.unfulfilled = list(pending.keys())
    return result


if __name__ == "__main__":
    from data_model import load_data

    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")

    for strategy in ["nearest_neighbor", "earliest_deadline_append", "minimize_deferral"]:
        res = run_baseline(depot, customers, strategy)
        total_served = sum(len(r.served_ids()) for r in res.routes.values())
        print(f"\n=== Baseline: {strategy} ===")
        print("Đã giao:", total_served, "/ Không hoàn thành:", len(res.unfulfilled))
        for day, route in res.routes.items():
            print(f"  Ngày {day}: {len(route.stops)} điểm, về kho lúc {route.return_time/60:.2f}h")