import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser
import os

def plot_weekly_routes_interactive(depot, customers, result, output_filename="weekly_routes_map_interactive.html"):
    """
    Trực quan hóa chu trình giao hàng 2D tương tác bằng Plotly.
    Hỗ trợ di chuột (hover) để xem ID, toạ độ, và thời gian phục vụ của từng điểm.
    """
    
    # 1. Tính toán trước Tiêu đề (Titles) cho 8 ô subplot (7 ngày + 1 ô trống)
    subplot_titles = []
    temp_pending_cids = set(customers.keys())
    for day in range(1, 8):
        route = result.routes.get(day)
        daily_candidates = [customers[cid] for cid in temp_pending_cids if customers[cid].has_any_window_on(day)]
        
        if route and route.stops:
            total_served = len(route.served_ids())
            hoan = len(daily_candidates) - total_served
            subplot_titles.append(f"Ngày {day} (Đơn: {total_served}, Hoãn: {hoan})")
            temp_pending_cids -= set(route.served_ids())
        else:
            subplot_titles.append(f"Ngày {day} (Không có đơn)")
    subplot_titles.append("")  # Ô thứ 8 trống
    
    # Tạo cấu trúc lưới 2 hàng x 4 cột
    fig = make_subplots(rows=2, cols=4, subplot_titles=subplot_titles, 
                        horizontal_spacing=0.03, vertical_spacing=0.08)
    
    # Khởi tạo lại danh sách chờ thực tế cho vòng lặp vẽ
    pending_cids = set(customers.keys())
    
    # Cờ để legend chỉ hiển thị 1 lần, không bị trùng lặp 7 lần cho 7 ngày
    show_legend = {'depot': True, 'pending': True, 'served': True, 'route': True}
    
    for day in range(1, 8):
        # Tính toán vị trí của subplot trên lưới 2x4
        row = 1 if day <= 4 else 2
        col = day if day <= 4 else day - 4
        
        route = result.routes.get(day)
        daily_candidates = [customers[cid] for cid in pending_cids if customers[cid].has_any_window_on(day)]
        
        # --- A. Vẽ khách hàng chờ giao (Nền xám) ---
        if daily_candidates:
            cand_x = [c.x for c in daily_candidates]
            cand_y = [c.y for c in daily_candidates]
            # Tạo nhãn hiển thị khi hover chuột
            cand_hover = [f"<b>Khách chờ giao</b><br>ID: {c.id}<br>Nhu cầu: {c.demand} kg<br>Tọa độ: ({c.x:.2f}, {c.y:.2f})" for c in daily_candidates]
            
            fig.add_trace(go.Scatter(
                x=cand_x, y=cand_y, mode='markers',
                marker=dict(color='lightgray', size=6, opacity=0.5),
                name='Khách hàng khác',
                hoverinfo='text', hovertext=cand_hover,
                showlegend=show_legend['pending']
            ), row=row, col=col)
            show_legend['pending'] = False
            
        # --- B. Vẽ Kho trung tâm (Vuông Đỏ) ---
        fig.add_trace(go.Scatter(
            x=[depot.x], y=[depot.y], mode='markers',
            marker=dict(color='red', size=12, symbol='square', line=dict(color='black', width=1)),
            name='Kho trung tâm',
            hoverinfo='text', hovertext=f"<b>Kho trung tâm</b><br>Tọa độ: ({depot.x}, {depot.y})",
            showlegend=show_legend['depot']
        ), row=row, col=col)
        show_legend['depot'] = False
        
        # --- C. Vẽ Lộ trình nếu có đơn ---
        if route and route.stops:
            served_ids = route.served_ids()
            
            route_x = [depot.x] + [customers[cid].x for cid in served_ids] + [depot.x]
            route_y = [depot.y] + [customers[cid].y for cid in served_ids] + [depot.y]
            
            # 1. Vẽ các điểm khách hàng được giao (Màu xanh dương)
            served_hover = []
            for stop in route.stops:
                c = customers[stop.cust_id]
                # Format thời gian theo hh:mm cho dễ đọc
                arr_h, arr_m = int(stop.arrival // 60), int(stop.arrival % 60)
                end_h, end_m = int(stop.service_end // 60), int(stop.service_end % 60)
                served_hover.append(f"<b>ID: {c.id}</b><br>Đến nơi: {arr_h:02d}:{arr_m:02d}<br>Giao xong: {end_h:02d}:{end_m:02d}")
                
            fig.add_trace(go.Scatter(
                x=route_x[1:-1], y=route_y[1:-1], mode='markers',
                marker=dict(color='blue', size=8),
                name='Khách được giao trong ngày',
                hoverinfo='text', hovertext=served_hover,
                showlegend=show_legend['served']
            ), row=row, col=col)
            show_legend['served'] = False
            
            # 2. Vẽ đường nối Lộ trình
            fig.add_trace(go.Scatter(
                x=route_x, y=route_y, mode='lines',
                line=dict(color='royalblue', width=1.5),
                name='Lộ trình di chuyển',
                hoverinfo='none', # Tắt hover ở line cho đỡ rối
                showlegend=show_legend['route']
            ), row=row, col=col)
            show_legend['route'] = False
            
            # 3. Vẽ mũi tên định hướng (Sử dụng Annotations của Plotly)
            # Trong subplots, Plotly yêu cầu xác định đúng trục (VD: x1, y1 cho ô 1; x5, y5 cho ô 5)
            xaxis_name = f'x{day}' if day > 1 else 'x'
            yaxis_name = f'y{day}' if day > 1 else 'y'
            
            for i in range(len(route_x) - 1):
                dx = route_x[i+1] - route_x[i]
                dy = route_y[i+1] - route_y[i]
                
                fig.add_annotation(
                    x=route_x[i] + dx * 0.55, y=route_y[i] + dy * 0.55, # Đầu mũi tên
                    ax=route_x[i] + dx * 0.45, ay=route_y[i] + dy * 0.45, # Đuôi mũi tên
                    xref=xaxis_name, yref=yaxis_name, axref=xaxis_name, ayref=yaxis_name,
                    showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="navy", opacity=0.7
                )
            
            # Cập nhật danh sách pending cho các ngày tiếp theo
            pending_cids -= set(served_ids)
            
        # --- D. Giữ đúng tỷ lệ Hình học 1:1 (Quan Trọng) ---
        # Tương đương với ax.set_aspect('equal') trong matplotlib
        fig.update_yaxes(scaleanchor=f"x{day}" if day > 1 else "x", scaleratio=1, row=row, col=col)
        
        # Thêm lưới toạ độ mờ
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='WhiteSmoke', row=row, col=col)
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='WhiteSmoke', row=row, col=col)

    # --- E. Cấu hình layout tổng thể ---
    fig.update_layout(
        title_text="BẢN ĐỒ KHÔNG GIAN CHU TRÌNH GIAO HÀNG TỪNG NGÀY (TƯƠNG TÁC)",
        title_font=dict(size=18, family="DejaVu Sans", color="black"),
        title_x=0.5,
        height=850, width=1700,  # Kích thước rộng tương đương figsize của Matplotlib
        plot_bgcolor='white',
        hovermode='closest',     # Chỉ hiện label của điểm gần chuột nhất
        legend=dict(yanchor="bottom", y=0.05, xanchor="right", x=0.98, bordercolor="lightgray", borderwidth=1)
    )

    # Xuất ra file HTML và tự động mở lên trình duyệt
    fig.write_html(output_filename)
    print(f"✓ Đã xuất bản đồ tương tác thành công tại: {output_filename}")
    webbrowser.open('file://' + os.path.realpath(output_filename))