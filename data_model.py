"""
data_model.py
-------------
Đọc dữ liệu, xây dựng các cấu trúc cơ bản: Customer, TimeWindow, ma trận khoảng cách,
ma trận thời gian di chuyển. Đơn vị thời gian nội bộ: PHÚT tính từ 00:00 của ngày trong tuần
đang xét (0 = 00:00). Ngày trong tuần: 1=Thứ Hai ... 7 = Chủ Nhật (theo đề bài).
"""

import csv
import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

SPEED_KMH = 50.0          # tốc độ tối đa cho phép, dùng luôn làm tốc độ di chuyển (km/h)
MINUTES_PER_KM = 60.0 / SPEED_KMH   # số phút để đi 1 km


@dataclass
class TimeWindow:
    start: int   # phút trong ngày, 0..1440
    end: int     # phút trong ngày, 0..1440

    def contains(self, t: int) -> bool:
        return self.start <= t <= self.end


@dataclass
class Customer:
    id: str
    name: str
    x: float
    y: float
    demand: float
    service_time: int  # phút
    # windows[day] = list các TimeWindow hợp lệ trong ngày đó (day: 1..7)
    windows: Dict[int, List[TimeWindow]] = field(default_factory=dict)

    def windows_on(self, day: int) -> List[TimeWindow]:
        return self.windows.get(day, [])

    def has_any_window_on(self, day: int) -> bool:
        return len(self.windows_on(day)) > 0


def parse_hhmm(s: str) -> int:
    """Chuyển 'HH:MM' -> số phút kể từ 00:00."""
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def load_data(locations_path: str, time_windows_path: str) -> Tuple[Customer, Dict[str, Customer]]:
    """
    Trả về (depot, customers_dict) trong đó customers_dict không bao gồm depot.
    """
    all_locs: Dict[str, Customer] = {}
    with open(locations_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cust = Customer(
                id=row["location_id"],
                name=row["location_name"],
                x=float(row["x_km"]),
                y=float(row["y_km"]),
                demand=float(row["demand_kg"]),
                service_time=int(float(row["service_time"])),
            )
            all_locs[cust.id] = cust

    with open(time_windows_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cid = row["location_id"]
            day = int(row["day_of_week"])
            tw = TimeWindow(parse_hhmm(row["start_time"]), parse_hhmm(row["end_time"]))
            all_locs[cid].windows.setdefault(day, []).append(tw)

    # sắp xếp mỗi danh sách window theo thời gian bắt đầu để duyệt cho tiện & nhất quán
    for c in all_locs.values():
        for day in c.windows:
            c.windows[day].sort(key=lambda w: w.start)

    depot = all_locs.pop("DEPOT")
    return depot, all_locs


def euclidean(a: Customer, b: Customer) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def travel_time_minutes(a: Customer, b: Customer) -> float:
    """Thời gian di chuyển (phút) giữa 2 điểm, dựa trên khoảng cách Euclid và tốc độ tối đa 50km/h.
    Giả định xe luôn chạy đúng tốc độ tối đa cho phép (kịch bản nhanh nhất & xác định,
    hợp lý cho bài toán lập lịch vì ta cần một ước lượng thời gian di chuyển duy nhất,
    không mô hình hoá tắc đường)."""
    return euclidean(a, b) * MINUTES_PER_KM


def build_distance_matrix(depot: Customer, customers: Dict[str, Customer]):
    """Trả về dict khoảng cách và thời gian di chuyển giữa MỌI cặp điểm (bao gồm depot),
    key là tuple (id1, id2)."""
    all_points = {depot.id: depot, **customers}
    ids = list(all_points.keys())
    dist = {}
    time = {}
    for i in ids:
        for j in ids:
            if i == j:
                dist[(i, j)] = 0.0
                time[(i, j)] = 0.0
            else:
                d = euclidean(all_points[i], all_points[j])
                dist[(i, j)] = d
                time[(i, j)] = d * MINUTES_PER_KM
    return dist, time, all_points


if __name__ == "__main__":
    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")
    print("Depot:", depot)
    print("Số khách hàng:", len(customers))
    c1 = customers["C001"]
    print("C001:", c1)
    print("Travel time DEPOT->C001 (phút):", travel_time_minutes(depot, c1))