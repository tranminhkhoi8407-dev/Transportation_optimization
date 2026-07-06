# Tài liệu Phân tích Hệ thống - Phần 4: Chỉ số Hiệu năng và Cơ chế Kiểm định Độc lập

Tài liệu này tập trung phân tích hai mô-đun quan trọng đóng vai trò quản lý chất lượng và đánh giá toán học cho toàn bộ hệ thống lập lịch: `metrics.py` (Bộ đo lường KPI) và `verify.py` (Trình kiểm định độc lập).

---

## 1. Kết nối Hệ thống với Yêu cầu Đề bài

* **Đề xuất cách đánh giá chất lượng (Yêu cầu 2 trong Đề bài):** Đề bài yêu cầu thí sinh phải đề xuất các tiêu chí đánh giá chất lượng của kế hoạch lập lịch và nêu rõ tiêu chí nào được ưu tiên hơn. Mô-đun `metrics.py` chính là sự cụ thể hóa yêu cầu này bằng cách định nghĩa cấu trúc dữ liệu `WeeklyMetrics` gồm 5 chỉ số logistics chuẩn mực, được sắp xếp theo một hệ thống cấp bậc ưu tiên logic phục vụ trực tiếp cho việc lập luận trong báo cáo cuộc thi.
* **Tính đúng đắn và khả thi của lời giải:** Cuộc thi yêu cầu các ràng buộc phải được tuân thủ tuyệt đối. Mô-đun `verify.py` hoạt động độc lập với tầng thuật toán, đóng vai trò như một bộ chấm bài thử nghiệm (Local Judge) để đảm bảo không có bất kỳ sai số tích lũy nào làm hỏng tính hợp lệ của lời giải trước khi nộp bài.

---

## 2. Phân tích Bộ Chỉ số Hiệu năng (`metrics.py`)

Hàm `compute_metrics(depot, customers, result: WeeklyResult) -> WeeklyMetrics` tiếp nhận kết quả lập lịch cuối cùng để bóc tách các chỉ số đo lường hiệu quả kinh tế và vận hành của hệ thống dưới góc độ quản lý chuỗi cung ứng:

### 2.1. Tỷ lệ hoàn thành đơn hàng (Completion Rate - Ưu tiên số 1)
* **Ý nghĩa:** Đây là chỉ số sống còn của mọi hệ thống điều phối logistics. Một lộ trình di chuyển rất ngắn nhưng bỏ sót nhiều đơn hàng của khách là một giải pháp thất bại hoàn toàn.
* **Công thức lập trình:**
    $$	ext{Completion Rate} = \left( rac{	ext{Số lượng đơn hàng giao thành công}}{	ext{Tổng số lượng khách hàng đầu vào}} ight) 	imes 100\%$$
    Trong mã nguồn, giá trị này được tính thông qua số lượng phần tử của bảng tra cứu `result.delivered_day_of` chia cho tổng số lượng của từ điển `customers`.

### 2.2. Tổng quãng đường di chuyển (Total Travel Distance - Ưu tiên số 2)
* **Ý nghĩa:** Phản ánh trực tiếp chi phí biến đổi vận hành thực tế của doanh nghiệp (chi phí nhiên liệu, hao mòn lốp xe, khấu hao phương tiện).
* **Logic tính toán:** Thuật toán duyệt qua lộ trình của từng ngày. Nếu ngày đó xe có hoạt động (`len(route.stops) > 0`), tổng quãng đường của ngày được tích lũy tuần tự từ ba thành phần:
    1. Chặng xuất phát: Từ kho trung tâm `depot` đến điểm dừng đầu tiên `route.stops[0]`.
    2. Các chặng giữa: Khoảng cách giữa các điểm dừng liên tiếp liên danh trong mảng `euclidean(point_a, point_b)`.
    3. Chặng quay về: Từ điểm dừng cuối cùng `route.stops[-1]` quay trở lại kho trung tâm `depot`.

### 2.3. Tổng thời gian chờ (Total Waiting Time - Ưu tiên số 3)
* **Ý nghĩa:** Thời gian xe phải đỗ tắt máy đứng chờ trước cửa nhà khách hàng do đến sớm hơn khung giờ mở cửa yêu cầu. Đây là thời gian "chết" không tạo ra giá trị thặng dư kinh tế, cần phải tối thiểu hóa bằng cách tối ưu hóa chuỗi thứ tự di chuyển.
* **Công thức lập trình:** Với mỗi điểm dừng `Stop`, thời gian chờ được tính bằng hiệu số: `waiting_minutes = stop.service_start - stop.arrival`. Chỉ số tổng tuần thu được bằng cách cộng dồn tất cả các giá trị này trên toàn bộ các ngày.

### 2.4. Độ cân bằng khối lượng công việc (Route Duration Balance - Ưu tiên số 4)
* **Ý nghĩa:** Đảm bảo tính bền vững và công bằng cho tài xế, tránh tình trạng "ngày làm việc kiệt sức 24 tiếng, ngày lại không có việc làm" gây quá tải nhân lực.
* **Công thức toán học áp dụng:** Thuật toán thu thập thời gian quay về kho của tất cả các ngày xe có hoạt động (`active_return_hours`), tính toán giá trị trung bình ($\mu$), sau đó áp dụng công thức tính độ lệch chuẩn ($\sigma$):
    $$\sigma = \sqrt{rac{1}{N} \sum_{i=1}^N (h_i - \mu)^2}$$
    Chỉ số độ lệch chuẩn này càng nhỏ chứng tỏ khối lượng ca làm việc giữa các ngày trong tuần càng cân bằng.

### 2.5. Tỷ lệ đơn hàng bị hẹn lại (Deferral Rate - Ưu tiên số 5)
* **Ý nghĩa:** Đo lường mức độ ảnh hưởng đến trải nghiệm khách hàng. Nếu khách hàng mong muốn nhận hàng vào thứ Hai nhưng hệ thống hoãn đến tận thứ Sáu mới giao (dù vẫn thỏa măn khung giờ thứ Sáu), điều này vẫn làm giảm mức độ hài lòng của khách.
* **Logic tính toán:** Với mỗi khách hàng được giao thành công, thuật toán rà soát lại cơ sở dữ liệu gốc để tìm ra ngày sớm nhất trong tuần mà khách hàng đó từng khai báo có mở cửa. Nếu ngày giao thực tế lớn hơn ngày sớm nhất đó, đơn hàng được tính là đã bị hẹn lại ít nhất một lần.

---

## 3. Phân tích Cơ chế Kiểm định Độc lập (`verify.py`)

Hàm `verify(depot, customers, result: WeeklyResult)` đóng vai trò là một kiểm toán viên độc lập chạy các thuật toán rà soát hộp đen nhằm phát hiện các lỗi logic tiềm ẩn hoặc sai số tích lũy dấu phẩy động. Nó thực hiện kiểm tra 4 quy tắc nghiêm ngặt:

1.  **Kiểm tra tính nhất quán của dòng thời gian (Time Consistency Check):** Thuật toán tự chạy một dòng thời gian độc lập dọc theo tuyến đường ngày. Nó tính toán thời gian cập bến lý thuyết dựa trên khoảng cách Euclid giữa điểm đứng trước và điểm đứng sau, sau đó so sánh trực tiếp với giá trị `arrival` ghi nhận trong đối tượng `Stop`. Nếu độ lệch tuyệt đối vượt quá ngưỡng sai số cho phép `EPS = 1e-6`, hệ thống lập tức phát hiện lỗi tính toán dòng thời gian:
    $$\left| 	ext{expected\_arrival} - 	ext{stop.arrival} ight| > 	ext{EPS}$$
2.  **Kiểm tra tính logic của hành động chờ:** Đảm bảo thời điểm bắt đầu phục vụ thực tế không được phép xảy ra trước khi đầu xe chạm bến khách hàng (`stop.service_start >= stop.arrival - EPS`).
3.  **Kiểm tra tính hợp lệ của Cửa sổ thời gian:** Xác thực mốc thời gian bắt đầu phục vụ `service_start` phải nằm trọn vẹn trong khoảng đóng-mở của khung giờ được sử dụng, và khung giờ đó phải là một khung giờ có thật được khai báo trong file dữ liệu gốc của khách hàng tại đúng ngày đang xét.
4.  **Kiểm tra tính toàn vẹn của tập hợp (Set Integrity Check):** Sử dụng các phép toán tập hợp của Python để đảm bảo tính nhất quán của giải pháp trên quy mô toàn tuần:
    * Không có hiện tượng một khách hàng bị giao trùng lặp hai lần trong tuần (sử dụng thuộc tính kiểm tra tập hợp `served_overall`).
    * Không có hiện tượng một khách hàng vừa được ghi nhận giao thành công vừa nằm trong danh sách không hoàn thành (`result.unfulfilled`).
    * Tổng hợp của tập giao thành công và tập thất bại phải trùng khớp hoàn toàn với danh sách khách hàng ban đầu, không được thừa hoặc thiếu bất kỳ một đơn hàng nào.
