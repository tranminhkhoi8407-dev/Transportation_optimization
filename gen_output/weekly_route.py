import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser
import os
from typing import List, Tuple

from main_algorithm.scheduler import next_available_day


def plot_weekly_routes_interactive(depot, customers, result, output_filename="weekly_routes_map_interactive.html") -> Tuple[List[List], List, List[int]]:
    """
    Trực quan hóa chu trình giao hàng 2D tương tác bằng Plotly.
    Hỗ trợ di chuột (hover) để xem ID, toạ độ, và thời gian phục vụ của từng điểm.

    PHÂN LOẠI MÀU cho mỗi khách có time window vào ngày `day` đang xét:

      - XÁM (pending)     : chưa được giao hôm nay, nhưng SẼ được giao vào một ngày
                             sau đó trong tuần (không rớt đơn cả tuần).
      - XANH (served)     : được giao thành công hôm nay, và hôm nay KHÔNG PHẢI là
                             ngày cuối cùng khách còn window trong tuần.
      - VÀNG/CAM (last-chance): hôm nay LÀ ngày cuối cùng khách còn window trong tuần
                             (next_available_day() trả về None). Gồm CẢ 2 trường hợp:
                               (a) được giao thành công hôm nay -> hover "Lần cuối được giao"
                               (b) KHÔNG được giao được dù đã ưu tiên xếp lịch hôm nay ->
                                   hover "Ngày cuối cùng - Không xếp được lịch"
                             (b) là điểm khác biệt so với bản cũ: trước đây nhóm này bị
                             vẽ chung màu ĐỎ với nhóm rớt-đơn; nay được tách riêng màu
                             vàng để thể hiện rằng họ ĐÃ được ưu tiên xếp lịch ở ngày
                             cuối cùng (đúng logic last-chance trong scheduler) nhưng bài
                             toán vẫn không đủ chỗ chèn họ.
      - ĐỎ (unfulfilled, CHƯA tới ngày cuối): khách rớt đơn cả tuần (có trong
                             result.unfulfilled), nhưng hôm nay chưa phải ngày cuối cùng
                             họ còn window (ngày cuối cùng của họ sẽ được tô VÀNG ở trên).

    Trả về:
        (delayed_by_day, definitely_unfulfilled, expected_day_list)

        - delayed_by_day: List[List[Customer]], độ dài 7 (index 0 = Ngày 1, ...,
          index 6 = Ngày 7). delayed_by_day[i] = danh sách khách có time window vào
          ngày (i+1) nhưng KHÔNG được giao trong chính ngày đó -- tức là hợp của nhóm
          XÁM + ĐỎ + VÀNG-thất-bại của ngày đó. Khách "xám" vẫn có thể được giao ở một
          ngày khác sau này; khách "đỏ" / "vàng-thất-bại" thì chắc chắn (hoặc đã) rớt
          đơn cả tuần.
        - definitely_unfulfilled: List[Customer], danh sách khách CHẮC CHẮN không giao
          được trong suốt cả tuần (tương ứng 1-1 với result.unfulfilled).
        - expected_day_list: List[int], CÙNG THỨ TỰ với customers.keys() (tức
          expected_day_list[i] tương ứng với khách hàng thứ i khi duyệt customers.keys()).
          Giá trị là ngày mà khách đó THỰC SỰ được giao (result.delivered_day_of), hoặc 0
          nếu khách không giao được trong cả tuần (nằm trong result.unfulfilled).
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
    show_legend = {
        'depot': True, 'pending': True, 'served': True, 'route': True,
        'unfulfilled': True, 'last_chance': True,
    }
    unfulfilled_cids = set(result.unfulfilled)

    # Danh sách trả về: khách bị hoãn theo từng ngày
    delayed_by_day: List[List] = []

    for day in range(1, 8):
        # Tính toán vị trí của subplot trên lưới 2x4
        row = 1 if day <= 4 else 2
        col = day if day <= 4 else day - 4

        route = result.routes.get(day)
        served_ids = set(route.served_ids()) if route and route.stops else set()

        # Tập ứng viên hôm nay: còn pending TRƯỚC ngày hôm nay và có window hôm nay
        today_candidate_ids = {cid for cid in pending_cids if customers[cid].has_any_window_on(day)}

        # --- Phân loại nhóm KHÔNG được giao hôm nay ---
        not_served_ids = today_candidate_ids - served_ids
        last_chance_failed_ids = {
            cid for cid in not_served_ids
            if next_available_day(customers[cid], day) is None
        }
        still_not_served_ids = not_served_ids - last_chance_failed_ids
        unfulfilled_today_ids = still_not_served_ids & unfulfilled_cids   # ĐỎ: rớt đơn, chưa tới ngày cuối
        pending_today_ids = still_not_served_ids - unfulfilled_cids       # XÁM: sẽ giao vào ngày sau

        # Danh sách bị hoãn hôm nay = xám + đỏ + vàng-thất-bại
        delayed_today = [customers[cid] for cid in not_served_ids]
        delayed_by_day.append(delayed_today)

        daily_candidates = [customers[cid] for cid in pending_today_ids]
        daily_unfulfilled = [customers[cid] for cid in unfulfilled_today_ids]
        daily_last_chance_failed = [customers[cid] for cid in last_chance_failed_ids]

        # --- A. Vẽ khách hàng chờ giao vào ngày sau (Nền xám) ---
        if daily_candidates:
            cand_x = [c.x for c in daily_candidates]
            cand_y = [c.y for c in daily_candidates]
            # Tạo nhãn hiển thị khi hover chuột
            cand_hover = [f"<b>Khách chờ giao</b><br>ID: {c.id}<br>Time window: {c.windows_on(day)}<br>Tọa độ: ({c.x:.2f}, {c.y:.2f})" for c in daily_candidates]

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

        # --- C. Vẽ khách rớt đơn cả tuần nhưng CHƯA tới ngày cuối cùng của họ (Đỏ) ---
        if daily_unfulfilled:
            unf_x = [c.x for c in daily_unfulfilled]
            unf_y = [c.y for c in daily_unfulfilled]
            unf_hover = [f"<b>Sẽ rớt đơn cả tuần</b><br>ID: {c.id}<br>Time window: {c.windows_on(day)}<br>Tọa độ: ({c.x:.2f}, {c.y:.2f})" for c in daily_unfulfilled]

            fig.add_trace(go.Scatter(
                x=unf_x, y=unf_y, mode='markers',
                marker=dict(color='red', size=8, line=dict(color='darkred', width=1)),
                name='Khách rớt đơn cả tuần',
                hoverinfo='text', hovertext=unf_hover,
                showlegend=show_legend['unfulfilled']
            ), row=row, col=col)
            show_legend['unfulfilled'] = False

        # --- D. Vẽ khách last-chance nhưng KHÔNG xếp được lịch hôm nay (Vàng/Cam) ---
        if daily_last_chance_failed:
            lcf_x = [c.x for c in daily_last_chance_failed]
            lcf_y = [c.y for c in daily_last_chance_failed]
            lcf_hover = [f"<b>ID: {c.id}</b><br>Time window: {c.windows_on(day)}<br><b>Ngày cuối cùng - Không xếp được lịch</b><br>Tọa độ: ({c.x:.2f}, {c.y:.2f})" for c in daily_last_chance_failed]

            fig.add_trace(go.Scatter(
                x=lcf_x, y=lcf_y, mode='markers',
                marker=dict(color='orange', size=8, line=dict(color='darkorange', width=1)),
                name='Last-chance (ưu tiên ngày cuối)',
                hoverinfo='text', hovertext=lcf_hover,
                showlegend=show_legend['last_chance']
            ), row=row, col=col)
            show_legend['last_chance'] = False

        # --- E. Vẽ Lộ trình nếu có đơn ---
        if route and route.stops:
            served_ids_list = route.served_ids()

            route_x = [depot.x] + [customers[cid].x for cid in served_ids_list] + [depot.x]
            route_y = [depot.y] + [customers[cid].y for cid in served_ids_list] + [depot.y]

            # 1. Vẽ các điểm khách hàng được giao (Màu xanh dương), tách riêng last-chance
            served_last_chance_ids = {
                cid for cid in served_ids_list
                if next_available_day(customers[cid], day) is None
            }
            served_hover = []
            last_hover = []
            for stop in route.stops:
                c = customers[stop.cust_id]
                served_hover.append(f"<b>ID: {c.id}</b><br>Time window: {c.windows_on(day)}<br>Đến nơi: {stop.arrival}<br>Giao xong: {stop.service_end}")
                if stop.cust_id in served_last_chance_ids:
                    last_hover.append(f"<b>ID: {c.id}</b><br>Time window: {c.windows_on(day)}<br>Đến nơi: {stop.arrival}<br>Giao xong: {stop.service_end}<br><b>Lần cuối được giao</b>")

            fig.add_trace(go.Scatter(
                x=route_x[1:-1], y=route_y[1:-1], mode='markers',
                marker=dict(color='blue', size=8),
                name='Khách được giao trong ngày',
                hoverinfo='text', hovertext=served_hover,
                showlegend=show_legend['served']
            ), row=row, col=col)
            show_legend['served'] = False

            if served_last_chance_ids:
                last_x = [customers[cid].x for cid in served_ids_list if cid in served_last_chance_ids]
                last_y = [customers[cid].y for cid in served_ids_list if cid in served_last_chance_ids]

                fig.add_trace(go.Scatter(
                    x=last_x, y=last_y, mode='markers',
                    marker=dict(color='orange', size=8, line=dict(color='darkorange', width=1)),
                    name='Last-chance (ưu tiên ngày cuối)',
                    hoverinfo='text', hovertext=last_hover,
                    showlegend=show_legend['last_chance']
                ), row=row, col=col)
                show_legend['last_chance'] = False

            # 2. Vẽ đường nối Lộ trình
            fig.add_trace(go.Scatter(
                x=route_x, y=route_y, mode='lines',
                line=dict(color='royalblue', width=1.5),
                name='Lộ trình di chuyển',
                hoverinfo='none',  # Tắt hover ở line cho đỡ rối
                showlegend=show_legend['route']
            ), row=row, col=col)
            show_legend['route'] = False

            # 3. Vẽ mũi tên định hướng (Sử dụng Annotations của Plotly)
            xaxis_name = f'x{day}' if day > 1 else 'x'
            yaxis_name = f'y{day}' if day > 1 else 'y'

            for i in range(len(route_x) - 1):
                dx = route_x[i+1] - route_x[i]
                dy = route_y[i+1] - route_y[i]

                fig.add_annotation(
                    x=route_x[i] + dx * 0.55, y=route_y[i] + dy * 0.55,  # Đầu mũi tên
                    ax=route_x[i] + dx * 0.45, ay=route_y[i] + dy * 0.45,  # Đuôi mũi tên
                    xref=xaxis_name, yref=yaxis_name, axref=xaxis_name, ayref=yaxis_name,
                    showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="navy", opacity=0.7
                )

        # --- F. Giữ đúng tỷ lệ Hình học 1:1 (Quan Trọng) ---
        fig.update_yaxes(scaleanchor=f"x{day}" if day > 1 else "x", scaleratio=1, row=row, col=col)

        # Thêm lưới toạ độ mờ
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='WhiteSmoke', row=row, col=col)
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='WhiteSmoke', row=row, col=col)

        # Cập nhật danh sách pending cho các ngày tiếp theo (chỉ bỏ người ĐÃ ĐƯỢC GIAO hôm nay)
        pending_cids -= served_ids

    # --- G. Cấu hình layout tổng thể ---
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

    definitely_unfulfilled = [customers[cid] for cid in result.unfulfilled]

    # expected_day_list: cùng thứ tự với customers.keys() -- ngày khách THỰC SỰ được
    # giao (result.delivered_day_of), hoặc 0 nếu khách nằm trong result.unfulfilled.
    expected_day_list: List[int] = [
        result.delivered_day_of.get(cid, 0) for cid in customers.keys()
    ]

    return delayed_by_day, definitely_unfulfilled, expected_day_list