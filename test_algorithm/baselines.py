"""
baselines.py
------------
Hai phương án cơ sở (baseline) để so sánh với thuật toán chính,

  BASELINE 1 — "Nearest Neighbor" (luôn giao đến khách gần nhất):
    Mỗi ngày, với tập candidates hôm đó, xây route bằng cách lặp: từ vị trí hiện tại,
    tìm khách CHƯA GIAO gần nhất (Euclidean) mà việc chèn vào CUỐI route vẫn khả thi
    (đúng time window, không vượt quá 24h) -> thêm vào cuối route. Đây là heuristic
    "tham lam theo khoảng cách" kinh điển, được đề bài gợi ý làm baseline.

  BASELINE 2 — "Hạn chế tối đa việc hẹn lại" (Minimize Deferral):
    Mục tiêu bám sát ĐÚNG công thức deferral_rate dùng để đánh giá (so ngày giao thực tế
    của mỗi khách ĐÃ giao với `earliest_possible_day` = ngày sớm nhất trong tuần mà khách
    đó có window; giao trễ hơn ngày này -> tính là 1 lần "hẹn lại"). Vì vậy, với candidate
    của một ngày `d` bất kỳ (candidate = khách còn pending & có window vào đúng ngày d),
    baseline này bắt chước cách CHIA NHÓM theo mức độ ưu tiên của thuật toán chính
    (weekly_scheduler_with_local_search) — chỉ khác tiêu chí tách nhóm:

      Nhóm A — "Đến hạn" (earliest_possible_day(khách) == d): hôm nay CHÍNH LÀ ngày sớm
        nhất khách này có thể được giao. Không giao được hôm nay thì chắc chắn (nếu sau
        này còn giao được) sẽ bị tính "hẹn lại" — đây là nhóm QUYẾT ĐỊNH deferral_rate,
        cần được ưu tiên tuyệt đối trong route hôm nay.

      Nhóm B — "Quá hạn" (earliest_possible_day(khách) < d): khách đã bị tính hẹn lại từ
        trước rồi (ngày đến hạn của họ đã trôi qua mà chưa giao được), nên giao hôm nay
        hay hôm sau cũng KHÔNG cứu được deferral_rate của riêng họ nữa — nhưng vẫn cần cố
        giao càng sớm càng tốt để tránh rơi vào unfulfilled cuối tuần.

    Route mỗi ngày được xây qua 2 giai đoạn (KHÔNG có giai đoạn improve-route bằng
    2-opt/Or-opt như thuật toán chính): giai đoạn 1 chạy Cheapest Insertion CHỈ với Nhóm A
    (route trống, cạnh tranh công bằng, không bị Nhóm B chiếm chỗ trước); giai đoạn 2 lấp
    Nhóm B vào phần route còn lại, cũng bằng Cheapest Insertion (luôn chọn vị trí chèn rẻ
    nhất mỗi vòng lặp) — khác bản trước ở chỗ KHÔNG còn kiểu "chấp nhận vị trí khả thi đầu
    tiên tìm thấy", vì cách đó không hề liên quan đến việc giữ deferral_rate thấp.

Cả 3 baseline đều dùng chung luật rolling-horizon (đơn không giao được thì tự động thử
lại các ngày sau trong tuần) giống thuật toán chính, để việc so sánh là công bằng — khác
biệt DUY NHẤT nằm ở (a) thứ tự/cách nhóm candidate mỗi ngày, và (b) chiến lược chèn vào route.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from main_algorithm.data_model import Customer, euclidean, travel_time_minutes
from main_algorithm.scheduler import (
    DayRoute, Stop, WeeklyResult, DAY_END_MINUTE, day_route_cheapest_insertion_multistart,
    earliest_feasible_service, earliest_window_end_in_week,
    try_insert_at_position, day_route_cheapest_insertion,
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


def earliest_possible_day(cust: Customer) -> int:
    """Ngày SỚM NHẤT trong tuần (1..7) mà `cust` có ít nhất 1 time window.

    Đây chính là mốc `earliest_possible_day` dùng trong công thức tính deferral_rate:
    một khách ĐÃ giao bị tính là "hẹn lại" (deferred) nếu ngày giao THỰC TẾ > mốc này.
    Giả định mỗi khách luôn có >=1 window nào đó trong tuần (đảm bảo bởi load_data),
    nên min() dưới đây luôn có phần tử để lấy.
    """
    return min(d for d in range(1, 8) if cust.has_any_window_on(d))


def day_route_minimize_deferral(
    candidates: List[Customer], depot: Customer, all_points: Dict[str, Customer], day: int,
):
    """BASELINE 2 (đã sửa lại): "hạn chế tối đa việc hẹn lại khách sang ngày hôm sau".

    Bản trước đó SAI vì không hề phân biệt candidate nào hôm nay có ảnh hưởng tới
    deferral_rate, chỉ nhồi bừa theo demand tăng dần và chấp nhận vị trí chèn khả thi
    đầu tiên tìm thấy -- không liên quan gì tới mục tiêu "hạn chế hẹn lại". Bản này bám
    sát ĐÚNG công thức deferral_rate (so ngày giao thực tế với earliest_possible_day) và
    bắt chước cách CHIA NHÓM-theo-mức-độ-ưu-tiên của thuật toán chính
    (weekly_scheduler_with_local_search trong scheduler.py), chỉ khác tiêu chí tách nhóm:

      Nhóm A -- "Đến hạn" (earliest_possible_day(cust) == day): hôm nay CHÍNH LÀ ngày sớm
          nhất trong tuần mà khách này có thể được giao. Không giao được hôm nay đồng
          nghĩa (nếu sau này vẫn giao được) họ chắc chắn bị tính "hẹn lại" -- đây là nhóm
          QUYẾT ĐỊNH deferral_rate, phải được ưu tiên tuyệt đối khi xây route hôm nay.

      Nhóm B -- "Quá hạn" (earliest_possible_day(cust) < day): ngày đến hạn thật sự của
          họ đã trôi qua mà chưa giao được -- tức ĐÃ bị tính hẹn lại từ trước, không thể
          "cứu" lại deferral_rate bằng cách giao hôm nay hay hôm sau nữa. Dù vậy vẫn cần
          cố gắng giao càng sớm càng tốt để tránh họ rơi vào unfulfilled cuối tuần.

    (Với candidate của một ngày d bất kỳ, chỉ có thể earliest_possible_day <= d, không
    thể > d -- vì d là một trong các ngày khách có window -- nên Nhóm A/B chia hết đúng
    toàn bộ candidates, không sót ai.)

    Xây route qua 2 giai đoạn, cả hai đều dùng Cheapest Insertion (chọn vị trí chèn có
    local_insertion_cost thấp nhất mỗi vòng lặp, giống hệt thuật toán chính) -- KHÔNG còn
    kiểu "chấp nhận vị trí khả thi đầu tiên" của bản cũ, vì cách đó không phục vụ mục tiêu
    hạn chế hẹn lại và thường tạo ra route vòng vèo vô ích:

      GIAI ĐOẠN 1 -- xây route CHỈ với Nhóm A bằng day_route_cheapest_insertion() gốc.
          Route lúc này còn trống nên Nhóm A cạnh tranh công bằng với NHAU, không bị Nhóm
          B (vốn không còn cứu được deferral_rate) chiếm mất chỗ trước.

      GIAI ĐOẠN 2 -- lấp Nhóm B vào phần route còn lại: mỗi vòng lặp quét mọi (khách B
          còn lại, mọi vị trí chèn khả thi trong route hiện tại), chọn phép chèn có
          local_insertion_cost nhỏ nhất, chèn, lặp lại đến khi không còn ai chèn được nữa.

    KHÔNG có giai đoạn 3 (2-opt/Or-opt improve_route) -- baseline chỉ dừng lại ở route thô
    2 giai đoạn, đúng theo yêu cầu.
    """
    group_a = [c for c in candidates if earliest_possible_day(c) == day]
    group_b = [c for c in candidates if earliest_possible_day(c) < day]
    if len(group_a) + len(group_b) != len(candidates):
        raise RuntimeError("BUG: tách Nhóm A ('đến hạn') / Nhóm B ('quá hạn') không khớp tổng số candidates")

    # --- GIAI ĐOẠN 1: ưu tiên tuyệt đối Nhóm A (đến hạn đúng hôm nay) ---
    route, unserved_a = day_route_cheapest_insertion(group_a, depot, all_points, day)

    # --- GIAI ĐOẠN 2: lấp Nhóm B (đã quá hạn từ trước, ưu tiên giao sớm để tránh fail)
    # vào phần route còn lại, vẫn theo đúng cơ chế cheapest-cạnh-tranh-công-bằng. ---
    remaining_b = {c.id: c for c in group_b}
    while remaining_b:
        best_choice = None  # (local_cost, cust_id, new_full_stops, new_return_time)
        for cust in remaining_b.values():
            for pos in range(len(route.stops) + 1):
                res = try_insert_at_position(route.stops, depot, all_points, cust, day, pos)
                if res is None:
                    continue
                _new_stop, new_return_time, new_full_stops, local_cost = res
                if best_choice is None or local_cost < best_choice[0]:
                    best_choice = (local_cost, cust.id, new_full_stops, new_return_time)
        if best_choice is None:
            break  # không còn ai trong Nhóm B chèn được nữa hôm nay
        _, chosen_id, new_full_stops, new_return_time = best_choice
        route = DayRoute(day=day, stops=new_full_stops, return_time=new_return_time)
        del remaining_b[chosen_id]

    unserved = list(unserved_a) + list(remaining_b.values())
    return route, unserved


def run_baseline(depot: Customer, customers: Dict[str, Customer], strategy: str) -> WeeklyResult:
    """
    strategy: 'nearest_neighbor', 'minimize_deferral'
    Dùng chung khung rolling-horizon 7 ngày như weekly_scheduler(), chỉ khác hàm xây route/ngày.
    Candidate mỗi ngày = khách còn pending & có window đúng ngày đó (giống thuật toán chính,
    để đảm bảo so sánh công bằng về mặt "cơ hội được xét").
    """
    day_fn = {
        "nearest_neighbor": day_route_nearest_neighbor,
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
    from main_algorithm.data_model import load_data

    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")

    for strategy in ["nearest_neighbor", "minimize_deferral"]:
        res = run_baseline(depot, customers, strategy)
        total_served = sum(len(r.served_ids()) for r in res.routes.values())
        print(f"\n=== Baseline: {strategy} ===")
        print("Đã giao:", total_served, "/ Không hoàn thành:", len(res.unfulfilled))
        for day, route in res.routes.items():
            print(f"  Ngày {day}: {len(route.stops)} điểm, về kho lúc {route.return_time/60:.2f}h")