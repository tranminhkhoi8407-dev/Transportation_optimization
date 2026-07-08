"""
local_search.py
----------------
Hậu xử lý (post-processing) route của MỘT ngày bằng Local Search, áp dụng SAU KHI
Cheapest Insertion đã chèn xong toàn bộ candidates của ngày đó (dùng trong
weekly_scheduler, xem scheduler.py).

TẠI SAO CẦN: Cheapest Insertion là thuật toán "greedy" -- mỗi bước chọn phép chèn rẻ
nhất TẠI THỜI ĐIỂM ĐÓ, nhưng không bao giờ quay lại sửa các quyết định trước đó. Khi
route đã đông khách (50-75 điểm/ngày như ngày 1-3 trong bộ dữ liệu này), thứ tự chèn
tuần tự gần như chắc chắn để lại 2 loại "vết thừa" kinh điển:
  (a) Các đoạn đường CẮT CHÉO nhau trên bản đồ (khách X và Y ở gần nhau về mặt không
      gian nhưng route lại đi X -> ... -> nhiều điểm khác ... -> Y) -- 2-opt sửa được.
  (b) Một điểm bị "kẹt" ở vị trí không hợp lý (lúc chèn nó là lựa chọn rẻ nhất, nhưng
      giờ route đông hơn nên nhấc nó sang chỗ khác sẽ rẻ hơn) -- Or-opt sửa được, mà
      2-opt (chỉ đảo ngược đoạn, không di chuyển 1 điểm đơn lẻ ra xa) không sửa được.

RÀNG BUỘC BẮT BUỘC (không được vi phạm mục tiêu #1 của đề bài -- completion rate):
  - Local Search KHÔNG BAO GIỜ thêm hoặc bớt khách khỏi route. Chỉ đổi THỨ TỰ các
    khách đã có trong route của ngày đó. Số điểm dừng trước/sau luôn bằng nhau.
  - Mọi ứng viên move phải được TÍNH LẠI TOÀN BỘ thời gian (arrival, service_start,
    service_end) cho MỌI điểm trong route mới, y hệt cách try_insert_at_position() làm
    trong scheduler.py -- vì đổi thứ tự 2 điểm sẽ dịch chuyển giờ đến của mọi điểm
    phía sau, có thể làm cả những điểm KHÔNG liên quan trực tiếp bị trễ window.
  - Chỉ chấp nhận move nếu route mới (a) khả thi 100% (đúng time window mọi điểm,
    về kho trước 24h) VÀ (b) return_time giảm (hoặc bằng, tuỳ chế độ). Nếu không thoả
    cả 2, move bị huỷ, route giữ nguyên như cũ.

Vì (b) ở trên áp dụng cho MỌI ứng viên move, hai heuristic dùng chung 1 hàm lõi
`_rebuild_route()`: cho một THỨ TỰ MỚI của các cust_id, tính lại toàn bộ Stop và
return_time, trả về None nếu bất kỳ đâu vi phạm window/24h.
"""

from typing import Dict, List, Optional
from data_model import Customer, travel_time_minutes
from scheduler import Stop, DayRoute, DAY_END_MINUTE, earliest_feasible_service


def _rebuild_route(
    order: List[str],
    depot: Customer,
    all_points: Dict[str, Customer],
    day: int,
) -> Optional[List[Stop]]:
    """
    Cho một danh sách `order` (thứ tự cust_id mới, không thêm/bớt so với route gốc),
    tính lại toàn bộ Stop y hệt logic try_insert_at_position() trong scheduler.py.
    Trả về None nếu bất kỳ điểm nào vi phạm time window, hoặc về kho sau 24h.
    Trả về danh sách Stop mới nếu khả thi hoàn toàn.
    """
    stops: List[Stop] = []
    prev_point = depot
    departure = 0.0

    for cust_id in order:
        cust = all_points[cust_id]
        windows = cust.windows_on(day)
        if not windows:
            return None  # không còn window ngày này -> move này bất khả thi

        arrival = departure + travel_time_minutes(prev_point, cust)
        res = earliest_feasible_service(arrival, windows)
        if res is None:
            return None
        service_start, w = res
        service_end = service_start + cust.service_time

        stops.append(Stop(cust_id, arrival, service_start, service_end, w))
        prev_point = cust
        departure = service_end

    return_time = departure + travel_time_minutes(prev_point, depot)
    if return_time > DAY_END_MINUTE:
        return None

    return stops


def _route_return_time(stops: List[Stop], depot: Customer, all_points: Dict[str, Customer]) -> float:
    if not stops:
        return 0.0
    last = all_points[stops[-1].cust_id]
    return stops[-1].service_end + travel_time_minutes(last, depot)


def two_opt(
    route: DayRoute,
    depot: Customer,
    all_points: Dict[str, Customer],
    day: int,
    max_passes: int = 30,
) -> DayRoute:
    """
    2-opt cổ điển thích ứng cho VRPTW: chọn 2 vị trí cắt i < j trong route, đảo ngược
    đoạn [i, j], giữ nguyên phần trước i và sau j. Move này gỡ được các đoạn đường
    "cắt chéo" mà Cheapest Insertion để lại.

    Dùng chiến lược "first improvement" (chấp nhận move CẢI THIỆN ĐẦU TIÊN tìm được,
    rồi quét lại từ đầu) thay vì "best improvement" (quét hết mọi cặp rồi mới chọn cặp
    tốt nhất) để chạy nhanh hơn trên route đông (50-75 điểm/ngày) -- với dữ liệu cỡ này,
    chờ quét hết O(n^2) cặp mỗi vòng rồi mới áp dụng 1 move là quá chậm để lặp nhiều pass.

    `max_passes`: giới hạn số lần quét lại toàn bộ route (an toàn, tránh vòng lặp vô hạn
    về mặt lý thuyết dù trên thực tế return_time luôn giảm ngặt nên sẽ hội tụ rất nhanh).
    """
    ids = [s.cust_id for s in route.stops]
    n = len(ids)
    if n < 3:
        return route  # cần ít nhất 3 điểm mới có gì để đảo

    current_stops = route.stops
    current_return = route.return_time

    for _ in range(max_passes):
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                candidate_order = ids[:i] + ids[i:j + 1][::-1] + ids[j + 1:]
                new_stops = _rebuild_route(candidate_order, depot, all_points, day)
                if new_stops is None:
                    continue
                new_return = _route_return_time(new_stops, depot, all_points)
                if new_return < current_return - 1e-6:
                    ids = candidate_order
                    current_stops = new_stops
                    current_return = new_return
                    improved = True
                    break  # first improvement: áp dụng ngay, quét lại từ đầu
            if improved:
                break
        if not improved:
            break

    return DayRoute(day=route.day, stops=current_stops, return_time=current_return)


def or_opt(
    route: DayRoute,
    depot: Customer,
    all_points: Dict[str, Customer],
    day: int,
    segment_lengths: List[int] = [1, 2, 3],
    max_passes: int = 30,
) -> DayRoute:
    """
    Or-opt: nhấc một ĐOẠN NGẮN liên tiếp (độ dài 1, 2, hoặc 3 điểm) ra khỏi vị trí hiện
    tại trong route, chèn đoạn đó (giữ nguyên thứ tự nội bộ) vào một vị trí KHÁC trong
    cùng route. Sửa được trường hợp 2-opt bỏ sót: một điểm (hoặc cụm nhỏ) bị "kẹt" ở vị
    trí xa mọi thứ xung quanh, dù không tạo crossing rõ rệt trên bản đồ.

    Cũng dùng first-improvement như two_opt(), vì cùng lý do tốc độ trên route đông.
    """
    ids = [s.cust_id for s in route.stops]
    n = len(ids)
    if n < 2:
        return route

    current_stops = route.stops
    current_return = route.return_time

    for _ in range(max_passes):
        improved = False
        for seg_len in segment_lengths:
            if improved:
                break
            if seg_len >= n:
                continue
            for start in range(n - seg_len + 1):
                segment = ids[start:start + seg_len]
                remainder = ids[:start] + ids[start + seg_len:]
                # thử chèn `segment` (giữ nguyên thứ tự) vào mọi vị trí có thể trong remainder
                for insert_at in range(len(remainder) + 1):
                    if insert_at == start:
                        continue  # vị trí gốc, không phải move thật sự
                    candidate_order = remainder[:insert_at] + segment + remainder[insert_at:]
                    new_stops = _rebuild_route(candidate_order, depot, all_points, day)
                    if new_stops is None:
                        continue
                    new_return = _route_return_time(new_stops, depot, all_points)
                    if new_return < current_return - 1e-6:
                        ids = candidate_order
                        current_stops = new_stops
                        current_return = new_return
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
        if not improved:
            break

    return DayRoute(day=route.day, stops=current_stops, return_time=current_return)


def improve_route(
    route: DayRoute,
    depot: Customer,
    all_points: Dict[str, Customer],
    day: int,
    max_rounds: int = 5,
) -> DayRoute:
    """
    Chạy xen kẽ 2-opt <-> Or-opt cho tới khi cả 2 đều không còn cải thiện được nữa
    (hoặc hết `max_rounds` vòng lặp, an toàn phòng trường hợp dao động hiếm gặp).
    Đây là hàm mà scheduler.py sẽ gọi cho mỗi DayRoute sau khi Cheapest Insertion
    chèn xong candidates của ngày đó.
    """
    current = route
    for _ in range(max_rounds):
        before = current.return_time
        current = two_opt(current, depot, all_points, day)
        current = or_opt(current, depot, all_points, day)
        if current.return_time >= before - 1e-6:
            break
    return current
