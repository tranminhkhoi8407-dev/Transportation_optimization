"""
exporter.py
-----------
Mô-đun hỗ trợ xuất kết quả lộ trình (WeeklyResult) ra tệp CSV chi tiết.
Hỗ trợ bóc tách từng điểm dừng, bao gồm cả các thông số tọa độ, thời gian phục vụ,
khung cửa sổ thời gian và tính toán quãng đường tích lũy (distance_moved).

Ngoài ra còn hỗ trợ xuất 2 tệp CSV bổ sung, dựa trên kết quả trả về của
plot_weekly_routes_interactive() (weekly_route.py):
  - export_delayed_customers_to_csv(): danh sách khách bị hoãn theo từng ngày,
    kèm ngày dự kiến giao thực tế (expected_day), 0 nếu không giao được cả tuần.
  - export_unfulfilled_customers_to_csv(): danh sách khách chắc chắn không giao
    được trong cả tuần (lọc lại từ file trên, expected_day == 0, bỏ cột expected_day).
"""

import pandas as pd
from typing import Dict, List
from main_algorithm.data_model import Customer, euclidean
from main_algorithm.scheduler import WeeklyResult, weekly_scheduler_with_local_search

def export_weekly_result_to_csv(
    depot: Customer, 
    customers: Dict[str, Customer], 
    result: WeeklyResult, 
    output_filename: str = "detailed_routes_output.csv"
):
    """
    Trích xuất thông tin chi tiết từ WeeklyResult và lưu thành file CSV.
    Dữ liệu được sắp xếp theo: Thứ tự ngày (day_of_week) -> Thứ tự điểm dừng (stops).
    """
    rows = []
    
    # Duyệt qua các ngày từ 1 đến 7 để đảm bảo thứ tự
    for day in range(1, 8):
        route = result.routes.get(day)
        
        # Nếu ngày đó không có lộ trình hoặc không có điểm dừng, bỏ qua
        if not route or not route.stops:
            continue
            
        # 1. Điểm xuất phát: Kho trung tâm (Đầu ngày)
        # Quãng đường ban đầu = 0, thời gian rời kho = 0.0
        cum_distance = 0.0
        prev_point = depot
        
        rows.append({
            "day_of_week": day,
            "cust_id": depot.id,
            "demand_kg": depot.demand,
            "service_time": depot.service_time,
            "x_coor": depot.x,
            "y_coor": depot.y,
            "window_start": None,       # Kho không dùng khung giờ của khách
            "window_end": None,
            "service_start": 0.0,       # Thời điểm rời kho xuất phát
            "service_end": 0.0,
            "distance_moved": round(cum_distance, 4)
        })
        
        # 2. Duyệt qua từng khách hàng được giao trong ngày
        for stop in route.stops:
            cust = customers[stop.cust_id]
            
            # Tính khoảng cách từ điểm trước đó đến khách hàng hiện tại và cộng dồn
            dist = euclidean(prev_point, cust)
            cum_distance += dist
            
            rows.append({
                "day_of_week": day,
                "cust_id": cust.id,
                "demand_kg": cust.demand,
                "service_time": cust.service_time,
                "x_coor": cust.x,
                "y_coor": cust.y,
                "window_start": stop.window_used.start,
                "window_end": stop.window_used.end,
                "service_start": round(stop.service_start, 2),
                "service_end": round(stop.service_end, 2),
                "distance_moved": round(cum_distance, 4)
            })
            
            # Cập nhật điểm trước đó thành điểm hiện tại cho vòng lặp tiếp theo
            prev_point = cust
            
        # 3. Điểm kết thúc: Xe quay trở về kho trung tâm (Cuối ngày)
        dist_to_depot = euclidean(prev_point, depot)
        cum_distance += dist_to_depot
        
        rows.append({
            "day_of_week": day,
            "cust_id": f"{depot.id}_RETURN",  # Đổi tên 1 chút để phân biệt với lúc xuất phát
            "demand_kg": depot.demand,
            "service_time": depot.service_time,
            "x_coor": depot.x,
            "y_coor": depot.y,
            "window_start": None,
            "window_end": None,
            "service_start": round(route.return_time, 2), # Thời gian xe về đến kho
            "service_end": round(route.return_time, 2),
            "distance_moved": round(cum_distance, 4)      # Tổng quãng đường cả ngày
        })

    # Chuyển đổi list dictionary thành Pandas DataFrame
    df = pd.DataFrame(rows)
    
    # Định dạng lại tên cột cho giống với yêu cầu (nếu cần đổi tên mapping)
    # (Hiện tại key của dict đã bám sát yêu cầu của bạn)
    
    # Xuất ra file CSV, index=False để không in cột số thứ tự mặc định của pandas
    df.to_csv(output_filename, index=False, encoding="utf-8-sig")
    print(f"✓ Đã xuất dữ liệu chi tiết lộ trình thành công tại: {output_filename}")


def export_delayed_customers_to_csv(
    customers: Dict[str, Customer],
    delayed_by_day: List[List[Customer]],
    expected_day_list: List[int],
    output_filename: str = "delayed_customers_output.csv",
) -> pd.DataFrame:
    """
    Xuất danh sách khách hàng bị hoãn theo từng ngày ra file CSV.

    `delayed_by_day` và `expected_day_list` lấy trực tiếp từ giá trị trả về của
    plot_weekly_routes_interactive() (weekly_route.py):
        delayed_by_day, definitely_unfulfilled, expected_day_list = \\
            plot_weekly_routes_interactive(depot, customers, result)

    Mỗi dòng trong file là 1 khách hàng bị hoãn vào 1 ngày cụ thể (delayed_by_day[day-1]),
    gồm các cột: day_of_week, cust_id, demand_kg, service_time, x_coor, y_coor,
    expected_day (ngày khách THỰC SỰ được giao sau khi lập lịch, 0 nếu không giao
    được trong cả tuần).

    Lưu ý: `expected_day_list` được sắp theo thứ tự customers.keys(), nên hàm tự
    dựng lại mapping cust_id -> expected_day để tra cứu chính xác cho từng khách,
    không phụ thuộc vào thứ tự trong delayed_by_day.
    """
    expected_day_map = dict(zip(customers.keys(), expected_day_list))

    rows = []
    for day in range(1, 8):
        idx = day - 1
        if idx >= len(delayed_by_day):
            continue
        for cust in delayed_by_day[idx]:
            rows.append({
                "day_of_week": day,
                "cust_id": cust.id,
                "demand_kg": cust.demand,
                "service_time": cust.service_time,
                "x_coor": cust.x,
                "y_coor": cust.y,
                "expected_day": expected_day_map.get(cust.id, 0),
            })

    df = pd.DataFrame(rows)
    df.to_csv(output_filename, index=False, encoding="utf-8-sig")
    print(f"✓ Đã xuất danh sách khách hàng bị hoãn thành công tại: {output_filename}")
    return df


def export_unfulfilled_customers_to_csv(
    delayed_df: pd.DataFrame,
    output_filename: str = "unfulfilled_customers_output.csv",
) -> pd.DataFrame:
    """
    Xuất danh sách khách hàng CHẮC CHẮN không giao được trong cả tuần ra file CSV.

    Đơn giản là lọc lại từ DataFrame đã tạo bởi export_delayed_customers_to_csv()
    (tham số `delayed_df`), chỉ giữ các dòng có expected_day == 0, và bỏ cột
    expected_day (vì cột này luôn = 0 với mọi dòng còn lại, không còn cần thiết).

    Cách dùng:
        delayed_df = export_delayed_customers_to_csv(customers, delayed_by_day,
                                                       expected_day_list,
                                                       "Output/delayed_customers.csv")
        export_unfulfilled_customers_to_csv(delayed_df, "Output/unfulfilled_customers.csv")
    """
    unfulfilled_df = delayed_df[delayed_df["expected_day"] == 0].drop(columns=["expected_day"])
    unfulfilled_df.to_csv(output_filename, index=False, encoding="utf-8-sig")
    print(f"✓ Đã xuất danh sách khách hàng không giao được thành công tại: {output_filename}")
    return unfulfilled_df


if __name__ == "__main__":
    # Script test nhanh
    from main_algorithm.data_model import load_data
    from main_algorithm.scheduler import weekly_scheduler_with_local_search
    from gen_output.weekly_route import plot_weekly_routes_interactive
    
    # Khởi tạo dữ liệu
    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")
    
    # Chạy thuật toán chính để lấy WeeklyResult
    result = weekly_scheduler_with_local_search(depot, customers)
    
    # Xuất file CSV chi tiết lộ trình (như cũ)
    export_weekly_result_to_csv(depot, customers, result, "Output/weekly_routing_details.csv")

    # Vẽ bản đồ tương tác + lấy danh sách khách bị hoãn theo ngày và ngày giao dự kiến
    delayed_by_day, definitely_unfulfilled, expected_day_list = plot_weekly_routes_interactive(
        depot, customers, result, "Output/weekly_routes_map_interactive.html"
    )

    # Xuất file CSV danh sách khách bị hoãn theo từng ngày
    delayed_df = export_delayed_customers_to_csv(
        customers, delayed_by_day, expected_day_list, "Output/delayed_customers.csv"
    )

    # Xuất file CSV danh sách khách chắc chắn không giao được (lọc từ file trên)
    export_unfulfilled_customers_to_csv(delayed_df, "Output/unfulfilled_customers.csv")