# Tài liệu Phân tích Hệ thống - Phần 1: Luồng xử lý Hệ thống, Kiến trúc và Cấu trúc Dữ liệu

Chào mừng bạn đến với tài liệu phân tích kỹ thuật chi tiết dành cho hệ thống lập lịch giao hàng tự động. Tài liệu này được thiết kế theo phong cách hướng dẫn từ trên xuống (Top-Down), giúp các thành viên trong đội ngũ phát triển nắm vững toàn bộ kiến trúc nền tảng trước khi đi vào mã nguồn chi tiết.

---

## 1. Bức tranh toàn cảnh & Luồng xử lý hệ thống (Overall Pipeline)

Hệ thống lập lịch này hoạt động theo mô hình **Khung thời gian cuốn (Rolling Horizon Framework)** để giải quyết bài toán Lập lộ trình xe có ràng buộc cửa sổ thời gian (VRPTW - Vehicle Routing Problem with Time Windows) trên phạm vi một tuần hoạt động (từ Ngày 1 đến Ngày 7). 

Dưới đây là chuỗi quy trình tuần tự gồm 6 giai đoạn chính mà hệ thống thực hiện từ khi khởi động cho đến khi xuất báo cáo:

```
[Dữ liệu CSV thô] 
       │
       ▼
1. Khởi tạo & Đọc dữ liệu (load_data) ──► Chuyển đổi định dạng giờ (parse_hhmm)
       │
       ▼
2. Quản lý Cửa sổ thời gian cuốn (Rolling Horizon Loop: Ngày 1 ──► Ngày 7)
       │
       ├──► Lọc ứng viên (candidates) có lịch trong ngày
       ├──► Sắp xếp mức độ khẩn cấp (EDF liên ngày hoặc Deadline nội ngày)
       │
       ▼
3. Xây dựng lộ trình ngày (DayRoute Construction)
       │
       ├──► Thử nghiệm vị trí chèn (try_insert_at_position hoặc nối đuôi)
       └──► Lan truyền dòng thời gian & Kiểm tra điều kiện biên (24h, Cửa sổ giờ)
       │
       ▼
4. Cập nhật trạng thái Toàn cục (State Update)
       │
       ├──► Ghi nhận đơn thành công ──► Xóa khỏi danh sách chờ (pending)
       └──► Hoãn lại đơn thất bại (Postponement) ──► Giữ lại trong pending cho ngày sau
       │
       ▼
5. Đánh giá Chỉ số Hiệu năng (compute_metrics) ──► Tỷ lệ hoàn thành, Quãng đường, Độ cân bằng
       │
       ▼
6. Kiểm định Độc lập (verify) ──► Rà soát toán học hộp đen, cam kết không lỗi logic
```

### Chi tiết luồng vận hành:
1. **Khởi tạo và Đọc dữ liệu (Data Loading):** Chương trình nạp hai tệp CSV cấu hình: `locations.csv` (chứa tọa độ không gian, nhu cầu hàng hóa, thời gian phục vụ) và `time_windows.csv` (chứa các khung thời gian yêu cầu nhận hàng của khách).
2. **Khởi tạo Đối tượng & Tiền xử lý (Object Creation & Preprocessing):** Dữ liệu thô được chuyển đổi thành các thực thể hướng đối tượng (`Customer`, `TimeWindow`). Các chuỗi ký tự dạng `HH:MM` được quy đổi đồng bộ sang đơn vị số nguyên nội bộ là **phút tính từ đầu ngày**. Khách hàng trung tâm (`DEPOT`) được phân tách riêng khỏi danh sách khách hàng cần phục vụ.
3. **Vòng lặp Cửa sổ thời gian cuốn (Rolling Horizon Loop):** Hệ thống khởi tạo một danh sách theo dõi toàn cục `pending` chứa tất cả khách hàng. Vòng lặp chính chạy tuần tự qua từng ngày từ ngày 1 đến ngày 7. Tại mỗi ngày, hệ thống lọc ra các khách hàng ứng viên (`candidates`) có đăng ký khung giờ mở cửa trong ngày đó.
4. **Sắp xếp & Thực hiện Chiến lược Lập lịch (Scheduling Logic):** Tập hợp ứng viên được sắp xếp theo một tiêu chí ưu tiên (ví dụ: Deadline đóng cửa sớm nhất, hoặc khối lượng nhu cầu nhỏ nhất) tùy thuộc vào chiến lược lựa chọn (Thuật toán chính hoặc các Thuật toán cơ sở). Sau đó, thuật toán lõi sẽ tiến hành xây dựng tuyến đường cho ngày đó (`DayRoute`).
5. **Lan truyền Thời gian & Kiểm tra Ràng buộc (Constraint Checking):** Khi thử nghiệm đưa một khách hàng vào tuyến đường, hệ thống thực hiện kiểm tra tính khả thi thông qua việc tính toán thời gian di chuyển, thời gian chờ, thời gian phục vụ, và quan trọng nhất là tính toán xem xe có kịp quay trở về kho trung tâm trước giới hạn cứng **24:00 (1440 phút)** hay không.
6. **Cập nhật trạng thái và Hoãn giao hàng (Postponement):** Khách hàng giao thành công sẽ được xóa khỏi `pending`. Khách hàng giao thất bại (do không tìm được vị trí chèn hợp lệ) vẫn nằm lại trong `pending` để tự động chuyển sang các ngày tiếp theo trong tuần (**Postponement/Deferral**).
7. **Đánh giá Chỉ số & Kiểm định Độc lập (Metrics & Verification):** Kết quả tổng hợp cả tuần được chuyển qua mô-đun `metrics.py` để chấm điểm chất lượng vận hành và mô-đun `verify.py` để chạy bộ kiểm toán hộp đen độc lập, cam kết không vi phạm bất kỳ quy định nào của đề bài.

---

## 2. Kiến trúc Mô-đun và Mối quan hệ Phụ thuộc (Module Dependencies)

Hệ thống được thiết kế theo nguyên lý phân tầng chức năng rõ ràng, đảm bảo tính đơn nhiệm (Single Responsibility Principle) và dễ bảo trì:

* **`data_model.py` (Tầng dữ liệu nền tảng):** Đây là nền móng của toàn bộ hệ thống. Tệp này hoàn toàn độc lập, không phụ thuộc vào bất kỳ mô-đun nội bộ nào khác. Nhiệm vụ của nó là định nghĩa cấu trúc dữ liệu cơ bản và cung cấp các phép toán hình học không gian (khoảng cách Euclid, tốc độ di chuyển).
* **`scheduler.py` (Tầng thuật toán chính):** Phụ thuộc trực tiếp vào `data_model.py`. Chứa thuật toán lõi của hệ thống: Chiến lược chèn tối ưu chi phí kết hợp bộ lọc hạn định thời gian trong tuần (Cheapest Insertion + EDF liên ngày).
* **`baselines.py` (Tầng chiến lược đối chứng):** Phụ thuộc vào cả `data_model.py` và `scheduler.py`. Tệp này tái sử dụng các hàm kiểm tra khả thi và cấu trúc thực thể để xây dựng 3 thuật toán heuristic kinh điển, phục vụ mục đích thiết lập mốc đối chứng thực nghiệm (baselines).
* **`metrics.py` (Tầng chấm điểm & KPI):** Phụ thuộc vào `data_model.py` và `scheduler.py`. Tiếp nhận giải pháp cuối cùng để bóc tách các chỉ số đo lường hiệu quả kinh tế và vận hành.
* **`verify.py` (Tầng kiểm định chất lượng phần mềm):** Phụ thuộc vào `data_model.py` và `scheduler.py`. Hoạt động như một kiểm toán viên độc lập, chạy các thuật toán rà soát hộp đen nhằm phát hiện các lỗi logic tiềm ẩn hoặc vi phạm ràng buộc đề bài trước khi xuất kết quả.

---

## 3. Phân tích Sâu các Cấu trúc Dữ liệu (Data Structures Deep Dive)

Việc sử dụng các lớp dữ liệu (`dataclass`) giúp mã nguồn tường minh và kiểm soát chặt chẽ trạng thái của các thực thể. Dưới đây là phân tích chi tiết từng cấu trúc dữ liệu được định nghĩa trong hệ thống.

### 3.1. Các lớp dữ liệu trong `data_model.py`

#### 1. Lớp `TimeWindow`
* **Vai trò:** Đại diện cho một cửa sổ thời gian mà khách hàng sẵn sàng mở cửa nhận hàng.
* **Thuộc tính:**
    * `start: int`: Mốc thời gian bắt đầu khung giờ (đơn vị: phút tính từ 00:00 của ngày).
    * `end: int`: Mốc thời gian kết thúc khung giờ (đơn vị: phút tính từ 00:00 của ngày).
* **Phương thức:**
    * `contains(self, t: int) -> bool`: Kiểm tra xem một mốc thời gian `t` bất kỳ có nằm trọn trong khung giờ này hay không (bao gồm cả hai đầu mút: `start <= t <= end`).
* **Vòng đời:** Được khởi tạo một lần duy nhất trong quá trình nạp tệp dữ liệu `time_windows.csv`, lưu trữ cố định bên trong đối tượng khách hàng và không bị thay đổi trong suốt quá trình chạy thuật toán.

#### 2. Lớp `Customer`
* **Vai trò:** Đại diện cho một nút giao dịch (khách hàng hoặc kho trung tâm) trên bản đồ logistics.
* **Thuộc tính:**
    * `id: str`: Mã định danh duy nhất (ví dụ: `"DEPOT"`, `"C001"`).
    * `name: str`: Tên gọi của khách hàng/địa điểm.
    * `x: float`, `y: float`: Tọa độ vị trí địa lý trên lưới tọa độ phẳng (đơn vị: km).
    * `demand: float`: Khối lượng hàng hóa cần giao (đơn vị: kg).
    * `service_time: int`: Thời gian cần thiết để thực hiện dỡ hàng, bàn giao chứng từ tại điểm (đơn vị: phút).
    * `windows: Dict[int, List[TimeWindow]]`: Từ điển quản lý lịch trình mở cửa. Khóa (`key`) là số thứ tự ngày từ $1 \dots 7$, giá trị (`value`) là danh sách các khung giờ hợp lệ trong ngày đó của khách hàng.
* **Phương thức bổ trợ:**
    * `has_any_window_on(self, day: int) -> bool`: Kiểm tra nhanh xem khách hàng này có lịch nhận hàng vào một ngày cụ thể nào đó hay không. Trả về `True` nếu ngày đó tồn tại trong từ điển và danh sách khung giờ không rỗng.
* **Vòng đời:** Được tạo ra ở giai đoạn nạp dữ liệu đầu tiên, đóng vai trò là cơ sở dữ liệu tĩnh tham chiếu xuyên suốt vòng đời ứng dụng.

---

### 3.2. Các lớp dữ liệu trong `scheduler.py`

#### 1. Lớp `Stop`
* **Vai trò:** Minh chứng cho một hành động ghé thăm thực tế của xe giao hàng tại một vị trí khách hàng cụ thể trong một lộ trình xác định.
* **Thuộc tính:**
    * `cust_id: str`: Mã định danh của khách hàng được phục vụ tại điểm dừng này.
    * `arrival: float`: Thời điểm chính xác đầu xe chạm bến khách hàng (đơn vị: phút trong ngày). Giá trị này có thể sớm hơn khung giờ yêu cầu của khách.
    * `service_start: float`: Thời điểm bắt đầu dỡ hàng thực tế. Nếu xe đến sớm (`arrival < window.start`), giá trị này sẽ bằng `window.start` (xe phải chịu thời gian chờ). Nếu xe đến đúng giờ hoặc trong khung, giá trị này bằng `arrival`.
    * `service_end: float`: Thời điểm xe hoàn thành công việc phục vụ và bắt đầu rời đi (`service_start + service_time`).
    * `window_used: TimeWindow`: Khung thời gian cụ thể được chọn để phục vụ trong số các khung giờ khả dụng của ngày hôm đó của khách hàng.
* **Vòng đời:** Được tạo ra tạm thời trong các phép thử chèn vị trí (`try_insert_at_position`), nếu phép chèn được chấp nhận và có chi phí tốt nhất, đối tượng này sẽ được đưa cố định vào mảng danh sách điểm dừng của ngày.

#### 2. Lớp `DayRoute`
* **Vai trò:** Quản lý toàn bộ lộ trình di chuyên và trạng thái vận hành của một xe trong một ngày cụ thể.
* **Thuộc tính:**
    * `day: int`: Ngày hoạt động trong tuần ($1 \dots 7$).
    * `stops: List[Stop]`: Danh sách chuỗi các điểm dừng theo thứ tự thời gian di chuyển từ đầu ngày.
    * `return_time: float`: Thời điểm xe quay trở về đến kho trung tâm sau khi kết thúc điểm dừng cuối cùng (đơn vị: phút). Xuất phát đầu ngày mặc định bằng `0.0`.
* **Phương thức bổ trợ:**
    * `served_ids(self) -> List[str]`: Trả về danh sách tất cả các mã khách hàng đã được phục vụ thành công trong ngày hôm nay theo đúng thứ tự di chuyển.
* **Vòng đời:** Khởi tạo vào đầu mỗi ngày giao hàng, liên tục được cập nhật, chèn thêm các `Stop` mới thông qua thuật toán lập lịch, và đóng gói lưu trữ khi kết thúc ngày công nhật.

#### 3. Lớp `WeeklyResult`
* **Vai trò:** Bản kế hoạch tổng thể, đại diện cho lời giải cuối cùng của cả chiến dịch logistics trong vòng một tuần.
* **Thuộc tính:**
    * `routes: Dict[int, DayRoute]`: Bản đồ ánh xạ từ số thứ tự ngày ($1 \dots 7$) sang đối tượng lộ trình `DayRoute` tương ứng của ngày đó.
    * `unfulfilled: List[str]`: Danh sách chứa mã định danh của các khách hàng "bị bỏ lại phía sau" – không thể sắp xếp giao hàng thành công trong suốt cả tuần hoạt động.
    * `delivered_day_of: Dict[str, int]`: Từ điển tra cứu nhanh, ánh xạ từ `cust_id` sang số thứ tự ngày mà khách hàng đó nhận được hàng thành công, hỗ trợ tăng tốc độ kiểm tra chéo dữ liệu.
* **Vòng đời:** Khởi tạo khi bắt đầu chạy thuật toán tuần, tích lũy dữ liệu lộ trình sau khi kết thúc mỗi ngày chạy qua cửa sổ cuốn, và là đầu ra cuối cùng cung cấp cho các mô-đun đánh giá chỉ số.
