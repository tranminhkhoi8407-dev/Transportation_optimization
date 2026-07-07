"""
exporter.py
-----------
Mô-đun hỗ trợ xuất kết quả lộ trình (WeeklyResult) ra tệp CSV chi tiết.
Hỗ trợ bóc tách từng điểm dừng, bao gồm cả các thông số tọa độ, thời gian phục vụ,
khung cửa sổ thời gian và tính toán quãng đường tích lũy (distance_moved).
"""

import pandas as pd
import math
from typing import Dict
from data_model import Customer, euclidean
from scheduler import WeeklyResult

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


if __name__ == "__main__":
    # Script test nhanh
    from data_model import load_data
    from scheduler import weekly_scheduler
    
    # Khởi tạo dữ liệu
    depot, customers = load_data("Data/locations.csv", "Data/time_windows.csv")
    
    # Chạy thuật toán chính để lấy WeeklyResult
    result = weekly_scheduler(depot, customers)
    
    # Xuất file CSV
    export_weekly_result_to_csv(depot, customers, result, "weekly_routing_details.csv")