# Tài liệu Phân tích Hệ thống - Phần 3: Phân tích 3 Chiến lược Cơ sở (Baseline Heuristics)

Tài liệu này đi sâu vào phân tích cấu trúc cấu tạo và nguyên lý hoạt động của 3 phương pháp lập lịch cơ sở (baselines) được định nghĩa trong tệp `baselines.py`. Các phương pháp này được thiết kế đúng theo các gợi ý trong đề bài nhằm thiết lập các cột mốc thực nghiệm để đánh giá định lượng sức mạnh của thuật toán chính.

---

## 1. Hàm bổ trợ chung: `_try_append_at_end`

Trước khi phân tích từng chiến lược, chúng ta cần hiểu hàm bổ trợ nội bộ `_try_append_at_end`. Đây là trung tâm kiểm tra khả thi được sử dụng bởi cả ba thuật toán cơ sở.

* **Tại sao hàm này cần thiết và vai trò đơn giản hóa:** Khác với thuật toán chính sử dụng hàm `try_insert_at_position` có khả năng tính toán chèn vào bất kỳ vị trí nào giữa tuyến đường và xử lý hiện tượng lan truyền độ trễ phức tạp, các thuật toán cơ sở áp dụng mô hình **Lập lịch nối đuôi (Append-only / List Scheduling)**. Nghĩa là, xe di chuyển tuần tự và đơn hàng mới luôn được thử nghiệm đặt vào **cuối tuyến đường hiện tại**. Hàm này giúp đóng gói toàn bộ logic kiểm tra khả thi đơn giản đó, giúp mã nguồn của các baseline cực kỳ gọn nhẹ. Nếu không có nó, logic kiểm tra cửa sổ giờ và quay về kho sẽ bị lặp đi lặp lại ở cả ba hàm baseline, gây nhiễu mã nguồn.
* **Tham số đầu vào:**
    * `current_stops (List[Stop])`: Danh sách các điểm dừng hiện tại của tuyến đường ngày.
    * `depot (Customer)`: Đối tượng kho trung tâm.
    * `all_points (Dict[str, Customer])`: Từ điển tra cứu nhanh tất cả đối tượng vị trí.
    * `new_cust (Customer)`: Khách hàng đang được thử nghiệm nối đuôi vào cuối tuyến.
    * `day (int)`: Ngày hiện hành.
* **Giá trị trả về:** Đối tượng `Stop` mới nếu việc nối đuôi hoàn toàn hợp lệ và an toàn; ngược lại trả về `None`.
* **Các bước thuật toán chi tiết:**
    1.  **Xác định điểm đứng trước hiện tại (Current Last Point):** Nếu tuyến đường hiện hành đang trống (`len(current_stops) == 0`), điểm xuất phát của xe chính là `depot` và mốc thời gian rời đi là `0.0`. Ngược lại, điểm đứng trước chính là điểm dừng cuối cùng hiện tại: `prev_stop = current_stops[-1]`, mốc rời đi là `prev_departure = prev_stop.service_end`.
    2.  **Tính toán thời gian đến điểm nối đuôi:** `arrival = prev_departure + travel_time_minutes(prev_point, new_cust)`.
    3.  **Kiểm tra cửa sổ thời gian:** Gọi hàm `earliest_feasible_service(arrival, new_cust.windows[day])`. Nếu kết quả trả về là `None` (xe đến muộn hơn giờ đóng cửa của khách hàng mới này), hàm lập tức trả về `None` để từ chối đơn hàng. Ngược lại, xác định được mốc phục vụ thực tế `service_start` và khung giờ sử dụng.
    4.  **Tính toán thời gian hoàn thành phục vụ tại điểm mới:** `service_end = service_start + new_cust.service_time`.
    5.  **Kiểm tra ràng buộc ca làm việc (Quay về kho trước nửa đêm):** Tính toán hành trình chạy thẳng từ điểm mới này về kho trung tâm: `return_time = service_end + travel_time_minutes(new_cust, depot)`. Nếu `return_time > 1440` (vượt quá 24:00), xe bị vi phạm quy định vận hành ngày, phép nối đuôi bị hủy bỏ, hàm trả về `None`.
    6.  Nếu vượt qua tất cả, khởi tạo và trả về đối tượng `Stop` hoàn chỉnh cho điểm cuối tuyến mới này.

---

## 2. Phân tích Chi tiết 3 Thuật toán Baseline

### 2.1. Baseline 1: Chiến lược Khách hàng Gần nhất (Nearest Neighbor - NN)
* **Kết nối Đề bài:** Đây chính là việc hiện thực hóa gợi ý: *"Giao hàng cho khách hàng gần nhất trước"*.
* **Tư duy thuật toán (Intuition):** Đây là thuật toán tìm kiếm tham lam theo không gian kinh điển. Tại mỗi bước, xe đang đứng ở vị trí điểm dừng cuối cùng, nó quét qua toàn bộ danh sách các ứng viên chưa được giao của ngày hôm đó, tính toán khoảng cách hình học và chọn ra người có khoảng cách **ngắn nhất** mà việc nối đuôi họ vẫn đảm bảo tính khả thi về mặt thời gian.
* **Các bước thuật toán chi tiết:**
    1. Khởi tạo tuyến đường ngày trống, đặt điểm vị trí hiện tại của xe là `current_point = depot`. Tạo bản sao danh sách ứng viên `remaining`.
    2. Vòng lặp `while remaining:` chạy liên tục cho đến khi danh sách ứng viên cạn kiệt.
    3. Thiết lập biến theo dõi khách hàng tốt nhất ở bước này: `best_cust = None` và khoảng cách ngắn nhất `min_dist = float("inf")`. Lưu lại cả đối tượng `Stop` tương ứng được sinh ra từ hàm bổ trợ là `best_stop = None`.
    4. Duyệt qua từng khách hàng `cust` trong `remaining`. Tính khoảng cách hình học đường chim bay bằng hàm `euclidean(current_point, cust)`.
    5. Nếu khoảng cách này nhỏ hơn `min_dist` hiện tại, thuật toán tiến hành gọi hàm `_try_append_at_end` để kiểm tra khả thi về mặt thời gian (ca làm việc và khung giờ). Nếu hàm bổ trợ trả về một đối tượng `Stop` hợp lệ, thực hiện cập nhật các biến theo dõi: `min_dist = d`, `best_cust = cust`, `best_stop = stop`.
    6. Sau khi kết thúc vòng duyệt toàn bộ ứng viên, nếu `best_cust` vẫn là `None` (không tìm thấy ai thỏa mãn hoặc những người còn lại đều ở quá xa/gây quá giờ), vòng lặp chính thức ngắt (`break`).
    7. Ngược lại, đưa `best_stop` vào danh sách lộ trình ngày, cập nhật điểm đứng hiện tại của xe về vị trí khách hàng vừa chọn (`current_point = best_cust`), và xóa khách hàng này ra khỏi tập `remaining` để chuyển sang bước tiếp theo.

### 2.2. Baseline 2: Chiến lược Hạn định đóng cửa sớm nhất (Earliest Deadline First Append)
* **Kết nối Đề bài:** Hiện thực hóa gợi ý: *"Giao hàng cho khách hàng có khung thời gian kết thúc sớm nhất trước"*.
* **Tư duy thuật toán (Intuition):** Thuật toán này bỏ qua hoàn toàn yếu tố khoảng cách hình học không gian, chỉ tập trung giải quyết áp lực thời gian cục bộ trong ngày. Nó sắp xếp cứng danh sách ứng viên theo thứ tự đóng cửa tăng dần, sau đó duyệt qua danh sách này đúng một lần duy nhất để thực hiện nối đuôi theo cơ chế lập lịch danh sách (List Scheduling).
* **Các bước thuật toán chi tiết:**
    1. Định nghĩa một hàm xếp hạng nội bộ: `day_deadline(c: Customer)`, hàm này duyệt qua danh sách khung giờ mở cửa **trong ngày hiện hành** của khách hàng, tìm ra mốc kết thúc sớm nhất `min(w.end for w in c.windows[day])`.
    2. Thực hiện sắp xếp cố định toàn bộ danh sách ứng viên của ngày theo khóa này: `ordered = sorted(candidates, key=day_deadline)`.
    3. Khởi tạo tuyến đường ngày trống. Tiến hành chạy một vòng lặp duy nhất duyệt qua danh sách đã sắp xếp: `for cust in ordered:`.
    4. Tại mỗi khách hàng, gọi hàm bổ trợ `_try_append_at_end`. Nếu kết quả trả về hợp lệ, lập tức đưa đối tượng `Stop` này vào cuối lộ trình ngày và chuyển sang người tiếp theo. Nếu trả về `None` (xe đến muộn hoặc không kịp về kho), khách hàng này bị bỏ qua lập tức trong ngày hôm nay, thuật toán chuyển ngay sang người tiếp theo mà không thực hiện bất kỳ hành động tìm kiếm vị trí chèn thay thế nào.

### 3.3. Baseline 3: Chiến lược Hạn chế tối đa việc hẹn lại (Minimize Deferral / Maximum Packing)
* **Kết nối Đề bài:** Hiện thực hóa gợi ý: *"Tìm cách giảm thiểu số lượng đơn hàng phải hoãn lại sang ngày hôm sau"*.
* **Tư duy thuật toán (Intuition):** Để giảm thiểu số lượng đơn hàng bị hoãn lại, mục tiêu tối thượng là phải nhồi nhét được **nhiều đầu đơn hàng nhất có thể** vào lộ trình một ngày, chấp nhận xe phải di chuyển vòng vèo hoặc tốn thời gian hơn. Thuật toán này áp dụng nguyên lý: ưu tiên xử lý các đơn hàng có nhu cầu khối lượng (`demand`) nhỏ trước (giống như việc xếp các viên đá nhỏ vào bình trước để tối đa hóa số lượng hạt). Đặc biệt, khác với Baseline 1 và 2 chỉ nối đuôi, Baseline 3 sử dụng hàm thuật toán chính `try_insert_at_position` để tìm mọi vị trí chèn khả dĩ trong tuyến nhằm tăng tối đa cơ hội giữ lại đơn hàng trong ngày.
* **Các bước thuật toán chi tiết:**
    1. Thực hiện sắp xếp danh sách ứng viên theo thứ tự nhu cầu khối lượng hàng hóa tăng dần: `ordered = sorted(candidates, key=lambda c: c.demand)`.
    2. Khởi tạo lộ trình ngày trống. Duyệt qua từng khách hàng trong danh sách đã sắp xếp: `for cust in ordered:`.
    3. Với mỗi khách hàng, thuật toán áp dụng chiến lược **Chấp nhận phương án đầu tiên khả thi (First-Fit Strategy)**: chạy chỉ mục vị trí chèn `pos` từ đầu tuyến đến cuối tuyến hiện tại (`range(len(stops) + 1)`).
    4. Tại mỗi vị trí, gọi hàm thuật toán chính `try_insert_at_position`. Chỉ cần hàm này trả về kết quả hợp lệ đầu tiên (thỏa mãn cửa sổ giờ và xe về kho trước 24:00), thuật toán lập tức chấp nhận phương án này, cập nhật toàn bộ danh sách điểm dừng của ngày, ngắt vòng lặp tìm kiếm vị trí (`break`), và chuyển sang xử lý khách hàng tiếp theo.
