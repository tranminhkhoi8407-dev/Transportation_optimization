"""
scheduler.py
------------
Thuật toán chính:
  1) day_route_cheapest_insertion(): với một tập khách hàng "ứng viên" cho 1 ngày cụ thể,
     xây dựng 1 tuyến đường (route) bắt đầu và kết thúc tại kho, dùng Cheapest Insertion
     Heuristic có kiểm tra khả thi time-window. Trả về route đã chèn được + phần bị bỏ lại.
  2) weekly_scheduler(): vòng lặp qua các ngày Thứ 2 -> Chủ Nhật (rolling horizon),
     mỗi ngày chọn tập ứng viên ưu tiên theo "deadline gần nhất trong tuần" (giống EDF),
     gọi day_route_cheapest_insertion(), đơn nào không giao được thì đẩy sang ngày sau.
     Cuối ngày Chủ Nhật, đơn còn lại -> KHÔNG HOÀN THÀNH.

Quy ước thời gian: mỗi ngày bắt đầu lúc phút 0 (00:00) tính lại từ đầu (không cộng dồn
qua nhiều ngày), vì ngày nào xe cũng xuất phát lại từ kho. Nếu về kho sau 24:00 thì coi
là vi phạm (không cho phép; ta sẽ chặn bằng cách không chèn đơn nào khiến tổng hành trình
vượt quá 1440 phút trong ngày).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from data_model import Customer, TimeWindow, travel_time_minutes

DAY_END_MINUTE = 24 * 60  # 1440, giới hạn cứng: phải về kho trước nửa đêm


@dataclass
class Stop:
    cust_id: str
    arrival: float       # thời điểm xe ĐẾN nơi (phút trong ngày)
    service_start: float  # thời điểm BẮT ĐẦU giao (>= arrival, có thể phải chờ)
    service_end: float    # thời điểm giao xong (service_start + service_time)
    window_used: TimeWindow


@dataclass
class DayRoute:
    day: int
    stops: List[Stop] = field(default_factory=list)
    return_time: float = 0.0  # thời điểm về đến kho sau khi giao xong stop cuối

    def total_distance_time(self) -> float:
        return self.return_time

    def served_ids(self) -> List[str]:
        return [s.cust_id for s in self.stops]


def earliest_feasible_service(
    arrival: float, windows: List[TimeWindow]
) -> Optional[Tuple[float, TimeWindow]]:
    """
    Cho thời điểm xe đến `arrival` và danh sách time window trong ngày (đã sort theo start),
    trả về (service_start, window) sớm nhất khả thi:
      - Nếu đến sớm hơn 1 window -> chờ tới window.start.
      - Nếu đến trong 1 window -> phục vụ ngay tại `arrival`.
      - Nếu đến muộn hơn hết mọi window -> None (không giao được ngày này nữa qua điểm này).
    Chọn window sớm nhất mà arrival <= window.end (ưu tiên window có thể phục vụ sớm nhất).
    """
    for w in windows:
        if arrival <= w.end:
            service_start = max(arrival, w.start)
            return service_start, w
    return None


def try_insert_at_position(
    route_stops: List[Stop],
    depot: Customer,
    all_points: Dict[str, Customer],
    new_cust: Customer,
    day: int,
    pos: int,
) -> Optional[Tuple[Stop, float, List[Stop]]]:
    """
    Thử chèn `new_cust` vào vị trí `pos` (0..len(route_stops)) trong route hiện tại.
    Trả về (stop_moi, chi_phi_tang_them, danh_sach_stop_sau_chen_da_cap_nhat_lai_thoi_gian)
    nếu khả thi (không vi phạm time window của new_cust LẪN của các điểm phía sau nó),
    ngược lại trả None.

    Chi phí tăng thêm được đo bằng THỜI GIAN TĂNG THÊM của toàn tuyến (phút), bao gồm cả
    di chuyển lẫn chờ đợi -- phù hợp vì đơn vị giới hạn cứng của ta là "phải về kho trước
    24:00", nên thời gian là đại lượng cần tối thiểu hoá, không đơn thuần là quãng đường.
    """
    windows = new_cust.windows_on(day)
    if not windows:
        return None  # khách này không nhận hàng vào ngày này -> không thể chèn

    prev_point = depot if pos == 0 else all_points[route_stops[pos - 1].cust_id]
    prev_departure = 0.0 if pos == 0 else route_stops[pos - 1].service_end

    arrival = prev_departure + travel_time_minutes(prev_point, new_cust)
    result = earliest_feasible_service(arrival, windows)
    if result is None:
        return None
    service_start, used_window = result
    service_end = service_start + new_cust.service_time

    new_stop = Stop(new_cust.id, arrival, service_start, service_end, used_window)

    # Lan truyền thời gian cho các điểm PHÍA SAU vị trí chèn để kiểm tra vẫn khả thi
    updated_after: List[Stop] = []
    cur_point = new_cust
    cur_departure = service_end
    feasible = True
    for old_stop in route_stops[pos:]:
        nxt = all_points[old_stop.cust_id]
        new_arrival = cur_departure + travel_time_minutes(cur_point, nxt)
        res2 = earliest_feasible_service(new_arrival, nxt.windows_on(day))
        if res2 is None:
            feasible = False
            break
        new_service_start, new_window = res2
        new_service_end = new_service_start + nxt.service_time
        updated_after.append(Stop(old_stop.cust_id, new_arrival, new_service_start, new_service_end, new_window))
        cur_point = nxt
        cur_departure = new_service_end

    if not feasible:
        return None

    # Tính thời điểm về kho sau cùng
    last_point = cur_point
    last_departure = cur_departure
    new_return_time = last_departure + travel_time_minutes(last_point, depot)
    if new_return_time > DAY_END_MINUTE:
        return None  # vi phạm ràng buộc phải về kho trước nửa đêm

    new_full_stops = route_stops[:pos] + [new_stop] + updated_after
    old_return_component = 0.0  # sẽ tính chi phí tăng thêm ở ngoài (dùng return_time cũ)
    return new_stop, new_return_time, new_full_stops


def day_route_cheapest_insertion(
    candidates: List[Customer],
    depot: Customer,
    all_points: Dict[str, Customer],
    day: int,
) -> Tuple[DayRoute, List[Customer]]:
    """
    Xây route cho 1 ngày bằng Cheapest Insertion:
      - Bắt đầu route rỗng (chỉ có kho).
      - Lặp: với mỗi khách chưa được chèn, tìm VỊ TRÍ chèn tốt nhất (tăng ít thời gian nhất);
        trong số các khách, chọn khách có "chi phí chèn tốt nhất" nhỏ nhất -> chèn khách đó.
      - Dừng khi không còn khách nào chèn được nữa (hết ứng viên hoặc mọi phép chèn đều
        vi phạm time window / giới hạn 24h).
    Trả về (DayRoute, danh_sach_khach_khong_chen_duoc_hom_nay).
    """
    remaining = {c.id: c for c in candidates}
    stops: List[Stop] = []
    return_time = travel_time_minutes(depot, depot)  # = 0 ban đầu (route rỗng)

    while remaining:
        best_choice = None  # (delta_cost, cust_id, pos, new_stop, new_return_time, new_stops)
        for cust in remaining.values():
            for pos in range(len(stops) + 1):
                res = try_insert_at_position(stops, depot, all_points, cust, day, pos)
                if res is None:
                    continue
                new_stop, new_return_time, new_full_stops = res
                delta = new_return_time - return_time
                if best_choice is None or delta < best_choice[0]:
                    best_choice = (delta, cust.id, pos, new_stop, new_return_time, new_full_stops)

        if best_choice is None:
            break  # không còn ai chèn được nữa trong ngày hôm nay

        _, chosen_id, _, _, new_return_time, new_full_stops = best_choice
        stops = new_full_stops
        return_time = new_return_time
        del remaining[chosen_id]

    route = DayRoute(day=day, stops=stops, return_time=return_time)
    unserved = list(remaining.values())
    return route, unserved


def next_available_day(cust: Customer, after_day: int) -> Optional[int]:
    """Tìm ngày sớm nhất > after_day (và <= 7) mà khách còn window."""
    for d in range(after_day + 1, 8):
        if cust.has_any_window_on(d):
            return d
    return None


def earliest_window_end_in_week(cust: Customer, from_day: int) -> int:
    """
    Trả về 'deadline' ước lượng của khách: min(end time) trên window sớm nhất còn khả dụng
    trong tuần kể từ from_day trở đi, quy đổi ra một con số có thể so sánh được:
    (ngày * 1440 + phút_end). Dùng để ưu tiên EDF (Earliest Deadline First) khi chọn ứng viên
    trong ngày -- khách có deadline gần bị "ép" xử lý trước để tránh dồn về cuối tuần.
    Nếu khách không còn window nào từ from_day trở đi -> trả về +inf (không còn cơ hội).
    """
    best = None
    for d in range(from_day, 8):
        for w in cust.windows_on(d):
            key = d * 1440 + w.end
            if best is None or key < best:
                best = key
    return best if best is not None else float("inf")


@dataclass
class WeeklyResult:
    routes: Dict[int, DayRoute] = field(default_factory=dict)
    unfulfilled: List[str] = field(default_factory=list)  # id khách không giao được cả tuần
    delivered_day_of: Dict[str, int] = field(default_factory=dict)  # cust_id -> ngày được giao


def weekly_scheduler(
    depot: Customer,
    customers: Dict[str, Customer],
    max_orders_per_day: Optional[int] = None,
) -> WeeklyResult:
    """
    Rolling horizon qua 7 ngày. Mỗi ngày:
      1) Xác định tập "candidates" = khách chưa giao & CÒN window vào đúng ngày hôm nay.
      2) Sắp xếp candidates theo EDF (deadline gần nhất trong tuần trước) để ưu tiên chèn
         trước -- tránh tình trạng khách "khó tính" (window hẹp, sắp hết hạn) bị bỏ lại
         đến cuối tuần rồi mới phát hiện không kịp giao.
      3) Gọi day_route_cheapest_insertion() build route cho ngày đó.
      4) Khách không được chèn hôm nay: tự động thử lại vào next_available_day (đề bài
         cho phép hẹn sang hôm sau/ngày sau đó trong tuần).
      5) Hết ngày 7 (Chủ Nhật): khách nào chưa giao -> unfulfilled.

    `max_orders_per_day`: nếu muốn giới hạn số ứng viên xét mỗi ngày (để mô phỏng ràng buộc
    thực tế / giảm thời gian tính với dữ liệu lớn), có thể set số này; mặc định None = không giới hạn.
    """
    result = WeeklyResult()
    pending = dict(customers)  # id -> Customer, còn phải giao

    for day in range(1, 8):
        candidates = [c for c in pending.values() if c.has_any_window_on(day)]
        # EDF: ưu tiên khách có deadline (window.end sớm nhất còn lại trong tuần) gần nhất
        candidates.sort(key=lambda c: earliest_window_end_in_week(c, day))
        if max_orders_per_day is not None:
            candidates = candidates[:max_orders_per_day]

        all_points = {depot.id: depot, **pending}
        route, unserved_today = day_route_cheapest_insertion(candidates, depot, all_points, day)
        result.routes[day] = route

        served_ids = set(route.served_ids())
        for cid in served_ids:
            result.delivered_day_of[cid] = day
            del pending[cid]

        # Các khách hôm nay không được chọn làm candidate (vì window ngày khác) vẫn nằm
        # nguyên trong `pending`, sẽ tự động được xét lại vào đúng ngày họ có window.
        # Các khách LÀ candidate hôm nay nhưng KHÔNG chèn được (unserved_today) cũng ở lại
        # `pending` và sẽ được xét lại vào ngày kế tiếp có window (vòng lặp ngày sau tự làm).

    # Sau ngày Chủ Nhật (day=7), pending còn lại = không hoàn thành
    result.unfulfilled = list(pending.keys())
    return result


if __name__ == "__main__":
    from data_model import load_data

    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")
    res = weekly_scheduler(depot, customers)
    total_served = sum(len(r.served_ids()) for r in res.routes.values())
    print("Tổng số khách:", len(customers))
    print("Đã giao được:", total_served)
    print("Không hoàn thành:", len(res.unfulfilled))
    for day, route in res.routes.items():
        print(f"Ngày {day}: {len(route.stops)} điểm dừng, về kho lúc phút {route.return_time:.1f} "
              f"({route.return_time/60:.2f}h)")
