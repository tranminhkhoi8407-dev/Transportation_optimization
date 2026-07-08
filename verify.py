"""
verify.py
---------
Kiểm tra độc lập tính hợp lệ (feasibility) của một WeeklyResult:
  - Mỗi Stop: service_start phải nằm trong window_used (start <= service_start <= end).
  - service_start >= arrival (không "dịch chuyển tức thời", có chờ nếu đến sớm).
  - arrival của điểm sau = departure của điểm trước + travel_time đúng khoảng cách Euclid.
  - return_time <= 1440 (về kho trước nửa đêm) mỗi ngày.
  - Không giao trùng 1 khách 2 lần trong cả tuần.
  - Mọi khách trong unfulfilled thực sự KHÔNG xuất hiện ở bất kỳ route nào.
Nếu có bất kỳ vi phạm nào, in ra chi tiết lỗi.
"""

from data_model import load_data, travel_time_minutes
from scheduler import weekly_scheduler_with_local_search, DAY_END_MINUTE

EPS = 1e-6


def verify(depot, customers, result):
    errors = []
    all_points = {depot.id: depot, **customers}
    served_overall = set()

    for day, route in result.routes.items():
        prev_point = depot
        prev_departure = 0.0
        for stop in route.stops:
            cust = all_points[stop.cust_id]

            # 1. Kiểm tra arrival tính đúng
            expected_arrival = prev_departure + travel_time_minutes(prev_point, cust)
            if abs(expected_arrival - stop.arrival) > 1e-3:
                errors.append(
                    f"[Ngày {day}] {stop.cust_id}: arrival sai lệch. "
                    f"Mong đợi {expected_arrival:.3f}, thực tế {stop.arrival:.3f}"
                )

            # 2. service_start >= arrival
            if stop.service_start < stop.arrival - EPS:
                errors.append(
                    f"[Ngày {day}] {stop.cust_id}: service_start ({stop.service_start:.2f}) "
                    f"< arrival ({stop.arrival:.2f})"
                )

            # 3. service_start nằm trong window_used
            w = stop.window_used
            if not (w.start - EPS <= stop.service_start <= w.end + EPS):
                errors.append(
                    f"[Ngày {day}] {stop.cust_id}: service_start ({stop.service_start:.2f}) "
                    f"KHÔNG nằm trong window [{w.start}, {w.end}]"
                )

            # 4. window_used phải thực sự thuộc windows_on(day) của khách
            actual_windows = cust.windows_on(day)
            if w not in actual_windows:
                errors.append(
                    f"[Ngày {day}] {stop.cust_id}: window_used {w} không có trong "
                    f"danh sách windows hợp lệ ngày {day}: {actual_windows}"
                )

            # 5. service_end = service_start + service_time
            expected_end = stop.service_start + cust.service_time
            if abs(expected_end - stop.service_end) > 1e-3:
                errors.append(
                    f"[Ngày {day}] {stop.cust_id}: service_end sai. "
                    f"Mong đợi {expected_end:.2f}, thực tế {stop.service_end:.2f}"
                )

            # 6. Không giao trùng khách trong tuần
            if stop.cust_id in served_overall:
                errors.append(f"[Ngày {day}] {stop.cust_id}: GIAO TRÙNG (đã giao ở ngày khác)")
            served_overall.add(stop.cust_id)

            prev_point = cust
            prev_departure = stop.service_end

        # 7. Kiểm tra return_time
        expected_return = prev_departure + travel_time_minutes(prev_point, depot)
        if abs(expected_return - route.return_time) > 1e-3:
            errors.append(
                f"[Ngày {day}] return_time sai. Mong đợi {expected_return:.3f}, "
                f"thực tế {route.return_time:.3f}"
            )
        if route.return_time > DAY_END_MINUTE + EPS:
            errors.append(
                f"[Ngày {day}] VI PHẠM: về kho lúc {route.return_time:.2f} phút "
                f"(> {DAY_END_MINUTE} = 24:00)"
            )

    # 8. Kiểm tra unfulfilled không trùng với served, và served + unfulfilled = tất cả khách
    all_ids = set(customers.keys())
    unfulfilled_set = set(result.unfulfilled)
    if served_overall & unfulfilled_set:
        errors.append(f"Có khách vừa 'đã giao' vừa 'unfulfilled': {served_overall & unfulfilled_set}")
    if served_overall | unfulfilled_set != all_ids:
        missing = all_ids - (served_overall | unfulfilled_set)
        extra = (served_overall | unfulfilled_set) - all_ids
        errors.append(f"Thiếu/thừa khách so với danh sách gốc. Thiếu: {missing}, Thừa: {extra}")

    # 9. Với mỗi unfulfilled, double-check: có đúng là họ hết cơ hội trong tuần không?
    #    (Không bắt buộc đúng về mặt thuật toán tối ưu, nhưng để hiểu NGUYÊN NHÂN fail)
    reasons = {}
    for cid in result.unfulfilled:
        cust = customers[cid]
        days_with_window = [d for d in range(1, 8) if cust.has_any_window_on(d)]
        reasons[cid] = days_with_window

    return errors, reasons


if __name__ == "__main__":
    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")
    result = weekly_scheduler_with_local_search(depot, customers)
    errors, reasons = verify(depot, customers, result)

    if errors:
        print(f"!!! TÌM THẤY {len(errors)} LỖI !!!")
        for e in errors[:30]:
            print(" -", e)
    else:
        print("✓ TOÀN BỘ LỜI GIẢI HỢP LỆ — không vi phạm ràng buộc nào.")

    print(f"\nSố đơn không hoàn thành: {len(result.unfulfilled)}")
    print("Chi tiết các ngày trong tuần mà mỗi đơn KHÔNG-hoàn-thành từng có window (để hiểu vì sao fail):")
    for cid, days in reasons.items():
        cust = customers[cid]
        print(f"  {cid} ({cust.name}): có window vào các ngày {days}, demand={cust.demand}kg")
        for d in days:
            for w in cust.windows_on(d):
                print(f"      -> ngày {d}: [{w.start//60:02d}:{w.start%60:02d} - {w.end//60:02d}:{w.end%60:02d}]")