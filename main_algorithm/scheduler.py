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
from main_algorithm.data_model import Customer, TimeWindow, travel_time_minutes

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
) -> Optional[Tuple[Stop, float, List[Stop], float]]:
    """
    Thử chèn `new_cust` vào vị trí `pos` (0..len(route_stops)) trong route hiện tại.
    Trả về (stop_moi, new_return_time, danh_sach_stop_sau_chen_da_cap_nhat_lai_thoi_gian,
    local_insertion_cost) nếu khả thi (không vi phạm time window của new_cust LẪN của các
    điểm phía sau nó), ngược lại trả None.

    `new_return_time`: thời điểm về kho MỚI của toàn route -- dùng để KIỂM TRA KHẢ THI
    (<=24h) và để cập nhật return_time thật của route. KHÔNG dùng giá trị này để XẾP HẠNG
    ứng viên chèn (xem local_insertion_cost bên dưới, và giải thích trong BUGFIX_NOTES.md).

    `local_insertion_cost`: chi phí CỤC BỘ của riêng phép chèn này, gồm 2 phần:
      (a) quãng đường-thời gian tăng thêm TẠI CHỖ chèn:
              travel(prev, new) + travel(new, next) - travel(prev, next)
          (nếu chèn cuối route, next = None -> chỉ có travel(prev, new), không có phần trừ)
      (b) waiting time PHÁT SINH của riêng new_cust (nếu new_cust phải chờ đến window.start).
    Đây là định nghĩa CHUẨN của "Cheapest Insertion Cost" trong y văn VRPTW (Solomon 1987),
    KHÔNG cộng dồn phần "waiting-time bị dịch chuyển dây chuyền" của các điểm phía sau vị
    trí chèn -- xem BUGFIX_NOTES.md để hiểu tại sao cộng dồn phần đó làm sai lệch xếp hạng
    khi route đã đông (chèn-giữa bị phạt oan so với chèn-cuối).
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

    # --- Tính local_insertion_cost (KHÔNG phụ thuộc các điểm phía sau) ---
    travel_prev_new = travel_time_minutes(prev_point, new_cust)
    own_waiting = max(0.0, service_start - arrival)  # thời gian new_cust tự phải chờ
    if pos < len(route_stops):
        next_point = all_points[route_stops[pos].cust_id]
        travel_prev_next_old = travel_time_minutes(prev_point, next_point)
        travel_new_next = travel_time_minutes(new_cust, next_point)
        detour = travel_prev_new + travel_new_next - travel_prev_next_old
    else:
        detour = travel_prev_new  # chèn cuối route: không có "next" để trừ lại
    local_insertion_cost = detour + own_waiting

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
    return new_stop, new_return_time, new_full_stops, local_insertion_cost


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
        best_choice = None  # (local_cost, cust_id, pos, new_stop, new_return_time, new_stops)
        for cust in remaining.values():
            for pos in range(len(stops) + 1):
                res = try_insert_at_position(stops, depot, all_points, cust, day, pos)
                if res is None:
                    continue
                new_stop, new_return_time, new_full_stops, local_cost = res
                # XẾP HẠNG theo local_insertion_cost (chi phí chèn CỤC BỘ tại chỗ chèn),
                # KHÔNG dùng (new_return_time - return_time). Lý do: hiệu số return_time
                # cộng dồn cả phần waiting-time bị dịch chuyển dây chuyền của MỌI điểm phía
                # sau vị trí chèn -- khi route đã đông, phần dịch chuyển này thường LỚN HƠN
                # nhiều so với chi phí chèn thật, khiến phép chèn-giữa (dù khách ở rất gần
                # route) bị "phạt oan" nặng hơn phép chèn-cuối (dù khách ở xa) chỉ vì có
                # nhiều điểm phía sau bị dịch lịch. local_insertion_cost đo đúng "chèn khách
                # này tốn thêm bao nhiêu" theo đúng định nghĩa Cheapest Insertion cổ điển,
                # không lẫn hệ quả dây chuyền của các quyết định TRƯỚC ĐÓ vào việc so sánh.
                # (Feasibility -- bao gồm chặn 24h -- vẫn được try_insert_at_position() kiểm
                # tra đầy đủ dựa trên new_return_time như cũ; ở đây chỉ đổi tiêu chí XẾP HẠNG.)
                if best_choice is None or local_cost < best_choice[0]:
                    best_choice = (local_cost, cust.id, pos, new_stop, new_return_time, new_full_stops)

        if best_choice is None:
            break  # không còn ai chèn được nữa trong ngày hôm nay

        _, chosen_id, _, _, new_return_time, new_full_stops = best_choice
        stops = new_full_stops
        return_time = new_return_time  # return_time THẬT của route vẫn phải lấy new_return_time
        del remaining[chosen_id]

    route = DayRoute(day=day, stops=stops, return_time=return_time)
    unserved = list(remaining.values())
    return route, unserved

def day_route_cheapest_insertion_multistart(
    candidates: List[Customer],
    depot: Customer,
    all_points: Dict[str, Customer],
    day: int,
) -> Tuple[DayRoute, List[Customer]]:
    """
    Biến thể multi-start của day_route_cheapest_insertion(), CHỈ dùng cho Giai đoạn 1
    (last-chance) của weekly_scheduler_with_local_search() -- KHÔNG dùng ở Giai đoạn 2,
    KHÔNG dùng trong baselines.py (baselines cần giữ nguyên day_route_cheapest_insertion()
    gốc để việc so sánh 4 phương án trong report vẫn công bằng).

    ĐỘNG LỰC (xem BUGFIX_NOTES.md, mục "Last-chance reserve"): Cheapest Insertion là
    greedy thuần -- một khi 2 candidate có chi phí chèn gần bằng nhau ở bước đầu, thứ tự
    remaining.values() (phụ thuộc thứ tự dict, tức thứ tự đọc CSV) quyết định luôn ai
    thắng ai thua ở bước đó, và với nhóm last-chance thua-là-mất-luôn. Trace thủ công
    trên bộ dữ liệu TMH2026 Bảng B cho thấy: với ĐÚNG một nhóm last-chance 15 người
    (ngày 5), chạy Cheapest Insertion chuẩn (route trống, thứ tự dict tự nhiên) chỉ chèn
    được 13/15 -- nhưng nếu ép bước ĐẦU TIÊN phải chèn một trong vài candidate cụ thể
    (rồi để các bước sau cạnh tranh cheapest bình thường như cũ), kết quả tăng lên 14/15
    một cách ổn định. Đây KHÔNG phải may rủi: random search hàng chục nghìn thứ tự chèn
    khác nhau cho nhóm 15 người này chưa từng vượt quá 14/15 -- tức 14/15 là trần vật lý
    thật của khung giờ hẹp đó, còn 13/15 của bản Cheapest Insertion chuẩn là do THUA OAN
    vì thứ tự duyệt, không phải vì bài toán chỉ cho phép 13.

    CÁCH LÀM: thử LẦN LƯỢT từng candidate làm "người được ép chèn trước" (route trống lúc
    đó nên chỉ có đúng 1 vị trí khả thi cho họ -- pos=0), rồi để toàn bộ phần còn lại chạy
    ĐÚNG cơ chế cheapest-cạnh-tranh-công-bằng như day_route_cheapest_insertion() nguyên
    bản (không ưu tiên gì thêm nữa từ bước 2 trở đi). Giữ lại kết quả START có completion
    cao nhất; nếu candidate được ép không thể chèn được (vd. window đã hết hạn ngay từ đầu
    -- hiếm nhưng về lý thuyết có thể), coi lượt start đó là bất khả thi và bỏ qua, không
    tính vào so sánh. Hoà completion -> ưu tiên return_time thấp hơn (route "rẻ" hơn).

    CHI PHÍ: với n candidate trong nhóm last-chance, hàm này chạy Cheapest Insertion đầy
    đủ N LẦN (một lần cho mỗi điểm khởi đầu bị ép) thay vì 1 lần -- tức chậm hơn ~N lần so
    với bản gốc CHỈ CHO RIÊNG bước xây route last-chance. Nhóm last-chance mỗi ngày trên bộ
    dữ liệu này dao động ~10-22 người (nhỏ hơn NHIỀU so với 300 khách tổng), nên chi phí
    tuyệt đối vẫn nhỏ (đo thực tế: dưới 0.4s/ngày ngay cả với nhóm 22 người, so với ~9s
    cho toàn bộ pipeline 7 ngày). Nếu về sau nhóm last-chance có thể phình to hơn nhiều
    (vài trăm người/ngày), nên cân nhắc giới hạn số điểm khởi đầu thử (vd. chỉ thử N
    candidate có local_insertion_cost thấp nhất ở bước đầu) thay vì thử toàn bộ như hiện tại.
    """
    if not candidates:
        return day_route_cheapest_insertion(candidates, depot, all_points, day)

    best_route: Optional[DayRoute] = None
    best_unserved: Optional[List[Customer]] = None

    for forced in candidates:
        remaining = {c.id: c for c in candidates}
        stops: List[Stop] = []
        return_time = 0.0

        # Bước ép: thử chèn `forced` vào route trống (chỉ có pos=0 khả thi lúc này).
        # Nếu bất khả thi (vd. hết window ngay từ đầu), bỏ qua lượt start này hoàn toàn --
        # KHÔNG âm thầm rơi về chạy không-ép, để tránh đếm trùng với lượt start khác.
        res = try_insert_at_position(stops, depot, all_points, forced, day, 0)
        if res is None:
            continue
        _new_stop, return_time, stops, _local_cost = res
        del remaining[forced.id]

        # Từ bước 2 trở đi: ĐÚNG cơ chế cheapest-cạnh-tranh-công-bằng của
        # day_route_cheapest_insertion() gốc, không ưu tiên gì thêm.
        while remaining:
            best_choice = None
            for cust in remaining.values():
                for pos in range(len(stops) + 1):
                    r2 = try_insert_at_position(stops, depot, all_points, cust, day, pos)
                    if r2 is None:
                        continue
                    _new_stop2, new_return_time, new_full_stops, local_cost = r2
                    if best_choice is None or local_cost < best_choice[0]:
                        best_choice = (local_cost, cust.id, new_return_time, new_full_stops)
            if best_choice is None:
                break
            _, chosen_id, return_time, stops = best_choice
            del remaining[chosen_id]

        candidate_route = DayRoute(day=day, stops=stops, return_time=return_time)
        candidate_unserved = list(remaining.values())

        if best_route is None:
            best_route, best_unserved = candidate_route, candidate_unserved
            continue

        # So sánh: completion cao hơn thắng; hoà completion -> return_time thấp hơn thắng
        # (đúng thứ tự ưu tiên completion > distance/thời gian như metrics.py đã định nghĩa).
        cur_n = len(candidate_route.stops)
        best_n = len(best_route.stops)
        if cur_n > best_n or (cur_n == best_n and candidate_route.return_time < best_route.return_time - 1e-9):
            best_route, best_unserved = candidate_route, candidate_unserved

    if best_route is None:
        # Không có candidate nào thậm chí chèn được ở bước ép (route trống mà vẫn fail) --
        # rơi về bản gốc để không bao giờ trả về None (giữ đúng contract của hàm).
        return day_route_cheapest_insertion(candidates, depot, all_points, day)

    return best_route, best_unserved


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


def weekly_scheduler_with_local_search(
    depot: Customer,
    customers: Dict[str, Customer],
    max_orders_per_day: Optional[int] = None,
) -> WeeklyResult:
    """
    Y HỆT weekly_scheduler(), nhưng xây route mỗi ngày qua HAI GIAI ĐOẠN thay vì một,
    cộng thêm 2-opt/Or-opt -- và đây là điểm khác biệt CĂN BẢN so với các bản trước
    (bản cũ trộn chung mọi candidate rồi mới "chèn bù" người bị bỏ lại SAU KHI route
    đã định hình; bản này ĐẢO NGƯỢC thứ tự: giữ chỗ cho người khó trước, rồi mới lấp
    người còn linh hoạt vào phần dư).

    ĐỘNG LỰC (xem BUGFIX_NOTES.md để có trace chi tiết từng ca cụ thể): với Cheapest
    Insertion thuần tuý, khi 2 khách có chi phí chèn GẦN BẰNG NHAU tại một bước (vd.
    18.20 vs 18.35 -- chêh chưa tới 1%), thuật toán luôn chọn người rẻ hơn TRƯỚC, đẩy
    người thua cuộc sang bước sau. Với khách còn NHIỀU ngày khác trong tuần, bị đẩy lùi
    một bước không sao -- ngày mai vẫn còn cơ hội. Nhưng với khách mà HÔM NAY LÀ NGÀY
    CUỐI CÙNG họ còn window trong cả tuần ("last-chance"), bị đẩy lùi dù chỉ 1 bước là
    fail vĩnh viễn, vì route sau đó tiếp tục phát triển sang khu vực khác trên bản đồ,
    khoá luôn khả năng quay lại chèn họ -- dù lúc thua họ chỉ cách route vài trăm mét.
    Cheapest Insertion không phân biệt được 2 loại "thua" này (thua-còn-cứu-được vs.
    thua-là-mất-luôn) vì nó chỉ nhìn chi phí cục bộ, không nhìn "khách này còn bao
    nhiêu cơ hội trong tuần".

    HAI GIAI ĐOẠN xây route mỗi ngày:

      GIAI ĐOẠN 1 -- "giữ chỗ" cho last-chance candidates: tách riêng các candidate
          hôm nay mà next_available_day(cust, day) trả về None (không còn ngày nào
          khác trong tuần), xây MỘT route Cheapest Insertion CHỈ với nhóm này trước
          tiên. Vì route lúc này còn trống, họ được cạnh tranh vị trí công bằng với
          NHAU (ai rẻ hơn thắng, vẫn đúng tinh thần Cheapest Insertion), thay vì phải
          cạnh tranh với toàn bộ candidate bình thường của ngày và luôn thua vì bị xét
          sau cùng như cơ chế "chèn bù" cũ.

      GIAI ĐOẠN 2 -- lấp candidate bình thường (còn ngày khác trong tuần) vào phần
          route còn lại, theo đúng EDF + Cheapest Insertion như thuật toán chính. Nhóm
          này "chịu thiệt" khi bị từ chối, vì họ luôn còn ít nhất 1 ngày dự phòng --
          rolling horizon sẽ tự động xét lại họ vào ngày kế tiếp có window.

      GIAI ĐOẠN 3 -- improve_route() (2-opt + Or-opt, local_search.py): CHỈ đổi thứ tự
          các khách đã có trong route, KHÔNG thêm/bớt ai. Cost function tối ưu là
          return_time (giống hệt try_insert_at_position() của Cheapest Insertion), để
          nhất quán thước đo với thuật toán chính.

    LƯU Ý QUAN TRỌNG: giai đoạn 1 chỉ ưu tiên last-chance-CỦA-HÔM-NAY; nó không đảm
    bảo tối ưu toàn cục cho những khách sắp thành last-chance vào 1-2 ngày tới. Trên
    bộ dữ liệu TMH2026 Bảng B, nhiều ngày cuối tuần (5, 6, 7) dồn số lượng last-chance
    lớn (tới 15 khách/ngày), nên ngay trong nội bộ giai đoạn 1 vẫn có khách thua nhau
    (xem BUGFIX_NOTES.md, ca C095/C268 ở ngày 5) -- đây là giới hạn vật lý thật của
    khung giờ hẹp cạnh tranh cao, không phải điểm có thể vá thêm bằng cách đổi thứ tự.

    Toàn bộ xử lý route chạy TRƯỚC khi xoá khách khỏi `pending`, vì cần all_points
    chứa đúng Customer object của mọi điểm trong route (kể cả khách vừa được chèn).
    """
    from main_algorithm.local_search import improve_route  # import trễ (deferred) để tránh circular import:
    # local_search.py cần Stop/DayRoute từ scheduler.py ngay lúc load module, nên
    # scheduler.py không thể import local_search ở đầu file -- chỉ import khi thực sự
    # gọi tới hàm này.

    result = WeeklyResult()
    pending = dict(customers)

    for day in range(1, 8):
        candidates = [c for c in pending.values() if c.has_any_window_on(day)]
        if max_orders_per_day is not None:
            # Giới hạn áp dụng trên TOÀN BỘ candidates hôm nay trước khi tách nhóm,
            # để giữ đúng ngữ nghĩa "chỉ xét N candidate đầu tiên" như bản gốc.
            candidates.sort(key=lambda c: earliest_window_end_in_week(c, day))
            candidates = candidates[:max_orders_per_day]

        all_points = {depot.id: depot, **pending}

        # --- GIAI ĐOẠN 1: giữ chỗ cho last-chance candidates của hôm nay ---
        last_chance = [c for c in candidates if next_available_day(c, day) is None]
        normal_candidates = [c for c in candidates if next_available_day(c, day) is not None]
        if len(last_chance) + len(normal_candidates) != len(candidates):
            raise RuntimeError("BUG: tách last-chance vs normal candidates không khớp tổng số")

        # Dùng biến thể multi-start (xem docstring day_route_cheapest_insertion_multistart)
        # thay vì day_route_cheapest_insertion() thuần cho riêng bước này: với nhóm
        # last-chance, "thua ở bước đầu" là thua vĩnh viễn, nên thứ tự duyệt candidate
        # (vốn chỉ phụ thuộc thứ tự đọc CSV, không mang ý nghĩa gì) có thể làm mất người
        # một cách không cần thiết dù bài toán vẫn còn đủ "chỗ" cho họ với thứ tự khác.
        # Giai đoạn 2 và baselines.py KHÔNG đổi -- vẫn dùng day_route_cheapest_insertion()
        # gốc, vì nhóm normal_candidates còn ngày dự phòng (thua hôm nay không mất hẳn) nên
        # không cần trả giá thêm thời gian chạy multi-start cho họ.
        route, unserved_last_chance = day_route_cheapest_insertion_multistart(
            last_chance, depot, all_points, day
        )

        # --- GIAI ĐOẠN 2: lấp candidate còn cơ hội tương lai vào phần route còn lại,
        # theo đúng EDF + greedy-cheapest-first như thuật toán chính (không đổi triết
        # lý xếp hạng, chỉ đổi THỜI ĐIỂM họ được xét so với last-chance). ---
        normal_candidates.sort(key=lambda c: earliest_window_end_in_week(c, day))
        remaining_normal = {c.id: c for c in normal_candidates}
        still_unserved_normal: List[Customer] = []
        while remaining_normal:
            best_choice = None  # (local_cost, cust_id, new_stops, new_return_time)
            for cust in remaining_normal.values():
                for pos in range(len(route.stops) + 1):
                    res = try_insert_at_position(route.stops, depot, all_points, cust, day, pos)
                    if res is None:
                        continue
                    _new_stop, new_return_time, new_full_stops, local_cost = res
                    if best_choice is None or local_cost < best_choice[0]:
                        best_choice = (local_cost, cust.id, new_full_stops, new_return_time)
            if best_choice is None:
                break  # không còn ai trong nhóm normal chèn được nữa hôm nay
            _, chosen_id, new_full_stops, new_return_time = best_choice
            route = DayRoute(day=day, stops=new_full_stops, return_time=new_return_time)
            del remaining_normal[chosen_id]
        still_unserved_normal = list(remaining_normal.values())

        # --- GIAI ĐOẠN 3: 2-opt + Or-opt, dọn lại thứ tự route trong ngày ---
        route = improve_route(route, depot, all_points, day)

        result.routes[day] = route

        served_ids = set(route.served_ids())
        for cid in served_ids:
            result.delivered_day_of[cid] = day
            del pending[cid]

        # Khách KHÔNG được chèn hôm nay (cả last-chance lẫn normal) ở lại `pending`.
        # Với normal candidates, rolling horizon sẽ tự xét lại họ vào ngày kế tiếp có
        # window (giống bản gốc). Với last-chance candidates không chèn được
        # (unserved_last_chance), hôm nay ĐÃ LÀ ngày cuối cùng của họ trong tuần --
        # họ sẽ rơi vào result.unfulfilled ở cuối vòng lặp, không có ngày nào để thử
        # lại nữa (next_available_day trả về None cho chính họ).

    result.unfulfilled = list(pending.keys())
    return result


def benchmark_average_runtime(
    depot: Customer,
    customers: Dict[str, Customer],
    n_runs: int = 10,
    use_local_search: bool = True,
    warmup: int = 1,
) -> Dict[str, float]:
    """
    Đo thời gian chạy TRUNG BÌNH của pipeline lập lịch qua nhiều lần lặp, thay vì chỉ
    một lần chạy đơn lẻ như khối `if __name__ == "__main__":` cũ. Một lần chạy đơn lẻ
    dễ bị nhiễu bởi các yếu tố tức thời của máy (cache OS, GC, các tiến trình nền khác
    đang chiếm CPU), nên số liệu trung bình + độ lệch chuẩn qua nhiều lần phản ánh đúng
    hơn hiệu năng thực của thuật toán -- đúng tinh thần "thời gian tham chiếu" mà mục
    5.1 của report đã lưu ý là "không phải phép đo hiệu năng phần cứng chuẩn hoá".

    Tham số:
      depot, customers: dữ liệu đầu vào, dùng lại y hệt cho mọi lần chạy (không load lại
        file mỗi lần, để tách riêng chi phí I/O ra khỏi thời gian đo thuật toán).
      n_runs: số lần lặp lấy để tính trung bình (không tính các lần warmup).
      use_local_search: True -> đo weekly_scheduler_with_local_search() (thuật toán đầy
        đủ, có 2-opt/Or-opt); False -> đo weekly_scheduler() (bản gốc, không local search).
      warmup: số lần chạy "khởi động" bỏ đi trước khi bắt đầu đo thật, nhằm loại bỏ hiệu
        ứng lần chạy đầu tiên thường chậm hơn bất thường (import module lười, cache CPU
        chưa "nóng", v.v.) làm lệch số liệu trung bình.

    Trả về dict gồm:
      "mean": thời gian chạy trung bình (giây)
      "std": độ lệch chuẩn (giây) -- đo mức ổn định giữa các lần chạy
      "min", "max": thời gian nhanh nhất / chậm nhất trong n_runs lần
      "n_runs": số lần lặp thực sự đã tính vào trung bình (không gồm warmup)
      "all_times": danh sách thời gian từng lần chạy (giây), để vẽ biểu đồ/kiểm tra thêm
        nếu cần, không bắt buộc phải dùng.

    LƯU Ý: vì weekly_scheduler()/weekly_scheduler_with_local_search() có tính DETERMINISTIC
    (không dùng số ngẫu nhiên -- xem BUGFIX_NOTES.md), kết quả lịch trình (completion rate,
    quãng đường...) sẽ GIỐNG HỆT NHAU qua mọi lần lặp; chỉ có runtime là dao động do các yếu
    tố phần cứng/hệ điều hành bên ngoài thuật toán. Hàm này KHÔNG kiểm tra lại tính đúng đắn
    của kết quả (đã có verify.py cho việc đó) -- chỉ tập trung đo thời gian.
    """
    import time
    import math

    algorithm_fn = weekly_scheduler_with_local_search if use_local_search else weekly_scheduler

    # Warmup: chạy trước vài lần, không tính vào kết quả đo.
    for _ in range(warmup):
        algorithm_fn(depot=depot, customers=dict(customers))

    all_times: List[float] = []
    for _ in range(n_runs):
        # dict(customers) để mỗi lần chạy nhận một bản sao mới của mapping id -> Customer,
        # tránh trường hợp một lần chạy nào đó vô tình sửa đổi customers gốc rồi ảnh hưởng
        # tới các lần chạy sau (dù hiện tại các hàm scheduler không mutate customers gốc,
        # việc copy vẫn giữ benchmark an toàn nếu code thay đổi về sau).
        start = time.perf_counter()
        algorithm_fn(depot=depot, customers=dict(customers))
        elapsed = time.perf_counter() - start
        all_times.append(elapsed)

    mean_time = sum(all_times) / len(all_times)
    variance = sum((t - mean_time) ** 2 for t in all_times) / len(all_times)
    std_time = math.sqrt(variance)

    return {
        "mean": mean_time,
        "std": std_time,
        "min": min(all_times),
        "max": max(all_times),
        "n_runs": len(all_times),
        "all_times": all_times,
    }


def _print_benchmark_result(stats: Dict[str, float]) -> None:
    """In kết quả benchmark_average_runtime() ra console theo định dạng dễ đọc."""
    print(f"Số lần chạy đo:       {stats['n_runs']}")
    print(f"Runtime trung bình:   {stats['mean']:.4f} giây")
    print(f"Độ lệch chuẩn:        {stats['std']:.4f} giây")
    print(f"Nhanh nhất / Chậm nhất: {stats['min']:.4f}s / {stats['max']:.4f}s")


if __name__ == "__main__":
    from main_algorithm.data_model import load_data

    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")

    # Chạy 1 lần để in kết quả lịch trình chi tiết (giữ nguyên hành vi cũ của script).
    res = weekly_scheduler_with_local_search(depot, customers)
    total_served = sum(len(r.served_ids()) for r in res.routes.values())
    print("Tổng số khách:", len(customers))
    print("Đã giao được:", total_served)
    print("Không hoàn thành:", len(res.unfulfilled))
    for day, route in res.routes.items():
        print(f"Ngày {day}: {len(route.stops)} điểm dừng, về kho lúc phút {route.return_time:.1f} "
              f"({route.return_time/60:.2f}h)")

    # Đo runtime TRUNG BÌNH qua nhiều lần lặp (thay vì chỉ 1 lần chạy đơn lẻ như trước).
    print("\n--- Benchmark runtime trung bình ---")
    stats = benchmark_average_runtime(depot, customers, n_runs=10, warmup=1)
    _print_benchmark_result(stats)