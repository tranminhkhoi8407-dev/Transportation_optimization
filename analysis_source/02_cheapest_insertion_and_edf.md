# Tài liệu Phân tích Hệ thống - Phần 2: Thuật toán Tối ưu Chính (Cheapest Insertion + EDF)

Tài liệu này tập trung mổ xẻ chi tiết thuật toán lập lịch chính được cài đặt trong tệp `scheduler.py`. Thuật toán này là sự kết hợp tinh tế giữa chiến lược phân loại ưu tiên liên ngày **EDF (Earliest Deadline First)** và kỹ thuật tối ưu hóa hình học cấu trúc tuyến **Cheapest Insertion Heuristic**.

---

## 1. Kết nối Thuật toán với Yêu cầu Đề bài

* **Ràng buộc ca làm việc 24h:** Đề bài yêu cầu xe xuất phát từ kho và phải quay trở lại kho trung tâm trong ngày. Hệ thống mã hóa việc này bằng hằng số `DAY_END_MINUTE = 1440`. Bất kỳ hành trình nào có thời gian xe về kho `return_time > 1440` đều bị coi là bất hợp pháp và bị loại bỏ lập tức. Điều này đáp ứng trực tiếp **Yêu cầu về thời gian vận hành** trong bài toán gốc.
* **Ràng buộc Khung thời gian nhận hàng (Time Windows):** Khách hàng chỉ nhận hàng trong các khoảng thời gian đã đăng ký trước. Hệ thống thực hiện kiểm tra điều kiện nghiêm ngặt: thời điểm xe bắt đầu phục vụ thực tế (`service_start`) phải thỏa mãn nằm trọn trong khung giờ được chọn. Nếu xe đến muộn (`arrival > window.end`), phép chèn bị coi là không khả thi. Điều này đáp ứng chính xác **Ràng buộc cửa sổ thời gian** của đề bài.
* **Quy tắc hoãn giao hàng (Postponement):** Đề bài cho phép hoãn đơn hàng chưa giao sang ngày tiếp theo nếu khách hàng có lịch mở cửa. Vòng lặp rolling horizon tuần tự từ Ngày 1 đến Ngày 7 kết hợp hàng đợi toàn cục `pending` hiện thực hóa hoàn hảo quy tắc này. Đơn hàng thất bại ở Ngày $T$ sẽ tự động quay lại `pending` để xét tiếp ở Ngày $T+1$.

---

## 2. Phân tích Chi tiết Các Hàm Thuật toán Lõi

### 2.1. Hàm `earliest_feasible_service`
* **Mục tiêu:** Tìm kiếm khung giờ mở cửa sớm nhất và hợp lệ của một khách hàng dựa trên thời điểm đầu xe chạm bến thực tế.
* **Tham số đầu vào:**
    * `arrival (float)`: Thời điểm xe chạy đến trước cửa nhà khách hàng (tính bằng phút từ đầu ngày).
    * `windows (List[TimeWindow])`: Danh sách các khung giờ mở cửa của khách hàng trong ngày đó (đã được sắp xếp tăng dần theo `start`).
* **Giá trị trả về:** Cặp tuple `(service_start, window_used)` nếu tìm thấy khung giờ hợp lệ; trả về `None` nếu xe đến muộn hơn tất cả các khung giờ khả dụng.
* **Thuật toán chi tiết:**
    1. Do danh sách `windows` đã được sắp xếp tăng dần theo mốc bắt đầu ở giai đoạn tiền xử lý, thuật toán thực hiện duyệt tuần tự qua từng khung giờ `for w in windows:`.
    2. Kiểm tra điều kiện ngắt biên: nếu thời điểm xe đến `arrival` nhỏ hơn hoặc bằng mốc kết thúc khung giờ `w.end`, điều đó có nghĩa xe vẫn có cơ hội được phục vụ tại khung giờ này (hoặc các khung giờ muộn hơn phía sau).
    3. Tính toán mốc thời gian bắt đầu phục vụ thực tế bằng biểu thức: `service_start = max(arrival, w.start)`. Biểu thức này xử lý mượt mà cả hai trạng thái thực tế:
        * Xe đến sớm (`arrival < w.start`): xe phải tắt máy đứng chờ, giờ phục vụ tính từ lúc mở cửa `w.start`.
        * Xe đến đúng khung (`w.start <= arrival <= w.end`): phục vụ được tiến hành ngay lập tức tại mốc `arrival`.
    4. Trả về kết quả ngay lập tức để đảm bảo tính tham lam (chọn cơ hội sớm nhất). Nếu duyệt hết danh sách mà điều kiện không thỏa mãn, hàm tự động trả về `None`.

### 2.2. Hàm `try_insert_at_position`
* **Mục tiêu:** Đánh giá toán học tính khả thi và tính toán dòng thời gian mới khi cố tình chèn khách hàng `new_cust` vào vị trí chỉ mục `pos` trong lộ trình hiện tại của ngày.
* **Cơ chế hoạt động - Hiện tượng lan truyền độ trễ (Time Ripple Effect):** Khi một khách hàng mới được chèn vào giữa một tuyến đường, hành động này làm phát sinh hai loại chi phí thời gian: thời gian di chuyển vòng qua vị trí khách hàng mới và thời gian dừng phục vụ tại đó. Hệ quả là toàn bộ các điểm dừng cũ nằm phía sau vị trí chèn sẽ bị đẩy lùi mốc thời gian cập bến. Hàm này có nhiệm vụ giả lập dòng thời gian lan truyền này để kiểm tra xem độ trễ đó có làm hỏng ràng buộc cửa sổ thời gian của các điểm phía sau hay không.
* **Tham số đầu vào:**
    * `route_stops (List[Stop])`: Danh sách các điểm dừng hiện có trong ngày.
    * `depot (Customer)`: Đối tượng kho trung tâm.
    * `all_points (Dict[str, Customer])`: Từ điển tra cứu nhanh thông tin tất cả các nút.
    * `new_cust (Customer)`: Đối tượng khách hàng mới đang được thử nghiệm chèn.
    * `day (int)`: Ngày hiện hành.
    * `pos (int)`: Vị trí chỉ mục mong muốn chèn (chạy từ `0` đến `len(route_stops)`).
* **Giá trị trả về:** Tuple gồm `(đối tượng Stop mới, mốc thời gian xe về kho mới, danh sách Stop mới sau khi cập nhật toàn bộ)` nếu phép chèn hoàn toàn hợp lệ. Ngược lại, trả về `None`.
* **Các bước thuật toán và Logic biến số:**
    1.  **Xác định điểm tựa phía trước (Predecessor):** Nếu vị trí chèn ở đầu tuyến (`pos == 0`), xe xuất phát từ kho: điểm phía trước là `depot`, mốc thời gian rời đi là `0.0`. Nếu chèn vào giữa hoặc cuối, lấy thông tin điểm dừng đứng ngay trước: `prev_stop = route_stops[pos - 1]`, mốc rời đi là `prev_departure = prev_stop.service_end`.
    2.  **Tính toán cho điểm chèn mới:** Thời gian xe chạy đến điểm mới: `arrival = prev_departure + travel_time_minutes(prev_point, new_cust)`. Gọi hàm `earliest_feasible_service(arrival, new_cust.windows[day])` để tìm khung giờ và mốc phục vụ hợp lệ. Nếu trả về `None`, phép thử thất bại lập tức. Ngược lại, khởi tạo đối tượng `new_stop` tạm thời với `service_end = service_start + new_cust.service_time`.
    3.  **Vòng lặp lan truyền thời gian (Time Ripple Loop):** Khởi tạo một mảng chứa kết quả mới `new_stops` và thiết lập điểm neo vừa tính xong làm mốc rời đi tiếp theo: `current_departure = new_stop.service_end`. Thuật toán tiến hành duyệt qua toàn bộ danh sách các điểm dừng cũ nằm phía sau vị trí chèn: `for next_stop in route_stops[pos:]:`.
    4.  Tại mỗi điểm dừng phía sau, tính toán mốc cập bến mới do ảnh hưởng bởi độ trễ: `new_arrival = current_departure + travel_time_minutes(current_point, next_cust)`. Tiếp tục gọi hàm `earliest_feasible_service` để kiểm tra xem mốc cập bến mới này có còn kịp giờ đóng cửa của điểm cũ này không. Nếu vượt quá (`res2 is None`), hệ thống ghi nhận một lỗi vi phạm dây chuyền và hủy bỏ toàn bộ phép chèn (`feasible = False`). Nếu đạt yêu cầu, tạo một `Stop` mới đã được cập nhật lại dòng thời gian và đưa vào mảng `new_stops`.
    5.  **Kiểm tra giờ về kho (24h Gate):** Sau khi thoát khỏi vòng lặp lan truyền an toàn, tính toán chặng di chuyển cuối cùng từ vị trí dừng cuối cùng quay trở về kho trung tâm: `return_time = current_departure + travel_time_minutes(current_point, depot)`. Nếu `return_time > DAY_END_MINUTE` (1440 phút), xe bị về muộn sau nửa đêm, phép chèn lập tức bị hủy bỏ.
    6.  **Trả về kết quả:** Nếu vượt qua tất cả các bộ lọc bảo vệ nghiêm ngặt trên, hàm trả về kết quả cấu trúc tuyến đường mới hoàn chỉnh.

### 2.3. Hàm `day_route_cheapest_insertion`
* **Mục tiêu:** Xây dựng lộ trình tối ưu cho một ngày dựa trên chiến lược Tham lam chèn chi phí thấp nhất (Cheapest Insertion Heuristic).
* **Ý nghĩa Thuật toán:** Thay vì xếp hàng khách hàng rồi nối đuôi một cách đơn giản, thuật toán này liên tục tìm cách mở rộng tuyến đường bằng cách tìm xem khách hàng nào khi chèn vào **bất kỳ vị trí nào** trên tuyến đường hiện tại sẽ làm tăng tổng thời gian di chuyển của xe ít nhất.
* **Các bước thuật toán:**
    1. Khởi tạo tuyến đường ngày trống `stops = []`, thời gian xe về kho ban đầu bằng `0.0` (xe đứng ở kho). Sao chép danh sách ứng viên vào tập hợp `remaining`.
    2. Vòng lặp `while remaining:` hoạt động liên tục cho đến khi không thể chèn thêm bất kỳ ai.
    3. Thiết lập hai biến theo dõi phương án tốt nhất toàn cục tại bước này: `best_delta = float("inf")` và `best_choice = None`.
    4. Vòng lặp lồng đôi duyệt qua từng khách hàng `cust` trong `remaining` và từng vị trí chèn `pos` khả dĩ trên tuyến đường hiện tại (chạy từ `0` đến `len(stops)`).
    5. Gọi hàm `try_insert_at_position`. Nếu phép chèn thành công và trả về thời gian về kho mới `new_return_time`, thuật toán tính toán độ tăng chi phí thời gian (marginal cost): `delta = new_return_time - return_time`.
    6. Nếu độ tăng chi phí này nhỏ hơn biến `best_delta` đang giữ, tiến hành cập nhật thông tin phương án tối ưu cục bộ: lưu lại giá trị `delta`, vị trí chèn, đối tượng khách hàng và mảng danh sách stop mới.
    7. Sau khi quét sạch không gian tìm kiếm của bước hiện tại, nếu `best_choice` vẫn là `None`, điều đó có nghĩa là toàn bộ các khách hàng còn lại trong danh sách không thể nhét vừa vào lộ trình hiện tại do nghẽn khung giờ hoặc xe không thể về kho trước 24:00. Vòng lặp lập tức ngắt (`break`).
    8. Ngược lại, chọn phương án có `delta` thấp nhất, cập nhật lại trạng thái tuyến đường (`stops = best_stops`, `return_time = best_ret_time`) và chính thức xóa khách hàng vừa được chọn ra khỏi tập `remaining`.

### 2.4. Hàm `earliest_window_end_in_week`
* **Mục tiêu:** Tính toán thước đo mức độ "khẩn cấp" (Deadline tổng thể) của một khách hàng trên phạm vi toàn bộ các ngày còn lại trong tuần.
* **Ý nghĩa toán học:** Để xếp hạng xem ai là người cần phục vụ trước, ta không thể chỉ nhìn vào ngày hôm nay. Nếu một khách hàng có một khung giờ cực kỳ hẹp vào thứ Ba, và đó là cơ hội duy nhất của họ trong tuần, họ phải được ưu tiên tuyệt đối so với một khách hàng khác tuy hôm nay cũng có lịch nhưng các ngày thứ Năm, thứ Sáu sau đó họ vẫn mở cửa đón xe. Hàm này tính toán một giá trị số hóa đại diện cho thời gian tuyệt đối trong tuần:
    $$	ext{Key} = 	ext{day} 	imes 1440 + 	ext{window.end}$$
    Giá trị này càng nhỏ thể hiện hạn định đóng cửa của khách hàng đó càng cận kề.

### 2.5. Hàm `weekly_scheduler`
* **Mục tiêu:** Hàm điều phối tổng thể chiến dịch logistics 7 ngày, áp dụng chiến lược kết hợp **EDF liên ngày (Earliest Deadline First)** và **Cheapest Insertion**.
* **Các bước thuật toán:**
    1. Khởi tạo bản ghi kết quả `WeeklyResult` và sao chép danh sách khách hàng vào bộ nhớ theo dõi hàng đợi toàn tuần `pending`.
    2. Chạy vòng lặp thời gian cuốn từng ngày: `for day in range(1, 8):`.
    3. Lọc ra danh sách `candidates` có lịch mở cửa trong ngày hôm đó.
    4. **Áp dụng chiến lược EDF (Phân loại ưu tiên):** Sắp xếp danh sách ứng viên này theo độ khẩn cấp giảm dần thông qua khóa sắp xếp là kết quả của hàm `earliest_window_end_in_week`. Việc đưa các khách hàng "khó tính", sắp hết hạn lên đầu danh sách duyệt sẽ giúp thuật toán Cheapest Insertion ưu tiên giữ chỗ và tìm vị trí chèn cho họ trước, tránh việc dồn các đơn hàng ngặt nghèo về cuối tuần dẫn đến đổ vỡ hệ thống đơn hàng.
    5. Gọi hàm `day_route_cheapest_insertion` để xây dựng lộ trình cho ngày hiện tại.
    6. Thu thập danh sách các mã khách hàng đã được giao thành công trong ngày, ghi nhận ngày giao vào bảng tra cứu tổng, và chính thức xóa bỏ họ khỏi hàng đợi toàn thời gian `pending`. Những khách hàng không giao được trong ngày hôm nay hoặc không được chọn làm ứng viên vẫn sẽ được giữ lại trong `pending` để tự động tham gia vào cuộc đua giành vị trí ở các ngày tiếp theo.
    7. Sau khi kết thúc ngày Chủ Nhật, những mã còn sót lại trong `pending` được đẩy vào mảng `unfulfilled`, hoàn tất lời giải của bài toán tuần.
